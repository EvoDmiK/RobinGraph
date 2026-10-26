---
created: 2026-10-22
date: 2026-10-22
project: RobinGraph
type: worklog
status: completed
task_id: RG-208
tags:
  - worklog
  - robingraph
  - mlflow
  - evaluation
---

# [RG-208 / 평가] MLflow GenAI Evaluate 기반 그래프 질의 496건 TEST 재평가 — 2026-10-22

> **문서 상태: 평가 및 검증 완료 (실제 API 496건 계약오류 0건, 이전 관측치 대비 상태/커버리지 차이 0건, fresh DB Oracle 480건 1,879종 3,126조건 불일치 0건, 18건 비답변 strict safety 18/18 통과 및 변조 13/13 탐지 완료; MLflow native 평가엔진 점수 저장 및 496행 결과표 등록 완료, Run `0295848aaa854d8cb8acc289373daf67` FINISHED 확인 완료; 원본 기대값 불변, 사람 검토 false, 운영 미배포, Git commit/push 없음, 조류 DB 쓰기 0건)**  
> 2026-10-22 등록된 496건 고유 질의 Native MLflow 평가 데이터셋(`robingraph-taxonomic-regression-v1-746baf0adb1b`, ID `d-9b84fb796702487a90cbf57e754995a8`)에 대해 `mlflow.genai.evaluate` SDK 인터페이스를 활용한 공식 재평가(Re-evaluation)를 성공적으로 완결했다.  
> 본 평가는 단순한 상위 API 상태 코드 확인에 그치지 않고, 결정적(deterministic) 계약 스코어러(Contract Scorer)를 통한 기대 조건 전수 검증(496건), TEST 컨테이너(`robingraph-api-test`) 환경에서 외부 TEST Neo4j(32GB Mac .98) 및 PostgreSQL(NAS .99)을 직접 조회하는 fresh DB Oracle 전수 대조(480건), 그리고 18개 비답변(non-answering) 케이스에 대한 사유별 엄격 감사(`scripts/audit_graph_question_safety.py`)를 결합하여 수행되었다.  
> 첫 번째 시도에서 MLflow SDK의 최상위 `expectations` Null 값 제약(`MlflowException: The 'value' field must be specified`)으로 인해 24개 응답 수집 시점에서 하네스 중단이 발생했으나(실패 런 보존: `20261022T113250Z`, Run ID `765da50a79ba42cd860bd13b5730499f`), 원본 데이터셋의 기대값을 불변 보존한 채 평가 DataFrame에서 `expectations={"contract": 원본expectations}`로 중첩 래핑하여 하네스를 정상화하고 신규 Run(`0295848aaa854d8cb8acc289373daf67`)으로 496건 전체 재실행 및 서버 집계표 등록을 완료했다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 목적** | MLflow GenAI Evaluate 공식 재평가 완결 | 등록된 496건 질의에 대해 `mlflow.genai.evaluate` 기반 정식 평가 수행. API 계약 통과, DB Oracle 전수 대조 및 비답변 엄격 감사 연계 완결 |
| **평가 대상 환경** | 실제 TEST API 환경 | Target URL: `https://robingraph-test.dove-nest.com`<br>Container Image: `robingraph-api:test-taxonomic-traits-eb8169862c0e`<br>데이터셋 ID: `d-9b84fb796702487a90cbf57e754995a8` (496건 고유 질의) |
| **1차 하네스 중단 및 조치** | SDK Assessment 스키마 제약 해결 | 24개 응답 수집 시점(`rank=None`, `taxon=None` 포함 케이스)에서 MLflow SDK 최상위 Null 제약 발생 (앱 오류 아님, 실패 런 `20261022T113250Z` 보존). 원본 불변 유지 및 `expectations={"contract": ...}` 중첩 래핑으로 해결 |
| **실제 API 496건 결과** | 계약 오류 0건, 이전 차이 0건 | - 계약 오류: **0건** (496 / 496 전수 통과, pass rate 100%)<br>- 이전 baseline 대비 status/disposition/coverage 차이: **0건**<br>- 응답 분포: `answer` 289건, `empty` 137건, `insufficient` 58건, `clarify` (status 없음) 12건 (합계 496건) |
| **DB Oracle 전수 대조** | 480건 직대조 불일치 0건 | - 대상: 480건 (`query`/`empty` 478건 + 아종 직접 부족 2건)<br>- 외부 활성 TEST Neo4j 및 PG 직접 조회 실행 완결 (`db-evidence.json`)<br>- 고유 반환 종수: **1,879종** / 검증 조건 근거: **3,126건** / 근거 오류: **0건** |
| **Safety 엄격 감사** | 18개 비답변 사유 100% 부합 | - 18건 비답변 사유별 엄격 감사 전수 통과 (`18/18 pass`, `safety-audit.json`)<br>- 모의 변조 13건 대상 self-check 전수 탐지 (`13/13`) *(감사기 자체 검증이며 앱 API 13건 검증 아님)* |
| **지연 시간 및 라우팅 추적** | 지연 측정 및 라우팅 메타 보존 | - 지연 시간: `first_request` **1,484.569 ms**, `subsequent_request` (495건) **p50 774.13 ms**, **p95 1,527.66 ms** (정렬 floor .95*(n-1) 계산, 가열 상태 확인, 부하테스트 아님)<br>- 라우팅: 496건 전수 `semantic` 라우팅 확인 (`selected_intent`, `route_method`, `kind` 보존) |
| **MLflow 실행 정보** | 신규 평가 Run 완료 | - Experiment ID: `33` (`robingraph-test`)<br>- Run ID: `0295848aaa854d8cb8acc289373daf67`<br>- Run URL: https://mlflow.dove-nest.com/#/experiments/33/runs/0295848aaa854d8cb8acc289373daf67<br>- 자산 경로: `docs/verification/assets/2026-10-22-dataset-evaluation-20261022T113441Z`<br>- 상태: **FINISHED (MLflow 결과표 496행 저장 완료, `summary.json`, `extended-summary.json`, `verified-results.json` 보존)** |
| **거버넌스 및 안전 상태** | 무영향 원칙 준수 | 기존 데이터셋 불변, 백로그 상태 일체 무변경, 운영 미배포, 조류 DB 쓰기 0건 (`bird_db_writes: 0`), Git commit/push 0건, 서비스 재시작 0건 |

