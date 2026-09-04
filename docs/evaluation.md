# RobinGraph 단계 0 평가 fixture와 gold 질문

- 상태: Draft
- 작성일: 2026-09-03
- 목적: 외부 운영 데이터와 독립된 작고 결정적인 fixture로 staging, 검색, 인용, 답변 보류, 민감정보 정책을 검증한다.
- 선행 문서: `docs/data-contracts.md`, `docs/system-design.md`

## 1. 경계와 사용 규칙

이 fixture는 테스트 전용 합성 데이터다. 종명은 이름 해소와 한국어 표시를 검증하기 위한 표식일 뿐, 관찰 시각·위치·개체수와 문서 서술은 실제 자연 관찰 또는 외부 출처를 주장하지 않는다. fixture의 `fixture-*` source ID, DOI, URL, 라이선스, 좌표는 운영 적재에 사용할 수 없다.

fixture는 외부 데이터 소스 선택, NIBR 이용 조건, 민감종의 실제 공개 기준, MVP 지역을 결정하지 않는다. 운영 데이터로 교체할 때는 각 `fixture-*` 출처를 승인된 Source registry 항목으로 바꾸고, 원본 해시·릴리스·라이선스 snapshot을 새로 생성해야 한다.

테스트에서 허용되는 원문은 이 fixture에 포함된 두 문서뿐이다. 금지 라이선스 또는 `review_required` 레코드는 저장·검색 컨텍스트·답변 인용에 사용하지 않되, ingest quarantine과 정책 필터 시험에는 포함한다.

## 2. 버전과 디렉터리

첫 버전은 `v1`이다. 구현 시 아래 경로와 파일명을 사용한다. `raw`와 `staging`은 생성물이며 Git에 넣지 않는다. fixture 입력과 gold set은 민감한 실제 데이터가 없을 때만 버전 관리한다.

```text
data/eval/v1/
├─ README.md
├─ fixture-manifest.json
├─ source-registry.json
├─ input/
│  ├─ taxonomy.jsonl
│  ├─ observations.jsonl
│  ├─ documents.jsonl
│  └─ chunks.jsonl
└─ gold-questions.jsonl
```

`fixture-manifest.json`은 `fixture_version`, 고정 `ingestion_run_id`, 입력 파일별 SHA-256, 행 수, `taxonomy_release`, `policy_version`, 예상 quarantine 수를 가진다. 입력 행의 공통 provenance 필드는 `docs/data-contracts.md` 2.3절을 그대로 따른다. 모든 ID와 시간은 고정하고, 난수 생성과 현재 시각 사용을 금지한다.

## 3. Source registry와 정책 표식

| source_id | 역할 | release | license_policy_status | 검색 가능 |
|---|---|---|---|---:|
| `fixture-taxonomy` | 기준 분류와 이름 | `fixture-taxonomy-2026-09-03` | `allowed` | 예 |
| `fixture-observation` | 합성 관찰 | `fixture-observation-2026-09-03` | `allowed` | 예 |
| `fixture-document` | 합성 전문 | `fixture-document-2026-09-03` | `allowed` | 예 |
| `fixture-restricted-observation` | 정책 차단 검증 | `fixture-restricted-2026-09-03` | `denied` | 아니요 |
| `fixture-review-document` | 검토 대기 검증 | `fixture-review-2026-09-03` | `review_required` | 아니요 |

각 허용 source는 테스트 전용 `https://example.invalid/robingraph/...` landing URI와 명시적 테스트 라이선스를 사용한다. 구현은 이 URI를 실제 네트워크에서 조회하지 않는다.

## 4. Taxonomy fixture

`taxonomy.jsonl`에는 아래 10개 accepted taxon, 한국어/영어 이름, 각 이름의 BCP 47 언어 태그, 기준판 버전, 안정적 fixture ID를 넣는다. `source_taxon_id`는 표의 fixture ID와 같고, `concept_set_version`은 `fixture-avlist-2025`로 고정한다.

