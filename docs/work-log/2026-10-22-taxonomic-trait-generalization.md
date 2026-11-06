# [RG-208] 전체 분류군(목·과·속·종·아종) × 15개 형질 일반화 수정 구현 및 공개 TEST 배포 검증 — 2026-10-22

> **문서 상태: 검증 범위 완료 (공개 TEST 배포, 실제 API 44건 회귀, 4개 스코프, 브라우저 12건 및 MLflow 관측 검증 완료; 단, 모든 자연어 지원 완료가 아니며 더 넓은 별도 표현 검증은 후속 과제 명시, 운영 미배포, Git commit/push 없음)**  
> 상위 에픽 **RG-204 (의미 기반 그래프 질의 해석 및 안전한 실행 전환)** 및 **RG-208 (통합·관측·TEST 비교·단계적 전환)**의 런타임 베이스라인 배포 검증 완료 이력을 보존하되, 실제 TEST 환경에서 사용자 실질 질의(`"까마귀과면서 열매를 먹는 새는 어떤 종이 있어?"`) 시 발생한 `clarify` 실패 및 "모든 분류군에 해야지/먹이에 대해서만 진행할 거야?" 지적에 따른 **전체 활성 5대 계급(목 46, 과 252, 속 2,376, 종 11,131, 아종 19,879; 총 33,684 분류군) × 15개 형질(먹이·서식지·생활·수치 치수) 일반화 수정 구현 및 공개 TEST 환경 배포·엔드투엔드 검증**을 완료했다.  
> 신규 컨테이너 이미지 `robingraph-api:test-taxonomic-traits-9adf41538e2e`를 공개 TEST 환경에 배포하여 **`shadow` -> `active` -> `off` -> `active`** 단계적 전환 라이프사이클을 거치며 기존 7질문 레거시 베이스라인 지문(fingerprint) 보존 확인, 공개 TEST 실제 API 44건 회귀 전원 통과, 4대 `species_scope` 통과, 공개 Chromium 뷰포트(1280px 데스크톱 / 390px 모바일) 각 6질문 총 12건 전수 렌더링 정상(페이지 에러 0건)을 확인했다. 또한 외부 원격 MLflow 실험 33에 `graph_intent.route` 및 `graph_intent.candidates` span이 성공적으로 저장 및 조회됨을 확인했다.  
> **검증 범위 및 한계 명시**:
> 1. 활성 카탈로그의 실제 분류 계급은 **목·과·속·종·아종 5단계**이며, 강(class) 노드는 DB에 0건이고 코드 상 지원하지 않는다 (강 지원 표기 배제).
> 2. Root가 작성한 독립 44건 평가 세트는 최초 실행 시 42건 통과 / 2건 안전 보류 후, 표기 정규화 수정을 거쳐 재검증 44건 전원 통과했다. 다만, 해당 44건이 수정 과정의 피드백으로 사용되었으므로 이를 **'미공개 일반 정확도(Fresh/Unseen Accuracy)'로 표현하지 않고 '피드백 반영 회귀 재검증 통과'로 명확히 한정**한다. 또한 본 검증이 **모든 구어체 자연어 질의 지원을 뜻하는 것은 아니며, 더 넓은 표현에 대한 검증은 후속 과제로 명시**한다.
> 3. **RG-205의 정답셋 사람 검토(Human Gold Review)는 여전히 미완료 후속 과제**이므로 상위 에픽(RG-204)의 전체 완료로 혼동하지 않는다.
> 4. Antigravity 세션의 CLI panic 및 편집 정체로 독립 QA 결과가 미확보되어, 실제 QA는 Root의 44건 작성 및 Writer의 인벤토리 의미 검토로 수행되었다(Antigravity 완료로 표기 금지).
> 5. 17개 수치 경계 조건은 격리 Candidate 컨테이너의 실제 API에서 검증된 것이며, 공개 TEST에서 17개를 실행한 것이 아니다 (임시 Candidate 컨테이너는 검증 후 Root가 정리 완료함).
> 6. 운영(Production) 배포, 조류 DB 쓰기, Git commit/push는 일체 수행하지 않았다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 배경** | 분류군×형질 질의 일반화 | 실제 TEST 사용자 질의 `"까마귀과면서 열매를 먹는 새는 어떤 종이 있어?"` clarify 실패 지적 수용. '목' 전용(`order_fruit`) 한계를 넘어 5대 활성 계급(목·과·속·종·아종) × 15개 형질 조합 지원 |
| **프레임워크 / 아키텍처** | Django + DRF 서비스층 | Django + Django REST Framework 공통 서비스 레이어 내 질의 해석 파이프라인 확장 (FastAPI 아님). 신규 외부 의존성 없음, DB 스키마 변경 없음 |
| **핵심 코드 수정** | Core 파이프라인 3개 모듈 수정 | 1) `graph_questions.py`: `taxon_traits` 질의 유형 추가, Cypher 쿼리 및 조건 핸들러 구현.<br>2) `graph_condition_extractor.py`: 임의 계급 분류군 스템 추출, `_ROUTED_KINDS` 분기에서 `kind_tie` 판정 격리, `species_profile.LABELS` 괄호형 명칭 정규화.<br>3) `graph_intent_schema.py`: `GraphIntent.conditions` 및 계급 표면 스키마 확장.<br>*(참고: `graph_semantic_router.py`는 해시 `85a36933…` 그대로 무변경)* |
| **UI 및 페이로드 계약** | 기존 렌더러 검증 범위 통과 | `ChatGraphResult.kind='graph_query'`이며, `ChatGraphResult.payload` dict(status, title, text, items, paths, sources, limitations, has_more, taxon, conditions, coverage; ids 없음) 구조 유지, 기존 UI 렌더러(`chat.js`, `buildGraphQueryAnswer`) 무수정으로 Mock UI 4건 + 공개 브라우저 12건 검증 범위 전원 통과 (절대 호환 주장 배제) |
| **형질 지원 및 안전 규칙** | 15개 형질 AND 결합 | 1) AVONET 13개 + EltonTraits 2개 필드 지원.<br>2) 명시적 수치 단위 정규화 (`0.1kg`→`100g`, `10cm`→`100mm`).<br>3) 스키마 허용 `text_values` 외 임의 값 차단.<br>4) **자료 없는 아종에 대한 부모 종 데이터 대체 엄격 금지** (`insufficient_data` 유지) |
| **카탈로그 해소 감사** | Fixture 전수 해소 검사 통과 | `catalog-resolution-audit.json`: 33,684개 전체 학명 해소 통과, 1,201개 한국어 고유 표면 중 13건 의도적 보류 (동명 6건, 명시 접미사 rank 상충 7건). 고정 템플릿 치환 34,891건 0실패 (자연어 정확도 아님 명시) |
| **평가셋 회귀 재검증** | 44건 공개 API 전수 통과 | 최초 44건 중 42건 통과 / 2건 안전 보류(`IT-020`, `IT-023`) → 괄호형 형질 라벨 정규화 수정 후 공개 TEST 실제 API에서 44건 전원 통과 (`independent-api-public.json`). *피드백 노출로 미공개 일반 정확도 아님을 명시* |
| **실제 DB 독립 Oracle 대조** | 131종·587조건 전수 일치 | `candidate-fixed-db-evidence.json`: 반환된 131개 종, 587개 원조건 근거, 32개 질의의 scoped/evaluable/matched 정확 대조 결과 불일치 0건 (`errors: []`) |
| **수치 중복 감사** | 76,776쌍 단일 claim 확인 | `numeric-claim-uniqueness.json`: 실제 DB 수치 76,776개 종·필드 쌍에서 다중 claim 0건 확인 (현재 자료 상 수치 혼용 위험 없음; 미래 자료 보증 아님) |
| **회귀 및 API 검증** | 1,164실행 1,125통과 39skip 0fail | 1) 전체 1,164건 실행 중 1,125 pass, 39 skip, 0 fail (26.816s; 39 skip은 opt-in 통합 및 RG406 재현 자료 번들(`/tmp/rg406-avilist.json`) 부재).<br>2) `tests/test_taxon_traits_api.py`: 신규 HTTP 통합 5건 통과.<br>3) `numeric-boundary-api`: 17/17 pass (격리 Candidate 실제 API 검증).<br>4) 4대 `species_scope` (`all`, `korea`, `outside`, `unknown`) 공개 API 4/4 통과 (`scope-api.json`).<br>5) 레거시 7질문 베이스라인 fingerprint shadow 및 off 모드 동일 (`legacy-api-shadow.json`, `legacy-api-off.json`).<br>6) 기존 40 holdout 기준선 점수 유지 (coverage 18/20, false exec 0/40) |
| **브라우저 검증** | 공개 Chromium 1280px / 390px 12건 | 공개 TEST URL(`https://robingraph-test.dove-nest.com`) 대상 데스크톱 6건, 모바일 6건 통과 (페이지 에러 0건, 스크린샷 12종 확보, 모의 응답 아님) |
| **원격 측정 (Telemetry)** | MLflow 실험 33 저장 및 조회 | `graph_intent.route` 및 `graph_intent.candidates` span shadow 및 active 실제 저장 조회 성공 (`shadow-mlflow.json`, `active-mlflow.json`) |
| **런타임 벤치마크** | 순차 호출 지연 및 리소스 샘플링 | active 모드 동일 질문 순차 호출: cold 2,268.416ms, warm 5회 472.135~549.153ms. 컨테이너 메모리 159.7MiB(2.0%) 관측 (`runtime-benchmark.json`). *소표본 순차 측정이며 부하/최대 용량 시험 아님* |
| **배포 및 환경 상태** | 공개 TEST 배포 완료 | 이미지 `robingraph-api:test-taxonomic-traits-9adf41538e2e`, 릴리스 디렉터리 반영, manifest 196파일 일치, health 정상 (`test-health-verify.json`). 격리 Candidate 컨테이너는 정리 완료 |
| **거버넌스 및 안전 경계** | 무영향 원칙 준수 | Production 배포 0건, 조류 DB 쓰기 0건, Git commit/push 0건. RG-208 수정 검증 범위 완료, RG-204 진행 중(사람 검토 대기) 유지 |

