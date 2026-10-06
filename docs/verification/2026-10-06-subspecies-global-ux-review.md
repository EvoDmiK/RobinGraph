# RobinGraph 전 아종(Subspecies) UX·데이터 커버리지 분석 및 범용 폴백 설계 보고서 — 2026-10-06

## 1. 요청 배경과 목표

### 1.1 배경 및 사용자 요구사항
최근 왜가리(`Ardea cinerea`)와 청둥오리(`Anas platyrhynchos`) 아종 카드에 대해 개별 종 단위의 하드코딩 패치가 진행되었다. 그러나 사용자는 **특정 종에 국한된 땜질식 개별 패치(species-specific patches)를 명확히 거부**하였으며, AviList에 수록된 모든 아종이 다음 기준을 충족하는 전역적(global) UX 및 데이터 커버리지를 가질 것을 요구했다:
1. **비학명 우선의 구별 가능한 표제(Distinguishable non-scientific-primary title)**: 학명 삼명법(trinomial)이 주 표제를 장악하지 않으면서도, 같은 종 내 각 아종 카드가 서로 명확히 구분되는 비학명 표제를 제공해야 한다.
2. **출처 기반의 분포 설명(Sourced range description)**: 임의 추정이 아닌 공식 출처에 기반한 고유 분포 정보를 제시해야 한다.
3. **통칭 우선순위 및 한국어 임의 작명 금지**: 검증된 한국어 통칭 > 검증된 영어 통칭 순으로 우선하되, 확인되지 않은 한국어 아종 통칭을 절대 임의로 지어내거나 기계 번역하지 않는다.
4. **학명 정체성 접힘(Scientific identity folded)**: 학명과 출처 링크는 화면에서 사라지는 것이 아니라 접을 수 있는 세부정보(`<details>`) 안에 안전하게 보존되어야 한다.
5. **분류 출처와 명칭/분포 출처의 분리**: 기본 분류 골격 출처(AviList)와 개별 명칭/분포 참조 출처를 UI와 데이터 모델에서 명확히 구분해야 한다.
6. **극단적 분포문 및 모바일 접근성 지원**: 수백 자에 달하는 장문 분포문, 미확인 분포 처리, 320px~390px 모바일 화면에서의 가로 넘침 방지와 스크린 리더 접근성을 보장해야 한다.

### 1.2 본 작업의 범위와 역할
- 본 작업은 **읽기 전용 조사 및 아키텍처 검토(Read-only review)** 작업이다.
- 소스 코드, 테스트 파일, 데이터베이스, 배포 환경에 대한 직접적인 변경이나 커밋은 수행하지 않으며, 상세 검토 보고서(`docs/verification/2026-10-06-subspecies-global-ux-review.md`) 작성을 통해 구현을 전담하는 코디네이터(Coordinator)에게 구체적인 데이터 근거와 설계안을 제공한다.

---

## 2. 원자료(AviList JSON) 및 DB 적재 현황 정량 분석

### 2.1 AviList v2025b 공식 스냅샷 정량 분석
RobinGraph가 고정(pin)하고 있는 공식 스냅샷(`https://explore.avilist.org/data/avilist-2025b.json`, SHA-256: `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`) 33,684행 전체를 정량 분석한 결과는 다음과 같다:

| 분류 계급(Rank) | 행 수 | 설명 |
|---|---|---|
| 목 (order) | 46 | 조류 상위 목 분류 |
| 과 (family) | 252 | 영문 과명 포함 |
| 속 (genus) | 2,376 | 속 분류군 |
| 종 (species) | 11,131 | 전 세계 공식 인정 조류 종 |
| **아종 (subspecies)** | **19,879** | **공식 인정 아종 전체** |
| **전체 (Total)** | **33,684** | **AviList v2025b 전체 레코드** |

### 2.2 아종 필드 가용성 정량 조사

