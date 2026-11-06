---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: RG-209
tags:
  - worklog
  - robingraph
  - query-guidance
  - diet-traits
  - biological-integrity
---

# [RG-209 / 검색] 먹이 세분화(곤충 등) 질의에 대한 자료 한계 및 대체 질문 안내 구조 개선 — 2026-10-23

> **문서 상태: 검증 완료 (2026-10-23 TEST 모바일 스크린샷 곤충 질의 clarify 인입에 따른 원인 분석, 생물학적 정합성 가드레일 확립, Claude 최소 구조 개선 구현, Codex 통합·TEST 배포 및 34건 표적 API 회귀 100% 통과, Playwright 반응형 검사 완료; 496건 전체 재평가 없음, 원본 데이터셋 기대값 불변, 백로그 상태 임의 변경 없음, 운영 미배포, Git commit/push 없음, 조류 DB 쓰기 0건)**  
> 2026-10-23 사용자 TEST 모바일 환경에서 "까마귀과 중에서 곤충을 먹는 새는?" 질의 시 일반적인 조건 추가 요구(`clarify`) 메시지만 반환되어 사용자가 원인을 파악하기 어려운 문제가 확인되었다.  
> 실제 TEST API 재현 결과, "까마귀과 중에서/중 곤충을 먹는 새는?"은 모두 clarify 처리된 반면, 상위 범주인 "까마귀과 중 무척추동물을 먹는 새는?"은 135개 스코프 중 100개 평가 가능, 98개 일치로 정상 응답을 반환했다.  
> 원인 분석 결과 `graph_condition_extractor.py`의 기존 `_UNSUPPORTED` 규칙에서 `곤충`이 `('other', r'...')` 정규식에 걸려 `unsupported=('other',)`로 단순 차단되어 있었으며(`unsupported_food` 진단 필드는 이번에 새로 추가), 실제 활성 TEST DB 실사 결과 그래프에는 "곤충(Insect)" 전용 claim/출처가 없고 상위 개념인 `invertebrate`/`Invertivore`(무척추동물)만 존재함이 확인되었다.  
> 곤충은 무척추동물의 하위 분류군(거미·지렁이·달팽이 등 제외)이므로 **"곤충 = 무척추동물"로 임의 치환하는 것은 생물학적 정확성에 위배**된다. 따라서 현재 자료로 정확한 곤충 섭식 목록을 단정할 수 없음을 투명하게 안내하고, 상위 범주인 "무척추동물을 먹는 새" 등으로 대체 검색할 수 있도록 구조화된 안내를 제공하는 최소 구조 개선을 완료하였다.  
> 실제 TEST 배포(`robingraph-api:test-taxonomic-traits-8a4dbb23f63e`) 환경에서 34개 표적 API 회귀 테스트(10건 안내, 12건 정규 질의, 4건 지원 먹이, 8건 안전/경계 조건)를 수행하여 34/34(100%) 통과를 검증하였으며, Playwright 모바일(390px)/데스크톱(1280px) 렌더링 검사에서도 무오류·무오버플로를 확인하였다.  
> **주의**: 실제 곤충 종 목록은 데이터 부재로 여전히 미지원이며, 금번 작업은 데이터 한계 안내 오류만 정정한 것이다. 또한 직전 496건 데이터셋 평가 100% 통과가 모든 자연어 질의 지원 완료를 의미하는 것은 아니다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 문제 인입** | 모바일 TEST 곤충 질의 clarify 현상 | 2026-10-23 모바일 스크린샷: "까마귀과 중에서 곤충을 먹는 새는?" 질의 시 일반 clarify 응답 반환. 사용자가 먹이 자료의 범주 한계를 알기 어려움 |
| **실제 TEST API 재현** | 곤충 vs 무척추동물 대조 검증 | - `까마귀과 중에서/중 곤충을 먹는 새는?`: 둘 다 일반 `clarify` 반환<br>- `까마귀과 중 무척추동물을 먹는 새는?`: scoped 135, evaluable 100, matched 98 정상 `answer` 반환 |
| **원인 분석 (파서)** | 기존 `_UNSUPPORTED` 차단 | `graph_condition_extractor.py` 내 기존 `_UNSUPPORTED` 규칙에서 `('other', r'(?<![가-힣])(?:곤충|벌레|어류|곡식|곡물|꿀|육류|고기|잎)(?:을|를)?(?=\s*먹)')`에 걸려 `unsupported=('other',)`로 단순 차단됨 (`unsupported_food` 필드는 이번에 새로 추가됨) |
| **데이터 실사 (Claude)** | 활성 TEST DB 내 곤충 자료 부재 | 실제 TEST Neo4j/PG 실사: 곤충 전용 claim/source 부재. 오직 `invertebrate`(무척추동물 비율) 및 `Invertivore`(무척추동물 섭식)만 존재 |
| **생물학적 정합성 원칙** | 곤충 ➔ 무척추동물 임의 치환 금지 | 곤충은 거미, 지렁이, 달팽이, 갑각류 등과 구분되는 무척추동물의 일부이므로, 자료에 없는 하위 개념을 상위 개념으로 1:1 강제 치환하지 않음 |
| **구조 개선 구현 (Claude)** | 자료 한계 명시 + 대체 질문 가이드 | 1) `FOOD_GAPS` 매핑 및 `GraphIntent` 스키마 확장 (`unsupported_food` 진단 필드 신설)<br>2) `unsupported_food_answer()`: `insufficient_data` 상태로 자료 한계 설명 및 조사(`을/를`)를 보정한 대체 질의 자동 생성<br>3) **정밀 가드레일**: 지원되고 모순 없는 조건(예: 체중 100g 이상)은 추천 질문에 보존하되, 부정·미해석·모호·모순·추가 미지원 관계 결합 시에만 안전한 `clarify` 유지 |
| **API 서비스 연동 (Codex)** | `services.py` 라우팅 분기 | `graph_intent_mode == "active"`에서 `unsupported_food` 감지 시 DB 조회 없이 `abstain`(`insufficient_data`) 즉시 반환 |
| **TEST 배포 및 활성화** | 점진적 안전 전환 검증 | snapshot 이미지 `robingraph-api:test-taxonomic-traits-8a4dbb23f63e` 빌드 ➔ shadow 모드 레거시 7건 대조(diff 0) ➔ `activation-gates.json` 통과 ➔ active 모드 전환 |
| **표적 회귀 검증 결과** | 34건 live TEST API 전수 검증 | - `before.json`: 24 통과 / 10 실패 (FG-01~10 미구현 실패)<br>- `after.json`: **34 / 34 (100%) 통과** (10건 food_guidance, 12건 query, 4건 supported_food, 8건 clarify)<br>- `regression-comparison.json`: 기존 24개 응답(selected_intent/route_method/disposition/result) 완전 동일, 10건 자료 한계 정정 확인<br>- 지연시간: 원본 `after.json` 영수증에 케이스별 `elapsed_ms` 보존 (성능 평가는 본 표적 검증 목표 아님) |
| **브라우저 QA (Playwright)** | 모바일 및 데스크톱 렌더링 검증 | Chromium 390px 및 1280px 검증: Playwright `pageerror` 이벤트 0건, 수평 오버플로 없음(`overflow: false`), 종 목록 행 0건(`.graph-query-species-row` 0개), 안내 카드(`.graph-query-answer`) 정상 표출 확인 (`browser.json`, `after-390.png`, `after-1280.png`). Root 시각 확인 완료. `physical_mobile: false` (에뮬레이션 환경) |
| **거버넌스 및 안전 상태** | 무영향 원칙 준수 | 직전 496건 평가 결과 과거 검증 범위로 영구 보존, 원본 Native 496 데이터셋 기대값 불변, 기존 백로그 상태 무변경, 운영 미배포, 조류 DB 쓰기 0건(`bird_db_writes: 0`), Git commit/push 0건 |

