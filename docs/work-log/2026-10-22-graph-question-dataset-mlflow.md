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
  - evaluation-dataset
---

# [RG-208 / 평가셋] 그래프 질의 496건 통합 평가 데이터셋 구축 및 MLflow 등록 — 2026-10-22

> **문서 상태: 등록 및 검증 완료 (Native MLflow Dataset ID `d-9b84fb796702487a90cbf57e754995a8` 등록 완료, Experiment 33 Run `efc2f268f03e45d2933a0cd6add85e35` 아티팩트 보존, 서버 496건 기대값 재조회 동등성 및 4개 첨부파일 SHA256 일치 확인 완료; 단, 수정 피드백에 노출된 회귀 전용 데이터셋이며 사람 검토 미완료[`human_reviewed: "false"`, `implementation_feedback_exposed: "true"`] 명시, 기존 백로그 상태 보존, 운영 미배포, Git commit/push 없음, 조류 DB 쓰기 0건)**  
> 2026-10-22 전 계급(46목·252과·속·종·아종) 분류학적 커버리지 및 자연어 검증 완료 후, **사용자 요청("질문들을 데이터셋으로 만들어 MLflow에 업로드")**에 따라 실제 검증에 사용된 질의 세트를 체계적인 평가 데이터셋(Evaluation Dataset)으로 규격화하여 원격 MLflow에 등록하고 아티팩트를 보존했다.  
> 등록된 데이터셋은 직전 실제 TEST API 검증을 통과한 **총 496건의 고유 질의**(`broad` 432건 + `natural` 20건 + `regression` 44건)로 구성되었으며, **기대 조건/분류군/응답 유형(Expected Criteria)**과 **실제 런타임 관측 결과(Observed Execution Results)**를 엄격히 분리했다.  
> 원격 MLflow Tracking Server(Experiment 33, `robingraph-test`)에 Native Evaluation Dataset(`robingraph-taxonomic-regression-v1-746baf0adb1b`, ID `d-9b84fb796702487a90cbf57e754995a8`)으로 정식 등록되었으며, Run `efc2f268f03e45d2933a0cd6add85e35`에 4개 규격 파일(`questions.jsonl`, `questions.csv`, `observations.jsonl`, `manifest.json`)이 보존되었다.  
> 서버에 등록된 496건 기대값의 재조회 동등성(`native_readback_verified: true`) 및 다운로드된 4개 아티팩트의 SHA256 해시 일치(`artifact_readback_verified: true`)가 모두 확인되었다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 배경** | 검증 질의 데이터셋화 및 MLflow 업로드 | 사용자의 "질문들을 데이터셋으로 만들어 MLflow에 업로드" 요청 수용. 실제 검증 질의 496건을 MLflow 표준 평가 데이터셋으로 등록 완결 |
| **데이터셋 구성 (총 496건)** | 3개 검증 스위트 통합 | 1) `taxonomic_matrix`: 432건 (46목, 252과, 속 46, 종 46, 아종 42)<br>2) `natural_language`: 20건 (공개 TEST 자연어 질의)<br>3) `prior_regression`: 44건 (초기 독립 작성 이력 질의; 이전 구현 피드백에 노출되어 블라인드셋이 아닌 회귀 전용)<br>중복 없는 고유 496건 질의 통합 (`case_sha256` 3종 매핑) |
| **스키마 설계 원칙** | 기대 기준 vs 관측 결과 분리 | - **기대 기준 (`expectations`)**: 의도된 분류군, 계급, 15개 형질 조건, 기대 outcome (`query`, `empty`, `hold`, `insufficient`)<br>- **관측 결과 (`observations.jsonl`)**: 실제 TEST API 관측치 8개 필드(`case_id`, `suite`, `question`, `response_status`, `disposition`, `coverage`, `passed`, `result_source`)로 분리 (임의의 `status`, `first`, `timing`, `elapsed_ms`, `n_items`, `span` 없음) |
| **거버넌스 태그** | 튜닝 노출 및 사람 검토 라벨링 | `human_reviewed: "false"` (사람 미검토 명시), `implementation_feedback_exposed: "true"` (수정 피드백 노출 명시), `evaluation_role: "regression"` (회귀용 한정) |
| **MLflow Native 등록** | Dataset ID 및 Run 발행 완료 | - **Dataset ID**: `d-9b84fb796702487a90cbf57e754995a8`<br>- **Dataset Name**: `robingraph-taxonomic-regression-v1-746baf0adb1b`<br>- **Experiment Name (ID)**: `robingraph-test` (`33`)<br>- **Run ID**: `efc2f268f03e45d2933a0cd6add85e35`<br>- **Run URL**: https://mlflow.dove-nest.com/#/experiments/33/runs/efc2f268f03e45d2933a0cd6add85e35 |
| **발행 스크립트 및 환경** | 임시 SDK 환경 실행 | `scripts/publish_graph_question_dataset.py` 스크립트를 `uv run --with mlflow==3.14.0 …`로 실행 (저장소 `pyproject.toml` 변경 없음, 비밀정보 출력 배제) |
| **재조회 무결성 검증** | 서버 데이터 동등성 전수 확인 | 서버 등록 496건 기대값 재조회 일치 (`native_readback_verified: true`), 첨부 4개 아티팩트 다운로드 SHA256 일치 (`artifact_readback_verified: true`) |
| **거버넌스 및 안전 상태** | 무영향 원칙 준수 | 기존 백로그 상태 일체 무변경, 신규 테스트 재실행 없음(기존 영수증 연결), Production 배포 0건, 조류 DB 쓰기 0건 (`bird_db_writes: 0`), Git commit/push 0건, 서비스 재시작 0건 |

