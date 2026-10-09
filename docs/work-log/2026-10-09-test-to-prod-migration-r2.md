# TEST → Production DB 재이관 — 이름 관계 수정 이후

- 수행일: 2026-10-09
- 요청: `Test DB 데이터를 Production DB에 마이그레이션해줘`
- 결과: Neo4j·PostgreSQL ingest 자료 복원 완료, 데이터 대조·Production API 검증 통과.
- 작업 기준 저장소: `884a865`.
- 범위: DB 데이터 이관. API 이미지·환경 비밀·프런트엔드·코드에 포함된 인덱스는 배포하지 않았다.

## 목차

1. [배경과 범위](#배경과-범위)
2. [사전 상태](#사전-상태)
3. [백업과 복원](#백업과-복원)
4. [검증과 결과](#검증과-결과)
5. [중간 오류와 해결](#중간-오류와-해결)
6. [중단 기록](#중단-기록)
7. [복구 절차](#복구-절차)
8. [증거와 남은 한계](#증거와-남은-한계)

## 배경과 범위

같은 날 최초 TEST → PROD 이관 이후 TEST의 통칭 관계를 수정했다. `까마귀 → 큰부리까마귀` 관계를 제외한 새 활성 자료 릴리스까지 Production DB에 반영하기 위해 다시 이관했다. 사용자 요청에 따라 데이터 전체를 TEST 스냅샷 기준으로 복원했다.

원래 Neo4j는 TEST가 Mac mini의 `neo4j-test`(5.26.30-community), Production이 NAS의 `neo4j`(2026.08.1)로 나뉜다. PostgreSQL은 NAS `postgres-n8n` 인스턴스 안의 `robingraph_test`와 `robingraph` DB가 분리되어 있다. `public`에는 두 DB 모두 테이블이 없었고, 애플리케이션 데이터는 `ingest` 스키마 8개 테이블에 있었다. 다른 DB와 n8n 데이터는 이관 대상이 아니다.

실행 중 ingestion_run은 없었다. TEST는 성공 12·실패 22, PROD는 성공 11·실패 22였다. outbox_event는 양쪽 모두 0행이었다. 기존 실패 이력은 과거 원장으로 함께 보존하며 이번 복원 실패 건수와 다르다.

## 사전 상태

| 항목 | TEST | PROD 이관 전 | PROD 이관 후 |
|---|---:|---:|---:|
| Neo4j 노드 | 475,031 | 474,998 | 475,031 |
| Neo4j 관계 | 543,683 | 543,637 | 543,683 |
| PG _schema_migration | 4 | 4 | 4 |
| PG ingest_state | 6 | 6 | 6 |
| PG ingestion_run | 34 | 33 | 34 |
| PG outbox_event | 0 | 0 | 0 |
| PG quarantine_item | 2,344 | 2,344 | 2,344 |
| PG source_dataset | 14 | 13 | 14 |
| PG source_record | 57,671 | 57,625 | 57,671 |
| PG source_release | 11 | 10 | 11 |

행 수는 통계 추정값 대신 실제 SELECT 결과를 사용했다. PostgreSQL 각 테이블을 row_to_json으로 직렬화하고 정렬한 전체 행의 SHA-256도 저장했다.

## 백업과 복원

백업 디렉터리: `/volume3/Birds-Nest/backups/robingraph-deploy/test-to-prod-20261009-r2/`.

| 파일 | 용도 | SHA-256 |
|---|---|---|
| `prod-ingest-before.sql` | 이관 전 PROD ingest 백업, 31,482,520바이트 | `87bb7060ef2d2638c5a2ea588d2e2f256055556a2ed9a41ff71de00fe1a0c4ab` |
| `test-ingest.sql` | TEST ingest 덤프, 31,582,689바이트 | `8658adfcb656e83b182be90743df256a075d5602e19edddd9b9f8358d5d4be64` |
| `prod-neo4j/neo4j.dump` | 이관 전 PROD Neo4j 백업 | `b9021ced7dfc0f4531116b1d817316e26fc25a2be839d567d0bb7b8a58f6cacc` |
| `test-neo4j/neo4j.dump` | TEST Neo4j 덤프 | `bab0772c995078919b9b224093fd3114898ee4ae5aefbb68fb4278a53403844d` |

1. PostgreSQL 두 DB의 ingest를 `pg_dump --schema=ingest --no-owner --no-privileges --clean --if-exists`로 각각 덤프했다. 백업 폴더를 만들 때 umask 077을 적용했다.
2. TEST Neo4j를 중지하고 같은 이미지 ID·데이터 볼륨으로 임시 컨테이너에서 `neo4j-admin database dump neo4j`를 실행했다. 성공 후 TEST를 시작했다. 실패 시에도 TEST를 시작하도록 종료 trap을 두었다.
3. PROD API와 Neo4j를 중지하고 PROD 버전 이미지로 기존 Neo4j 덤프를 만든 뒤 다시 시작했다. 기존 데이터 백업이 성공하기 전에는 덮어쓰지 않았다.
4. TEST 덤프를 SSH 표준입력으로 NAS에 전달하고 로컬·NAS SHA-256 일치를 확인했다.
5. TEST 덤프 전후를 다시 조회했다. PostgreSQL 전 테이블 내용 해시 및 Neo4j 노드·관계·레이블·관계 종류·인덱스·제약 메타데이터가 동일했다.
6. PROD API와 Neo4j를 중지하고 `database load neo4j --overwrite-destination=true`로 TEST 덤프를 복원했다. 이어 PROD 버전의 `database migrate neo4j`로 커널 V5_25 → V2026_08 변환을 완료했다.
7. TEST ingest SQL을 PROD robingraph DB에 `psql --single-transaction -v ON_ERROR_STOP=1`로 복원했다. 오류 시 부분 적용되지 않도록 트랜잭션으로 처리했다.
8. PROD Neo4j와 API를 다시 시작하고, DB 복원 후 발견한 소유권 문제를 아래와 같이 교정했다. 최종 검증은 교정 이후 값이다.

Neo4j 이미지 ID는 TEST `sha256:22ec5cd05a8cbb372fc4bed5e384c30bc75fd92504c72be4462039761b105f61`, PROD `sha256:1719b47322e7462aef593ffaff3e8cde2e13e2b537139f2bd4c28037494c8eaa`로 고정했다. latest 태그를 새로 내려받지 않았다.

## 검증과 결과

- 실제 PROD 앱 계정으로 PostgreSQL ingest 8개 테이블의 행 수와 전체 내용 해시를 조회했다. TEST와 모두 일치했다.
- Neo4j 노드 475,031·관계 543,683, 레이블별·관계 종류별 수가 TEST와 일치했다.
- 인덱스 22개가 TEST와 일치하고 ONLINE이었다. 제약 17개의 이름·레이블·속성·의미가 일치했다. 버전별 타입 이름 차이는 아래에 별도로 설명한다.
- 최종 비교 완료 시각: 2026-10-09 10:03:48 UTC / 19:03:48 KST.
- PROD 컨테이너 안에서 `scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --lineage-name 대륙검은지빠귀 --expected-scientific-name 'Turdus mandarinus' --json`을 실행했다. passed·backend_reachable·contract_parity_ok 모두 true.
- 실제 공개 `https://robingraph.dove-nest.com/health` 및 TEST health 모두 status ok.
- 공개 Production `name-relations?name=까마귀`: Corvus corone 1종만 반환.
- 공개 Production `name-relations?name=Corvus macrorhynchos`: 빈 관계 목록. 제거한 통칭이 Production에서도 제거되어 있음.
- 최종 비교는 모의 DB가 아닌 실제 두 환경을 대상으로 했다. 단위 테스트·브라우저 화면 검증은 실행하지 않았다. 애플리케이션 코드 변경이 없고 DB 이관 결과가 검증 대상이기 때문이다.

## 중간 오류와 해결

1. 사전 확인용 SSH 명령의 중첩 인용 오류가 있었다. 명령 실행 전 셸에서 실패했고, 스크립트를 표준입력으로 전달하는 방식으로 수정했다. 데이터 변경은 없었다.
2. 복원 직후 Neo4j 시작이 끝나기 전에 API가 기동되어 연결 거절·재시도가 발생했다. API 검증 명령도 종료 코드 137로 중단된 시도가 있었다. 확인 당시 OOMKilled는 false였으며 DB 기동 완료 후 다시 검증해 통과했다. 처음 실패한 검증을 통과로 기록하지 않았다.
3. PostgreSQL 덤프에 `--no-owner --no-privileges`를 사용했기 때문에 복원 실행 계정 n8n이 ingest 객체 소유자가 되었다. PROD 앱 계정 robingraph_app으로 조회하면 information_schema에 테이블이 보이지 않아 첫 비교가 실패했다. ingest 스키마·8개 테이블·2개 시퀀스의 소유자를 Production 전용 robingraph_app으로 변경했고, 그 계정으로 전 테이블 내용 해시 일치를 확인했다. TEST 계정 robingraph_test_app을 PROD에 부여하지 않았다. **다음 이관에서도 환경별 소유권 매핑을 복원 절차에 포함해야 한다.**
4. Neo4j 5.26은 제약 타입을 UNIQUENESS, 2026.08은 NODE_PROPERTY_UNIQUENESS로 반환한다. 최초 문자열 동일성 비교가 실패했다. 17개 모두 동일한 노드 고유성 제약임을 이름·레이블·속성으로 확인하고 이 타입만 정규화해 비교했다. 다른 차이를 무시하지 않았다.
5. 과거 문서의 공개 주소 aviary.dove-nest.com은 525를 반환했다. 현재 Production 주소 robingraph.dove-nest.com으로 검증해 통과했다. 기존 호스트의 TLS 설정은 이번 데이터 이관 범위에서 변경하지 않았다.
6. 최종 DB/API 검증 이후 추가 Docker 상태 조회 때 NAS SSH 99번 포트가 연결 거절로 바뀌었다. 이관과 데이터 대조는 그 전에 완료했다. 이후 공개 TEST·PROD health와 관계 API는 다시 확인해 정상이었다. 최종 Docker health 값을 추정해 쓰지 않았다.

## 중단 기록

명령 로그의 UTC 타임스탬프 기준이다. start는 컨테이너 시작 명령 완료이며 API 요청 가능 시각과 다르다.

| 구간 | 시작 | 컨테이너 시작 명령 완료 |
|---|---|---|
| TEST Neo4j 덤프 | 09:59:41 | 09:59:54 |
| PROD Neo4j 백업 | 10:00:02 | 10:00:29 |
| PROD 복원 | 10:01:00 | 10:01:22 |

PROD Neo4j 실제 Started 로그는 10:02:07.943 UTC다. 이후 API가 연결에 성공했고 10:03:48 UTC 전체 비교를 통과했다. 이 세션에서 사용자 관점의 정확한 총 불가용 시간을 별도 모니터링하지 않았다.

## 복구 절차

이번에는 복원 명령이 성공해 이전 백업으로 되돌리지 않았다. 실패 시 두 DB를 함께 복구하도록 실행 스크립트에 오류 trap을 두었으며, 실제 롤백 실행 검증은 하지 않았다.

되돌릴 때에는 PROD API·Neo4j를 중지한 뒤 같은 PROD 이미지로 `prod-neo4j/neo4j.dump`를 load하고, `prod-ingest-before.sql`을 robingraph DB에 단일 트랜잭션으로 복원한다. **복원 후 ingest 스키마·테이블·시퀀스를 robingraph_app 소유로 지정해야 한다.** TEST 자격 증명·계정을 복사하지 않는다. DB 준비 상태를 확인한 뒤 API를 시작하고 동일한 검증을 반복한다. 이전 PROD와 현재 TEST를 섞어 한쪽만 되돌리면 활성 자료 릴리스가 어긋날 수 있다.

## 증거와 남은 한계

- [TEST 기준 상태](../verification/assets/2026-10-09-db-promotion-r2-test-before.json)
- [PROD 이전 상태](../verification/assets/2026-10-09-db-promotion-r2-prod-before.json)
- [PROD 최종 상태](../verification/assets/2026-10-09-db-promotion-r2-prod-after.json)
- [비교 결과](../verification/assets/2026-10-09-db-promotion-r2-comparison.json)
- [PROD API 검증](../verification/assets/2026-10-09-db-promotion-r2-api-verify.json)
- [공개 주소 검증](../verification/assets/2026-10-09-db-promotion-r2-public-checks.json)
- [읽기 전용 감사 코드](../verification/assets/2026-10-09-db-promotion-r2-audit.py)

Neo4j는 덤프 전송 해시와 복원·마이그레이션 성공, 전체 개수·구조를 검증했다. 모든 노드 속성을 독립적으로 해시 대조했다고 주장하지 않는다. PostgreSQL은 전체 행 내용까지 해시 비교했다. 공통 health의 fixture-avlist-2025 표기는 별도 fixture 영역이며 실제 분류 계통 canary는 v2025b를 검증했다. health의 deployment_target=legacy는 기존 환경 설정이며 이번 이관에서 변경하지 않았다.

PROD API 이미지 `robingraph-api:prod-e90ff85`, TEST API 이미지 `robingraph-api:test-badge-017a273`은 유지했다. 최근 보전 등급 참고평가 인덱스·형질 연결 인덱스·카드 UI 중 패키지 코드에 들어 있는 변경은 DB 복원으로 배포되지 않는다. 그 기능까지 Production에 동일하게 반영하려면 별도 앱 배포가 필요하다. 이번 요청에서는 코드 배포를 수행하지 않았다.

문서·검증 증거만 저장소에 추가했다. DB 덤프 자체와 인증 정보는 Git·Obsidian에 포함하지 않았다.