---

## 1. 배경 및 실제 TEST 환경 인입 증상

### 1) 사용자 인입 증상
- **일시**: 2026-10-23
- **환경**: TEST 모바일 웹 (`https://robingraph-test.dove-nest.com/chat`)
- **질의**: `"까마귀과 중에서 곤충을 먹는 새는?"`
- **증상**: 구체적인 조류 목록이나 명확한 안내 없이 단순 clarify("질문의 조건을 모두 확인하지 못했습니다. 기준 종과 분류·먹이·서식지 조건을 명확히 입력해 주세요.") 류의 일반 응답 반환.
- **사용자 경험 문제**: 사용자는 왜 까마귀과의 곤충 섭식 질문이 처리되지 않는지, 데이터의 한계 때문인지 질문 형식의 문제인지 전혀 파악할 수 없었음.

### 2) 실제 TEST API 대조 재현
- **검증 환경**: `https://robingraph-test.dove-nest.com` (Image: `robingraph-api:test-taxonomic-traits-eb8169862c0e`)
- **재현 질의 1**: `"까마귀과 중에서 곤충을 먹는 새는?"` ➔ `clarify` (동일 재현)
- **재현 질의 2**: `"까마귀과 중 곤충을 먹는 새는?"` ➔ `clarify` (동일 재현)
- **대조 질의 3**: `"까마귀과 중 무척추동물을 먹는 새는?"`
  - `disposition`: `answer`
  - `status`: `answer`
  - `coverage`: `scoped: 135`, `evaluable: 100`, `matched: 98`
  - 정상 조류 목록 및 카드 반환 확인.

