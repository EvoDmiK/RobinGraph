# 독립 평가 세트(44건) 의미 및 인벤토리 정합성 검토 보고서

> **문서 성격 고지**: 본 검토는 구현 코드 열람 전 Root가 작성한 독립 평가 데이터(`independent-cases.json`, 44건)와 실제 TEST 환경 인벤토리 카탈로그(`inventory.json`, 33,684건 및 `trait-inventory.json`, 15개 형질 필드) 간의 **에이전트 의미 검토(Agent Review)** 결과입니다.  
> 본 검토는 **인간 검토(Human Gold Review)가 아니며**, 평가 대상 파일(`independent-cases.json`)은 원본 그대로 보존되었습니다(수정 0건).

---

## 1. 검토 개요 및 총평

- **검토 대상 파일**: `docs/verification/assets/2026-10-22-taxonomic-trait-generalization/independent-cases.json` (44건)
- **대조 기준 데이터**:
  - 분류 카탈로그: `inventory.json` (총 33,684 분류군: Order 46, Family 252, Genus 2,376, Species 11,131, Subspecies 19,879)
  - 형질 카탈로그: `trait-inventory.json` (AVONET 13개 필드, EltonTraits 2개 필드)
- **기대 결과(Outcome) 분포 (44건)**:
  - `query` (유효 질의 추출): **31건**
  - `hold` (명료화/보류): **10건** (IT-034 ~ IT-041, IT-043, IT-044)
  - `insufficient` (자료 부족 명시): **2건** (IT-011, IT-042)
  - `empty` (공집합 반환): **1건** (IT-033)
- **종합 판정**:
  - 작성된 44건의 기대 의미는 활성 TEST DB의 분류군 및 형질 스키마와 전반적으로 높은 정합성을 유지하고 있습니다.
  - 특히 **단위 정규화(kg→g, cm→mm)**, **계급 체계(목/과/속/종/아종)**, **형질 값(범주형 허용치, 먹이 비율 딕셔너리)**이 스키마와 일치합니다.
  - 다만, 평가 실행 및 해석 시 유의해야 할 **분류군 국명 특이사항(앵무새)**, **계급 동음이의어 모호성(초승달가슴새류, 화식조)**, **카탈로그 레이블 이상치(Cinclus)** 등이 확인되어 상세 내역을 아래와 같이 정리합니다.

---

## 2. 세부 검토 결과

### 2.1. 없는 분류(Missing Taxa) 및 분류군 실재성 검토

| 케이스 ID | 질의 내 분류 표현 | 기대 학명 및 계급 | 카탈로그 실재 여부 및 검토 의견 |
| :--- | :--- | :--- | :--- |
| **IT-001 ~ IT-002, IT-012 ~ IT-031, IT-033 ~ IT-040, IT-042** | 까마귀과 / Corvidae | `Corvidae` (family) | **실재함** (`avilist-taxon:v2025b:19917`, ko: `까마귀과`). 계급 일치. |
| **IT-003 ~ IT-004** | 까마귀속 / Corvus | `Corvus` (genus) | **실재함** (`avilist-taxon:v2025b:20236`, ko: `까마귀속`). 계급 일치. |
| **IT-005 ~ IT-006** | 까마귀 / Corvus corone | `Corvus corone` (species) | **실재함** (`avilist-taxon:v2025b:20280`, ko: `까마귀`). 계급 일치. |
| **IT-007** | 매목 | `Falconiformes` (order) | **실재함** (`avilist-taxon:v2025b:11087`, ko: `매목`). 계급 일치. |
| **IT-008** | 오리과 | `Anatidae` (family) | **실재함** (`avilist-taxon:v2025b:240`, ko: `오리과`). 계급 일치. |
| **IT-009** | Anas | `Anas` (genus) | **실재함** (`avilist-taxon:v2025b:526`, ko: `오리속`). 계급 일치. |
| **IT-010** | 앵무새 | `Psittaciformes` (order) | **실재함** (`avilist-taxon:v2025b:11278`, ko: `앵무새`). 계급 일치. *(국명 특이사항: 2.2절 참조)* |
| **IT-011** | Corvus corone corone | `Corvus corone corone` (subspecies) | **실재함** (`avilist-taxon:v2025b:20281`, ko: null). 계급 일치. *(자료 부족: 2.3절 참조)* |
| **IT-032** | (분류군 없음) | `taxon: None, rank: None` | **해당 없음** (전체 조류 대상 순수 형질 질의). |
| **IT-041** | 가짜조류과 | `taxon: None, rank: None` | **존재하지 않음 (의도된 가상 분류군)**. 카탈로그에 없는 분류군으로 `outcome: 'hold'` 기대 타당. |
| **IT-043** | 초승달가슴새류 | `taxon: None, rank: None` | **카탈로그에 실재함 (동음이의어 보류)**. Genus `Melanopareia`와 Family `Melanopareiidae` 양쪽에 동일 국명 등록됨. *(상세: 2.2절 참조)* |
| **IT-044** | 화식조 | `taxon: None, rank: None` | **카탈로그에 실재함 (동음이의어 보류)**. Genus `Casuarius`와 Species `Casuarius casuarius` 양쪽에 동일 국명 등록됨. *(상세: 2.2절 참조)* |

