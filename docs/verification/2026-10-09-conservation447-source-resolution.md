# 평가 참고 자료 미연결 447종: 전수 조사와 출처별 연결 결과

작성 기준일: 2026-10-09. 이 문서는 보전 자료 담당 작업의 소스 조사, 구현 및 검증 결과를 기록한다. 전체 기능 통합, 실제 TEST API/브라우저 확인, 커밋 및 NAS 배포의 최종 결과는 조정자의 작업 기록에서 별도로 확인해야 한다.

## 요청 배경과 목표

사용자는 AviList의 NE가 실제 개별 평가의 미평가 여부와 동일하지 않다는 설명을 받은 뒤 자료 신뢰성 개선과 다른 출처 탐색을 요청했다. 이번 범위는 일부 예시만 조사하는 것이 아니라, 기존 런타임 감사에서 `assessment_status=needs_review`이고 `reference_category=null`이었던 447종 모두의 공개 자료 연결 가능성을 확인하는 것이다.

대상은 [기존 런타임 감사 JSON](assets/2026-10-09-active-species-runtime-audit.json)의 해당 조건에 해당하는 종으로 고정했다. 종별 고유 ID, 학명 및 명명자를 공식 AviList v2025b 스냅샷과 다시 대조했고, 모든 대상의 원자료 등급이 NE임을 확인했다. 같은 기준으로 모든 447종을 처리한 결과는 [종별 조사 ledger](assets/2026-10-09-unresolved-conservation-review.json)에 저장했다. 현재 변경 후 API 결과를 이 과거 입력 감사와 혼동하지 않아야 한다.

## 결과와 의미

| 선택한 참고 출처 또는 결과 | 종 수 | 처리 |
|---|---:|---|
| 공식 IUCN · GBIF 공개 목록 | 25 | 기존 엄격한 확정 연결과 분리한 참고 평가 추가 |
| BIRDBASE v2025.1의 IUCN 2024 등급 열 | 117 | 저자의 명시적 AviList 학명 연결을 이용한 참고 자료 추가 |
| 조사한 공개 자료에 연결 가능한 등급 없음 | 305 | 원본의 등급 부재와 검토 필요 상태 유지 |
| 합계 | 447 | 모두 원본 행 및 조사 결과 보존 |

추가 참고 연결은 142종이다. BIRDBASE 원본에서는 447종 중 142종에 등급이 있었고 305종의 등급 셀이 비어 있었다. 그 142종 중 25종에는 공식 GBIF 참고 자료가 우선 적용되어, BIRDBASE의 순수 추가 연결 수는 117종이다. 305종은 **검토한 고정 공개 자료에서 연결 가능한 등급을 찾지 못했다**는 뜻이며, 세계 어느 출처에도 평가가 없다는 결론이 아니다.

| 참고 등급 | GBIF 25종 | BIRDBASE 신규 117종 | 총 142종 |
|---|---:|---:|---:|
| LC | 25 | 108 | 133 |
| NT | 0 | 2 | 2 |
| VU | 0 | 2 | 2 |
| EN | 0 | 1 | 1 |
| CR | 0 | 3 | 3 |
| EX | 0 | 1 | 1 |

이 표의 등급은 각 참고 자료의 값이다. 현재 AviList 종 개념과 개별 평가의 생물학적 범위가 일치한다는 검증을 수행하지 않았으므로, 모든 신규 참고 연결은 `assessment_status=reference_only`, `taxonomy_alignment=unverified`, `independently_verified=false`를 유지한다. 현재 종의 확정 보전 등급으로 승격한 종은 0종이다. 기존 확정 연결 7,507종의 `taxa` 객체는 변경 전 HEAD의 객체와 전체 값이 동일함을 다시 비교했다. 기존 까치의 요청에 따른 앱 표시 계약은 이번 작업으로 수정하지 않았다.

## 확인한 원인과 전수 분류

GBIF 고정 목록을 먼저 조사했을 때 대상 종별 결과는 다음과 같았다. 이 분류는 GBIF 조사 결과이며, BIRDBASE 추가 연결 이후의 최종 25/117/305 집계와 별도이다.

