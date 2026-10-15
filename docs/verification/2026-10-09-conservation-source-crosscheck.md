# 2026-10-09 보전 등급 공식·전문가 자료 교차 검토

## 요청 배경과 목표

사용자는 박새 한 종의 표시만 고치는 대신, 앱에서 평가 자료가 연결되지 않은 종 전체에 실제 출처를 찾아 연결할 것을 요청했다. 기존 447종 감사에서는 GBIF 공개 IUCN 자료 25종과 BIRDBASE 참고 자료 117종을 연결하고 305종이 남았다. 이번 감사는 이 **원래 미연결 305종 전부**를 HKBWS 공개 목록과 대조하고, 확보한 전문가 출처의 명시 등급을 현재 앱 자료와 비교하는 작업이다.

사용자 승인 전 운영 배포는 금지되어 있다. 이 감사는 조회·파일 검토·재현 자료 작성이며, 런타임 등급 변경이나 배포를 수행하지 않았다.

## 확인한 자료와 접근 방식

| 자료 | 확보·검증 방식 | 확인 범위 |
| --- | --- | --- |
| [HKBWS Hong Kong List 2024](https://avifauna.hkbws.org.hk/hk-list) | 공식 페이지의 검색 캐시 조각을 결합하여 행 번호 1–584를 확보 | 분류 I/II 목록 584행, 페이지 갱신일 2025-05-11. 직접 HTML 전체 GET이나 원본 목록 PDF 다운로드 성공을 뜻하지 않음 |
| HKBWS 개별 종 설명 | 접근 가능한 공식 페이지 검색 캐시 본문의 보전 상태·학명·권장 인용·갱신일 확인 | 검토한 개별 출처만 짧은 상태문과 사실 메타데이터 보존. 584개 종 설명 전체를 내려받은 것은 아님 |
| [IUCN 2025-2 등급 변경표 Table 7](https://nc.iucnredlist.org/redlist/content/attachment_files/2025-2_RL_Table7.pdf) | 직접 HTTP 다운로드 성공, PDF 텍스트 추출과 관련 1·2·3페이지 이미지 확인 | 2024–2025 등급 변경, 표 갱신일 2025-10-10 |
| [IUCN 2023-1 등급 변경표 Table 7](https://nc.iucnredlist.org/redlist/content/attachment_files/2023-1_RL_Table_7.pdf) | 직접 HTTP 다운로드 성공, PDF 텍스트 추출과 관련 4페이지 이미지 확인 | 2022–2023 등급 변경 중 Terpsiphone atrocaudata |
| [IUCN GBIF 공개 체크리스트 2026-1](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3) | 이미 확보된 고정 원본 ZIP의 taxon.txt·distribution.txt 재조회 | 학명·동의어·세계 등급·개별 평가 인용 연도·SIS·평가 ID 확인. 이번에 새 IUCN API 인증을 받거나 호출한 것은 아님 |
| 현재 앱 자료 11,131종 | 실제 DB에서 이전에 저장한 읽기 전용 행을 백엔드에 재생한 `/tmp/rg-expert-all-runtime.json` 대조 | 입력 모드는 saved read-only DB rows replay. 이번 감사에서 새로 실행한 라이브 DB/API 전수 검증으로 표현하지 않음 |

HKBWS는 홍콩에 기록된 종의 전문가 자료다. 이번 결과를 전 세계 11,131종의 전문가 자료 확보로 해석하지 않는다. 목록의 자료 이름은 2024이며, 2025-05-11이라는 페이지 갱신일을 개별 IUCN 평가 연도로 사용하지 않았다. 공식 사이트에 2026 목록 파일 정보가 존재하는 것은 확인했지만, 그 목록 파일을 이번 감사의 원본으로 확보한 것은 아니다.

공식 PDF 원본 SHA-256:

- IUCN 2025-2 Table 7: `8449b798759f09c2626b3693b6bf7e5d48cad1d661c6dbb2e6c1c763ae700caf`
- IUCN 2023-1 Table 7: `639da1d46193be85c7aa9276c0995bb69a225d6911a91ef53c739ff926499b05`

GBIF 고정 원본 SHA-256은 `2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d`이다. 공개 체크리스트의 이용 허락은 CC BY 4.0이다. HKBWS 본문 전체를 재배포하는 별도의 허락을 확보한 것으로 주장하지 않으며, 감사 자료에는 짧은 상태문과 학명·등급·날짜·URL 같은 사실만 보존한다.

## 전수 대조 방법과 결과

학명 비교는 목록에 실제 나타난 전체 이명법 이름의 정확 일치로 수행했다. 이름이 일치하지 않는 경우에는 원래 305종 감사 자료의 **공식 AviList 분류 결정문에 전체 학명이 명시되어 있는지**를 보조 후보로 검사했다. 같은 종소명만 공유하거나 비슷한 이름이라는 이유로 등급을 전달하지 않았다. 보조 후보는 추가 원문 검토 대상이며, 자동 평가 연결이 아니다.

| 검사 | 실제 결과 |
| --- | ---: |
| HKBWS 목록 행 | 584 / 584, 행 번호 누락 0 |
| 비교한 현재 종 | 11,131 |
| HKBWS 학명과 현재 종 학명 정확 일치 | 574 |
| 정확 일치하지 않는 HKBWS 학명 | 10 |
| 목록에 명시된 IUCN 등급 | 72 |
| 빈 칸 또는 등급으로 해석하지 않은 칸 | 512 |
| 명시 등급 72개 중 현재 학명 정확 일치 | 72 |
| 현재 표시와 다른 명시 등급 | 7 |
| 원래 미연결 305종 중 목록 학명 정확 일치 | 8 |
| 정확 일치 없이 공식 분류 결정문 이름으로 얻은 후보 | 29 |
| 해당 목록 대조에서 일치·후보가 나오지 않은 원래 미연결 종 | 268 |

305종은 모두 대조 결과를 갖는다. 마지막 268종은 **이 홍콩 목록에서 일치하지 않았다는 결과**이며, 세계 어디에도 평가나 전문가 자료가 없다는 판정이 아니다. 또한 정확 일치한 8종의 목록 등급 칸은 모두 비어 있으므로, 목록만으로 LC를 지정할 수 없다. 실제 LC 참고 자료 연결은 별도로 확인한 개별 종 설명을 근거로 한다.

캐시 조각에 일부 학명 표기 차이가 남아 있으므로 574건은 문자 단위의 목록 커버리지다. 이것만으로 분류 개념이 동일하다고 인증하지 않는다. 목록의 빈 칸 512개는 LC로 추정하지 않았고, 기존 값은 하나도 덮어쓰지 않았다.

## 등급 차이 7건: 공식 과거 변경으로 설명됨

일곱 차이는 모두 IUCN 공식 발표의 이전·이후 등급과 대응한다. 6건은 2025-2 변경표, 1건은 2023-1 변경표에서 확인했다. HKBWS 목록 갱신일이 늦더라도 각 행의 등급이 최신으로 갱신되었다고 보장하지 않는다는 실제 사례다.

| 현재 종 학명 | HKBWS 목록 → 현재 앱 | 현재 앱 직접 출처 | GBIF 개별 평가 인용 연도 | SIS / 평가 ID | 공식 변경 근거 |
| --- | --- | --- | ---: | --- | --- |
| Anas luzonica | VU → LC | GBIF 2026-1 primary | 2025 | [22680214 / 268091408](https://www.iucnredlist.org/species/22680214/268091408) | 2025-2 Table 7, p.1, VU→LC, N |
| Platalea minor | EN → VU | AviList v2025b snapshot | 2025 | [22697568 / 154689773](https://www.iucnredlist.org/species/22697568/154689773) | 2025-2 Table 7, p.3, EN→VU, G |
| Psittacula eupatria | NT → LC | AviList v2025b snapshot | 2025 | [22685434 / 241494588](https://www.iucnredlist.org/species/22685434/241494588) | 2025-2 Table 7, p.3, Palaeornis eupatria NT→LC, G |
| Terpsiphone atrocaudata | NT → LC | GBIF 2026-1 primary | 2023 | [22707151 / 154681084](https://www.iucnredlist.org/species/22707151/154681084) | 2023-1 Table 7, p.4, NT→LC, N |
| Helopsaltes pryeri | NT → LC | GBIF 2026-1 primary | 2025 | [22715480 / 266406861](https://www.iucnredlist.org/species/22715480/266406861) | 2025-2 Table 7, p.3, NT→LC, N |
| Helopsaltes pleskei | VU → LC | AviList v2025b snapshot | 2025 | [22714674 / 266418398](https://www.iucnredlist.org/species/22714674/266418398) | 2025-2 Table 7, p.2, VU→LC, N |
| Emberiza rustica | VU → NT | GBIF 2026-1 primary | 2025 | [22720960 / 276823281](https://www.iucnredlist.org/species/22720960/276823281) | 2025-2 Table 7, p.2, VU→NT, G |

위 연도는 GBIF에 기록된 개별 평가 인용에서 읽었다. 앱에서 AviList snapshot을 사용하는 세 종의 객체에 해당 평가 연도·ID가 이미 연결되어 있다는 뜻은 아니다. 이번 감사는 그 세 종을 primary로 승격하는 코드를 작성하지 않았다.

Psittacula eupatria는 공식 변경표·GBIF accepted 레코드에서 Palaeornis eupatria로 나타난다. 고정 GBIF 원본에 Psittacula eupatria 동의어 레코드가 있고, 같은 Palaeornis 평가 URL·인용을 명시하는 것을 확인했다. 단순한 종소명 매칭으로 이 이름 관계를 만든 것이 아니다.

G는 공식 표의 실제 보전 상태 변화, N은 새 정보·기준 이해·분류 수정·오류 정정 등으로 인한 비실제 상태 변화를 뜻한다. N인 각 종의 정확한 개별 변경 사유까지 독립 검증한 것은 아니므로, 개체수가 회복되었다는 설명으로 바꾸지 않는다.

결과 분류는 `historical_category_change_confirmed` 7건, 미해결 **등급 값 차이** 0건이다. 새 전체 종 분류 개념의 평가 일치 검증은 0건이다. 과거 등급 변경의 확인과 현행 분류 범위 전체의 독립 검증은 구분한다.

모든 개별 IUCN 평가 페이지 접근을 시도했지만 도구에서 403 또는 접근 불가로 실패했다. 위 링크는 실제 GBIF 원본에 있는 SIS·평가 ID URL이며, 성공적으로 읽은 IUCN 개별 원문처럼 표현하지 않는다. 반면 두 공식 변경표 PDF는 직접 다운로드에 성공했으며 관련 표 행을 이미지로도 확인했다.

## 개별 전문가 출처 보강 9종의 범위

부모 통합 작업에서 아래 9종을 HKBWS 참고 출처로 연결했다. 모두 LC를 명시하는 전문가 출처의 참고 연결이다. 기존 AviList NE와 원래 미연결 상태를 보존하며, `reference_only`와 `independently_verified=false`를 유지한다.

| 현재 앱 학명 | HKBWS 출처 이름·날짜 | 자료 범위와 남은 한계 |
| --- | --- | --- |
| Parus cinereus | [Parus minor](https://avifauna.hkbws.org.hk/species/0270/034800), 갱신 2024-01-10, 인용 2023 | LC를 과거 Parus major 포함 평가로 설명. Cornell 2024의 minor→cinereus 관계를 별도 근거로 보존. 현재 cinereus 전체의 신규 독립 평가가 아님 |
| Anser serrirostris | [Anser serrirostris](https://avifauna.hkbws.org.hk/species/0010/000400), 갱신 2025-06-04, 인용 2023 | 평가에서 fabalis와 serrirostris를 하나의 종으로 다룬다고 원문에 명시 |
| Larus mongolicus | [Larus mongolicus](https://avifauna.hkbws.org.hk/species/0110/017510), 갱신 2025-12-03, 인용 2025 | 평가 이름 Larus smithsonianus의 넓은 Arctic Herring Gull 범위를 인용 |
| Anthus japonicus | [Anthus japonicus](https://avifauna.hkbws.org.hk/species/0440/054600), 갱신 2025-03-04, 인용 2023 | 현재 제목은 japonicus이지만 권장 인용에 이전 rubescens가 남음. 개별 평가 학명은 확인되지 않아 null 유지 |
| Alcippe hueti | [Alcippe hueti](https://avifauna.hkbws.org.hk/species/0360/043800), 갱신 2024-07-25, 인용 2024 | Alcippe morrisonia에 포함된 LC 평가라고 명시 |
| Cinnyris ornatus | [Cinnyris ornatus](https://avifauna.hkbws.org.hk/species/0420/052300), 갱신 2025-06-16, 인용 2023 | 현재 제목은 ornatus이지만 권장 인용은 jugularis, 본문 아종 표기는 C. j. rhizophorae. 현재 범위와 과거 범위의 동일성을 단정하지 않음 |
| Larus brachyrhynchus | [Larus brachyrhynchus](https://avifauna.hkbws.org.hk/species/0110/017100), 갱신 2024-01-14, 인용 2023 | LC 옆 평가 이름이 Larus canus brachyrhynchus로 명시됨 |
| Ardea coromanda | [Bubulcus coromandus](https://avifauna.hkbws.org.hk/species/0170/023000), 갱신 2024-01-13, 인용 2023 | ITIS 동의어 관계를 보존. 본문에 과거 Bubulcus ibis의 전 세계 분포 설명이 남아 있어 평가 범위 동일성을 단정하지 않음 |
| Butorides atricapilla | [Butorides striata](https://avifauna.hkbws.org.hk/species/0170/022800), 갱신 2024-01-13, 인용 2023 | 원문의 넓은 구세계·남미 범위와 현재 AviList 구세계 atricapilla의 관계를 분리하여 표시 |

날짜 열의 갱신일과 권장 인용 연도는 개별 IUCN 평가 연도가 아니다. 위 전문가 참고 레코드의 `assessment_year`를 그 날짜로 채우지 않았다. `exact_source_name`이라는 내부 값은 출처 제목의 학명과 앱 학명의 일치를 나타내며, 과거 평가 분류 범위까지 일치한다고 인증하는 값으로 해석하지 않는다. 범위 설명은 별도로 유지한다.

보조 분류 근거에는 [Cornell 2024 분류 개정](https://www.birds.cornell.edu/clementschecklist/updates-and-corrections-october-2024/)과 [ITIS Ardea coromanda 레코드](https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value=1244987)가 사용된다. 다른 종이나 하위집단에도 같은 LC를 일괄 전달하는 규칙은 도입하지 않았다.

재갈매기 Larus vegae는 [Cornell 공식 설명](https://blog.allaboutbirds.org/guide/Vega_Gull/lifehistory)에서 현재 개별 종 미평가와 더 넓은 Arctic Herring Gull의 LC를 함께 설명하는 자료가 확인되었다. 원문은 Vega·American·Mongolian을 포함하고 BirdLife 2019의 2018 평가 수정 인용을 사용한다. 해당 과거 넓은 평가를 현재 Vega만의 독립 평가로 올리지 않는다. HKBWS 개별 페이지 접근 실패 및 Cornell 페이지 갱신일 미확인 문제 때문에 이 조사에서 새 독립 등급으로 처리하지 않았다.

## 산출물과 실제 검증

변경 파일은 다음 세 개다. 런타임 보전 코드와 기존 원자료·등급 레코드는 이 감사 담당자가 수정하지 않았다.

- [전수 대조 JSON](assets/2026-10-09-hkbws-conservation-coverage.json): 584행 목록 사실, 305종 결과, 등급 차이 7건의 현재 출처·GBIF 인용·SIS·평가 ID·PDF 페이지·해시·접근 한계 및 개별 검토 참고 사실.
- [재현 스크립트](assets/2026-10-09-hkbws-conservation-coverage.py): 보존한 HKBWS 사실과 제공한 runtime replay·원래 unresolved 감사 자료를 대조하는 읽기 전용 Python 스크립트. 웹사이트를 다시 수집하는 크롤러는 아님.
- 이 검토 문서: 방법·근거·한계와 실제 수행 범위를 기록.

재현 예시:

```sh
python3 docs/verification/assets/2026-10-09-hkbws-conservation-coverage.py \
  --source-facts docs/verification/assets/2026-10-09-hkbws-conservation-coverage.json \
  --runtime RUNTIME_REPLAY.json \
  --unresolved docs/verification/assets/2026-10-09-unresolved-conservation-review.json \
  --output RECOMPUTED_COVERAGE.json
```

이번 실제 실행에서는 저장된 11,131종 runtime replay를 입력해 JSON의 목록 비교·305종 결과·7건 충돌 상세가 재계산 결과와 정확히 같음을 확인했다. 584행 번호 전체 존재, 학명 584개 중복 없음, 개별 상태문 25단어 이하, 7개 공식 변경 근거가 현재 표시를 뒷받침함을 별도 assertion으로 확인했다. 실패 0건이다. 이를 새로운 전체 Python·frontend 테스트 실행 수치로 합산하지 않는다. DB/API 조회나 브라우저 배포 검증은 이 감사에서 새로 수행하지 않았다.

감사 스크립트 추가 후 `graphify update .`는 성공했다. SQL parser 의존성이 없어 일부 SQL 파일 추출을 건너뛰었다는 도구 경고가 있었으며, 이번 감사 스크립트 재현 결과와는 별개다.

## 커밋·배포와 후속 사항

이 감사 담당자는 커밋·push·배포를 실행하지 않았다. 부모 통합 담당자로부터 9종 보강을 포함한 TEST 커밋 `71501e3`의 TEST 배포 완료를 전달받았지만, 이 문서 작성자의 독립 배포·브라우저 검증 결과로 기록하지 않는다. 운영 변경은 수행하지 않았으며 사용자가 승인하기 전 운영 배포를 하지 않는 제한을 유지한다.

후속 작업은 다른 지역·종 범위 전문가 자료 조사, 현재 종 전체에 맞는 개별 평가 출처 연결, HKBWS의 최신 목록·종 설명 갱신 확인이다. 목록 미일치 268종과 보조 후보 29종은 원래 305종의 목록 대조 분류이며, 별도 전문가 설명으로 보강한 종도 포함될 수 있다. 이 수치를 최신 미연결 종 수로 그대로 사용하지 않는다. 305종에 결과 행이 있다는 사실을 305종의 평가 자료 확보 완료로 표현하지 않는다. 이번 9종 참고 보강과 역사적 등급 차이 해소도 전 세계 전체 종에 대한 실시간 IUCN 평가 독립 검증을 뜻하지 않는다.
