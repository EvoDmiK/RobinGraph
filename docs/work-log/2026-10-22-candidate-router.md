# [RG-206] 질문 임베딩 기반 질의 유형 후보 검색 구현 및 검증 — 2026-10-22

> **문서 상태: 검증 범위 완료 (유형 후보 검색 한정; 전체 런타임 미완료, 운영은 향후 별도 승인)**  
> 상위 에픽 **RG-204 (의미 기반 그래프 질의 해석 및 안전한 실행 전환)**의 2단계 과제인 **RG-206 (질문 임베딩 기반 질의 유형 후보 검색)**의 구현과 독립 검증을 완료했다. 자체 호스팅 Jina v3 모델을 활용하여 7대 그래프 질의 유형의 45개 대표 프로토타입 벡터 인덱스와 신뢰도(`confidence: 0.80`) 및 마진(`margin: 0.06`) 기반 라우터를 구축하였으며, Leave-One-Out 교차 검증에서 53/67(79.1%) top-1 정확도와 답변 가능 질문에 대한 오분류 0건을 달성했다.  
> **검증 범위 및 런타임 한계 명시**: 본 완료는 **질의 유형 후보 탐색(`KindCandidates`)에 한정된 완료**이며, 종 ID 식별, 조건 추출 및 전체 의미론적 품질(semantic quality)은 RG-207 및 RG-208에서 순차 검증된다. 전체 기능은 아직 완료되지 않았으며, TEST 서버는 당시 단계 시점 기준 기존 RG-203 배포본(`robingraph-api:test-question-endings-203d19900989`)을 유지한 상태였고 (현재는 후속 [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-통합-관측-TEST-비교-단계적-전환|RG-208]]을 통해 active 배포로 전환 완료), 새 배포/DB 쓰기/운영 변경/Git commit·push는 일체 수행하지 않았다. 이제 **RG-207 (원문 조건 추출·스팬 커버리지·안전 검증)** 단계로 진입한다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 목적** | 7대 질의 유형 후보 임베딩 라우터 구축 | 사용자 자연어 질문에서 7개 고정 그래프 질의 유형 후보(top-3)를 탐색하고, 신뢰도 미달 시 안전하게 `clarify`를 유도하는 auxiliary 라우터 구현 |
| **설계 및 아키텍처** | 프로토타입 캐싱 & 신뢰도/마진 판정 | 1) 45개 튜닝 질문 기반 프로토타입 인덱스, 2) 캐시 키 `(VERSION, model, dims, normalized)` 검증, 3) `embed_queries` 배치 함수 추가로 기존 단건 루프 대비 콜드 로드 9.6s -> 2.1s 단축 |
| **코드 / 모듈 변경** | 라우터 신규 작성 및 공통 임베딩 확장 | `graph_semantic_router.py`(신규), `test_graph_semantic_router.py`(신규 12건), `embeddings/__init__.py`(`embed_queries` 추가, 기존 동작 보존), `test_embeddings.py`(2건 추가) |
| **테스트 검증** | Python 1,105실행 1,066통과 39skip | 전체 1,105건 실행 (1,066 통과 / 39 skip [opt-in 통합 및 RG-406 번들 부재] / 0 fail, 22.032초). 라우터 독립 12건 통과. Staging 7건 실패(git 미포함)는 실제 워크트리에서 완전 해소 |
| **실측 지표 (Jina TEST)** | 웜업 p95 222.8ms, 콜드 2,125.3ms | 1) Warm (84건): p50 = 210.5ms, p95 = 222.8ms, max = 250.4ms (질의당 1 HTTP). 2) Cold: 총 2,125.3ms (32건 배치 1.2s + 13건 배치 0.6s + 질의 0.2s = 총 3 HTTP 요청; 개별 요청 타임아웃 2초 준수) |
| **임계치 검증 (LOO)** | threshold 0.80 / margin 0.06 | Leave-One-Out 53/67 top-1 (query task). 30건 confident 판정 중 28건 일치, 답변 가능 질문 오분류 0건. *종/조건/답변 정확도가 아님* |
| **인프라 및 배포** | 기능 플래그 `off`, TEST 기존 유지 | TEST 환경은 해당 단계 시점 기준 기존 203 이미지 유지 (후속 [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-통합-관측-TEST-비교-단계적-전환|RG-208]]을 통해 active 배포 전환 완료), 새 배포 0건, DB 쓰기 0건, Prod 변경 0건, Git commit/push 0건 |

