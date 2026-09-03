# RobinGraph 데이터 계약

- 상태: Draft
- 작성일: 2026-09-03
- 선행 문서: `system-design.md`
- 미확정 입력: 분류 기준판, 실제 외부 소스, 라이선스 허용 행렬, 좌표 민감도 정책

## 1. 목적

이 문서는 출처마다 다른 원본을 공통 staging 데이터로 변환할 때 지켜야 할 계약을 정의한다. 특정 API 필드명을 내부 도메인 모델에 직접 퍼뜨리지 않고, 원본 보존·분류 해소·중복 제거·provenance 생성을 재현 가능하게 하는 것이 목적이다.

모든 staging 데이터는 UTF-8 Parquet을 기본 교환 형식으로 사용한다. JSON이 필요한 중첩 값은 구조화된 Parquet 타입을 우선하고, 시스템 경계를 넘을 때만 명시적인 JSON Schema를 사용한다.

## 2. 공통 규칙

### 2.1 식별자

- 내부 ID는 UUIDv7 또는 동등한 불변 ID를 사용한다.
- 외부 ID는 `source_id`, `source_release`, `external_id`의 조합으로만 유일성을 판단한다.
- 표시 이름, URL, 학명 문자열, DOI를 내부 기본키로 사용하지 않는다.
- 결정적 재처리가 필요한 staging 행에는 위 조합에서 만든 `record_key`를 둔다.
- 외부 레코드가 갱신되면 이전 판본을 덮어쓰지 않고 `record_version`과 `supersedes_record_key`를 기록한다.

### 2.2 값과 결측

- 빈 문자열, `N/A`, `unknown`, 0을 같은 값으로 취급하지 않는다.
- 알 수 없는 값은 null로 저장하고 `missing_reason`이 제공되면 별도 필드에 보존한다.
- 날짜는 ISO 8601, 시각은 timezone이 있는 UTC를 기본으로 하며 원문도 보존한다.
- 날짜가 연·월·일 중 일부만 알려졌으면 값을 임의로 채우지 않고 `event_date_precision`을 기록한다.
- 좌표는 WGS84 십진도와 원문 좌표계를 함께 기록한다.
- 수량이 없는 관찰과 0개 관찰은 구분한다. 존재 기록에서 수량 미상은 null이다.
- enum에 없는 값은 버리지 않고 `raw_*` 필드에 보존하고 quarantine 또는 매핑 검토 대상으로 보낸다.

### 2.3 provenance 공통 필드

모든 staging 행은 다음 필드를 가져야 한다.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `record_key` | string | 예 | 내부 결정적 staging 키 |
| `source_id` | string | 예 | Source registry의 ID |
| `source_release` | string | 예 | 데이터 릴리스 또는 수집 스냅샷 ID |
| `external_id` | string | 예 | 원본 레코드 ID |
| `raw_object_uri` | string | 예 | 불변 원본 객체 위치 |
| `raw_sha256` | string | 예 | 원본 또는 원본 레코드의 해시 |
| `retrieved_at` | timestamp | 예 | UTC 수집 시각 |
| `parser_version` | string | 예 | 어댑터/파서 버전 |
| `ingestion_run_id` | string | 예 | 실행 manifest와 연결 |
| `license_policy_status` | enum | 예 | `allowed`, `restricted`, `review_required`, `denied` |

## 3. Source registry 계약

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `source_id` | string | 예 | 저장소 내 안정적 소스 ID |
| `name` | string | 예 | 공식 명칭 |
| `provider` | string | 예 | 제공 기관 |
| `landing_uri` | URI | 예 | 공식 소개/다운로드 페이지 |
| `access_method` | enum | 예 | `api`, `download`, `manual` |
| `auth_method` | enum | 예 | `none`, `api_key`, `oauth`, `manual` |
| `release_strategy` | enum | 예 | `versioned`, `dated_snapshot`, `mutable` |
| `incremental_cursor` | string/null | 아니요 | 갱신 시 사용할 필드 |
| `rate_limit_note` | string/null | 아니요 | 공식 제한과 준수 방법 |
| `license_uri` | URI | 예 | 수집 시점 라이선스 원문 |
| `terms_uri` | URI/null | 아니요 | 별도 이용 약관 |
| `adapter_owner` | string | 예 | 유지보수 책임 |
| `enabled` | boolean | 예 | 수집 활성 여부 |

