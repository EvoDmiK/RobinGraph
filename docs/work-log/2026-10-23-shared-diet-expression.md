---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: RG-211
tags:
  - worklog
  - robingraph
  - bugfix
  - species-questions
  - trophic-niche
  - ecological-related
---

# [RG-211 / 검색·질의해석] 먹이 생태 공유 어순 및 동의 표현 지원: 까치와 같은 먹이 생태를 가진 새 질문 해석 개선 — 2026-10-23

> **문서 상태: 검증 완료 (사용자 제보 "까치랑 같은 먹이 생태를 가진 새를 알려줘" clarify 오분류 수정 완료; Claude 백엔드 최소 확장 및 Codex 통합·검증; Python 102/102 단위 테스트 통과; 실제 TEST 배포 및 24건 live API 24/24 통과, Playwright 4개 브라우저 반응형 시나리오 전원 통과; 원본 496 데이터셋 불변, 조류 DB 쓰기 0건, 운영 미배포, Git commit/push 없음)**  
> 2026-10-23 사용자 모바일 화면에서 `"까치랑 같은 먹이 생태를 가진 새를 알려줘"` 질의 시 `"조회할 새 이름을 하나 명확히 입력하고, 질문과 필터의 이름을 맞춰 주세요."`라는 clarify 응답이 반환되는 버그가 제보되었다.  
> 원인 분석 결과 `src/robingraph/retrieval/species_questions.py`의 `ecological_related` / `trophic_niche` 정규식 패턴이 `<종명>와 <먹이>가 비슷한 새` 형태의 정방향 어순만 지원하고, `<종명>와 같은 <먹이 생태>를 가진 새` 형태의 역방향 어순 및 확장 어휘(`먹이 생태 범주`, `먹이 범주`, `먹이 습성`)를 지원하지 못해 단일 종 프로필 JEV 규칙으로 폴백되어 clarify가 반환된 것으로 확인되었다.  
> **아키텍처 현실 및 한계 명확화**: 사용자가 기대한 "자연어 질의의 벡터 자동 노드 연결"과 달리, 실제 코드(`src/robingraph/cli.py` `graph_intent_handler`)에서는 어휘 분석 결과가 `not_graph`일 경우 `execution_gate`에서 즉시 차단되어 **임베딩 호출 0건(`embedding_calls: 0`)**으로 조기 반환된다 ([lexical-diagnostic.json](../verification/assets/2026-10-23-shared-diet-expression/lexical-diagnostic.json)). 또한 `graph_semantic_router`는 45개 정적 예시(7개 유형) 대상 nearest-prototype 후보 분류기일 뿐 종/조건을 추출하거나 질문을 영구 노드로 연결하는 시스템이 아니다.  
> 따라서 본 수정은 **당장 제보된 스크린샷 오류를 복구하기 위한 2개 파일 표면 어휘·어순 매핑 패치**이며, 전체적인 semantic generalization이 완료된 것이 아님을 명시한다.  
> 본 작업은 신규 `graphkind` 정의나 신규 조류 DB 쓰기가 일체 없으며(`bird_db_writes: 0`), "같은 먹이 생태"는 **AVONET 대표 먹이 생태 범주(`trophic_niche`)**를 공유한다는 의미임을 보존한다 (EltonTraits `diet_5cat` 공유 아님). 기존 canonical baseline과 동일하게 까치(`Pica serica`)는 그래프 내 직접 `trophic_niche` 출처 자료가 부재하므로 억지 목록을 생성하지 않고 정직하게 `abstain`을 유지하며, 자료가 존재하는 직박구리·청둥오리·왜가리는 정상 `answer`를 반환함을 실사 확인하였다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **문제 제보 및 baseline** | 먹이 생태 공유 어순 미지원에 따른 clarify 오류 | 사용자 질의 `"까치랑 같은 먹이 생태를 가진 새를 알려줘"` clarify 발생.<br>사전 공개 TEST baseline 3건([before.json](../verification/assets/2026-10-23-shared-diet-expression/before.json)) 확인: 어순 미지원 1건 clarify, 의미 해석 실패 1건 clarify, 서식지 결합 1건 abstain (`insufficient_data`) |
| **원인 규명 및 아키텍처 현실** | `species_questions.py` 어순 한계 및 벡터 진입 전 차단 | 1) `species_questions.py`가 `<NAME>와 같은 <먹이>를 가진 새` 어순 및 `먹이 범주/습성` 미지원<br>2) **벡터 검색 미진입 현실**: `cli.py` `graph_intent_handler`에서 어휘 추출 결과 `not_graph` 시 `execution_gate`에 의해 **임베딩 호출 0건**으로 종료됨 확인 ([lexical-diagnostic.json](../verification/assets/2026-10-23-shared-diet-expression/lexical-diagnostic.json))<br>3) `graph_semantic_router`는 45예시 7유형 프로토타입 후보 분류기일 뿐 영구 노드 연결 아님<br>4) **수정 범위 한정**: 당장 스크린샷 오류 복구 패치이며 semantic generalization 완결 아님 |
| **설계 원칙 및 가드레일** | 데이터 의미 보존 및 서식지 조건 보호 | 1) **신규 graphkind / DB 변경 없음**: 기존 `trophic_niche` 관계와 AVONET 자료 범주 재사용 (`bird_db_writes: 0`, EltonTraits diet_5cat 아님)<br>2) **자료 범주 의미 명시**: 동일 개별 먹이 섭식이나 먹이 경쟁이 아니라 AVONET 대표 먹이 생태 범주(`trophic_niche`) 공유 의미임을 보존<br>3) **서식지 조건 암묵 누락 금지**: `"숲에 사는 새 중 까치와..."`처럼 서식지 구문 선행 결합 시 `_PLACE_TOKEN` 가드로 종명 오인식을 차단하여 서식지 조건 누락 방어 (기존 `graph_query` 경로 정상 보존)<br>4) **자료 부재 시 억지 목록 금지**: 까치는 그래프 내 직접 `trophic_niche` 근거 자료가 없으므로 `abstain` 유지 (canonical baseline과 일치, 직박구리/청둥오리/왜가리는 정상 `answer`) |
| **코드 수정 (Claude/Codex)** | 최소 확장 (앱 1개, 테스트 1개 파일) | 1) `src/robingraph/retrieval/species_questions.py`: `_DIET_WORD`에 `먹이 생태 범주`, `먹이 범주`, `먹이 습성` 추가 및 역어순 패턴 신설, `_PLACE_TOKEN` 가드 추가<br>2) `tests/test_species_questions.py`: Claude 파서 단위 테스트 2건 + Codex active API 모의 테스트 1건 추가<br>3) `graph_intent_schema`, `graph_semantic_router`, `api/services.py`, 조류 DB 쿼리는 일체 변경 없음 |
| **단위 테스트 검증** | Python 포커스 스위트 전원 통과 | `PYTHONPATH=tests uv run --locked --extra test python -m unittest tests.test_species_questions tests.test_ecological_relations tests.test_taxon_traits tests.test_taxon_traits_api tests.test_graph_condition_extractor tests.test_graph_semantic_api` ➔ **102 / 102 통과 (1.293s)** ([focused-python.log](../verification/assets/2026-10-23-shared-diet-expression/focused-python.log)) |
| **TEST 배포 및 게이트** | 점진적 컨테이너 배포 및 게이트 통과 | snapshot 이미지 `robingraph-api:test-taxonomic-traits-6a5ab77e8b13` 빌드 ➔ shadow 모드 레거시 대조 ➔ active 전환 ([activation-gates.json](../verification/assets/2026-10-23-shared-diet-expression/activation-gates.json): `all_passed: true`, `python_tests: 102`, `fixture_network_none_smoke: true`). 릴리스 207개 해시 일치, 컨테이너 114개 불일치 0건 ([final-state.json](../verification/assets/2026-10-23-shared-diet-expression/final-state.json)) |
| **live TEST API 검증** | 24건 HTTP / 24개 논리 검증 통과 | **24 / 24 (100%) 통과** ([after.json](../verification/assets/2026-10-23-shared-diet-expression/after.json)):<br>- 4건 canonical baseline 일치 (까치 abstain, 직박구리/청둥오리/왜가리 answer)<br>- 12건 새 표현 동등성 100% 일치 (4종 × 3개 동의/어순)<br>- 6건 추가 조건 보존 및 미지원 보류 (clarify 5건 + graph_query 조건 보존 1건)<br>- 2건 기존 먹이 표시명 회귀 검증 (곤충 98, 고기 68)<br>- 하네스 보정: 초기 검사기가 서식지 결합 질의에 clarify를 강제했던 오류를 수정하고 동일 24개 응답 재검증으로 24/24 통과 확인 ([after-first-check.json](../verification/assets/2026-10-23-shared-diet-expression/after-first-check.json) 보존, 앱 실패 아님) |
| **브라우저 QA (Playwright)** | 뷰포트 반응형 실사 4건 전원 통과 | Chromium 390px, 1280px 각 2건(총 4건) 실사 통과 ([browser.json](../verification/assets/2026-10-23-shared-diet-expression/browser.json)): 까치 `abstain`, 직박구리 `answer`, `page_errors: []`, `overflow: false`, `response_mocking: false`. 스크린샷 4건 확보 (`physical_mobile: false`) |
| **코드 지식 그래프 동기화** | AST 지식 그래프 최신화 완료 | 7,940 노드, 17,103 엣지, 454 커뮤니티 graphify 갱신 완료 ([graphify.log](../verification/assets/2026-10-23-shared-diet-expression/graphify.log)) |
| **거버넌스 및 브랜치** | 무영향 원칙 준수 및 역할 분담 | 앱 통합 브랜치: `dev-codex`, 문서 작성 브랜치: `dev` (`main-2`). 운영(Production NAS) 미배포, 조류 DB 쓰기 0건 (`bird_db_writes: 0`), Git commit/push 없음 |

