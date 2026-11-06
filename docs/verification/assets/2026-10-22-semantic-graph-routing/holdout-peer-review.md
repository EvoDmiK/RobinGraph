# RG-204/205 독립 수기 평가셋 (holdout.jsonl) 도메인·시맨틱 독립 검토 보고서

- **검토 대상 파일**: `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/data/eval/graph_questions/holdout.jsonl` (40건)
- **초안 작성자**: Codex (`agent:codex`, `review_status: "agent_draft"`)
- **검토자**: Writer (`agent:writer`, 독립 도메인·시맨틱 검토)
- **검토 일시**: 2026-10-22
- **검토 상태**: `agent_reviewed_draft` (⚠️ **주의**: 본 문서는 Root 최종 검토 및 확정을 위한 에이전트 독립 검토 초안이며, `human_reviewed`로 기록하지 않음)
- **보안 및 격리 주의**: 본 검토 파일 및 holdout 질문 내용은 구현 담당 에이전트(Claude)에게 공유되지 않음.

---

## 1. 개요 및 총평

Codex가 독립 수기 작성한 40개 holdout 질문(`GGQ-H-001` ~ `GGQ-H-040`)은 정규식 조합 생성이 아닌 자연스러운 한국어 구어체 및 도메인 경계 사례를 효과적으로 포괄하고 있습니다.

- **7대 그래프 질의 유형 커버리지**:
  1. `common_taxonomy` (공통 상위분류): 4건 (H-001 ~ H-004)
  2. `same_genus` (같은 속 종): 3건 (H-005 ~ H-007)
  3. `korea_same_genus` (국내 기록 같은 속 종): 3건 (H-008 ~ H-010)
  4. `order_fruit` (특정 목 열매 섭식 종): 4건 (H-011 ~ H-014)
  5. `habitat_shared_diet` (서식지 + 먹이 범주 공유): 3건 (H-015 ~ H-017)
  6. `habitat_different_diet` (서식지 동일 + 먹이 범주 상이): 3건 (H-018 ~ H-020)
  7. `specific_fruit` (특정 식물 열매 / 같은 열매 공유): 3건 (H-021 ~ H-023)
- **경계 및 안전 장치 커버리지**:
  - 부정 표현(`negation`): 3건 (H-024 ~ H-026)
  - 지원 외 추가 조건(`extra_condition` / `residual`): 4건 (H-027 ~ H-030)
  - 과도한 주장/지원 외 관계 거부(`overclaim_reject` / `unsupported`): 4건 (H-031 ~ H-034)
  - 비그래프 단일 종/일반 질의(`not_graph`): 4건 (H-035 ~ H-038)
  - 모호성/문맥 부재(`ambiguity`): 2건 (H-039 ~ H-040)

검토 결과 전체적인 완성도와 도메인 부합도가 매우 높으나, **한국어 의미 해석, 백엔드 Cypher 계약과의 부합성, 카테고리 태깅 및 슬롯 추출 일관성** 측면에서 재검토가 필요한 **4가지 주요 오류/불일치 후보**와 **4가지 스키마·정책 명확화 사항**이 도출되었습니다.

---

## 2. 주요 오류 및 재검토 후보 (Candidate Issues)

### [후보 1] GGQ-H-025: "박새 말고 같은 속인 새" — 부정(`clarify`) vs 동속 동료(peer) 조회 의미 불일치

- **질문**: `"박새 말고 같은 속인 새가 뭐가 있나요?"`
- **현재 expected**:
  ```json
  {
    "kind": "same_genus",
    "disposition": "clarify",
    "species": ["박새"],
    "relation": "same",
    "negation": ["말고"]
  }
  ```
