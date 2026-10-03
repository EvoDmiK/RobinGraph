# 한국어 조류 일반명 및 가축형 관계 연구

> **기준일**: 2026-10-03  
> **상태**: Reviewed Research (패키지 `src/robingraph/retrieval/name_relations.json` 구현 근거)  
> **범위**: 사용자 질의 4개 및 파생 명칭 등 초기 8개 관계 레코드의 사실 관계 검증. 전체 분류군 후보의 완전한 목록이 아니며, 로컬/NAS 운영 그래프 적재 완료를 주장하지 않음.

## 1. 개요 및 원칙
- **가축형과 야생종의 분리**: 가축형(domestic form)은 자동으로 야생종의 아종으로 판정하거나 하나의 노드로 합병(invented taxon merge)하지 않고, 별도의 `domesticated_from` 관계로 연결한다.
- **통칭과 표준 국명의 불일치 보존**: 대중의 통칭(common usage) 후보는 RobinGraph의 독자적 추론이며, 원천 소스의 직접 진술과 명확히 구분한다. 소스 간 명칭 차이(예: Wikidata vs NIBR)는 임의로 수정하지 않고 있는 그대로 기록한다.
- **원문 복제 배제**: 소스 저작물의 문장을 복제하거나 라이선스를 재부여하지 않으며, 사실적 관계만을 독자적인 한국어 요약으로 기술한다.

## 2. 4대 대상 사례별 사실 관계 및 검증 URL

### 1) 비둘기 / 바위비둘기 (*Columba livia*)
- **분류 체계**: 비둘기목(Columbiformes) 비둘기과(Columbidae) *Columba livia*
- **사실 관계**: 도시에서 흔히 관찰되는 비둘기 및 사육 품종은 야생 바위비둘기(*Columba livia*)에서 유래했다. 비둘기라는 통칭의 모든 대상을 이 한 종으로 한정할 수는 없으나, 일반적 검색 후보로 바위비둘기를 안내한다.
- **구현 관계 (2건)**:
  - `비둘기` (`common_name`) → `common_usage` → *Columba livia*
  - `집비둘기` (`domestic_form`) → `domesticated_from` → *Columba livia*
- **검증 출처**: Cornell Lab of Ornithology (Rock Pigeon Overview): `https://www.allaboutbirds.org/guide/Rock_Pigeon/overview`

### 2) 까마귀 / 큰부리까마귀 (*Corvus corone* vs *Corvus macrorhynchos*)
- **분류 체계**: 참새목(Passeriformes) 까마귀과(Corvidae) 까마귀속(*Corvus*)
- **사실 관계**: 국내 조사 자료(NIBR 센서스)에서는 *Corvus corone*를 '까마귀', *Corvus macrorhynchos*를 '큰부리까마귀'로 구분한다. 두 종은 별개의 독립된 종이며 동의어로 합치지 않는다. 대중이 검은 까마귀류를 통칭할 때 두 종 모두 관찰 후보가 될 수 있다.
- **소스 불일치 및 불확실성**: 활성 AviList 테스트 환경에서 *Corvus corone*의 한국어 라벨은 Wikidata 유래인 '송장까마귀'로 적재되어 있으며, *Corvus orientalis*는 독립 종으로 존재하지 않는다. 표준명을 임의로 고치지 않고 출처별 차이를 그대로 유지한다.
- **구현 관계 (2건)**:
  - `까마귀` (`common_name`) → `common_usage` → *Corvus corone*
  - `까마귀` (`common_name`) → `common_usage` → *Corvus macrorhynchos*
- **검증 출처**: 국립생물자원관 (겨울철 조류 동시 센서스 2015–2016): `https://www.nibr.go.kr/aiibook/catImage/12/2015-2016.pdf`