---

## 1. 작업 배경 및 문제 분석

### 1) 발생 현상 및 사용자 제보
- **제보 화면**: 사용자 모바일 질의 `"까치랑 같은 먹이 생태를 가진 새를 알려줘"`
- **반환 응답**:
  ```text
  selected_intent: profile
  route_method: jev
  disposition: clarify
  answer_text: "조회할 새 이름을 하나 명확히 입력하고, 질문과 필터의 이름을 맞춰 주세요."
  warnings: ["종 이름을 임의로 추정하지 않았습니다."]
  ```
- **문제점**: 사용자는 기준 종('까치')과 생태적 관계('먹이 생태가 같은 새')를 명시하였으나, 질의 파서가 어순을 해석하지 못하고 단일 종 프로필 조회용 JEV 어미 규칙으로 폴백되어 종 이름 불명확 clarify를 반환함.

### 2) 사전 live TEST baseline 실측 (`before.json`)
공개 TEST 환경(`https://robingraph-test.dove-nest.com/v1/chat`) 대상 사전 질의 3건 실측 결과 ([before.json](../verification/assets/2026-10-23-shared-diet-expression/before.json)):
1. `"까치랑 같은 먹이 생태를 가진 새를 알려줘"` ➔ `route_method: jev` ➔ `disposition: clarify` ("조회할 새 이름을 하나 명확히 입력...")
2. `"까치와 같은 먹이 범주를 공유하는 새는?"` ➔ `route_method: semantic` ➔ `disposition: clarify` ("질문의 조건을 모두 확인하지 못했습니다...")
3. `"숲에 사는 새 중 까치와 같은 먹이 범주를 공유하는 새는?"` ➔ `route_method: semantic` ➔ `disposition: abstain` (`status: insufficient_data`, "까치의 서식 환경 또는 먹이 생태 범주 자료가 없습니다.")

