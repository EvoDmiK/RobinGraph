# DB 저장소 분담 논의 — 문헌 Chunk 검색을 PostgreSQL로 옮길지 — 2026-10-09

TEST → PROD 이관(`2026-10-09-test-to-prod-migration.md`) 직후 이어진 논의를 기록한다.
논의에서 나온 판단과 근거, 확인한 코드 구조, 아직 정하지 않은 사항을 구분해 남긴다.
설계안은 `docs/decisions/0007-chunk-search-store-split.md`(Proposed), 후속 작업은 Obsidian 백로그
RG-101로 등록했다. 이 논의에서는 코드·스키마·배포를 바꾸지 않았다.

## 논의 흐름과 결론

### 1. 관찰·문헌을 RDB에 두면 되지 않는가

사용자가 TEST → PROD 이관 중에 "관찰과 문헌은 RDB에 있어도 되지 않느냐"고 물었다.

- 방향 자체는 맞다. `docs/deployment-profile.md`에도 관찰 원장을 TimescaleDB로 옮기는 확장안이 있다.
- 그러나 현재 API는 관찰(`retrieval/operational_neo4j.py`)과 문헌 Chunk의 전문·벡터 검색
  (`retrieval/neo4j_hybrid.py`)을 Neo4j에서 읽는다. 옮기면 데이터 이관이 아니라 검색 코드 재작성이다.
- 당시 TEST 기준 Observation 116개, Document 2개, Chunk 4개로 양이 적어 이전 이득이 없었다.
  노드 474,998개의 대부분은 TraitClaim 174,843, EvidenceUnit 136,213, ExternalIdentifier 60,796이다.
- 결론: 이관은 구조를 바꾸지 않고 그대로 수행했다(완료). RDB 이전은 별도 작업으로 미뤘다.

### 2. Neo4j 벡터 인덱스와 pgvector의 차이

일반적인 특성 비교로 답했다. 이 저장소의 코드나 Neo4j 2026.08 공식 문서로 확인한 내용이 아니다.

| | Neo4j 벡터 인덱스 | pgvector |
|---|---|---|
| 정체 | 그래프 DB의 인덱스 기능 | PostgreSQL 확장(`vector` 타입) |
| 인덱스 | HNSW 기반 | HNSW, IVFFlat |
| 질의 | Cypher `db.index.vector.queryNodes` 후 곧바로 그래프 확장 | SQL `ORDER BY embedding <=> $1` |
| 필터링 | 검색 후 `WHERE`로 거름, 인덱스 안 사전 필터는 제한적 | SQL `WHERE`·조인과 자유롭게 결합(필터가 강하면 근사 검색이 놓칠 수 있음) |
| 강점 | 후보에서 Claim→Evidence→출처로 이어지는 GraphRAG | 정형 조건 필터, 조인·집계, 트랜잭션, 백업·운영 |
| 약점 | 벡터 대량 워크로드에 덜 최적화 | 그래프 순회가 불편 |

### 3. 문헌 Chunk는 계속 늘어난다 → 분리 방향

사용자가 문헌 Chunk가 점점 늘어난다고 알려 주었다. 이에 따라 방향을 정했다.

- **Chunk 본문·벡터·전문 색인은 PostgreSQL(pgvector), 그래프 관계는 Neo4j**로 나누는 쪽이 늘어나는 규모에 맞다.
- 근거(추정, 실측 아님): 512차원 float32 벡터는 하나에 약 2KB다. Chunk 100만 개면 벡터만 약 2GB이고
  HNSW 오버헤드가 더해진다. PROD Neo4j는 메모리 16GB NAS에서 다른 서비스와 함께 동작한다.
  라이선스·출처·기간 같은 정형 조건으로 먼저 거르는 검색도 SQL 쪽이 자연스럽다.
- 원장 구조와도 맞다. `ingest` 스키마가 이미 원본 레코드와 outbox(ADR-0006)를 갖고 있다.
- **이전 시점의 규모 기준은 정하지 않았다.** "약 10만 개"는 임의의 예시였고 실측으로 정해야 한다.
  ADR-0001도 "관찰 기록과 문헌 청크의 규모 및 실제 성능을 측정한 후 유지 여부를 다시 판단한다"고 정했다.

### 4. 현재 검색 코드 구조 (읽기 전용으로 확인)

`src/robingraph/retrieval/neo4j_hybrid.py`의 `Neo4jHybridSearch.search`:

1. Neo4j FULLTEXT로 chunk id 순위를 구한다. `escape_lucene_query_text`가 Lucene 연산자를 무력화한다.
2. 임베더가 있고 벡터 인덱스 차원이 맞으면 VECTOR 인덱스로 순위를 구한다. 노드의 `hybrid_content_hash`,
   모델명, 차원, 정규화 여부도 재확인한다. 안 맞으면 전문 검색만 하고 `warnings`에 이유를 남긴다.
3. 후보 id 전부를 `_RECHECK_AND_CITE_QUERY`로 보내 Chunk와 Document 양쪽의
   `SourceDataset.policy_status = 'allowed'`를 다시 확인하고 본문·출처·라이선스를 가져온다.
   통과 못 한 id는 모든 채널에서 제거한다(fail-closed). 경고에는 개수만 쓰고 id를 쓰지 않는다.
4. `embedding_allowed`는 벡터 채널에만 적용한다.
5. `retrieval/hybrid.py`의 RRF가 두 순위를 합친다. 이 모듈은 Neo4j에 의존하지 않는다.

