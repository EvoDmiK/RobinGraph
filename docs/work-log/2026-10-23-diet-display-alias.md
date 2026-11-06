---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: RG-210
tags:
  - worklog
  - robingraph
  - diet-alias
  - display-name
  - species-traits
---

# [RG-210 / 검색·UI] 먹이 표시명 개선: 곤충(원자료: 무척추동물) 및 고기(척추동물 성분 합계) 대표 표시화 — 2026-10-23

> **문서 상태: 검증 완료 (사용자 어제 요청 무척추동물➔곤충, 척추동물➔고기 표시명 변경 누락 지적 반영; 이전 RG-209 먹이 세분화 안내의 사용자 의도 오해를 정정하고 정식 후속 개선 추진 완료; Python 173/173 및 Node 315/315 단위 테스트 통과; 실제 TEST 배포 및 34건 live API 24/24 통과, 독립 DB 오라클 실사 0오류, 6개 브라우저 반응형 시나리오 전원 통과; 원본 496 데이터셋 기대값 불변, 원천 DB 수정 없음, 운영 미배포, Git commit/push 없음, 조류 DB 쓰기 0건)**  
> 2026-10-23 사용자로부터 어제 요청되었던 먹이 표시명 변경(`무척추동물 ➔ 곤충`, `척추동물 ➔ 고기`)이 누락되었다는 지적이 인입되었다.  
> 직전 RG-209(먹이 세분화 안내) 작업에서는 사용자의 질의 의도를 "데이터베이스에 없는 세부 곤충 종 목록 요청"으로 오해하여, 곤충을 미지원 먹이로 분류하고 단순 clarify 대신 상위 범주(무척추동물)로 대체 질문을 유도하는 과도기적 우회 안내를 적용했었다. 그러나 사용자의 실제 요구사항은 **원천 데이터(EltonTraits 10개 범주)는 그대로 보존하되, 사용자 대면 화면 및 질의 해석에서 친숙한 대표 명칭('곤충', '고기')으로 표시 및 질의할 수 있도록 매핑**하는 것이었다.  
> 이에 따라 원자료의 학술적 정확성과 거버넌스를 엄격히 유지하면서, 사용자 편의성을 극대화하는 정식 표시명 개선 작업을 완료하였다.  
> Claude(백엔드 4개 파일 및 tests 2개 패치)와 Codex(UI 및 통합 대행, tests 3개 추가)를 통해 핵심 구현을 완료하고, 단위 테스트(Python 173건, Node 315건) 통과 후 실제 TEST 컨테이너(`robingraph-api:test-taxonomic-traits-43fa2e4bcfd5`) 배포를 완료하였다.  
> 공개 TEST 환경에서 34건 HTTP(24개 논리 검증) API 전수 통과, 독립 DB 오라클 28쿼리 집합 실사(115개 고유 반환 종, 411개 조건 지지 무오류 검증), Playwright 모바일(390px) 및 데스크톱(1280px) 6개 시나리오 전원 통과(왜가리 프로필: 물고기 60%·곤충 20%·고기 20% 실사 확인)를 완결하였다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 인입** | 먹이 표시명 누락 지적 및 의도 명확화 | 사용자 지적: 어제 요청한 `무척추동물 ➔ 곤충`, `척추동물 ➔ 고기` 표시명 변경 반영 요구.<br>이전 RG-209의 "미지원 먹이 안내"는 의도 오해에 따른 과도기 조치였음을 명시하고 본 작업으로 완전 정정 |
| **원자료 및 매핑 원칙** | 원천 데이터 보존 + 대표 표시명화 | - **원자료 보존**: Neo4j/Postgres DB 및 EltonTraits 10대 범주 원천 데이터는 일체 수정하지 않음<br>- **곤충**: `invertebrate`의 대표 표시명으로 매핑하되, 화면에 "원자료: 무척추동물 (곤충 외 무척추동물 포함)" 안내 병기<br>- **고기**: 3개 척추동물 성분(`endotherm_vertebrate` + `ectotherm_vertebrate` + `unknown_vertebrate`)의 합산 표시명으로 매핑. `물고기(fish)` 및 `사체(carrion)`는 별도 분리 유지 |
| **양방향 질의 지원** | 대표어 및 원천어 동시 지원 | 사용자가 새로운 대표어(`곤충`, `고기`)로 질문하든 기존 학술어(`무척추동물`, `척추동물`)로 질문하든 동일한 조건으로 동등하게 파싱·조회 |
| **백엔드 구조 개선 (Claude)** | retrieval, 프로필, 질의 해석 연동 (backend 4개 파일) | 1) `species_profile.py`: `VALUES` 내 `곤충 (원자료: 무척추동물)`, `고기` 표시명 갱신 및 `SOURCE_CATEGORY` 역매핑 정의 (단독 '고기 (원자료: 척추동물)'는 BirdBase 레이블임)<br>2) `birdbase.py`: `DIET_LABELS` 내 `Vertebrate: '고기 (원자료: 척추동물)'` 동기화<br>3) `graph_questions.py`: `FOOD_GAPS`에서 `곤충` 제거(데이터 키 승격), `SHARE_SCOPE` 설명 문구 신설<br>4) `graph_condition_extractor.py`: `_trait_surfaces`를 통해 새 대표어(`곤충`, `고기`)와 기존 원천어(`무척추동물`, `척추동물`) 모두 질의 추출 지원 |
| **프런트엔드 UI 개선 (Codex)** | `chat.js` 먹이 렌더링 개선 | - `DISTRIBUTION_LABELS` 및 `DIET_ICONS` 레이블 갱신 (무척추동물 ➔ 곤충, 척추동물 ➔ 고기)<br>- 물고기(`fish`)가 척추동물 하위 묶음 아이콘으로 중복 렌더링되던 레거시 로직 제거(독립 아이콘 유지)<br>- `buildDietLegend` 상세 박스(`details.species-diet-legend`) 및 그래프 안내/상세 표시 영역에 곤충(양수 무척추동물 비율 범주 포함) 및 고기(3종 합산) 표시 기준 설명문 추가 (tooltip 추가 아님)<br>- AGY 터미널 환경 장애로 UI 실행 불가하여 Codex가 UI 수정 및 Node 테스트 대행 |
| **단위 테스트 검증** | Python 173건 & Node 315건 통과 (실제 변경 tests 5개) | - 실제 변경 테스트 5개: `test_taxon_traits.py`, `test_taxon_traits_api.py`, `test_species_profile.py`, `test_graph_condition_extractor.py`, `frontend/chat_ui.test.js` (`test_birdbase_traits.py`는 실행만 되었으며 변경 없음)<br>- Python 포커스 스위트: **173 / 173 통과** (1.763s, mock/fixture)<br>- Node 프런트엔드 스위트: **315 / 315 통과** (244.7ms, `chat_ui.test.js`) |
| **골드 데이터셋 정책** | 불변 원칙 준수 | 별도 튜닝셋([`data/eval/graph_questions/tuning.jsonl`](../../data/eval/graph_questions/tuning.jsonl))의 원본 `GGQ-T-049` gold 기대값은 불변 보존(496 Native 데이터셋 소속 아님). 단위 테스트에서 구정책 채점을 제외하고 새 정책 `invertebrate exactcondition`으로 검증 |
| **TEST 배포 및 활성화** | 점진적 안전 전환 검증 | snapshot 이미지 `robingraph-api:test-taxonomic-traits-43fa2e4bcfd5` 빌드 ➔ shadow 모드 레거시 7건 대조(diff 0) ➔ `activation-gates.json` 통과 ➔ active 모드 전환.<br>release source snapshot manifest 207개 파일 해시 검증 및 root manifest 207개 일치 (`final-state.json`). 실행 중인 컨테이너 내부 소스 실측은 114개 파일 불일치 0건 (`container-source-check.json`, Docker runtime 전체 207개 실측이 아님) |
| **live TEST API 검증** | 34건 HTTP / 24개 논리 검증 통과 | **24 / 24 (100%) 통과** ([`after.json`](../verification/assets/2026-10-23-diet-display-alias/after.json)):<br>- 10쌍(5개 분류군 계급 × 곤충/무척추동물, 고기/척추동물) 동등성 검증 100% 일치<br>- 까마귀과 곤충: scoped 135 / evaluable 100 / matched 98, 고기: matched 68<br>- 14건 경계·부정·미지원 질의: **4건 clarify, 2건 guidance, 8건 query** 정합성 확인<br>- 하네스 보정: 초기 테스트 하네스가 고기 설명에 '원자료' 문자열을 강제하여 4개 고기 질의 설명 검사에서 4건 실패(`raw_scope_not_explained`)했던 오류를 수정한 후 동일 응답 재검증으로 24통과 확인 (`after-first-check.json` 보존, 앱 실패 아님) |
| **독립 DB 오라클 실사** | 실제 TEST DB 직접 대조 | **28개 쿼리 집합 범위/건수 100% 일치** ([`db-evidence.json`](../verification/assets/2026-10-23-diet-display-alias/db-evidence.json)):<br>- 3개 척추동물 성분의 OR 조건 및 전체 반환 멤버/범위/건수 검증 (115개 고유 종, 411개 조건 지지 레코드, 오류 0건, `bird_db_writes: 0`). API 표기 합계 숫자 전수 대조가 아니며 sum 표시는 Python fixture 및 실제 왜가리 카드로 실사 검증<br>- 하네스 보정: 초기 오라클이 '물고기'의 '고기' 부분 문자열을 meat로 오인 분류하던 오류를 longest-token 매핑으로 수정한 후 동일 응답 재검증으로 무오류 확인 (`db-evidence-first-check.json` 보존, 앱 실패 아님) |
| **브라우저 QA (Playwright)** | 모바일 및 데스크톱 렌더링 실사 | Chromium 390px 및 1280px 각 3개 시나리오(총 6개) 전원 통과 ([`browser.json`](../verification/assets/2026-10-23-diet-display-alias/browser.json)):<br>- 곤충 질의, 고기 질의, 왜가리 프로필(물고기 60%·곤충 20%·고기 20%) 실사 확인<br>- Playwright `pageerror` 0건, 수평 오버플로 없음 (`overflow: false`), 응답 모킹 없음 (`response_mocking: false`)<br>- 스크린샷 6건 확보. `physical_mobile: false` (실제 맥 기기 모바일, Safari, Firefox 미실행이며 Chromium 모바일/데스크톱 뷰포트 에뮬레이션 환경임) |
| **코드 지식 그래프 갱신** | AST-only 동기화 완료 | 7,889 노드, 17,003 엣지, 439 커뮤니티 graphify 갱신 완료 ([`graphify.log`](../verification/assets/2026-10-23-diet-display-alias/graphify.log)) |
| **거버넌스 및 안전 상태** | 무영향 원칙 준수 | 과거 496건 평가 결과 불변 보존 (과거 1.0 정확도를 본 변경에 재사용 주장 금지), 원본 Native 496 데이터셋 기대값 불변 (별도 tuning.jsonl의 구정책 케이스 `GGQ-T-049`는 superseded 처리), 원천 조류 DB 쓰기 0건(`bird_db_writes: 0`), 운영 미배포, Git commit/push 0건 |