### 3) 시스템 아키텍처 현실 및 벡터 검색 진입 한계 (User Steering 반영)
- **사용자 피드백 의문**: *"질문들도 벡터로 연결되어 있다고 들었는데 왜 어순 변경만으로 clarify가 발생하는가?"*
- **코드 직접 확인 (`src/robingraph/cli.py` `graph_intent_handler`)**:
  ```python
  def graph_intent_handler(question):
      with tracing.span("graph_intent.candidates", tracing.CHAIN) as candidate_span:
          lexical = extract_graph_intent(question)
          if execution_gate(question, lexical) == "not_graph":
              candidate_span.set_attributes({"graph_intent.status": "not_graph",
                                             "graph_intent.embedding_calls": 0,
                                             "graph_intent.prototype_calls": 0})
              return lexical
          candidates = graph_router.classify(question) if graph_router is not None else ()
  ```
- **발견된 시스템 현실 ([lexical-diagnostic.json](../verification/assets/2026-10-23-shared-diet-expression/lexical-diagnostic.json))**:
  1. 질의 인입 시 어휘적 추출기(`extract_graph_intent`)가 먼저 실행되며, 해당 질의는 그래프 고유 조건에 매칭되지 않아 `not_graph` (`kind=None`, `species=[]`, `residual=[]`)를 반환함.
  2. `execution_gate == "not_graph"` 판정에 의해 즉시 조기 반환되며, **임베딩 호출은 0건(`embedding_calls: 0`)**으로 벡터 검색 경로에 진입조차 하지 않음. (참고: `lexical-diagnostic.json`은 로컬 추출기 출력 및 CLI 코드 경로 확인 근거이며 운영 trace가 아님).
  3. `graph_semantic_router`는 45개 정적 문항 예시(7개 고정 유형)에 대한 nearest-prototype 후보 추천기일 뿐, 종이나 조건을 추출하지 않으며 사용자 질문을 그래프 내에 영구 벡터 노드로 자동 연결하는 구현이 아님.
