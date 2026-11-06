# [RG-204/205] 의미 기반 그래프 질의 해석 선행 설계 및 평가 게이트 검증 — 2026-10-22

> **문서 상태: 선행 설계 검증 완료 (구현 진행 중, 런타임 미검증, 운영은 향후 별도 승인)**  
> 사용자 지시("일단 204 먼저 검증하고, 다른 것도 진행해")에 따라 상위 에픽 **RG-204 (의미 기반 그래프 질의 해석 및 안전한 실행 전환)**의 선행 설계 및 아키텍처 안전성 검증을 최우선으로 완료했다. Claude의 동료 검토(`design-peer-review.md`) 및 Codex의 독립 테스트를 통해 관측·호환·안전경계 측면의 3대 핵심 위험을 식별 및 수정 조율하였으며, **RG-205 (구조화 질의 계약·정답 평가셋·기준선 실측)**의 정형 스키마 계약 및 40건 고정 홀드아웃셋(`agent_reviewed`, sha256 고정, invalid/leak 0) 기준선 측정을 마쳤다.  
> **현재 런타임 완료 아님**: 본 문서는 선행 설계 및 계약 검증 완료 보고서이며, 전체 기능 완성 기록이 아니다. 당시 기본값은 `off`로 유지되었으며, TEST 컨테이너는 해당 단계 시점 기준 기존 RG-203 배포본(`robingraph-api:test-question-endings-203d19900989`)을 유지한 상태였고 (현재는 후속 [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-통합-관측-TEST-비교-단계적-전환|RG-208]]을 통해 active 배포로 전환 완료), 새 배포/DB 쓰기/운영 변경/Git commit·push는 일체 수행하지 않았다. 이제 **RG-206 (질문 임베딩 기반 질의 유형 후보 검색)** 작업만 재개하며, 이후 RG-207로 순차 진행한다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 배경** | RG-204 선행 설계 안전성 우선 검증 | 사용자 범위 정정에 따라 RG-204 아키텍처 및 정형 계약을 우선 검증하고, 하위 과제 순차 진행 기반 마련 |
| **설계 위험 해결 (3건)** | 호환성·성능/비용·안전경계 위험 수정 | 1) 비그래프 질문의 기존 자동 라우트 보장, 2) 어휘적 큐 사전 검사로 불필요한 임베딩 호출(<=1회) 방지, 3) 활성 모드에서 추출기 소스 엄격 검증 |
| **정형 스키마 및 게이트** | `graph_intent_schema.py` & `gates.json` | 7대 질의 유형 및 조건 파라미터 DTO 정의, 오실행률 0 / 커버리지 70% 이상 목표 평가 게이트(`rg204-gates-v1`) 고정 |
| **자동화 테스트 검증** | 단위 및 API 가드 통과 | 전체 Python 1,088건 실행(1,049 통과 / 39 skip [opt-in 통합 및 RG-406 번들 부재] / 0 fail, 23.142s), 그래프 단위 57건 통과(0.152s), 최종 API 가드 14건 통과(0.107s) |
| **Jina 임베딩 실측** | 자체 호스팅 Jina v3 (512차원) | 5회 순차 측정(클라이언트 타임아웃 8초 설정, 0 재시도): p50 = 214.58ms, p95(최대) = 517.06ms (표본 5회 참고치; 향후 런타임 2초 예산과 구분) |
| **평가셋 및 기준선** | 84건 튜닝 / 40건 홀드아웃 (`agent_reviewed`) | leak 0건. 홀드아웃 게이트 커버리지 55%, 오실행 0건이나 튜닝셋 게이트 오실행 3건/조건누락 2건 잔존. 스키마 게이트 단독 보장 불가 및 207 스팬 커버리지 필수 명시. *사람 미검토* |
| **인프라 및 배포** | 기능 플래그 `off`, TEST 기존 유지 | TEST 환경은 해당 단계 시점 기준 기존 203 이미지 유지 (후속 [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-통합-관측-TEST-비교-단계적-전환|RG-208]]을 통해 active 배포 전환 완료), 새 배포 0건, DB 쓰기 0건, Prod 변경 0건, Git commit/push 0건 |

---

## 1. 작업 배경 및 설계 검토

### 1) 추진 배경
- RG-203에서 7대 그래프 질의 및 공통 어미(`_ASK`) 대응을 완료했으나, 정규식 기반 파서는 어순 도치, 띄어쓰기 변형, 비정형 구어체 질문에서 누락이 발생할 수 있는 한계가 존재함.
- 이를 해결하기 위한 상위 과제 RG-204 착수 과정에서 사용자 정정 지시("일단 204 먼저 검증하고, 다른 것도 진행해")가 하달됨에 따라, 전체 런타임을 임의 구현하는 대신 **선행 아키텍처 설계의 완결성, 안전성 경계, 정형 계약 검증을 최우선으로 수행**함.

