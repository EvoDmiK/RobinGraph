# 전체 아종 영어 이름 출처 감사와 재현 가능한 수집 — 2026-10-06

## 요청 배경과 목표

사용자는 청둥오리·왜가리 같은 개별 종 보정이 아니라 **모든 아종**의 출처 있는 이름과 분포를 요구했다. 이 작업은 그 가운데 "영어 아종 이름"을 재현 가능하게 수집하는 부분이다. Orca 코디네이터의 지시에 따라 1차 자료(DOF 세계 조류 이름 PDF, Birds New Zealand 체크리스트, 정당화되는 기타 자료)에서 영어 이름을 수집하고, 정확한 학명을 고정된 AviList v2025b 아종에 매핑한다. 런타임·UI 연동, 커밋, 배포, DB 변경은 이 작업의 범위가 아니며 하지 않았다. 지역·번역에서 이름을 만들지 않는다. 태스크 소유 파일은 아래 네 개뿐이다.

| 파일 | 역할 |
|---|---|
| `scripts/build_subspecies_names.py` | 수집·검증·병합 스크립트 (pypdf 기반, 약 635줄) |
| `src/robingraph/retrieval/subspecies_name_references.json` | 실제 전체 릴리스에서 생성한 산출물 (약 830KB) |
| `tests/test_subspecies_name_references.py` | 산출물·규칙·충돌 거부 테스트 |
| `docs/verification/2026-10-06-subspecies-name-source-audit.md` | 이 문서 |

`taxonomy_lineage.py`의 수동 검증 이름 4개(Oriental Grey Heron, Mauritanian Heron, Greenland Mallard, Northern Mallard)는 수정하지 않았다. 스크립트가 실행 시 그 딕셔너리를 읽어 산출물의 `preserved_manual_references`에 그대로 복사하고, 생성 결과가 이와 다르면 충돌로 보고하며 수동 값을 우선한다. (작업 트리의 `taxonomy_lineage.py` 등 다른 파일은 다른 세션이 수정 중이며 이 작업이 만진 것이 아니다.)

## 결론 요약

- **분모**: AviList v2025b의 `subspecies` 행 19,879개(학명 중복 없음).
- **분자**: 출처로 검증된 영어 이름 **1,074개 = 5.40%** (DOF 978 + Birds NZ 98, 두 출처가 일치해 중복 인용된 항목 2개 포함). 수동 검증 이름 중 생성 결과에 없는 Northern Mallard를 더하면 1,075개.
- 수동 참조 포함 1,075개에만 출처 통칭을 연결했다. 나머지 18,804개의 통칭은 이번 자료 수집에서 확인하지 못했다. 이것이 전 세계에 통칭이 존재하지 않는다는 뜻은 아니다. AviList와 실제 확인한 IOC 파일의 아종 영어 열은 비어 있으며, Clements는 HTTP 403으로 내용을 확인하지 못했으므로 빈 열이라고 단정하지 않는다. 이름 없는 아종도 부모 종 일반명과 원자료 분포 캡션으로 구분하고 학명은 상세 토글에 보존한다. 전체 아종의 AviList Range는 비어 있지 않다.
- 모든 항목은 출처 PDF 쪽수·레코드 번호, 원문 셀, 출처 저자 표기, AviList 저자 표기를 가진다. 충돌 14건, 제외 항목 320건과 사유가 산출물에 기록된다.

## 사용한 자료와 고정 값

| 자료 | URL | SHA-256 | 라이선스/이용 조건 |
|---|---|---|---|
| AviList v2025b Explorer JSON (33,684행) | https://explore.avilist.org/data/avilist-2025b.json | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` (`config/collection-points.json`의 `expected_sha256`과 동일) | CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) |
| DOF Navnegruppen, *Navne på alverdens fugle* (PDF 769쪽, 파일 표기 231119) | https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf | `bdf253b373fccf20649664402003fd2c731199872d5c03a4511fbf5505ba678e` | 공개 라이선스 없음. PDF 5쪽 고지: "개별 이름은 자유롭게 사용할 수 있으나 파일 또는 일부를 서면 허가 없이 다른 인쇄·전자 형태로 재현할 수 없다" |
| Checklist Committee (OSNZ) 2022, *Checklist of the Birds of New Zealand* 5판 (PDF 336쪽) | https://www.birdsnz.org.nz/wp-content/uploads/2022/05/checklist-2022.pdf | `e2cb09bae5c46e2bf585a11fa0dee9ddee36a5445a4086942bfa128bffb7659b` | 저작권 보유(3쪽), 오픈 라이선스 없음. 쪽수가 붙은 짧은 개별 이름만 보관 |

