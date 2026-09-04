# 다음 구현 배치: 임베딩과 하이브리드 검색

2026-09-04. 기존 fixture/Neo4j 검색 작업 위에서 진행하며 기존 미커밋 변경을 보존한다.

## 완료 결과

이번 배치의 1~3번은 구현·통합 검증을 완료했다. Orca run은 `run_72551fcfb8d1`이며, Luna 작업 `task_300dbe9eabb9`와 Claude 작업 `task_08741ae33fce`가 모두 완료됐다. 두 worker 터미널은 완료 후 해제했다.

- Luna: Jina 어댑터와 정책 허용 청크 임베딩 구현.
- Claude: Neo4j 전문·벡터 검색, RRF, 출처별 정책 재검사 구현.
- Coordinator: 정규화 검증 보완, CLI 연결, 인덱스 충돌 처리, 권한 철회 시 벡터 제거 보완, 통합 검증.
- 검증: 실제 Neo4j 포함 96/96 통과, DB 없이 76개 통과·20개 skip, gold 15/15 유지, CLI 전문/하이브리드 검색 확인.
- 후속 검증에서 실제 Jina의 512차원 벡터 4개를 로컬 Neo4j에 저장하고 한국어 질문 2개의 결합 검색·출처 반환을 확인했다. 최신 전체 테스트는 DB 통합 20개를 포함해 102/102 통과, gold 15/15다. Hermes 연결과 원격 CI 실행은 미확인이다. 커밋/푸시는 수행하지 않았다.

## 다음 실행 목록

Jina API 문서를 반영하고 정정된 서버 Bearer 키로 실제 문서·검색어 임베딩 인증과 512차원 정규화 검증을 완료했다. 현재 결과는 [임베딩 연결 기록](embedding-adapter.md)에 있다.

1. 운영 모델 revision과 키 공급 방식을 확정. 실제 Jina → 로컬 Neo4j → 하이브리드 검색 연결 검증은 완료했다.
2. [진행 중] 한국어 검색 평가 질문을 늘리고 전문/벡터/결합 검색의 recall@k와 지연시간 비교. 현재 15개 gold는 기존 그래프 답변 회귀 기준이며 의미 검색 품질 평가가 아니다. fixture 5개 검색 gold와 `evaluate-search-neo4j`를 추가했으며, 실제 baseline 측정과 운영 corpus 확장은 후속이다.
3. Hermes의 구조화 출력 계약을 확인하고 검색된 evidence만 사용하는 답변 생성·인용 검증 연결.
4. Claude의 소스 조사 결과에서 승인된 source/release를 선택하고 source registry → 원본 저장 → 정제 → 학명 매핑 → Neo4j 적재 구현. 기존 질문 경로도 SourceDataset 단위 정책 검사로 통일.
5. 실제 모델·서버 규모가 정해지면 Neo4j SEARCH 구문 전환, 성능/비용 측정, 운영 모니터링을 진행.

## 작업 순서와 담당

1. GPT-5.6 Luna: Jina HTTP adapter, 임베딩 설정과 응답 검증, 정책 허용 청크의 배치 임베딩, 모의 서버 테스트.
2. Claude: Neo4j 청크 전문/벡터 인덱스, 정책을 재검사하는 검색, RRF 순위 결합, 단위/opt-in DB 테스트.
3. Coordinator: 공유 계약 조정, CLI 연결, 통합 검증, 실행 문서와 남은 결정 갱신.
4. 후속: 한국어 검색 품질 평가, Hermes 생성 경계와 근거 검증, 승인된 실제 source adapter.

## 이번 배치의 경계