- **수정 범위의 한계 명시**:
  - 이번 2개 파일(`species_questions.py`, `tests/test_species_questions.py`) 수정은 **당장 스크린샷 오류를 복구하기 위한 어휘·어순 매핑 패치**이며, 임의의 자연어를 자율 해석하는 semantic generalization이 완료된 것이 아님.

---

## 2. 해결 방안 및 설계 원칙

### 1) 최소 침습 정규식 확장
- 기존 `ecological_related` / `trophic_niche` 패턴 구조를 유지하면서 역방향 어순 패턴 1개를 추가하고, `_DIET_WORD` 정규식에 누락된 동의 어휘를 통합:
  ```python
  _DIET_WORD = r'(?:먹이\s*생태\s*범주|먹이\s*생태|먹이\s*범주|먹이\s*습성|먹이|식성)'
  ```

### 2) 서식지 조건 암묵 누락 방지 가드 (`_PLACE_TOKEN`)
- 질문 시작 부분에 `"숲에 사는"`, `"산에서 살고"` 등의 장소·서식지 수식어가 결합된 경우, 이를 단순 단일 종의 생태 관계 질문으로 파싱하여 서식지 조건을 탈락시키는 일을 엄격히 차단:
  ```python
  _PLACE_TOKEN = re.compile(r'(?:에|에서)$|^(?:사는|살고|서식하는)$')
  ...
  if topic == 'ecological_related' and any(_PLACE_TOKEN.search(t) for t in name.split()[:-1]):
      return None
  ```
- 서식지 조건이 결합된 질문은 기존에 구축되어 있는 `graph_query` 경로로 정상 진입하여 서식지와 먹이 생태 범주 조건을 함께 평가함 (신규 파이프라인 구축 불필요).

### 3) 생물학적 자료 의미 가드레일 및 자료 부재 수용
- **AVONET 대표 먹이 생태 범주(`trophic_niche`) 의미 보존**:
  - `trophic_niche` 관계는 **AVONET 대표 먹이 생태 범주**를 공유한다는 의미이며, 특정 단일 먹이를 놓고 다투는 '먹이 경쟁'이나 '동일 개별 먹이 섭식' 관계가 아님을 보존 (EltonTraits `diet_5cat` 공유가 아님).