---

## 2. 원인 분석 및 생물학적 정합성 가드레일

### 1) 코드 원인 분석 (`graph_condition_extractor.py`)
기존 의도 추출기에서는 EltonTraits 10대 범주에 직접 대응되지 않는 먹이 명칭들을 `_UNSUPPORTED` 규칙의 `'other'` 범주로 일괄 차단하고 있었다:
```python
_UNSUPPORTED = (
    ('co_occurrence', r'같은\s*곳에서\s*(?:공존하는|공존|사는)|...'),
    ...
    # Foods with no composition key in the data (곤충 is not 무척추동물); 물고기/씨앗/꽃꿀 are data keys now.
    ('other', r'(?<![가-힣])(?:곤충|벌레|어류|곡식|곡물|꿀|육류|고기|잎)(?:을|를)?(?=\s*먹)'),
    ...
)
```
- 질의에 `곤충`이 포함되면 `unsupported=('other',)` 의도로만 분류되어 `GraphIntent.kind`가 생성되지 않고, `execution_gate`에서 단순 `clarify`로 탈락됨 (`unsupported_food` 진단 필드는 존재하지 않았음).

### 2) 활성 TEST DB 실사 결과 (Claude 확인)
- 활성 TEST Neo4j 및 PostgreSQL 데이터 실사:
  - 그래프에 존재하는 먹이 관련 형질은 AVONET의 `trophic_niche` (`Invertivore`, `Vertivore` 등) 및 EltonTraits의 `diet_distribution` (`invertebrate`, `endotherm_vertebrate`, `ectotherm_vertebrate`, `fish`, `unknown_vertebrate`, `carrion`, `fruit`, `nectar`, `seed`, `other_plant` 등 10개 키)으로 구성됨.
  - **"곤충(Insect)" 전용 claim, 속성 또는 원천 문헌 근거는 DB에 전혀 존재하지 않음.**

### 3) 생물학적 정합성 가드레일 (엄격 준수)
- **"곤충 = 무척추동물" 임의 치환 절대 금지**:
  - 생물학적으로 무척추동물(Invertebrate)은 곤충류(Insecta)뿐만 아니라 거미류(Arachnida), 갑각류(Crustacea), 환형동물(지렁이류), 연체동물(달팽이류) 등을 광범위하게 포괄함.
  - 만약 시스템 내부에서 `곤충`을 `invertebrate`로 1:1 강제 치환하여 답변을 생성한다면, 지렁이나 달팽이를 주로 먹는 조류까지 "곤충을 먹는 새"로 단정하여 사용자에게 제공하게 됨.
  - 이는 **생물학적 왜곡이자 허위 정보(Hallucination)**를 조장하는 치명적인 결함이므로, 조류 데이터 거버넌스 원칙에 따라 임의 치환을 일체 금지함.