---

## 1. 작업 배경 및 문제 분석

### 1) 발생 현상 및 한계 지적
- **사용자 실질 질의 실패**:
  - 실제 TEST 환경에서 사용자 질의 `"까마귀과면서 열매를 먹는 새는 어떤 종이 있어?"` 입력 시, 의도된 조류 종 목록 대신 모호성 보류(`clarify`) 응답이 반환됨.
- **원인 분석**:
  - 이전 베이스라인 파이프라인은 고정 7개 질의 유형 중 '목' 계급 한정 열매 질의인 `order_fruit`에 맞춰 추출·스키마·조회 제약이 설계되어 있었음.
  - 과(`Corvidae`, 까마귀과), 속(`Corvus`, 까마귀속) 등 다른 계급이나, 서식지·생활방식·형태학적 수치 치수(체중, 부리, 날개 등)가 결합된 질문을 처리할 수 있는 파이프라인 경로와 조건 스키마가 부재하여 미지원 상태로 남아 있었음. (코드의 억지 매핑이나 `rank_not_order` 차단에 대한 실제 로그 증거는 없으며, 목 전용 구조적 한계로 인한 미지원이 정확한 원인임)
- **요구사항 확장**:
  - "모든 분류군에 해야지/먹이에 대해서만 진행할 거야?"라는 명확한 방향성에 따라, 특정 목에 국한되지 않는 **활성 5대 계급(목·과·속·종·아종) × 근거 있는 15개 형질 차원의 일반화된 질의 해석 체계**로 확장하기로 확정함.
  - *(참고: 실제 DB에 등록된 활성 계급은 목 46, 과 252, 속 2,376, 종 11,131, 아종 19,879개로 총 33,684개 분류군이며, 강(class) 노드는 0건이고 코드 상 지원하지 않음)*