- **까치의 직접 `trophic_niche` 근거 부재 vs 전체 먹이 자료 부재 구분**:
  - 까치(`Pica serica`)는 프로필 보충 자료나 개별 섭식 기록은 존재할 수 있으나, 그래프 내에 직접 검증된 **`trophic_niche` 출처 자료가 부재**함.
  - 시스템은 엄격한 분류학적 무결성을 준수하므로 `Pica serica`를 `Pica pica`로 대체하거나 상위 분류군(까마귀과)에서 임의로 형질을 추정·상속하지 않음.
  - 따라서 까치 질의 시 억지로 가짜 조류 목록을 생성하지 않고 정직하게 `abstain`을 반환하는 것이 시스템의 올바른 정합성 동작임.
- **응답 구조 규격 구분**:
  - 단일 프로필 생태 질문: `disposition: "abstain"`, `result.kind: "profile"`, `result.question_answer` 형태를 반환함 (`result.payload.status: "insufficient_data"`가 아님).
  - 서식지 결합 그래프 질문: `result.kind: "graph_query"`, `result.payload.status: "insufficient_data"` 형태를 반환함.

---

## 3. 주요 구현 내용

### 1) 수정 파일 목록 (총 2개 파일)
* [src/robingraph/retrieval/species_questions.py](src/robingraph/retrieval/species_questions.py) — 먹이 동의 어휘 확장, 역어순 패턴 추가, 서식지 수식어 가드(`_PLACE_TOKEN`) 추가
* [tests/test_species_questions.py](tests/test_species_questions.py) — Claude 파서 단위 테스트 2건 + Codex active API 모의 테스트 1건 추가
*(참고: `display_name` 폴백은 이전부터 존재하던 기존 로직이며 이번 변경사항이 아님. `graph_intent_schema`, `graph_semantic_router`, `api/services.py`, 조류 DB 쿼리 등 기타 모듈은 일체 수정하지 않음).*

### 2) 핵심 코드 스니펫
```python
# src/robingraph/retrieval/species_questions.py

_DIET_WORD = r'(?:먹이\s*생태\s*범주|먹이\s*생태|먹이\s*범주|먹이\s*습성|먹이|식성)'
_PLACE_TOKEN = re.compile(r'(?:에|에서)$|^(?:사는|살고|서식하는)$')

_PATTERNS = (
    # 기존 정방향: 까치와 먹이 생태가 같은 새
    ('ecological_related', 'trophic_niche', rf'{_NAME}(?:와|과|랑|하고)\s*{_DIET_WORD}(?:가|이)?\s*(?:비슷한|같은|동일한)\s*(?:새|종)(?:들)?(?:을|를|는|은|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    # 신규 역방향: 까치와 같은 먹이 생태를 가진 새
    ('ecological_related', 'trophic_niche', rf'{_NAME}(?:와|과|랑|하고)\s*같은\s*{_DIET_WORD}(?:의|(?:를|을)?\s*(?:가진|지닌|갖는|공유하는))?\s*(?:새|종)(?:들)?(?:을|를|는|은|이|가)?\s*(?:(?:어떤\s*(?:게|것|종|새)(?:가)?\s*)?(?:있니|있어(?:요)?|있나요)|{_ASK})?'),
    ...
)

def parse_species_question(question):
    ...
    if topic == 'ecological_related' and any(_PLACE_TOKEN.search(t) for t in name.split()[:-1]):
        return None  # 서식지 구문이 종명에 포함된 경우 단일 종 질의 매칭 차단 (graph_query 경로로 위임)
    ...
```

---

## 4. 검증 및 테스트 결과

### 1) Python 단위 테스트 검증
- **실행 명령**:
  ```bash
  PYTHONPATH=tests uv run --locked --extra test python -m unittest \
    tests.test_species_questions \
    tests.test_ecological_relations \
    tests.test_taxon_traits \
    tests.test_taxon_traits_api \
    tests.test_graph_condition_extractor \
    tests.test_graph_semantic_api
  ```