### 4) 개선 설계: 투명한 한계 안내 + 대체 질문 유도
- 사용자가 "곤충을 먹는 새"를 물었을 때:
  1. **데이터 한계 투명성**: 현재 조회하는 EltonTraits 먹이 성분 자료에는 세부 '곤충' 단위 기록이 없음을 명확히 설명.
  2. **범주 불일치 고지**: 데이터베이스에는 ‘무척추동물’ 범주로 기록되어 있으나, 두 개념이 일치하지 않으므로 임의로 바꿔 조회하지 않았음을 밝힘.
  3. **대체 질의 자동 생성**: 원래 질문의 분류군 및 조사 맥락을 유지한 채 상위 범주 질의(예: `“까마귀과 중에서 무척추동물을 먹는 새는?”`)를 제안.

---

## 3. 아키텍처 및 구현 세부 사항

Codex와 Claude의 협업을 통해 최소 구조 수정을 적용하였다. 통합된 6개 파일의 형상은 아래와 같다 (`integrated-files.json`):

| 파일 경로 | 수정 전 SHA-256 | 수정 후 SHA-256 | 주요 수정 내용 |
| --- | --- | --- | --- |
| `src/robingraph/retrieval/graph_questions.py` | `21315a10...` | `32e29681...` | `FOOD_GAPS` 매핑, `LIMITATIONS['no_food_key']`, `unsupported_food_answer()` 및 조사 보정 로직 구현 |
| `src/robingraph/retrieval/graph_intent_schema.py` | `dd949e3a...` | `ee2f06db...` | `GraphIntent.unsupported_food` 필드 추가, 유효성 검사 및 `unsupported_food()` 게이트 함수 추가 |
| `src/robingraph/retrieval/graph_condition_extractor.py` | `17765013...` | `2a437ebf...` | `_UNSUPPORTED` 내 `food` 정규식 분리, unsupported food span 추출 및 복합 조건 모호성 검증 연동 |
| `tests/test_taxon_traits.py` | `7c6665d7...` | `f6dbc863...` | unsupported food 골드 라벨 불변 검증, 게이트 분기, 안내 문구 정확성 및 복합 조건 차단 단위 테스트 추가 |
| `src/robingraph/api/services.py` | `a1dac11d...` | `9c60190c...` | active 모드에서 `unsupported_food` 감지 시 DB 조회 없이 `insufficient_data` / `abstain` 즉시 반환 |
| `tests/test_taxon_traits_api.py` | `4708b66d...` | `e6fd3cd7...` | API 레벨 단위 테스트 갱신 |

### 1) 먹이 갭 매핑 정의 (`FOOD_GAPS`)
```python
FOOD_GAPS = {
    '곤충': ('invertebrate',),
    '벌레': ('invertebrate',),
    '곡식': ('seed',),
    '곡물': ('seed',),
    '꿀': ('nectar',),
    '잎': ('other_plant',),
    '육류': ('endotherm_vertebrate', 'ectotherm_vertebrate', 'unknown_vertebrate', 'fish', 'carrion'),
    '고기': ('endotherm_vertebrate', 'ectotherm_vertebrate', 'unknown_vertebrate', 'fish', 'carrion')
}
```
- `어류`: `물고기(fish)`와의 동의어 처리 이슈이므로 `FOOD_GAPS`가 아닌 `other`로 유지하여 데이터 갭과 구별.

### 2) 정밀 가드레일 (`unsupported_food` 게이트 함수)
```python
def unsupported_food(question, intent):
    """Food spans when a food with no data key is the only thing blocking question, else ().
    Any negation, residual, ambiguity, specific plant or another unsupported relation keeps the clarify."""
    if (not isinstance(intent, GraphIntent) or validate_intent(question, intent) or intent.unsupported != ('other',)
            or not intent.unsupported_food or intent.negation or intent.residual or intent.ambiguity
            or intent.specific_plant is not None):
        return ()
    return intent.unsupported_food
```
- **지원되고 모순 없는 조건 보존**: 지원 가능한 형질 조건(예: 체중 `100g 이상`, 서식지 `숲에 사는`)은 추천 질문에 그대로 보존됨 (예: `"까마귀과 중 곤충을 먹고 체중 100g 이상인 새"` ➔ `“까마귀과 중 무척추동물을 먹고 체중 100g 이상인 새”` 처럼 보존되어 정상 유도).
- **clarify 유지 대상**: 오직 부정 표현(`안 먹는`, `먹지 않는`), 미해석/모호한 단위(`체중 3파운드`, `부리 길이 30mm`), 모순된 조건(`체중 100g 이상 50g 이하`), 추가 미지원 관계(`먹이 경쟁`, `공존`, `잡아먹는`, `같은 과인`), 시간/계절(`겨울에`), 다중 분류군 결합(`까마귀과 참새목`) 시에만 `()`를 반환하여 안전한 `clarify`로 분기함.