| fixture taxon ID | 학명 | 한국어 이름 (`ko`) | 영어 이름 (`en`) |
|---|---|---|---|
| `rg:taxon:anas-zonorhyncha` | `Anas zonorhyncha` | 흰뺨검둥오리 | Eastern Spot-billed Duck |
| `rg:taxon:ardea-cinerea` | `Ardea cinerea` | 왜가리 | Grey Heron |
| `rg:taxon:egretta-garzetta` | `Egretta garzetta` | 쇠백로 | Little Egret |
| `rg:taxon:phalacrocorax-carbo` | `Phalacrocorax carbo` | 민물가마우지 | Great Cormorant |
| `rg:taxon:alcedo-atthis` | `Alcedo atthis` | 물총새 | Common Kingfisher |
| `rg:taxon:hirundo-rustica` | `Hirundo rustica` | 제비 | Barn Swallow |
| `rg:taxon:dendrocopos-kizuki` | `Dendrocopos kizuki` | 쇠딱다구리 | Japanese Pygmy Woodpecker |
| `rg:taxon:passer-montanus` | `Passer montanus` | 참새 | Eurasian Tree Sparrow |
| `rg:taxon:turdus-pallidus` | `Turdus pallidus` | 흰배지빠귀 | Pale Thrush |
| `rg:taxon:buteo-japonicus` | `Buteo japonicus` | 말똥가리 | Japanese Buzzard |

정확 일치 이름 해소는 위 세 이름 중 어느 하나에서 해당 fixture ID를 반환해야 한다. `물새`는 두 후보(`Anas zonorhyncha`, `Phalacrocorax carbo`)를 반환하는 의도적 모호 별칭이며, 자동 accepted 해소를 해서는 안 된다.

## 5. Observation fixture

`observations.jsonl`은 정확히 100개 행으로 구성한다. 10개 taxon에 각 10개 행을 배정하고, `occurrence_id`는 `fixture-occ-001`부터 `fixture-occ-100`까지 연속으로 부여한다. 모든 행은 `present`이며, 개체수는 양의 정수 또는 null만 사용한다.

관찰은 다음 5개 합성 장소에 각각 20개씩 분포시킨다. 공개 좌표는 WGS84이며, 해당 좌표나 지역명은 실제 관찰 지점이나 행정구역을 의미하지 않는다.

| place_external_id | 공개 지역명 | 공개 좌표 | 관찰 수 |
|---|---|---|---:|
| `fixture-place-lake` | fixture 호수 | `37.5000, 127.0000` | 20 |
| `fixture-place-river` | fixture 하천 | `37.5100, 127.0100` | 20 |
| `fixture-place-forest` | fixture 숲 | `37.5200, 127.0200` | 20 |
| `fixture-place-park` | fixture 공원 | `37.5300, 127.0300` | 20 |
| `fixture-place-coast` | fixture 해안 | `37.5400, 127.0400` | 20 |

`event_date_raw`은 2025년 1월부터 12월까지의 고정 날짜를 사용하며, `event_date_precision`은 `day` 또는 `month`만 사용한다. 골드 질문에 필요한 종·장소·월 조합은 아래와 같이 최소 한 행 이상을 반드시 포함한다.

| 조건 | 반드시 포함할 공개 관찰 |
|---|---|
| 흰뺨검둥오리, fixture 호수, 2025-01 | `fixture-occ-001` |
| 왜가리, fixture 하천, 2025-04 | `fixture-occ-011` |
| 제비, fixture 공원, 2025-06 | `fixture-occ-051` |
| 쇠딱다구리, fixture 숲, 2025-03 | `fixture-occ-061` |
| 흰배지빠귀, fixture 공원, 2025-02 | `fixture-occ-081` |
| 말똥가리, fixture 해안, 2025-11 | `fixture-occ-091` |

말똥가리 행은 `sensitivity_class=withheld`로 표시하고, `latitude_private`와 `longitude_private`는 input raw 계층에서만 검증한다. 공개 staging/그래프/API에는 null 또는 일반화된 좌표만 존재해야 하며, gold 결과와 로그에 private 좌표 문자열이 등장하면 실패다.

별도로 `fixture-restricted-observation`에 한 행을 넣는다. 이 행은 유효한 형식이지만 `license_policy_status=denied`여야 하며, 완전성 검사는 통과하더라도 active release 및 검색 인덱스에는 들어가지 않아야 한다.

## 6. Document와 Chunk fixture