- **검증 결과**: `Ran 102 tests in 1.293s — OK` ([focused-python.log](../verification/assets/2026-10-23-shared-diet-expression/focused-python.log))
- **검증 내용**:
  - `test_same_diet_paraphrases_reuse_the_trophic_niche_relation`: 까치, 직박구리, 흰뺨검둥오리 대상 10개 자연어 질의가 정확히 `('종명', 'ecological_related', 'trophic_niche')`로 파싱됨 확인.
  - `test_same_food_competition_habitat_and_negation_are_not_a_shared_category`: 먹이 경쟁(3건), 서식지 결합(4건), 부정 질의(1건) 등 8건이 단일 생태 관계로 오분류되지 않고 `None`을 반환하는지 가드 검증.
  - `test_shared_diet_paraphrases_keep_active_route_and_source_category`: active 모드에서 왜가리 질의가 임베딩/그래프 해석을 우회하여 `trophic_niche` 단일 경로로 처리됨을 모의 검증.

### 2) TEST 컨테이너 점진적 배포
- **대상 컨테이너**: `robingraph-api-test` (ARM64 Mac .97 TEST 환경)
- **배포 이미지**: `robingraph-api:test-taxonomic-traits-6a5ab77e8b13`
- **소스 SHA-256**: `6a5ab77e8b139cc85022532e3d6e23de33acd06f11b73ce1e6d73f2b668a59c9`
- **릴리스 디렉터리**: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-6a5ab77e8b13-87de05`
- **게이트 통과**: `deploy-shadow` ➔ `legacy-api-shadow.json` 대조 ➔ `activation-gates.json` 통과 (`all_passed: true`, `python_tests: 102`, `fixture_network_none_smoke: true`, `production_changed: false`).
- **최종 상태 실측 ([final-state.json](../verification/assets/2026-10-23-shared-diet-expression/final-state.json))**:
  - `target: "test"`, `image: "robingraph-api:test-taxonomic-traits-6a5ab77e8b13"`, `health: "healthy"`, `graph_intent_mode: "active"`
  - release source snapshot 207개 파일 해시 일치, 컨테이너 내부 소스 실측 114개 파일 불일치 0건 (`container_source: {checked_files: 114, mismatches: []}`).

### 3) live TEST API 24건 전수 회귀 검증 ([after.json](../verification/assets/2026-10-23-shared-diet-expression/after.json))
실제 공개 TEST API(`https://robingraph-test.dove-nest.com/v1/chat`) 대상 24건 HTTP 요청 및 24개 논리 검증 결과:
- **결과**: **24 / 24 통과 (100% 합격)**
- **4건 Canonical baseline 대조 ([canonical-before.json](../verification/assets/2026-10-23-shared-diet-expression/canonical-before.json))**:
  - `"까치와 먹이 생태가 같은 새는?"` ➔ `disposition: abstain` (까치의 생태가 비슷한 종 자료 부재)
  - `"직박구리와 먹이 생태가 같은 새는?"` ➔ `disposition: answer` (열매 섭식: 검은뻐꾸기 등)
  - `"청둥오리와 먹이 생태가 같은 새는?"` ➔ `disposition: answer` (수생 초식: 가창오리 등)
  - `"왜가리와 먹이 생태가 같은 새는?"` ➔ `disposition: answer` (수생동물 포식: 가마우지 등)
- **12건 신규 표현 동등성 검증 (4종 × 3개 동의/어순)**:
  - `<종명>랑 같은 먹이 생태를 가진 새를 알려줘`, `<종명>와 같은 먹이 범주를 공유하는 새는?`, `<종명>와 식성이 같은 새는?`
  - 까치 3건 모두 `abstain` 일치, 직박구리/청둥오리/왜가리 각 3건 모두 `answer` 일치 확인.
- **6건 추가 조건 보존 및 미지원 보류 검증**:
  - 6건 중 5건 clarify, 1건 서식지 조건 보존 graph_query abstain 확인 (질의별 원본은 [after.json](../verification/assets/2026-10-23-shared-diet-expression/after.json) 참조).