---

## 1. 작업 배경 및 1차 하네스 중단 분석

### 1) 작업 배경
- 2026-10-22 등록 완결된 496건 통합 평가 데이터셋(`robingraph-taxonomic-regression-v1-746baf0adb1b`, ID `d-9b84fb796702487a90cbf57e754995a8`)에 대해 일회성 스크립트 실행을 넘어 MLflow GenAI 공식 평가 프레임워크(`mlflow.genai.evaluate`)를 통한 재평가를 수행함.
- Claude의 사전 스코어러 리뷰(`/tmp/taxonomic-trait-mlflow-scorer-review-claude.md`)에 따라, 단순한 상위 API 상태 코드(query ➔ answer/empty) 일치만으로는 질의 필터 누락이나 스코프 왜곡을 탐지할 수 없으므로, **DB Oracle 480건 직대조 및 보류/자료부족 18건 비답변 사유별 엄격 감사를 결합**하여 검증을 진행함.

### 2) 1차 시도 하네스 중단 원인 분석 (20261022T113250Z)
- **증상**: 24개 응답 수집 시점에서 MLflow 평가 하네스 중단 및 에러 발생.
- **실패 증거**: `docs/verification/assets/2026-10-22-dataset-evaluation-20261022T113250Z/` (`run.json`, `results.jsonl`, `harness-failure.log`, `harness-attempt.json`).
- **원인 분석**:
  ```text
  File ".../mlflow/genai/evaluation/harness.py", line 982, in _get_new_expectations
    for exp in eval_item.get_expectation_assessments()
  File ".../mlflow/genai/evaluation/entities.py", line 194, in get_expectation_assessments
    Expectation(name=key, value=val)
  File ".../mlflow/entities/assessment.py", line 419, in __init__
    raise MlflowException.invalid_parameter_value("The `value` field must be specified.")
  mlflow.exceptions.MlflowException: The `value` field must be specified.
  ```
  - MLflow SDK의 `get_expectation_assessments()`는 `expectations` 딕셔너리의 최상위 각 키를 `Expectation(name=key, value=val)` 엔터티로 변환함.
  - 이 때 `value` 인자가 `None`인 경우 `MlflowException`을 발생시킴.
  - 데이터셋 496건 중 분류군이 지정되지 않은 6건(`rank=None`, `taxon=None`; 예: `CT-016` 등)에서 최상위 값이 `None`으로 전달되어 예외가 발생함.
  - MLflow 비동기 예측/평가 파이프라인 특성상 24개 응답 수집 시점에서 중단되었으며, 실제 예외를 발생시킨 특정 케이스의 순번은 미확정임.
  - **이는 앱이나 백엔드 API 오류가 아니라, MLflow SDK Assessment 엔터티의 최상위 Null 허용 제약에 기인한 하네스 스키마 이슈임.**

