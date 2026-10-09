# 사용자 승인 후 TEST 데이터 동기화·Production 동일 이미지 배포

## 요청 배경과 목표

사용자가 카드 사진 확대·모바일 점선 박스 중앙 정렬의 TEST 결과를 확인한 뒤 “좋아 운영 DB에도 마이그레이션 시키고, 운영 서버도 배포해줘”라고 명시적으로 승인했다. 이번 배포에는 TEST에서 검증한 전체 종 보전 출처 처리와 최신 카드 UI가 포함된다. 이전의 운영 승인 대기는 이번 릴리스에 한해 해제되며, 향후 별도 변경까지 포괄적으로 승인된 것으로 해석하지 않는다.

목표는 TEST의 최신 데이터를 운영에 반영하고, 실제 검증한 이미지를 재빌드 없이 운영 설정으로 실행한 뒤 DB·공개 API·브라우저 표시를 검증하는 것이다. 운영에만 존재하는 수집 이력은 보존한다. 인증 정보는 문서나 Git에 저장하지 않는다.

관련 이전 작업:

- `docs/work-log/2026-10-09-card-photo-layout-test-only.md`: PC 사진 확대·모바일 자료 없음 박스 정렬과 TEST 검증. 당시 운영 미배포라는 기록은 그 작업 시점의 사실로 유지한다.
- 이번 앱 릴리스 기준 커밋 `a2c8bcc374211f0c8d3cb7b2964114e1fdf7d043`. `63a478b`는 이후 검증 도구·문서 변경이며 앱 CSS/JS는 같다.

## 사전 조사와 원인·근거

단순한 행 개수 비교로는 TEST/운영 데이터가 같다고 판단할 수 없어 실제 DB 내용을 비교했다. `quality_audit_report` 에이전트의 읽기 전용 검토에서 전체 내용 해시, 운영 전용 수집 이력 보존, 운영 역할 소유권·외래키·시퀀스 검사, 동일 이미지 승격을 점검했다. 주 에이전트가 실제 이관과 배포를 수행했다. 이번 배포에 Claude·Antigravity가 직접 참여했다고 기록하지 않는다.

### Neo4j: 이미 전체 데이터가 같음

- TEST는 Mac mini의 `neo4j-test`(5.26.30), 운영은 NAS의 `neo4j`(2026.08.1)이다.
- 각 노드의 라벨·전체 속성을 정규화한 JSON의 SHA-256을 계산하고, 라벨 조합별로 정렬한 행 해시를 다시 해시했다. 모든 관계는 방향·타입·전체 속성·양 끝 노드의 라벨/속성을 함께 해시했다. 내부 element ID와 버전별 저장 형식은 비교에서 제외했다.
- 노드 475,063개, 관계 543,728개, 노드 라벨 조합 28개, 관계 타입 19개가 모두 일치했다. 각 그룹의 **전체 속성 및 관계 내용 해시도 일치**했다. 인덱스는 ONLINE, 제약 조건도 동일했다. Neo4j 버전 사이의 `NODE_PROPERTY_UNIQUENESS`/`UNIQUENESS` 명칭만 정규화했다.
- 따라서 최신 TEST 그래프 데이터는 이미 운영에 반영되어 있었다. 이번 작업에서는 그래프 DB를 덮어쓰거나 재시작하지 않았다. 불필요한 Neo4j dump/restore도 실행하지 않았다.
- 사전 전체 검사에는 각 환경 약 4분 30초가 소요됐다. 배포 후에는 그래프의 개수·라벨·타입·인덱스/제약과 컨테이너 시작 시각을 재확인했다. 배포 후 전체 그래프 해시를 다시 계산했다고 주장하지 않는다.

### PostgreSQL: 수집 시각·실행 이력 차이

NAS `postgres-n8n`의 TEST DB `robingraph_test`, 운영 DB `robingraph`에 있는 앱 소유 `ingest` 스키마만 대상으로 했다. 두 DB 모두 8개 테이블의 개수는 같았지만 5개 테이블의 전체 행 해시는 달랐다.

| 테이블 | 사전 TEST/운영 행 수 | 확인한 차이 | 이관 후 운영 |
|---|---:|---|---:|
| `_schema_migration` | 4 | 동일 | 4 |
| `ingest_state` | 6 | 1행의 마지막 성공 실행 ID·수정 시각 | 6 |
| `ingestion_run` | 35 | 동일한 공통 34행 + 각 환경 전용 1행 | **36** |
| `outbox_event` | 0 | 동일 | 0 |
| `quarantine_item` | 2,344 | 동일 | 2,344 |
| `source_dataset` | 15 | 1행의 생성·수정 시각 | 15 |
| `source_record` | 57,716 | 45행의 조회 시각·실행 ID·생성 시각 | 57,716 |
| `source_release` | 12 | 1행의 조회·생성 시각 | 12 |

