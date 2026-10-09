# ADR-0007: 문헌 Chunk 검색 저장소 분리와 정책 재확인 설계

- 상태: Proposed
- 작성일: 2026-10-09
- 결정 대상: 문헌 Chunk의 본문·임베딩·전문 검색을 PostgreSQL로 옮길 때의 정책 재확인 구조
- 관련: ADR-0001(기본 데이터베이스), ADR-0003(라이선스 정책), ADR-0006(PostgreSQL ingest 제어면)

## 맥락

ADR-0001은 MVP에서 Neo4j 한 인스턴스에 도메인 그래프와 Chunk 벡터·전문 인덱스를 두고,
"관찰 기록과 문헌 청크의 규모 및 실제 성능을 측정한 후 유지 여부를 다시 판단한다"고 정했다.
문헌 Chunk는 앞으로 계속 늘어난다. 늘어나면 Chunk 본문과 벡터가 Neo4j의 페이지 캐시와
메모리를 차지하고(512차원 float32 벡터는 하나에 약 2KB), 라이선스·출처 같은 정형 조건으로
먼저 거른 뒤 검색하기 어렵다. 이 문서는 Chunk 검색을 PostgreSQL(pgvector)로 옮기는 경우의
설계를 정리한다. 이전 시점과 규모 기준은 실측(별도 작업)으로 정하며 이 문서가 정하지 않는다.

## 현재 구조 (코드 확인 결과)

`src/robingraph/retrieval/neo4j_hybrid.py`의 `Neo4jHybridSearch.search`는 다음 순서로 동작한다.

1. Neo4j FULLTEXT 인덱스로 chunk id 순위를 구한다(`escape_lucene_query_text`로 Lucene 연산자를 무력화).
2. 질의 임베더가 있고 벡터 인덱스 차원이 일치하면 VECTOR 인덱스로 chunk id 순위를 구한다.
   노드 자체의 `hybrid_content_hash == content_hash`, 모델명, 차원, 정규화 여부도 재확인한다.
   조건이 안 맞으면 전문 검색만 하고 이유를 `warnings`에 남긴다. 벡터를 만들어 채우지 않는다.
3. 후보 id 전부를 `_RECHECK_AND_CITE_QUERY`로 보내, Chunk와 Document 양쪽의
   `SourceDataset.policy_status = 'allowed'`를 다시 확인하고 본문·출처·라이선스를 가져온다.
   통과하지 못한 id는 모든 채널의 순위에서 빠진다(fail-closed).
4. `embedding_allowed`는 필터가 아니라 값으로 돌려받아 벡터 채널에만 적용한다.
   문서의 임베딩 허용이 취소돼도 본문 저장 허용이 유지되면 전문 검색에는 남을 수 있다.
5. `hybrid.py`의 RRF가 두 순위를 합친다. 이 모듈은 Neo4j에 의존하지 않는다.

정책 판단의 기준 데이터는 Neo4j의 `SourceDataset.policy_status`와 `Document.embedding_allowed`다.
정책 위반 id는 경고 문구에 노출하지 않고 개수만 알린다(존재 여부가 새지 않도록).
호출처는 `api/app.py`, `cli.py`, `scripts/load_pmc_pilot.py`이며 모두 `search()`와
`HybridSearchRequest`만 거친다.

## 결정 (제안)

### 1. 책임 분리

| 데이터 | 기준 저장소 | 이유 |
|---|---|---|
| Chunk 본문, 임베딩, 전문 검색용 색인 | PostgreSQL | 규모 증가와 사전 필터링, 대량 적재·재임베딩에 유리 |
| Document, Chunk 식별 노드(id, ordinal), HAS_CHUNK, EvidenceUnit, Claim 관계 | Neo4j | 근거 연결과 출처 추적은 그래프 순회가 본업 |
| 라이선스 정책의 기준값(`SourceDataset.policy_status`, `Document.embedding_allowed`) | Neo4j (유지) | 기존 단일 기준을 바꾸지 않아 fail-closed 규칙을 그대로 유지 |

### 2. 검색 흐름: SQL 사전 필터 + Neo4j 권위 재확인

```
질의 → PG: (정책 비정규화 플래그로 사전 필터) 전문/벡터 top-k 후보 chunk id
     → Neo4j: id 목록으로 _RECHECK_AND_CITE (정책·출처·locator 재확인, 본문은 가져오지 않음)
     → 통과한 id만 순위 유지 → hybrid.fuse_hybrid_results (변경 없음)
```

- PG의 Chunk 행에 `policy_allowed`, `embedding_allowed`를 **비정규화한 사본**으로 두고 SQL `WHERE`로
  먼저 거른다. 이렇게 하지 않으면 top-k를 뽑은 뒤 정책에서 대부분 탈락해 결과가 모자라진다.