| GBIF 단계의 종별 분류 | 종 수 |
|---|---:|
| 같은 학명 참고 연결 가능, 종 개념 일치 미검증 | 25 |
| 같은 학명이 있지만 명명자·식별 근거 충돌 | 93 |
| 다른 학명 또는 분류 범위에 관한 후보 존재 | 302 |
| 고정 GBIF 자료에서 후보 없음 | 27 |
| 합계 | 447 |

후보 레코드별 문제는 다른 학명·분류 범위 후보 548건, 같은 학명의 명명자 표기 또는 동일성 충돌 53건, 명명 연도 충돌 40건, 안전하게 표시 가능한 같은 학명 참고 자료 25건이었다. 후보 건수는 종 수와 같은 분모가 아니다. 하나의 종에 여러 후보가 있을 수 있다.

AviList 공식 분류 결정문에서 split 관련 표현이 있는 종은 269종, lump 관련 표현이 있는 종은 116종, 속 변경 관련 표현이 있는 종은 15종이었다. 이 표현 기반 분류는 서로 겹칠 수 있고, 종 개념의 동등성을 확정하는 판정이 아니다. 결정문이 비어 있는 종은 23종이다. 모든 결정문, 후보 발견 경로, 원문 학명·명명자·SIS·인용·Global 등급과 충돌 사유를 ledger에 보존했다.

후보 발견에는 정확한 학명, 공식 결정문에 언급된 학명, 결정문에 나타난 현재 학명과 기존 속명의 명목상 연결, 같은 종소명·명명자·연도의 다른 속명이라는 네 경로를 사용했다. 다른 속을 찾는 단계에서 명명자 괄호를 제거한 비교는 후보 탐색에만 사용했고, 그 결과를 참고 등급이나 확정 등급 연결에 사용하지 않았다. 모든 후보의 `assign_grade_to_target`은 false다.

추가 검토에서 `Parus cinereus`의 명목상 연쇄에 `Dendrocopos major`와 `Circaetus cinereus`가 섞이는 오탐을 발견했다. 종소명·명명자·연도만으로는 서로 다른 목·과의 종이 충돌할 수 있었기 때문이다. 런타임 참고 또는 확정 연결에는 원래 사용되지 않았지만, 감사 후보 자체의 신뢰성을 높이기 위해 약한 두 명목상 연쇄 경로는 비어 있지 않은 목과 과가 모두 일치해야 후보로 허용하도록 수정했다. 대소문자만 정규화하며, 목이나 과가 없거나 다르면 그 경로를 제외한다. 실제 명시된 같은 학명 또는 공식 결정문에 직접 적힌 출처 학명은 직접 근거로 따로 유지한다. 분류 체계마다 과 또는 목의 취급이 다를 수 있어, 이 보수적 필터는 모든 실제 과거 학명 연결을 보장하지 않는다.

전체 447종을 다시 생성한 결과 명목상 경로에서 제외된 종·후보 쌍은 449건이다. 일부는 정확한 학명 또는 결정문 직접 언급이라는 별도 경로로 남을 수 있으므로 이 수치를 삭제된 후보 레코드 수로 해석하지 않는다. 각 제외 이유와 양쪽 목·과를 `excluded_nominal_collisions`에 보존했고, 남은 후보에도 `source_order`, `source_family`, `target_order`, `target_family`, `higher_taxonomy_matches`를 기록했다. `Parus cinereus`의 실제 후보 목록에는 `Parus major`만 남으며 딱따구리와 수리 두 종은 포함되지 않는다. 후보 분류는 309/20에서 302/27로 바뀌었지만 최종 참고 결과 **25/117/305는 변하지 않았다**. 이 보완은 감사 스크립트·ledger·문서에만 적용했으며 런타임 배포 코드는 수정하지 않았다.

## 고정 출처와 실제 접근 확인

### AviList v2025b