---

## 2. 해결 방안 및 3중 엄격 검증 체계

### 1) 원본 데이터셋 보존 및 DataFrame 중첩 래핑
- 원본 Native 데이터셋(496건)의 expectations 스키마(`taxon`, `rank`, `conditions`, `outcome`)는 수정 없이 그대로 불변 유지함.
- `scripts/evaluate_graph_question_dataset.py`에서 `mlflow.genai.evaluate`로 전달하는 평가용 DataFrame 생성 시:
  ```python
  # 최상위 Null 제약을 우회하면서 내부 Null을 완벽히 보존
  eval_df["expectations"] = eval_df["expectations"].apply(lambda exp: {"contract": exp})
  ```
  - 최상위 키가 `"contract"` 1개로 단일화되고 그 값은 딕셔너리(`dict`, non-null)가 되므로 MLflow SDK의 `Expectation(name="contract", value={...})`가 정상 생성됨.
  - 스코어러 내부에서는 `expectations["contract"]`를 참조하여 원본의 `rank=None`, `taxon=None`을 그대로 보존하여 엄격한 일치성 검증을 수행함.

### 2) 3중 엄격 검증 파이프라인
1. **Contract Scorer (결정적 계약 스코어러, 496건)**:
   - `predict_fn`을 통해 반환된 응답과 기대값(`contract`)을 1:1 비교.
   - `taxon`, `rank`, `conditions` 일치 여부 및 `outcome`(`query`, `empty`, `hold`, `insufficient`) 판정.
2. **DB Oracle 재대조 (`verify_graph_question_evaluation_evidence.py`, 480건)**:
   - 496건 중 `query`/`empty` 478건과 아종 직접 부족 2건 등 총 **480건**에 대해 TEST 컨테이너(`robingraph-api-test`) 환경에서 외부 TEST Neo4j(32GB Mac .98) 및 PostgreSQL(NAS .99)을 직접 조회하여 조상 계통 및 형질을 재계산하고 전수 대조.
   - 반환 종수, `coverage`(`scoped`, `evaluable`, `matched`), 페이지네이션(`has_more`), 조건 일치성 검증.
3. **Safety 엄격 감사기 (`scripts/audit_graph_question_safety.py`, 18건)**:
   - 18개 비답변(non-answering) 케이스(`hold` 14건, `insufficient` 4건)의 사유별 엄격 감사:
     - `CLARIFY` (12건: `CT-017`~`CT-020`, `IT-034`~`IT-041`): `disposition == 'clarify'` 및 조건 미실행 확인
     - `AMBIGUOUS` (3건: `IT-043`, `IT-044`, `CT-016`): 복수 분류군 동음이의어로 인한 `ambiguous_taxon` 및 미해소 확인. 특히 **`IT-043`, `IT-044`는 조건 추출은 되었으나 `taxon_resolution="ambiguous"`로 의도적 미실행된 정상 보류(abstain)**임을 명문화하여 '조건 존재 = 실행 실패' 오판 방지.
     - `SUBSPECIES` (2건: `CT-011`, `IT-011`): 아종 질의에 대해 실제로 scope 및 직접 근거 조회를 수행했으나 데이터가 없어 `evaluable == 0`으로 정상 비답변 처리됨 확인 (`SUBSPECIES_LIMIT`). (DB 조회 미실행이 아님).
     - `SPECIFIC_PLANT` (1건: `IT-042`): 특정 식물 먹이 종 단위 기록 부재 한계 문구 확인 (`PLANT_LIMIT`)
   - **감사기 자체 검증(Self-check) 결과**: 과거 실제 응답 18건 대상 사전 검사 통과(`pass`) 및 13개 모의 변조 응답 대상 self-check에서 변조 13건 전수 탐지(`13/13`). *(주의: 감사기 자체 로직 검증이며 앱 API 13건 검증이 아님)*