| 필드명 | 데이터 위치 | 아종 가용 건수 | 가용률 | 비고 |
|---|---|---|---|---|
| `Range` (`range_text`) | Column 13 (N) | **19,879건** | **100.00%** | **모든 아종에 분포문이 100% 존재함** |
| `English_name_AviList` | Column 8 (I) | **0건** | **0.00%** | AviList 공식 영문 통칭은 아종에 미제공 |
| `English_name_Clements_v2025` | Column 9 (J) | **0건** | **0.00%** | Clements 영문 통칭 아종 레코드 미제공 |
| `English_name_BirdLife_v10` | Column 10 (K) | **0건** | **0.00%** | BirdLife 영문 통칭 아종 레코드 미제공 |
| 한국어 통칭 | 별도 수집 | **0건** | **0.00%** | AviList에는 한국어 열이 없으며 이번 검토에서 별도 한국어 아종명을 수집하지 않음 |

#### 주요 정량적 사실:
1. **아종 고유 분포문(Range)은 19,879개 아종 전체(100.00%)에 빠짐없이 존재한다.** 누락된 아종은 0건이다.
2. **AviList 기본 데이터에는 아종 수준의 영문 통칭이 전무(0.00%)하다.** 이는 데이터 누락이 아니라 국제 조류학 체크리스트가 원칙적으로 종 단위 영문 통칭만을 표준화하기 때문이다.
3. **분포문 길이 분포 통계**:
   - 최소 길이: 4자 (예: `Tachybaptus novaehollandiae javanicus` → `"Java"`, `Coccyzus merlini merlini` → `"Cuba"`)
   - 중앙값(Median): **59자**
   - 최대 길이: **542자** (`Psittacula krameri krameri`)
   - 세미콜론(`;`) 포함 비율: 약 28.4% (번식지와 월동지/도입지가 구분 서술됨)

### 2.3 동일 종 내 아종 분포문 구별성(Distinctiveness) 검증
전 세계 4,994개의 다아종 종(polytypic species, 2개 이상의 아종을 가진 종) 전체를 대상으로, 세미콜론 이전 첫 절(`raw.split(';')[0]`) 및 72자 절삭 텍스트를 기준으로 동일 종 내 중복 여부를 전수 조사했다.
- **결과: 동일 종 내에서 분포문 앞 절이 중복되는 아종은 0건(0.00%)이었다.**
- **결론**: AviList의 원문 분포문 첫 번째 절은 모든 다아종 종에 대해 이번 고정 스냅샷의 검사에서는 상호 구별된다. 새 릴리스나 다른 자료에 대해 이를 보장하지 않으므로 UI는 제목이 겹칠 때 번호를 추가한다.

### 2.4 라이선스 검토
- **출처**: AviList — The Global Avian Checklist v2025b
- **라이선스**: **Creative Commons Attribution 4.0 International (CC BY 4.0)**
- **이용 조건**: 저작자 표시("AviList: The Global Avian Checklist © 2026 by AviList Core Team") 하에 자유로운 공유, 복제, 수정 및 상업적/비상업적 데이터 임베딩 가능.
- **정책 판정**: RobinGraph의 데이터 라이선스 정책 상 `allowed`로 정상 등록되어 있음 (`config/collection-points.json`).

### 2.5 Neo4j 데이터베이스 현황
- `scripts/generate_n8n_reference_ingest.py` 분석 결과, n8n 수집 파이프라인에서 이미 19,879개 아종 노드(`Taxon:BirdTaxon {rank: 'subspecies'}`)에 `taxon.range_text = row.range_text`가 완전히 적재되어 있다.
- 따라서 **별도의 데이터베이스 마이그레이션이나 신규 크롤링 없이, 기존 DB의 읽기 쿼리(`SUBSPECIES_QUERY`)를 통해 즉시 모든 아종의 원본 분포문을 조회할 수 있다.**

---

