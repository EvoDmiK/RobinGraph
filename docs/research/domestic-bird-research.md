# 주요 가축화 조류(Domesticated Birds) 분류 관계 확장 연구

> **기준일**: 2026-10-03  
> **상태**: Reviewed Research (후보 목록: `docs/research/domestic-bird-candidates.json`, 7개 레코드)  
> **범위**: RG-501 확장 가축 조류(거위, 칠면조, 가축메추리, 뿔닭, 카나리아, 사육염주비둘기)의 1차 문헌 검증. 단순 사육조(cagekeeping)나 길들임(taming)과의 엄격한 분리 및 보류 사유 명시. (십자매·금화조는 Claude 트랙, 고유 닭 품종은 Root 트랙 전담)

## 1. 개요 및 연구 원칙
- **가축화(Domestication)와 단순 사육·길들임의 분리**: 검토한 출처가 가축화 관계를 뒷받침할 때 `domestic_form`으로 채택한다. 이 조사에서 단순 사육·훈련만 확인했거나 기원 근거를 검증하지 못한 이름은 가축화 관계로 등록하지 않는다. 미등록이 해당 조류의 가축화 가능성을 부정하는 것은 아니다.
- **다계통 및 모호성 보존**: 서로 다른 야생종에서 기원한 거위는 단일 종으로 억지 합병하지 않고 동일한 `entity_id`(`goose-domestic`)와 공통 한국어 검색어(`[거위, 집거위, 가축거위]`)를 부여하여 모호성을 투명하게 보존한다.
- **사실 진술과 편집적 추론의 엄격한 분리**: 1차 문헌의 분류·유전학적 직접 진술과 RobinGraph의 한국어 검색어/별칭 매핑을 명확히 구분하며, 원문 복제나 재라이선스를 하지 않는다.
- **불확실성 보고**: 전 세계 모든 조류의 망라를 주장하지 않으며, 로컬/NAS 운영 그래프 적재 완료를 주장하지 않는다.

## 2. 검증된 가축화 조류 사실 관계 및 1차 출처

### 1) 거위 (Domestic Geese): 회색기러기 및 개리의 이원 기원
- **원종**: *Anser anser* (회색기러기) 및 *Anser cygnoides* (개리)
- **사실 관계**: 유럽 계통 거위는 주로 *Anser anser*, 동아시아 계통 거위는 주로 *Anser cygnoides*에서 가축화되었다. 단, 중국 신장 지역의 일리(Yili) 거위처럼 동양에서도 *Anser anser* 유래 품종이 존재하며 품종 간 교잡과 유전자 유입이 확인되므로 단순 지리적 이분법으로 나뉘지 않는다. 두 계통 모두 공통 검색어 `[거위, 집거위, 가축거위]`를 공유한다.
- **1차 출처**:
  - FAO Gateway (Other poultry - Geese): `https://www.fao.org/poultry-production-products/production/poultry-species/other-species/en`
  - PMC9640629 (Chinese indigenous geese genome): `https://pmc.ncbi.nlm.nih.gov/articles/PMC9640629/`

### 2) 칠면조 (Domestic Turkey)
- **원종**: *Meleagris gallopavo* (들칠면조)
- **사실 관계**: 고대 메소아메리카 원주민에 의해 가축화된 후 16세기 유럽으로 전래된 북미·중앙아메리카 원산 가금류이다.
- **1차 출처**:
  - FAO Gateway (Other poultry - Turkeys): `https://www.fao.org/poultry-production-products/production/poultry-species/other-species/en`
  - PMC3414452 (Earliest Mexican Turkeys in the Maya Region): `https://pmc.ncbi.nlm.nih.gov/articles/PMC3414452/`

### 3) 가축메추리 (Domestic Japanese Quail)
- **원종**: *Coturnix japonica* (동아시아 메추라기)
- **사실 관계**: 산업적으로 사육되는 가축 메추리는 유럽메추라기(*C. coturnix*)가 아닌 동아시아의 *C. japonica*에서 가축화되었다. 일상어로 '메추리'라 부르나 야생 표준 국명은 '메추라기'이므로, 검토 검색어는 `[집메추리, 가축메추리, 사육메추리, 메추리]`로 한정하여 야생·가축 맥락을 주석으로 구분한다.
- **1차 출처**: PMC5249226 (Genetic Divergence in Domestic Japanese Quail): `https://pmc.ncbi.nlm.nih.gov/articles/PMC5249226/`

### 4) 뿔닭 (Domestic Guineafowl)
- **원종**: *Numida meleagris* (투구뿔닭 / 뿔닭)
- **사실 관계**: 서아프리카 원산 뿔닭에서 가축화된 가금류이다. 단순 '뿔닭'은 야생종과 가축형 모두에 쓰이므로 가축형 검색어는 `[집뿔닭, 가축뿔닭, 사육뿔닭, 뿔닭]`을 사용하되 주석으로 야생/가축 맥락을 명시한다.
- **1차 출처**:
  - FAO Gateway (Other poultry - Guinea fowl): `https://www.fao.org/poultry-production-products/production/poultry-species/other-species/en`
  - FAO World Watch List (Numida meleagris): `https://www.fao.org/docrep/pdf/009/x8750e/x8750e.pdf`

