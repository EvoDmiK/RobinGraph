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
  - taxonomic-coverage
  - graphrag
---

# [RG-208] 전 계급(46목·252과·속·종·아종 432건) 분류학적 커버리지 및 원DB Oracle 대조 검증 — 2026-10-22

> **문서 상태: 검증 범위 완료 (최신 TEST 이미지 `eb8169862c0e` 배포, `broad-final` 432건 실제 API 및 원DB Oracle 불일치 0건 전수 통과, 공개 TEST `natural-public-final` 20건 전수 통과 및 원DB 대조 통과, 레거시 27건 통과; 단, 모든 분류군 전수 검증이나 15개 형질 모든 조합 검증이 아니며 표본 내 편중 완화 검증으로 한정, RG-205 사람 검토 미완료로 상위 에픽 RG-204 진행 중 유지, 운영 미배포, Git commit/push 없음, 조류 DB 쓰기 0건)**  
> 2026-10-22 전체 분류군×15개 형질 일반화 수정 구현 및 공개 TEST 배포 후 제기된 **기존 검증 표본의 특정 분류군(까마귀과, Corvidae) 편중 한계(직전 실제 실행 32건 중 23건, 71.9%)**를 공식 인정하고, 전체 46개 목과 252개 과 각각 1질의 및 하위 계급(속 46, 종 46, 아종 42건) 표본 총 432건에 대한 교차 검증을 완수했다.  
> 직전 검증 단계에서 생활양식 자연어 결함(`CT-013` "동박새과 중 나무 위에서 생활하는 새는?")이 발견되어, `graph_condition_extractor.py`에 "X 생활" 표시값으로부터 "X에서 생활" 파생 및 연결 어미("하며", "하고", "하면서") 처리를 추가하고 3개 회귀 테스트를 작성했다. Root focused 110건 통과 후 최신 이미지 `robingraph-api:test-taxonomic-traits-eb8169862c0e`를 배포하여 shadow 동등성 및 fixture 검증을 거쳐 active 모드로 전환했다.  
> **공개 TEST URL 대상 자연어 20건 검증 경과**:  
> 1) 1차 시도(`independent-api-natural-fixed.json`): Python 기본 User-Agent 사용 시 20건 전원 `HTTPError` 발생 (실제 애플리케이션 문장 검증 미도달 하네스 차단 관측, 실패 기록 보존).  
> 2) 하네스 명시 후 재실행(`independent-api-natural-public-final.json`): `Mozilla` User-Agent 명시 후 공개 TEST URL에서 **20 / 20 전원 정상 통과 확정**. `CT-013`은 동박새과 147개 범위(scoped), 129개 자료 부합(evaluable), 129개 조건 일치(matched) 중 페이징 제한에 따라 첫 20종 반환 및 `has_more: true`로 정상 응답했다. 원DB Oracle 대조(`natural-public-final-db-evidence.json`)에서도 반환된 고유 종 199개, 조건 근거 294건에 대해 불일치 0건(`passed: true`)을 확인했다.  
> **최신 이미지 전 계급 432건 최종 검증 (`broad-final`)**:  
> 최신 배포 컨테이너 상에서 432건 전 계급 API 재실행(`broad-final`)을 완료하여 **432 / 432 전수 통과**를 달성했으며, 원 PostgreSQL/Neo4j DB 직접 조회 Oracle(`broad-final-db-evidence.json`)을 통해 **432건 질의 전수 대조, 반환된 고유 종 1,676개, 조건 근거 2,245건에 대한 불일치 0건 (`errors: []`, `passed: true`)**을 확정했다.  
> 레거시 27개 질의(`legacy-api-active.json`) 역시 최신 active 모드에서 전원 정상 통과했다. (fingerprint 동등성 비교는 shadow 7질문에서만 수행되었으며, active 27은 성공/조건 검증임)  
> *(주의: 본 432건 검증은 전체 46목 252과 각각 1질의 및 하위 계급 표본 질의로 표본 내 편중을 완화한 것이며, 모든 분류군 전수 검증이나 편중의 완전한 해소, 15개 형질의 모든 조합(카르테시안 곱) 검증, 일반적인 안전 규칙 100% 보장을 의미하지 않는다.)*

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 배경** | 까마귀과 편중 한계 인정 및 완화 | 직전 32건 실제 실행 중 23건(71.9%)이 까마귀과(`Corvidae`)에 편중되었고, 34,891건 치환 검사는 고정 템플릿 파서 감사였음을 인정. 전체 46목 252과 각 1질의 및 하위 계급(속 46, 종 46, 아종 42) 표본 총 432건으로 표본 내 편중 완화 및 교차 검증 수행 |
| **코드 수정 내역** | `CT-013` 생활양식 표현 파생 확장 | 1) `src/robingraph/retrieval/graph_condition_extractor.py` (`17765013…`): "X 생활" 라벨에서 "X에서 생활" 파생 및 연결 어미("하며", "하고", "하면서") 지원.<br>2) `tests/test_taxon_traits.py` (`7c6665d7…`): 3개 회귀 테스트 메서드 추가 |
| **단위 / 회귀 검증** | Root 110건 / Claude 162건 통과 | 1) Root focused: `PYTHONPATH=tests uv run --locked --extra test python -m unittest tests.test_taxon_traits tests.test_taxon_traits_api tests.test_graph_condition_extractor tests.test_graph_intent_schema tests.test_graph_semantic_router tests.test_graph_questions` 실행으로 110건 전수 통과 (0.999s, OK).<br>2) Claude: 162건 통과 및 실제 DB 4건 실측 전원 통과 (`claude-lifestyle-db.json`) |
| **TEST 최신 배포** | 이미지 `eb8169862c0e` active 전환 | 이미지 `robingraph-api:test-taxonomic-traits-eb8169862c0e` 배포, 레거시 shadow 동등성 및 fixture smoke 검증 완료 후 `active` 모드 전환 (`test-release.json`) |
| **전 계급 432건 검증** | `broad-final` 432/432 전원 통과 | 최신 배포 이미지 상에서 432건 전 계급 API 재실행 완료 (`independent-api-broad-final.json`).<br>- `answer`: 248건<br>- `empty`: 132건<br>- `insufficient_data`: 52건 (아종 42건 전원 포함)<br>- 실패: 0건 |
| **원DB 독립 Oracle 대조** | 1,676종·2,245조건 불일치 0건 | `broad-final-db-evidence.json`: 반환된 1,676개 고유 종, 2,245건의 조건 근거, 432건의 스코프/일치수 전수 대조 결과 **불일치 0건 (`errors: []`, `passed: true`)** |
| **자연어 공개 검증 (하네스 분리 기록)** | 하네스 HTTP 차단 분리 후 20/20 확정 | 1) `independent-api-natural-fixed.json`: 기본 User-Agent 사용 시 공개 URL 20건 `HTTPError` 차단 관측 (실제 문장 검증 미도달 하네스 결함 기록 보존).<br>2) `independent-api-natural-public-final.json`: `Mozilla` User-Agent 명시 후 **공개 URL 20/20 전수 통과 확정** (`CT-013` 정상 응답 포함).<br>3) `natural-public-final-db-evidence.json`: 199종, 294조건 Oracle 불일치 0건 (`passed: true`) |
| **레거시 회귀 검증** | 레거시 27개 질의 active 통과 | `legacy-api-active.json`: 레거시 27개 질의 실제 TEST API active 모드 전수 통과 (성공/조건 검증 통과) |
| **지식 그래프 갱신** | Graphify AST 갱신 완료 | 코드 변경 반영 후 `graphify update .` 수행 완료 (`graphify.log`) |
| **거버넌스 및 안전 상태** | 운영/Git/DB 불변 준수 | Production 배포 0건, 조류 DB 쓰기 0건 (`bird_db_writes: 0`), Git commit/push 0건 (TEST 컨테이너 교체 및 Root/Claude 코드 수정은 검증 완료됨) |