### 3) 구조화된 안내 응답 생성기 (`unsupported_food_answer`)
- 반환 속성:
  - `status`: `'insufficient_data'`
  - `disposition`: `'abstain'`
  - `title`: `'먹이 자료 범위'`
  - `items`: `[]` (DB 조회 0건, 조류 카드 0건)
  - `has_more`: `False`
  - `limitations`: `[LIMITATIONS['no_food_key']]`
- 단일 대상 범주인 경우(곤충 ➔ 무척추동물 등):
  - 한국어 목적격 조사 교정 함수 `_object_particle()`을 통해 `'무척추동물'` + `'을'`, `'씨앗'` + `'을'`, `'꽃꿀'` + `'을'`을 정확히 합성하여 자연스러운 대체 질의를 생성.
- 복수 대상 범주인 경우(`고기`, `육류`):
  - 단일 대체 질의를 단정할 수 없으므로 특정 질문 제안 문구를 생략하고 개념 목록만 안내.

### 4) API 서비스 연동 (`services.py`)
```python
if self.graph_intent_mode == "active":
    legacy_match = graph_question is not None
    graph_question = to_graph_question(request.question, interpreted)
    graph_method = "semantic" if request.intent == "auto" else "explicit"
    foods = unsupported_food(request.question, interpreted)
    if foods:
        from ..retrieval.graph_questions import unsupported_food_answer
        payload = unsupported_food_answer(request.question, foods)
        return ChatResponse(
            selected_intent="profile", route_method=graph_method, disposition="abstain",
            answer_text=payload["text"], warnings=payload["limitations"],
            result=ChatGraphResult(payload=payload),
        )
```

---

## 4. 검증 절차 및 실제 결과

### 1) 단위 테스트 검증
- **실제 실행 명령**:
  ```bash
  PYTHONPATH=tests uv run --locked --extra test python -m unittest \
    tests.test_taxon_traits \
    tests.test_taxon_traits_api \
    tests.test_graph_condition_extractor \
    tests.test_graph_intent_schema \
    tests.test_graph_semantic_router \
    tests.test_graph_questions \
    tests.test_graph_semantic_api
  ```
- **결과**: `Ran 128 tests in 1.018s — OK` (총 128개 포커스 단위 테스트 전원 통과, `focused-python.log`).