기본키별 전체 행/필드 해시로 차이를 조사했다. `source_record` 45행은 **payload·원문 SHA·출처 릴리스·파서·정책 등 자료 자체는 같고**, `retrieved_at`, `ingestion_run_id`, `created_at`만 달랐다. 즉 기존 데이터 불일치는 새의 설명/등급 내용보다 서로 다른 환경의 수집 실행 메타데이터에서 발생했다. 실행 중/대기 수집은 0건이었다.

## 이관 방식과 변경 전후

1. 운영 `ingest` 전체를 SQL dump로 백업하고 TEST `ingest` dump를 준비했다. 운영의 기존 `ingestion_run` 35행은 별도 보존 SQL로 저장했다.
2. 운영 API를 정지한 상태에서 TEST dump, 기존 운영 실행 이력 `INSERT … ON CONFLICT DO NOTHING`, 운영 역할 소유권 복구 SQL을 `psql --single-transaction -v ON_ERROR_STOP=1`로 한 트랜잭션에서 실행했다.
3. 공통 34개 실행은 충돌 무시로 중복되지 않는다. TEST 전용 1개와 운영 전용 1개를 모두 보존해 운영 실행 이력은 정확히 36개가 됐다. 기본키 및 각 행/필드 해시의 합집합과 일치함을 확인했다.
4. 나머지 7개 테이블은 TEST 전체 내용과 일치한다. 45개 원자료 행의 수집 메타데이터도 TEST 값으로 동기화했다. 운영 전용 실행 행을 보존했다고 해서 이전 45개 행의 메타데이터 버전까지 활성 DB에서 보존한 것은 아니다. 이전 상태는 운영 전체 SQL 백업에 남아 있다.
5. `ingest` 스키마·8개 테이블·2개 시퀀스는 운영 역할 `robingraph_app` 소유로 복구했다. 공유 n8n DB·스키마·워크플로는 변경하지 않았다.

### 실제 발생한 복원 실패와 복구

첫 시도는 2026-10-09 13:52:01 UTC에 운영 API를 정지한 뒤, 소유권 변경 루프가 테이블보다 시퀀스를 먼저 처리해 실패했다. PostgreSQL은 `outbox_event_id_seq`가 `outbox_event` 테이블에 연결되어 있으므로 단독으로 먼저 소유자를 바꿀 수 없다고 반환했다.

- 단일 트랜잭션 전체가 롤백됐고 기존 운영 API를 다시 시작했다.
- 기존 이미지 `robingraph-api:prod-readable-5fce6eb`가 healthy인 것을 확인했다. 운영 8개 테이블의 전체 내용 해시가 이관 전과 완전히 같음을 재검증했다. `…-rollback-confirmation.json`에 실제 결과를 기록했다.
- 소유권 처리 순서를 `ORDER BY (c.relkind='S'), c.relname`으로 수정해 **테이블을 먼저, 시퀀스를 나중에** 변경했다.
- 두 번째 시도: API 정지 13:52:57 UTC, PG 복원 commit 13:53:00 UTC, 새 운영 API 시작 13:53:00.901732645 UTC. 한국 시간은 각각 2026-10-09 22:52:57, 22:53:00, 22:53:00.901732645이다.
- 성공 후 health 확인을 완료했다. 외부 사용자 관점의 전체 중단 시간을 별도로 측정하지 않았으므로 위 시각 차이를 정확한 서비스 중단 시간이라고 주장하지 않는다.
- SSH stdin으로 보낸 실행 스크립트의 마지막 로그 일부가 compose/verify의 stdin 소비로 출력되지 않아, 독립적인 후속 `docker inspect`로 이미지·상태·재시작 수를 재확인했다. DB 이관을 중복 실행하지 않았다.

## 운영 이미지·환경 및 백업