---

### 2.2. 국명(Korean Naming) 및 분류 카탈로그 특이사항

1. **`Psittaciformes` / `앵무새` (IT-010)**:
   - 일반 생물학 국명 체계에서 '목(Order)' 계급은 통상 `-목`(예: 앵무목) 접미사를 사용하나, 참조 카탈로그(`AviList v2025b`)에서는 `Psittaciformes`(Order)의 국명이 `"앵무새"`로 단독 등록되어 있습니다.
   - 따라서 질의 `"앵무새 중 숲에 사는 새는?"`에서 `taxon: 'Psittaciformes', rank: 'order'`로 추출하는 기대는 **현재 DB 카탈로그 기준 정확한 매핑**입니다.
   - *유의사항*: 파서가 '목' 접미사를 엄격히 요구하도록 구현될 경우 오탐이 발생할 수 있으므로, 카탈로그 국명 직접 매핑 규칙을 지원해야 합니다.

2. **`초승달가슴새류`의 계급 동음이의 모호성 (IT-043)**:
   - 질의: `"초승달가슴새류 중 숲에 사는 새는?"` (기대: `taxon: None, rank: None, outcome: 'hold'`)
   - `inventory.json` 조회 결과:
     - `avilist-taxon:v2025b:14306`: Family `Melanopareiidae` (ko: `"초승달가슴새류"`)
     - `avilist-taxon:v2025b:14307`: Genus `Melanopareia` (ko: `"초승달가슴새류"`)
   - **판정**: 이 케이스는 분류군이 DB에 없어서 `hold`가 되는 것이 아니라, **과(Family)와 속(Genus)이 동일한 국명을 공유하여 단일 계급으로 확정할 수 없는 '계급 동음이의어(Rank Homonym)'**에 해당합니다. 기대 결과 `hold`는 타당하나, "미등록 분류군"으로 오해하지 않도록 명시가 필요합니다.

3. **`화식조`의 계급 동음이의 모호성 (IT-044)**:
   - 질의: `"화식조 중 숲에 사는 새는?"` (기대: `taxon: None, rank: None, outcome: 'hold'`)
   - `inventory.json` 조회 결과:
     - `avilist-taxon:v2025b:18`: Genus `Casuarius` (ko: `"화식조"`)
     - `avilist-taxon:v2025b:19`: Species `Casuarius casuarius` (ko: `"화식조"`)
     - (참고: 과는 `Casuariidae` / `"화식조과"`, 목은 `Casuariiformes` / `"화식조목"`)
   - **판정**: '화식조'는 화식조속 전체(Genus)를 가리킬 수도 있고, 단일 종인 남방화식조(Species)를 가리킬 수도 있습니다. 종 수준에서 하위 종을 묻거나 속 수준과 혼동되므로 명료화(`hold`) 기대가 타당합니다.

