# 이름 벡터의 Neo4j 영구 저장·인덱스 검색 이전

## 요청 배경과 목표

사용자는 현재 이름 벡터 검색이 Neo4j가 아닌 Python 앱 메모리에서 수행된다는 설명을 들은 뒤, Neo4j에 저장하고 검색하도록 변경할 것을 요청했다. 초기 구현은 검토 국명 850개의 벡터를 각 앱 프로세스에서 처음 만들고 캐시했다. 앱 재시작과 여러 프로세스에서 목록 전체 임베딩을 반복하는 문제가 있었다. 이름 벡터를 별도 인덱스에 준비하고, 채팅 요청에서는 질문 이름만 임베딩하여 Neo4j에서 후보를 찾도록 이전하는 것이 목표다.

사용자 후속 질문에 따라 실제 활성 분류판도 읽었다. TEST에는 종 11,131개·아종 19,879개(속 2,376·과 252·목 46)가 있다. 이번 이름 벡터 범위는 기존 검토 국명 850종이다. 전체 종·아종으로 벡터 범위를 확대하지 않았다. 기존 그래프 정확 이름 조회와 후보 선택·주제 보존, 일반 하한 및 제한적 자모 보완 정책은 유지한다. Production 이전은 이번 범위가 아니다.

## 협업과 확인한 근거

- Claude: 새 Neo4j 이름 벡터 저장소와 fake-driver 검사. Task `task_be62670e89d0` / Dispatch `ctx_ac184290460a`, 실제 분류 문맥 후속 정정 Task `task_9fcf93720f88` / Dispatch `ctx_29dad5f7b08f`를 성공 보고로 전달했다. 새 파일 두 개만 수정했고 DB/API 쓰기나 배포는 하지 않았다.
- Codex: 메모리 벡터·캐시 제거, CLI 연결과 TEST 전용 색인 명령, 단위 검사와 실제 격리 DB 검증, NAS DB 대상 확인·색인·배포·API/브라우저 검증·기록을 맡았다. 저장소 통합 시 실수로 Taxon 노드를 수정하지 않도록 entry guard도 보완했다.
- Antigravity가 앞서 만든 후보 UI는 변경하지 않았다. 기존 사용자 확인 UI와 실제 브라우저 검증 자산을 재사용했다.
- Orca의 두 완료 보고를 실제 Task/Dispatch와 대조한 뒤 정산했다. 외부 사용자 터미널은 worker-release 결과 retained/external_terminal로 유지됐고 reclaimable worker는 0개다.

실제 NAS Neo4j 버전은 5.26.30이었다. 기존 문헌 인덱스는 `robingraphFixtureChunkVector`, 라벨 `HybridVectorChunk`, 속성 `hybrid_vector`, 512차원·cosine·ONLINE으로 확인했다. 새 이름 인덱스와 분리했다. 최신 Cypher SEARCH를 무조건 사용하지 않고 실제 5.26에서 지원하는 `db.index.vector.queryNodes`를 사용했다.