### 2) TEST 환경 점진적 안전 배포 (`deploy-test-snapshot.py`)
- **대상 컨테이너**: `robingraph-api-test` (ARM64 Mac .97 TEST 환경)
- **배포 이미지**: `robingraph-api:test-taxonomic-traits-8a4dbb23f63e` (런타임 206개 파일 SHA-256 일치 확인)
- **릴리스 디렉터리**: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-8a4dbb23f63e-8eae24`
- **검증 게이트**:
  1. `deploy-shadow`: shadow 모드로 배포 후 기존 레거시 질의 7건 대조 (`legacy-api-baseline.json` vs `legacy-api-shadow.json`). 지문 차이 0건, DB 쓰기 0건 확인.
  2. `activation-gates.json`: `{"all_passed": true, "shadow_api_verified": true, "focused_tests": 128, "fixture_network_none": true}`
  3. `activate`: active 모드로 전환 완료 (`test-release.json`: `graph_intent_mode: "active"`).
- **코드 지식 그래프 갱신**: AST 기반 graphify 갱신 완료 (7,821 노드, 16,862 엣지, 434 커뮤니티, `graphify.log`).

### 3) 표적 API 34건 회귀 검증 (`cases.json`, `verify-api.py`)
전체 496건 재평가를 무리하게 돌리지 않고, 문제 범위와 경계를 정밀하게 포괄하는 34건의 표적 질의 세트를 구성하여 전수 live API 검증을 수행하였다.

#### 회귀 매트릭스 구성
- **군 1: 미지원 먹이 안내 (`food_guidance`, 10건)**:
  - FG-01 ~ FG-07: 곤충 질의 (까마귀과 중에서, 딱따구리과 중, 참새목 가운데, Corvus 중에서, Anas platyrhynchos 중, Corvus corone corone 중, 루트 "곤충을 먹는 새는?")
  - FG-08 ~ FG-10: 곡물(오리과 중에서), 잎(Anser 중), 꿀(벌새 중)
- **군 2: 정규 상위 범주 질의 (`query`, 12건)**:
  - FG-11 ~ FG-22: 분류군(과·목·속·종·아종) × 조사(`중` vs `중에서`) × 무척추동물 섭식 조건
- **군 3: 기존 지원 먹이 질의 (`supported_food`, 4건)**:
  - FG-23 ~ FG-26: 물고기(오리과), 씨앗(참새과), 꽃꿀(Nectarinidae), 열매(직박구리과)
- **군 4: 안전 및 복합 조건 차단 (`clarify`, 8건)**:
  - FG-27 ~ FG-28: 부정 표현 (`곤충을 안 먹는`, `곤충을 먹지 않는`)
  - FG-29: 계절 한정 (`겨울에만`)
  - FG-30: 수식어 (`빨간 곤충을`)
  - FG-31 ~ FG-32: 생태 상호작용 복합 (`먹이 경쟁을 하는`, `공존하는`)
  - FG-33: 모호한 단위 결합 (`체중이 30cm 이상인`)
  - FG-34: 배제 표현 (`곤충 말고 열매를 먹는`)

#### 검증 결과 대조
| 검증 단계 | 파일 | 통과 건수 / 전체 | 실패 건수 | 판정 및 분석 |
| --- | --- | :---: | :---: | --- |
| **수정 전 (Before)** | `before.json` | 24 / 34 | 10 | FG-01~10 미지원 먹이 질의가 단순 clarify로 처리되어 실패 (정상 baseline) |
| **수정 후 (After)** | `after.json` | **34 / 34** | **0** | **100% 전수 통과 (미지원 10건 안내 성공, 기존 24건 무회귀 유지)** |

- **기존 24건 무회귀 증명 (`regression-comparison.json`)**:
  ```json
  {
    "supported_and_safety_responses_compared": 24,
    "all_identical": true,
    "new_guidance_cases": 10,
    "api_cases_after_passed": 34,
    "physical_mobile_tested": false
  }
  ```
  - 기존 24개 응답의 `selected_intent`, `route_method`, `disposition`, `result`가 수정 전과 완전히 동일함이 확인됨.

#### 응답 시간 영수증 보존
- **측정 대상**: 실제 `https://robingraph-test.dove-nest.com` live API 34건
- **응답 모킹**: 없음 (`response_mocking: false`)
- **지연 시간 영수증**: 성능 집계 및 벤치마크는 본 표적 기능 검증의 평가 목표가 아니므로, 34개 케이스의 개별 응답 소요 시간은 원본 검증 영수증([`after.json`](../verification/assets/2026-10-23-food-granularity/after.json) 내 `elapsed_ms` 필드)에 그대로 보존함 (전체 범위: 611.14 ms ~ 2,701.62 ms).

#### 실제 반환 메시지 검증 (FG-01 케이스 실사)
- **질의**: `"까마귀과 중에서 곤충을 먹는 새는?"`
- **disposition**: `abstain`
- **payload.status**: `insufficient_data`
- **payload.text**:
  > *"곤충만 따로 구분한 기록은 현재 조회하는 먹이 성분 자료로 확인할 수 없습니다. 자료는 ‘무척추동물’ 범주로 기록돼 요청한 곤충 섭식 여부를 이 범주만으로는 확인할 수 없습니다. 범주를 바꿔 조회하지 않았습니다. 해당 범주로 찾으려면 “까마귀과 중에서 무척추동물을 먹는 새는?”처럼 질문해 주세요."*