### 5) 카나리아 (Domestic Canary)
- **원종**: *Serinus canaria* (야생 카나리아)
- **사실 관계**: 대서양 마카로네시아 원산 야생종에서 유래했다. 단순 '카나리아'는 야생종과 사육종을 모두 가리킨다. 특히 붉은색 품종(레드 팩터)은 *Spinus cucullatus*와의 종간 교잡에서 유래했으므로 모든 색상 변종이 순수 카나리아 단일종은 아니다.
- **1차 출처**:
  - Lopes et al. (2016), Genetic Basis for Red Coloration in Birds (PDF): `https://corbolab.wustl.edu/publications/Lopes2016.pdf`
  - IOC World Bird List (Finches): `https://www.worldbirdnames.org/new/bow/finches/`

### 6) 사육염주비둘기 / 바바리비둘기 (Barbary Dove)
- **원종**: *Streptopelia roseogrisea* (사하라염주비둘기)
- **사실 관계**: 린네의 가축형 학명 *Streptopelia risoria*는 ICZN Opinion 2215에서 우선권이 유지되었으며, 프로젝트의 AviList v2025b는 야생 원종인 *S. roseogrisea*를 유효 종으로 채택한다. 한국 야생 텃새인 염주비둘기(*Streptopelia decaocto*) 및 집비둘기 백색 변종과의 혼동을 막기 위해 검색어를 `[사육염주비둘기, 바바리비둘기, Streptopelia risoria]`로 엄격히 한정한다.
- **1차 출처**:
  - ICZN Opinion 2215 (Bulletin of Zoological Nomenclature): `https://www.biotaxa.org/bzn/issue/download/5181/303`
  - IOC World Bird List (Pigeons): `https://www.worldbirdnames.org/new/bow/pigeons/`

## 3. 명시적 보류 및 제외 대상 (Withheld / Deferred Birds)

| 대상 | 학명 (Scientific Name) | 구분 | 보류 및 제외 사유 |
|---|---|---|---|
| **십자매 / 금화조** | *Lonchura striata* / *Taeniopygia guttata* | **위임 제외** | 별도 통칭·사육조 조사에서 검토. 십자매는 채택했고 금화조는 분류 경계 추가 확인을 위해 보류. |
| **사랑앵무 / 왕관앵무** | *Melopsittacus undulatus* / *Nymphicus hollandicus* | **보류 (Deferred)** | 케이지 사육 및 색상 변이가 있으나 가축화 증후군이나 이 조사에서는 가축화 기원 근거를 검증하지 못함. |
| **자바참새 (문조)** | *Padda oryzivora* | **보류 (Deferred)** | 백문조 등 사육 변종이 있으나 이 조사에서 가축화 기원 근거를 검증하지 못함. |
| **타조** | *Struthio camelus* | **제외 (Withheld)** | 농장 사육은 확인할 수 있으나 이 조사에서 가축화 기원 근거를 검증하지 못함. |
| **매 / 참매 / 가마우지**| *Falco peregrinus* / *Accipiter gentilis* / *Phalacrocorax carbo* | **제외 (Withheld)** | 사냥·어업용으로 훈련·사육 사실만으로 가축화 기원을 확정하지 않음. |

## 4. 후보 레코드 요약표 (7건)

| ID | 명칭 (Name) | 엔티티 ID | 대상 학명 (Scientific Name) | 검색어 (Search Terms) | 1차 출처 URL |
|---|---|---|---|---|---|
| `goose-greylag` | 거위 | `goose-domestic` | *Anser anser* | 거위, 집거위, 가축거위 | [PMC9640629](https://pmc.ncbi.nlm.nih.gov/articles/PMC9640629/) |
| `goose-swan` | 거위 | `goose-domestic` | *Anser cygnoides* | 거위, 집거위, 가축거위 | [PMC9640629](https://pmc.ncbi.nlm.nih.gov/articles/PMC9640629/) |
| `turkey-wild` | 칠면조 | `turkey-domestic` | *Meleagris gallopavo* | 칠면조, 집칠면조, 가축칠면조 등 | [PMC3414452](https://pmc.ncbi.nlm.nih.gov/articles/PMC3414452/) |
| `quail-japanese` | 메추리 | `quail-domestic` | *Coturnix japonica* | 집메추리, 가축메추리, 사육메추리, 메추리 등 | [PMC5249226](https://pmc.ncbi.nlm.nih.gov/articles/PMC5249226/) |
| `guineafowl-helmeted` | 뿔닭 | `guineafowl-domestic` | *Numida meleagris* | 집뿔닭, 가축뿔닭, 사육뿔닭, 뿔닭 등 | [FAO Docrep](https://www.fao.org/docrep/pdf/009/x8750e/x8750e.pdf) |
| `canary-atlantic` | 카나리아 | `canary-domestic` | *Serinus canaria* | 사육카나리아, 가축카나리아, 카나리아 등 | [Lopes 2016](https://corbolab.wustl.edu/publications/Lopes2016.pdf) |
| `ringneck-dove-roseogrisea` | 사육염주비둘기 | `ringneck-dove-domestic` | *Streptopelia roseogrisea* | 사육염주비둘기, 바바리비둘기 등 | [BioOne ICZN](https://www.biotaxa.org/bzn/issue/download/5181/303) |