- 공개 운영 URL: https://robingraph.dove-nest.com/chat
- 운영 컨테이너: `robingraph-api`.
- 운영 태그: `robingraph-api:prod-card-photo-a2c8bcc`.
- TEST 태그: `robingraph-api:test-card-photo-a2c8bcc`.
- 양쪽 실제 이미지 ID: `sha256:6d98571a254d1e686f11fc8a4b197da87b2b40ee449c9746a33ce9141d32ede2`.
- OCI revision: `a2c8bcc374211f0c8d3cb7b2964114e1fdf7d043`.
- 이미 검증한 TEST 이미지를 `docker tag`로 승격하고 `docker compose … up -d --no-build api`로 실행했다. 재빌드로 의존성을 바꾸지 않았다.
- NAS 릴리스 디렉터리: `/home/kimdove/RobinGraph-prod-card-photo-a2c8bcc`.
- 릴리스 archive SHA-256: `03559cefd9cf16fc655b7f0088255830af9dcea8ccc57220ea123d29c1347a7d`.
- 기존 운영 `.env.nas.prod`를 `/home/kimdove/RobinGraph-readable-5fce6eb`에서 복사하고 이미지 태그만 변경했다. 실제 DB `robingraph`, PG 역할 `robingraph_app`, Neo4j URI `bolt://neo4j:7687`, `serve-neo4j`, 배포 대상 `prod`를 확인했다. TEST 자격 증명을 운영에 복사하지 않았다.
- `deploy_nas.sh preflight`와 `verify` 통과. TEST/운영 모두 healthy, 재시작 0. Neo4j 운영 컨테이너 시작 시각은 기존 `2026-10-09T10:01:22.437998406Z` 그대로였다.

NAS 백업: `/volume3/Birds-Nest/backups/robingraph-deploy/approved-20261009T134305Z` (umask 077).

| 파일 | SHA-256 | 용도 |
|---|---|---|
| `prod-ingest-before.sql` | `e18621040d93f4199078d4aec2d20c5214cc7f286b38e4bec4f56b763d561217` | 이전 운영 전체 ingest 복구, 31,681,124 bytes |
| `test-ingest.sql` | `9c5c591bece89d70fc9f20d3a6d1e916ae7e1407dd8dd0f356fa0af1dc351f00` | 적용한 TEST dump, 31,681,124 bytes |
| `prod-ingestion-runs-preserve.sql` | `4760b1773f283db26b4017a4f61ca8776583fd977783e0393c905c9294732c23` | 기존 운영 실행 이력 보존 |

소유권 SQL·복원 로그도 이 폴더에 보관했다. 준비된 `prod-neo4j`/`test-neo4j` 디렉터리는 비어 있으며 이번 작업의 새 Neo4j 백업이라고 기록하지 않는다. DB dump와 기본키별 비공개 상세 자료는 Git/Obsidian에 올리지 않는다.

롤백 시에는 API를 정지하고 `prod-ingest-before.sql`과 운영 소유권 SQL을 단일 트랜잭션으로 복원한 뒤, 기존 운영 이미지 `robingraph-api:prod-readable-5fce6eb`를 재빌드 없이 실행한다. 기존 이미지·환경 디렉터리·SQL은 유지했다. 성공 후 롤백 절차를 실제 실행한 것은 아니다. 실패했던 첫 트랜잭션의 자동 롤백과 기존 앱 재시작만 실제 검증했다.

## 실제 검증 결과

### DB 검증

- 사전 실제 Neo4j 전체 내용 동등성: 노드 475,063개·관계 543,728개, 전체 속성/방향/끝점 내용 해시 일치.
- 이관 후 PG: `ingestion_run`을 제외한 7개 테이블 전체 행 해시·행 수가 TEST와 일치. 실행 이력은 TEST와 이전 운영의 정확한 합집합 36건으로 검증했다.
- 운영 app 역할로 DB 접속 확인. 스키마·8개 테이블·2개 시퀀스 소유권 일치, 제약 43개(외래키 11개 포함) 전부 validated.
- 시퀀스 값 및 `is_called`는 TEST와 일치: `outbox_event_id_seq` 2,928/true, `quarantine_item_id_seq` 2,662/true. 이 검증에서 `nextval`을 호출하지 않았다.
- 실행 이력 상태: succeeded 14, failed 22, pending/running 0. failed 22는 기존 과거 수집 이력으로, 이번 이관 작업 실패 22건이라는 뜻이 아니다. outbox 0.
- 사후 Neo4j 개수·라벨·타입·인덱스/제약 재검사 통과. 그래프 복원/재시작 없이 기존 내용을 유지했다.

### 운영 11,131종 보전 표시 전수 검사

운영 DB의 실제 모든 종 행을 **운영 이미지의 reader로 일괄 처리**하고, 해당 payload를 프런트엔드 `conservationInfo`에 넣어 검사했다. 11,131건의 HTTP 요청이나 브라우저 DOM 검사로 표현하지 않는다.

