# Embedding adapter

## BirdsNest API 계약과 연결 결과 (2026-09-04)

사용자가 제공한 `API-USAGE.md`에 맞춰 `ROBINGRAPH_JINA_API_FORMAT=birdsnest` 프로필을 추가했다. `.env.example`에 공개 endpoint와 설정을 반영했고 API 키는 저장하지 않았다.

- Endpoint: `https://embed.dove-nest.com/v1/embeddings`
- 모델: `jinaai/jina-embeddings-v3`. 짧은 별칭 `jina-embeddings-v3`도 설정으로 받되 요청·저장 프로필은 정식 이름으로 통일한다.
- 차원: 512 기본 설정. 서버가 지원하는 32/64/128/256/512/768/1024만 허용한다.
- 문서 `retrieval.passage`, 질문 `retrieval.query`, `encoding_format=float`, `max_length=1024`를 명시한다.
- 서버는 항상 L2 정규화된 벡터를 반환하는 계약이다. 지원되지 않는 `normalized` 요청 필드는 보내지 않고 실제 반환 벡터의 norm을 검사한다.
- 입력당 20,000자, 요청당 64개/200,000자 제한을 적용한다. 전체 입력을 먼저 검사하고 개수·문자 수에 따라 요청을 나눈다.
- HTTP timeout 기본 120초. 429/500/503 및 일시적인 전송 오류는 기본 2회, 0.5초/1초 간격으로 재시도한다. 400/401/413/422는 재시도하지 않는다.
- 요청에는 `User-Agent: RobinGraph/0.1`을 사용한다.

실제 확인 결과: `/healthz`는 **200 / ready**, 모델 `jinaai/jina-embeddings-v3`, MPS/float16, 기본 차원 512를 보고했다. 첫 키는 401로 거절됐으나, 사용자가 정정한 서버 Bearer 키로 **문서·검색어 임베딩 인증과 응답 검증에 성공**했다. 키는 숨김 입력으로 실행 프로세스에만 전달했고 파일에는 저장하지 않았다.

| 실제 API 스모크 검증 | 결과 |
|---|---|
| 허용 fixture 청크, `retrieval.passage` | 4개, 각 512차원, 한 요청 2.250초 |
| 검색어, `retrieval.query` | 1개, 512차원, 1.313초 |
| 벡터 L2 norm 범위 | 0.999999977 ~ 1.000000057, 검증 통과 |
| 질문 `호수와 하천에서 관찰된 물새`의 dot product 최상위 청크 | `fixture-chunk-waterbirds-1`, 점수 0.569742 |

위 표는 최초 API 단독 점검 결과이며 당시 벡터는 메모리에서 비교 후 폐기했다. 이후 실제 벡터의 Neo4j 적재·검색 연결도 아래와 같이 검증했다. 측정값은 단일 실행의 왕복 시간이며 부하 테스트나 일반적인 검색 품질 평가가 아니다.

API 계약 반영 직후 DB 없이 실행한 테스트는 82개 통과·DB 테스트 20개 skip이었다. 아래 후속 실행에서는 DB 테스트까지 모두 실행했다.

실행 시 `.env.example`의 설정을 환경 변수로 지정하고, `ROBINGRAPH_JINA_API_KEY`는 로컬 환경 또는 secret store에서 제공한다. `.env` 자동 로딩은 없다. `MAX_LENGTH`나 모델·차원 설정을 바꿀 때는 전체 문헌 벡터를 다시 생성해야 한다. 토큰 수 기준 truncation이 적용되므로 운영 문서는 1,024토큰 안에 들어오도록 청크화 정책을 정해야 한다.

## 실제 Jina → Neo4j 연결 검증 (2026-09-04)

프로젝트의 `embed_fixture_chunks` → `index_chunks` → `search` Python API로 실제 Jina 서버와 로컬 Neo4j Community 2026.07.1을 연결했다. Neo4j 주소는 테스트 전용 `bolt://127.0.0.1:17687`이다. API 키는 숨김 입력으로 프로세스에만 전달했다.

| 검증 항목 | 결과 |
|---|---|
| 문서 임베딩 | 허용 청크 4개, 각 512차원, 한 요청 1.766초 |
| Neo4j 저장 | 4개 성공, 누락 0개; 저장된 차원·모델·본문 hash·정규화 플래그 일치 |
| `호수와 하천에서 관찰된 물새` | 결합 검색 1위 `fixture-chunk-waterbirds-1`; 검색어 임베딩 포함 2.250초 |
| `공원과 숲의 새` | 결합 검색 1위 `fixture-chunk-woodland-2`; 검색어 임베딩 포함 1.031초 |
| 검색 채널 | 두 질문 모두 전문·벡터 결과를 결합, fallback 경고 0개 |
| Provenance | 반환된 모든 결과에 source ID·URL·locator·license 존재 |
| 그래프 검증 | Taxon 10, Observation 100, Document 2, Chunk 4; 비공개 좌표 속성과 제한 관찰 0개 |
| 후속 회귀 테스트 | 102/102 통과, DB 통합 20개 포함, skip 0개; gold 15/15 |

전문 검색만 사용하면 첫 질문은 물가 청크 2개, 두 번째는 숲 청크 1개를 반환했다. 결합 검색은 각각 4개를 반환했고 관련 주제 청크 2개가 상위에 위치했다. 작은 코퍼스에서 `limit=4`를 사용했으므로 하위에는 다른 주제도 포함된다. 이 결과로 일반적인 정확도나 recall 개선을 주장하지 않는다. 출처 URL과 라이선스는 합성 fixture의 `example.invalid` 값이며 실제 문헌의 권리 확인을 의미하지 않는다. Hermes/LLM 답변 생성은 이번 검증에 포함하지 않았다.