---

## 1. 배경 및 사용자 요구사항 명확화

### 1) 사용자 인입 배경
- **일시**: 2026-10-23
- **피드백 내용**: 어제 요청했던 `무척추동물 ➔ 곤충`, `척추동물 ➔ 고기` 표시명 변경 작업이 누락되었음을 지적.

### 2) 이전 작업(RG-209)의 의도 오해와 정정
- **이전 작업(RG-209)의 한계**:
  - 사용자 TEST 모바일 화면에서 "까마귀과 중에서 곤충을 먹는 새는?" 질의가 clarify 처리된 것에 대해, 초기 분석에서는 "DB에 곤충 단위 데이터가 없으므로 곤충을 먹이 조건으로 질의할 수 없다고 안내해야 한다"고 판단함.
  - 이에 따라 `unsupported_food_answer`를 통해 "자료에 곤충이 없으니 상위 범주인 무척추동물로 질문해 달라"는 우회 안내를 적용했음.
- **사용자 실제 의도 명확화**:
  - 사용자의 실제 요구사항은 **일반 대중이 직관적으로 이해할 수 있는 단어인 '곤충'과 '고기'를 대표 표시명으로 제공하되, 원천 데이터의 학술적 범주(무척추동물, 척추동물 3종)를 보존**하는 것이었음.
  - 즉, 곤충을 질의에서 배제하는 것이 아니라, `invertebrate`를 화면에 '곤충'으로 보여주고 '곤충을 먹는 새' 질의 시 `invertebrate` 조건으로 직접 검색되게 하기를 원했던 것임.