taxon ID는 항상 `avilist-taxon:v2025b:<Sequence>` (n8n 수집 코드와 같은 규칙)이고 `concept_set_id`는 `rg:concept-set:avilist-v2025b`다. 세 파일은 `--cache-dir`에 받아 해시가 다르면 즉시 실패한다. 산출물에는 시각 정보를 넣지 않아(`retrieved_on`은 고정 문자열 2026-10-06) 같은 입력이면 같은 바이트가 나온다.

### 자료 이용 범위

DOF의 개별 이름 자유 이용 고지와 Birds NZ 저작권 표시를 각각 기록한다. 두 자료를 CC BY로 표시하지 않는다. 앱 참고 파일에는 짧은 개별 이름 사실, 분류 식별자·명명자, 출처 쪽수만 보관하며 책 본문·다른 언어 열·완전한 PDF 또는 전체 추출문은 배포하지 않는다. AviList 원자료 분포의 CC BY 4.0과 개별 이름 참고 출처의 조건을 구분한다.

## PDF 추출과 최종 코디네이터 수정

Claude의 최초 제출에는 독자적인 약 600줄 PDF/AES 판독기가 포함되어 있었다. 코디네이터는 검증된 PDF 패키지로 대체하고 독자 암호 구현과 해당 테스트를 삭제했다. 빌드 시에만 pypdf 6.19.0과 cryptography 50.0.2를 임시 환경에서 사용하며 앱 의존성이나 uv.lock은 변경하지 않는다. DOF는 pypdf의 논리 줄 추출, Birds NZ는 폰트가 붙은 위치 run 추출을 사용한다. PDF 원자료는 빈 사용자 암호로 열리는 공개 파일이고 별도 암호를 추측하지 않는다.

위치 run을 DOF에 그대로 적용하는 시도에서 이름 수가 57개로 감소했다. 이를 채택하지 않고 원문 줄 순서 추출로 수정한 뒤 DOF 레코드 27,268개·아종 후보 16,564개와 NZ 제목 191개가 복구되는 것을 확인했다. NZ의 추가 두 이름은 원문 PDF 84쪽 Campbell Island Snipe와 113쪽 Australian Little Penguin의 정확한 학명·명명자·이름을 직접 확인했다. 최종 통칭 수는 생성 1,074개·수동 참조 포함 1,075개이다. 수치는 최초 제출과 같지만 포함 구성은 바뀌었다.

`Lonchura striata acuticauda`의 Bengalese Munia는 가축형과 혼동될 가능성이 있어 채택하지 않는다. [Bengalese finch genome 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC5861438/)에서 Bengalese/Society finch는 domestica 가축형으로 다뤄진다. 이는 기존 DOF 이름이 절대적으로 잘못됐다고 단정하는 것이 아니라 현재 앱에서 야생 아종과 가축형을 분리하기 위한 보수적 제외다. `domestication_name_ambiguous` 사유와 출처 페이지를 기록한다. Society Finch, Bengalese Munia/Finch와 Domestic 형태 이름을 제외하되 Society라는 지리 단어 자체를 모두 차단하지 않는다.

## 규칙: 어떤 이름만 수락했나