- **2건 기존 먹이 표시명 회귀 검증**:
  - `"까마귀과 중에서 곤충을 먹는 새는?"` ➔ `coverage.matched: 98`
  - `"까마귀과 중에서 고기를 먹는 새는?"` ➔ `coverage.matched: 68`
- **테스트 하네스 보정 내역 (앱 실패 아님)**:
  - 초기 검사기(`verify-api.py`)가 `'숲에 사는 까치와 먹이가 같은 새는?'` 질의에 대해 일률적으로 `clarify` 응답을 요구하여 1건 실패가 기록되었었음 ([after-first-check.json](../verification/assets/2026-10-23-shared-diet-expression/after-first-check.json): 23 passed, 1 failed).
  - 실제 앱은 서식지 조건을 탈락시키지 않고 정상적으로 `graph_query` (`insufficient_data`)로 해석하여 조건을 안전하게 보존하고 있었음.
  - 검사기 조건을 정상 조건 보존 검사로 정정한 후 동일한 24개 응답을 재검증(`--recheck`)하여 24/24 전원 통과를 확인하였음.

### 4) Playwright 반응형 브라우저 실사 ([browser.json](../verification/assets/2026-10-23-shared-diet-expression/browser.json))
- **도구**: Playwright (Headless Chromium)
- **검증 URL**: `https://robingraph-test.dove-nest.com/chat`
- **시나리오**: 2개 뷰포트(모바일 390px, 데스크톱 1280px) × 2개 질의 = **총 4개 시나리오 전원 통과 (4/4)**:
  1. `"까치랑 같은 먹이 생태를 가진 새를 알려줘"` ➔ `disposition: abstain` ("까치의 생태가 비슷한 종에 관한 출처가 확인된 자료를 현재 제공하지 못했습니다.", `page_errors: []`, `overflow: false`)
  2. `"직박구리랑 같은 먹이 생태를 가진 새를 알려줘"` ➔ `disposition: answer` ("직박구리와 같은 자료의 생태 범주를 공유하는 종을 찾았습니다...", `page_errors: []`, `overflow: false`)
- **스크린샷 증거 확보**:
  - 모바일(390px): [까치-390.png](../verification/assets/2026-10-23-shared-diet-expression/까치-390.png), [직박구리-390.png](../verification/assets/2026-10-23-shared-diet-expression/직박구리-390.png)
  - 데스크톱(1280px): [까치-1280.png](../verification/assets/2026-10-23-shared-diet-expression/까치-1280.png), [직박구리-1280.png](../verification/assets/2026-10-23-shared-diet-expression/직박구리-1280.png)
- **검증 환경 한계 명시**: `physical_mobile: false` (Chromium 모바일/데스크톱 에뮬레이션 환경 실측이며 실제 물리 모바일 기기/Safari/Firefox 미실행).

### 5) 코드 지식 그래프 동기화
- **실행 내용**: AST 기반 코드 지식 그래프 갱신 완료
- **결과**: 7,940개 노드, 17,103개 엣지, 454개 커뮤니티 최신화 완료 ([graphify.log](../verification/assets/2026-10-23-shared-diet-expression/graphify.log)).

---

## 5. 배포 및 형상 관리 상태

- **앱 통합 브랜치**: `dev-codex` (통합, 검증, TEST 배포 관리)
- **문서 작업 브랜치**: `dev` (`main-2` 워크트리)
- **대상 환경**: TEST Mac .97 (ARM64)
- **운영(Production NAS) 상태**: 배포 없음, 컨테이너 재시작 없음 (`production_changed: false`)
- **조류 DB 상태**: 쓰기 연산 0건 (`bird_db_writes: 0`)
- **Git 형상**: 별도 지시 전 commit 및 push 없음

---

## 6. 한계 및 후속 과제