---

## 1. 작업 배경 및 문제 분석

### 1) 사용자 지적 및 기존 검증의 한계
- **까마귀과(Corvidae) 편중 인정**:
  - 직전 일반화 검증에서 실제 TEST API로 실행 및 DB 대조가 이루어진 32건의 질의 중 23건(71.9%)이 까마귀과(`Corvidae`)에 집중되어 있었음.
  - 다양한 목과 과, 속, 종, 아종 전반에 걸친 실제 동작 검증 표본이 부족했음을 공식 인정함.
- **고정 템플릿 감사의 성격 명확화**:
  - `catalog-fruit/habitat-parse-audit.json`의 34,891건 검사는 고정된 문장 템플릿에 명칭을 대입하여 파서가 분류군과 형질을 추출할 수 있는지를 점검한 구문 감사(Parser Audit)였음.
  - 이는 실제 DB에 저장된 계통 트리 탐색, Cypher 질의 생성, 실제 형질 필터링 및 응답 조립까지 포괄하는 '실제 전체 DB 엔드투엔드 질의 실행'이 아니었음.

### 2) 전체 커버리지 검증 목표 및 정확한 범위 규정
- 활성 DB에 존재하는 모든 상위 계급(목 46개, 과 252개) 각 1질의 검증.
- 하위 계급(속 46개, 종 46개, 아종 42개)에 대해 각 목을 대표하는 균등 표본 질의 검증.
- 총 432건의 질의 세트를 구성하여 실제 TEST API로 호출하고, 원 DB의 실제 계통(ancestry)과 형질 주장(claims) 데이터를 기반으로 정답 Oracle과 대조.
- *(정확한 표현 주의)*: 본 검증은 전체 46목 252과 각각 1질의 및 하위 계급 표본 질의로 표본 내 편중을 완화한 것이며, **모든 분류군 전수 검증이나 편중의 완전한 해소, 15개 형질의 모든 조합(카르테시안 곱) 검증, 일반적인 안전 규칙 100% 보장을 의미하지 않음**.

