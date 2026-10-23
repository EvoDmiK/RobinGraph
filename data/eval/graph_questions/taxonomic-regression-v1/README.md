# RobinGraph Taxonomic Regression Evaluation Dataset (v1)

- **Dataset Name**: `robingraph-taxonomic-regression-v1-746baf0adb1b`
- **Version**: `2026-10-22-v1`
- **MLflow Dataset ID**: `d-9b84fb796702487a90cbf57e754995a8`
- **MLflow Experiment**: Experiment 33 (`robingraph-test`)
- **MLflow Run ID**: `efc2f268f03e45d2933a0cd6add85e35`
- **MLflow Run URL**: https://mlflow.dove-nest.com/#/experiments/33/runs/efc2f268f03e45d2933a0cd6add85e35
- **Records**: 496 unique questions
- **Evaluation Role**: `regression` (회귀 테스트 및 모니터링 기준선용)
- **Human Reviewed**: `false` (`pending_human_review`, 사람 검토 미완료)

---

## 1. 개요 및 구성

본 데이터셋은 2026-10-22 의미 기반 그래프 질의 파이프라인의 전체 5대 계급(목 46, 과 252, 속 46, 종 46, 아종 42) 및 자연어 검증 과정에서 실제 TEST API로 검증된 질의 세트를 체계적으로 표준화한 회귀 평가 데이터셋입니다.

### 구성 스위트 (총 496건)
1. **`taxonomic_matrix` (432건)**: 46개 목, 252개 과 전수 및 속 46, 종 46, 아종 42건 표본 질의와 15개 형질 교차 질의 (`case_sha256: 914b6fd7…`)
2. **`natural_language` (20건)**: 공개 TEST URL에서 검증된 구어체 및 생활양식 파생 표현 질의 (`case_sha256: f210fe2c…`)
3. **`prior_regression` (44건)**: 초기 독립 작성 이력을 가진 분류군×형질 회귀 및 경계값 질의 (이전 파서/규칙 수정 피드백에 이미 노출되어 블라인드셋이 아니며 회귀 방지용으로만 사용, `case_sha256: 0a21fa14…`)

---

## 2. 파일 목록 및 해시 (SHA256)

| 파일명 | SHA256 다이제스트 | 설명 |
| --- | --- | --- |
| `questions.jsonl` | `746baf0adb1bda3cd8c0fcdf2c16d045fdc1a39bde7658bad093eed364a8ad58` | MLflow Dataset 정규 포맷 (inputs, expectations, tags) |
| `questions.csv` | `39ea0b080fe4fcaeff064218128fd0e51338765ea49850da5794593df6600e24` | 스프레드시트 검토 및 테이블 분석용 플랫 포맷 |
| `observations.jsonl` | `1f5c148c0828999df416649e87fd5b68deb8f1c9aaeff5c226f6cec80a344fb6` | 실제 TEST API 실행 관측치 (정확히 8개 필드: case_id, suite, question, response_status, disposition, coverage, passed, result_source) |
| `manifest.json` | - | 데이터셋 계급·형질 집계 및 원본 출처 매니페스트 |
| `publish-receipt.json` | - | 원격 MLflow 발행 영수증 및 재조회 검증 증거 |

---

## 3. 스키마 구조

### `questions.jsonl` 레코드 규격
- `inputs`:
  - `question`: 사용자 입력 질의 텍스트
- `expectations`:
  - `taxon`: 기대 분류군 명칭 (학명 또는 국명, 미지정 시 null)
  - `rank`: `order`, `family`, `genus`, `species`, `subspecies`, 또는 `None`/null (분류군 무관 질의 1건 및 보류/미해소 5건 포함)
  - `conditions`: 형질 조건 목록 (`op`, `trait_name`, `unit`, `value`)
  - `outcome`: 기대 응답 유형 (`query`, `empty`, `hold`, `insufficient`)
- `tags`:
  - `case_id`: 케이스 고유 식별자 (예: `BROAD-0001`, `CT-0001`, `IT-0001`)
  - `suite`: `taxonomic_matrix` / `natural_language` / `prior_regression`
  - `origin`: 원본 작성 출처 (`template_generated` 등)
  - `source_path`: 원본 출처 파일 경로
  - `human_reviewed`: `"false"` (사람 검토 미완료 명시)
  - `implementation_feedback_exposed`: `"true"` (구현 및 규칙 수정 피드백 노출 명시)
  - `evaluation_role`: `"regression"` (회귀 방지 및 기준선 추적용 명시)

### 관측치 분리 (`observations.jsonl`)
- 평가 기준(`expectations`)과 실제 런타임 실행 결과를 혼동하지 않도록, 실제 TEST API 실행 관측치는 `observations.jsonl`에 별도로 분리 저장되어 있습니다.
- 레코드당 정확히 다음 8개 필드로만 구성됩니다:
  - `case_id`: 케이스 고유 ID
  - `suite`: 검증 스위트 명칭 (`taxonomic_matrix` / `natural_language` / `prior_regression`)
  - `question`: 실행된 질의 텍스트
  - `response_status`: API 응답 상태
  - `disposition`: 처리 결과 분류
  - `coverage`: 스코프 및 검증 종수 통계 (`scoped`, `evaluable`, `matched`)
  - `passed`: 기대값 부합 여부 불리언 (`true` / `false`)
  - `result_source`: 원본 실행 결과 JSON 자산 경로
  *(주의: 임의의 `status`, `first`, `timing`, `elapsed_ms`, `n_items`, `span` 등의 미정의 필드는 포함되지 않음)*

---

## 4. 사용 방법

### MLflow에서 데이터셋 로드
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

### 로컬 JSONL 활용
```python
import json

with open("data/eval/graph_questions/taxonomic-regression-v1/questions.jsonl") as f:
    for line in f:
        item = json.loads(line)
        question = item["inputs"]["question"]
        expected = item["expectations"]
        # 회귀 검증 파이프라인 수행
```

---

## 5. 한계 및 거버넌스 주의사항

1. **회귀 전용 (Regression Only)**:
   - 본 데이터셋은 파서 및 라우터 수정 피드백 과정에 노출된 질의들이 포함되어 있으므로(`implementation_feedback_exposed: "true"`), **미공개 일반 정확도(Unseen General Accuracy) 측정용으로 사용할 수 없으며 회귀 방지용으로만 사용**해야 합니다.
2. **에이전트 검토 데이터셋 (Agent Expectations)**:
   - 본 데이터셋의 기대 조건은 생물학 전문가의 최종 검토를 거친 Gold Set이 아니며(`human_reviewed: "false"`), **RG-205 사람 검토 과제와 엄격히 분리**됩니다.
3. **초기 독립 작성 44건의 성격**:
   - `prior_regression` 44건은 초기 독립 작성 이력을 가지고 있으나, 이전 반복 수정 과정에서 이미 피드백으로 노출되었으므로 블라인드셋이 아니며 회귀 추적용으로 한정됩니다.
4. **고정 구문 기반 표본**:
   - 432건 매트릭스는 검토된 정형 문장 템플릿과 실제 카탈로그를 교차한 것으로, 임의의 다양한 구어체 자연어 표현 전체를 대변하지 않습니다.