### 3) 닭 / *Gallus gallus*
- **분류 체계**: 닭목(Galliformes) 꿩과(Phasianidae) 야계속(*Gallus*)
- **사실 관계**: 유전체 분석 연구에 따르면 가축 닭은 동남아시아 및 남아시아 일대의 적색야계(붉은멧닭, *Gallus gallus*)로부터 기원했다. 초기 가축화 이후 타 야계종과의 유전적 혼합이 있었으나 주 원종은 *Gallus gallus*이다. 야생종의 특성을 가축 닭에 그대로 대입하지 않는다.
- **구현 관계 (1건)**:
  - `닭` (`domestic_form`) → `domesticated_from` → *Gallus gallus*
- **검증 출처**: Wang et al. (2020), 863 genomes reveal the origin and domestication of chicken (Cell Research): `https://www.nature.com/articles/s41422-020-0349-y`

### 4) 집오리 / *Anas platyrhynchos* 및 *Cairina moschata*
- **분류 체계**: 기러기목(Anseriformes) 오리과(Anatidae)
- **사실 관계**: 가축 오리는 단일 기원이 아니다. 대다수 집오리는 청둥오리(*Anas platyrhynchos*)에서 가축화되었으나, 머스코비오리(*Cairina moschata*) 계통의 가축 오리도 별도로 존재한다. 배포된 원천 레이블은 '머스코비오리'이며, 1차 근거 없이 사향기러기 등으로 야생/가축 지위를 단정하지 않는다.
- **구현 관계 (3건)**:
  - `집오리` (`domestic_form`) → `domesticated_from` → *Anas platyrhynchos*
  - `집오리` (`domestic_form`) → `domesticated_from` → *Cairina moschata*
  - `청둥오리 계통의 가축 오리` (`domestic_form`) → `domesticated_from` → *Anas platyrhynchos*
- **검증 출처**: FAO (Ducks - Animal Production and Health): `https://www.fao.org/poultry-production-products/production/poultry-species/ducks/en`

## 3. 초기 패키지 매핑 요약 (8건)

| ID | 입력 명칭 (Name) | 엔티티 종류 (Kind) | 관계 유형 (Relation) | 대상 학명 (Scientific Name) | 1차 검증 URL |
|---|---|---|---|---|---|
| `pigeon-rock` | 비둘기 | `common_name` | `common_usage` | *Columba livia* | [Cornell Lab](https://www.allaboutbirds.org/guide/Rock_Pigeon/overview) |
| `domestic-pigeon-rock` | 집비둘기 | `domestic_form` | `domesticated_from` | *Columba livia* | [Cornell Lab](https://www.allaboutbirds.org/guide/Rock_Pigeon/overview) |
| `crow-corone` | 까마귀 | `common_name` | `common_usage` | *Corvus corone* | [NIBR 센서스](https://www.nibr.go.kr/aiibook/catImage/12/2015-2016.pdf) |
| `crow-large-billed` | 까마귀 | `common_name` | `common_usage` | *Corvus macrorhynchos* | [NIBR 센서스](https://www.nibr.go.kr/aiibook/catImage/12/2015-2016.pdf) |
| `chicken-red-junglefowl` | 닭 | `domestic_form` | `domesticated_from` | *Gallus gallus* | [Nature Cell Res](https://www.nature.com/articles/s41422-020-0349-y) |
| `domestic-duck-mallard` | 집오리 | `domestic_form` | `domesticated_from` | *Anas platyrhynchos* | [FAO Ducks](https://www.fao.org/poultry-production-products/production/poultry-species/ducks/en) |
| `domestic-duck-muscovy` | 집오리 | `domestic_form` | `domesticated_from` | *Cairina moschata* | [FAO Ducks](https://www.fao.org/poultry-production-products/production/poultry-species/ducks/en) |
| `domestic-mallard-specific`| 청둥오리 계통의 가축 오리 | `domestic_form` | `domesticated_from` | *Anas platyrhynchos* | [FAO Ducks](https://www.fao.org/poultry-production-products/production/poultry-species/ducks/en) |
