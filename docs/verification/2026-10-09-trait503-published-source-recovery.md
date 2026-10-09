# 형질 공백 503종의 원자료 재조사·공통 복구

작성일: 2026-10-09. 이 문서는 형질 담당의 원자료·코드 검증 기록이다. 실제 TEST/Production 배포와 DB 조회 결과·최종 커밋은 통합 작업 문서 `docs/work-log/2026-10-09-remaining-species-resolution.md`에서 별도로 기록한다. 여기의 원본 추출 검증을 실제 DB 검증으로 바꾸어 읽으면 안 된다.

## 요청 배경과 목표

박새 등의 검색 이름은 복구됐지만 체중·서식 환경·먹이·생활 방식이 비어 있었다. 사용자는 개별 종 예외 처리 대신 기존 전체 활성종 감사의 형질 공백 503종 모두를 실제 조사하고, 공개 근거가 있는 자료를 연결하도록 요청했다. 기준은 `docs/verification/assets/2026-10-09-active-species-runtime-audit.json`에서 `trait_names=[]`인 503종이다. 기존 까치의 별도 검토 자료는 `read_traits` 다음에 붙는 구조여서, 이 숫자가 곧 모든 카드의 모든 필드가 비었다는 뜻은 아니다.

목표는 공백을 보간한 숫자로 감추는 것이 아니다. 분류 범위가 맞는 공개 원자료를 추가하고, 문헌 집계·저자 추정·아종군 참고 자료를 구분하며, 원자료가 없는 필드는 그대로 비워 둔다.

## 원인과 원자료 조사

기존 AVONET 적재는 `AVONET1_BirdLife` 시트 중심이었다. 같은 원본의 `AVONET2_eBird`는 저자가 eBird 분류로 별도로 집계한 데이터이며, BirdLife 분류와 다른 종 범위를 제공한다. 기존 자료의 이름만 현재 이름으로 바꾸는 것과 다르다.