- 합성 fixture만 사용한다. 실제 외부 데이터 수집과 Hermes 호출은 후속이다.
- 기존 질문 API는 그대로 실행 가능하게 유지하고 새 검색은 별도 CLI로 먼저 노출한다.
- Jina endpoint와 API key는 환경 변수로만 받는다. URL을 기본 운영 서버로 추정하지 않는다.
- 표준 Jina와 BirdsNest JSON HTTP 계약을 명시적으로 선택한다. BirdsNest의 실제 문서·검색어 요청을 확인했다.
- Neo4j 변경은 fixture 범위로 제한한다. 새 벡터 검색 전용 라벨/속성으로 다른 데이터와 분리한다.
- 임베딩 정책이 철회되거나 본문 hash/모델 설정이 달라지면 이전 벡터를 재사용하지 않는다.
- 커밋/푸시는 이번 구현 배치의 자동 단계에 포함하지 않는다.

## 두 worker의 공유 Python 계약

Luna는 `robingraph.embeddings`에서 다음을 export한다. Claude는 이 계약을 소비하고 별도 임베딩 HTTP client를 만들지 않는다.

```python
@dataclass(frozen=True)
class EmbeddingProfile:
    model: str
    dimensions: int
    normalized: bool

@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_id: str
    content_hash: str
    vector: tuple[float, ...]
    profile: EmbeddingProfile

class EmbeddingClient(Protocol):
    profile: EmbeddingProfile
    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...
    def embed_query(self, text: str) -> tuple[float, ...]: ...

def embed_fixture_chunks(corpus: FixtureCorpus, client: EmbeddingClient) -> tuple[EmbeddedChunk, ...]: ...
```

문서 task는 `retrieval.passage`, 질문 task는 `retrieval.query`로 고정한다. 모델/차원/정규화 정책과 본문 hash가 벡터의 호환 조건이다. `embed_fixture_chunks`는 chunk·부모 document·양쪽 source registry의 허용 상태와 embedding 권한을 재검사하고, 허용 청크가 없으면 HTTP 요청을 하지 않는다. 호출 실패는 명시적 오류이며 임의 벡터로 대체하지 않는다.

Claude는 `robingraph.retrieval.hybrid`의 검색 결과와 `robingraph.retrieval.neo4j_hybrid`의 인덱싱/검색 메서드를 정의하고 coordinator에게 정확한 공개 API를 보고한다. 인덱스 준비/벡터 적재는 명시적 쓰기 동작이고, 검색은 읽기 전용이다. 결과에는 chunk ID, 본문, 순위 점수, 매칭 채널, 실제 citation을 포함한다. RRF는 서로 다른 원점수를 직접 더하지 않고 순위로 결합한다. 벡터 사용 불가 시 전문 검색으로 제한된 사실을 결과 경고에 표시한다.

## 파일 소유권

| 담당 | 수정 범위 |
|---|---|
| Luna | `src/robingraph/embeddings/`, `tests/test_embeddings.py`, `docs/embedding-adapter.md` |
| Claude | `src/robingraph/retrieval/hybrid.py`, `src/robingraph/retrieval/neo4j_hybrid.py`, `src/robingraph/graph/fixture_projection.py`, `src/robingraph/graph/neo4j_client.py`, `tests/test_hybrid_retrieval.py`, `tests/test_neo4j_hybrid.py`, `docs/hybrid-retrieval.md` |
| Coordinator | CLI, 환경변수 예시, 의존성/lock 변경이 필요할 때, 통합 테스트, README/현황/본 문서 |

## 수용 기준

- 기존 fixture hash와 15개 gold 질문 회귀 없음.
- 잘못된 차원, NaN/Inf, 중복/누락 응답 index, HTTP 오류/timeout을 검출한다.
- 금지/미확정 embedding 콘텐츠를 HTTP로 전송하거나 벡터로 적재하지 않는다.
- RRF 중복 제거와 순위가 결정적이며 query 문자열은 Cypher에 바인딩한다.
- 본문 변경/embedding 권한 철회 후 오래된 벡터가 검색되지 않는다.
- 모의 Jina 검증과 실제 Jina 연결 검증을 구분해 보고한다.
- Neo4j 인덱스/검색은 disposable DB에서 검증하며 연결 플래그가 없으면 DB 테스트만 skip한다.