- **문제점 및 근거**:
  1. **한국어 자연어 의미**: "A 말고 같은 속인 새"는 한국어 화자가 "A(박새)를 제외하고, A와 같은 속에 속하는 다른 새"를 묻는 지극히 자연스러운 표현입니다.
  2. **백엔드 Cypher 계약 일치**: RobinGraph의 `GENUS_PEERS_QUERY` Cypher 코드는 다음과 같이 작성되어 있습니다:
     ```cypher
     MATCH (genus:...)-[:PARENT_OF*1..2]->(peer:Taxon:BirdTaxon {rank:'species', ...})
     WHERE peer.id <> $target_id ...
     ```
     즉, 백엔드 엔진은 이미 기준 종(`$target_id`, 박새)을 **스스로 제외한 동료 종(peers)만을 반환**하도록 구현되어 있습니다.
  3. **과도한 보류(False Rejection) 위험**: 사용자가 "박새 말고 같은 속인 새"라고 물었을 때, 시스템이 "말고"라는 단어가 포함되었다는 이유만으로 `clarify`로 되물으며 답변을 거부한다면 사용자 의도와 정확히 일치하는 기능을 스스로 차단하는 결과가 됩니다.
- **권고 사항**:
  - **대안 A (권장)**: `disposition`을 `"answer"`로 변경하고, `"말고"`는 기준 종 제외 peer 관계의 자연어 수식어로 인정 (또는 `negation: ["말고"]`가 있더라도 `target_id` 제외와 일치하므로 정상 답변 허용).
  - **대안 B**: 만약 "모든 형태의 제외 표현은 템플릿 외 부정으로 간주하여 엄격히 보류한다"는 안전 우선 정책을 의도한 것이라면, 해당 설계 의도를 notes에 명시하여 향후 평가 시 혼선 방지.

---

### [후보 2] GGQ-H-040: "참새목 새 중 어떤 새가 좋아?" — `clarify` vs `not_graph` 분류 오류

- **질문**: `"참새목 새 중 어떤 새가 좋아?"`
- **현재 expected**:
  ```json
  {
    "kind": null,
    "disposition": "clarify",
    "species": [],
    "rank": null,
    "ambiguity": ["other"]
  }
  ```
- **문제점 및 근거**:
  1. **질문의 본질**: "어떤 새가 좋아?"는 객관적 사실이나 그래프 관계 조회가 아닌 **주관적 취향/선호도 질의(subjective preference/chitchat)**입니다.
  2. **시스템 동작과의 괴리**: `disposition: "clarify"`는 사용자에게 추가 정보나 조건 구체화를 요구하여 궁극적으로 그래프 질의를 실행할 수 있는 질의에 적용되는 처분입니다. 하지만 주관적 취향 질문은 사용자에게 명확화를 요구하더라도 RobinGraph의 고정 사실 그래프 DB에서 답변을 산출할 수 없습니다.
  3. **타 질의와의 일관성**:
     - `GGQ-H-038` ("오늘 서울 날씨는 어때?") -> `disposition: "not_graph"`
     - 주관적 선호 질의 역시 그래프 질의 대상이 아니므로 `not_graph`로 분류하는 것이 의미론적으로 정확합니다.
- **권고 사항**:
  - `disposition`을 `"not_graph"`로 수정하거나, `unsupported: ["subjective_preference"]`로 명시.
  - 또한 질문에 명시된 `"참새목"` 슬롯 추출 여부(`rank: "참새목"` vs `rank: null`)에 대한 정책 정리 필요 (후술 3절 참조).

---

### [후보 3] GGQ-H-015: "습지에 사는 새 중..." — `categories` 메타데이터 오분류

- **질문**: `"습지에 사는 새 중 쇠오리와 같은 먹이 범주를 공유하는 새 알려 주세요"`
- **현재 categories**: `["contrastive"]`
- **문제점 및 근거**:
  1. H-015의 질의는 `habitat_shared_diet`이며, `relation: "same"` (동일 서식지 + 동일 먹이 범주)입니다. 대조적이거나 상반된 조건을 묻지 않습니다.
  2. 반면 유사한 질의인:
     - `GGQ-H-016` ("숲에서 사는 새 가운데 박새랑 식성이 같은 새") -> `categories: ["paraphrase"]`
     - `GGQ-H-017` ("직박구리와 먹이가 같은 새 중에서 숲에 사는 종") -> `categories: ["paraphrase"]`
  3. 그리고 진정한 대조 질의(서식지 같고 먹이 다름)인:
     - `GGQ-H-018` ("고방오리와 서식 환경이 같고 먹이 범주가 다른 새") -> `categories: ["contrastive"]`
     - `GGQ-H-019` ("서식지는 쇠오리와 겹치지만 먹이는 다른 새") -> `categories: ["paraphrase"]`
     - `GGQ-H-020` ("박새랑 같은 서식 환경에 살지만 식성이 다른 새") -> `categories: ["paraphrase"]`
