# AviList 분류 계통 API

## 목적

NAS에 배포한 RobinGraph API에서 학명 또는 한국어 일반명을 기준으로 활성 AviList
분류체계의 목(order) → 과(family) → 속(genus) → 종(species) 계통을 조회한다.
운영 GBIF 관찰 데이터의 `ExternalTaxonConcept`와 AviList 기준 분류의 `Taxon`은
합치지 않는다.

## HTTP 계약

```http
GET /v1/taxa/lineage?scientific_name=Anas%20zonorhyncha
GET /v1/taxa/lineage?name=흰뺨검둥오리
```

- `scientific_name`과 `name` 중 **정확히 하나**만 전달해야 한다. 둘 다 없거나
  둘 다 있으면 422다.
- 두 파라미터 모두 앞뒤 공백을 제거한 뒤 1~200자여야 하며 공백만 있는 값은
  422다.
- `scientific_name`은 활성 AviList concept set에 속한 `Taxon.scientific_name`과
  대소문자 구분 없이 정확히 일치시킨다 (기존 동작, 변경 없음).
- `name`은 대상 `Taxon`에 직접 연결된(`HAS_VERNACULAR_NAME`) 한국어
  `VernacularName`(`language: 'ko'`)의 이름과 대소문자 구분 없이 정확히
  일치시킨다. 이 조회는 활성 concept set 안에서만 이루어지며, 학명 조회와
  동일한 조상(ancestor) 순회 로직을 공유한다.
- `serve-neo4j`에서만 실제 조회가 가능하다. `serve-fixture`에서는 HTTP 503을
  반환한다.
- 현재 AviList 적재의 일반명은 영명(`language: 'en'`)만 보장된다. 한국어
  `VernacularName`은 데이터 모델과 조회 경로가 준비되어 있을 뿐, 아직 라이선스
  적재가 없는 종은 `name=` 조회가 항상 404를 반환한다 — 이는 결함이 아니라
  현재 AviList 적재 상태를 그대로 반영한 것이다. 한국어 이름을 임의로
  번역·생성해 채우지 않는다.
- [n8n 한국어 일반명 수집 런북](n8n/korean-vernacular-ingest.md)이 이 간극을
  메우는 별도 적재 경로(Wikidata CC0 구조화 데이터, 학명으로 활성 AviList
  `Taxon`에만 매칭)를 정의한다. 다만 이 문서 작성 시점에는 그 workflow가
  오프라인으로만 검증되었고 실제 n8n/Neo4j에서 실행된 적이 없다 — 실행 전까지는
  `청둥오리` 같은 이름도 여전히 404를 반환한다.

성공 응답 예시는 다음과 같다. `taxonomy_release`와 `concept_set_id`는 현재 활성화된
AviList 적재 상태에서 읽으므로 배포 환경에 따라 값이 달라질 수 있다. 아래는
`scientific_name` 조회 예시다 (`name` 조회는 `matched_by`가 `"korean_name"`이고
`query_name`이 입력한 한국어 이름이 된다는 점만 다르다).

```json
{
  "query_name": "Anas zonorhyncha",
  "query_scientific_name": "Anas zonorhyncha",
  "resolved_query_scientific_name": "Anas zonorhyncha",
  "matched_by": "scientific_name",
  "taxonomy_source": "AviList",
  "taxonomy_release": "v2025b",
  "concept_set_id": "rg:concept-set:avilist-v2025b",
  "lineage": [
    {
      "taxon_id": "...",
      "rank": "order",
      "scientific_name": "Anseriformes",
      "authority": null,
      "korean_name": null,
      "korean_name_status": null
    },
    {
      "taxon_id": "...",
      "rank": "family",
      "scientific_name": "Anatidae",
      "authority": null,
      "korean_name": null,
      "korean_name_status": null
    },
    {
      "taxon_id": "...",
      "rank": "genus",
      "scientific_name": "Anas",
      "authority": null,
      "korean_name": null,
      "korean_name_status": null
    },
    {
      "taxon_id": "...",
      "rank": "species",
      "scientific_name": "Anas zonorhyncha",
      "authority": null,
      "korean_name": "흰뺨검둥오리",
      "korean_name_status": "community-sourced"
    }
  ]
}
```