## 3. 기존 왜가리(Heron)·청둥오리(Mallard) 개별 패치 한계 및 결함 감사

현재 코드베이스(`src/robingraph/retrieval/subspecies.py`, `src/robingraph/retrieval/taxonomy_lineage.py`, `src/robingraph/api/static/chat.js`)를 정밀 감사하여 확인된 한계와 구체적 결함은 다음과 같다:

### 3.1 종별 하드코딩의 한계 (커버리지 0.03%)
- `subspecies.py`에 선언된 `REVIEWED_RANGES`와 `REVIEWED_RANGE_RAW`는 청둥오리 2개 아종만을 대상으로 하며, `HERON_DISTRIBUTIONS`는 왜가리 4개 아종만을 대상으로 한다.
- `taxonomy_lineage.py`의 `SUBSPECIES_NAME_REFERENCES` 역시 왜가리 2종(`jouyi`, `monicae`)과 청둥오리 2종(`conboschas`, `platyrhynchos`) 총 4개 아종만을 수동 등록했다.
- 검토 당시 한국어 분포 요약은 전체 19,879개 중 6개에 한정되어 있었다. 이를 종별 수동 목록으로 계속 확장하면 유지보수 부담이 크므로, 모든 아종에 공통으로 원자료 분포를 제공하는 처리가 필요했다.

### 3.2 [버그 확인] `chat.js`의 카드 앞면 설명 필터링 결함
감사 과정에서 왜가리 패치의 실제 동작 상 심각한 결함이 발견되었다:
- `src/robingraph/api/static/chat.js` (1634~1638행):
  ```javascript
  var metadataSource = metadata && sanitizeUrl(metadata.source_url);
  ...
  var descriptions = metadataSection && metadataSection.key === "subspecies_taxonomy" && Array.isArray(metadataSection.items) ? metadataSection.items.slice(1).filter(function (item) { return item && typeof item.text === "string" && item.text.trim() && sanitizeUrl(item.source_url) === metadataSource; }).map(function (item) { return item.text; }) : [];
  description.textContent = metadataSource && descriptions.length ? descriptions.join(" ") : "이 아종만의 외형·분포 차이는 검토된 자료에서 아직 확인하지 못했습니다.";
  ```
- **원인 분석**:
  - `metadata.source_url`은 AviList 스냅샷 URL(`https://explore.avilist.org/data/avilist-2025b.json`)이다.
  - 그러나 왜가리 패치(`subspecies.py`)는 왜가리 아종의 설명 출처 URL(`item.source_url`)을 `HERON_DISTRIBUTION_URL`(`https://www.birdlife.org.za/red-data-book/red-list/grey-heron/`)로 지정했다.
  - `chat.js`는 `sanitizeUrl(item.source_url) === metadataSource` 일치를 강제하므로, 출처 URL이 서로 다른 왜가리 아종 설명은 **모두 필터링되어 버려진다(`descriptions.length === 0`).**
  - **실제 증상**: 왜가리 아종 카드를 클릭해 카드를 열면 앞면에 한국어 요약문이 나오는 대신, `"이 아종만의 외형·분포 차이는 검토된 자료에서 아직 확인하지 못했습니다."`라는 폴백 안내문이 출력된다.
  - **시사점**: 기본 분류 출처(`source_url`)와 개별 설명/명칭 출처(`item.source_url`)를 동일하게 취급해서는 안 되며, 유효하고 안전한(sanitized) 외부 출처 링크를 가진 항목은 카드 앞면에 정상 표시되어야 한다.

### 3.3 문자열 결합 및 언어 불일치 문제
- `subspecies.py` (90~94행):
  ```python
  caption = distribution + ' 분포' if distribution else raw.split(';')[0]
  ...
  taxon['display_label'] = parent_name + ' 아종' + (' · ' + caption if caption else '')
  ```