API 키와 비밀 URL은 registry 파일에 넣지 않고 환경 변수나 비밀 저장소의 참조명만 둔다.

기계 검증용 JSON Schema는 `config/schemas/source-registry.schema.json`에 둔다. 애플리케이션은 같은 enum과 필수 필드를 `robingraph.ingest.validation.validate_source_registry_record`로 검증하며, source registry 오류는 fetch 전 차단한다.

## 4. 분류와 이름 staging

### 4.1 Taxon concept

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| 공통 provenance 필드 | - | 예 | 2.3 참조 |
| `source_taxon_id` | string | 예 | 출처 분류 ID |
| `source_parent_taxon_id` | string/null | 아니요 | 출처 상위 분류 ID |
| `rank` | enum | 예 | kingdom부터 infraspecific까지 통제 값 |
| `taxonomic_status` | string | 예 | 원문 지위 |
| `scientific_name_raw` | string | 예 | 원문 전체 학명 |
| `canonical_name` | string/null | 아니요 | 파싱한 canonical name |
| `authorship` | string/null | 아니요 | 저자명과 연도 |
| `accepted_source_taxon_id` | string/null | 아니요 | 동의어가 가리키는 인정 개념 |
| `name_according_to` | string/null | 아니요 | 분류 개념 출처 |
| `concept_set_version` | string | 예 | 분류 기준판 |

### 4.2 Vernacular name

필수 필드는 `source_taxon_id`, `name`, BCP 47 형식의 `language`, 적용 지역 `region_code`, `name_status`다. 언어 또는 지역을 모르는 이름은 전역 대표명으로 자동 승격하지 않는다.

## 5. 관찰 staging

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| 공통 provenance 필드 | - | 예 | 2.3 참조 |
| `occurrence_id` | string | 예 | 출처의 발생/관찰 ID |
| `event_id` | string/null | 아니요 | 조사 이벤트 또는 체크리스트 ID |
| `scientific_name_raw` | string | 예 | 원본에 기록된 동정명 |
| `source_taxon_id` | string/null | 아니요 | 출처 분류 ID |
| `observed_at` | timestamp/null | 아니요 | timezone이 확인된 시각 |
| `event_date_raw` | string | 예 | 원문 날짜 |
| `event_date_precision` | enum | 예 | `instant`, `day`, `month`, `year`, `range`, `unknown` |
| `count` | integer/null | 아니요 | 음수 금지 |
| `basis_of_record` | enum | 예 | 관찰, 표본, 문헌 등 |
| `latitude_private`, `longitude_private` | decimal/null | 아니요 | 접근 통제 원좌표 |
| `latitude_public`, `longitude_public` | decimal/null | 아니요 | 정책 적용 공개 좌표 |
| `coordinate_uncertainty_m` | number/null | 아니요 | 좌표 불확실성 |
| `geodetic_datum_raw` | string/null | 아니요 | 원문 좌표계 |
| `place_external_id` | string/null | 아니요 | 출처 지역 ID |
| `locality_public` | string/null | 아니요 | 공개 가능한 지역명 |
| `sensitivity_class` | enum | 예 | `public`, `generalized`, `withheld`, `unknown` |
| `observer_external_id` | string/null | 아니요 | 직접 개인정보 대신 출처 내 불투명 ID |
| `occurrence_status` | enum | 예 | `present`, `absent`, `unknown` |

원좌표와 공개 좌표는 같은 필드에 덮어쓰지 않는다. 민감도 정책이 정해지지 않은 레코드는 공개 API에 적재하지 않는다.

## 6. 장소와 서식지 staging

장소는 `place_external_id`, `name`, `place_type`, `country_code`, `admin_level`, `parent_place_external_id`, `geometry_uri`, `centroid`를 가진다. 큰 geometry는 그래프 속성에 직접 넣지 않고 파일 참조와 해시를 사용한다.

서식지는 `habitat_external_id`, `preferred_label`, `vocabulary`, `parent_habitat_external_id`, `description`을 가진다. 관찰의 자유 텍스트 서식지는 원문과 통제 어휘 후보를 모두 보존하며 자동 매핑 점수가 낮으면 검토 대상으로 둔다.