- **payload.limitations**:
  > *["먹이 구성은 현재 조회하는 EltonTraits 먹이 성분 자료의 10개 범주로만 확인합니다. 곤충·곡물처럼 범주와 다르게 부르는 먹이의 섭식 여부는 이 범주만으로 확인할 수 없습니다."]*
- **조류 종 목록 행**: 0건 (`items: []`, `.graph-query-species-row` 0개)

### 4) Playwright 반응형 UI 렌더링 검사 (`browser.cjs`, `browser.json`)
실제 브라우저 환경에서 안내 문구가 사용자 화면에 올바르게 렌더링되고 레이아웃이 깨지지 않는지 검증하였다.
- **도구**: Playwright (Headless Chromium)
- **검증 URL**: `https://robingraph-test.dove-nest.com/chat`
- **물리 모바일 여부**: `physical_mobile: false` (실제 물리 모바일 기기가 아닌 Chromium 뷰포트 에뮬레이션 환경임을 명확히 구분)
- **시각 검토**: `after-390.png` 및 `after-1280.png`에 대해 Root 시각 확인 완료
- **검증 뷰포트**:
  1. **모바일 뷰 (390px × 900px)**:
     - 상태: `abstain` / `insufficient_data`
     - 종 목록 행: 0개 (`.graph-query-species-row` 0개)
     - 안내 카드: 정상 표출 (`.graph-query-answer` 정상 렌더링)
     - 페이지 에러: 0건 (Playwright `pageerror` 이벤트 0건)
     - 수평 오버플로: 없음 (`overflow: false`, `document.documentElement.scrollWidth <= innerWidth`)
     - 스크린샷: `docs/verification/assets/2026-10-23-food-granularity/after-390.png`
  2. **데스크톱 뷰 (1280px × 900px)**:
     - 상태: `abstain` / `insufficient_data`
     - 종 목록 행: 0개
     - 안내 카드: 정상 표출
     - 페이지 에러: 0건 (Playwright `pageerror` 이벤트 0건)
     - 수평 오버플로: 없음 (`overflow: false`)
     - 스크린샷: `docs/verification/assets/2026-10-23-food-granularity/after-1280.png`

---

## 5. 한계점 및 후속 과제

> [!NOTE] 후속 변경 안내 (2026-10-23)
> 본 문서의 먹이 세분화 안내(RG-209)는 사용자 의도(무척추동물 ➔ 곤충, 척추동물 ➔ 고기 표시명 변경 요청)에 대한 초기 오해에서 작성된 과도기적 기록입니다.  
> 원천 데이터(EltonTraits/AVONET)는 그대로 보존하되, `invertebrate`의 사용자 대표 표시명을 '곤충'으로 매핑(비곤충 무척추동물 포함 안내 병기)하고 `endotherm/ectotherm/unknown vertebrate` 3개 성분을 '고기'로 합산 표시하는 정식 개선 작업은 후속 작업 문서 [`./2026-10-23-diet-display-alias.md`](./2026-10-23-diet-display-alias.md)에 상세히 기록됩니다. 본 문서는 당시의 의사결정 및 검증 역사로서 영구 보존됩니다.

1. **실제 곤충 종 목록 미지원 유지**:
   - 금번 작업은 데이터 한계 안내 오류(clarify ➔ abstain/insufficient_data + 대체 질문)를 수정한 것이며, 데이터베이스에 없는 곤충 종 목록을 생성하거나 반환하는 기능이 아님.
2. **이전 496건 통과와 자연어 범위의 한계**:
   - 직전 496건 데이터셋 평가 100% 통과는 특정 계약 템플릿에 대한 회귀 안정성 증명이며, **모든 자연어 질문이나 변형 표현의 지원 완료를 의미하지 않음**.