- 처리 11,131 / 오류 0. 모든 보전 payload가 이전 TEST 전수 검사 결과와 일치한다.
- 상태: linked_checklist 7,507, snapshot_only 2,816, needs_review 807, manual_override 1.
- 참고 평가 출처: GBIF 385, BirdBase 117, 홍콩 조류학회 HKBWS 9. 참고 평가가 없는 종 10,620에는 정상 연결 등급이 있는 종도 포함되며 전부 미확인이라는 뜻이 아니다.
- 실제 표시 등급: LC 8,502 · NT 926 · VU 653 · EN 360 · CR 206 · EX 148 · EW 5 · DD 35.
- 알려진 등급의 뱃지 코드·색상 매핑·IUCN 뱃지 유무·참고 평가 수용 검사: 실패 0. 미확인 색상 331 = 근거 미연결 296 + DD 35.
- **등급 근거 미연결 296종은 남아 있다.** 이번 배포가 모든 종의 보전 정보 원문 정확성을 새롭게 독립 검증했다는 의미는 아니다. 이전 미해결 목록과 근거를 유지한다.

### 공개 HTTPS/API와 정적 자산

- 실제 운영 HTTPS `/health`, `/openapi.json`, `/v1/taxa/lineage`와 계약/값 검사 통과. 국명 `대륙검은지빠귀`는 `Turdus mandarinus`, `source-reference`로 조회됐다. schema drift·response drift·canary issues 모두 0.
- `/health`의 `fixture-avlist-2025`는 fixture 프로세스 자료의 릴리스이고 lineage의 `v2025b`는 실제 AviList 개념집합 릴리스다. 서로 다른 데이터 영역이므로 값이 다른 것은 배포 오류가 아니다. 운영 health의 배포 대상은 `prod`였다.
- 실제 공개 POST `/v1/chat`, `intent:auto`, 추가 설명/관계 탐색 지연: 박새→`Parus cinereus`, 까치→`Pica serica`, 큰부리까마귀→`Corvus macrorhynchos`, 청둥오리→`Anas platyrhynchos` 모두 HTTP 200·profile·정상 답변, 경고 0. 각각 0.801/0.713/0.774/0.802초였다(2개 병렬 요청, 일회성 측정). 모두 deterministic 라우팅이므로 Jev API 호출/지연 검증으로 주장하지 않는다.
- 운영·TEST·로컬 CSS SHA-256은 `e1ac11fe342c6959a605c5182306ef6ba990030e8aacc5378f031cdb9db8f9a1`, JS SHA-256은 `ed25611f02e0d79e79429c6e94b6912592472dde4e98ffd00d39f6e4387b4d79`로 일치한다.

### 운영 실제 Chrome 카드 검사

- 운영에서 세 종의 프로필을 **새로 조회**했다. 이전 TEST 캐시나 로컬 CSS interception을 사용하지 않았다. 실제 운영 CSS/JS와 같은 앱 카드 함수로 표시했다. 자연어 답변 전체 UI의 클릭 과정은 별도 API 검사와 구분한다.
- PC 1280×900·1280×700, 모바일 390×844·320×640에서 청둥오리·도도·까치 12개 화면 + PC/모바일의 자료 없음·긴 설명 합성 변형 4개: **16 통과, 실패 0, 건너뜀 0**.
- 기본 앞뒷면 화면 맞춤·동일 카드 높이·휠 입력 후 내부 scrollTop 0·PC 사진 비율 7:6·점선 박스와 열/제목 중심 차이 1px 미만을 확인했다. 사진 전환 4회, 모바일 CDP 터치 스와이프 8회 통과, page error 0.
- 운영 1280×900 청둥오리 사진은 약 361.79×310.10px이다. 종별 카드 축소 배율에 따라 최종 px는 다르지만 동일 비율과 무스크롤 기본 화면을 확인했다.
- 실제 프로필 화면의 주 사진 decode는 성공했다. hidden lazy 사진은 별도 decode 5초 제한에서 성공하지 않은 경우도 있어 모든 이미지 decode 성공이라고 표현하지 않는다. 자료 없음 합성 변형은 이미지 0개로 정상이다.
- 32개 스크린샷: `/tmp/rg-approved-prod-browser/`. PC 청둥오리 앞면과 모바일 까치 뒷면을 직접 열어 사진/박스 정렬을 확인했다. 큰 PNG들을 Git에 추가하지 않았다.
- 기존 상세 토글을 펼치면 가독성을 위해 스크롤을 허용하는 기능이 있다. 이번 무스크롤 결과는 토글을 닫은 기본 양면 상태다. 실제 휴대폰·Safari 실행 결과가 아니라 Chrome 모바일 에뮬레이션이다.
- 기존 검증 도구 출력에 TEST라는 고정 설명이 있어 저장한 운영 결과 JSON에 실제 실행 URL·fresh PROD 자료임을 명시했다. 공통 도구의 설명도 URL 기반으로 수정했으며 검사 단정은 바꾸지 않았다.