---

## 2. 평가 데이터셋 설계 (총 432건)

### 1) 계급별 질의 구성 (`summary.json`)
- **목(Order) 전수**: 46개 목 전체 (각 1질의: 37 answer, 9 empty)
- **과(Family) 전수**: 252개 과 전체 (각 1질의: 161 answer, 90 empty, 1 insufficient_data)
- **속(Genus) 표본**: 46개 속 (각 목별 1개 대표 속: 27 answer, 17 empty, 2 insufficient_data)
- **종(Species) 표본**: 46개 종 (각 목별 1개 대표 종: 23 answer, 16 empty, 7 insufficient_data)
- **아종(Subspecies) 표본**: 42개 아종 (각 목별 1개 대표 아종: 42 insufficient_data — 자료 부족 시 부모 종 대체 배제 안전 규칙 준수)
- **고유 분류군 수**: 432개 (까마귀과는 1건으로 제한하여 표본 내 편중 완화)
- **복합 조건 질의 수**: 87건
- **데이터셋 해시**: `case_sha256: 914b6fd74343936aa35ba8f6f571e10f9164751e908892c984db044a46949945`

### 2) 15개 형질의 계급별 분포 (`trait_rank`)
| 형질 필드 (Trait Field) | 목(Order) | 과(Family) | 속(Genus) | 종(Species) | 아종(Subspecies) |
| --- | :---: | :---: | :---: | :---: | :---: |
| `habitat` (서식지) | 4 | 16 | 3 | 3 | 3 |
| `trophic_niche` (섭식 지위) | 7 | 33 | 6 | 6 | 6 |
| `primary_lifestyle` (주 생활양식) | 3 | 17 | 3 | 3 | 3 |
| `habitat_density_category` (서식 밀도) | 3 | 17 | 3 | 3 | 3 |
| `trophic_level` (영양 단계) | 3 | 17 | 3 | 3 | 3 |
| `diet_category` (주요 식단 범주) | 3 | 17 | 3 | 3 | 3 |
| `beak_length_nares` (부리 길이 - 콧구멍) | 6 | 34 | 6 | 6 | 6 |
| `body_mass` (체중) | 3 | 17 | 3 | 3 | 3 |
| `beak_length_culmen` (부리 길이 - 능선) | 3 | 17 | 3 | 3 | 3 |
| `beak_width` (부리 너비) | 3 | 17 | 3 | 3 | 3 |
| `beak_depth` (부리 깊이) | 3 | 17 | 3 | 3 | 3 |
| `tail_length` (꼬리 길이) | 6 | 33 | 7 | 6 | 5 |
| `tarsus_length` (발척 길이) | 3 | 17 | 3 | 3 | 3 |
| `wing_length` (날개 길이) | 3 | 17 | 3 | 3 | 2 |
| `diet_distribution` (먹이 구성비) | 3 | 16 | 3 | 4 | 2 |
| **계급별 총 질의 수** | **46** | **252** | **46** | **46** | **42** |

---

## 3. 수정 및 구현 내용