---

## 1. 작업 배경 및 목적

### 1) 사용자 요청
- 2026-10-22 진행된 의미 기반 그래프 질의 검증(베이스라인, 일반화, 전 계급 커버리지 432건, 자연어 20건, 독립 44건) 과정에서 검증된 질의들을 일회성 스크립트 실행 자산으로 두지 않고, **향후 지속적인 품질 모니터링과 회귀 방지를 위한 정식 평가 데이터셋으로 규격화하여 MLflow에 업로드**할 것을 요청함.

### 2) 데이터셋 규격화 목적
1. **평가 자산의 영구화**: 분산되어 있던 테스트 케이스(`independent-cases.json`, `broad-cases`, `natural-cases`)를 단일 표준 스키마로 통합.
2. **MLflow Native 연동**: MLflow GenAI Datasets(`mlflow.genai.datasets`) 인터페이스를 활용하여 실험(Experiment 33, `robingraph-test`)에 영구 등록 및 추적성 확보.
3. **엄격한 평가 거버넌스 준수**:
   - 기대치(Ground Truth / Expected)와 관측치(Run Artifacts)의 분리.
   - 각 질문이 모델 튜닝이나 규칙 수정 과정에 노출되었는지 여부(`implementation_feedback_exposed: "true"`)를 투명하게 기록하여 unseen gold와 혼동 방지.
   - 사람 검토가 완료되지 않은 에이전트 검토셋(`human_reviewed: "false"`)임을 명시하여 RG-205 사람 검토 과제와 엄격히 분리.

---

## 2. 평가 데이터셋 설계 및 구성 (총 496건)

### 1) 구성 스위트 내역 (`manifest.json`)
- **전 계급 커버리지 질의 (`taxonomic_matrix`)**: 432건
  - 목 46개 전수, 과 252개 전수, 속 46건, 종 46건, 아종 42건
  - 15개 형질 및 복합 AND 조건 교차 질의 (`cases_sha256: 914b6fd7…`, `results_sha256: cfeb2702…`)
- **공개 TEST 자연어 질의 (`natural_language`)**: 20건
  - 구어체 표현, 생활양식 파생 표현("X에서 생활" 등) 포함 (`cases_sha256: f210fe2c…`, `results_sha256: 955a40fa…`)
- **회귀 질의 (`prior_regression`)**: 44건
  - 초기 독립 작성 이력을 가진 평가셋 및 경계값 질의 (이전 구현/규칙 수정 피드백에 이미 노출되어 블라인드 평가셋이 아니며 회귀 방지 전용, `cases_sha256: 0a21fa14…`, `results_sha256: c036e245…`)
- **총합계**: **고유 질의 496건**