### 2) Claude 동료 검토 기반 3대 핵심 위험 식별 및 해결

Claude의 설계 동료 검토([`design-peer-review.md`](../verification/assets/2026-10-22-semantic-graph-routing/design-peer-review.md))를 거쳐 아래 3가지 위험을 식별하고 Root 코드 및 계약에 즉시 반영함:

1. **위험 1 (호환성 - 기존 자동 라우트 침범 방지)**:
   - *문제*: 단일 종 매칭이 없는 모든 질문이 시맨틱 경로를 거칠 때, 비그래프 질문(예: "참새목 관찰 기록 보여줘")에 잔여 텍스트(`residual`)가 남으면 `clarify`로 차단되어 기존 관찰/문헌/분류 라우트에 도달하지 못할 위험.
   - *해결*: 그래프 큐(목·먹이·서식지·속/관계·특정 식물 등)가 전혀 없는 질문은 잔여/부정/모호성을 기록하지 않고 클린한 `not_graph`(`GraphIntent(None)`)를 반환하여 기존 라우트로 온전히 전달되도록 계약 확정.
2. **위험 2 (성능 및 비용 - 비그래프 질문의 임베딩 호출 방지)**:
   - *문제*: 모든 자동 질문에 대해 동기식으로 임베딩 라우터를 호출하면, 비그래프 질문에서도 최대 2초의 지연과 불필요한 임베딩 비용이 발생함.
   - *해결*: 어휘 규칙 기반의 `extract_graph_intent(question)`를 먼저 실행하여 그래프 큐가 감지된 경우에만 임베딩 분류(`classify`)를 호출(질의당 임베딩 <= 1회 엄수). 그래프 큐가 없으면 임베딩 호출 0회로 즉시 반환.
3. **위험 3 (안전 경계 - 활성 모드의 소스 검증 및 기존 정규식 탈락 보호)**:
   - *문제*: 활성(active) 모드에서 추출기가 `not_graph`를 반환할 때, 기존 정규식으로 정상 답변되던 질문이 다른 라우트로 조용히 유실될 위험.
   - *해결*: 활성 모드는 `interpreted.source == "extractor"`인 경우만 엄격히 수용하며, 기존 정규식 매칭이 존재했으나 추출기가 `not_graph`를 낸 경우 침묵 실행 대신 `clarify` 처리. 또한 게이트를 통과하기 전까지 활성 모드 진입을 원천 차단.

---

## 2. 정형 계약 및 평가 게이트 수립 (RG-205)

### 1) 구조화 질의 계약 (`graph_intent_schema.py`)
- 허용 질의 유형(7개 고정): `common_taxonomy`, `same_genus`, `korea_same_genus`, `order_fruit`, `specific_fruit`, `habitat_shared_diet`, `habitat_different_diet`.
- 추출 대상 슬롯: `species`, `rank`, `group`, `diet`, `habitat`, `relation`, `scope`, `specific_plant`, `negation`, `residual`, `unsupported`, `ambiguity`.
- 임의 Cypher 생성 금지 및 정형 DTO(`GraphIntent`) 기반의 고정 Cypher 템플릿 실행 계약 확립.

### 2) 독립 평가 게이트 정의 (`data/eval/graph_questions/gates.json`)
- 버전: `rg204-gates-v1` (sha256: `099cf3559268151df280a43730c44c09e009fb183a0221e1498867ddc946f3d1`)
- **안전성(Safety) 게이트**:
  - `false_executions_max`: 0 (오실행 절대 허용 안 함)
  - `condition_loss_executed_max`: 0 (조건 누락 후 실행 금지)
  - `free_cypher_max`: 0 (자유 Cypher 생성 금지)
  - `query_alias_or_species_writes_max`: 0 (DB 쓰기 일체 금지)
- **품질(Quality) 게이트**:
  - 질의 유형 정확도(`typed_kind_accuracy_min`): 0.75 (75%)
  - 전체 슬롯 정확도(`typed_all_slots_exact_min`): 0.70 (70%)
  - 답변 커버리지(`answer_coverage_min`): 0.70 (70% 이상, 베이스라인 55% 대비 15%p 향상)
  - 사용자 실패 회귀(`user_failure_regressions_max`): 0
- **자원 및 지연(Resources) 게이트**:
  - 질의당 임베딩 호출 최대 1회, 타임아웃 2초, 재시도 0회.
  - 웜업 라우터 p95 지연 상한: 1,500ms.
  - 외부 유료 모델 호출 0건, 신규 인프라 요구 0건.

---

## 3. 검증 및 테스트 결과

