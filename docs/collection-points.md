# 종 정보 수집 포인트 선정

- 기준일: 2026-09-09
- 선택 설계: `terra-claim-first`
- 실행 설정: `config/source-registry.json`, `config/collection-points.json`

## 제안 점수

두 제안은 담당 범위가 달랐으므로 사실 조사량이 아니라 RobinGraph의 전체 수집 설계로 바로 사용할 수 있는지를 평가했다.

| 평가 기준 | 배점 | Claude 분류학안 | GPT-5.6 Terra Claim안 |
|---|---:|---:|---:|
| 공식·권위 소스의 정확성 | 25 | 24 | 22 |
| 라이선스 차단 안전성 | 20 | 14 | 19 |
| provenance·Claim 모델 적합성 | 25 | 16 | 24 |
| 특징·서식지·식생 범위 | 15 | 7 | 15 |
| 구현 가능성 | 15 | 12 | 13 |
| **합계** | **100** | **73** | **93** |

Claude안은 AviList, Catalogue of Life, NIBR의 역할 구분이 강하다. Terra안은 식생을 종의 고정 속성으로 만들지 않고 직접 관찰·문헌·공간 추론을 구분하며, 제한된 원문을 Claim이나 Chunk로 잘못 적재하지 않는 경계가 더 명확하다. 따라서 Terra안을 골격으로 선택하고 Claude안의 분류학 소스를 수집 포인트에 결합했다.

## 소스별 선정 점수와 상태

점수는 해당 역할 안에서 권위, 라이선스 명확성, 기계 접근성, 안정적 ID·버전, RobinGraph 계약 적합성을 합산한 100점 척도다. 점수가 높아도 라이선스가 `review_required` 또는 `restricted`이면 자동 수집하지 않는다.

| 수집 포인트 | 점수 | 상태 | 적재 방식 |
|---|---:|---|---|
| AviList v2025b | 92 | enabled | 버전·해시를 고정한 taxonomy snapshot |
| Catalogue of Life / ChecklistBank | 88 | enabled | 동의어·외부 ID·crosswalk Claim |
| EltonTraits 1.0 | 90 | enabled | 값·단위·출처가 분리된 TraitClaim |
| GBIF Species name match | 82 | review_required | 자동 병합하지 않는 mapping candidate |
| EcoBank 식생 공간결합 | 81 | review_required | layer 버전과 방법을 가진 spatial inference |
| IUCN Red List API v4 | 79 | restricted | 승인 전 link-only |
| AVONET | 78 | enabled | Figshare v7 파일 34480856의 CC BY 4.0 확인, 형태·서식 환경 claim |
| Wikidata 한국어 일반명 | 74 | enabled | CC0 확인(2026-09-11), 학명 완전 일치로만 매칭, 충돌·미매칭은 candidate로 격리 |
| NIBR | 76 | review_required | 승인 전 metadata·link-only |

현재 자동 수집 가능한 포인트는 AviList, ChecklistBank, EltonTraits, AVONET, Wikidata 한국어 일반명 다섯 개다. Wikidata 포인트(`korean-vernacular-wikidata-species-labels`)는 국립생물자원관(NIBR)과는 별개다 — NIBR은 정확한 공공누리 유형이 확인되기 전까지 여전히 `review_required`/`enabled: false`로 남는다([ADR-0002](decisions/0002-taxonomy-backbone.md) 참고). Wikidata는 커뮤니티가 계속 편집하는 데이터라 고정 SHA-256 대신 매 실행마다 응답을 해시해 보존하고, 활성 `reference-taxonomy` concept set의 기존 `Taxon`에만 학명 완전 일치로 붙인다. 자세한 실행 계약은 [n8n 한국어 일반명 수집 런북](n8n/korean-vernacular-ingest.md)에 기록한다. AVONET은 Figshare article 16586228 v7의 파일 34480856과 SHA-256을 고정하고 별도 n8n workflow에서 형태·서식 환경 claim을 수집한다. [실행 가이드](n8n/species-information-ingest.md)를 참고한다. AviList는 v2025b Extended XLSX의 직접 URL과 SHA-256을, ChecklistBank는 Catalogue of Life 2026-08-20 릴리스(dataset 316115, DOI 10.48580/dgywk)를, EltonTraits는 Figshare의 조류 파일(`BirdFuncDat.txt`, file ID 5631081, CC0)과 SHA-256을 고정했다. 나머지는 설정에는 남겨 운영자가 확인할 수 있지만 `enabled=false`이며 런타임 loader가 비허용 포인트의 활성화를 거부한다.

AviList·ChecklistBank·EltonTraits는 `n8n/robingraph-reference-ingest.json`에 연결했다. AviList와 EltonTraits는 snapshot을 직접 내려받아 SHA-256과 행 수를 확인한 뒤 Neo4j에 배치 적재한다. ChecklistBank는 고정 릴리스 메타데이터를 먼저 확인하고 EltonTraits 미대응 학명의 검토 URL을 제공하지만, fuzzy match를 자동 승인하지 않는다. 상세한 실행 계약은 [n8n 분류·형질 기준정보 수집 런북](n8n/reference-ingest.md)에 기록한다.

## 수집 경계

- taxonomy는 AviList concept set을 기준으로 하고 다른 출처를 별도 `ExternalTaxonConcept`와 `TaxonMappingClaim`으로 보존한다.
- trait 값은 하나의 종 설명 문장으로 합치지 않고 값마다 `TraitClaim`과 `EvidenceUnit`을 만든다.
- 식생 공간결합은 `VegetationAssociationClaim`이며 `evidence_kind=spatial_inference`를 강제한다. layer ID·버전, CRS, buffer, 관찰일, 방법, confidence를 후속 adapter의 필수값으로 둔다.
- `review_required`와 `restricted` 소스는 endpoint가 등록돼 있어도 자동 fetch·Chunk·embedding 대상이 아니다.

설정은 다음 명령으로 검증하고 조회한다.

```sh
uv run --locked robingraph collection-points
uv run --locked robingraph collection-points --scope vegetation --include-blocked
```
