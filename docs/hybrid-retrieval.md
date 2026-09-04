# 문헌 청크 하이브리드 검색

2026-09-04 기준, 실제 Jina의 512차원 벡터를 로컬 Neo4j Community 2026.07.1에 적재하고 한국어 질문 2개의 결합 검색과 출처 반환까지 검증했다. 입력은 합성 fixture 청크 4개이며, 일반적인 검색 품질 평가는 후속이다. [실행 결과](embedding-adapter.md#실제-jina--neo4j-연결-검증-2026-09-04)를 참고한다.

## 실행 경로

`load-neo4j-fixture` → `index-neo4j-fixture` → `search-neo4j --question "..."` 순서로 실행한다. 기본 경로는 전문 검색만 사용한다. 환경에 Jina 연결 정보를 설정한 뒤 인덱싱에 `--embeddings`, 검색에 `--hybrid`를 붙이면 Jina 호환 HTTP 요청과 벡터 검색을 사용한다. 전체 명령은 [README](../README.md#문헌-청크-검색)에 있다.

이 경로는 문헌 근거를 검색한다. 기존 질문 API의 종·장소·기간 그래프 질의는 별도로 유지되며, LLM 답변 생성은 후속 단계다.

## 공개 Python API

- `bootstrap_hybrid_search_schema(settings, *, dimensions, config=HybridSchemaConfig())`: 명시적인 스키마 쓰기. `dimensions=None`이면 전문 검색 인덱스만 준비한다. 인덱스 이름·라벨·속성·옵션을 확인하고 ONLINE 상태를 기다린다.
- `index_chunks(settings, embedded_chunks, *, expected_profile, indexed_at)`: 현재 허용된 **전체** 임베딩 집합을 한 트랜잭션으로 반영한다. 반환하는 `ChunkIndexReport`는 `indexed`, `invalidated`, `skipped` ID를 담는다. 부분 배치 갱신용 API가 아니다.
- `search(settings, HybridSearchRequest(query_text, limit=10), *, query_embedder=None, config=...)`: 읽기 전용 검색. `HybridSearchOutcome(results, warnings)`를 반환한다.
- `HybridResult`: `chunk_id`, `text`, `score`, `channels`, `citation`을 제공한다. Citation에는 source ID·URL·인용 위치·라이선스명이 있다.
- `Neo4jHybridSearch`: 반복 검색에서 driver를 재사용할 수 있는 context manager. 스키마 준비와 인덱싱 메서드는 별도 driver를 여는 모듈 함수를 호출한다.
- `validate_embedded_chunks`, `reciprocal_rank_fusion`, `fuse_hybrid_results`: DB 없이 검증·순위 결합을 수행한다.

## 그래프와 벡터의 연결

fixture Chunk는 `HybridSearchChunk` 라벨을 가진다. 전문 검색은 이 라벨의 `text`를 대상으로 한다. 벡터가 저장된 청크에는 `HybridVectorChunk`와 다음 속성이 추가된다.

`hybrid_vector`, `hybrid_model`, `hybrid_dimensions`, `hybrid_normalized`, `hybrid_content_hash`, `hybrid_indexed_at`

SourceDataset에 저장한 `policy_status`와 Document의 `embedding_allowed`를 적재·검색에서 다시 확인한다. 문서·청크 양쪽 출처의 License 연결도 필요하다. License URI가 같더라도 출처별 정책은 SourceDataset 단위로 구분한다.

- 본문 hash가 변경되거나 문서의 임베딩 허용이 철회되면, fixture 재적재 트랜잭션에서 기존 벡터와 라벨을 제거한다.
- 입력 본문과 기록된 SHA-256가 다르면 그래프 투영을 거부한다.
- 임베딩 적재는 현재 그래프의 본문 hash·출처 정책·임베딩 권한을 확인한다. 오래된 입력은 `skipped`로 보고한다.
- 전체 집합에서 빠진 벡터도 제거한다. 권한을 다시 허용해도 제거된 벡터는 새로 임베딩하기 전까지 돌아오지 않는다.
- 검색은 벡터의 모델·차원·정규화 설정·본문 hash와 현재 출처 정책을 재확인한다.

## 검색과 실패 처리

전문 검색 점수와 벡터 유사도를 직접 더하지 않는다. 채널마다 독립적으로 순위를 정하고 RRF의 `1 / (60 + rank)`를 합한다. 같은 청크는 결과에 한 번 나타나며 동점은 chunk ID로 정렬한다. 벡터 ANN 자체의 후보 선택은 근사 검색이므로 같은 데이터에서도 동점 후보 선택까지 완전히 결정적이라고 보장하지 않는다.

질문은 Cypher 파라미터로 바인딩하며 Lucene 특수문자와 대문자 연산자도 무력화한다. Python 요청의 결과/후보 수는 1~500, CLI 결과 수는 1~100으로 제한한다. 정책에서 탈락한 ID는 경고에 노출하지 않는다.

벡터 인덱스나 호환 벡터가 없으면 전문 검색으로 제한하고 경고를 반환한다. CLI의 Jina 요청 실패도 전문 검색으로 돌아가며 경고를 남긴다. 연결 설정 자체가 빠진 `--hybrid` 요청은 구성 오류로 실패한다.

Neo4j에서는 같은 스키마를 다른 이름으로 다시 만들려는 `IF NOT EXISTS`가 원하는 이름의 인덱스를 만들지 않을 수 있다. Bootstrap은 생성 후 실제 인덱스를 검증해 이를 명시적으로 실패시킨다. 인덱스 이름·차원·분석기를 바꿀 때는 별도 마이그레이션이 필요하다.

## 한국어와 남은 한계

기본 `standard-no-stop-words`는 한국어 형태소를 분석하지 않는다. 한국어는 띄어쓰기를 사용하지만 조사·어미가 붙으므로 동일한 개념도 표현에 따라 전문 검색에서 누락될 수 있다. 로컬 2026.07.1에서 `standard-no-stop-words`와 `cjk` 분석기의 존재는 확인했다. 분석기별 한국어 정밀도·재현율 비교는 아직 하지 않았다. [Neo4j 전문 검색 문서](https://neo4j.com/docs/cypher-manual/25/indexes/semantic-indexes/full-text-indexes/)

- 벡터 후보를 뽑은 뒤 프로필·정책을 필터링하므로 결과가 요청 수보다 적어질 수 있다. 작은 fixture를 넘어설 때 후보 수와 재현율을 측정해야 한다.
- `db.index.vector.queryNodes`는 2026.04부터 deprecated지만 이번 검증 서버에서 동작한다. 운영 전 `SEARCH` 구문 전환을 검토한다. [Neo4j 벡터 검색 문서](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- 기존 `Neo4jGraphRepository`의 질문 경로는 여전히 License 노드 정책을 사용한다. 실제 여러 출처를 적재하기 전에 출처별 정책 검사로 통일해야 한다.
- 같은 모델 ID 뒤에서 서버 가중치가 교체되는 경우는 자동 감지하지 못한다. 실제 배포에서는 모델 revision 식별과 재임베딩 절차를 정해야 한다.
- 실 데이터, 한국어 의미 검색 품질, 실제 Jina 지연시간·비용은 이번 합성 벡터 테스트로 판단할 수 없다.

## 검증 결과

- 전체 96개 테스트: 실제 Neo4j를 포함해 96개 통과, skip 0개.
- DB 연결 플래그 없이 실행: 76개 통과, DB 테스트 20개 skip.
- 기존 gold 질문: 15/15 유지.
- 모의 Jina 서버와 실제 Neo4j를 연결한 HTTP → 임베딩 적재 → 하이브리드 검색 → 출처 검증 통과.
- CLI의 전문/하이브리드 검색 스모크 테스트 통과.
- 본문 변경, 임베딩 권한 철회, 오래된 벡터 재적재 거부, 인덱스 이름 충돌 검증 통과.

테스트 실행은 [개발 가이드](development.md#neo4j-통합-테스트)를 따른다. 합성 벡터는 테스트 서버에서만 생성하며 운영 fallback으로 사용하지 않는다. 실제 Jina 호출은 별도 [연결 기록](embedding-adapter.md)에서 확인할 수 있다. 원격 GitHub Actions 실행은 미확인이다.