1. 학명 **정확 일치**: 출처의 3명법이 AviList v2025b `subspecies`의 `Scientific_name`과 글자 그대로 같아야 한다(대소문자·공백·철자 보정 없음). AviList에서 같은 학명이 둘 이상이면 어느 ID에도 묶지 않는다(이번 릴리스에서는 0건).
2. **저자 일치**: 출처 저자의 성(姓) 집합이 AviList 저자와 교집합을 가져야 하고, 출처에 연도가 있으면 연도가 같아야 한다. DOF는 연도 필수. Birds NZ 제목에는 연도가 없어 성만 비교한다. 같은 학명이라도 다른 저자(동음이의·다른 분류군)를 막는 장치다. 실제로 `Aerodramus maximus lowi`(Hume 1878 대 Sharpe 1879), `Prunella modularis fuscata`(Watson 1961 대 Mauersberger 1971) 같은 불일치가 걸렸다.
3. **영어 열 그대로**: DOF는 `학명+저자 • 덴마크어 • 영어 • 독일어` 행에서 정확히 4열인 행의 세 번째 열만 읽는다(줄바꿈은 병합, 하이픈 줄바꿈은 붙여 읽음). Birds NZ는 굵은 기울임체 3명법 머리글과 같은 줄의 굵은 이름 run에서 읽는다. 덴마크어·독일어 열, 지리, 번역은 사용하지 않는다.
4. **영어 이름 한 개**: `/`로 구분된 복수 이름, 괄호·콤마·숫자·`†`, 말줄임/잘린 문자열, 6단어 초과, 덴마크어·독일어 문자(æ ø å ä ö ü ß)를 포함한 셀은 제외한다. DOF 서문은 복수 이름 중 첫째가 공식이라고 하지만 사용자 지시("모호한 열은 제외")에 따라 첫째를 임의 선택하지 않는다.
5. **DOF 단일 단어·덴마크어 열 복사 제외**: DOF 영어 셀이 덴마크어/독일어 셀과 같은 경우(예: 영어 칸에 `Kangean-sultanspætte`)와 한 단어 이름은 제외한다. 실제로 한 단어 이름이 다른 종 이름의 오기재였다(`Chlorodrepanis virens wilsoni` 행의 `Akiapolaau`는 다른 종 이름).
6. **Birds NZ 막대 표기**: 체크리스트 10쪽 규칙(`영어 | 마오리어`, 막대 왼쪽이 더 많이 쓰인 이름, 일부 종은 마오리어가 먼저, 매크론만 다른 경우 마오리어가 먼저)에 따라 왼쪽이 두 단어 이상이고 매크론이 없으며 오른쪽과 매크론 제외 동일하지 않을 때만 영어로 인정한다. 한 단어 왼쪽(`Ruru | Morepork` 등)은 언어 순서를 확정할 수 없어 제외한다.
7. **종 이름과 동일하면 제외**: 부모 종의 AviList 영어 이름(DOF는 DOF의 종 행 영어 이름도)과 같으면 아종을 구분하지 못하므로 제외한다(예: `Mallard`).
8. **형제 아종 중복 제외**: 같은 출처에서 같은 종의 두 아종에 같은 이름이 붙으면 둘 다 제외하고 충돌로 기록한다.
9. **출처 간·수동 참조와의 충돌**: 두 출처가 다르거나 수동 검증 이름과 다르면 어느 쪽도 내보내지 않고 충돌로 기록한다. 수동 이름이 항상 우선한다.

## 데이터셋 커버리지

| 항목 | 최종 결과 |
|---|---|
| AviList 아종 | 19,879개 |
| 생성 이름 | 1,074개 (5.40%) |
| 수동 검증 참조 포함 | 1,075개 |
| 출처별 채택 | DOF 978 / Birds NZ 98 (2개 이름은 두 근거) |
| DOF 처리 | 27,268개 종·아종 레코드 / 16,564개 아종 후보 |
| NZ 처리 | 191개 아종 제목 |
| 제외 레코드 | 320개 |
| 충돌 | 14건 |
| AviList ID에 연결하지 않은 영어 이름 후보 | 564개 |
| AviList 중복 학명 | 0개 |

### 제외 사유 집계

아래는 최종 pypdf 재생성 결과이다. 제외 후보마다 산출물의 `excluded`에 학명·출처·페이지와 원문 셀을 남긴다. 출처 충돌을 같은 이름의 동의어라고 추정해 병합하지 않는다.

```json
{
  "birds-nz-2022:authority_surname_mismatch": 3,
  "birds-nz-2022:nz_english_maori_identical_apart_from_macrons": 1,
  "birds-nz-2022:nz_maori_name_listed_first": 1,
  "birds-nz-2022:nz_single_word_left_of_bar_language_unverified": 3,
  "birds-nz-2022:same_as_parent_species_name": 36,
  "birds-nz-2022:sources_disagree": 9,
  "dof-2019:authority_missing_in_source": 2,
  "dof-2019:authority_surname_mismatch": 12,
  "dof-2019:authority_year_mismatch": 7,
  "dof-2019:domestication_name_ambiguous": 1,
  "dof-2019:english_contains_danish_or_german_letters": 2,
  "dof-2019:english_equals_danish_or_german_column": 4,
  "dof-2019:english_multiple_names": 96,
  "dof-2019:english_single_word_unverified": 5,
  "dof-2019:english_unclean": 19,
  "dof-2019:malformed_columns": 74,
  "dof-2019:same_as_parent_species_name": 26,
  "dof-2019:same_name_for_several_subspecies": 10,
  "dof-2019:sources_disagree": 9
}
```