### 1) 자동화 테스트 검증
- **전체 Python 테스트 suite** ([`design-full-python.log`](../verification/assets/2026-10-22-semantic-graph-routing/design-full-python.log)):
  - 실행: 1,088건 (통과: 1,049건, 건너뜀: 39건, 실패: 0건, 실행 시간: 23.142초)
  - *건너뜀(39건) 사유*: 전부 opt-in 실 DB 테스트가 아니며, opt-in 통합/실제 DB 테스트 및 RG-406 재현 번들(`/tmp/rg406-avilist.json`) 부재에 따른 skip이 포함됨.
  - *주의*: 추가 API 가드 3건 작성 직전 기준 수치임 (중복 합산 금지).
- **그래프 관련 테스트 suite** ([`design-tests.log`](../verification/assets/2026-10-22-semantic-graph-routing/design-tests.log)):
  - 실행: 57건 통과 (실행 시간: 0.152초, 0 skip / 0 fail, 추가 3건 이전)
- **최종 API 델타 테스트 suite**:
  - 실행: 14건 통과 (기존 11건 + 3대 위험 가드 3건, 실행 시간: 0.107초)
  - 주입된 모의 해석/검색 검증이며 실제 라이브 라우터 구동 아님.

### 2) 자체 호스팅 Jina 임베딩 실측 ([`embedding-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/embedding-baseline.json))
- 모델: `jinaai/jina-embeddings-v3` (512차원, 자체 호스팅 TEST 환경)
- 실측 조건: 클라이언트 타임아웃 8초(`timeout_seconds: 8`), 재시도 0회(`retries: 0`) 설정으로 5회 순차 호출.
- 개별 응답 시간: `[517.06ms, 233.43ms, 213.48ms, 206.78ms, 214.58ms]`
- 지표 산출: **p50 = 214.58ms**, **p95(최대치) = 517.06ms**
- *타임아웃 구분 주의*: 실제 5회 측정은 8초 클라이언트 타임아웃 환경에서 수행되어 응답이 2초 미만으로 측정된 것이며, 2초 타임아웃 설정으로 실측한 것이 아님. '2초 타임아웃'(`graph_embedding_timeout_seconds: 2`)은 향후 RG-206 런타임 구현 시 적용할 상한 예산(`gates.json`)임. (부하/동시성 성능 검증 아님).

### 3) 84건 튜닝 / 40건 홀드아웃 평가셋 및 정규식 기준선 실측
- **평가셋 상태**:
  - 튜닝셋: 84건 (`tuning.jsonl`)
  - 홀드아웃셋: 40건 (`holdout.jsonl`, sha256: `11853040600799247e69510dfa74fe60698a75a1ea0a7bfd3b2245563b3b50e4`)
  - 검증 결과: `invalid: 0`, `leaked_ids / normalized_overlap: 0` (누출 없음 확인)
  - 검토 상태: `agent_reviewed` (Codex 수기 작성 + Writer 독립 시맨틱 검토 + Root 판정 반영)
  - **사람 미검토 명시**: 본 평가셋은 사람 검토(human gold review)가 완료된 것이 아니며, 에이전트 간 독립 작성/리뷰 결과임.
- **기준선 실측 비교 및 스키마 게이트의 핵심 한계**:
  - **40건 홀드아웃 표본 ([`holdout-regex-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/holdout-regex-baseline.json))**:
    - Raw 정규식: 잠재 오실행(`false_execution`) 1건(2.5%), 조건 누락 실행 1건 (파서 수준).
    - Gated 정규식: 오실행 0건(0.0%), 적정 보류율 20/20건(100.0%), 답변 커버리지 11/20건(55.0%), 유형 정확도 13/31건(41.94%).
  - **84건 튜닝셋 표본 ([`tuning-regex-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/tuning-regex-baseline.json))**:
    - Gated 정규식: 오실행 3건(3/84, 3.57%), 조건 누락 실행 2건 잔존.
  - **안전성 보장 한계 명시 (Claude 동료 검토 `design-peer-review.md` 핵심 결론)**:
    - 홀드아웃 표본 40건에서 오실행이 0건으로 나왔다고 해서 게이트 단독으로 모든 잠재 오실행이 차단된다고 단정할 수 없음 (튜닝셋에서 3건 잔존).
    - 스키마 게이트(`execution_gate`)는 추출기가 `negation`/`residual`/`unsupported`/`ambiguity`에 명시적으로 기록한 조건만 차단할 수 있음.
    - 만약 추출기가 원문의 수식 조건(예: "해외에만 있는 청둥오리"에서 '해외에만 있는')을 누락하고 잔여 텍스트로도 남기지 않으면 게이트 단독으로는 오실행을 감지할 수 없음.
    - 따라서 진정한 안전성 확보를 위해서는 스키마 게이트뿐만 아니라, **RG-207 원문 조건 추출기에서 원문의 모든 문자 스팬이 완전히 소비되거나 잔여로 분류되는지 검증하는 스팬 커버리지(span-coverage) 검사가 필수적**임.