---

## 2. 해결 방안 및 아키텍처 설계

### 1) 신규 질의 유형 `taxon_traits` 도입
- 기존 레거시 7개 유형을 파괴하지 않고 독립적인 일반화 유형 `taxon_traits`를 신설:
  - 계급 제약 완화: `order`, `family`, `genus`, `species`, `subspecies` 5대 활성 계급 수용.
  - 다중 조건 결합: `AND` 논리 조건으로 서식 환경, 먹이 범주, 수치 치수 등을 유연하게 결합.
  - 순수 형질 질의 수용: 분류군 제약 없이 조류 전체를 대상으로 하는 질의(`taxon: None`, 예: `"숲에 살고 열매를 먹는 새는?"`)도 지원.

### 2) 엄격한 생물학 데이터 안전 경계
- **자료 없는 아종 부모 대체 엄격 금지**:
  - `trait-inventory.json` 상 모든 AVONET/EltonTraits 형질은 종(`rank: "species"`) 수준에서만 수집되어 있음.
  - 아종(`subspecies`)에 대한 형질 필터링 질의 시, 부모 종의 형질을 몰래 끌어와 마치 아종의 형질인 것처럼 조작하여 반환하지 않고, 정확하게 자료 부족(`insufficient_data`)을 반환하도록 강제.