4. **참조 카탈로그 레이블 이상치 참고 (`Cinclus` / `Cinclidae`)**:
   - `inventory.json` 분석 중 발견된 데이터 특이사항:
     - `avilist-taxon:v2025b:26499`: Family `Cinclidae` (ko: `null`)
     - `avilist-taxon:v2025b:26500`: Genus `Cinclus` (ko: `"물까마귀과"`)
     - `avilist-taxon:v2025b:26516`: Species `Cinclus pallasii` (ko: `"물까마귀"`)
   - 속(Genus)인 `Cinclus`의 국명에 접미사 `"과"`가 붙어 있고, 실제 과(Family)는 국명이 누락되어 있습니다. 이번 44건 세트에는 포함되지 않았으나 향후 확장 시 유의해야 할 상위 카탈로그 특이점입니다.

---

### 2.3. 불명확 기대(Ambiguous Expectations) 및 엣지 케이스 정합성

1. **아종 단위 형질 부재 (`Corvus corone corone`, IT-011)**:
   - 질의: `"Corvus corone corone 중 숲에 사는 새는?"` (기대: `outcome: 'insufficient'`)
   - 검토: `trait-inventory.json`의 모든 파이프라인(AVONET 13개 필드, EltonTraits 2개 필드)은 **`rank: "species"` 수준에서만 형질이 수집/정의**되어 있습니다. 아종(Subspecies) 단위에는 측정 형질이 없으므로, 아종에 대한 형질 필터링을 자료 부족(`insufficient`)으로 처리하는 기대는 데이터 카탈로그 제약상 매우 정확합니다.

2. **미세 식물 종 단위 먹이 부재 (`감나무 열매`, IT-042)**:
   - 질의: `"까마귀과 중 감나무 열매를 먹는 새는?"` (기대: `outcome: 'insufficient'`)
   - 검토: EltonTraits의 `diet_distribution`은 대분류 먹이 범주(`fruit`, `seed`, `nectar`, `invertebrate`, `fish` 등 10개)만 백분율로 제공하며, '감나무'와 같은 구체적인 식물 종 정보는 지원하지 않습니다. 따라서 `insufficient` 판정은 정확합니다.

3. **극단값 공집합 처리 (IT-033)**:
   - 질의: `"까마귀과 중 체중이 1000000g 이상인 새는?"` (기대: `outcome: 'empty'`)
   - 검토: 외부 생물학 일반론(타조 최대 체중 등)이 아닌 실제 DB 형질 데이터(`trait-inventory.json` / AVONET)의 `body_mass` 실측 조건을 기준으로, 1,000,000g 이상을 만족하는 데이터 레코드가 전무(0건)하므로 질의 조건 평가 결과 공집합(`empty`)을 반환하는 기대가 타당합니다.

4. **보류(Hold) 케이스 유형별 타당성 (IT-034 ~ IT-041)**:
   - **IT-034 (부정형)**: `"숲에 살지 않는"` → 부정 조건은 자연어 질의에서 범위가 모호하므로 명료화(`hold`) 기대 타당.
   - **IT-035 (시간/계절)**: `"겨울에만"` → AVONET/EltonTraits에 계절별 서식 데이터 미제공(`hold`).
   - **IT-036 (주관적 형용사)**: `"몸집이 큰"` → 수치 기준이 없으므로 모호성 보류(`hold`).
   - **IT-037 (단위 누락)**: `"체중이 100 이상"` → 100g인지 100kg인지 불분명하므로 보류(`hold`).
   - **IT-038 (모순 서식지)**: `"숲에 살고 바다에 사는"` → 상충 조건 확인 보류(`hold`).
   - **IT-039 (Cypher 주입 시도)**: `"MATCH (n) DETACH DELETE n"` → 보안 위협 입력 방어(`hold`/차단).
   - **IT-040 (미지원 형질)**: `"날개가 빨간"` → 깃털 색상 형질 미보유(`hold`).
   - **IT-041 (미존재 가상 분류군)**: `"가짜조류과"` → 인벤토리에 없는 분류군(`hold`).