- **문서 거버넌스 처리**:
  - 이전 작업 문서 [2026-10-23-food-granularity-guidance.md](./2026-10-23-food-granularity-guidance.md)는 당시의 의사결정 및 검증 이력으로서 영구 보존하고, 상단에 후속 링크 콜아웃을 추가함.
  - 본 작업(RG-210)을 통해 정식 표시명 별칭(alias) 매핑 및 UI/라우팅 통합을 완결함.

---

## 2. 데이터 및 생물학적 정합성 가드레일

### 1) 원천 데이터 보존 원칙
- **원자료 무변경**: Neo4j 노드/관계 및 PostgreSQL 원천 데이터(EltonTraits 10개 범주)는 일체 수정하지 않음.
- 내부 계산 및 저장소 키(`invertebrate`, `endotherm_vertebrate`, `ectotherm_vertebrate`, `unknown_vertebrate`, `fish`, `carrion` 등)는 100% 동일하게 유지됨.

### 2) 곤충 (원자료: 무척추동물) 매핑
- **표시명 정의**: `invertebrate`의 한국어 대표 표시명을 `곤충 (원자료: 무척추동물)`로 정의.
- **검색 및 단축어**: 단축어 `곤충`을 등록하여 `"까마귀과 중에서 곤충을 먹는 새는?"` 질의 시 `diet_distribution.invertebrate > 0` 조건으로 직접 매핑.
- **섭식 범위 명시 (App Scope)**: 단순히 '곤충만 먹는 새'가 아니라 **양수(0보다 큰) 무척추동물 비율 범주를 포함**함 (거미, 지렁이, 달팽이 등 비곤충 무척추동물 포함 및 잡식 조류처럼 다른 먹이와 병행 섭식하는 조류 모두 포함).
- **학술 안내 병기**: 결과 안내 텍스트 및 limitation에 *"원자료 범주는 ‘무척추동물’로, 곤충이 아닌 무척추동물을 먹는 경우도 포함합니다"*라는 설명을 반드시 포함하여 생물학적 왜곡을 방지.