- 왜가리의 경우 한국어 수동 번역이 있어 `"왜가리 아종 · 마다가스카르 분포"`가 되지만, 그 외 19,873개 아종은 영어 원문이 그대로 들어가 `"Great Tit 아종 · Europe to western Siberia"`와 같이 한국어 조어 뒤에 영문이 직접 붙는 어색한 표제가 생성된다.
- 영문 분포문이 매우 긴 경우(예: 300자) 72자에서 단순 절삭되어 의미가 중간에 끊어지는 현상이 발생한다.

---

## 4. 범용 최소 안전 폴백(Minimal Safe General Fallback) 설계안

코디네이터의 구현을 위해, 19,879개 전 아종을 포괄하는 견고하고 안전한 범용 폴백 아키텍처를 다음과 같이 제안한다:

```
[아종 표제(Title/Heading) 결정 파이프라인]
  │
  ├─ 1순위: 검증된 한국어 통칭 (korean_name) ──[존재 시]──► 한국어 통칭 표시 (현재 0건, 위조 금지)
  │
  ├─ 2순위: 검증된 영문 통칭 (english_name) ────[존재 시]──► 공식 영문 통칭 표시 (출처 링크 필수, 현재 4건)
  │
  ├─ 3순위: 부모 통칭 + 출처 기반 분포 표제 ────[기본값]──► "{부모 통칭} 아종 · {정제된 분포 요약}"
  │         (검토된 한국어 분포요약 > AviList 영문 첫 절 클램핑)
  │
  └─ 4순위: 분포문 부재 시 안전망 ──────────[극단 예외]──► "{부모 통칭} 아종 {번호}" (식별성 보장)
```

### 4.1 표제(Title) 및 표시 라벨(`display_label`) 생성 규칙
1. **절대 원칙**: 검증되지 않은 한국어 통칭을 기계 번역하거나 창작하지 않는다.
2. **부모 종 명칭 상속 기준**: 부모 종의 `korean_name` 우선, 부재 시 `english_name`, 부재 시 `scientific_name`을 기반명으로 사용한다.
3. **분포 캡션 정제 알고리즘**:
   - **한국어 검토 요약이 존재하는 경우** (Tier A): 해당 한국어 요약을 사용 (예: `"마다가스카르 분포"`).
   - **AviList 영문 원문인 경우** (Tier B, 100% 가용):
     - 첫 번째 절 추출: `raw.split(';')[0].strip()`
     - 불필요한 공백 정규화: `' '.join(...)`
     - 길이 제한(Clamp): 모바일 가로 폭을 고려하여 최대 50~60자로 절삭 후 말줄임표(`…`) 처리.
     - 표제 포맷: `{부모명} 아종 · {분포요약}` (예: `"Great Tit 아종 · Europe to western Siberia"`)
   - **분포문이 아예 없는 극단적 결측 상태** (Tier C 안전망):
     - `{부모명} 아종 {인덱스}` (예: `"박새 아종 1"`, `"박새 아종 2"`)로 생성하여 동일한 표제가 중복되지 않도록 방어.

### 4.2 학명(Trinomial)의 폴딩(Folding) 처리
- **탐색기 목록 (`subspecies-peer`)**:
  - 학명은 주 표제에서 제외하고, 하단의 `<details class="subspecies-identity">` 내부의 `<summary>학명·출처</summary>` 아래에 배치한다.
  - 기본적으로 접혀 있으므로 목록 화면이 복잡해지지 않으며, 사용자가 필요할 때 즉시 펼쳐서 정확한 학명과 명명자(Authority), 출처 링크를 확인할 수 있다.
- **선택된 아종 카드 (`species-card`)**:
  - 카드 상단 배지: `<span class="species-category">아종</span>`
  - 소속 종 표시: `<p class="species-parent">소속 종: {부모 통칭/학명}</p>`
  - 학명 표시: `<p class="species-scientific-name">{아종 학명}</p>`