- 그러나 이 사본은 **권위가 아니다**. Neo4j 재확인을 반드시 거치고, 통과하지 못한 id는 버린다.
  사본이 정책 변경보다 늦게 갱신돼도 노출은 일어나지 않는다(성능 최적화일 뿐 보안 경계가 아님).
- 본문은 PG에서 가져오고, Neo4j 재확인 쿼리는 `c.text`를 반환하지 않고 `source_id`, `source_url`,
  `locator`, `license_name`, `embedding_allowed`만 반환하도록 줄인다.
- 후보를 넉넉히 뽑는다(`top_k × overfetch`). 재확인 후 `limit`에 모자라면 한 번만 더 넓혀 조회하고,
  그래도 모자라면 있는 만큼 반환한다(무한 반복 금지, 상한은 기존 `_MAX_SEARCH_BOUND` 유지).

### 3. fail-closed 규칙 (현행 동작을 그대로 보존)

- Neo4j 재확인이 실패하거나 응답하지 않으면 **PG만으로 만든 결과를 반환하지 않고** 오류 또는 빈 결과로 처리한다.
- 재확인에서 빠진 id는 전문·벡터 두 순위 모두에서 제거한다.
- `embedding_allowed`는 벡터 채널에만 적용한다. 전문 채널은 본문 저장 허용만 요구한다.
- 경고에는 개수만 쓰고 id를 쓰지 않는다.
- 벡터 채널은 모델명·차원·정규화·content_hash가 현재 프로필과 같은 행만 사용한다.
  불일치 시 전문 검색으로 내려가고 경고를 남기며 벡터를 임의로 만들지 않는다.

### 4. PostgreSQL 스키마 초안

```sql
-- ingest 스키마와 분리된 검색 전용 스키마
CREATE TABLE search.chunk (
  chunk_id        text PRIMARY KEY,
  document_id     text NOT NULL,
  ordinal         int  NOT NULL,
  text            text NOT NULL,
  content_hash    text NOT NULL,
  policy_allowed  boolean NOT NULL,      -- Neo4j 기준값의 비정규화 사본
  embedding_allowed boolean NOT NULL,    -- 동일
  policy_synced_at timestamptz NOT NULL
);

CREATE TABLE search.chunk_embedding (
  chunk_id     text NOT NULL REFERENCES search.chunk,
  profile_id   text NOT NULL,            -- 모델+차원+정규화
  content_hash text NOT NULL,            -- 임베딩 시점의 본문 해시
  embedding    vector(512) NOT NULL,
  PRIMARY KEY (chunk_id, profile_id)
);
```

- `vector(N)`은 차원이 고정이므로 임베딩 프로필이 바뀌면 프로필별 테이블 또는 부분 인덱스가 필요하다.
  새 프로필 임베딩을 다른 `profile_id`로 병행 적재한 뒤 전환하고 이전 프로필을 지운다.
- HNSW 인덱스는 `profile_id`별 부분 인덱스로 만든다. 코사인 연산자와 정규화 여부를 프로필과 일치시킨다.

### 5. 쓰기 경로와 정책 동기화

- 현행 `index_chunks`의 "완전한 현재 집합으로 전체 교체" 의미(한 트랜잭션에서 쓰고, 집합에 없는 항목은 무효화)를
  PG 트랜잭션으로 그대로 구현한다. 부분 갱신 상태가 관측되지 않아야 한다.
- 정책 변경(데이터셋 허용 취소, 임베딩 허용 취소)은 ADR-0006의 outbox 이벤트로 PG 사본을 갱신한다.
  갱신 지연 동안에도 2번의 Neo4j 재확인이 노출을 막는다.
- 쓰기 시점 fail-closed(현 `_INDEX_WRITE_QUERY`가 라이선스 사슬과 `embedding_allowed`를 쓰기 쿼리 자체에서 확인)는
  PG 적재 전에 Neo4j에서 허용 여부를 조회하는 단계로 옮긴다. 입력 배치를 신뢰하지 않는다는 원칙은 유지한다.

### 6. 전문 검색

현재는 Neo4j FULLTEXT 인덱스와 분석기를 쓴다. PostgreSQL 기본 `tsvector`는 한국어 형태소 분석을 하지 않는다.
후보는 다음과 같으며 어느 것도 이 저장소에서 검증하지 않았다.