1. **표면 표현 수정 한계 (Not Semantic Generalization)**:
   - 이번 수정은 `ecological_related` / `trophic_niche`의 표면 어순과 어휘 결합을 최소 확장한 오류 복구 패치임.
   - 임의의 자연어 질문을 의미적 구조로 일반화 분해하는 GraphRAG semantic generalization이 완성된 것이 아니며, 향후 미지원 문형 확장은 구조적 질의 엔진 고도화로 다루어야 함.
2. **벡터 경로 진입 한계 및 실행 게이트 구조**:
   - `extract_graph_intent`에서 어휘적으로 포착되지 않는 문장은 `execution_gate`에서 즉시 차단되어 임베딩 호출 없이 종료되는 구조적 제약이 존재함.
   - 향후 상위 의미 라우터와의 유기적 협력 체계 검토 필요.
3. **까치의 직접 trophic_niche 출처 자료 부재**:
   - 까치(`Pica serica`)처럼 국내 대표 조류라도 Neo4j 노드에 직접적인 AVONET `trophic_niche` 출처 자료가 누락되어 있는 경우 정직하게 `abstain`으로 응답함.
   - RobinGraph의 근거 혼용 금지 지침에 따라 부모 분류군으로부터 임의 추정하거나 다른 학명(`Pica pica`)으로 대체하지 않음.

---

## 관련 문서 및 검증 자산

- **검증 자산 디렉터리**: [docs/verification/assets/2026-10-23-shared-diet-expression/](../verification/assets/2026-10-23-shared-diet-expression/)
  - [before.json](../verification/assets/2026-10-23-shared-diet-expression/before.json) (사전 public 3건 질의 응답)
  - [canonical-before.json](../verification/assets/2026-10-23-shared-diet-expression/canonical-before.json) (기존 canonical 4종 질의 실측 베이스라인)
  - [lexical-diagnostic.json](../verification/assets/2026-10-23-shared-diet-expression/lexical-diagnostic.json) (execution_gate not_graph 및 embedding 0 로컬 진단)
  - [focused-python.log](../verification/assets/2026-10-23-shared-diet-expression/focused-python.log) (Python 102/102 통과 영수증)
  - [test-release.json](../verification/assets/2026-10-23-shared-diet-expression/test-release.json) (TEST 배포 영수증, 이미지 해시 및 모드 이력)
  - [final-state.json](../verification/assets/2026-10-23-shared-diet-expression/final-state.json) (TEST 활성 최종 상태 영수증)
  - [activation-gates.json](../verification/assets/2026-10-23-shared-diet-expression/activation-gates.json) (active 전환 게이트 영수증)
  - [after.json](../verification/assets/2026-10-23-shared-diet-expression/after.json) (24건 live API 24/24 통과 영수증)
  - [after-first-check.json](../verification/assets/2026-10-23-shared-diet-expression/after-first-check.json) (하네스 보정 전 1차 응답 보존 영수증)
  - [browser.json](../verification/assets/2026-10-23-shared-diet-expression/browser.json) (Playwright 4개 시나리오 렌더링 결과)
  - [까치-390.png](../verification/assets/2026-10-23-shared-diet-expression/까치-390.png), [까치-1280.png](../verification/assets/2026-10-23-shared-diet-expression/까치-1280.png) (까치 스크린샷)
  - [직박구리-390.png](../verification/assets/2026-10-23-shared-diet-expression/직박구리-390.png), [직박구리-1280.png](../verification/assets/2026-10-23-shared-diet-expression/직박구리-1280.png) (직박구리 스크린샷)
  - [graphify.log](../verification/assets/2026-10-23-shared-diet-expression/graphify.log) (AST 지식 그래프 갱신 영수증)
- **관련 코드**:
  - [src/robingraph/retrieval/species_questions.py](src/robingraph/retrieval/species_questions.py)
  - [tests/test_species_questions.py](tests/test_species_questions.py)
- **이전 작업 문서**:
  - [2026-10-23-diet-display-alias.md](./2026-10-23-diet-display-alias.md) (RG-210)
  - [2026-10-23-food-granularity-guidance.md](./2026-10-23-food-granularity-guidance.md) (RG-209)