Neo4j의 cosine 점수 범위는 기존 앱의 raw cosine과 다르다. [공식5.x 벡터 인덱스 문서](https://neo4j.com/docs/cypher-manual/5/indexes/semantic-indexes/vector-indexes/)의 규약에 따라 `2*score-1`로 변환한다. 실제 격리5.26.30에서 직교 벡터가 Neo4j0.5, 어댑터 raw0.0을 반환함을 확인했다. 이 차이를 무시해 후보 하한이 사실상 바뀌지 않도록 했다.

처음 전달된 저장소에는 이전 그래프 `IngestState`를 요구하는 경로가 있었다. 실제 NAS에서 해당 노드가 없음을 읽기 조회로 확인했다. 현재 활성 분류판의 기준은 PostgreSQL `active_release_context('reference-taxonomy-traits')`이며 CLI가 기존 계통 저장소에도 callback으로 전달한다. Claude 후속 작업에서 레거시 상태 의존성을 제거했고, 전달받은 문맥과 allowed TaxonConceptSet·실제 종 연결을 확인하도록 정정했다. 옛 상태 노드를 새로 만들지 않았다. 색인 명령·resolver가 PostgreSQL 문맥을 전후로 다시 확인한다.

## 변경 전후 동작과 파일

- `src/robingraph/retrieval/taxon_name_resolution.py`: 메모리 LRU·single-flight·목록 embed_documents·Python 전체 벡터 코사인 비교를 제거했다. 그래프에서 이름을 찾지 못하면 질문 이름 벡터 하나만 만들고 주입한 Neo4j candidate_search를 호출한다. 반환된 최대10개 후보의 실제 cosine·ID·학명·이름·텍스트가 검토 목록과 일치해야 한다. 후보는 기존 그래프 ID·species rank·활성 문맥으로 다시 검사하며 최대3개만 제시한다. 인덱스가 없거나 불능이면 unavailable로 보류하고 메모리 검색으로 우회하지 않는다.
- `src/robingraph/retrieval/taxon_name_vectors_neo4j.py`: 새 저장소. `TaxonNameVectorEntry`에 프로필·분류판·텍스트 해시와 taxon ID를 보관하고 `NAME_VECTOR_OF`로 기존 조류 노드에 연결한다. 현재 catalog만 `TaxonNameVector` 라벨·`name_vector` 속성을 가지며 `robingraphTaxonNameVector` 인덱스가 이 범위만 검색한다. catalog 지문은 정렬된 검토 목록·모델·차원·정규화·문맥을 포함한다. 조회는 DDL·쓰기·임베딩 호출 없는 읽기 트랜잭션이다.
- 같은 저장소의 명시적 `index_names`: 기본 dry-run은 읽기와 누락 수 확인만 한다. apply는 모델 응답을 모두 검증한 뒤 현재 feature entry·연결·오래된 feature 라벨/벡터 제거·catalog 전환을 한 쓰기 트랜잭션으로 처리한다. 기존 조류는 읽고 연결만 하며 원자료를 수정하지 않는다. 이름 삭제·텍스트 변경·모델/문맥 변경을 감지하고 재사용 가능한 벡터를 다시 임베딩하지 않는다. 차원이 다른 기존 인덱스를 자동 삭제·교체하지 않는다.
- `src/robingraph/cli.py`: 이름 저장소의 search를 resolver에 연결하고 서버 종료 시 driver를 닫는다. 앱 시작이나 채팅 요청은 schema 또는 이름 벡터를 생성하지 않는다.
- `scripts/index_taxon_name_vectors.py`: TEST 전용 명령. `ROBINGRAPH_DEPLOY_TARGET=test`를 DB 설정 조회 전에 확인하며 기본은 dry-run, 실제 쓰기는 `--apply`로만 실행한다. 검토 목록과 PostgreSQL 활성 문맥을 색인 전후로 확인하고 driver를 정리한다. 명시적 색인 명령은 한 번에 하나씩 실행한다.
- `tests/test_taxon_name_resolution.py`: 옛 메모리 캐시 전용 검사를 퇴역시키고 query-only·DB 장애 시 보류·후보 검증·기존 후보 기준·공백 오타·문맥 변경·목록 전체 임베딩 없음 검사로 갱신했다.
- `tests/test_taxon_name_vectors_neo4j.py`, `tests/test_index_taxon_name_vectors.py`: 저장소의 읽기/쓰기 분리, dry-run·재사용·원자성·기존 인덱스 호환성·문맥·프로필·점수·TEST 경계 검사.
- ADR-0008과 실제 검증 자산·작업 기록을 갱신했다. API 응답 계약·화면·영구 별칭 정책은 바꾸지 않았다.

## 검증: mock과 실제 DB/API 구분

### 단위·계약 검사

최종 전체 Python 명령 `PYTHONPATH=src /tmp/robingraph-qa-python/bin/python -m unittest discover -s tests`는 896개 중858개 통과·38개 제외·실패0, 21.605초였다. opt-in 실제 통합 검사는 제외된 상태다. 관련 resolver·저장소·색인명령·API 검사53개도 통과했다(실패·제외0). Claude 저장소 fake-driver 검사는19개였다. UI 소스 변경이 없어 프런트엔드 fake-DOM 전체 검사를 반복하지 않았고 실제 NAS 브라우저 검사를 수행했다.

### 실제 격리 Neo4j

공유 TEST에 schema/data를 쓰기 전에 별도 Docker `robingraph-name-vector-qa-20261015`, Neo4j5.26.30, localhost17687에서 실제 Cypher를 실행했다. 인증 없는 일회용 DB이고 외부 인터페이스에 포트를 공개하지 않았다. 검증 스크립트는 DB가 비어 있어야 진행한다. fixture 종2개와 합성3차원 벡터로 아래 항목을 통과했다. 실제 조류 정보 검증으로 표현하지 않는다.

- dry-run: schema/data 쓰기와 모델 호출0.
- 최초 apply:2개 임베딩·이름 index/constraint 생성·기존 fixture taxon 연결.
- 재실행:2개 재사용·신규 임베딩0.
- 텍스트 갱신·목록 삭제:1개만 재임베딩, 오래된 entry1개를 검색 범위에서 제외.
- 임베딩 실패: 기존 catalog와 검색 결과 유지.
- 4차원 프로필로3차원 index 변경 시도: 실패하며 기존 index 유지.
- 새 저장소 연결: 저장된 벡터로 검색 성공, 점수 변환 확인.
- fixture 문헌 index/schema와 fixture taxon 속성: 전후 동일. 레거시 IngestState 없음.

첫 실행은 이 항목들을 통과한 뒤 검증기 마지막 보조식의 Cypher 실수(`[1.,0.]`)로 실패했다. 해당 검증기 숫자를1.0으로 수정하고 일회용 컨테이너를 재생성해 처음부터 재실행하여 통과했다. 프로덕션 코드 수정으로 감추거나 첫 실행을 성공으로 기록하지 않았다. 검증 후 이 컨테이너를 제거했다.

### 실제 NAS TEST 색인

NAS TEST와 PROD의 Neo4j URI·PostgreSQL DB가 서로 다르고 새 TEST 환경 사본이 실행 중 TEST 설정과 일치함을 메모리에서 비교했다. 비밀값은 출력하지 않았다. 일회용 DB 검증 통과 후 TEST 대상에만 명시적 이름 색인을 실행했다. 새 이미지의 일회성 컨테이너에 기존 TEST 환경을 전달했으며 비밀 임시 파일은 실행 후 삭제했다. 앱 교체보다 먼저 이름 색인을 준비했다.

| 실행 | 대상 | 재사용 | 새 임베딩 | 결과 |
|---|---:|---:|---:|---|
| dry-run |850|0|0|준비850, 이름 schema/constraint 없음 확인|
| 최초 apply |850|0|850|전용 schema/constraint·catalog 생성|
| 두 번째 apply |850|850|0|동일 catalog·기존 벡터 재사용|

최종 이름 인덱스는 ONLINE·cosine·512차원, feature vector850개와 조류 연결850개, 잘못된 차원/Taxon 라벨 혼입0이었다. 기존 Taxon·Document·Chunk·HybridVectorChunk 수는 전후 동일했다. 문헌 인덱스의 이름·라벨·속성·차원·설정과 기존 문헌 벡터의 SHA-256도 전후 동일했다. 새 이름 벡터·entry/catalog·constraint 외의 문헌 색인을 삭제하거나 시험 차원에 맞춰 교체하지 않았다.

### 실제 NAS API와 브라우저

새 TEST 앱으로 교체한 뒤 실제 Jina·Neo4j·HTTP에서 천둥오리 회귀12회와 기존 흰뺨검둥오리 기준선8회, 합계20회가 통과했다. 별도 배포 API 계약 검사는 passed=true, backend_reachable=true, contract_parity_ok=true였다. route mock은 쓰지 않았다.

첫 `천둥오리에 대해 알려줘`는 청둥오리 확인 후보를1.106초에 반환했다. 과거 메모리 방식에서 같은 질문의 최초 요청은29.052초였다. 두 관측치이며 통제된 성능 비교나 p95 보장이 아니다. 새 앱 시작 후 국명850개 재임베딩을 수행하지 않은 코드·단위 검사와 함께 초기 목록 구축 지연 제거를 확인한 결과다. 질문 임베딩·DB 지연은 여전히 남는다.

공백 이름의 graph_exact/graph_normalized, 흰뺨검둥오려·천둥오리·천둥 오리·청둥오려 후보, 후보 확인 후 같은 taxon ID 및 먹이 주제 유지가 통과했다. 천둥·우주선·아무새·아무오리는 기존처럼 보류했다. 실제 NAS 컨테이너에 SSH 포워딩으로 연결한 Chromium1280·390·320px 각3회 요청(총9회)도 통과했다. 후보 자동 전송 없음, Enter 키 선택, 과거 까치 필터 무시, diet 유지, 후보44px 높이, 가로 넘침 없음, pageerror0을 확인했다. 물리 모바일이나 공개 프록시 도메인 검사가 아니다. 포워딩은 종료했다.

## 배포·소스·운영 불변

기준 커밋 `434b6a4be8493f9b8bd85f477cbe8aca65ec7413`의 runtime allowlist에 미커밋 source12개를 덮어쓴 스냅샷이다. 이전 협업 변경과 MRR·감사 도구를 보존했다. 이번 runtime 변경은 resolver·CLI·새 저장소·새 색인 명령이다. commit/push/병합 없이 스냅샷·파일 해시를 명시한다. AGENTS·MCP·비밀 환경 파일은 포함하지 않았다.

- 스냅샷 SHA-256: `0b3da84849533cee211381691e62ac2f79e9dd16e1582ce217138ff6cc144093`.
- 아카이브 SHA-256: `70f07ae891817eee4b5331771398c2fade6a7f63cff144eacdb2c1161a23900f`.
- runtime138개 파일 해시를 원격에서 확인하고 배포 컨테이너의 overlay12개도 전부 대조했다.
- 릴리스: `/home/<nas-user>/robingraph-name-neo4j-0b3da8484953`.
- 이미지: `robingraph-api:test-name-neo4j-0b3da8484953`.
- 이미지 ID: `sha256:51cd8188ff96e5af18d5e601fee2e34bca315873ac6d147fde39aee108be2275`.
- OCI revision: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-name-neo4j-0b3da8484953`.
- TEST 컨테이너: `4e181dafa15a2bd3c54c5081788da2333641354957502653386e80683bade514`, 시작 `2026-10-15T10:07:14.104270099Z`, running·healthy.
- `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh build/deploy` 실행. 직전 TEST `robingraph-api:test-name-resolution-2ef0b2b08937`은 보존했다.

운영 컨테이너 ID `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`, 시작 `2026-10-10T06:07:33.413088244Z`, 이미지 `robingraph-api:prod-approved-ui-0681747`은 전후 동일했다. Production 배포·재시작·DB 쓰기는 하지 않았다. 이번 실제 DB 쓰기는 사용자 요청에 따른 NAS TEST 이름 벡터 영역과 일회용 QA DB로 구분한다.

필요 시 새 릴리스에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-name-resolution-2ef0b2b08937`로 이전 앱을 복구할 수 있다. 새 이름 index/data는 기존 앱과 분리되어 자동 삭제할 필요가 없다. 실제 롤백은 실행하지 않았다. 이전 메모리 방식의 로컬 임시 검증 앱8001은 종료했고 기본 로컬 TEST8000은 교체하지 않았다.

## 증거와 남은 한계

`docs/verification/assets/2026-10-15-neo4j-name-vectors/`에 일회용 DB 실행 코드/결과, 실제 NAS before/after·색인 dry-run/apply/repeat·이미지 소스 해시·API/브라우저 JSON·스크린샷·분류판 범위·검사 요약을 보관한다. 주요 임시 로그는 `/tmp/robingraph-name-neo4j-full-tests.log`, `robingraph-name-neo4j-unit.log`, `robingraph-name-neo4j-build.log`, `robingraph-name-neo4j-deploy.log`, `robingraph-name-index-*.log`다. 임시 파일의 영구 보관은 보장하지 않는다.

Graphify AST 갱신은5,593노드·11,559엣지·345커뮤니티로 완료했다. SQL4개는 tree_sitter_sql 부재로 제외됐고 문서 의미 추출은 AST 범위 밖이다. HTML은5,000노드 초과에 따른 커뮤니티 집계 화면이다. `git diff --check`도 확인했다. 저장소와 Obsidian의 작업 기록·핵심 검증 결과를 일치시킨다.

이름 벡터 범위는850종이며 종11,131개·아종19,879개 전체를 색인한 결과가 아니다. Neo4j 벡터 index는 근사 이웃 검색이어서 모든 입력의 전수 비교 순위를 보장하지 않는다. 후보 하한·좁은 자모 보완·사용자 확인은 유지하며, 모델·차원·분류판 변경 시 명시적 재색인/마이그레이션이 필요하다. 물리 모바일·Safari·Firefox·운영 부하·물리 재부팅·공개 도메인 경유 검사는 이번 범위 밖이다. 공개 TEST 도메인은 앞선 외부 접근의403 때문에 직접 확인하지 못했으며 NAS 컨테이너 직접 검증과 구분한다.