| 후보 | 장점 | 확인할 점 |
|---|---|---|
| `pg_trgm` 트라이그램 | 설치 쉬움, 형태소 분석 불필요 | 긴 문서에서 정밀도·성능 |
| `pg_bigm` / `pgroonga` | 한국어·CJK 전문 검색에 쓰임 | 사용 중인 PostgreSQL 이미지에 설치 가능한지 |
| 전문 검색은 Neo4j 유지 | 이전 범위 축소 | Chunk 본문을 Neo4j에도 둬야 해 규모 문제가 남음 |

전문 채널의 품질이 떨어지면 하이브리드 결과가 나빠지므로, 이 선택은 평가 세트로 먼저 비교해야 한다.

### 7. 코드 구조

- `search(settings, request, *, query_embedder)` 시그니처와 `HybridSearchRequest`를 유지한다.
- 채널별 순위 생성(전문, 벡터)과 재확인을 인터페이스로 분리하고 구현체를 Neo4j/PG로 둔다.
  `hybrid.py`의 RRF는 바꾸지 않는다.
- 설정값(예: `ROBINGRAPH_CHUNK_SEARCH_BACKEND=neo4j|postgres`)으로 전환한다.
- 호출처(`api/app.py`, `cli.py`, `load_pmc_pilot.py`)는 `search()`만 쓰므로 변경 범위가 작다.

## 전환 절차

1. PG에 `search` 스키마와 확장을 준비하고 Chunk·임베딩을 이중 적재한다(Neo4j는 그대로 서비스).
2. 그림자 비교: 같은 질의 세트로 두 백엔드 결과를 비교해 겹침·순위 차이·누락·정책 제외 수를 기록한다.
   기존 평가 코드(`retrieval/evaluation.py`)와 평가 세트를 활용한다.
3. 품질과 지연이 기준을 만족하면 설정값으로 PG 백엔드를 켠다.
4. 일정 기간 뒤 Neo4j의 Chunk 본문·벡터 속성과 인덱스를 제거하고, Chunk 식별 노드와 관계만 남긴다.

## 검증 계획

`tests/test_neo4j_hybrid.py`의 시나리오를 두 백엔드에 같이 적용한다.

- 데이터셋 정책 취소 시 해당 Chunk가 모든 채널에서 사라지는가(PG 사본이 오래된 경우 포함)
- 문서 임베딩 허용만 취소했을 때 전문에는 남고 벡터에서는 빠지는가
- 프로필(모델·차원·정규화) 불일치와 `content_hash` 불일치 시 벡터 채널이 꺼지고 경고가 나오는가
- Neo4j 재확인 불가 시 PG 결과가 새어 나가지 않는가
- 경고 문구에 제외된 id가 들어가지 않는가
- 전문 질의의 특수문자·불리언 키워드가 안전하게 처리되는가
- 이중 적재 후 두 백엔드 결과 비교(겹침·순위)

## 위험과 미해결 사항

- **인프라**: 현재 5433 포트의 PostgreSQL은 n8n이 함께 쓰는 `postgres:16-alpine` 컨테이너다.
  이 이미지에 pgvector가 있는지 확인하지 않았고 일반적으로 기본 포함이 아니다. NAS의 TimescaleDB
  컨테이너(`timescale/timescaledb:latest-pg16`)에 pgvector가 있는지도 확인하지 않았다.
  n8n과 인스턴스를 공유하는 점과 NAS 메모리(16GB)를 고려하면 검색용 PostgreSQL을 별도 인스턴스로
  두는 방안을 함께 검토해야 한다.
- **정합성**: 사본 정책과 Neo4j 기준값이 어긋나는 구간. 재확인이 노출을 막지만, 어긋남이 길어지면
  결과가 모자라는 문제가 생긴다. 어긋남을 측정하는 지표가 필요하다.
- **두 번의 왕복**: 지연이 늘어난다. 후보 수와 재확인 쿼리 비용은 실측해야 한다.
- **사전 필터와 근사 검색**: 필터가 강하면 HNSW 근사 검색이 결과를 놓칠 수 있다. 정책 필터가 실제로
  얼마나 많이 걸러내는지 먼저 확인해야 한다.
- **현재 코드 범위**: 쿼리의 `:Fixture` 레이블이 보여주듯 검색은 fixture·파일럿 코퍼스를 대상으로 한다.
  PROD 코퍼스가 커지는 경로와 이 레이블 정책을 같이 정리해야 한다.
- **규모 기준**: 이전 시점(Chunk 수, 지연, 메모리)은 실측 전이라 정하지 않았다.

## 하지 않는 것

- 정책의 기준 데이터를 PG로 옮기지 않는다.
- 관찰(Observation)·분류·Claim은 이전하지 않는다. 이 문서는 문헌 Chunk 검색만 다룬다.
- 이 문서는 구현을 포함하지 않는다. 코드, 스키마, 배포는 바뀌지 않았다.