- **권고 사항**:
  - H-015의 `categories`를 `["paraphrase"]`로 수정.
  - (선택) H-018, H-019, H-020을 일관되게 `["contrastive"]`로 묶거나 `["paraphrase"]`로 통일.

---

### [후보 4] GGQ-H-039 & GGQ-H-040: `ambiguity: ["other"]` 분류의 모호성

- **질문**:
  - `GGQ-H-039`: `"그중에서 먹이가 다른 새는?"` -> `ambiguity: ["other"]`
  - `GGQ-H-040`: `"참새목 새 중 어떤 새가 좋아?"` -> `ambiguity: ["other"]`
- **문제점 및 근거**:
  1. H-039는 **대명사/앞선 대화 맥락 부재(anaphora / missing context)** 및 **비교 기준 종 부재(missing anchor species)** 문제입니다.
  2. H-040은 **주관적 선호/평가 기준 결여(subjective / missing objective criteria)** 문제입니다.
  3. 서로 완전히 다른 실패 원인을 포괄적인 `"other"` 문자열 하나로 묶어둘 경우, 향후 평가 시 분류기가 어떤 모호성을 감지해야 하는지 정량 평가하기 어렵습니다.
- **권고 사항**:
  - H-039: `ambiguity: ["anaphora"]` 또는 `["missing_context"]`, `["missing_species"]`
  - H-040: `ambiguity: ["subjective"]` 또는 `not_graph`로 전환.

---

## 3. 스키마 및 경계 처리 권고사항 (Schema & Policy Clarifications)

### [권고 1] GGQ-H-031 ~ H-033: `unsupported` 질의에서의 개체 슬롯(species) 추출 정책 명시

- **현황**:
  - `GGQ-H-031` ("박새와 실제로 공존하는 새") -> `species: []`, `unsupported: ["co_occurrence"]`
  - `GGQ-H-032` ("쇠오리와 진화적으로 가장 가까운 새") -> `species: []`, `unsupported: ["evolutionary_distance"]`
  - `GGQ-H-033` ("직박구리를 잡아먹는 새 종류") -> `species: []`, `unsupported: ["predation"]`
  - 반면 `GGQ-H-034` ("참새목 열매 먹는 새를 많이 먹는 순서로 정렬해줘") -> `rank: "참새목"`, `diet: "fruit_share"`, `unsupported: ["ranking"]`
- **검토 의견**:
  - H-031, H-032, H-033 질문에는 명확히 조류 종 개체명("박새", "쇠오리", "직박구리")이 등장합니다.
  - 의미 구조 파서(Semantic Parser)가 엔티티 인식(NER) 단계에서 종을 정확히 추출하더라도, gold expected에 `species: []`로 적혀 있으면 엔티티 추출 평가에서 오답으로 처리될 위험이 있습니다.
  - **정책 제안**:
    - 질의 유형(`kind`)이 `null`이더라도 추출된 개체명은 보존할 것인지(`species: ["박새"]`), 아니면 지원되지 않는 관계일 경우 모든 슬롯을 비우는 규칙인지 스키마 규칙에 명시 필요.

---

### [권고 2] GGQ-H-022: `specific_plant: "같은 열매"` 슬롯 값의 성격

- **질문**: `"숲에 사는 새 중 박새랑 같은 열매를 먹는 새를 알려 주세요"`
- **현재 expected**: `specific_plant: "같은 열매"`, `disposition: "insufficient_data"`
- **검토 의견**:
  - H-021의 `"산수유"`, H-023의 `"마가목"`은 구체적 식물 분류군(botanical taxon) 이름입니다.
  - 반면 H-022의 `"같은 열매"`는 식물명이 아니라 기준 종과의 섭식 공유를 나타내는 관계적 명사구입니다.
  - RobinGraph의 `_PATTERNS` 상으로도 패턴 96/97은 `같은 열매` 패턴이고, 패턴 98이 `(?P<plant>[가-힣]+) 열매`로 분리되어 있습니다.
  - `specific_plant` 슬롯에 식물명 외에 구문 표현(`"같은 열매"`)이 들어가는 것이 허용되는지 스키마에 정의하거나, `relation: "same_fruit"` 등으로 슬롯을 분리하는 방안 검토 권장.