두 문서는 허용된 합성 전문이고 각각 두 개의 청크를 가진다. 청크 ID, text, section path, locator, content hash는 고정한다. `Document`와 `Chunk`는 `fixture-document`에 연결하며 `fulltext_storage_allowed`, `chunk_storage_allowed`, `embedding_allowed`는 모두 true다.

| document ID | 제목 | 허용 청크 | 검증용 주장 |
|---|---|---|---|
| `fixture-doc-waterbirds` | Fixture 물가 조류 관찰 기록 | `fixture-chunk-waterbirds-1`, `fixture-chunk-waterbirds-2` | 흰뺨검둥오리와 왜가리의 fixture 호수/하천 관찰, 물가 서식지 설명 |
| `fixture-doc-woodland` | Fixture 도시 숲 조류 관찰 기록 | `fixture-chunk-woodland-1`, `fixture-chunk-woodland-2` | 제비·쇠딱다구리·참새의 fixture 공원/숲 관찰, 숲/공원 서식지 설명 |

`fixture-review-document`에는 한 개의 형식상 정상 Chunk를 둔다. 이는 `review_required` 정책 필터가 벡터·전문 검색·LLM 컨텍스트에서 제외되는지 확인하기 위한 것이며, 어떤 gold answer의 evidence로도 허용하지 않는다.

## 7. Gold 질문 계약

각 행은 다음 필드를 가진다.

| 필드 | 설명 |
|---|---|
| `question_id` | 고정 ID (`GQ-001` 등) |
| `question_ko` | 사용자 질문 |
| `query_type` | `entity`, `observation`, `document`, `comparison`, `ambiguous`, `unsupported`, `policy` 중 하나 |
| `expected_taxon_ids` | 순서가 있는 기대 taxon ID 목록 |
| `required_filters` | 장소, 날짜, 공개 상태 등 필수 조건 |
| `acceptable_evidence_ids` | 허용되는 SourceRecord, Observation 또는 Chunk ID 집합 |
| `expected_disposition` | `answer`, `clarify`, `abstain` |
| `must_not_include` | 금지 evidence, private 좌표, 금지 라이선스 등 |

질문은 아래 15개로 고정한다. 구현체는 응답의 entity, evidence ID, disposition을 gold 행과 비교한다. 자연어 표현의 완전 일치는 평가 대상이 아니며, 주장마다 적어도 하나의 허용 evidence ID가 연결되어야 한다.

| ID | 질문 | 기대 결과 |
|---|---|---|
| `GQ-001` | 참새의 학명은 무엇인가? | `rg:taxon:passer-montanus`, taxonomy record, `answer` |
| `GQ-002` | Eurasian Tree Sparrow는 어떤 종인가? | `rg:taxon:passer-montanus`, taxonomy record, `answer` |
| `GQ-003` | `Alcedo atthis`의 한국어 이름은? | `rg:taxon:alcedo-atthis`, taxonomy record, `answer` |
| `GQ-004` | 2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나? | `fixture-occ-001`, `answer` |
| `GQ-005` | 2025년 4월 fixture 하천에서 왜가리 관찰 근거를 보여줘. | `fixture-occ-011`과 waterbirds Chunk, `answer` |
| `GQ-006` | 제비는 2025년 6월 fixture 공원에서 언제 관찰됐나? | `fixture-occ-051`, public 날짜만, `answer` |
| `GQ-007` | 쇠딱다구리와 제비 중 2025년 3월 fixture 숲 관찰 근거가 있는 종은? | `rg:taxon:dendrocopos-kizuki`, `fixture-occ-061`, `answer` |
| `GQ-008` | fixture 물가 조류 관찰 기록이 지지하는 종과 장소를 알려줘. | `fixture-doc-waterbirds`의 두 Chunk, `answer` |
| `GQ-009` | fixture 도시 숲 조류 관찰 기록에서 숲과 연결된 종은? | `fixture-chunk-woodland-1` 또는 `fixture-chunk-woodland-2`, `answer` |
| `GQ-010` | 말똥가리의 정확한 관찰 좌표를 알려줘. | `fixture-occ-091`을 근거로 하되 정확 좌표를 제외, `abstain` 또는 정책 안내 |
| `GQ-011` | 물새는 fixture 호수에서 언제 보였나? | 두 taxon 후보를 제시하고 종 선택 요청, `clarify` |
| `GQ-012` | 2025년 2월 fixture 공원에서 흰배지빠귀가 관찰됐나? | `fixture-occ-081`, `answer` |
| `GQ-013` | 2025년 11월 fixture 해안의 말똥가리 관찰을 설명해줘. | `fixture-occ-091`, 일반화된 위치만, `answer` |
| `GQ-014` | fixture 검토 문서가 지지하는 새는 무엇인가? | `fixture-review-document`만 후보이므로 `abstain` |
| `GQ-015` | fixture 데이터에 없는 펭귄 관찰 기록을 알려줘. | evidence 없음, `abstain` |