### 4.3 분류 출처와 명칭/분포 참조 출처의 분리
- **분류 체계 기준(Classification Backbone)**:
  - 항시 AviList v2025b 스냅샷을 기준으로 유지한다.
  - 카드의 분류 근거 링크: `https://explore.avilist.org/data/avilist-2025b.json` (CC BY 4.0).
- **분포 설명 및 명칭 근거(Distribution & Naming Reference)**:
  - 검토된 외부 자료(Birds New Zealand, Dansk Ornitologisk Forening, BirdLife South Africa 등)가 있는 경우, 해당 자료의 공식 명칭과 링크를 `description_source_title` 및 `description_source_url`로 별도 기재한다.
  - AviList 자체 영문 분포문을 사용할 경우, 언어 속성 `lang="en"`, 상태 `source-original`, 안내 문구 `분포(영어 원문): `를 명시하여 사용자를 속이지 않는다.
- **`chat.js` 카드 앞면 필터링 수정안**:
  - `sanitizeUrl(item.source_url) === metadataSource`와 같은 과도한 일치 검사를 제거하고, `subspecies_taxonomy` 섹션에 등록된 유효한 텍스트 항목 중 `safeLink` 검증을 통과하는 안전한 HTTP(S) URL을 가진 항목은 카드 앞면 요약에 정상 표시되도록 개선한다.

### 4.4 극단적 장문(Huge Range) 및 미확인 분포 처리
1. **장문 분포문(최대 542자) 처리**:
   - 카드 앞면: 첫 문장 또는 첫 1~2개 절(세미콜론 기준)만을 표시하거나 말줄임 처리하여 카드의 레이아웃 붕괴를 방지.
   - 카드 뒷면: `metadata.range_raw` 전체를 `<blockquote class="subspecies-range-raw">`에 온전히 인용하여 연구 목적의 완전한 원문을 제공.
2. **XSS 및 인젝션 방어**:
   - 외부에서 유입될 수 있는 악의적 스크립트나 태그(`script`, `iframe` 등)는 반드시 `.textContent`로만 DOM에 삽입하며, `innerHTML`을 일체 사용하지 않는다.

### 4.5 모바일 접근성(a11y) 및 반응형 규격
- **뷰포트 규격**: 320px(최소 모바일), 390px(표준 모바일), 1280px(데스크톱).
- **가로 넘침 방지**: 긴 영문 지명(예: `Mittelmeerraum`, `Banc d'Arguin`, `Amami-Oshima`)으로 인한 박스 넘침을 방지하기 위해 CSS에 `word-break: keep-all; overflow-wrap: break-word;` 적용, `scrollWidth === innerWidth` 만족.
- **터치 타깃 및 ARIA 속성**:
  - "아종 보기" 버튼의 터치 타깃 최소 44px × 44px 확보.
  - `aria-label`: `"{아종 표제} · 아종 자료 보기"` 형태로 버튼의 역할을 명확히 낭독.
  - `<details>` 및 `<summary>`를 활용하여 보조공학 기술이 접힘/펼침 상태를 자연스럽게 인식하도록 함.

### 4.6 동시성/경쟁상태(Race Condition) 및 데이터 일관성 방어
1. **세대 카운터(`generation`) 가드**:
   - 목록에서 여러 아종을 빠르게 연속 클릭할 때, 비동기 통신이 늦게 완료된 이전 요청이 최신 선택 화면을 덮어쓰지 않도록 `current !== generation` 체크를 유지.
2. **분류 릴리스 및 개념집합 불일치 거부**:
   - 조회된 아종 프로필의 `concept_set_id`와 `taxonomy_release`가 현재 대화의 부모 종과 불일치할 경우(`matches(other.lineage) === false`), 화면 렌더링을 차단하고 오류 안내 표시.
3. **대화 지우기(`conversationGuard`)**:
   - 사용자가 "대화 지우기"를 실행한 후 비동기 응답이 도착한 경우 DOM에 렌더링되지 않고 안전하게 폐기.