### 1) 결함 분석 및 수정
- **결함 증상**: Claude 자연어 20건 검증 중 `CT-013` ("동박새과 중 나무 위에서 생활하는 새는?") 질의 시, "나무 위 생활" 표시값과 구어체 표현 "나무 위에서 생활하는" 간의 조사/어미 차이로 인해 조건 추출에 실패하고 `clarify`로 보류됨.
- **수정 구현**:
  - `src/robingraph/retrieval/graph_condition_extractor.py` (`17765013…`):
    - `primary_lifestyle`의 "X 생활" 라벨로부터 "X에서 생활" 변형을 자동 파생.
    - 서술 및 복합 조건 연결 어미("하며", "하고", "하면서") 결합 인식 지원.
  - `tests/test_taxon_traits.py` (`7c6665d7…`):
    - 신규 생활양식 파생 표현에 대한 3건의 회귀 테스트 메서드 추가.

### 2) 테스트 하네스 및 단위 검증
- **Root Focused 테스트**:
  - 실행 명령어:
    ```bash
    PYTHONPATH=tests uv run --locked --extra test python -m unittest \
      tests.test_taxon_traits \
      tests.test_taxon_traits_api \
      tests.test_graph_condition_extractor \
      tests.test_graph_intent_schema \
      tests.test_graph_semantic_router \
      tests.test_graph_questions
    ```
  - 결과: **110건 전수 통과 (0.999s, OK)** (`focused-python-fixed-harness.log`)
  - *하네스 수정 메모*: 첫 실행 시 106건 중 1건 `ImportError: Failed to import test module: test_taxon_traits_api (No module named 'asgi_client')`가 발생했으나, 이는 테스트 실행 환경의 PYTHONPATH에 `tests` 디렉터리가 누락되어 발생한 테스트 하네스 설정 문제였으며, `PYTHONPATH=tests` 추가로 즉시 정상 통과함 (애플리케이션 결함 아님).
- **Claude 단위 및 실 DB 검증**:
  - Claude 테스트 스위트 162건 전수 통과.
  - 실제 DB 대상 4건 질의 검증 (`claude-lifestyle-db.json`): 동박새과, 칼새목, 꿩과, 딱따구리과 복합 질의 모두 `status: "answer"` 정상 반환.

---

## 4. 배포 및 회귀·자연어 검증 결과

### 1) 최신 TEST 배포 상태 (`test-release.json`, `final-state.json`)
- **대상 환경**: `robingraph-api-test` (16GB Mac mini .97)
- **최신 이미지**: `robingraph-api:test-taxonomic-traits-eb8169862c0e`
- **소스 해시**: `eb8169862c0ed6f616c480441e1befddda3a32fdead09e25cb77fd3aeaa2a802` (196개 파일 런타임 매니페스트 일치 확인)
- **릴리스 디렉터리**: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-eb8169862c0e-a6d975`
- **모드 전환 라이프사이클**: `shadow` (레거시 7개 베이스라인 지문 동등성 및 fixture smoke 검증 통과) → **`active` 전환 완료**

### 2) 레거시 27개 질의 active 회귀 검증 (`legacy-api-active.json`)
- 최신 배포 이미지 `eb8169862c0e` 상에서 레거시 27개 질문 실제 TEST API 호출: **27건 전원 정상 통과** (성공/조건 검증 통과; fingerprint 동등성 비교는 shadow 7질문에서만 수행되었으며 active 27은 성공/조건 검증임).

### 3) 공개 TEST URL 자연어 20건 검증 (하네스 분리 기록)
- **1차 시도 (하네스 네트워크 차단 결함)** (`independent-api-natural-fixed.json`):
  - 공개 TEST URL(`https://robingraph-test.dove-nest.com`) 대상 호출 시, Python 기본 User-Agent(`Python-urllib`)를 사용하여 20건 전원 `HTTPError` 발생.
  - 이는 애플리케이션의 질의 해석 엔진에 도달하지 못한 HTTP 차단 관측이었음.
  - *기록 원칙*: 최종 성공으로 이전 실패를 숨기지 않고 해당 영수증 파일을 분리 보존함.
- **2차 시도 (하네스 명시 후 전수 통과)** (`independent-api-natural-public-final.json`):
  - 검증기 스크립트에 `Mozilla/5.0 …` User-Agent를 명시한 후 동일 공개 TEST URL로 재실행.
  - 결과: **20 / 20 전원 정상 통과 (성공률 100%)**
  - `CT-013` ("동박새과 중 나무 위에서 생활하는 새는?") 결과:
    - `scoped: 147`, `evaluable: 129`, `matched: 129`
    - 페이징 제한에 따라 **첫 20종 반환 + `has_more: true`** 정상 응답 확인 (129종 전부 반환이 아님).