### 3) 고기 (척추동물 성분 합계) 매핑
- **표시명 정의**: `고기`는 3개 척추동물 성분(`endotherm_vertebrate` + `ectotherm_vertebrate` + `unknown_vertebrate`)의 합산(`meat`)으로 정의.
- **어류 및 사체 분리**: `물고기(fish)`와 `사체(carrion)`는 섭식 생태가 구별되므로 고기 합산에 포함하지 않고 별도의 독립 범주로 유지.
- **설명 문구 병기**: *"고기는 온혈 척추동물·변온 척추동물·기타 척추동물 성분 중 하나라도 0보다 큰 경우이며, 물고기·사체 성분은 포함하지 않습니다"*를 명시.

### 4) 양방향 검색 동등성 (Dual Searchability)
- 사용자가 새로운 대표어(`곤충`, `고기`)로 질문하든 기존 원천 학술어(`무척추동물`, `척추동물`)로 질문하든, 동일한 데이터베이스 쿼리와 조건으로 해석되어 100% 동등한 결과(items, coverage, conditions)를 반환하도록 설계.

---

## 3. 아키텍처 및 구현 세부 사항

### 1) 파일 수정 및 역할 분담
- **Claude 패치 (앱 백엔드 4개 + 테스트 2개 파일)**:
  - `src/robingraph/retrieval/species_profile.py`: `VALUES` 내 `곤충 (원자료: 무척추동물)`, `고기` 표시명 갱신 및 `SOURCE_CATEGORY` 역매핑 신설 (단독 '고기 (원자료: 척추동물)'는 BirdBase 레이블임)
  - `src/robingraph/retrieval/birdbase.py`: `DIET_LABELS` 내 `Vertebrate: '고기 (원자료: 척추동물)'` 동기화
  - `src/robingraph/retrieval/graph_questions.py`: `FOOD_GAPS`에서 곤충 제거(데이터 키 승격), `SHARE_SCOPE` 설명 문구 신설, `_short_word()` 구현
  - `src/robingraph/retrieval/graph_condition_extractor.py`: `_trait_surfaces()`에서 대표어 및 원천어 동시 등록, `_UNSUPPORTED` 규칙 갱신
  - `tests/test_taxon_traits.py`, `tests/test_species_profile.py`
- **Codex 통합 및 UI 대행 (앱 프런트엔드 1개 + 테스트 3개 파일)**:
  - `src/robingraph/api/static/chat.js`: 프런트엔드 먹이 라벨, 아이콘 및 `buildDietLegend` 상세 박스 갱신 (AGY 터미널 장애에 따라 Codex가 대행)
  - `tests/test_taxon_traits_api.py`, `tests/test_graph_condition_extractor.py`, `tests/frontend/chat_ui.test.js`
- **실제 변경된 테스트 5개 파일**:
  1. `tests/test_taxon_traits.py`
  2. `tests/test_taxon_traits_api.py`
  3. `tests/test_species_profile.py`
  4. `tests/test_graph_condition_extractor.py`
  5. `tests/frontend/chat_ui.test.js`  
  *(참고: `tests/test_birdbase_traits.py`는 테스트 스위트 실행에만 포함되었으며 변경되지 않았음).*

### 2) 백엔드 매핑 구현 세부 사항
```python
# species_profile.py
VALUES = {
    ...
    'Invertebrate': '곤충 (원자료: 무척추동물)',
    'VertFishScav': '고기·물고기·사체 (원자료: 척추동물·물고기·사체)',
    'Invertivore': '곤충 섭식 (원자료: 무척추동물 섭식)',
    'Vertivore': '고기 섭식 (원자료: 척추동물 섭식)',
    'invertebrate': '곤충 (원자료: 무척추동물)',
    'meat': '고기',
    'endotherm_vertebrate': '고기 (온혈 척추동물)',
    'ectotherm_vertebrate': '고기 (변온 척추동물)',
    'unknown_vertebrate': '고기 (기타 척추동물)',
    ...
}

# 단독 '고기 (원자료: 척추동물)'는 BirdBase의 DIET_LABELS['Vertebrate']에 정의됨
# birdbase.py
DIET_LABELS = {
    ...
    'Invertebrate': '곤충 (원자료: 무척추동물)',
    'Vertebrate': '고기 (원자료: 척추동물)',
    ...
}

SOURCE_CATEGORY = {
    'Invertebrate': '무척추동물', 'invertebrate': '무척추동물',
    'VertFishScav': '척추동물·물고기·사체', 'Invertivore': '무척추동물 섭식',
    'Vertivore': '척추동물 섭식', 'endotherm_vertebrate': '온혈 척추동물',
    'ectotherm_vertebrate': '변온 척추동물', 'unknown_vertebrate': '기타 척추동물'
}
```