## 7. 미디어 staging

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| 공통 provenance 필드 | - | 예 | 2.3 참조 |
| `media_external_id` | string | 예 | 출처 자산 ID |
| `media_type` | enum | 예 | `image`, `audio`, `video` |
| `landing_uri` | URI | 예 | attribution을 볼 수 있는 원문 페이지 |
| `asset_uri` | URI/null | 아니요 | 직접 파일 URL, 저장 허용과 별개 |
| `creator` | string/null | 아니요 | 제작자 표시 |
| `captured_at` | timestamp/null | 아니요 | 촬영/녹음 시각 |
| `scientific_name_raw` | string/null | 아니요 | 원본 동정명 |
| `source_taxon_id` | string/null | 아니요 | 출처 분류 ID |
| `mime_type` | string/null | 아니요 | MIME |
| `width`, `height`, `duration_s` | number/null | 아니요 | 유형별 기술 정보 |
| `asset_sha256` | string/null | 아니요 | 다운로드가 허용된 경우 |
| `perceptual_hash` | string/null | 아니요 | 허용된 처리 범위에서만 생성 |
| `attribution_text` | string | 예 | 표시할 문구 |
| `redistribution_allowed` | tri-state | 예 | `true`, `false`, `unknown` |
| `embedding_allowed` | tri-state | 예 | 멀티모달 임베딩 허용 상태 |

## 8. 문헌·문서·청크 staging

Publication은 정규화 DOI, 제목, 저자, 연도, 발행처, 서지 문자열을 가진다. Document는 실제 접근한 웹페이지/PDF/데이터 설명서의 판본이며 `content_hash`, `retrieved_at`, `language`, `fulltext_storage_allowed`, `chunk_storage_allowed`, `embedding_allowed`를 별도로 가진다.

Chunk 필수 필드는 다음과 같다.

| 필드 | 설명 |
|---|---|
| `chunk_id` | document version과 ordinal에서 만든 안정적 ID |
| `document_id` | 특정 Document 판본 |
| `ordinal` | 문서 내 순서 |
| `section_path` | 제목 계층 |
| `text` | 정책상 저장 가능한 검색 텍스트 |
| `locator` | 페이지, 절, 문단, 표와 행 |
| `char_start`, `char_end` | 추출 본문 내 범위 |
| `token_count` | 사용 tokenizer와 함께 기록 |
| `content_hash` | 텍스트 변경 탐지 |
| `embedding_model`, `embedding_version` | 벡터 재현 정보 |

저장 불가 문서는 Chunk text를 만들지 않는다. 링크와 허용된 서지만으로는 해당 본문을 근거로 답변하지 않는다.

## 9. 분류 해소 결과 계약

| 필드 | 설명 |
|---|---|
| `input_record_key` | 매핑 대상 staging 행 |
| `input_name` | 원문 학명 |
| `backbone_version` | 사용한 기준판 |
| `resolved_taxon_id` | 확정된 내부 Taxon, 미확정이면 null |
| `candidate_taxon_ids` | 점수와 이유가 있는 후보 목록 |
| `resolution_method` | stable ID, approved crosswalk, exact, synonym, fuzzy, manual |
| `score` | 비교 가능한 범위가 명시된 점수 |
| `decision` | `accepted`, `ambiguous`, `unmatched`, `rejected` |
| `rule_version` | 해소 규칙 버전 |
| `reviewer`, `reviewed_at` | 사람 검토 정보 |

fuzzy 결과는 후보 생성에만 사용하고 자동 병합하지 않는다. `ambiguous`와 `unmatched`는 관찰 원본을 버리는 이유가 아니며 그래프 연결만 보류한다.

## 10. 중복 후보 계약

중복 그룹은 원본을 삭제하지 않고 `duplicate_group_id`, `member_record_keys`, `representative_record_key`, `match_method`, `score`, `rule_version`, `review_status`를 기록한다. 집계는 승인된 그룹에서 대표 레코드만 세지만 각 출처와 라이선스는 모두 유지한다.

## 11. 라이선스 정책 계약

각 라이선스 판정은 다음 동작을 개별 tri-state로 갖는다.

- 메타데이터 저장
- 원문/파일 저장
- Chunk 저장
- 임베딩 생성과 저장
- 검색 컨텍스트 사용
- 답변 인용
- 썸네일 표시
- 원본 재배포
- 상업 서비스 사용
- 파생물 생성

상태는 `allowed`, `denied`, `review_required` 중 하나다. `review_required`는 기본적으로 검색과 생성에서 제외한다. 판정에는 라이선스 원문 URL, 확인일, 적용 객체 범위, attribution template, 판정자, 정책 버전을 저장한다.

## 12. Quarantine 계약