응답 필드는 다음과 같다.

| 필드 | 의미 |
|---|---|
| `query_name` | 요청에 사용된 원본 값(공백 제거 후). `scientific_name=` 요청이면 학명, `name=` 요청이면 한국어 이름이다. |
| `query_scientific_name` | 기존(레거시) 필드. `scientific_name=` 요청에서는 이전과 동일하게 공백만 제거한 입력값 원문이다. `name=` 요청에서는 실제로 일치한 학명이다. |
| `resolved_query_scientific_name` | 새 필드. 조회로 실제 일치한 대상 `Taxon`의 정식 학명이며 두 조회 경로 모두에서 항상 채워진다. |
| `matched_by` | `"scientific_name"` 또는 `"korean_name"` — 어느 경로로 대상을 찾았는지. |
| `lineage[].korean_name` | 각 계통 항목(조상 포함)에 직접 연결된 한국어 `VernacularName`이 있으면 그 이름, 없으면 `null`이다. |
| `lineage[].korean_name_status` | 해당 `korean_name`을 적재한 `VernacularName.status`. `korean_name`이 `null`이면 항상 `null`이다. 현재 값은 `"community-sourced"`([n8n 한국어 일반명 수집 런북](n8n/korean-vernacular-ingest.md), Wikidata 구조화 데이터)뿐이며 **국립생물자원관(NIBR) 등 공식 국명이 아니다** — 커뮤니티가 계속 편집하는 Wikidata 항목의 한국어 label이다. NIBR 공식 국명이 승인·적재되면 다른 `status` 값(예: `"source-preferred"`)으로 구분한다([ADR-0002](decisions/0002-taxonomy-backbone.md) 참고). |

`taxonomy_source`, `taxonomy_release`, `concept_set_id`, `lineage[].taxon_id` /
`rank` / `scientific_name` / `authority`는 기존과 동일하다.

상태 코드는 다음과 같다.

| 상태 | 의미 |
|---|---|
| 200 | 활성 AviList concept set에서 계통 조회 성공 |
| 404 | `scientific_name=`: 활성 분류체계에 정확히 일치하는 학명이 없음. `name=`: 대상 `Taxon`에 직접 연결된 라이선스 한국어 `VernacularName`이 없음 |
| 422 | `scientific_name`/`name` 중 정확히 하나가 아님, 누락, 공백 또는 길이(1~200자) 제한 위반 |
| 503 | Neo4j 모드가 아니거나 활성 분류 projection을 안전하게 읽을 수 없음 |

## Swagger와 NAS 호출

Reverse proxy가 제공하는 API 주소의 `/docs`를 열면 `GET /v1/taxa/lineage`에
`scientific_name`과 `name` 두 query parameter가 모두 노출된다. `Try it out`을
선택한 뒤 둘 중 하나에만 값을 입력하고 `Execute`를 누른다.

```sh
curl "https://<NAS-API-HOST>/v1/taxa/lineage?scientific_name=Anas%20zonorhyncha"
curl "https://<NAS-API-HOST>/v1/taxa/lineage?name=%ED%9D%B0%EB%BA%A8%EA%B2%80%EB%91%A5%EC%98%A4%EB%A6%AC"
```

이 endpoint는 FastAPI를 호출한다. 브라우저나 외부 LLM wiki가 내부 Neo4j Bolt
주소(`bolt://...:7687`)를 직접 호출하지 않도록 한다.

## 데이터 경계와 실패 처리

- `IngestState {id: 'reference-taxonomy'}`의 `active_concept_set_id`와 활성 release만
  사용한다.
- 모든 사용자 입력은 Cypher parameter로 바인딩하며 query 문자열에 보간하지 않는다.
  `name=` 조회도 동일하게 `$korean_name` parameter로 바인딩한다.