---

## 5. 시험 명세(Test Specifications) 및 검증 계획

코디네이터가 구현 후 검증할 수 있도록, 기존 왜가리/청둥오리 외에 **서로 무관한 6개 이상의 목(Order)과 속(Genus)**을 아우르는 테스트 시나리오를 명세한다:

### 5.1 검증 대상 분류군 세트
1. **참새목 (Passeriformes) - 박새과**: `Parus major` (Great Tit; 현재 한국의 박새 Parus cinereus와 구분)
   - 아종: `Parus major major` (Range: `"Europe to western Siberia"`)
   - 검증점: 영문 통칭 부재 시 표제 `"Great Tit 아종 · Europe to western Siberia"`, 학명 접힘 확인.
2. **타조목 (Struthioniformes) - 타조과**: `Struthio camelus` (타조)
   - 아종: `Struthio camelus syriacus` (Range: `"formerly Syrian and Arabian desert; extinct ca. 1966"`, 멸종 플래그)
   - 검증점: 과거 분포 및 멸종 아종의 분포문 및 상태 표기 검증.
3. **닭목 (Galliformes) - 꿩과**: `Phasianus colchicus` (꿩)
   - 아종: `Phasianus colchicus torquatus` (Range: `"eastern China"`)
   - 검증점: 동아시아 분포 아종의 영문 원문 표제 생성.
4. **참새목 (Passeriformes) - 까마귀과**: `Corvus macrorhynchos` (큰부리까마귀)
   - 아종: `Corvus macrorhynchos japonensis` (Range: `"Japan"`)
   - 검증점: 단문(5자) 분포문의 표제 및 카드 렌더링.
5. **수리목 (Accipitriformes) - 수리과**: `Buteo japonicus` (말똥가리)
   - 아종: `Buteo japonicus toyoshimai` (Range: `"Izu Islands and Bonin Islands"`)
   - 검증점: 도서 지역 분포 아종의 세부 출처 분리.
6. **매목 (Falconiformes) - 매과**: `Falco peregrinus` (매)
   - 아종: 전 세계 19개 아종 (극단적 장문 및 다수 아종 목록 스크롤 검증)
   - 검증점: 72자 이상 장문 분포문의 말줄임(`…`) 절삭 및 고유성 유지.

### 5.2 단위 테스트 명세 항목
- `test_subspecies_title_priority_chain`:
  - 1단계(한국어 통칭) → 2단계(영문 통칭) → 3단계(부모명 + 분포 캡션) 순서로 정확히 표제가 결정되는지 검증.
- `test_unrelated_genera_distribution_captions`:
  - 위 6개 속의 아종들이 하드코딩 사전 없이도 AviList DB의 `range_text`로부터 고유한 `display_label`을 자동 생성하는지 검증.
- `test_subspecies_card_front_description_with_external_source`:
  - 설명 출처 URL이 기본 분류 스냅샷 URL과 다르더라도 카드 앞면에 정상 노출되는지 검증 (기존 버그 회귀 방지).
- `test_huge_range_text_clamping_and_card_back_raw`:
  - 500자 이상의 초장문 분포문이 표제에서는 안전하게 클램핑되고, 카드 뒷면 `<blockquote>`에는 전체 원문이 보존되는지 검증.
- `test_race_and_stale_release_rejection`:
  - 빠른 연속 클릭 시 마지막 클릭 대상만 렌더링되는지, `stale` 릴리스 응답이 올 경우 카드가 열리지 않고 안전하게 차단되는지 검증.

---

## 6. 실제 테스트 실행 결과

본 검토 작업을 수행하며 로컬 환경에서 기존 단위 및 프런트엔드 테스트를 실제 실행하여 현재 상태를 측정했다.