```python
# graph_questions.py
FOOD_GAPS = {'벌레': ('invertebrate',), '곡식': ('seed',), '곡물': ('seed',), '꿀': ('nectar',),
             '잎': ('other_plant',), '육류': ('meat',)}

SHARE_SCOPE = {
    'invertebrate': "원자료 범주는 ‘무척추동물’로, 곤충이 아닌 무척추동물을 먹는 경우도 포함합니다.",
    'meat': ('고기는 온혈 척추동물·변온 척추동물·기타 척추동물 성분 중 하나라도 0보다 큰 경우이며, '
             '물고기·사체 성분은 포함하지 않습니다.')
}
```

```python
# graph_condition_extractor.py
def _trait_surfaces(name):
    if name == 'habitat':
        return {**{VALUES[v]: v for v in TRAIT_CONDITIONS[name][2]}, **HABITATS}
    values = TRAIT_CONDITIONS[name][2]
    # '곤충 (원자료: 무척추동물)'의 단축어 곤충 -> invertebrate, 고기는 meat 매핑
    short = {}
    for value in values:
        short.setdefault(VALUES[value].split(' (')[0], []).append(value)
    surfaces = {word: found[0] for word, found in short.items() if len(found) == 1}
    # 기존 원천 학술어(무척추동물, 척추동물 등)도 동시에 조회 가능하도록 등록
    surfaces.update({SOURCE_CATEGORY[v]: v for v in values if v in SOURCE_CATEGORY})
    return surfaces
```

### 3) 프런트엔드 UI 구현 세부 사항 (`chat.js`)
- `DISTRIBUTION_LABELS`: `invertebrate` ➔ `"곤충 (원자료: 무척추동물)"`, `endotherm_vertebrate` ➔ `"고기 (온혈 척추동물)"` 등 갱신.
- `DIET_ICONS`: `invertebrate` 레이블을 `"곤충"`, `vertebrate` 레이블을 `"고기"`로 갱신.
- 물고기(`fish`) 단독 섭식 조류에서 상위 척추동물 묶음 아이콘이 중복으로 생성되던 레거시 로직 제거.
- **설명 배치 위치**: scope 설명은 icon tooltip이 아니라, 먹이 범례 상세 박스(`buildDietLegend`, `details.species-diet-legend`) 및 그래프 질의 응답 상세 영역에 추가됨:
  > *"표시명 기준: 곤충은 원자료의 무척추동물 범주로, 곤충 외 무척추동물도 포함합니다. 고기는 온혈·변온·기타 척추동물 성분을 합친 표시이며, 물고기와 사체는 별도로 표시합니다."*

---

## 4. 단위 테스트 검증 결과

실제 실행된 단위 테스트 스위트 검증 결과는 아래와 같다:

### 1) Python 백엔드 포커스 단위 테스트
- **실제 실행 명령**:
  ```bash
  PYTHONPATH=tests uv run --locked --extra test python -m unittest \
    tests.test_taxon_traits \
    tests.test_taxon_traits_api \
    tests.test_graph_condition_extractor \
    tests.test_graph_intent_schema \
    tests.test_graph_semantic_router \
    tests.test_graph_questions \
    tests.test_graph_semantic_api \
    tests.test_species_profile \
    tests.test_birdbase_traits \
    tests.test_species_questions
  ```
- **검증 결과**: `Ran 173 tests in 1.763s — OK` ([`focused-python.log`](../verification/assets/2026-10-23-diet-display-alias/focused-python.log))
- **검증 내용**:
  - 곤충 및 고기 alias 추출 및 질의 라우팅
  - 원자료 무척추동물/척추동물 질의와의 동등성
  - 별도 `tuning.jsonl`의 `GGQ-T-049` 불변 gold 유지(496 Native 데이터셋 미포함) 및 구정책 채점 제외 후 새 정책 exact condition 검증
  - 모의 환경(mock/fixture) 기반 회귀 무결성 확인

### 2) Node 프런트엔드 단위 테스트
- **실제 실행 명령**:
  ```bash
  node --test tests/frontend/chat_ui.test.js
  ```
- **검증 결과**: `pass 315 / fail 0 / duration 244.7ms` ([`frontend.log`](../verification/assets/2026-10-23-diet-display-alias/frontend.log))
- **검증 내용**:
  - `buildGraphQueryAnswer` 및 먹이 아이콘 렌더링
  - 곤충/고기 레이블 및 `buildDietLegend` 상세 박스 표출
  - 종 목록 렌더링 무결성 및 XSS 방지 검증

---

## 5. TEST 배포 및 통합 검증 결과

### 1) 사전 상태 검증 (`before.json`)
- **실행 내용**: 배포 전 34건 HTTP 사전 검증 수행
- **결과**: 수정 전 상태에서 10쌍의 새 alias/raw 비교가 모두 불일치(미구현 상태)로 정상 재현됨 확인. (수정 전 엄격화 기준 이전 파일이므로 전체 통과율은 참고용임).