### 3) 지연 시간 및 라우팅 메타데이터 기록 원칙
- **지연 시간 표기 원칙**:
  - 앱이 재시작되지 않고 이전 평가로 이미 가열(warm)된 상태이므로, 'Cold prototype load'로 단정하지 않고 **`first_request`와 `subsequent_request (p50/p95)`로만 분리 기록**.
- **라우팅 추적 원칙**:
  - API 응답 내 `selected_intent`, `route_method`, `result.kind` 메타데이터는 보존.
  - 단, MLflow `graph_intent` 스팬/상태에 대한 독립 감사는 미실시되었으므로 **'fallback 발생 여부 확인 완료' 등으로 추정하지 않음**.

---

## 3. 평가 실행 및 검증 완료 증거

### 1) 실행 환경 및 명령어
- **명령어**:
  ```bash
  uv run --with mlflow==3.14.0 python scripts/evaluate_graph_question_dataset.py \
    --env-file [TEST_ENV_FILE]
  ```
  *(스크립트 내부 상수 및 `publish-receipt.json`을 통해 대상 URL `https://robingraph-test.dove-nest.com`과 데이터셋 ID `d-9b84fb796702487a90cbf57e754995a8`을 자동 로드하며, 인자로는 `--env-file`만 전달)*
- **실행 컨테이너**: `robingraph-api:test-taxonomic-traits-eb8169862c0e` (Image ID `sha256:8638ed7a8382b4831d6996d6fa62a5e71806f428fbba48ef4c24e67a530cc3d6`)
- **실행 Run ID**: `0295848aaa854d8cb8acc289373daf67` (Experiment 33, `robingraph-test`)
- **최종 자산 보존 경로**: `docs/verification/assets/2026-10-22-dataset-evaluation-20261022T113441Z`

### 2) 실제 TEST API 496건 전수 실행 결과
- **계약 검증 결과**: **496 / 496 통과 (계약 오류 0건, pass rate 100%)**
  - `taxonomic_matrix`: 432 / 432 통과
  - `natural_language`: 20 / 20 통과
  - `prior_regression`: 44 / 44 통과
- **이전 기준선(baseline) 대비 차이**: status, disposition, coverage 차이 **0건**
- **응답 유형별 상세 집계**:
  - `answer`: 289건
  - `empty`: 137건
  - `insufficient`: 58건
  - `clarify` (status 없음): 12건
  - **합계**: 496건
- **실행 지연 시간 (Latency)**:
  - `first_request`: **1,484.569 ms** (~1.48s)
  - `subsequent_request` (495건): **p50 774.13 ms**, **p95 1,527.66 ms** (정렬 floor .95*(n-1) 계산)
  - *비고: 순차 API 호출 지연이며, 부하 테스트나 고립 Neo4j 지연시간이 아님*

### 3) Fresh DB Oracle 480건 재대조 결과 (`db-evidence.json`)
- **검증 환경**: TEST 컨테이너(`robingraph-api-test`)에서 오라클 검증 스크립트 실행, 외부 TEST Neo4j 및 PostgreSQL 직접 조회
- **검증 대상**: 480건 (`query`/`empty` 478건 + 아종 `insufficient` 2건)
- **고유 반환 종수 (`unique_returned_taxa`)**: **1,879종**
- **형질 및 조상 근거 검증 건수 (`checked_condition_supports`)**: **3,126건**
- **대조 결과**: **불일치 오류 0건 (`errors: []`), 전수 통과 (`passed: true`)**
- **조류 DB 쓰기**: **0건 (`bird_db_writes: 0`)**

### 4) Safety 비답변 사유 엄격 감사 결과 (`safety-audit.json`)
- **검증 대상**: 18개 비답변 케이스 (`audited: 18`, `expected_ids: 18`)
- **감사 결과**: **전수 사유 부합 통과 (`passed: true`, `failed: []`, `missing: []`)**
  - `CLARIFY` 12건: 정상 clarify 처리 확인
  - `AMBIGUOUS` 3건 (`IT-043`, `IT-044`, `CT-016`): 동음이의 및 미해소로 인한 정상 abstain 확인
  - `SUBSPECIES` 2건 (`CT-011`, `IT-011`): 아종 직접 근거 조회 후 `evaluable == 0` 정상 비답변 확인
  - `SPECIFIC_PLANT` 1건 (`IT-042`): 특정 식물 한계 안내 문구 확인