- `(Taxon:BirdTaxon)`만 조회하므로 GBIF `(ExternalTaxonConcept:BirdTaxon)`가 계통에
  섞이지 않는다. 한국어 `VernacularName` 조회도 `Taxon:BirdTaxon`에 직접 연결된
  것만 읽으며 GBIF `ExternalTaxonConcept`는 절대 조회·병합하지 않는다.
- 한국어 `VernacularName`은 대상 조회와 계통 항목의 `korean_name` 투영 모두에서
  `VernacularName -[:FROM_RECORD]-> SourceRecord -[:IN_DATASET]->
  SourceDataset {policy_status: 'allowed'}` 연결이 끊기지 않아야만 조회된다.
  이는 화면 표시 필터가 아니라 조회 자체의 경계다 — 승인된 적재 경로를 거치지
  않았거나, 나중에 정책이 바뀌어 `review_required`/`restricted`로 내려간
  데이터셋에 연결된 이름은 계통에서 감춰지는 게 아니라 애초에 대상을 찾지
  못한다(적재된 적 없는 이름과 구분되지 않는다).
- `PARENT_OF.concept_set_id`가 활성 concept set과 일치하는 관계만 순회한다.
- 두 조회 경로 모두 대상 `Taxon`을 `ORDER BY target.id LIMIT 1`로 결정론적으로
  하나만 선택한 뒤 조상 순회를 시작하므로, 동일한 학명이나 동일한 한국어
  이름을 가진 `Taxon`이 둘 이상 있어도 모호하게 fan-out 되지 않는다. 한국어
  이름 노드가 같은 대상에 중복 연결된 경우에도 대상 후보를 먼저 중복 제거한다.
- 한 계통 항목에 한국어 일반명이 여러 개 연결된 비정상·중복 데이터는 이름순으로
  하나만 결정적으로 선택하며, 선택한 이름의 `status`도 같은 `VernacularName`
  노드에서 함께 가져온다(서로 다른 노드의 이름과 상태를 따로 집계해 섞지
  않는다). 항목을 중복 반환하거나 입력값으로 새 이름을 만들지 않는다.
- 누락되거나 잘못된 projection은 내부 예외를 노출하지 않고 HTTP 503 경계로 변환한다.
- fixture 그래프(`Taxon:RobinGraph:Fixture`)의 이름은 AviList 기준 분류에 절대
  복사하지 않으며, 라이선스가 확인되지 않은 한국어 번역을 임의로 만들어 채우지
  않는다.

## 구현 위치와 검증

- API 및 OpenAPI 계약: `src/robingraph/api/app.py`
- 읽기 전용 도메인 계약: `src/robingraph/retrieval/taxonomy_lineage.py`
- Neo4j 조회: `src/robingraph/retrieval/taxonomy_lineage_neo4j.py`
- `serve-neo4j` wiring과 종료 처리: `src/robingraph/cli.py`
- API 테스트: `tests/test_api.py`
- Neo4j 계약 테스트: `tests/test_taxonomy_lineage_neo4j.py`

`scientific_name=` 경로의 기존 조회 계약은 유지한다. 계약 테스트는 기존 학명 경로와
`name=` 한국어 경로 모두에 대해 `query_name` /
`resolved_query_scientific_name` / `matched_by` / `lineage[].korean_name`, 활성
concept set 경계, 파라미터 바인딩, 중복 이름의 결정적 처리를 검증한다. 전체
오프라인 테스트는 200개 통과, 조건부 live integration 21개 skip, 실패 0이다.

## 배포 반영

새 환경 변수나 Neo4j 쓰기 권한은 필요하지 않다. NAS에서 현재 소스를 반영해 API
이미지를 다시 빌드·배포하고 `ROBINGRAPH_API_MODE=serve-neo4j`인지 확인한다. 배포 후
`/health`, `/docs`, 실제 계통 endpoint(`scientific_name=`, `name=` 둘 다) 순서로
확인한다.