---

### [권고 3] GGQ-H-010: `group: "오리"`의 계통 상위분류 검증 정책 유지 확인

- **질문**: `"한국에서 기록된 오리 중 쇠오리하고 같은 속인 종은?"`
- **현재 expected**: `group: "오리"`, `disposition: "answer"`
- **검토 의견**:
  - H-028 ("몸집이 작은"), H-030 ("텃새") 등은 지원 외 조건으로 `residual`에 담겨 `clarify` 처리되는 반면, H-010의 `"오리"`는 정식 슬롯 `group: "오리"`로 파싱되어 `answer`로 허용됩니다.
  - 이는 `graph_questions.py` line 421-429의 상위분류 검증 로직(`confirmed = next((item for item in lineage.items if item.rank in ('order', 'family', 'genus') and _group_label(item) == parsed.group), None)`)과 정확히 일치하며 타당합니다.
  - 따라서 H-010의 현재 주석은 적절하며, "기준 종의 목·과·속 명칭과 일치하는 수식어만 허용된다"는 점이 백로그/평가 기준에 잘 반영되어 있습니다.

---

### [권고 4] GGQ-H-012: `diet: "tree_fruit_share"`와 직전 픽스 정책의 일치성

- **질문**: `"나무 열매를 먹는 새를 참새목에서 찾아줘"`
- **현재 expected**: `diet: "tree_fruit_share"`, `disposition: "answer"`, `rank: "참새목"`
- **검토 의견**:
  - 2026-10-22 완료된 나무열매 라우팅 픽스의 핵심 원칙인 "나무열매는 일반 열매 검색으로 조회하되 `tree_fruit_share` 기준을 보존하고 제목에 `(나무·풀 구분 없음)` 및 limitations를 추가한다"는 정책과 완벽히 부합합니다.
  - `fruit_share`(H-011), `tree_fruit_share`(H-012), `frugivore`(H-013)의 3자 구분이 매우 명확하게 반영되어 있습니다.

---

## 4. 전체 40개 항목 전수 검토 매트릭스 (Evaluation Matrix)