공식 JSON: [AviList v2025b](https://explore.avilist.org/data/avilist-2025b.json).

종 범위는 11,131종이며 `taxonomy_release=v2025b`, `concept_set_id=rg:concept-set:avilist-v2025b`로 고정했다. 파일 SHA-256은 `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`이다. 이 자료는 현재 분류의 원본이며, NE 종에 다른 개념의 평가 등급을 그대로 상속시키는 근거가 아니다.

### 공식 IUCN 공개 체크리스트 · GBIF

공식 배포 페이지: [The IUCN Red List of Threatened Species](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3). 자료 DOI: [10.15468/0qnb58](https://doi.org/10.15468/0qnb58). 라이선스는 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)이다.

실제 내려받은 Darwin Core archive의 EML에서 발행기관 International Union for Conservation of Nature, release `2026-1`, 배포일 `2026-07-28`, 명시적 CC BY 4.0 라이선스와 인용을 검사했다. archive SHA-256은 `2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d`이다. taxon core는 310,544행이고 accepted AVES species는 11,185행이다. 공개 고정 파일의 실제 접근 및 파싱을 수행했다. 인증이 필요한 IUCN API를 사용하거나 접근 거절을 우회하지 않았다.

기존 확정 연결은 AviList의 정확한 BirdLife SIS 연결과 학명·명명자·원자료·공개 평가 식별 근거가 맞는 경우만 유지한다. 이번 참고 자료 25종은 이 확정 연결과 분리했다.

25종 중 19종은 명명자의 성·순서·연도·명명 규칙상 괄호를 보존한 채 이니셜 생략·축약 또는 저자 구분기호만 정규화한 경우다. 다른 이니셜, 다른 성, 저자 순서 변경, 연도 변경, 괄호 차이는 허용하지 않는다. 나머지 6종은 공개 archive의 인용이 끝에서 잘려 DOI가 없지만, 정확한 원문 학명·명명자·동일 인용 연도와 canonical IUCN SIS/assessment URL을 확인한 참고 전용 사례다. 이 경우 `assessment_identity_method=canonical_source_url_truncated_citation`를 별도로 표시하고 DOI를 만들지 않는다. 개별 `assessment_year`도 반환하지 않는다. 확정 연결의 DOI 및 식별 검증은 그대로 유지했고, 확장 규칙은 NE 참고 자료에서만 사용할 수 있도록 제한했다.

### BIRDBASE v2025.1

공개 자료: [BIRDBASE Figshare v1](https://doi.org/10.6084/m9.figshare.27051040.v1). 실제 접근한 파일: [파일 55634729](https://ndownloader.figshare.com/files/55634729). 논문 식별자: [Scientific Data 논문, DOI 10.1038/s41597-025-05615-3](https://www.nature.com/articles/s41597-025-05615-3).

Figshare 공개 metadata의 article ID 27051040, version 1, public 상태, DOI, file ID 55634729, download URL 및 CC BY 4.0 라이선스를 검사했고 XLSX 파일을 실제 내려받아 파싱했다. 파일 SHA-256은 `cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b`이다. Nature 논문 본문은 접근 경로에서 정상 취득하지 못했으므로 본문 전체를 읽었다고 기록하지 않는다. 공개 metadata와 실제 XLSX의 열·값을 검증한 것이 이 연결의 직접 근거다.

Data 시트의 2행이 헤더이며 `AviList v1 2025`, `Family AviList v1 2025`, `HBW/BirdLife International (v9.1)`, `2024 IUCN Red List category` 열을 검사했다. 종명 중복 없이 AviList 11,131종 전체가 정확하게 매핑되고 해당 AviList 과명도 일치해야 빌드가 성공한다. 전체 매핑 종 중 원본 등급이 있는 종은 10,824종, 비어 있는 종은 307종이다. 이번 447종 부분집합에서는 각각 142종과 305종이다.

저자가 명시적으로 연결한 AviList 종명 열은 명목상 연결 근거다. HBW/BirdLife 열에 적힌 평가 학명과 AviList 학명이 다를 수 있고, 같더라도 평가의 종 범위가 같다는 결론은 내리지 않았다. 런타임에서 새로운 참고 자료는 needs_review인 NE 종에서만 선택되며, 기존 공식 GBIF 참고 자료가 항상 우선한다.

`2024`는 `data_year`이고 개별 평가 연도가 아니다. `source_release=v2025.1`도 평가 연도가 아니다. BIRDBASE 참고 자료에는 개별 assessment ID나 `assessment_year`를 추가하지 않았다. 원본 `CR (PE)` 또는 `CR (PEW)` 표기는 전체 index에서 `category_raw`로 보존하고 정규 등급을 CR로 분리했다.

## BirdLife 권고와 실제 평가 출시의 구분

공식 [2026.1 변경 권고 PDF](https://forums.birdlife.org/wp-content/uploads/2026/02/Red_List_status_changes_2026.1.pdf)를 실제 접근해 확인했다. SHA-256은 `051d899372dfb9eccdcca68bdd5b64699019fec9fb540d99650d78679c81195a`이며 다음 네 사실은 PDF의 1페이지에 있다. 원문 PDF 전체를 저장소에 재배포하지 않고 종명·권고 등급·출처·페이지·해시만 조사 결과에 보존했다.

| 종 | 2026 권고 등급 | 이번 처리 |
|---|---|---|
| Scytalopus intermedius | LC | 출시 전 권고로 기록; 현재 등급에 미반영 |
| Scytalopus whitneyi | NT | 출시 전 권고로 기록; 현재 등급에 미반영 |
| Scytalopus frankeae | LC | 출시 전 권고로 기록; 현재 등급에 미반영 |
| Scytalopus androstictus | LC | 출시 전 권고로 기록; 현재 등급에 미반영 |

공식 [BirdLife 포럼 절차와 일정](https://forums.birdlife.org/red-list-changes-forum/)은 IUCN 평가가 공개 출시될 때 새 등급이 공식화되며 2026년 업데이트의 출시를 11월로 안내한다. [Scytalopus androstictus 개별 결정](https://forums.birdlife.org/2026-1-loja-tapaculo-scytalopus-androstictus/)도 IUCN에 제출할 권고라는 단계를 명시한다. 확인 기준일 2026-10-09에는 이를 출시된 개별 평가로 취급하지 않았다. 고정 GBIF 자료와 권고 PDF에 비슷한 버전 이름이 붙어 있다는 사실만으로 네 권고가 이미 GBIF 평가에 포함되었다고 추정하지 않았다.

ledger의 이 근거는 `unreleased_recommendation`이며 `decision_year=2026`, `publication_status=recommended_to_iucn_not_published`, `assign_grade_to_target=false`다. 권고 연도를 assessment_year로 변환하지 않았다. 11월 실제 출시 후 공식 자료에서 확인하는 것이 후속 작업이다.

## 변경 전후 동작 및 파일

변경 전에는 같은 학명이 있어도 허용된 명명자 표기를 충족하지 못하면 참고 연결이 없었고, BIRDBASE의 공개 등급 열을 보전 참고 자료로 사용하지 않았다. 변경 후에도 primary conservation은 기존 엄격한 규칙을 따른다. 별도 `reference_assessment`만 공식 GBIF 또는 BIRDBASE의 검증된 고정 자료에서 선택한다.

| 파일 | 구현 또는 증거 |
|---|---|
| `src/robingraph/retrieval/conservation.py` | 참고 전용 명명자·인용 식별 검사, `birdbase_reference_checklist`, GBIF 우선 `best_reference_assessment` |
| `scripts/build_conservation_index.py` | NE 참고 전용 규칙을 사용한 고정 GBIF index 생성 |
| `src/robingraph/retrieval/conservation_index.json` | 기존 primary 7,507개 유지; 참고 레코드 360→385개 |
| `scripts/build_birdbase_conservation_index.py` | 외부 Excel 라이브러리 없이 고정 XLSX XML 파싱, metadata·해시·전체 종명·과명 검증 및 재현 검사 |
| `src/robingraph/retrieval/birdbase_conservation_index.json` | 11,131종 원본 행, null 및 출처 보존; 아티팩트 SHA-256으로 런타임 내용 고정 |
| `scripts/audit_unresolved_conservation.py` | 최초 447종 전수 후보 조사, BIRDBASE 전체 행 대조 및 권고 제외 근거 생성 |
| `tests/test_conservation_reference.py` | 385개 참고 index 수로 고정 데이터 회귀 기준 갱신 |
| `tests/test_conservation_unresolved.py` | 명명자·인용 안전성 및 신규 GBIF 25종 회귀, 전수 ledger 검사 |
| `tests/test_conservation_birdbase.py` | 전체 447종 런타임 결과, 출처 우선순위, source disabling, 식별·해시·행·연도·등급 거부 검사 |
| `docs/verification/assets/2026-10-09-unresolved-conservation-review.json` | 447종 종별 원본, 후보, 선택 참고 출처 또는 부재, 권고 제외 근거 |

BIRDBASE 아티팩트의 SHA-256은 `156b755b2433f34c00a162150118788426d4bd084dae992b976448bd2057efd4`이다. 런타임은 원본 해시뿐 아니라 이 파생 파일 해시도 확인한다. `birdbase.source_allowed()`를 사용하므로 source registry에서 관련 공개 자료가 disabled이거나 허용되지 않으면 참고 자료를 반환하지 않는다.

BIRDBASE 반환 계약의 주요 필드는 다음과 같다. 숫자로 된 `source_row`와 문자열인 `source_locator`를 구분한다.

```json
{
  "evidence_kind": "published_dataset_reference",
  "reference_evidence_type": "birdbase_iucn_2024",
  "assessment_status": "reference_only",
  "taxonomy_alignment": "unverified",
  "independently_verified": false,
  "source_id": "birdbase-v2025.1",
  "source_name": "BIRDBASE · IUCN 2024 reference",
  "source_release": "v2025.1",
  "source_url": "https://doi.org/10.6084/m9.figshare.27051040.v1",
  "mapping_method": "exact_unique_birdbase_avilist_v1_2025",
  "category_column": "2024 IUCN Red List category",
  "data_year": 2024,
  "taxon_id": "avilist-taxon:v2025b:33116",
  "scientific_name": "Cnemoscopus rubrirostris",
  "assessment_scientific_name": "Cnemoscopus rubrirostris",
  "category": "LC",
  "label": "관심대상",
  "source_row": 11361,
  "source_locator": "Data!row 11361"
}
```

위 예시는 일부 필드만 보여주며 실제 payload에는 원본·분류 해시, 라이선스, publication URL, citation 및 범위 설명도 포함된다. 개별 평가 연도·평가 ID 필드는 없다. 조정자가 API 통합과 출처·자료 연도를 구분하는 UI 표시를 담당했다. 이 문서는 조정자가 실행한 frontend 또는 실제 배포 검증 결과를 대신 증명하지 않는다.

## 재현 방법과 실제 검증 결과

아래 환경 변수에는 허가된 공개 자료를 내려받은 로컬 파일 경로를 지정한다. 인증값은 필요하지 않다. 두 builder의 `--check`는 원본을 다시 파싱해 저장소의 파생 파일과 정확히 일치하는지 확인하며 파일을 수정하지 않는다.

```sh
python3 scripts/build_conservation_index.py \
  --avilist "$AVILIST_FILE" --snapshot "$IUCN_ARCHIVE" --check

python3 scripts/build_birdbase_conservation_index.py \
  --avilist "$AVILIST_FILE" --source "$BIRDBASE_FILE" \
  --metadata "$BIRDBASE_METADATA_FILE" --check

python3 scripts/audit_unresolved_conservation.py \
  --runtime-audit docs/verification/assets/2026-10-09-active-species-runtime-audit.json \
  --avilist "$AVILIST_FILE" --iucn "$IUCN_ARCHIVE" \
  --output docs/verification/assets/2026-10-09-unresolved-conservation-review.json

PYTHONPATH=src "$TEST_PYTHON" -m unittest discover -s tests -p 'test_conservation*.py'
```

최종 보전 테스트는 실제로 `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -p 'test_conservation*.py'`로 실행했다. 로그는 `/tmp/rg-unresolved-conservation-tests.log`이며 최종 결과는 **55개 실행, 55개 통과, 0개 실패, 0개 건너뛰기**, 실행 시간 4.443초다. 이 수치는 보전 관련 테스트 범위이며 저장소 전체 Python 또는 frontend 테스트 총계가 아니다.

검증에는 고정 자료 기반 447종 전수 런타임 함수 호출, 기존 primary 7,507종 객체 전체 동일성 비교, 두 원본 builder의 재생성 일치 검사, `py_compile`, 수정한 tracked 파일의 `git diff --check`가 포함된다. 전수 런타임 테스트에서는 공식 GBIF 25종, BIRDBASE 117종, 미연결 305종의 결과를 각 원본 행과 비교하고, 새 참고 연결 때문에 primary grade가 생성되지 않는 것도 확인한다. source disabling과 변조된 출처·행·등급에 대한 거부 테스트는 모의 변경을 통한 회귀 검증이다.

명목상 후보 오탐 보완 후 ledger를 원본에서 다시 생성했다. 추가 읽기 전용 전수 검사로 447종의 모든 약한 명목상 경로가 양쪽 목·과 일치 조건을 충족하는지, 박새 후보가 `Parus major` 한 종뿐인지, 최종 참고 집계 25/117/305가 유지되는지 확인했다. 모두 통과했다. 이 검사는 실제 고정 원본으로 재생성한 ledger 검사이며 새 테스트 파일이나 런타임 코드를 작성한 것이 아니다.

같은 보전 테스트 명령도 보완 후 다시 실행했다. `/tmp/rg-conservation-ledger-filter-tests.log`의 결과는 **55개 실행, 55개 통과, 0개 실패, 0개 건너뛰기**, 4.239초다. 감사 스크립트의 `py_compile`과 해당 수정 범위의 `git diff --check`도 통과했다.

이번 소스 담당 범위에서 실제 Neo4j DB 조회나 실제 배포 API 447종 전수 호출은 새로 수행하지 않았다. 실제 공개 고정 파일에 접근하고 파싱한 검증과, 해당 파일을 사용하는 로컬 런타임 함수 테스트를 구분해야 한다. IUCN 개별 평가 원문을 라이브로 전수 확인한 수는 0건이다. 인증 API 접근, 접근 거절 우회, 인증정보 취득 또는 기록은 수행하지 않았다.

## 커밋·배포 상태와 남은 한계

이 소스 작업 담당자는 git 커밋과 NAS TEST 배포를 수행하지 않았다. 문서 작성 시점에는 조정자의 최종 통합·배포 결과가 확인되지 않았으므로 완료로 기록하지 않는다. 사용자 화면의 실제 표시, API 전수 감사 및 전체 회귀 결과는 조정자의 최종 작업 문서와 배포 증거에 통합할 예정이다.

142종의 참고 연결도 평가 종 범위 일치와 독립 검증을 증명하지 않는다. BIRDBASE 2024 등급은 이후의 상태 변화를 반영한다고 보장할 수 없다. null인 305종은 LC나 다른 등급으로 보정하지 않았다. 이 종들은 새로운 공식 평가 출시, 출처별 평가 개념의 명시적 대응 자료 또는 적법한 개별 원문 확인이 필요하다. 네 BirdLife 권고는 실제 출시 이후 별도 확인이 필요하다.

박새 `Parus cinereus`는 AviList에서 `Parus major` 복합군을 구분하는 현재 종이며 공식 결정문은 `minor` 복합군도 `cinereus`에 포함한다고 설명한다. 고정 공개 IUCN 목록에는 `Parus major`의 LC 평가가 있지만, 과거 넓은 `major` 범위가 현재 `cinereus`를 내포했는지와 해당 개별 평가의 정확한 생물학적 범위는 이번 조사에서 확정하지 않았다. 따라서 그 LC를 현재 박새의 독립적인 평가로 승계하지 않는다. BIRDBASE 박새 행의 IUCN 등급도 null이다. 같은 목·과인 `Parus major` 후보를 남긴 것은 이 과거·현재 분류 범위 문제를 후속 검토할 근거를 보존한 것이며 현재 종의 확정 등급 연결이 아니다.

이번 작업은 447종 모두를 조사·분류하고 근거와 부재를 저장한 작업이다. 447종 모두에 확인된 최신 평가 등급이 생겼다는 의미로 보고하면 안 된다.