---

### 2.4. 단위 및 연산자(Unit & Operator) 정합성 검토

1. **수치형 단위 매핑**:
   - `inventory` 허용 단위: `body_mass`는 `['g']`, 나머지 7개 수치형 치수(부리, 날개, 꼬리, 발척 등)는 `['mm']`.
   - **IT-026**: `"0.1kg 이상"` → 조건: `{'body_mass': 100, 'unit': 'g'}` (1000배 정규화 일치).
   - **IT-027**: `"10cm 이상"` → 조건: `{'wing_length': 100, 'unit': 'mm'}` (10배 정규화 일치).
   - 단위 정규화 기대값이 카탈로그 정의 단위와 완벽히 부합합니다.

2. **먹이 비율 연산자 (`diet_distribution`)**:
   - 카탈로그의 `diet_distribution`은 JSON 딕셔너리(`invertebrate`, `fish`, `fruit`, `nectar`, `seed` 등) 형태입니다.
   - IT-001, IT-028, IT-029, IT-030, IT-032에서 사용된 연산자:
     - `op: 'share_gt'`, `value: {'fruit': 0}`, `unit: None`
   - 카탈로그의 `units`가 `['percent']`로 등록되어 있으나, `share_gt` 연산자 수준에서는 비율 임계치 딕셔너리를 직접 전달하므로 `unit: None`으로 표현된 기대는 의미적으로 타당합니다.

3. **범주형 텍스트 값 일치**:
   - `habitat`: `'Forest'` ∈ `['Forest', 'Shrubland', 'Human Modified', 'Grassland', 'Woodland', 'Wetland', 'Rock', 'Desert', 'Coastal', 'Riverine', 'Marine']` (일치)
   - `primary_lifestyle`: `'Terrestrial'` ∈ `['Insessorial', 'Terrestrial', 'Generalist', 'Aerial', 'Aquatic']` (일치)
   - `habitat_density_category`: `'open'` ∈ `['dense', 'semi_open', 'open']` (일치)
   - `trophic_niche`: `'Omnivore'` ∈ `['Frugivore', 'Omnivore', 'Invertivore', ...]` (일치)
   - `trophic_level`: `'Omnivore'` ∈ `['Herbivore', 'Carnivore', 'Omnivore', 'Scavenger']` (일치)
   - `diet_category`: `'Omnivore'` ∈ `['FruiNect', 'Invertebrate', 'Omnivore', 'PlantSeed', 'VertFishScav']` (일치)
   - 대소문자 및 영문 카테고리 명칭이 카탈로그의 `text_values`와 100% 일치합니다.

---

## 3. 평가 하네스 및 후속 검증 시 권장사항

1. **평가 파일 무변경 원칙 준수**:
   - Root의 지침에 따라 `independent-cases.json`은 일체 수정하지 않고 원본 그대로 평가 기준으로 사용합니다.
2. **동음이의어(IT-043, IT-044) 평가 판정 주의**:
   - 하네스에서 IT-043, IT-044를 검증할 때, 모델이 `Melanopareia`나 `Casuarius`를 찾아냈더라도 `outcome`이 `hold`(명료화 요구)가 아닌 즉시 질의(`query`)를 수행했다면 감점 또는 보류 판정이 올바릅니다. (계급 불확정 상태에서의 임의 선택 방지 목적)
3. **`Psittaciformes` / `앵무새` (IT-010) 국명 매핑 규칙 확인**:
   - 추출 파서가 '목' 접미사가 없다는 이유로 `Psittaciformes`를 거부하지 않도록, `inventory.json`의 Order 계급에 등록된 국명 리스트를 완화 없이 조회할 수 있는지 평가합니다.

---

*보고서 작성 일시: 2026-10-22*  
*작성자: dev / Writer (Agent Review)*