- **수치형 단위 명시적 정규화**:
  - AVONET 기준 단위: 체중은 `g`, 길이 치수(부리, 날개, 꼬리, 발척)는 `mm`.
  - 사용자가 `0.1kg` 입력 시 `100g`으로, `10cm` 입력 시 `100mm`로 명시적 변환 규칙을 적용하여 DB 조건과 일치시킴.
- **미지원 식물/부정/모호 표현 방어**:
  - 특정 식물 종(`감나무 열매` 등)은 카탈로그 미지원으로 `insufficient_data` 처리.
  - 부정 조건(`살지 않는`), 시간/계절(`겨울에만`), 주관적 형용사(`몸집이 큰`), 단위 누락(`체중 100 이상`)은 섣부른 오실행 대신 `clarify` 보류 처리.

### 3) 라우터 간섭 차단
- 7개 기존 유형 임베딩 프로토타입 후보가 신규 `taxon_traits`의 규칙 기반 해석을 왜곡하거나 부당하게 보류시키지 않도록, `graph_condition_extractor.py`의 `_ROUTED_KINDS` 분기에서 `kind_tie` 판정을 모델링된 기존 7개 유형에만 한정하도록 격리함.
- `graph_semantic_router.py` 자체는 해시 `85a36933…` 그대로 무변경 상태를 유지함.

---

## 3. 주요 수정 및 구현 내용

### 1) 수정 및 추가 파일 목록
- `src/robingraph/retrieval/graph_questions.py` (`21315a10…`):
  - 신규 `taxon_traits` 유형 핸들러, `TraitCondition`, 허용 조건 목록(`TRAIT_CONDITIONS`), Cypher 쿼리 템플릿(`TAXON_BY_NAME_QUERY`, `TAXON_TRAITS_QUERY`, `CATALOG_TRAITS_QUERY`) 및 엄격한 유효성 검증 로직 구현.
- `src/robingraph/retrieval/graph_condition_extractor.py` (`0f6af2fa…`):
  - 5대 계급의 분류군 스템 추출 로직(`_claim_taxon`), `_ROUTED_KINDS` 기반 라우팅 격리, `species_profile.LABELS` 기반 괄호형 명칭(`X (Y)`, `X Y`, `X(Y)`) 일반 정규화 구현.
- `src/robingraph/retrieval/graph_intent_schema.py` (`dd949e3a…`):
  - `GraphIntent.conditions` 필드 추가, `KIND_FAMILIES` 확장, `bad_taxon` 표면 처리.
- `tests/test_taxon_traits.py` (`580f38c5…`):
  - 신규 계급별·형질별·단위별 단위 테스트 37건 전수 작성 및 통과.
- `tests/test_taxon_traits_api.py`:
  - 신규 HTTP 라우팅 및 조건 보존 통합 테스트 5건 전수 작성 및 통과.

### 2) UI 렌더러 호환성 검증
- 백엔드 결과는 `ChatGraphResult.kind = 'graph_query'`이며, `ChatGraphResult.payload`는 `status`, `title`, `text`, `items`, `paths`, `sources`, `limitations`, `has_more`, `taxon`, `conditions`, `coverage` 등의 딕셔너리 포맷(ids 없음)을 유지함.
- 프런트엔드(`src/robingraph/api/static/chat.js`)의 `buildGraphQueryAnswer`는 새로운 UI 컴포넌트 추가나 스키마 수정 없이 신규 `taxon_traits` 응답을 처리할 수 있음을 **Mock UI 테스트 4건 및 공개 브라우저 12건 검증 범위 내에서 확인**함 (절대적 100% 호환 주장 배제).

---

## 4. 검증 및 테스트 결과

### 1) 단위 / 회귀 자동화 테스트
- **전체 파이썬 테스트 스위트** (`full-python.log`):
  - 실행 명령어: `PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests`
  - 결과: **1,164 실행 중 1,125 통과, 39 skip, 0 fail (26.816s)**
  - *건너뜀(39건) 사유*: opt-in 통합 검증 및 RG406 재현 자료 번들(`/tmp/rg406-avilist.json`) 부재 테스트로, 의도된 skip 상태 유지.