- **원DB 독립 Oracle 대조** (`natural-public-final-db-evidence.json`):
  - 반환된 고유 종 199개, 조건 근거 294건, 14건의 스코프/매치 대조 결과: **불일치 0건 (`errors: []`, `passed: true`)**
  - 조류 DB 쓰기: **0건 (`bird_db_writes: 0`)**

### 4) 전 계급 432건 최종 검증 (`broad-final`)
- **실제 TEST API 전수 실행** (`independent-api-broad-final.json`, `summary.json`):
  - 432건 전 계급 API 호출: **432 / 432 전수 통과 (100.0%)**
  - 응답 유형 집계:
    - `answer`: **248건**
    - `empty`: **132건**
    - `insufficient_data`: **52건** (아종 42건 전원 포함)
    - 실패: **0건** (`failures: []`)
- **원DB 독립 Oracle 대조** (`broad-final-db-evidence.json`):
  - 반환된 고유 조류 종 (`unique_returned_taxa`): **1,676개 종**
  - 검증된 조건 근거 (`checked_condition_supports`): **2,245건**
  - 정확 스코프 및 매치 대조 (`checked_exact_scope_and_match_counts`): **432건 질의 전수 대조**
  - 불일치 및 에러 (`errors`): **0건 (`[]`)**
  - 최종 판정 (`passed`): **`true`**
  - 조류 DB 쓰기 (`bird_db_writes`): **0건**

---

## 5. 배포 및 형상 관리 상태

- **대상 환경**: 공개 TEST 환경 (`robingraph-api-test`, image `robingraph-api:test-taxonomic-traits-eb8169862c0e`)
- **애플리케이션 코드**: Root/Claude 통합 완료 (`graph_condition_extractor.py`, `test_taxon_traits.py`)
- **조류 DB 쓰기**: **0건 (`bird_db_writes: 0`)**
- **운영(Production) 배포**: **0건 (일체 미반영, 사용자 명시 승인 전 실행 금지)**
- **Git 상태**: **commit / push 0건**

---

## 6. 검증 범위 한계 명시

1. **표본 구성 및 조합 한계**:
   - 본 432건은 전체 46목 252과 각각 1질의 및 하위 계급(속 46, 종 46, 아종 42) 표본 질의로 구성되어 표본 내 까마귀과 편중을 완화한 것이며, **모든 분류군 전수 검증이나 15개 형질의 모든 조합(카르테시안 곱)을 검증한 것이 아님**.
   - '모든 분류군 전수 검증', '편중 완전히 해소', '안전규칙 100% 일반 보장'과 같은 과대표현을 일체 배제함.
2. **검토된 어휘 기반 한계**:
   - 본 검증은 검토된 정형 어휘 및 특정 파생 표현(X에서 생활 등)을 실제 카탈로그와 교차한 것이며, 임의의 미확인 구어체 표현 전체에 대한 지원을 뜻하지 않음.
3. **상위 에픽 및 사람 검토 미완료**:
   - **RG-205 사람 검토(Human Gold Review)는 여전히 미완료 상태**이며, 본 RG-208 커버리지 검증을 완료하더라도 상위 에픽(RG-204) 전체 완료로 간주하지 않음 (RG-204 진행 중 유지).

---

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-208|RG-208 상세 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-전체-분류군-형질-일반화-수정-검증|전체 분류군×15개 형질 일반화 수정 구현 및 공개 TEST 배포 검증]]
- `docs/verification/assets/2026-10-22-taxonomic-coverage/summary.json`
- `docs/verification/assets/2026-10-22-taxonomic-coverage/broad-final-db-evidence.json`
- `docs/verification/assets/2026-10-22-taxonomic-coverage/final-state.json`
- `docs/verification/assets/2026-10-22-taxonomic-coverage/natural/independent-api-natural-fixed.json` (하네스 차단 보존)
- `docs/verification/assets/2026-10-22-taxonomic-coverage/natural/independent-api-natural-public-final.json` (공개 20/20 확정)
- `docs/verification/assets/2026-10-22-taxonomic-coverage/natural/natural-public-final-db-evidence.json` (Oracle 대조)
- `docs/verification/assets/2026-10-22-taxonomic-coverage/legacy-api-active.json` (레거시 27건 통과)
- `docs/verification/assets/2026-10-22-taxonomic-coverage/test-release.json` (최신 배포)

---
*문서 작성 일시: 2026-10-22*  
*작성자: dev / Writer (전 계급 432건 커버리지 및 원DB Oracle 대조 최종 검증 완료)*