---

## 1. 작업 배경 및 문제 분석

### 1) 추진 배경
- RG-204의 7대 고정 그래프 질의를 안전하게 라우팅하기 위해, 정규식의 어휘적 한계를 보완할 수 있는 auxiliary 질의 유형 후보 검색 체계(RG-206)가 요구됨.
- 후보 검색은 절대 종 ID나 조건 파라미터를 임의 확정하거나 Cypher를 직접 생성해서는 안 되며, 오직 사전 정의된 질의 유형 후보(`candidates: tuple[str, ...]`)와 신뢰도 마진만을 산출하여 RG-207 조건 추출기로 전달해야 함.

### 2) 핵심 기술 요구 및 해결
- **임베딩 태스크 일치**: 프로토타입 임베딩 생성 시 문서(passage) 태스크 대신 질문(query) 태스크를 적용하여 Leave-One-Out top-1 일치도를 41/67에서 **53/67 (79.1%)**로 대폭 향상.
- **배치 쿼리 지원**: 기존 45회 순차 HTTP 루프(9,614ms)를 방지하기 위해 공통 모듈에 `embed_queries`를 추가하여 2회 배치(32건 + 13건)로 단축, 총 콜드 로드 시간을 **2,125.3ms**로 최적화. 기존 `embed_documents` 및 `embed_query` 동작은 관련 테스트 통과로 보존 확인.
- **예외 없는 방어**: `classify(question) -> KindCandidates` 인터페이스는 어떤 비정상 입력(빈 문자열, 특수문자, 임베딩 실패, 프로필 오류)에서도 절대 예외를 던지지 않고 안전하게 `status="unavailable"` 또는 `status="below_threshold"`를 반환하도록 설계.

---

## 2. 주요 구현 내용

### 1) 신규 및 수정 파일 목록
* `src/robingraph/retrieval/graph_semantic_router.py` (신규) — 7대 질의 유형 후보 라우터 구현 (sha256: `85a36933dccf68d73c991b61f5fe702bf1654749d88d197683b3ae296b1aa4dc`)
* `tests/test_graph_semantic_router.py` (신규) — 라우터 단위 테스트 12건 (sha256: `c07b909116a0353a733f78fb9c972d10348d7c64e71c0c50a2d58671ff3d8fe1`)
* `src/robingraph/embeddings/__init__.py` (수정) — `embed_queries` 배치 함수 추가 (sha256: `d7e8807d915dd7e809dbc3262bc7b2ea8816e368654f204acba6aff00df1715c`)
* `tests/test_embeddings.py` (수정) — 배치 쿼리 및 태스크 분기 단위 테스트 2건 추가 (sha256: `3c314f31738184febcafc99fa229f0629c9f7b711d8e7f73f51171c7a2de1bb4`)

### 2) 라우터 계약 (`KindCandidates`)
```python
@dataclass(frozen=True)
class KindCandidates:
    candidates: tuple[str, ...]  # top-3 유형 후보
    margin: float                # 1위와 2위 간 유사도 마진
    status: str                  # "ok" | "below_threshold" | "unavailable"
    prototype_version: str       # 인덱스 버전
    model: str                   # 모델명
    elapsed_ms: float            # 소요 시간
    embedding_calls: int         # 질의 임베딩 시도 횟수
    prototype_calls: int         # 캐시 로드 시도 횟수
    prototype_requests: int      # 클라이언트 메서드 호출 수
    prototype_batches: int | None # HTTP 배치 수
```

