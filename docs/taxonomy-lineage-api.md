# AviList 분류 계통 API

## 목적

NAS에 배포한 RobinGraph API에서 학명을 기준으로 활성 AviList 분류체계의
목(order) → 과(family) → 속(genus) → 종(species) 계통을 조회한다. 운영 GBIF
관찰 데이터의 `ExternalTaxonConcept`와 AviList 기준 분류의 `Taxon`은 합치지 않는다.

## HTTP 계약

```http
GET /v1/taxa/lineage?scientific_name=Anas%20zonorhyncha
```

- `scientific_name`은 필수이며 앞뒤 공백을 제거한 뒤 대소문자 구분 없이 정확히
  일치시킨다.
- 허용 길이는 1~200자다.
- 첫 버전은 한국어 일반명이 아니라 안정적인 학명을 조회 키로 사용한다.
- `serve-neo4j`에서만 실제 조회가 가능하다. `serve-fixture`에서는 HTTP 503을
  반환한다.

성공 응답 예시는 다음과 같다. `taxonomy_release`와 `concept_set_id`는 현재 활성화된
AviList 적재 상태에서 읽으므로 배포 환경에 따라 값이 달라질 수 있다.

```json
{
  "query_scientific_name": "Anas zonorhyncha",
  "taxonomy_source": "AviList",
  "taxonomy_release": "v2025b",
  "concept_set_id": "rg:concept-set:avilist-v2025b",
  "lineage": [
    {
      "taxon_id": "...",
      "rank": "order",
      "scientific_name": "Anseriformes",
      "authority": null
    },
    {
      "taxon_id": "...",
      "rank": "family",
      "scientific_name": "Anatidae",
      "authority": null
    },
    {
      "taxon_id": "...",
      "rank": "genus",
      "scientific_name": "Anas",
      "authority": null
    },
    {
      "taxon_id": "...",
      "rank": "species",
      "scientific_name": "Anas zonorhyncha",
      "authority": null
    }
  ]
}
```

상태 코드는 다음과 같다.

| 상태 | 의미 |
|---|---|
| 200 | 활성 AviList concept set에서 계통 조회 성공 |
| 404 | 활성 분류체계에 정확히 일치하는 학명이 없음 |
| 422 | 누락, 공백 또는 길이 제한 위반 |
| 503 | Neo4j 모드가 아니거나 활성 분류 projection을 안전하게 읽을 수 없음 |

## Swagger와 NAS 호출

Reverse proxy가 제공하는 API 주소의 `/docs`를 열고 `GET /v1/taxa/lineage`에서
`Try it out`을 선택한다. `scientific_name`에 `Anas zonorhyncha`를 입력한 뒤
`Execute`를 누른다.

```sh
curl "https://<NAS-API-HOST>/v1/taxa/lineage?scientific_name=Anas%20zonorhyncha"
```

이 endpoint는 FastAPI를 호출한다. 브라우저나 외부 LLM wiki가 내부 Neo4j Bolt
주소(`bolt://...:7687`)를 직접 호출하지 않도록 한다.

## 데이터 경계와 실패 처리

- `IngestState {id: 'reference-taxonomy'}`의 `active_concept_set_id`와 활성 release만
  사용한다.
- 모든 사용자 입력은 Cypher parameter로 바인딩하며 query 문자열에 보간하지 않는다.
- `(Taxon:BirdTaxon)`만 조회하므로 GBIF `(ExternalTaxonConcept:BirdTaxon)`가 계통에
  섞이지 않는다.
- `PARENT_OF.concept_set_id`가 활성 concept set과 일치하는 관계만 순회한다.
- 누락되거나 잘못된 projection은 내부 예외를 노출하지 않고 HTTP 503 경계로 변환한다.

## 구현 위치와 검증

- API 및 OpenAPI 계약: `src/robingraph/api/app.py`
- 읽기 전용 도메인 계약: `src/robingraph/retrieval/taxonomy_lineage.py`
- Neo4j 조회: `src/robingraph/retrieval/taxonomy_lineage_neo4j.py`
- `serve-neo4j` wiring과 종료 처리: `src/robingraph/cli.py`
- API 테스트: `tests/test_api.py`
- Neo4j 계약 테스트: `tests/test_taxonomy_lineage_neo4j.py`

전체 로컬 테스트 결과는 177개 실행, 실패 0, 조건부 live integration 21개 skip이다.
소스 구현은 Claude, 독립 계약 테스트는 GPT-5.6 Terra가 맡았고 coordinator가 결과를
통합해 projection 검증과 전체 회귀 테스트를 완료했다.

## 배포 반영

새 환경 변수나 Neo4j 쓰기 권한은 필요하지 않다. NAS에서 현재 소스를 반영해 API
이미지를 다시 빌드·배포하고 `ROBINGRAPH_API_MODE=serve-neo4j`인지 확인한다. 배포 후
`/health`, `/docs`, 실제 계통 endpoint 순서로 확인한다.