### 2) TEST 컨테이너 점진적 배포 (`test-release.json`, `deploy.log`, `final-state.json`)
- **대상 컨테이너**: `robingraph-api-test` (ARM64 Mac .97 TEST 환경)
- **배포 이미지**: `robingraph-api:test-taxonomic-traits-43fa2e4bcfd5`
- **소스 SHA-256**: `43fa2e4bcfd559b9262aff0d4b154f0f464f0b8f8f0fa7005fcb7efff6e4630c`
- **릴리스 디렉터리**: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-43fa2e4bcfd5-b7b54b`
- **매니페스트 및 소스 무결성 실측**:
  - `deploy-test-snapshot.py`가 release source snapshot의 207개 manifest 파일 해시를 검증했고, root manifest와도 207개 전수 일치 확인 (`source_manifest_files: 207`, `root_manifest_matches: true`, [`final-state.json`](../verification/assets/2026-10-23-diet-display-alias/final-state.json)).
  - 실제 실행 중인 컨테이너 내부 소스 실측([`container-source-check.json`](../verification/assets/2026-10-23-diet-display-alias/container-source-check.json)): `src`, `pyproject.toml`, `uv.lock`, `README.md` 등 114개 파일에 대해 불일치 0건 (`checked_files: 114, mismatches: []`). Docker runtime 전체 207개 실측이 아님(data/eval 등은 이미지 미포함).
- **점진적 전환 게이트**:
  1. `deploy-shadow`: shadow 모드로 배포 후 기존 레거시 7건 질의 대조 (`legacy-api-baseline.json` vs `legacy-api-shadow.json`). 지문(fingerprint) 차이 0건, DB 쓰기 0건 확인.
  2. [`activation-gates.json`](../verification/assets/2026-10-23-diet-display-alias/activation-gates.json): 게이트 전수 통과 (`all_passed: true`, shadow API 검증, 단위 테스트 173/315 통과, `fixture_network_none_smoke: true`, 운영 변경 0건 확인).
  3. `activate`: active 모드로 전환 완료 (`test-release.json`: `graph_intent_mode: "active"`).

### 3) live TEST API 34건 회귀 검증 (`verify-api.py` ➔ `after.json`)
실제 공개 TEST API(`https://robingraph-test.dove-nest.com/v1/chat`)를 대상으로 34건의 HTTP 요청을 수행하여 24개 논리 검증을 평가하였다.

#### 검증 결과 요약
- **결과**: **24 / 24 통과 (100% 합격)** ([`after.json`](../verification/assets/2026-10-23-diet-display-alias/after.json))
- **10쌍 alias/raw 동등성 검증 (5개 분류군 계급 × 2개 먹이 쌍, 20건 HTTP)**:
  - 참새목 (order), 까마귀과 (family), Corvus (genus), 청둥오리 (species), Anas platyrhynchos platyrhynchos (subspecies)
  - `곤충` vs `무척추동물`, `고기` vs `척추동물`의 결과 시그니처(`status`, `taxon`, `conditions`, `coverage`, `items`, `has_more`)가 100% 완전 일치함 확인.
  - 대표 수치:
    - 까마귀과 곤충: `scoped: 135`, `evaluable: 100`, `matched: 98` (무척추동물과 동일)
    - 까마귀과 고기: `matched: 68` (척추동물과 동일)
- **14건 경계·부정·복합 조건 검증 (14건 HTTP)**:
  - **4건 clarify**: 부정 2건(`곤충을 안 먹는`, `고기를 안 먹는`), 복합/수식어 2건(`곤충을 먹는 빨간 새`, `곤충을 먹으면서 경쟁하는 새`)
  - **2건 guidance**: 미지원 먹이(`곡물을 먹는 새`, `잎을 먹는 새`)
  - **8건 query**: 물고기, 사체, 열매, 씨앗, 서식지 결합(숲), 곤충 종 어떤 종이 있어, 곤충 중, 매목 고기
- **테스트 하네스 보정 내역 (앱 실패 아님)**:
  - 초기 API 검사 하네스 스크립트가 고기(`meat`) 설명 문구에 '원자료' 문자열을 강제하여 4개 고기 질의(참새목, 까마귀과, Corvus, 청둥오리)에 대한 설명 검사에서 4건의 실패(`raw_scope_not_explained`)가 발생했었음 ([`after-first-check.json`](../verification/assets/2026-10-23-diet-display-alias/after-first-check.json): 20 passed, 4 failed).
  - 고기는 3개 척추동물 성분의 합산이므로 개별 원자료 명칭 대신 합산 설명이 들어가는 것이 정상 사양임.
  - 하네스 오류만 수정하고 동일한 API 응답을 재검증(recheck)하여 24/24 전원 통과를 확인하였음 (`after-first-check.json` 보존, 앱 실패 아님).