| 부분 | Neo4j 결합 |
|---|---|
| `hybrid.py` RRF | 없음. 그대로 재사용 가능 |
| 전문·벡터 순위 구하기 | 강함. PostgreSQL 구현으로 대체할 부분 |
| 라이선스 재확인·출처 조회 | 강함. 그래프 관계를 따라가는 쿼리라 가장 까다로움 |
| 인덱스 생성·적재(`bootstrap_hybrid_search_schema`, `index_chunks`) | 강함. 쓰기 경로 |

호출처는 `api/app.py`, `cli.py`, `scripts/load_pmc_pilot.py`이며 모두 `search()`와
`HybridSearchRequest`만 거친다. 인터페이스가 좁아 구현 교체가 쉽다. 쿼리에 `:Fixture` 레이블이 붙어 있어
현재 검색은 fixture·파일럿 코퍼스를 대상으로 한다.

### 5. 정책 재확인 2단계 설계 (ADR-0007 제안)

- 정책의 기준값(`SourceDataset.policy_status`, `Document.embedding_allowed`)은 Neo4j에 유지한다.
- PostgreSQL이 정책 사본 플래그로 사전 필터해 후보를 뽑고, Neo4j가 권위 있는 재확인을 한다.
  사본은 결과가 모자라지 않게 하는 성능 최적화이고 보안 경계는 Neo4j 재확인이다.
- Neo4j 재확인이 안 되면 PostgreSQL 결과만 내보내지 않는다. 현행 fail-closed 규칙을 그대로 보존한다.
- `search()` 시그니처와 RRF는 유지하고 순위 생성과 재확인을 인터페이스 뒤로 뺀다.
- 전환은 이중 적재 → 그림자 비교 → 전환 → Neo4j 속성 제거 순이다.

## 새로 확인된 제약과 위험

- **pgvector 가용성 미확인**: 5433 포트 PostgreSQL은 n8n과 공유하는 `postgres:16-alpine` 컨테이너다.
  이 이미지에 pgvector가 있는지 확인하지 못했고 일반적으로 기본 포함이 아니다. NAS의 TimescaleDB
  컨테이너(`timescale/timescaledb:latest-pg16`)도 확인하지 못했다. 검색용 PostgreSQL을 별도 인스턴스로
  두는 방안을 함께 검토해야 한다.
- **한국어 전문 검색**: PostgreSQL 기본 `tsvector`는 한국어 형태소 분석을 하지 않는다. `pg_trgm`,
  `pg_bigm`, `pgroonga`를 후보로 보지만 이 환경에서 검증하지 않았다. 전문 채널 품질이 하이브리드 결과를
  좌우하므로 평가 세트로 먼저 비교해야 한다.
- **임베딩 프로필 변경**: `vector(N)`은 차원이 고정이라 모델·차원이 바뀌면 프로필별 테이블이나 부분 인덱스가 필요하다.
- **정책 사본의 어긋남**: 재확인이 노출을 막지만 어긋남이 길면 결과가 모자란다. 어긋남을 재는 지표가 필요하다.
- **사전 필터와 근사 검색**: 정책 필터가 실제로 얼마나 걸러내는지 먼저 확인해야 한다.
- **RG-014와의 충돌 가능성**: HippoRAG 스타일 검색(RG-014)도 `retrieval/hybrid.py`, `retrieval/neo4j_hybrid.py`를
  수정 대상으로 잡고 있다. 두 작업의 순서와 인터페이스를 함께 정해야 한다.

## 결정된 것과 정해지지 않은 것

| 구분 | 내용 |
|---|---|
| 결정됨 | TEST → PROD 이관은 구조 변경 없이 전부 그대로 수행(완료). 관찰·문헌의 RDB 이전은 이번 이관에서 제외 |
| 방향만 정함 | 문헌 Chunk가 늘어나는 것을 전제로 Chunk 본문·벡터·전문 색인은 PostgreSQL, 그래프 관계는 Neo4j |
| 제안 상태 | 정책 재확인 2단계 설계(ADR-0007, Proposed) |
| 정해지지 않음 | 이전 시점과 규모 기준, 검색용 PostgreSQL 인스턴스(기존 공유 vs 별도), 한국어 전문 검색 방식, 관찰의 RDB 이전 여부와 시점, RG-014와의 순서 |

## 확인하지 않은 것

- 실제 Chunk 수와 Neo4j 검색 지연·메모리 사용(실측하지 않음)
- 정책 필터 탈락률
- Neo4j 2026.08의 벡터 인덱스 세부 기능(사전 필터 지원 여부 등)
- 후보 PostgreSQL 이미지의 pgvector·한국어 전문 검색 확장 설치 가능 여부
- `tests/test_neo4j_hybrid.py` 실행(코드 읽기만 했고 테스트는 돌리지 않음)

## 후속

- Obsidian 백로그에 RG-101(DB 작업은 100번대로 관리)로 등록했다. 첫 단계는 실측이다.
- 설계 확정(ADR-0007 승인)은 실측과 인프라 확인 뒤에 한다.
- 관련 문서: `docs/decisions/0001-primary-database.md`, `docs/decisions/0006-postgresql-ingest-control-plane.md`,
  `docs/decisions/0007-chunk-search-store-split.md`, `docs/work-log/2026-10-09-test-to-prod-migration.md`