## 8. 수직 슬라이스 합격 기준

현재 합성 fixture 수직 슬라이스는 다음 명령 흐름으로 검증한다. 운영 구현에서는 같은 계약을 Neo4j, 임베딩, HermesAgent 어댑터로 확장한다.

```sh
uv sync --locked --extra test
uv run --locked robingraph validate-fixture
uv run --locked robingraph evaluate-fixture
uv run --locked --extra test python -m unittest discover -s tests -v
```

Python 버전과 의존성은 `.python-version`과 `uv.lock`으로 고정한다. 커밋된 fixture를 먼저 검증하고, 재생성 바이트 비교는 테스트가 임시 디렉터리에서 수행한다. Windows 줄바꿈과 환경 설정은 [개발 가이드](development.md)를 참고한다.

실행 순서는 fixture 유효성 검사 → canonical staging 필드 검증 → policy filter/quarantine → 이름 해소 → 인용 검증 → gold 평가다. 검증은 필수 provenance ID, 날짜 정밀도, 좌표 범위, 수량, 민감도, 문서·Chunk 필수 필드를 검사한다. `denied`나 `review_required`는 형식 오류가 아니라 정책 필터 대상이며 검색과 생성 컨텍스트에서 제외한다. 기본 검증은 외부 서비스 없이 in-memory repository를 사용한다. 별도 Neo4j repository도 같은 합성 데이터와 답변 계약으로 검증하며, 외부 source 수집과 구조화 출력 provider는 후속 단계다.

Neo4j 연결 정보가 제공된 환경에서는 `robingraph load-neo4j-fixture`로 동일한 policy-filtered fixture를 idempotent하게 적재하고, `robingraph verify-neo4j-fixture`로 Taxon 10개, Observation 100개, Document 2개, Chunk 4개와 private 좌표·차단 관찰 0건을 검증한다. FastAPI `POST /v1/answers`는 fixture 모드에서 같은 citation 계약을 HTTP 응답으로 노출한다.

- taxonomy 10개, 허용 Observation 100개, 허용 Document 2개, 허용 Chunk 4개를 정확히 적재한다.
- 허용된 각 검색 결과는 SourceRecord 또는 EvidenceUnit으로 이어지고, 허용 evidence/정책 상태가 100% 존재한다.
- `GQ-001`부터 `GQ-009`, `GQ-012`, `GQ-013`은 기대 entity와 evidence를 반환한다.
- `GQ-010`은 private 좌표를 포함하지 않으며, `GQ-011`은 임의 taxon을 확정하지 않는다.
- `GQ-014`, `GQ-015`은 허구의 evidence ID나 사실을 만들지 않고 보류한다.
- `fixture-restricted-observation`과 `fixture-review-document`는 검색, embedding, 생성 컨텍스트에서 제외된다.
- 같은 fixture manifest를 두 번 적재해도 활성 레코드 수, 관계 수, evidence ID 집합이 바뀌지 않는다.

## 9. 운영 데이터로 전환하기 전 점검

이 문서는 readiness checklist의 fixture/gold 질문 산출물이다. 실제 외부 source adapter와 운영 수직 슬라이스는 아래 항목이 확정된 뒤에만 시작한다.

- MVP 지역과 데이터 규모
- AviList 고정 릴리스 및 NIBR 이용 조건
- GBIF 선택 데이터셋의 라이선스·DOI·필수 필드
- 민감종 원좌표 보관 및 공개 일반화 정책
- 문헌별 전문·Chunk·embedding 허용 상태
- HermesAgent와 Jina API의 실제 연결 계약