## 변경 파일·검증 산출물

앱 코드·DB 스키마를 새로 변경하지 않았다. 배포한 앱은 이미 TEST에서 검증한 `a2c8bcc` 그대로다. 이번 저장소 변경은 작업 문서, 검증 결과/재현 도구와 기존 카드 검증 도구의 환경 설명이다.

`docs/verification/assets/2026-10-09-approved-production-*`:

- `test-before.json`, `prod-before.json`, `db-before-comparison.json`: 실제 사전 전체 DB 감사와 비교.
- `pg-difference-summary.json`, `record-difference-summary.json`: 환경별 차이·45행 차이 필드.
- `prod-after.json`, `db-after-comparison.json`: 이관 후 전체 PG 해시, 그래프 구조, 합집합 보존 결과.
- `pg-metadata.json`, `pg-metadata-checks.json`: 운영 역할·소유권·시퀀스·제약 결과.
- `rollback-confirmation.json`: 첫 실패 후 실제 데이터/이미지 복구 검증.
- `container-state.txt`, `asset-hashes.json`: 실제 이미지 ID·health·재시작·공개 자산 일치.
- `public-contract.json`, `public-samples.json`: 공개 계약/국명·자연어 질문 확인.
- `conservation-runtime-summary.json`, `conservation-display.json`: 실제 전종 reader 검사·표시 검사. 17MB 전체 payload 대신 집계·입출력 해시를 저장했다.
- `browser.json`: 운영 카드 16가지 실측 결과.
- `db-audit.py`, `db-compare.py`, `pg-audit.py`, `pg-metadata.py`: 읽기 전용 재현 도구. DB 환경변수는 실행 컨테이너에 이미 주입된 값을 사용하고 출력하지 않는다. `db-compare.py`는 완전 동등성 비교라 이번 intentional 이력 합집합의 사후 비교에는 그대로 적용하지 않는다.

Python 백엔드/Node 전체 테스트는 이번 배포에서 재실행하지 않았다. 앱 코드 변경이 없고 같은 이미지를 승격했으며 실제 운영 DB/API/카드 검증을 수행했다. 이전 CSS 구현 뒤 실행한 Node 296 통과(실패/건너뜀 0)는 이전 문서에 기록되어 있다. CI 상태는 이번에 조회하지 않았다.

## 문서·커밋·남은 사항

이 문서와 검증 산출물을 `dev`에 커밋하고 push한다. 현재 배포된 앱의 revision은 위 `a2c8bcc`이며, 이번 검증 문서 커밋은 앱 이미지 재빌드를 뜻하지 않는다. 사용자가 이번에 main 병합을 요청한 것은 아니므로 이번 작업에서 main 병합은 수행하지 않는다.

Obsidian `Work/RobinGraph/작업기록/2026-10-09-운영승인-PG이관-동일이미지-배포.md`에 같은 상세 본문을 저장하고 작업기록·프로젝트 index에 연결한다. 읽기 검증으로 문서 일치를 확인한다. 이전 프로젝트 index의 “운영 승인 대기” 표시는 이번 승인·배포 완료 상태로 갱신한다.

실제 Obsidian 본문·두 index의 저장 후 전체 읽기 결과가 작성 내용과 정확히 일치했다. `graphify update .`도 AST 방식으로 완료했다(5,011 노드·10,483 연결). 기존 SQL 파서 미설치 안내와 LLM 기반 community 이름 갱신 안내는 있었으나 AST 갱신은 성공했다. 의미 추출/이름 갱신 API는 실행하지 않았다. 변경한 카드 검증 도구는 `node --check` 통과했다. 이 변경은 검증 결과의 환경 설명만 바꾸며 카드 구현·검사 단정은 같다.

남은 한계는 296종 보전 근거 미연결, 출처의 분류 범위/시점 차이, 일괄 표시 검사와 원문 독립 검증의 차이, 실제 모바일 기기 미검증이다. n8n을 이용한 새 수집 작업은 이번 DB 동기화/동일 이미지 배포에 필요하지 않아 실행하지 않았다.