- **자체 검증(Self-check)**: 13개 모의 변조 케이스 전수 탐지 완료 (`13/13`)

---

## 4. MLflow 평가 결과 등록 및 아티팩트 보존

### 1) Run 상태 및 결과표 등록
- **Run 상태**: **FINISHED** (`0295848aaa854d8cb8acc289373daf67`)
- **결과표 (Evaluation Table)**: 496개 행 전수 저장 완료 (`mlflow-eval-results.json`)
- **실행 시간 및 동시성 관련 특이사항**:
  - `MLFLOW_GENAI_EVAL_MAX_WORKERS=1` 설정이 API 질의뿐만 아니라 MLflow SDK의 `_refresh_eval_result_traces`(서버로부터 496개 트레이스를 재조회하여 집계표를 생성하는 과정)까지 직렬화시켜 총 소요 시간이 과도하게 지연되는 원인이 됨 (Root 설정의 과도한 보수성 확인).

### 2) 보존 아티팩트 목록 (`docs/verification/assets/2026-10-22-dataset-evaluation-20261022T113441Z/`)
- `run.json`: 실행 메타데이터 및 대상 정보
- `results.jsonl`: 496건 질의 및 API 원본 응답
- `summary.json`: 스위트별 통과율, 지연시간 및 기본 집계
- `extended-summary.json`: DB Oracle, Safety 감사, 라우팅 및 지연 통계 통합 집계
- `mlflow-eval-results.json`: MLflow evaluation 결과 테이블
- `verified-results.json`: 3중 검증 통합 확인 결과
- `db-evidence.json`: 480건 fresh DB Oracle 전수 대조 증거
- `safety-audit.json`: 18건 비답변 사유 및 13건 모의변조 감사 증거
- `harness-attempt.json`: 1차 하네스 중단 및 해결 내역

---

## 5. 형상 관리 및 거버넌스 상태

- **백로그 상태**: **기존 백로그 상태 일체 무변경 (RG-208 완료 보존, RG-204/RG-205 진행 중 보존)**
- **기존 데이터셋**: **불변 유지 (`d-9b84fb796702487a90cbf57e754995a8` 기대값 수정 없음)**
- **사람 검토 상태**: **`human_reviewed: false` 명시 유지 (에이전트 검증셋)**
- **조류 DB 쓰기**: **0건 (`bird_db_writes: 0`)**
- **운영(Production) 배포**: **0건 (일체 미반영)**
- **Git 상태**: **commit / push 0건**
- **서비스 재시작**: **0건**

---

## 6. 한계 및 후속 과제

1. **회귀 전용 평가 (Regression Assessment)**:
   - 본 평가는 모델/파서 수정 피드백에 노출된 496건 회귀 데이터셋을 대상으로 하므로, 미공개 일반 성능 측정이 아닌 기존 품질 기준선의 엄격한 유지 여부를 검증하는 용도임.
2. **단일 스코프(`species_scope='all'`) 중심**:
   - 현재 496건 평가셋은 전수 종 스코프 위주로 구성되어 있으므로, 향후 한반도 조류 스코프(`korea`) 및 다양한 정렬 기준에 대한 추가 평가셋 보강이 권장됨.
3. **MLflow 평가 하네스 동시성 설정 최적화**:
   - 향후 대규모 평가 시에는 API 호출과 SDK 트레이스 집계 단계의 동시성을 분리하거나 적정 Worker 수를 확보하여 불필요한 직렬화 지연을 완화할 필요가 있음.

---

## 관련 문서

- [`./2026-10-22-graph-question-dataset-mlflow.md`](./2026-10-22-graph-question-dataset-mlflow.md)
- [`../../data/eval/graph_questions/taxonomic-regression-v1/README.md`](../../data/eval/graph_questions/taxonomic-regression-v1/README.md)
- [`../../data/eval/graph_questions/taxonomic-regression-v1/manifest.json`](../../data/eval/graph_questions/taxonomic-regression-v1/manifest.json)
- [`../../data/eval/graph_questions/taxonomic-regression-v1/publish-receipt.json`](../../data/eval/graph_questions/taxonomic-regression-v1/publish-receipt.json)
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-208|RG-208 상세 백로그]]

---
*문서 작성 일시: 2026-10-22*  
*작성자: dev / Writer (MLflow GenAI Evaluate 496건 재평가 완료)*