| ID | 질문 원문 | 현재 kind | 현재 disp | 검토 결과 | 비고 및 권고사항 |
|:---|:---|:---|:---|:---:|:---|
| GGQ-H-001 | 박새와 쇠박새의 공통 상위 분류군을 알려 주세요 | common_taxonomy | answer | ✅ 정상 | 명확한 상위분류 질의 |
| GGQ-H-002 | 쇠오리랑 고방오리의 분류 경로를 비교해 주세요 | common_taxonomy | answer | ✅ 정상 | 분류 경로 비교 질의 |
| GGQ-H-003 | 흰뺨검둥오리와 청둥오리는 분류상 공통점이 뭐니? | common_taxonomy | answer | ✅ 정상 | 분류상 공통점 질의 |
| GGQ-H-004 | 까치하고 직박구리는 어떤 관계인지 알고 싶어요 | common_taxonomy | answer | ✅ 정상 | '어떤 관계' -> 분류 관계 매핑 적절 |
| GGQ-H-005 | 박새랑 같은 속에 속하는 새는 어느 종들이 있나요? | same_genus | answer | ✅ 정상 | 표준 same_genus 질의 |
| GGQ-H-006 | 같은 속인 새를 찾아 줘, 기준은 쇠오리야 | same_genus | answer | ✅ 정상 | 어순 도치 paraphrase 케이스 |
| GGQ-H-007 | 고방오리하고 같은 속인 새들이 궁금해 | same_genus | answer | ✅ 정상 | 표준 same_genus 질의 |
| GGQ-H-008 | 국내에 기록된 박새와 같은 속의 종은 뭐가 있어요? | korea_same_genus | answer | ✅ 정상 | 국내 기록 한정 same_genus |
| GGQ-H-009 | 고방오리와 같은 속 중 한국에 기록된 종을 보여 주세요 | korea_same_genus | answer | ✅ 정상 | 어순 변형 korea_same_genus |
| GGQ-H-010 | 한국에서 기록된 오리 중 쇠오리하고 같은 속인 종은? | korea_same_genus | answer | ✅ 정상 | group='오리' 계통 검증 일치 |
| GGQ-H-011 | 참새목에서 열매 먹는 새는 어떤 종류가 있는지 알려 주세요 | order_fruit | answer | ✅ 정상 | diet='fruit_share' 적절 |
| GGQ-H-012 | 나무 열매를 먹는 새를 참새목에서 찾아줘 | order_fruit | answer | ✅ 정상 | diet='tree_fruit_share' 직전 픽스 계약 일치 |
| GGQ-H-013 | 참새목에 속하는 과실식 새들이 궁금합니다 | order_fruit | answer | ✅ 정상 | diet='frugivore' (AVONET Niche) 적절 |
| GGQ-H-014 | Passeriformes 새 중 열매를 먹고 사는 새를 보여 주세요 | order_fruit | answer | ✅ 정상 | 학명 목 이름(Passeriformes) 처리 적절 |
| GGQ-H-015 | 습지에 사는 새 중 쇠오리와 같은 먹이 범주를 공유하는 새 알려 주세요 | habitat_shared_diet | answer | ⚠️ 재검토 | categories가 `["contrastive"]`로 잘못 표기됨 -> `["paraphrase"]` 권장 |
| GGQ-H-016 | 숲에서 사는 새 가운데 박새랑 식성이 같은 새를 찾아 줘 | habitat_shared_diet | answer | ✅ 정상 | '숲에서...가운데' 구어 표현 처리 적절 |
| GGQ-H-017 | 직박구리와 먹이가 같은 새 중에서 숲에 사는 종이 궁금해 | habitat_shared_diet | answer | ✅ 정상 | 서식지 조건 후치 변형 적절 |
| GGQ-H-018 | 고방오리와 서식 환경이 같고 먹이 범주가 다른 새를 보여 주세요 | habitat_different_diet | answer | ✅ 정상 | habitat='target', relation='different' 적절 |
| GGQ-H-019 | 서식지는 쇠오리와 겹치지만 먹이는 다른 새들이 있을까요? | habitat_different_diet | answer | ✅ 정상 | 어순/연결어미 변형 적절 |
| GGQ-H-020 | 박새랑 같은 서식 환경에 살지만 식성이 다른 새가 궁금해 | habitat_different_diet | answer | ✅ 정상 | 식성 표현 변형 적절 |
| GGQ-H-021 | 참새목 새 중 산수유 열매를 먹는 새는 어느 종이 있나요? | specific_fruit | insufficient_data | ✅ 정상 | 특정 식물(산수유) -> 자료 부족 처리 적절 |
| GGQ-H-022 | 숲에 사는 새 중 박새랑 같은 열매를 먹는 새를 알려 주세요 | specific_fruit | insufficient_data | 💡 제언 | specific_plant='같은 열매' 슬롯 정의 확인 권장 |
| GGQ-H-023 | 참새목 중 마가목 열매를 먹고 사는 새는 뭐가 있습니까? | specific_fruit | insufficient_data | ✅ 정상 | 특정 식물(마가목) -> 자료 부족 처리 적절 |
| GGQ-H-024 | 참새목 중 열매를 안 먹는 새를 알려 주세요 | order_fruit | clarify | ✅ 정상 | 미지원 부정 조건('안 먹는') 보류 적절 |
| GGQ-H-025 | 박새 말고 같은 속인 새가 뭐가 있나요? | same_genus | clarify | ⚠️ 재검토 | '말고'는 peer 제외(peer.id <> target_id)와 일치하므로 answer 검토 필요 |
| GGQ-H-026 | 참새목에서 과실식이 아닌 새들이 궁금해 | order_fruit | clarify | ✅ 정상 | 미지원 부정 조건('아닌') 보류 적절 |
| GGQ-H-027 | 참새목 중 겨울에 열매를 먹는 새를 보여 줘 | order_fruit | clarify | ✅ 정상 | 미지원 계절 조건('겨울에') 보류 적절 |
| GGQ-H-028 | 참새목 중 열매를 먹는 몸집이 작은 새는? | order_fruit | clarify | ✅ 정상 | 미지원 체구 조건('몸집이 작은') 보류 적절 |
| GGQ-H-029 | 숲에 사는 새 중 박새와 먹이가 같은 멸종위기인 새는? | habitat_shared_diet | clarify | ✅ 정상 | 미지원 보전 상태('멸종위기인') 보류 적절 |
| GGQ-H-030 | 고방오리와 서식지가 겹치고 먹이가 다른 텃새는? | habitat_different_diet | clarify | ✅ 정상 | 미지원 이동성('텃새') 보류 적절 |
| GGQ-H-031 | 박새와 실제로 공존하는 새를 찾아 주세요 | null | unsupported | 💡 제언 | unsupported='co_occurrence' 적절. species 슬롯 추출 정책 확인 권장 |
| GGQ-H-032 | 쇠오리와 진화적으로 가장 가까운 새가 뭐야? | null | unsupported | 💡 제언 | unsupported='evolutionary_distance' 적절. species 슬롯 정책 확인 권장 |
| GGQ-H-033 | 직박구리를 잡아먹는 새 종류를 보여줘 | null | unsupported | 💡 제언 | unsupported='predation' 적절. species 슬롯 정책 확인 권장 |
| GGQ-H-034 | 참새목 열매 먹는 새를 많이 먹는 순서로 정렬해줘 | order_fruit | unsupported | ✅ 정상 | order_fruit 기본형에 unsupported='ranking' 정확히 반영 |
| GGQ-H-035 | 박새의 학명이 궁금합니다 | null | not_graph | ✅ 정상 | 단일 종 프로필 질의(not_graph) 적절 |
| GGQ-H-036 | 쇠오리의 서식 환경을 알려 주세요 | null | not_graph | ✅ 정상 | 단일 종 서식지 질의(not_graph) 적절 |
| GGQ-H-037 | 직박구리는 무엇을 먹고 살아? | null | not_graph | ✅ 정상 | 단일 종 먹이 질의(not_graph) 적절 |
| GGQ-H-038 | 오늘 서울 날씨는 어때? | null | not_graph | ✅ 정상 | 도메인 외 일반 질의(not_graph) 적절 |
| GGQ-H-039 | 그중에서 먹이가 다른 새는? | null | clarify | ⚠️ 재검토 | ambiguity='other' 대신 'anaphora'/'missing_context' 구체화 권장 |
| GGQ-H-040 | 참새목 새 중 어떤 새가 좋아? | null | clarify | ⚠️ 재검토 | 주관적 선호 질의이므로 clarify보다 not_graph 분류 타당 |