### 2) 분류 계급 및 형질 분포 집계
- **계급별 분포**:
  - `order` (목): 53건
  - `family` (과): 294건
  - `genus` (속): 50건
  - `species` (종): 49건
  - `subspecies` (아종): 44건
  - `None`: 6건 (분류군 무관 순수 형질 질의 1건[`IT-032`] 및 보류/미해소 5건[`CT-016` insufficient, `CT-017` hold, `IT-041` hold, `IT-043` hold, `IT-044` hold])
- **형질별 출현 건수**:
  - `habitat`: 47건 / `trophic_niche`: 60건 / `primary_lifestyle`: 32건 / `habitat_density_category`: 31건
  - `trophic_level`: 31건 / `diet_category`: 31건 / `beak_length_nares`: 60건 / `body_mass`: 34건
  - `beak_length_culmen`: 31건 / `beak_width`: 31건 / `beak_depth`: 31건 / `tail_length`: 59건
  - `tarsus_length`: 31건 / `wing_length`: 31건 / `diet_distribution`: 36건

### 3) 저장 파일 및 무결성 다이제스트
- `questions.jsonl` (286,458 bytes): `746baf0adb1bda3cd8c0fcdf2c16d045fdc1a39bde7658bad093eed364a8ad58`
- `questions.csv` (126,705 bytes): `39ea0b080fe4fcaeff064218128fd0e51338765ea49850da5794593df6600e24`
- `observations.jsonl` (185,480 bytes): `1f5c148c0828999df416649e87fd5b68deb8f1c9aaeff5c226f6cec80a344fb6`
- `manifest.json` (3,003 bytes)
- `publish-receipt.json` (580 bytes)

### 4) 스키마 상세 구조
- **`questions.jsonl` 레코드 규격**:
  - `inputs`:
    - `question`: 사용자 입력 질의 텍스트
  - `expectations`:
    - `taxon`: 기대 분류군 명칭 (학명 또는 국명, 미지정 시 null)
    - `rank`: `order`, `family`, `genus`, `species`, `subspecies`, 또는 `None`/null
    - `conditions`: 형질 조건 목록 (`op`, `trait_name`, `unit`, `value`)
    - `outcome`: 기대 응답 유형 (`query`, `empty`, `hold`, `insufficient`)
  - `tags`:
    - `case_id`: 케이스 고유 식별자 (`BROAD-0001` 등)
    - `suite`: 검증 스위트 명칭 (`taxonomic_matrix` / `natural_language` / `prior_regression`)
    - `origin`: 원본 작성 출처 (`template_generated` 등)
    - `source_path`: 원본 출처 파일 경로
    - `human_reviewed`: `"false"` (사람 검토 미완료 명시)
    - `implementation_feedback_exposed`: `"true"` (구현 피드백 노출 명시)
    - `evaluation_role`: `"regression"` (회귀 전용 명시)
- **`observations.jsonl` 관측치 규격**:
  - 레코드당 정확히 다음 8개 필드로만 구성:
    - `case_id`, `suite`, `question`, `response_status`, `disposition`, `coverage`, `passed`, `result_source`
  - *(주의: 임의의 `status`, `first`, `timing`, `elapsed_ms`, `n_items`, `span` 등의 미정의 필드는 포함되지 않음)*

---

## 3. 발행 실행 및 MLflow 등록 정보

### 1) 발행 명령어
- 실행 명령어:
  ```bash
  uv run --with mlflow==3.14.0 python scripts/publish_graph_question_dataset.py \
    --publish \
    --env-file [TEST_ENV_FILE]
  ```
- *실행 환경 주의*: Native Datasets API 지원을 위해 `mlflow==3.14.0`을 인라인으로 임시 사용하여 발행했으며, 저장소의 `pyproject.toml`은 수정하지 않고 유지함. 환경 설정 파일 내 민감한 인증 정보는 화면 및 로그에 출력되지 않음.