---

## 4. 배포 및 형상 관리 상태

- **TEST 환경 컨테이너**: 해당 단계 시점 기준 `robingraph-api:test-question-endings-203d19900989` (기존 RG-203 배포 상태 유지, 변경 없음; 현재는 후속 RG-208을 통해 active 전환 완료).
- **기능 플래그 기본값**: `ROBINGRAPH_GRAPH_INTENT_MODE=off`.
- **배포 및 인프라 지표**:
  - 신규 배포(`new_deployments`): 0건
  - 데이터베이스 쓰기(`db_writes`): 0건
  - Production 변경: 없음 (`production_changed: false`)
  - Git commit / push: 없음 (`git_commit_push: false`)

---

## 5. 작업 현황 및 순차 진행 로드맵

1. **RG-203**: `완료 (2026-10-22, 구현·TEST 검증 완료; 운영 미배포 · 향후 명시 승인 필수)` (상태 유지).
2. **RG-204 (상위 에픽)**: `진행 중 (선행 설계 검증 완료 · 런타임 미검증)`
   - 선행 아키텍처, 3대 위험 조율, 정형 계약 검증 완료. 자식 과제들이 모두 완료될 때까지 상위 에픽 완료 불가.
3. **RG-205 (Phase 1)**: `진행 중 (계약·기준선·에이전트 평가셋 구축 검증 완료; 사람 미검토 분리)`
   - 스키마 계약, 평가 게이트, 40건 홀드아웃셋 구축 및 기준선 실측 검증 완료. 사람 미검토 항목은 후속 과제로 분리 관리.
4. **RG-206 (Phase 2)**: **`진행 중 (재개, 질문 임베딩 기반 질의 유형 후보 검색 구현·검증 착수)`**
   - 이제 사용자 지침에 따라 RG-206 후보 검색 프로토타입 구현 및 검증만 단독 재개.
5. **RG-207 (Phase 3)**: `착수 대기 (RG-206 검증 완료 후 순차 착수)`
   - 원문 조건 추출, 스팬 커버리지, 안전 검증은 RG-206 통과 후 순차 진행.
6. **RG-208 (Phase 4)**: `착수 대기 (미착수, 기존 연결 초안은 off로 보존)`
   - 런타임 통합, 관측성, TEST 비교 검증은 최후 단계에 진행.

---

## 관련 문서 및 검증 증거 링크

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- 검증 자산 (상대 경로 링크):
  - [`design-verification.json`](../verification/assets/2026-10-22-semantic-graph-routing/design-verification.json) (선행 설계 검증 매니페스트)
  - [`design-peer-review.md`](../verification/assets/2026-10-22-semantic-graph-routing/design-peer-review.md) (Claude 설계 동료 검토 보고서)
  - [`gates.json`](../../data/eval/graph_questions/gates.json) (RG-204 평가 및 안전 게이트 v1)
  - [`embedding-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/embedding-baseline.json) (TEST Jina v3 5회 실측)
  - [`holdout-regex-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/holdout-regex-baseline.json) (40건 홀드아웃 기준선 실측)
  - [`tuning-regex-baseline.json`](../verification/assets/2026-10-22-semantic-graph-routing/tuning-regex-baseline.json) (84건 튜닝셋 기준선 실측)
  - [`design-full-python.log`](../verification/assets/2026-10-22-semantic-graph-routing/design-full-python.log) (1,088건 단위 테스트 로그)
  - [`design-tests.log`](../verification/assets/2026-10-22-semantic-graph-routing/design-tests.log) (57건 그래프 테스트 로그)
- 선행 완료 과제:
  - [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
  - [`2026-10-22-question-endings.md`](2026-10-22-question-endings.md) (RG-203 완료 작업문서)
- 관련 상세 백로그:
  - [[Work/RobinGraph/백로그 상세/RG-204|RG-204 — 의미 기반 그래프 질의 해석 및 안전한 실행 전환 (상위/에픽)]]
  - [[Work/RobinGraph/백로그 상세/RG-205|RG-205 — 구조화 질의 계약·정답 평가셋·현재 기준선]]
  - [[Work/RobinGraph/백로그 상세/RG-206|RG-206 — 질문 임베딩 기반 질의 유형 후보 검색]]
  - [[Work/RobinGraph/백로그 상세/RG-207|RG-207 — 원문 조건 추출·엔티티 연결·안전 검증]]
  - [[Work/RobinGraph/백로그 상세/RG-208|RG-208 — 통합·관측·TEST 비교·단계적 전환]]