3. **후속 처리 과제**:
   - **`어류` 동의어 매핑**: `어류`는 `물고기(fish)`와의 동의어 처리 과제이므로 데이터 갭과 분리하여 현재 `other`로 유지함. 후속 동의어 정규화 검토 필요.
   - **표 밖 미등록 먹이 용어**: `거미`, `지렁이` 등 `FOOD_GAPS`에 정의되지 않은 세부 생물명에 대한 단계적 어휘 확장.
   - **명사 병렬 연결 질의**: `곤충과 열매` 등 다중 먹이 명사가 병렬 연결된 복합 질의의 파싱 분해 로직 고도화.

---

## 6. 형상 관리 및 거버넌스 준수

RobinGraph 작업 지침 및 안전 원칙을 철저히 준수하였다:
- **과거 평가 자산 보존**: 직전 완료된 496건 MLflow GenAI Evaluate 평가 결과(`Experiment 33 / run 0295848aaa854d8cb8acc289373daf67`)는 독립된 과거 검증 범위로 영구 보존하며 덮어쓰지 않음.
- **원본 평가 데이터셋 불변**: `data/eval/graph_questions/taxonomic-regression-v1/`의 질문 및 기대값은 일체 수정하지 않음.
- **백로그 상태 무변경**: 기존 작업 백로그의 상태를 임의로 조작하지 않음.
- **조류 DB 쓰기 0건**: 활성 TEST 및 Production Neo4j/PostgreSQL에 대한 쓰기 연산은 전혀 발생하지 않음 (`bird_db_writes: 0`).
- **운영(Production) 무영향**: Production NAS 환경 배포, 재시작, 이미지 교체 일체 없음 (`production_changed: false`).
- **Git 무영향**: 별도 지시 없이 `git commit` 및 `git push`를 수행하지 않음.

---

## 관련 문서 및 검증 자산

- **후속 개선 작업 문서**: [`./2026-10-23-diet-display-alias.md`](./2026-10-23-diet-display-alias.md) (사용자 의도 명확화에 따른 무척추동물➔곤충, 척추동물➔고기 표시명 개선)
- **검증 자산 디렉터리**: [`../verification/assets/2026-10-23-food-granularity/`](../verification/assets/2026-10-23-food-granularity/)
  - [`after.json`](../verification/assets/2026-10-23-food-granularity/after.json) (34건 live API 100% 통과 영수증)
  - [`before.json`](../verification/assets/2026-10-23-food-granularity/before.json) (수정 전 24/34 통과 대조 영수증)
  - [`cases.json`](../verification/assets/2026-10-23-food-granularity/cases.json) (34건 표적 회귀 케이스 정의)
  - [`regression-comparison.json`](../verification/assets/2026-10-23-food-granularity/regression-comparison.json) (기존 24건 100% 무회귀 일치 증명)
  - [`test-release.json`](../verification/assets/2026-10-23-food-granularity/test-release.json) (TEST 배포 영수증, 이미지 해시 및 모드 이력)
  - [`activation-gates.json`](../verification/assets/2026-10-23-food-granularity/activation-gates.json) (active 전환 게이트 통과 영수증)
  - [`browser.json`](../verification/assets/2026-10-23-food-granularity/browser.json) (Playwright 모바일/데스크톱 렌더링 결과)
  - [`after-390.png`](../verification/assets/2026-10-23-food-granularity/after-390.png) (390px 모바일 화면 스크린샷)
  - [`after-1280.png`](../verification/assets/2026-10-23-food-granularity/after-1280.png) (1280px 데스크톱 화면 스크린샷)
  - [`integrated-files.json`](../verification/assets/2026-10-23-food-granularity/integrated-files.json) (통합 6개 파일 전후 SHA-256 목록)
- **이전 평가 작업 문서**: [`./2026-10-22-graph-question-dataset-evaluation.md`](./2026-10-22-graph-question-dataset-evaluation.md)
- **데이터셋 문서**: [`../../data/eval/graph_questions/taxonomic-regression-v1/README.md`](../../data/eval/graph_questions/taxonomic-regression-v1/README.md)
- **Obsidian 작업기록**: `Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-먹이-세분화-한계-안내.md`

---
*문서 작성 완료 일시: 2026-10-23*  
*작성자: dev / Writer*