1. AVONET의 세 분류 시트를 모두 확인했다. eBird 시트는 10,661행이며 Avibase concept ID가 있다. BirdTree 시트는 concept ID가 없어 학명만으로 분할·병합 문제를 무시할 수 없다.
2. source/target 양쪽 Avibase ID가 고유하게 같은 경우, 기존 승인된 BirdLife 자료가 없는 **615종**을 연결할 수 있었다. 기준 공백 503종 중 **187종**이 이에 해당한다. 187종의 source Inference는 NO 79, YES 108이다. YES가 모든 필드의 추정이라는 뜻은 아니므로 필드별 `Traits.inferred`를 보존했다.
3. eBird v2025 공식 다국어 분류 파일의 `issf → report_as → species` 관계로 구분류의 자료가 현종의 특정 아종군에 속함을 확인했다. 전체적으로 356종·708개 하위군 관계이며, 503종 중 추가 4종은 이 경로만으로도 범위가 명시된 참고 자료를 제공할 수 있다. 박새의 cinereus Group, Corypha somalica, Nannopsittacus nigrifrons, Dicrurus sharpei가 해당한다. 아종군 값은 현종 전체 평균으로 쓰지 않는다.
4. 여기서 중단하지 않고 다른 공개 형질 데이터셋을 조사했다. [BIRDBASE 원논문](https://www.nature.com/articles/s41597-025-05615-3)과 [저자 공개 데이터 v1](https://doi.org/10.6084/m9.figshare.27051040.v1)을 확인하고 실제 Excel 파일을 내려받았다. BIRDBASE 11,589행 중 `AviList v1 2025` 열이 있는 11,131행은 현재 고정 AviList v2025b의 종 이름 집합과 완전히 같고, `Family AviList v1 2025`도 전종 일치한다. 모든 학명 대응은 1:1이다. 공통 `Order` 열은 다른 분류 체계의 목을 포함하므로 현재 AviList 목과 같은 것으로 간주하지 않는다.
5. 잔여 **316종 모두** BIRDBASE의 명시적 AviList 열로 연결되며 서식 범주가 존재한다. 따라서 원자료 및 오프라인 조회 규칙 기준으로 기존 503종 모두에 형질을 제공할 수 있다. 316종 중 286종은 원자료 주학명과 같고 30종은 저자 AviList 대응열에 이름 변경이 명시된다. 이 대응은 독립 Avibase concept ID 일치와 다른 근거이므로 `author_avilist_column` 방법으로 구별한다.

최종 원자료 대응 수는 **187종 AVONET eBird 동일 concept + 316종 BIRDBASE 명시적 AviList 대응 = 503종**이다. BIRDBASE에서도 일부 필드는 비어 있다. 316종 중 체중 값이 있는 종은 152종, 없는 종은 164종이며, 22종의 `Primary Diet`는 `No Information`이다. 이 항목은 값을 만들지 않는다. BIRDBASE에 대응되는 `primary_lifestyle` 변수가 없으므로 이동성(Migration)을 생활 방식으로 바꾸지 않는다.

## 원본 핀·이용 범위

| 원자료 | 파일·릴리스 | SHA-256 | 이용 조건 |
|---|---|---|---|
| AviList | v2025b JSON | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` | CC BY 4.0 |
| AVONET | Figshare 16586228 v7, file 34480856 | `eb645e83dddb40f1654a3e8d721998dbca76eff540231b7b809267c1e96f8d3e` | CC BY 4.0 |
| eBird taxonomy | v2025 full_sparse | `5a6c29b6a48db107b20f8bd1bc6f468ef652a51ccae299b1102350459d73b909` | 공식 분류 식별자·하위군 관계만 사용, AVONET 값과 별도 출처 |
| BIRDBASE | Figshare 27051040 v1, file 55634729 | `cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b` | Figshare 공식 메타데이터 CC BY 4.0 |

원본 URL:

- [AviList JSON](https://explore.avilist.org/data/avilist-2025b.json)
- [AVONET workbook](https://ndownloader.figshare.com/files/34480856)
- [Cornell eBird 분류 파일](https://cornell.box.com/s/zjci66divvqnz00k98r7pmmb6kpc69zs)
- [BIRDBASE workbook](https://ndownloader.figshare.com/files/55634729)
- [BIRDBASE 공식 메타데이터·라이선스](https://api.figshare.com/v2/articles/27051040/versions/1)

AVONET 공식 API 최신 버전도 v7임을 확인했다. BIRDBASE의 후속 원논문/데이터를 새로 조사한 이유가 여기에 있다. 완성된 packaged extract를 PostgreSQL `source_record`나 Neo4j Claim으로 가장하지 않는다. 새 조회 형질은 `evidence_kind=packaged_source_extract`, `source_record_id=null`, source URL·sheet·row·field·원본 해시·추출물 해시를 제공한다. BIRDBASE는 registry의 enabled/allowed/정확한 CC BY 라이선스와 출처 URL 검증도 통과해야 한다. 등록이 취소되면 반환하지 않는다.

## 값 해석과 변경 전후 동작

### AVONET eBird

원자료와 대상의 고유 concept ID가 같은 경우만 승인한다. 다른 concept ID를 가진 같은 학명은 자동 승인하지 않는다. source 추정 필드는 `(추정값)` 및 `species_estimate`로 표시하고, 추정에 쓰인 참조 종과 원자료 Inference·행 번호를 남긴다. 비추정 원자료 집계의 통계는 `species_mean`이다. AVONET `Total.individuals`는 전체 형태측정 대상 수이므로 `sample_size`로 내보내지 않는다. `source_morphology_sample_size`에 따로 보존하고 source_note에서 개별 형질 유효 표본수·체중 문헌 표본수가 아님을 명시한다.

까치 eBird 행은 표본 0, `Pica pica`를 참조한 저자 추정 체중 217.5 g이다. 기존 한국 표본 연구 220.64 g를 이 값으로 대체하지 않도록, 검토된 비추정값이 저자 추정값보다 우선하도록 보완했다. 기존 비추정값을 다른 값으로 덮어쓰지는 않는다.

### BIRDBASE

`Average Mass`는 문헌의 암컷·수컷·성별 미구분 최소·최대값을 저자가 평균한 것이다. 개체별 측정 표본 평균도 아니며, 성별 정보가 여럿이면 전체 최솟값과 최댓값 두 개만의 중간값도 아니다. 따라서 `summary_statistic=literature_bounds_mean`, `체중 · 문헌 범위 평균`으로 분리한다. 여섯 개 원값은 `source_mass_bounds`와 source_note에 보존한다. 박새 원자료는 성별 미구분 11–22.1 g와 Average Mass 16.55 g다.

`Primary Habitat` 14개 범주와 `Primary Diet`의 모든 유효 범주에 한국어 표시를 제공한다. `Diet_Lit=0`은 원저자 보간이며 `inferred=true`, `Diet_Lit=1`은 발표 문헌 근거다. 보간 여부를 카드뿐 아니라 API summary/sections에도 표시한다. `No Information`을 잡식이나 0으로 바꾸지 않는다.

BIRDBASE의 IN-Wt·FR-Wt 등은 문헌 설명을 0–10점으로 부호화한 값이며 `T`는 미량이다. 이 숫자를 10배 하여 측정된 먹이 구성 백분율인 것처럼 도넛차트에 넣지 않는다. 원래 값은 추출물에 보존하되 `diet_distribution`으로 생성하지 않는다.

### 하위군 참고 값

종 전체에 연결된 값이 우선하고, 없는 필드만 하위군 참고 자료로 보완한다. 서로 다른 하위군이 여러 개면 모든 행을 반환하며 평균을 내거나 첫 행만 대표로 선택하지 않는다.

- `source_scope_kind=subspecies_group`
- `source_scope`: 실제 아종군 학명
- `summary_statistic`: subgroup_mean / subgroup_estimate / subgroup_category
- `taxonomy_alignment.status=reference_subgroup`
- source_note: 현재 종 전체의 평균·전체 분포를 뜻하지 않는다는 설명

종 설명의 summary에서 아종군 평균을 종 체중이라고 단정하지 않는다. sections는 각 하위군을 별도로 적는다. 생태 관계와 유사종 점수 계산에서는 하위군 범주를 종 전체 생태 근거로 쓰지 않는다.

BIRDBASE를 추가한 최종 순서는 기존 검증 자료 → AVONET eBird 보완 → BIRDBASE → 하위군 참고다. 따라서 박새에는 BIRDBASE 종 범위의 서식·먹이·문헌 체중이 먼저 제공되고, BIRDBASE에 없는 부리·날개·생활 방식 등은 범위가 표시된 하위군 참고 정보가 될 수 있다.

## 변경 파일

- `scripts/build_avonet_ebird_supplement.py`: 핀 확인 후 고유 concept ID 매핑, 승인된 기존 BirdLife 대상 제외, 615종 생성.
- `src/robingraph/retrieval/avonet_ebird.py`, `avonet_ebird_supplement.json`: 기존 활성 AVONET provenance 확인 후 없는 형질만 보완.
- `scripts/build_avonet_subgroup_supplement.py`, `avonet_subgroups.py`, `avonet_subgroup_supplement.json`: 고정 Cornell 관계를 통한 하위군 연결. 중복 source/parent, slash 그룹 자동 승격 거부.
- `scripts/build_birdbase_traits.py`, `birdbase.py`, `birdbase_traits.json`: 고정 원본, 명시적 AviList 열, 전종 집합·과 일치 검증, 문헌 수치·분류범주 보완.
- `species_profile.py`: 공급자 순서, 빈 기존 공급자에도 독립 허용 BIRDBASE 공급, 통계·보간·참고 범위의 본문 표기.
- `reviewed_magpie.py`: 저자 추정 체중보다 기존 검토 비추정 체중 우선.
- `ecological_relations.py`, `similar_species.py`: 아종군 참고값을 종 생태 연관·점수에 사용하는 것을 금지.
- `scripts/audit_trait503_sources.py`: 기준 503종 모두 세 AVONET 시트, eBird 관계, BIRDBASE 실제 원자료와 대조.
- `docs/verification/assets/2026-10-09-trait503-source-resolution.json`: 503종 전원의 원인과 source row·분류 관계·최종 연결 근거. AVONET 단독 조사 결과도 `avonet_disposition`에 남긴다.
- `tests/test_avonet_ebird.py`, `test_avonet_subgroups.py`, `test_birdbase_traits.py`: 실제 추출물 전행·변조·중복·라이선스 취소·범위·통계·추정·우선순위 회귀검증.

## 실행·검증

빌드 시에만 openpyxl이 필요하며 런타임 새 의존성은 없다. 아래 RAW_DIR은 고정 AviList/Elton/AVONET 원본 세 파일이 있는 디렉터리다. 이 세션에서는 `/tmp/rg-trait503-raw`가 해당 원본 디렉터리를 가리킨다. 임시 원본 경로는 배포/영구 저장소 경로가 아니다.

```sh
python scripts/build_avonet_ebird_supplement.py --raw-dir "$RAW_DIR" --check
python scripts/build_avonet_subgroup_supplement.py --raw-dir "$RAW_DIR" --ebird "$EBIRD_XLSX" --check
python scripts/build_birdbase_traits.py --source "$BIRDBASE_XLSX" --avilist "$AVILIST_JSON" --check
python scripts/audit_trait503_sources.py --raw-dir "$RAW_DIR" --ebird "$EBIRD_XLSX"
ROBINGRAPH_TRAIT_RAW_DIR="$RAW_DIR" PYTHONPATH=src python -m unittest tests.test_birdbase_traits tests.test_avonet_ebird tests.test_avonet_subgroups tests.test_trait_mapping tests.test_trait_crosswalk tests.test_ecological_relations tests.test_similar_species
```

실제 결과:

- 최초 BIRDBASE 포함 관련 86개 테스트: 실패 0, 84개 통과, 2개 원본 조건부 테스트 skip. 이후 원본 디렉터리를 주입해 재실행한 86개는 전부 통과(실패 0, skip 0, 4.184초)했다. 마지막 source_note 원체중 범위 보강 뒤 BIRDBASE 8개를 추가 재실행하여 모두 통과했다. 독립 검토에서 형태측정 총개체수와 형질별 표본수 혼동을 수정하고 회귀검증을 추가한 최종 87개도 모두 통과(실패 0, skip 0, 4.079초)했다.
- 그 전 AVONET·하위군 관련 78개 테스트는 원본 디렉터리를 넣고 전부 통과했다.
- BIRDBASE 실제 추출물 11,131종 전행을 런타임 함수에 넣어 유효 한국어 서식 범주·출처 반환 확인. 기준 공백 503종 모두 서식 형질을 반환한다. 이것은 고정 원자료/로컬 함수 검증이며 실제 DB 전종 조회 결과와 구별한다.
- 실제 세 `--check` 모두 통과했다. 추출물 SHA-256: eBird `3b9995a9576ec7ca13cc25ed66aba83143d40c7d66058a062f714883f07aca2c`, 하위군 `9920f900c7365ab3c3e178f6f349ecfa741328512f2992badc00f9e752225a22`, BIRDBASE `e891b76cc809f843ba38758d713f3427d396d073037911c01ca1d758b30ca7ab`. 각 `--check`는 실제 원본에서 다시 만든 바이트와 커밋 대상 JSON이 동일한지 확인한다. 해시 불일치, 중복 대상·관계, 과 불일치, 다른 분류판, 취소된 registry를 거부하는 테스트가 있다.

## 추가 조사와 남는 한계

[AVONICHE](https://datadryad.org/dataset/doi:10.5061/dryad.1zcrjdg56)는 AviList 10,981종의 먹이·먹이활동 정량 자료를 제공하는 추가 후보다. 공식 메타데이터에서 파일 `Avoniche4_AviList_2025.csv`, file ID 4513907, SHA-256 `04bad4666bfcbf9744c9a34afdf7b3704f47ed8cc3c59649294ebfbcabd0261a`, CC0를 확인했다. 이 세션에서 공식 웹 다운로드는 403, API download는 401이었다. 파일 본문을 확보·검증하거나 적용했다고 기록하지 않는다. 접근 제한을 우회하지 않았으며, 이 자료가 있다는 이유만으로 백분율을 생성하지 않았다.

503종의 완전 공백은 공개 BIRDBASE 연결로 해소할 수 있지만, 모든 종의 모든 형질·도넛차트가 채워진다는 뜻은 아니다. 개체별 평균이 없는 체중, 문헌 먹이 정보 부재, 먹이 비율 부재, 원자료가 없는 생활 방식은 실제 한계로 남긴다. BIRDBASE도 여러 문헌을 종합한 데이터이므로 전종 모든 사실을 현장 관찰로 독립 검증했다는 뜻은 아니다. 직접 측정·문헌 요약·저자 보간·하위군 참고값은 구조화 출처와 표시에서 계속 구분한다.

이 담당 작업은 DB를 변경하지 않았다. 원자료 수집/추출물·조회 계층을 추가했고, 배포·운영 실측·최종 커밋·Obsidian 기록은 통합 작업 담당이 별도로 수행한다.