---

## 3. 검증 및 테스트 결과

### 1) 자동화 테스트 전수 검증 ([`candidate-full-python.log`](../verification/assets/2026-10-22-semantic-graph-routing/candidate-full-python.log))
- **실행 결과**: 전체 1,105건 실행 (통과: 1,066건, 건너뜀: 39건, 실패: 0건, 실행 시간: 22.032초)
- **독립 단위 테스트**:
  - `test_graph_semantic_router.py`: 12건 전수 통과
  - `test_embeddings.py`: 14건 전수 통과 (기존 12건 + 신규 2건)
  - `test_graph_intent_schema.py`: 12건 전수 통과
- **환경 차이 기록 (Staging 7건 실패 해소)**:
  - Git 메타데이터가 없는 임시 스테이징 디렉터리에서는 `git rev-parse HEAD`를 호출하는 `test_nas_release_package` 7건이 실패했으나, 실제 Git 워크트리에서는 전수 정상 통과하여 완전 해소됨.

### 2) 자체 호스팅 Jina 임베딩 실측 ([`candidate-router-probe.json`](../verification/assets/2026-10-22-semantic-graph-routing/candidate-router-probe.json))
- 모델: `jinaai/jina-embeddings-v3` (512차원, 정규화, 배치 크기 32, 타임아웃 2초, 재시도 0)
- **웜업 상태 (Warm Classify, 84개 튜닝 질문 전수 실측)**:
  - **p50 = 210.5ms**, **p95 = 222.8ms**, **최대 = 250.4ms**
  - 질의당 정확히 **1회 HTTP 요청** 발생 (`prototype_calls: 0`, 캐시 적중).
- **콜드 상태 (Cold Classify, 프로세스 기동 직후 최초 1회)**:
  - **총 소요 시간: 2,125.3ms** (프로토타입 2배치 [32건 1,258ms + 13건 595ms] + 질의 1건 211ms = 총 3회 HTTP 요청).
  - *타임아웃 구분 주의*: `gates.json`의 2초 타임아웃(`graph_embedding_timeout_seconds: 2`)은 **개별 HTTP 요청 단위의 타임아웃**이며, 3개 요청이 순차 합산된 총 콜드 기동 시간(2.1초)의 상한이 아님. 모든 개별 HTTP 요청은 1.3초 이내로 2초 타임아웃을 안정적으로 준수함.
- **단일 쿼리 vs 배치 쿼리 벡터 일치도**:
  - 최소 코사인 유사도: **0.999999** (완전 일치 확인).
- **장애 복구 검증**:
  - 최초 프로토타입 로드 타임아웃 모의 시 `status="unavailable"`로 즉시 안전 실패하며, 다음 요청에서 정상 재로드(2,184ms)되어 복구됨.

### 3) 임계치 검증 (Leave-One-Out on Tuning Set)
- 튜닝 질문 67건 대상 Leave-One-Out(질문 자신을 프로토타입에서 제외) 결과:
  - 질의(query) 태스크 LOO top-1: **53/67 (79.1%)** (문서 태스크 41/67 대비 대폭 개선).
  - 최종 채택 임계치: `confidence = 0.80`, `margin = 0.06`.
  - 임계치 적용 결과: 30건 confident 판정 중 **28건 일치**, **답변 가능 질의(answerable) 오분류 0건** (오분류 2건은 자료부족 `specific_fruit`와 모호한 대조 질의로 안전하게 `clarify` 처리됨).

---

## 4. 검증 범위의 한계 및 전체 런타임 상태

1. **지표 성격의 엄격한 한계**:
   - LOO 53/67(79.1%)는 **오직 질의 유형 후보(`kind`) 분류 정확도**일 뿐이며, 종 식별, 조건 파라미터 추출, 최종 자연어 답변 정확도가 아님.
   - 대조 쌍(같은 서식지+같은 먹이 vs 같은 서식지+다른 먹이, 일반 열매 vs 특정 열매, 일반 같은 속 vs 국내 같은 속) 간의 최종 변별은 라우터가 아닌 **RG-207 추출기의 결정론적 규칙과 스팬 커버리지 검증**에 의존함.