| 필드 | 설명 |
|---|---|
| `record_key` | 실패한 원본 staging 키 |
| `stage` | fetch, parse, validate, resolve, dedupe, load, embed |
| `reason_code` | 안정적 기계 판독 코드 |
| `severity` | warning, error, blocked |
| `field_path` | 문제가 난 필드 |
| `raw_value_redacted` | 민감정보를 제거한 값 |
| `rule_version` | 검증 규칙 버전 |
| `first_seen_run_id`, `last_seen_run_id` | 발생 이력 |
| `resolution_status` | open, ignored, fixed, source_fixed |

파서 예외로 전체 실행을 중단하기보다 행 단위 격리를 우선하되, 라이선스 manifest 누락이나 기준판 불일치처럼 전체 릴리스 신뢰를 깨는 오류는 release activation을 막는다.

## 13. Ingestion manifest와 활성화

manifest는 실행 ID, pipeline Git SHA, 설정 해시, 시작/종료 시각, 각 원본 URI·해시·바이트 수, staging 행 수, quarantine 수, 분류 해소 분포, 중복 그룹 수, 그래프 upsert 수, 임베딩 성공/실패 수를 가진다.

한 실행은 다음 조건을 모두 만족할 때만 활성화한다.

- 필수 원본 해시가 모두 존재한다.
- 차단 등급 quarantine이 없다.
- 출처·라이선스 연결 완전성이 100%다.
- 그래프 참조 무결성 위반이 없다.
- 이름 해소율과 변동 폭이 설정된 gate 안에 있다.
- 임베딩 실패가 허용 한도 안에 있다.
- 동일 manifest 재실행 결과가 논리적으로 동일하다.

## 14. 권장 소스의 계약 매핑

아래는 소스 수준 매핑이다. 정확한 원본 열 이름과 enum 변환은 고정된 샘플 파일을 받은 뒤 추가한다.

| 내부 계약 | 선택 소스 원본 필드 | 변환 | 결측/격리 규칙 | 라이선스 정책 |
|---|---|---|---|---|
| Taxon concept | AviList v2025b + NIBR 국가생물종목록 | AviList를 기준 concept set으로, NIBR은 별도 concept set과 한국어 이름으로 변환 | 릴리스 범위 키 생성, ambiguous crosswalk 격리 | AviList CC BY 4.0. NIBR은 정확한 공공누리 유형 확인 전 적재 보류 |
| Observation | GBIF Occurrence | GBIF dataset key, gbifID/occurrenceID, taxon key, event/좌표 필드를 staging에 보존 | CC0/CC BY 데이터셋만 수집, taxon unresolved와 민감도 unknown은 공개 적재 보류 | 데이터셋 단위 라이선스와 DOI를 SourceDataset/다운로드 manifest에 연결 |
| Place | 국가공간정보포털 행정구역 경계 | 행정 코드와 계층을 Place로, 좌표 공간 조인은 버전 기록 | 정확한 이용 조건 확인 전 fixture만 사용 | 공공누리 유형 확인 필요 |
| Habitat | EcoBank | 국내 서식지 라벨을 별도 vocabulary로 유지 | 자유 텍스트 자동 병합 금지 | 항목별 공공누리 유형 확인 전 검색 적재 보류 |
| Image | iNaturalist | CC0/CC BY 자산의 ID, landing URL, creator, license, taxon만 저장 | 관찰 라이선스와 사진 라이선스를 별도 확인 | 파일 저장 없이 메타데이터/딥링크. 자산별 allowlist |
| Audio | Xeno-canto | CC0/CC BY 녹음의 XC ID, landing URL, recordist, license, taxon만 저장 | API 제한 준수, 동정 신뢰도와 배경종 보존 | 파일 저장 없이 메타데이터/딥링크. 자산별 allowlist |
| Publication | Crossref | DOI, 제목, 저자, 연도, 발행처를 Publication으로 변환 | 초록은 메타데이터와 분리하고 권리 확인 전 저장하지 않음 | 서지 메타데이터 CC0 |
| Document/Chunk | 개별 OA 논문·정부 발간물 | 허용 목록이 확인된 판본만 Document/Chunk 생성 | 문서별 license snapshot이 없으면 Chunk 생성 금지 | CC0·CC BY·공공누리 1유형만 MVP 허용 |

이 매핑의 관련 ADR이 승인되고 실제 샘플 열을 검증하기 전에는 외부 데이터 수집 코드를 작성하지 않는다.