기존 테스트용 3차원 벡터 인덱스의 이름·라벨·속성·차원을 확인한 뒤 명시적으로 512차원으로 전환했다. 검증 후 벡터를 지우고 인덱스를 3차원으로 복구한 상태에서 아래 회귀 테스트를 실행했다. 실제 Jina 요청은 문서 배치 1회와 질문 2회이며 자동 테스트의 HTTP 모의 서버와 구분된다.

```powershell
$env:NEO4J_URI = 'bolt://127.0.0.1:17687'
$env:NEO4J_USERNAME = 'neo4j'
$env:NEO4J_PASSWORD = 'fixture-test-only'
$env:NEO4J_DATABASE = 'neo4j'
$env:ROBINGRAPH_NEO4J_INTEGRATION_TESTS = '1'
uv run --locked --extra test python -m unittest discover -s tests -q
uv run --locked robingraph evaluate-fixture
```

위 인증 설정은 인증을 끈 로컬 임시 인스턴스 전용이다. 실제 Jina를 다시 연결할 때는 README의 `index-neo4j-fixture --embeddings`와 `search-neo4j --hybrid` 경로를 사용하고, 대상 인덱스가 512차원인지 먼저 확인한다.

## Shared adapter

`robingraph.embeddings` exposes the shared embedding contract used by the
fixture embedding and retrieval work:

- `EmbeddingProfile(model, dimensions, normalized)` records the model/vector
  compatibility contract.
- `EmbeddedChunk(chunk_id, content_hash, vector, profile)` carries embedding
  provenance.
- `EmbeddingClient` defines `embed_documents(...)` and `embed_query(...)`.
- `JinaEmbeddingSettings`, `JinaEmbeddingClient`, and
  `embed_fixture_chunks(...)` provide the stdlib HTTP implementation.

## Configuration

The endpoint is intentionally required and has no built-in default. Configure
the adapter with these environment variables, then call
`JinaEmbeddingSettings.from_env()`:

| Variable | Required | Meaning |
|---|---:|---|
| `ROBINGRAPH_JINA_ENDPOINT` | yes | Complete `http(s)` URL for the compatible server |
| `ROBINGRAPH_JINA_MODEL` | yes | Model identifier sent in each request |
| `ROBINGRAPH_JINA_DIMENSIONS` | yes | Expected output dimension |
| `ROBINGRAPH_JINA_API_KEY` | no | Bearer token; omitted for keyless private servers |
| `ROBINGRAPH_JINA_NORMALIZED` | no | `true`/`false`, default `true` |
| `ROBINGRAPH_JINA_BATCH_SIZE` | no | Default 32; maximum 128 for jina, 64 for birdsnest |
| `ROBINGRAPH_JINA_TIMEOUT_SECONDS` | no | Per-request timeout: jina 30s, birdsnest 120s by default |
| `ROBINGRAPH_JINA_API_FORMAT` | no | `jina` (default) or `birdsnest`; the example selects birdsnest |
| `ROBINGRAPH_JINA_MAX_LENGTH` | no | BirdsNest truncation length, 1–1024 tokens, default 1024 |
| `ROBINGRAPH_JINA_MAX_RETRIES` | no | 0–3 transient-error retries; default 0 for jina, 2 for birdsnest |

In the generic `jina` profile, the client sends JSON with `model`, `task`, `dimensions`, `normalized`, and
`input` fields. Document calls use the fixed task `retrieval.passage`; query
calls use `retrieval.query`. Responses must contain exactly one indexed
`data` row per input, with a finite numeric vector of the configured
dimension and a non-zero norm. When `normalized=true`, the returned L2 norm
must be 1 within a 0.001 tolerance; a response that reports a different model
is rejected. HTTP failures, transport failures, malformed JSON, missing or
duplicate indexes, non-finite values, and dimension/count mismatches raise an
explicit `EmbeddingError` subclass.

The request/response shape follows the official Jina Embedding API's documented
JSON contract (including `POST`, `Authorization: Bearer`, `input`, model/task,
dimensions, and normalized options): [Jina Embedding API](https://jina.ai/embeddings/).
The official hosted endpoint shown by Jina is intentionally not used as a
default here. The BirdsNest profile follows the operator-supplied contract
above; live document/query requests and 512-dimensional normalized responses
were verified with the corrected server Bearer key.

## Fixture policy and integrity

`embed_fixture_chunks` performs all local checks before the first client call.
For every candidate it rechecks the chunk policy, parent document permissions,
the chunk source registry entry, and the parent document source registry entry.
Both source entries must exist, be enabled, and have `license_policy_status ==
"allowed"`. Denied, restricted, review-required, missing, orphaned, or
embedding-disallowed records are skipped, and an empty eligible set performs no
HTTP request.

Eligible chunk text is hashed as UTF-8 with SHA-256 and must match its recorded
`content_hash`; a mismatch raises `EmbeddingIntegrityError` before any request.
Returned vectors are checked again before they are wrapped in
`EmbeddedChunk`. There is no stale-vector reuse path: changing text, profile,
or permissions requires a fresh embedding operation.

No live Jina connection is made by the repository tests. `tests/test_embeddings.py`
uses injected/mock HTTP transports for task selection, bounded request batches,
errors, response validation, permission/source policy, and hash integrity.
`tests/test_embedding_flow.py` additionally exercises a real localhost HTTP
round-trip against a synthetic server, including UTF-8 requests, reordered
response indexes, normalization/model rejection, and malformed permissions.