### 검토했으나 채택하지 않은 자료 (`evaluated_and_excluded_sources`)

| 자료 | 해시/URL | 증거와 사유 |
|---|---|---|
| IOC World Bird List 15.2 `IOC_Names_File_Plus-15.2_full_ssp.xlsx` | `8517d4df…f81f30` | `ssp` 행 19,797개 모두 영어 이름 칸이 비어 있음 |
| DOF IOC 표 PDF (`…Systematiske_danske_engelske_og_tyske_navne_PDF.pdf`, 856쪽) | `6812a967…6eea` | 열 좌표로 추출해 봤더니 AviList 일치 아종 18,261행 중 영어 칸이 있는 것은 175개. `Tinamou`, `Gray-headed pileated`, `Huila black Tinamou`처럼 줄바꿈된 표 셀에서 잘린 문자열이거나 종 이름이라 열을 정확히 검증할 수 없음 |
| NCBI Taxonomy `taxdmp_2026-10-01.zip` | `d744af37…c9eb` | 일치 아종 3,991개 중 일반명이 있는 것은 111개, 제출자 입력·소문자·종 이름(`common mallard`, `ring-necked pheasant`). 편집된 체크리스트가 아님. 수동 보존된 Northern Mallard의 근거로만 남김 |
| Clements v2025 CSV | (해시 없음) | 2026-10-06 코넬 서버가 자동 접근에 HTTP 403 응답. 그룹 이름은 여러 아종에 걸침 |

## 재현 방법

```sh
uv run --no-project --with pypdf==6.19.0 --with cryptography==50.0.2 python scripts/build_subspecies_names.py --cache-dir <DIR>          # 내려받기+해시 검증+생성
uv run --no-project --with pypdf==6.19.0 --with cryptography==50.0.2 python scripts/build_subspecies_names.py --cache-dir <DIR> --offline --check   # 재생성 후 바이트 비교
ROBINGRAPH_SUBSPECIES_SOURCE_DIR=<DIR> python -m unittest tests.test_subspecies_name_references
```

`<DIR>`에는 `avilist-2025b.json`, `dof-navne-pa-alverdens-fugle-2019.pdf`, `birds-nz-checklist-2022.pdf`가 들어간다(없으면 위 URL에서 받고 SHA-256을 검증). 산출물 SHA-256은 `83a21444131accfcf17ab25c9981920ba557642015676e17dc0467dbd4c44751`이다. 같은 입력으로 두 번 생성해 바이트가 같음을 확인했다.

## 산출물 구조

`schema_version`, `taxonomy`(release·concept_set_id·ID 패턴), `policy`, `sources`(URL·해시·라이선스·조회일), `evaluated_and_excluded_sources`, `coverage`(분자·분모·출처별·목별·제외 사유), `preserved_manual_references`(4건 + AviList 식별 확인 + 생성 일치 여부), `names`(taxon ID 키: 학명, 영어 이름, AviList 저자, 부모 종 ID, 수동 이름 일치 여부, `style_flags`, `evidence[]`=출처·출처 저자·원문 셀·쪽/레코드), `conflicts`, `excluded`, `unmapped_candidates`. 이름은 출처 표기 그대로이며 다시 쓰지 않는다. DOF가 소문자로 적은 4개(`Cantabrian capercaillie` 등)는 `style_flags: ['lowercase_word']`로 표시했다. 소비 측은 `taxon_id`와 `scientific_name`을 둘 다 대조한 뒤 사용해야 하며(기존 `SUBSPECIES_NAME_REFERENCES`와 같은 방식), `names`에 없는 아종은 이름을 만들지 말고 학명과 AviList 분포로 표시한다.

## 검증과 실제 결과

