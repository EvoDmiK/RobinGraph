# ADR-0002: MVP 분류 기준판과 한국어 이름

- 상태: Proposed
- 작성일: 2026-09-03
- 근거 입력: `docs/data-source-decision-input.md`

## 맥락

조류 분류는 IOC, Clements/eBird, GBIF, 국내 국가생물종목록 사이에 차이가 있고 개정도 잦다. GraphRAG가 학명, 동의어, 한국어 이름, 관찰 기록을 일관되게 연결하려면 제품이 따르는 기준판 하나와 외부 소스 crosswalk가 필요하다.

## 결정

- 국제 조류 분류의 MVP 기준판으로 **AviList v2025b** 스냅샷을 사용한다.
- 국립생물자원관 국가생물종목록은 별도 `TaxonConceptSet`으로 유지하고, 정확한 공공누리 유형을 확인한 뒤 한국어 일반명과 국내 지정 정보를 연결한다.
- 외부 분류 개념을 하나로 덮어쓰지 않는다. 원 출처 개념, 이름, 지위를 보존하고 승인된 crosswalk로 AviList 개념에 연결한다.
- 다음 AviList 판이 나와도 기존 Taxon을 수정하지 않고 새 concept set과 버전 간 매핑을 만든다.

## 이유

- AviList는 주요 국제 조류 목록을 통합하려는 최신 기준판이며 CC BY 4.0으로 명시되어 있다.
- 장기 유지가 종료되는 방향인 IOC 독자판이나 향후 교체가 예고된 GBIF Backbone을 신규 제품의 장기 기준으로 택하는 위험을 줄인다.
- NIBR은 한국어 이름과 국내 맥락에 필요하지만 국제 기준판과 분리해야 분류 충돌을 표현할 수 있다.

## ID 정책

AviList의 sequence나 학명 문자열을 내부 ID로 사용하지 않는다. 소스 레코드는 `avilist:v2025b:<release-scoped-key>` 형태의 릴리스 범위 키를 사용하고, Taxon은 별도 불변 내부 ID를 가진다. 차기 판으로의 연속성은 accepted name, rank, parent lineage와 사람이 검토한 split/merge crosswalk로 판단한다.

## 검토한 대안

- **IOC World Bird List**: 풍부한 이력이 있으나 독자 갱신 종료 방향 때문에 신규 장기 기준으로 부적합하다.
- **Clements/eBird Taxonomy**: eBird 관찰과 연결하기 편하지만 재배포 조건과 장기 유지 방향을 추가 확인해야 한다.
- **GBIF Backbone**: occurrence 연결은 쉽지만 전 생물군 중심이며 분류 백본 전환 계획이 있어 조류 기준판으로 고정하기 어렵다.
- **NIBR 단독**: 국내 이름과 지정 정보에는 강하지만 국제 문헌·관찰 소스와의 연결을 위해 별도 국제 기준이 필요하다.

## 확정 전 조건

- AviList v2025b 다운로드 파일, 인용문, CC BY 4.0 원문을 프로젝트 manifest에 보존한다.
- AviList 행을 재현 가능하게 식별할 release-scoped key 규칙을 실제 열 구성에 맞춰 검증한다.
- NIBR 국가생물종목록의 정확한 공공누리 유형과 API/다운로드 조건을 확인한다.
- MVP 대상 종 표본으로 AviList↔NIBR crosswalk를 만들고 split, merge, synonym 사례를 검토한다.

## 결과

NIBR 조건 확인 전에는 해당 데이터를 운영 그래프에 넣지 않는다. fixture에서는 출처와 사용 허가가 명확한 소수 한국어 이름만 사용한다.

## 추가 결정 (2026-09-11): Wikidata를 한국어 일반명의 임시 승인 소스로 채택

확인한 NIBR 데이터셋(15048041)은 공공누리 제3유형으로 기본 허용 목록 밖이므로
운영 적재 비활성 상태를 유지한다(ADR-0005 참조). 별도로 Wikidata
구조화 데이터(query.wikidata.org)가 **CC0**로 명시되어 있음을
<https://www.wikidata.org/wiki/Wikidata:Licensing>에서 직접 확인했고, 실제
SPARQL 질의로 조류 종 학명과 한국어 label이 함께 반환됨을 확인했다(예:
Q25348 → `Anas platyrhynchos` → `청둥오리`). 이 라이선스는 ADR-0003의 허용
목록(CC0/CC BY/공공누리 1유형)에 그대로 해당하므로, NIBR과 별개로
`korean-vernacular-wikidata-species-labels` collection point를 승인해
한국어 `VernacularName` 적재를 시작한다.

- 이 결정은 NIBR의 상태를 바꾸지 않는다. NIBR이 나중에 승인되면 국내 법적
  지위(멸종위기종 등)와 국명을 원 출처로 병행 적재하는 기존 계획은 그대로
  유효하다.
- Wikidata 적재는 활성 `reference-taxonomy` concept set의 기존 `Taxon`에
  학명 완전 일치로만 붙이며, 충돌하거나 모호한 매칭은 `VernacularNameCandidate`로
  격리하고 임의로 하나를 선택하지 않는다.
- 상세 실행 계약: [n8n 한국어 일반명 수집 런북](../n8n/korean-vernacular-ingest.md).