### 2) MLflow 등록 영수증 (`publish-receipt.json`)
- **Tracking Server URL**: `https://mlflow.dove-nest.com`
- **Experiment Name (ID)**: `robingraph-test` (`33`)
- **Dataset Name**: `robingraph-taxonomic-regression-v1-746baf0adb1b`
- **Dataset ID**: `d-9b84fb796702487a90cbf57e754995a8`
- **Run ID**: `efc2f268f03e45d2933a0cd6add85e35`
- **Run URL**: https://mlflow.dove-nest.com/#/experiments/33/runs/efc2f268f03e45d2933a0cd6add85e35
- **등록 레코드 수**: 496건
- **Content SHA256**: `746baf0adb1bda3cd8c0fcdf2c16d045fdc1a39bde7658bad093eed364a8ad58`

### 3) 재조회 무결성 검증
- **Native Dataset 검증 (`native_readback_verified`)**: `true`
  - 서버에 등록된 데이터셋을 `get_dataset`으로 직접 재조회하여 496건 기대값 및 스키마 구조가 로컬 파일과 정확히 동등함을 확인.
- **아티팩트 다운로드 검증 (`artifact_readback_verified`)**: `true`
  - Run `efc2f268f03e45d2933a0cd6add85e35`에 첨부된 4개 아티팩트(`questions.jsonl`, `questions.csv`, `observations.jsonl`, `manifest.json`)를 다운로드하여 로컬 원본과의 SHA256 해시 일치를 확인.

### 4) SDK 데이터셋 활용 방법
```python
import os
import mlflow
from mlflow.genai.datasets import get_dataset

# Tracking URI를 환경 변수로 설정해야 정상 로드 가능
# os.environ["MLFLOW_TRACKING_URI"] = "https://mlflow.dove-nest.com"

dataset = get_dataset(dataset_id="d-9b84fb796702487a90cbf57e754995a8")
df = dataset.to_df()  # to_pandas()가 아닌 to_df() 지원
print(f"Loaded dataset: {dataset.name}, records: {len(df)}")
```

---

## 4. 형상 관리 및 거버넌스 상태

- **백로그 상태**: **기존 백로그 상태 일체 무변경 (RG-208 완료 보존, RG-204/RG-205 진행 중 보존)**
- **신규 테스트 재실행**: **없음 (`tests_rerun: false`, 직전 검증된 TEST 영수증 연결)**
- **조류 DB 쓰기**: **0건 (`bird_db_writes: 0`)**
- **운영(Production) 배포**: **0건 (일체 미반영)**
- **Git 상태**: **commit / push 0건**
- **서비스 재시작**: **0건**

---

## 5. 한계 및 후속 과제

1. **사람 검토(Human Gold Review) 미완료 명시**:
   - 본 496건 데이터셋의 기대 조건은 원DB Oracle 및 규칙 검증을 거쳤으나 생물학 전문가에 의한 사람 검토(Human Review)는 완료되지 않은 상태임.
   - 따라서 메타데이터에 `human_reviewed: "false"`를 명시하여 RG-205 사람 검토 과제와 엄격히 분리함.
2. **회귀 전용 (Regression Role)**:
   - 본 데이터셋은 파서 및 라우터 수정 과정의 피드백으로 사용된 문항들이 포함되어 있으므로(`implementation_feedback_exposed: "true"`), '미공개 블라인드 평가'가 아닌 '회귀 방지 및 기준선 추적용'으로만 활용해야 함.
3. **초기 독립 작성 44건의 성격**:
   - `prior_regression` 44건은 초기 독립 작성 이력을 가지고 있으나, 이전 반복 수정 과정에서 이미 피드백으로 노출되었으므로 블라인드셋이 아니며 회귀 추적용으로 한정됨.

---

## 관련 문서

- [`data/eval/graph_questions/taxonomic-regression-v1/README.md`](data/eval/graph_questions/taxonomic-regression-v1/README.md)
- [`data/eval/graph_questions/taxonomic-regression-v1/manifest.json`](data/eval/graph_questions/taxonomic-regression-v1/manifest.json)
- [`data/eval/graph_questions/taxonomic-regression-v1/publish-receipt.json`](data/eval/graph_questions/taxonomic-regression-v1/publish-receipt.json)
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-208|RG-208 상세 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-전계급-432건-분류학적-커버리지-검증|전 계급 432건 분류학적 커버리지 및 원DB Oracle 대조 검증 (2026-10-22)]]

---
*문서 작성 일시: 2026-10-22*  
*작성자: dev / Writer (496건 MLflow 평가 데이터셋 구축 및 등록 완료)*