| 검증 | 범위 | 결과 |
|---|---|---|
| `tests.test_subspecies_name_references` (환경변수 없음) | 27개 중 25개 실행 | 25 통과, 2 건너뜀(고정 원본 파일이 필요한 실제 AviList 대조·바이트 재생성) |
| 같은 테스트, `ROBINGRAPH_SUBSPECIES_SOURCE_DIR` 지정 | 27개 전체 | 27 통과 / 실패 0 / 건너뜀 0. 실제 AviList JSON에서 산출물의 모든 ID가 `subspecies` 행이고 학명·저자가 정확히 같음을 확인하고, 세 원본으로 재생성한 결과가 산출물과 바이트 동일함을 확인(약 46초) |
| 전체 `unittest discover -s tests` | 581개 | 581개 발견 / 실패 0 / 건너뜀 34 (실행·통과 547개)(기존 DB·네트워크 통합 테스트 + 위 2개) |
| `build_subspecies_names.py --check` | 실제 PDF 2종 + AviList | 바이트 동일 |

테스트가 보증하는 것: 릴리스·concept set·원본 해시가 `config/collection-points.json`의 AviList 해시와 일치; 모든 이름이 `avilist-taxon:v2025b:<n>` ID, 3명법 학명, 정확히 한 개의 깨끗한 영어 이름, 쪽수가 있는 근거, 저자 일치를 가짐; 한 종 안에서 이름 중복 없음; 분자·분모·목별 합계 정합; 수동 4건 보존과 비모순; 충돌 분류군은 `names`에 없음; 합성 AviList로 정확한 ID 결합, 근접 철자·대소문자·공백 변형 비매칭, 저자·연도 불일치 거부, 중복 AviList 학명 거부, 출처 간·수동·출처 내 중복·형제 중복 충돌 거부, 종 이름 동일 거부, DOF 줄바꿈 병합·머리글 누수·열 수 불량·덴마크어 열 복사, Birds NZ 머리글과 막대 규칙, 가축형 이름의 야생 아종 등록 방지. **모의 검증**은 합성 행/runs를 쓰는 단위 테스트이고, **실제 데이터 검증**은 환경변수를 준 두 테스트와 `--check`다. DB·네트워크 API 검증은 이 작업 범위가 아니라 하지 않았다.

## 한계와 후속 사항

1. 영어 이름 커버리지는 이번 검증 자료에서 5.40%다. 추가 기관 자료나 확인된 한국어 자료로 늘릴 수 있으며 이름을 추정 생성하지 않는다.
2. DOF 열은 사람이 만든 PDF라 오기재(다른 종 이름, 덴마크어 복사)가 있다. 자동 검사로 알려진 유형은 거르지만 모든 오기재를 증명할 수 없다. 서비스 표시 전 표본 검토를 권한다. 단어 단위 저자 검증이 이 위험을 줄이지만 없애지는 않는다.
3. 출처 저자 표기가 달라 제외된 항목(DOF 20건, NZ 3건)과 AviList에 없는 동의어 학명 등 미연결 영어 후보 564건은 분류 담당자가 동의어 매핑을 검토할 후보다. 자동으로 묶지 않았다.
4. 출처의 이용 조건은 위 자료 이용 범위와 산출물 source metadata에 기록한다.
5. 분포: 이 작업은 이름만 다뤘다. AviList `Range`(영어 원문)는 19,879개 아종 모두에 있으나 한국어 설명은 별도 검토가 필요하다.
6. 런타임·UI 연동은 코디네이터 몫이다. 이 작업은 커밋·푸시·배포·DB 변경을 하지 않았고 `graphify update .`만 실행했다.
7. 작업 트리에는 이 작업과 무관한 다른 세션의 변경 파일이 있다(`taxonomy_lineage.py` 등). 이 작업은 위 네 개 파일만 만들었다.


## 최종 통합 검증 기록 안내

위 최초 제출 테스트 표는 Claude 제출 시점의 기록이다. `581개`는 실행 총수이며 건너뛴 34개를 포함해 581개가 모두 실행·통과했다는 뜻은 아니다. PDF 판독기 교체와 가축형 제외 후의 최종 테스트, 전체 DB 감사, 실제 NAS TEST HTTP·배포 및 git 상태는 [코디네이터 최종 작업 문서](2026-10-06-global-subspecies-names-and-ranges.md)를 따른다. 최종 소스 재생성 명령은 아래와 같다.

```sh
uv run --no-project --with pypdf==6.19.0 --with cryptography==50.0.2 python scripts/build_subspecies_names.py --cache-dir DIR --offline --check
```
