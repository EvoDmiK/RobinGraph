# RobinGraph 현재 구현 상태

- 상태: In progress
- 기준일: 2026-09-04
- 범위: 합성 fixture + 라이선스 정책·provenance + Neo4j 그래프/전문/벡터 검색 + Jina 호환 HTTP 어댑터

§1~11은 첫 그래프 슬라이스의 구현 기록이며, 이후 완료한 하이브리드 검색과 최신 검증 결과는 §12에 정리했다.

최신 연결 점검: 실제 Jina로 합성 문서 청크 4개의 512차원 벡터를 생성해 로컬 Neo4j에 저장하고, 한국어 질문 2개로 전문·벡터 결합 검색과 출처·라이선스 반환을 검증했다. 이후 **전체 102개 테스트 통과(DB 통합 20개 포함, skip 0개), gold 15/15**를 확인했다. Hermes 연동은 후속이며 [연결 결과](embedding-adapter.md#실제-jina--neo4j-연결-검증-2026-09-04)에 범위와 한계를 기록했다.

## 1. 완료된 범위

현재 구현은 실제 외부 조류 데이터가 아닌 결정적 synthetic fixture를 사용한다. fixture는 10개 Taxon, 허용 Observation 100건, 허용 Document 2개, 허용 Chunk 4개, 정책 차단 입력과 15개 gold 질문으로 구성된다.

| 영역 | 구현 내용 | 검증 결과 |
|---|---|---|
| Fixture 생성 | 고정 timestamp, ID, manifest SHA-256을 생성 | 재생성 가능 |
| Staging 검증 | provenance, 날짜, 좌표, 수량, 민감도, 문서/Chunk 필드 검사 | 형식 오류와 정책 필터 분리 |
| Source registry | JSON Schema 및 Python validator | 잘못된 source 설정 차단, 스키마-validator parity 테스트 |
| License policy 엔진 | `license_policy_status` + 문서별 fulltext/chunk/embedding tri-state 조합 판정 (`robingraph.policy`), 그래프 투영 단계에서 재적용(fail-closed) | 문서 metadata는 fulltext 차단과 무관하게 보존, chunk는 문서·자기 status 둘 다 허용해야 포함, source registry 불일치도 차단 |
| 이름·장소·문서 해소와 답변 | `QuestionService`가 저장소(`GraphRepository`)의 이름/장소/문서 인덱스만으로 해소, 특정 종·장소·문서 ID 분기 없음 | gold 질문 15/15 통과(fixture, Neo4j 두 백엔드 모두 실제 실행 확인) |
| Citation/provenance | 모든 evidence(Taxon/Observation/Chunk)에 실제 source·license를 첨부, 하드코딩 literal 라이선스명 제거, locator는 EvidenceUnit 자신의 값 사용 | provenance 테스트 통과(fixture·Neo4j 모두) |
| Neo4j fixture 적재 | idempotent upsert + **재적재 시 정책상 탈락한 노드를 같은 트랜잭션에서 정리(reconciliation)**, License/EvidenceUnit을 포함한 graph projection | 실 Neo4j 2026.07.1에서 반복 적재·정책 철회 시나리오까지 실제 실행 확인 |
| Neo4j 검색 백엔드 | `Neo4jGraphRepository`가 parameterized Cypher로 이름/장소/기간 필터 관찰과 fail-closed citation을 조회 | 기존 opt-in 통합 테스트 10개 전부 실 서버에서 통과, 기존 전체 스위트 **44개 전부 통과**(§9) |
| HTTP API / CLI | `serve-fixture`/`serve-neo4j`(종료 시 드라이버 close), `ask-neo4j` | fixture 모드 FastAPI contract 테스트 통과, `ask-neo4j` 실 서버 스모크 테스트 통과 |

## 2. 라이선스 정책과 provenance 완전성

`robingraph/policy.py`는 순수 함수로 라이선스 판정을 계산한다.

- `record_allowed`: Taxon/Observation은 `license_policy_status == allowed`일 때만 corpus에 포함한다.
- `document_metadata_allowed` / `document_fulltext_allowed` / `document_chunk_allowed` / `document_embedding_allowed`: 문서의 4단계 권한을 계층적으로 판정한다. **문서 metadata(제목·source·license)는 `fulltext_storage_allowed`가 false여도 보존된다** — 파생 콘텐츠(청크·임베딩)만 제외된다.
- `chunk_allowed` / `chunk_embedding_allowed`: 청크는 자신의 `license_policy_status`와 **부모 문서의 권한을 모두** 만족해야 검색 corpus에 들어간다.

`robingraph/graph/fixture_projection.py`의 `fixture_graph_payload`는 호출자가 넘긴 `FixtureCorpus`가 이미 정책 필터링됐다고 신뢰하지 않는다. 위 정책 함수를 **투영 시점에 다시 적용**하고, 추가로 각 레코드의 `source_id`가 가리키는 source registry 항목 자체가 `allowed`인지도 재확인한다(`_source_allowed`). 레코드 자신의 상태가 `allowed`라도 참조하는 source가 `denied`거나 registry에서 아예 사라졌으면 그래프 payload에서 제외한다 — fail-closed다. `tests/test_retrieval.py::GraphPayloadPolicyReapplicationTest`가 `load_fixture`를 거치지 않고 직접 만든/수정한 `FixtureCorpus`로 이를 검증한다.

Citation은 taxonomy/observation/document/chunk 네 범주 모두 `GraphRepository.citation_for`를 통해 실제 source registry(fixture 모드) 또는 그래프의 `SourceRecord`/`SourceDataset`/`License`(Neo4j 모드)에서 `source_url`, `locator`, `license_name`을 가져온다.

- 이전 구현은 `license_name`을 `"fixture-test-license"` literal로 하드코딩했다; 지금은 source registry의 `license_name`(신규 optional 필드, 없으면 `license_uri`로 대체)에서 가져온다.
- Neo4j 모드의 `_CITATION_QUERY`는 `SourceDataset -[:LICENSED_UNDER]-> License` 홉을 `OPTIONAL MATCH`가 아니라 **일반 MATCH로, `lic.policy_status = 'allowed'` 조건과 함께** 요구한다. 라이선스가 없거나 `allowed`가 아니면 citation이 `'unknown'`으로 조용히 대체되지 않고 결과가 0행이 되어 `citation_for`가 `ValueError`를 던진다(fail-closed). `known_evidence_ids()`도 같은 조건으로 필터링해서, "알려진 evidence인데 citation은 실패"하는 불일치가 나지 않는다.
- locator는 이제 항상 **`EvidenceUnit.locator`**(적재 시점에 taxon ID/occurrence_id/문서 section처럼 사람이 읽을 수 있는 값으로 채워짐)에서 가져온다. 이전에는 Chunk citation이 `Chunk.locator`(적재 코드가 실제로는 설정한 적 없는 속성)를 먼저 보고 실패한 뒤 `SourceRecord.external_id`(=chunk의 opaque ID)로 대체돼, "section 1" 같은 사람이 읽을 수 있는 위치 정보가 사라지고 있었다. `tests/test_neo4j_integration.py::test_chunk_citation_locator_is_the_readable_section_not_the_chunk_id`가 이 회귀를 고정한다.
- Neo4j 적재도 이제 Taxon/Observation/Chunk 모두 `-[:FROM_RECORD]->`로 자신의 `SourceRecord`에 직접 연결된다(Document는 이전부터 있었다; 이전에는 Taxon과 Chunk가 EvidenceUnit을 통해서만 간접적으로 SourceRecord에 닿을 수 있었다). 모든 범주의 `SourceDataset`에 `LICENSED_UNDER → License` 관계가 있다.

**fail-closed는 citation뿐 아니라 조회(retrieval) 자체에도 적용된다.** `Neo4jGraphRepository`의 `list_taxonomy`, `list_places`, `list_documents`, `list_chunks`/`chunks_for_document`, `observations_for_taxa` 모두 각 노드 자신의(Chunk/Document는 자신과 부모 문서 양쪽의) `FROM_RECORD → SourceRecord → IN_DATASET → SourceDataset → LICENSED_UNDER → License` 체인이 `policy_status = 'allowed'`로 존재해야만 결과에 포함시킨다. Place는 라이선스가 없는 순수 공간 참조이므로, 대신 "허용된 관찰이 하나라도 WITHIN으로 연결된 장소"만 노출한다. citation 단계의 fail-closed 검사만으로는 답변 **본문**(예: 학명·한국어 이름 문장)이 citation 검증 이전에 이미 저장소 조회로부터 구성되므로, 어떤 노드에 유효한 허용 라이선스 체인이 없으면 그 이름·텍스트·존재 자체가 애초에 조회 결과에 나타나지 않도록 했다 — 답변 생성 이후에야 citation에서 막는 것보다 한 단계 이전에서 차단한다. `Neo4jPolicyReconciliationTest.test_revoking_a_taxon_removes_it_from_retrieval_directly_not_only_citation`과 `test_revoking_a_chunk_removes_it_and_its_evidence_on_reload`가 `list_taxonomy()`/`list_chunks()`/`observations_for_taxa()` 각각에서 철회된 항목이 사라지는지(citation 실패 여부와 별개로) 실 서버에서 확인한다.

## 3. 재적재 시 정책 철회 반영(reconciliation)

`neo4j_client.load_fixture`는 매번 전체 payload를 MERGE로 upsert한 뒤, **같은 쓰기 트랜잭션 안에서** `_reconcile_stale_nodes`를 실행한다. 이 함수는 `_expected_ids(payload)`가 계산한 "이번 적재 후에도 남아 있어야 하는 ID 집합"과 비교해서, `:RobinGraph:Fixture` 라벨을 가진 노드 중 그 집합에 없는 것을 라벨별로 `DETACH DELETE`한다(`TaxonConceptSet`, `Taxon`, `ScientificName`, `VernacularName`, `Observation`, `Place`, `Document`, `Chunk`, `SourceRecord`, `SourceDataset`, `License`, `EvidenceUnit`).

- 모든 MATCH가 `:RobinGraph:Fixture` 라벨로 범위가 좁혀져 있어서, 이 라벨이 없는 노드(무관한 실 데이터)는 절대 매치·삭제되지 않는다.
- 업서트와 정리가 한 트랜잭션이므로 "일부만 반영된" 중간 상태가 외부에 보이지 않는다.
- 이전 구현은 MERGE만 했다 — 어떤 청크나 관찰이 나중에 `denied`로 바뀌어도 예전에 적재된 노드가 그래프에 그대로 남아 citable했다.

`tests/test_neo4j_integration.py::Neo4jPolicyReconciliationTest`가 실제 Neo4j에 대해 이를 검증한다: 청크 하나를 `denied`로 바꿔 재적재하면 그 청크 노드와 evidence가 사라지고 `citation_for`가 실패하는지, 문서의 `chunk_storage_allowed`를 철회하면 그 문서의 청크만 사라지고 문서 metadata는 남는지, 같은 fixture를 반복 적재해도 개수가 변하지 않는지(idempotent)를 확인한다. 각 테스트는 `addCleanup`으로 커밋된 fixture를 다시 적재해 복원하므로, 전체 스위트를 한 번 실행하면 disposable DB는 실행 전과 같은 상태로 끝난다(§8에서 `verify-neo4j-fixture`로 확인).

## 4. 데이터-driven 검색: QuestionService와 GraphRepository

`robingraph/retrieval/repository.py`의 `GraphRepository` 프로토콜(`list_taxonomy`, `list_places`, `list_documents`, `list_chunks`, `chunks_for_document`, `observations_for_taxa`, `citation_for`, `known_evidence_ids`, `known_private_coordinate_values`)을 `robingraph/slice.py`의 `QuestionService` 하나가 소비한다. 구현체는 두 가지다.

- `FixtureRepository` (`robingraph/retrieval/fixture_repository.py`): 정책 필터링된 in-memory fixture corpus를 감싼다. 오프라인 모드는 그대로 유지된다.
- `Neo4jGraphRepository` (`robingraph/retrieval/neo4j_repository.py`): 이미 `load-neo4j-fixture`로 적재된 그래프를 parameterized Cypher(질문에서 만든 문자열을 그대로 쿼리에 넣지 않는다)로 조회한다. 관찰 조회는 `taxon_ids`/`place_id`/`month_prefix` 파라미터로 필터링하고 `ORDER BY o.occurrence_id`로 정렬해, in-memory 저장소가 보존하는 fixture 생성 순서와 같은 순서를 보장한다(관찰 여러 건 중 "첫 번째"를 대표 근거로 쓰는 민감 좌표 abstain 경로가 두 백엔드에서 같은 결과를 내야 하기 때문).
- `QuestionService`는 특정 종·장소·문서 ID에 분기하지 않는다. 장소/문서 해소는 저장소가 반환하는 데이터에서 만든 인덱스를 쓰고, "정확한 좌표" 질문은 매칭된 관찰의 `sensitivity_class == withheld` 여부로 판단한다(특정 종 ID 검사가 아니다 — §5의 버그와 직결). 모호한 이름("물새" 등)은 과학명 인덱스로 해소되는 작은 alias 표(코드 상수)를 거친다; 실제 서비스에서는 분류 백본의 synonym/group vocabulary로 대체해야 한다.

`tests/test_retrieval.py`는 fixture에 전혀 없던 장소명/문서 제목/taxon으로 구성한 합성 `GraphRepository`로 위 해소 로직을 검증해서, "특정 fixture 데이터에만 맞는 우연한 일치"가 아님을 증명한다.

## 5. 수정한 버그

### 5.1 근거 없는 민감 좌표 질문의 IndexError

이전 코드는 "말똥가리"(`buteo-japonicus`) + "정확한"/"좌표" 질문에서 무조건 `self._matching_observations(question, taxa)[0]`을 읽었다. 장소·기간 필터와 겹치는 관찰이 하나도 없으면 빈 리스트를 인덱싱해 `IndexError`가 발생했다.

지금은 매칭 관찰이 없으면 곧바로 abstain하고, 있으면 첫 관찰의 `sensitivity_class`로 판단한다. `tests/test_retrieval.py::test_precise_coordinate_request_with_no_matching_observation_abstains_without_crashing`가 회귀를 고정한다.

### 5.2 Neo4j 적재 Cypher의 `WITH` 누락 (실 서버에서 재현)

`neo4j_client._load_fixture_tx`의 observation/chunk UNWIND 블록이 `MERGE`(SourceDataset/License) 직후 바로 `MATCH`(Taxon/Document)를 실행해서, 서버의 GQL 호환 파서가 `Neo.ClientError.Statement.SyntaxError`(`WITH` required between `MERGE` and `MATCH`)로 거부했다. 공유된 `_MERGE_SOURCE_AND_LICENSE` 블록 끝에 `WITH *`를 추가하고, observation 블록의 두 번째 MERGE→MATCH 경계에도 `WITH *`를 추가해 해결했다. 실 Neo4j 2026.07.1(`bolt://127.0.0.1:17687`)에 대해 `load-neo4j-fixture` 경로(`Neo4jIntegrationTest.setUpClass`)가 실제로 통과하는 것으로 확인했다.

### 5.3 Neo4j 백엔드 gold 질문 GQ-010 순서 불일치

수정 (1)~(4)를 실 서버에 대해 처음 돌렸을 때 `test_gold_questions_pass_through_real_parameterized_cypher_retrieval`의 GQ-010("말똥가리의 정확한 관찰 좌표를 알려줘")이 실패했다. 원인은 `_OBSERVATIONS_QUERY`가 `ORDER BY o.event_date_raw`로 정렬해서 "정확한 좌표" abstain 경로가 대표 근거로 고르는 "첫 관찰"이 날짜순 최솟값(occ-094, 1월)이 됐기 때문이다 — in-memory `FixtureRepository`는 fixture 파일/생성 순서(occ-091이 해당 종의 첫 레코드)를 그대로 보존해서 gold가 기대하는 `fixture-occ-091`과 달랐다. `ORDER BY o.occurrence_id`로 바꿔 두 백엔드가 같은 순서를 내도록 맞췄다(§4). 이 수정 후 opt-in 통합 테스트가 실 서버에서 전부 통과했다(§9).

### 5.4 metadata-only 문서 질문이 빈 "answer"를 내던 문제

문서는 metadata가 보존돼도 청크가 0개일 수 있다(§2 — `chunk_storage_allowed`가 철회된 경우 등). 이전 `_document_answer`는 청크가 없어도 그대로 진행해서 `answer_text=""`, `evidence_ids=()`인데 `disposition="answer"`인 응답을 냈다 — 근거 없는 답변이 "지원됨"으로 보이는 상태였다. 이제 청크가 0개면 곧바로 abstain한다. `tests/test_retrieval.py::test_a_metadata_only_document_with_no_chunks_abstains_instead_of_answering_empty`가 합성 저장소(청크가 없는 문서를 하나 추가)로 이를 고정한다.

## 6. 데이터와 보안 경계

- fixture의 `fixture-*` URL, 위치, 관찰값은 실제 관찰·출처가 아니다.
- `latitude_private`, `longitude_private`는 graph projection과 HTTP 응답에 포함하지 않는다. Neo4j 모드의 `known_private_coordinate_values()`는 그래프에 애초에 없는 값이므로 항상 빈 집합을 반환한다.
- `denied`와 `review_required` 입력은 감사를 위해 fixture 입력에 존재하지만 graph, 검색, 생성 근거에는 포함하지 않는다.
- Neo4j URI, 사용자명, 비밀번호는 환경 변수로만 제공한다. `.env`는 Git에서 제외하고, `.env.example`에는 placeholder만 둔다.
- Neo4j 적재 코드는 모든 쓰기(업서트와 §3의 정리 삭제 모두)를 `:RobinGraph:Fixture` 라벨로 엄격히 제한한다. 이 라벨이 없는 노드는 절대 매치되지 않으므로, 같은 데이터베이스에 무관한 실 데이터가 있어도 안전하다. opt-in 통합 테스트도 이 경계 안에서만 쓰고, 각 테스트가 끝나면 커밋된 fixture로 복원한다.
- 실제 source adapter는 승인된 source registry, 라이선스 snapshot, 고정 release, 원본 manifest가 준비될 때까지 작성하지 않는다. Jina 호환 어댑터는 §12에서 추가했고, 실제 서버 연결 확인과 HermesAgent 생성은 후속이다.

## 7. 실행 방법

Python 3.12 이상, `uv`가 필요하다(Codex가 `uv.lock`/`pyproject.toml`을 관리한다).

```sh
uv sync --locked --extra test
uv run --locked robingraph validate-fixture
uv run --locked robingraph evaluate-fixture
uv run --locked --extra test python -m unittest discover -s tests -v
```

Neo4j 연결 정보가 환경 변수에 있을 때 fixture 적재와 검증을 실행한다.

```sh
uv run --locked robingraph verify-neo4j
uv run --locked robingraph load-neo4j-fixture
uv run --locked robingraph verify-neo4j-fixture
```

fixture API(오프라인, 기본값)는 다음으로 실행한다.

```sh
uv run --locked robingraph serve-fixture
```

Neo4j에 이미 적재된 그래프로 API를 서비스하려면(`load-neo4j-fixture`를 먼저 실행해야 한다):

```sh
uv run --locked robingraph serve-neo4j
```

그래프에 대해 API 서버 없이 질문 하나만 던져보려면:

```sh
uv run --locked robingraph ask-neo4j --question "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"
```

`GET /health`는 활성 저장소에 따라 `mode: fixture` 또는 `mode: neo4j`를 반환한다. `POST /v1/answers`는 아래 형식의 질문을 받으며, `answer_text`, `evidence_ids`, `citations`, `disposition`, `warnings`을 반환한다. 이 계약은 두 모드에서 동일하다.

```json
{"question": "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"}
```

## 8. Neo4j 통합 테스트(opt-in)와 CI 연동 요청

`tests/test_neo4j_integration.py`는 **`ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1`이 없을 때만** skip된다.

```sh
export ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=<password>
export NEO4J_DATABASE=neo4j
uv run --locked --extra test python -m unittest tests.test_neo4j_integration -v
```

플래그가 설정됐는데 `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`가 없거나 잘못되면 **skip이 아니라 `setUpClass` 단계에서 즉시 실패**한다(`Neo4jSettings.from_environment()`가 `ValueError`를 던진다) — 명시적으로 opt-in했는데 연결이 깨진 상태가 조용히 통과로 보이지 않도록 하기 위함이다.

전체 스위트를 그대로 두고 opt-in 테스트만 포함하려면:

```sh
uv run --locked --extra test python -m unittest discover -s tests -v
```

CI의 `.github/workflows/ci.yml`에 별도 Ubuntu `neo4j` job이 구현돼 있다. Neo4j Community `2026.07.1` 이미지와 인증을 켠 일회용 fixture DB를 사용하고, 같은 opt-in 환경 변수로 전체 테스트를 실행한다. Windows/macOS fixture job은 DB 없이 실행한다. 자세한 설정과 로컬 실행법은 [개발환경 가이드](development.md#neo4j-통합-테스트)를 참고한다. 로컬 테스트 통과와 원격 GitHub Actions 결과는 별개이며, 원격 실행은 아직 확인하지 않았다.

## 9. 검증 명령과 이번 세션의 실제 실행 결과

이번 세션은 coordinator가 준비한 disposable Neo4j 2026.07.1(`bolt://127.0.0.1:17687`)에 대해 실제로 실행해서 확인했다(정적 검토가 아니다).

| 명령 | 결과 |
|---|---|
| `uv run --locked robingraph validate-fixture` | 10 taxa, 100 allowed observations, 2 allowed documents, 4 allowed chunks |
| `uv run --locked robingraph evaluate-fixture` | 15/15 gold questions passed |
| `uv run --locked robingraph verify-neo4j-fixture` (수정 전) | `Neo.ClientError.Statement.SyntaxError`로 `load-neo4j-fixture` 자체가 실패 |
| `uv run --locked robingraph load-neo4j-fixture` → `verify-neo4j-fixture` (수정 후) | `10 taxa, 100 observations, 2 documents, 4 chunks; private_coordinates=0, restricted_observations=0` |
| `uv run --locked robingraph ask-neo4j --question "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"` | `{"disposition": "answer", "evidence_ids": ["fixture-occ-001"], ...}` — 실 서버 왕복 확인 |
| `ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 uv run --locked --extra test python -m unittest discover -s tests -v` (연결 정보 포함) | **44 tests, 44 passed, 0 skipped** — 여러 차례 반복 실행 모두 통과(idempotent) |
| 위와 동일하되 `ROBINGRAPH_NEO4J_INTEGRATION_TESTS`만 없음 | 44 tests, 34 passed, **10 skipped**(Neo4j 관련 테스트만) — 기본 실행은 여전히 live DB를 건드리지 않는다 |
| 위와 동일하되 플래그는 1, `NEO4J_URI`/`USERNAME`/`PASSWORD`는 없음 | **skip이 아니라 `setUpClass` ERROR 2건**(§8에서 의도한 동작) |
| 스위트 종료 후 `uv run --locked robingraph verify-neo4j-fixture` | `10 taxa, 100 observations, 2 documents, 4 chunks; private_coordinates=0, restricted_observations=0` — disposable DB가 시작 전 상태로 복원됨 확인 |

## 10. 남은 한계

- 모호한 이름(예: "물새") 해소는 여전히 코드 상수 alias 표에 의존한다. 분류 백본에 synonym/group vocabulary 노드가 생기면 그쪽으로 옮겨야 한다.
- Jina 호환 어댑터와 별도 문헌 검색 CLI는 §12에서 추가했고, 이후 실제 Jina 문서·검색어 임베딩을 확인했다. HermesAgent 생성과 외부 source adapter는 아직 없다.
- License 판정은 fixture의 `license_policy_status`/tri-state 플래그를 그대로 신뢰한다(단, §2처럼 그래프 투영과 조회 양쪽에서 fail-closed로 재확인은 한다). 실제 라이선스 문구를 SPDX ID로 정규화하는 절차는 아직 없다(§11의 "다음 운영 단계 입력" 항목).
- reconciliation은 이번 fixture 규모(노드 수백 개)에서는 매 적재마다 라벨별 전체 스캔으로 충분하지만, 노드가 크게 늘어나면(운영 규모) `ingestion_run_id` 기반 증분 정리나 인덱스 보강이 필요할 수 있다.

## 11. 다음 운영 단계의 입력

실제 서비스 구현으로 전환하기 전에는 다음을 확정해야 한다.

- MVP 지역과 대상 사용자, 서비스의 상업성
- AviList v2025b와 NIBR 이용 조건에 대한 최종 분류·국명 정책
- GBIF의 선택 dataset, DOI, 고정 release, 최소 필드와 라이선스
- 민감종 원좌표 보관본과 공개 일반화 규칙
- 문헌별 실제 full text, Chunk, embedding 허용 상태(정책 *엔진*은 이제 준비됐다 — §2)
- HermesAgent와 Jina API의 endpoint, 인증, 구조화 출력, token usage, embedding dimension/task/normalization 계약

운영 소스가 확정되면 fixture 전용 repository를 source adapter, Neo4j retrieval(이제 `Neo4jGraphRepository`로 준비되고 실 서버에서 검증됨), Jina embedding, HermesAgent structured generation으로 교체한다. API의 provenance와 citation validation 계약은 유지한다.

## 12. 하이브리드 검색 배치 완료

GPT-5.6 Luna가 Jina 호환 HTTP 어댑터를, Claude가 Neo4j 전문/벡터 검색과 RRF를 구현했다. Coordinator가 CLI와 실제 DB 테스트를 연결하고 인덱스 충돌, 정규화 검증, 재적재 시 권한 철회에 따른 벡터 제거를 보완했다.

- `index-neo4j-fixture`: 기본은 전문 검색 인덱스 준비. `--embeddings`를 명시하면 설정된 Jina 서버에 허용 청크를 보내고 벡터를 저장한다.
- `search-neo4j --question ...`: 문헌 청크의 본문·점수·검색 채널·출처·라이선스를 반환한다. `--hybrid`는 질문 임베딩과 벡터 검색을 추가한다.
- 기존 `serve-fixture`, `serve-neo4j`, `ask-neo4j`의 답변 경로는 기존 그래프 질의를 사용한다. 새 검색 CLI에는 아직 LLM 생성이 없다.
- 새 검색은 SourceDataset 단위 정책을 확인한다. 기존 질문 repository의 License 단위 정책 검사는 실제 다중 소스 적재 전에 통일해야 한다.

실행 문서: [하이브리드 검색](hybrid-retrieval.md), [임베딩 어댑터](embedding-adapter.md), [작업 기록과 다음 목록](next-implementation-batch.md).

| 검증 | 결과 |
|---|---|
| 실제 Neo4j 2026.07.1 포함 전체 테스트 | **96/96 통과**, skip 0개 |
| DB 없는 기본 테스트 | 76개 통과, DB 테스트 20개 skip |
| 기존 gold 질문 | 15/15 통과 |
| 모의 Jina HTTP → 실제 Neo4j → 검색 → citation | 통과 |
| CLI 전문 검색 / 하이브리드 검색 | 통과 |
| Neo4j fixture 검증 | Taxon 10, Observation 100, Document 2, Chunk 4; 비공개 좌표·제한 관찰 0 |
| 실제 보유 Jina/Hermes 서버 연결 | 후속 검증에서 Jina 문서·검색어 임베딩 성공; Hermes 미확인 |
| 원격 GitHub Actions | 미실행 |

테스트용 벡터는 서버 연결과 정책·검색 흐름을 검사하기 위한 합성 값이다. 실제 한국어 의미 검색 품질·성능을 입증하지 않는다. 변경은 작업공간에 있으며 이번 배치에서 커밋/푸시는 하지 않았다.

## 13. 한국어 검색 baseline

`data/eval/v1/search-questions.jsonl`에 4개 relevance와 1개 정책 제외 질문을 추가했다. `evaluate-search-neo4j --mode all --limit 3`는 fulltext, vector, hybrid(RRF)를 개별 실행해 recall@k, MRR, 평균/p95 지연시간과 정책 제외 여부를 JSON으로 반환한다. 실제 fixture baseline은 fulltext recall@3 `0.75`, vector/hybrid `1.00`, 전 모드 `policy_safe=true`였다. 4개 허용 문헌 Chunk로는 운영 한국어 검색 품질을 판정할 수 없으므로, 승인된 실제 corpus 이후 질문 수와 난이도를 확대해야 한다.