### 4) 독립 DB 오라클 실사 (`verify-db.py` ➔ `db-evidence.json`)
활성 TEST DB(Neo4j 및 PostgreSQL)를 대상으로 독립된 오라클 스크립트를 통해 API 반환 결과의 팩트 무결성을 실사하였다.
- **검증 범위**: **3개 척추동물 성분의 OR 조건(온혈·변온·기타 척추동물 중 하나라도 > 0) 및 전체 반환 멤버/범위/건수 검증** (API 표기 합계 숫자 전수 대조가 아님. 합계 숫자는 Python fixture 및 실제 왜가리 카드로 실사 검증).
- **결과**: **28개 쿼리 집합 범위/매칭 건수 100% 일치, 오류 0건** ([`db-evidence.json`](../verification/assets/2026-10-23-diet-display-alias/db-evidence.json))
- **실사 통계**:
  - 검증된 고유 반환 분류군: **115개 종**
  - 검증된 조건 지지 레코드: **411개 레코드**
  - 조류 DB 쓰기: **0건 (`bird_db_writes: 0`)**
- **오라클 하네스 보정 내역 (앱 실패 아님)**:
  - 초기 독립 오라클 스크립트가 '물고기'의 부분 문자열인 '고기'를 `meat`로 오인 매핑하여 오류가 발생했었음.
  - 이를 longest-token 매핑(`물고기` 우선 인식)으로 보정하고 동일한 API 응답을 재검증하여 0오류 통과를 확인하였음 (`db-evidence-first-check.json` 보존).

### 5) Playwright 반응형 브라우저 검사 (`browser.cjs`, `browser.json`)
실제 공개 웹 브라우저 환경에서 렌더링 무결성을 실사 검증하였다.
- **도구**: Playwright (Headless Chromium)
- **검증 URL**: `https://robingraph-test.dove-nest.com/chat`
- **시나리오**: 2개 뷰포트(모바일 390px, 데스크톱 1280px) × 3개 질의 = **총 6개 시나리오 전원 통과 (6/6)** ([`browser.json`](../verification/assets/2026-10-23-diet-display-alias/browser.json))
  1. `"까마귀과 중에서 곤충을 먹는 새는?"`: answer 렌더링, 조류 카드 20개 노출 정상
  2. `"까마귀과 중에서 고기를 먹는 새는?"`: answer 렌더링, 조류 카드 20개 노출 정상
  3. `"왜가리에 대해 알고 싶어"` (프로필): 먹이 아이콘 렌더링 실사 확인  
     ➔ **`물고기 60%`, `곤충 20%`, `고기 20%`** 정상 표출 확인
- **품질 지표**:
  - 응답 모킹 없음 (`response_mocking: false`)
  - Playwright `pageerror` 이벤트: 0건
  - 수평 오버플로 없음 (`overflow: false`, `document.documentElement.scrollWidth <= innerWidth`)
- **스크린샷 증거 확보**:
  - 모바일(390px): [`query-곤충-390.png`](../verification/assets/2026-10-23-diet-display-alias/query-곤충-390.png), [`query-고기-390.png`](../verification/assets/2026-10-23-diet-display-alias/query-고기-390.png), [`profile-390.png`](../verification/assets/2026-10-23-diet-display-alias/profile-390.png)
  - 데스크톱(1280px): [`query-곤충-1280.png`](../verification/assets/2026-10-23-diet-display-alias/query-곤충-1280.png), [`query-고기-1280.png`](../verification/assets/2026-10-23-diet-display-alias/query-고기-1280.png), [`profile-1280.png`](../verification/assets/2026-10-23-diet-display-alias/profile-1280.png)
- **검증 환경 한계 명시**: `physical_mobile: false` (실제 맥 기기 모바일, Safari, Firefox는 미실행이며 Chromium 모바일/데스크톱 뷰포트 에뮬레이션 환경임).

### 6) 코드 지식 그래프 동기화
- **실행 내용**: AST 기반 코드 지식 그래프 갱신 완료
- **결과**: 7,889개 노드, 17,003개 엣지, 439개 커뮤니티 최신화 완료 ([`graphify.log`](../verification/assets/2026-10-23-diet-display-alias/graphify.log)).

---

## 6. 한계점 및 평가 자산 정책

1. **과거 496건 평가 자산 정책**:
   - 직전 MLflow GenAI Evaluate 496건 평가에서 달성된 1.0(100%) 정확도를 본 변경에 그대로 재사용하여 주장하지 않음.
   - 별도 튜닝 데이터셋([`data/eval/graph_questions/tuning.jsonl`](../../data/eval/graph_questions/tuning.jsonl))에 수록된 구정책(곤충 미지원 안내) 케이스 1건(`GGQ-T-049`)은 본 표시명 정책 개정에 의해 자연스럽게 대체(superseded)되었음. 이는 496건 Native 회귀 데이터셋 소속이 아니며, 두 평가 자산은 엄격히 분리 관리됨.
   - 원본 496건 평가 데이터셋의 기대값은 불변 보존되며, 이번 변경으로 496건 전체 재평가는 실행하지 않음.