### 6.1 테스트 실행 상세 결과
- **Python 단위 테스트** (`.venv/bin/python3 -m unittest tests/test_subspecies.py`):
  - **실행 건수**: 8건
  - **통과(Passed)**: 8건
  - **실패(Failed)**: 0건
  - **오류(Errors)**: 0건
  - **소요 시간**: 0.042초
- **프런트엔드 단위 테스트** (`node --test tests/frontend/chat_ui.test.js`):
  - **실행 건수**: 127건
  - **통과(Passed)**: 127건
  - **실패(Failed)**: 0건
  - **취소/건너뛰기(Skipped/Cancelled)**: 0건
  - **소요 시간**: 143.58ms

### 6.2 검증의 성격 구분
- 본 테스트는 모의 객체(Mock) 및 가상 DOM 환경에서 수행된 로컬 모의 검증(Mock Verification)이다.
- 실제 Neo4j DB 및 실제 브라우저 렌더링에 대한 변경 테스트는 수행하지 않았다.

---

## 7. 배포 및 커밋 정보 (해당하지 않음)

- **사유**: 본 태스크는 **읽기 전용 조사 및 아키텍처 제안(Read-only review)**으로 지정되었으며, 지침에 따라 일체의 소스/테스트 코드 수정, Git 커밋, 도커 이미지 빌드, NAS TEST/PROD 배포, DB 데이터 변이를 수행하지 않았다.
- 실제 구현, 코드 수정, 배포는 본 보고서를 바탕으로 코디네이터(Coordinator)가 전담하여 진행한다.

---

## 8. 남은 한계와 후속 사항 (Honest Reporting)

### 8.1 데이터 현실에 대한 정직한 보고
1. **전 세계 아종 통칭 부재**: 이번 검토에서 확인한 별도 한국어 아종 통칭은 0건이며 (전 세계적으로 한국어 이름이 없다는 뜻은 아님), AviList 원자료에도 영문 아종 통칭은 0건이다. 시스템이 모든 아종의 통칭을 가지고 있다고 홍보하거나 가장해서는 안 되며, 사용자가 보는 표제(`display_label`)는 공식 명칭이 아닌 "설명용 캡션"임을 학명·출처 세부정보에 명확히 밝혀야 한다.
2. **영문 분포문 한계**: 한국어로 검토된 소수 종(청둥오리, 왜가리 등)을 제외한 대다수 아종의 분포 설명은 영어 원문(`source-original`, `en`)으로 제공된다. 영문 지명에 익숙하지 않은 국내 사용자에게 다소 불친절할 수 있으나, 검증되지 않은 기계 번역을 임의로 제공하는 것보다는 출처를 명확히 밝히는 것이 데이터 신뢰성 면에서 안전하다.

### 8.2 후속 권고 사항
1. **코디네이터 구현 착수**:
   - `subspecies.py`의 `HERON_DISTRIBUTIONS` 및 `REVIEWED_RANGES`와 같은 종별 특수 처리 의존도를 낮추고, DB에서 반환된 `child.range_text`를 안전하게 정제하여 `display_label`을 생성하는 일반 로직으로 통합할 것.
   - `chat.js`의 카드 앞면 설명 필터 조건(`sanitizeUrl(item.source_url) === metadataSource`)을 수정하여 외부 출처 분포문이 정상 출력되도록 수정할 것.
2. **향후 국가생물다양성 정보 연계**:
   - 국립생물자원관(NIBR) 또는 국가생물종목록에서 국내 서식 조류 아종의 공식 한국어 통칭이 검증·공개될 경우, `species_ko_names.json`과 같은 검증된 매핑 채널을 통해 점진적으로 확충할 것을 권장한다.


최종 통합에서는 전체 아종에 원자료 분포를 제공하고 통칭 1,075개를 출처와 함께 연결했다. 이 문서는 검토 시점의 발견과 제안이며 실제 최종 테스트·배포 기록은 [코디네이터 작업 문서](2026-10-06-global-subspecies-names-and-ranges.md)를 따른다.