- **HTTP 라우팅 통합 테스트** (`tests/test_taxon_traits_api.py`):
  - 5건 신규 HTTP 통합 테스트 전수 통과 (계급별 미확장 도달, 복합 조건/4대 scope 보존, 미지원 수식어/오형식 수치 Cypher 도달 차단, 아종 자료 부족 시 부모 대체 배제, 명시 라우트/충돌 프로필 필터 권위 유지).
- **수치 경계 조건 API 테스트** (`numeric-boundary-api.json`):
  - 17개 경계 조건(0.1kg 정규화, 10cm 정규화, 극단값 공집합 등) **격리 Candidate 실제 API에서 17/17 전수 통과** (공개 TEST 실행이 아님).
- **기존 40 홀드아웃 고정 평가** (`legacy-holdout-extractor.json`):
  - 커버리지: `18/20` (90.0%)
  - 오실행(`false_execution`): `0/40` (0.0%)
  - 조건 유실 실행(`condition_loss_executed`): `0건`
  - 적정 보류(`appropriate_hold`): `20/20` (100.0%)
  - 기존 평가 기준선 완벽 보존 확인.

### 2) 카탈로그 전수 파싱 및 Fixture 해소 감사
- **카탈로그 표면 치환 검사** (`catalog-fruit/habitat-parse-audit.json`):
  - DB 등록 전체 이름 34,891건을 고정 템플릿에 치환하여 파싱 감사 수행: **실패 0건 (성공률 100%)**.
  - *(주의: 고정 템플릿 추출 검사이며, 실 DB 전수 실행이나 자연어 정확도가 아님)*
- **실제 Exported DB Fixture 해소 검사** (`catalog-resolution-audit.json`):
  - 33,684개 전체 학명 해소 통과.
  - 1,201개 한국어 고유 표면 중 **13개 표면 의도적 보류 확인**:
    - 동명(계급 모호성) 6건: `오스트레일리아동고비류`, `초승달가슴새류`, `열대새`, `나팔새류`, `레아`, `화식조`.
    - 명시 접미사 rank 상충 7건: `물까마귀과`, `팔색조속`, `사다새과`, `군함조과`, `카구속`, `장다리물떼새과`, `논병아리목`.
- **수치형 Claim 단일성 감사** (`numeric-claim-uniqueness.json`):
  - 실제 TEST DB의 76,776개 종·형질 수치 쌍 전수 확인: 쌍당 최대 claim 1개, 다중 claim 0건. 현재 자료 상 측정치 혼용 위험이 없음을 입증 (미래 자료 보증 아님).

### 3) 독립 44건 평가 및 실제 DB Oracle 대조
- **독립 44건 평가 진행 경과**:
  - Root가 구현 코드 열람 전 작성한 독립 평가 데이터(`independent-cases.json`, 44건) 최초 실행: 42건 통과 / 2건 안전 보류(`IT-020` 콧구멍 기준 부리 길이, `IT-023` 부척 다리 길이).
  - Claude의 괄호형 명칭 일반 정규화 수정 후 공개 TEST 배포 API 재검증: **44/44 전원 통과** (`independent-api-public.json`).
  - **평가 성격 고지**: 44건 사례가 수정 피드백으로 사용되었으므로, 본 44건 통과는 '피드백 반영 회귀 검증 통과'이며 '미공개 일반 정확도'가 아님.
- **실제 DB 독립 Oracle 대조** (`candidate-fixed-db-evidence.json`):
  - 실제 DB 직접 조회 기반 검증: 반환된 고유 종 131개, 검증된 조건 근거 587개.
  - 32개 질의의 `scoped`, `evaluable`, `matched` 수치 정확 대조: **불일치 0건 (`errors: []`, `passed: true`)**.
  - 극단값 공집합(IT-033) 검증: 까마귀과(`Corvidae`) 범위 내에서 체중 1,000,000g 이상을 만족하는 종이 0건임을 확인 (전체 AVONET 전무로의 확대 해석 배제).
  - 조류 DB 쓰기: **0건**.