2. **미등록 세부 먹이 어휘의 한계**:
   - `벌레`, `곡식`, `곡물`, `꿀`, `잎`, `육류`는 여전히 `FOOD_GAPS`를 통해 적절한 대체 범주 안내를 제공함.
   - `어류`는 `물고기(fish)`와의 동의어 매핑 과제로 분류되어 있으며 후속 과제로 관리됨.
   - `거미`, `지렁이` 등 표 밖 미등록 먹이 어휘 및 `곤충과 열매` 등 명사 병렬 연결 질의는 향후 확장 과제로 유지됨.

---

## 7. 형상 관리 및 거버넌스 준수

RobinGraph 작업 지침 및 안전 원칙을 철저히 준수하였다:
- **조류 DB 쓰기 0건**: 활성 TEST 및 Production Neo4j/PostgreSQL에 대한 쓰기 연산은 발생하지 않음 (`bird_db_writes: 0`).
- **운영(Production) 무영향**: Production NAS 환경 배포, 재시작, 이미지 교체 일체 없음 (`production_changed: false`).
- **Git 무영향**: 별도 지시 없이 `git commit` 및 `git push`를 수행하지 않음.
- **백로그 상태 무변경**: 기존 작업 백로그 상태를 임의로 조작하지 않음.

---

## 관련 문서 및 검증 자산

- **검증 자산 디렉터리**: [`../verification/assets/2026-10-23-diet-display-alias/`](../verification/assets/2026-10-23-diet-display-alias/)
  - [`focused-python.log`](../verification/assets/2026-10-23-diet-display-alias/focused-python.log) (Python 173/173 통과 영수증)
  - [`frontend.log`](../verification/assets/2026-10-23-diet-display-alias/frontend.log) (Node 315/315 통과 영수증)
  - [`test-release.json`](../verification/assets/2026-10-23-diet-display-alias/test-release.json) (TEST 배포 영수증, 이미지 해시 및 모드 이력)
  - [`final-state.json`](../verification/assets/2026-10-23-diet-display-alias/final-state.json) (최종 릴리스 매니페스트 및 형상 상태 영수증)
  - [`container-source-check.json`](../verification/assets/2026-10-23-diet-display-alias/container-source-check.json) (실행 중인 컨테이너 소스 114개 실측 영수증)
  - [`activation-gates.json`](../verification/assets/2026-10-23-diet-display-alias/activation-gates.json) (active 전환 게이트 영수증)
  - [`after.json`](../verification/assets/2026-10-23-diet-display-alias/after.json) (34건 live API 24/24 통과 영수증)
  - [`after-first-check.json`](../verification/assets/2026-10-23-diet-display-alias/after-first-check.json) (하네스 보정 전 1차 응답 보존 영수증)
  - [`db-evidence.json`](../verification/assets/2026-10-23-diet-display-alias/db-evidence.json) (독립 DB 오라클 28쿼리 무오류 영수증)
  - [`db-evidence-first-check.json`](../verification/assets/2026-10-23-diet-display-alias/db-evidence-first-check.json) (오라클 하네스 보정 전 1차 응답 보존 영수증)
  - [`browser.json`](../verification/assets/2026-10-23-diet-display-alias/browser.json) (Playwright 6개 시나리오 렌더링 결과)
  - [`query-곤충-390.png`](../verification/assets/2026-10-23-diet-display-alias/query-곤충-390.png), [`query-고기-390.png`](../verification/assets/2026-10-23-diet-display-alias/query-고기-390.png), [`profile-390.png`](../verification/assets/2026-10-23-diet-display-alias/profile-390.png) (모바일 스크린샷)
  - [`query-곤충-1280.png`](../verification/assets/2026-10-23-diet-display-alias/query-곤충-1280.png), [`query-고기-1280.png`](../verification/assets/2026-10-23-diet-display-alias/query-고기-1280.png), [`profile-1280.png`](../verification/assets/2026-10-23-diet-display-alias/profile-1280.png) (데스크톱 스크린샷)
  - [`graphify.log`](../verification/assets/2026-10-23-diet-display-alias/graphify.log) (AST 지식 그래프 갱신 영수증)
- **이전 작업 문서 (과거 의사결정 이력 보존)**: [`./2026-10-23-food-granularity-guidance.md`](./2026-10-23-food-granularity-guidance.md)
- **데이터셋 문서**: [`../../data/eval/graph_questions/taxonomic-regression-v1/README.md`](../../data/eval/graph_questions/taxonomic-regression-v1/README.md)
- **Obsidian 작업기록**: `Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-먹이-표시명-개선.md`

---
*문서 작성 완료 일시: 2026-10-23*  
*작성자: dev / Writer*