2. **전체 기능 미완료 및 TEST 서버 상태**:
   - RG-206은 완료되었으나, 상위 에픽 RG-204 전체 및 런타임 엔드투엔드 파이프라인은 아직 미완료 상태임.
   - TEST 서버는 당시 검증 시점 기준 기존 RG-203 배포본(`robingraph-api:test-question-endings-203d19900989`)을 유지하고 있었으며, 신규 배포 0건, DB 쓰기 0건, 운영 변경 0건, Git commit/push 0건이었음. (현재는 후속 RG-208을 통해 전환 완료)
3. **RG-205 사람 미검토 유지**:
   - 40건 홀드아웃셋은 `agent_reviewed` 상태이며, 사람 검토(human gold review)는 향후 실제 사용자 평가 과제로 계속 분리 관리됨.

---

## 5. 작업 현황 및 순차 진행 로드맵

1. **RG-203**: `완료 (2026-10-22, 구현·TEST 검증 완료; 운영 미배포 · 향후 명시 승인 필수)` (보존).
2. **RG-204 (상위 에픽)**: `진행 중 (Phase 1·2 검증 완료, 전체 런타임 미완료)` (하위 4개 완료 시까지 에픽 완료 불가).
3. **RG-205 (Phase 1)**: `진행 중 (계약·기준선·에이전트 평가셋 구축 검증 완료; 사람 미검토 분리)`.
4. **RG-206 (Phase 2)**: **`완료 (2026-10-22, 검증 범위 한정: 유형 후보 검색 완료; 전체 semantic quality 미검증)`**.
5. **RG-207 (Phase 3)**: **`진행 중 (원문 조건 추출·스팬 커버리지·안전 검증 착수)`** — 이제 순차 착수.
6. **RG-208 (Phase 4)**: `착수 대기 (통합·관측·TEST 비교)` — RG-207 완료 후 착수.

---

## 관련 문서 및 검증 증거 링크

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- 선행 설계 검증 문서:
  - [`2026-10-22-semantic-graph-routing.md`](2026-10-22-semantic-graph-routing.md) (RG-204/205 선행 설계 및 평가 게이트 검증 역사 기록 보존)
- 검증 자산 (상대 경로 링크):
  - [`candidate-router-handoff.md`](../verification/assets/2026-10-22-semantic-graph-routing/candidate-router-handoff.md) (Claude RG-206 구현 핸드오프 보고서)
  - [`candidate-router-probe.json`](../verification/assets/2026-10-22-semantic-graph-routing/candidate-router-probe.json) (Jina 실측 프로브 및 LOO 스윕 데이터)
  - [`candidate-full-python.log`](../verification/assets/2026-10-22-semantic-graph-routing/candidate-full-python.log) (1,105건 전체 Python 단위 테스트 로그)
  - [`gates.json`](../../data/eval/graph_questions/gates.json) (RG-204 평가 및 안전 게이트 v1)
- 관련 상세 백로그:
  - [[Work/RobinGraph/백로그 상세/RG-204|RG-204 — 의미 기반 그래프 질의 해석 및 안전한 실행 전환 (상위/에픽)]]
  - [[Work/RobinGraph/백로그 상세/RG-205|RG-205 — 구조화 질의 계약·정답 평가셋·현재 기준선]]
  - [[Work/RobinGraph/백로그 상세/RG-206|RG-206 — 질문 임베딩 기반 질의 유형 후보 검색 (검증 범위 완료)]]
  - [[Work/RobinGraph/백로그 상세/RG-207|RG-207 — 원문 조건 추출·엔티티 연결·안전 검증 (진행 중 착수)]]
  - [[Work/RobinGraph/백로그 상세/RG-208|RG-208 — 통합·관측·TEST 비교·단계적 전환 (착수 대기)]]