---

## 5. 결론 및 Root 반영을 위한 권고 요약

1. **즉시 수정 권고 (Errata)**:
   - `GGQ-H-015`: `categories`를 `["contrastive"]` -> `["paraphrase"]`로 수정.
   - `GGQ-H-040`: 주관적 질의이므로 `disposition`을 `"clarify"` -> `"not_graph"`로 수정 (또는 `unsupported: ["subjective"]`).
2. **정책 결정 권고 (Policy Decision)**:
   - `GGQ-H-025` ("박새 말고 같은 속인 새"): 한국어 구어에서 "말고"가 피어(peer) 제외와 동의어로 쓰이며 Cypher의 `WHERE peer.id <> $target_id`와 일치하므로 `answer` 허용 여부를 결정.
   - `GGQ-H-031 ~ H-033`: `unsupported` 질의에서 질문 내 언급된 조류 종(`species`)을 슬롯에 추출해 둘지(`["박새"]`), 비워둘지(`[]`) 통일.
   - `GGQ-H-039`: `ambiguity` 분류를 `"other"`에서 구체적 사유(`"anaphora"`, `"missing_context"`)로 세분화.
3. **상태 관리**:
   - 본 검토 결과는 Root(사용자/총괄)가 최종 판단하여 `holdout.jsonl`에 반영할 수 있도록 `/tmp/rg204-writer-gold-review.md`로 격리 유지하며, 인간 검토가 완료되기 전까지 `review_status`는 `human_reviewed`로 승격하지 않습니다.