### 4) 공개 TEST 브라우저 렌더링 검증 (`browser-public.json`)
- 공개 TEST URL(`https://robingraph-test.dove-nest.com`) 대상 실제 Playwright Chromium 구동 (모의 응답 아님):
  - 데스크톱(1280px) 6건, 모바일(390px) 6건 총 12건 전수 통과:
    1. `original` ("까마귀과면서 열매를 먹는 새는 어떤 종이 있어?"): 정상 답변 (20개 항목 표시).
    2. `composite` ("까마귀과 중 숲에 살고 열매를 먹는 새는?"): 정상 답변 (20개 항목 표시).
    3. `measure` ("까마귀과 중 부리 길이 콧구멍 기준이 5mm 이상인 새는?"): 정상 답변 (20개 항목 표시).
    4. `subspecies` ("Corvus corone corone 중 숲에 사는 새는?"): 정직한 자료 부족(`abstain`/`insufficient_data`, 0개 항목).
    5. `negation` ("까마귀과 중 숲에 살지 않는 새는?"): 안전한 명료화 요구(`clarify`, 0개 항목).
    6. `label-conflict` ("물까마귀과 중 숲에 사는 새는?"): 계급 상충 보류(`abstain`, 0개 항목).
  - 콘솔 및 페이지 에러: **0건**, 스크린샷 12종(`public-*.png`) 증거 확보 완료.

### 5) 런타임 벤치마크 및 원격 관측 (`runtime-benchmark.json`, `active-mlflow.json`)
- **지연시간 및 리소스 샘플링**:
  - 공개 TEST active 모드 동일 질문 순차 호출: cold 2,268.416ms, warm 5회 472.135~549.153ms (평균 ~502ms).
  - 컨테이너 메모리 159.7MiB(2.0%), CPU 0.17~30.6%로 총 4개 표본(3개 중간 + 1개 최종 스냅샷) 관측 (안정화나 최대 보장이 아닌 소표본 관측치임).
  - *(주의: 소표본 순차 측정이며 부하/최대 용량 시험이 아님)*
- **MLflow 관측성**:
  - 외부 원격 MLflow 실험 33에 `graph_intent.route` 및 `graph_intent.candidates` span이 shadow 및 active 모드 모두 정상 저장 및 조회됨을 확인.

---

## 5. 배포 및 환경 상태

- **공개 TEST 환경**:
  - 대상: `robingraph-api-test` (16GB Mac mini .97)
  - 배포 이미지: `robingraph-api:test-taxonomic-traits-9adf41538e2e`
  - 릴리스 경로: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-9adf41538e2e-670f2a`
  - 소스 해시 일치: `9adf41538e2ee7b5…` (196개 파일 런타임 매니페스트 일치 확인)
  - 모드 전환 라이프사이클: `shadow` -> `active` -> `off` -> `active` 전수 검증 완료
  - 헬스체크: `/health`, `/openapi.json`, `/v1/taxa/lineage` 정상 통과 (`test-health-verify.json`)
- **격리 Candidate 컨테이너**: 검증 완료 후 Root가 정상 정리 완료.
- **운영(Production) 배포**: **0건 (일체 미반영, 명시 승인 전 실행 금지)**.
- **Git 상태**: **commit / push 0건**.

---

## 6. 한계 및 후속 과제

1. **자연어 표현 다양성 한계**:
   - 정의된 `species_profile.LABELS` 어휘를 벗어난 임의의 구어체 자연어 표현은 오실행 방지를 위해 명료화(`clarify`)로 보류됨.
   - 본 수정 검증 완료가 모든 자연어 지원 완료를 의미하지 않으며, 더 넓은 어휘 및 표현에 대한 검증은 후속 과제로 지속 수행해야 함.
2. **미지원 조건 보류 유지**:
   - 계절성 조건(`겨울에만`), 부정 조건(`살지 않는`), 모호한 수치 표현(`몸집이 큰`), 미지원 식물 세부 종은 안전 보류 처리됨.
3. **상위 에픽 및 사람 검토 미완료**:
   - **RG-205 사람 검토(Human Gold Review)는 미완료 상태**이며, 본 RG-208 수정 검증을 완료하더라도 상위 에픽(RG-204) 전체 완료로 간주하지 않음.
4. **후속 예정 작업**:
   - Graphify AST 갱신 완료 확인 (`graphify.log`).
   - RG-205 사람 검토 골드셋 확정 및 장기 벤치마크 평가.

---

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG208-통합-관측-TEST-비교-단계적-전환|RG-208 이전 베이스라인 배포 기록]]
- [[docs/verification/assets/2026-10-22-taxonomic-trait-generalization/independent-meaning-review.md|독립 44건 의미 검토 보고서]]

---
*문서 작성 일시: 2026-10-22*  
*작성자: dev / Writer (dev-codex 최종 배포 증거 기반 최종화)*
