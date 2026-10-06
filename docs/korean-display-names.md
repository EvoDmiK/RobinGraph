# 한국어 조류 표시명

2026-10-06 사용자 요청에 따라 자동 번역명을 제거했다. 한국조류학회의 **2025 한국조류목록 개정판 v2.1**에서 확인한 국명을 표시하며, 확인되지 않은 종은 원문 영어 이름으로 표시한다. 영어 이름도 없는 경우에만 학명을 사용한다. 기존 Wikidata 이름도 이 목록으로 확인되지 않으면 종의 한국어 표시명으로 사용하지 않는다. 이 기준은 카드·설명·같은 속/과 목록·그래프 유사도 TOP3·생태 비교 목록에 공통으로 적용한다.

[한국조류학회 자료실](https://sites.google.com/khu.ac.kr/korornsoc/알림마당/자료실)의 공개 XLSX `공식목록` 시트에서 Species 598행을 추출했다. 자료의 안내 시트에는 자유로운 가공과 형식 변경이 허용돼 있다. 원본 SHA-256은 `b660e125a35abc00df77aa61f3ba24997de7fe1d213ef1350ceacfe08466ba7a`이다. 학회의 국명을 그대로 사용하며, 선행 공백만 제거했다. 목록의 표기법을 일반 사전 철자로 임의 변경하지 않는다.

활성 AviList v2025b 11,131종과 학명이 정확히 일치하는 593종, 속 이동을 확인한 3종을 합쳐 **596종**을 적용했다. 나머지 **10,535종**은 영어로 표시한다. 모든 기록에는 원본 학명·시트·행 번호·자료 URL을 보존한다. 한국조류학회 목록은 국내 기록종 목록이므로 해외 모든 종의 국명을 포함하지 않는다.

| 학회 학명 | 활성 AviList 학명 | 국명 | 연결 근거 |
| --- | --- | --- | --- |
| Charadrius dubius | Thinornis dubius | 꼬마물떼새 | AviList v2025b extended의 Protonym |
| Charadrius placidus | Thinornis placidus | 흰목물떼새 | AviList v2025b extended의 Protonym |
| Pardaliparus venustulus | Periparus venustulus | 노랑배진박새 | ITIS의 동물이명 |

분류 연결 자료는 [AviList v2025b](https://www.avilist.org/checklist/v2025b/)와 [ITIS Pardaliparus venustulus](https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value=1279937)다. AviList는 CC BY 4.0이다. 학회에서 별도 종으로 다루는 Anas carolinensis(미국쇠오리)와 Saxicola stejnegeri(검은딱새)는 현재 활성 종에 바로 대응하지 않으므로 다른 종에 이름을 붙이지 않는다. 영어 이름만으로 종 분할·통합을 추정하지 않는다.

예를 들어 Aethia cristatella는 ‘뿔바다새’ 대신 **뿔바다오리**, Cacomantis merulinus는 ‘울음두견이’ 대신 **우는뻐꾸기**로 표시한다. 이름을 출처에서 확인하지 못한 Abeillia abeillei는 **Emerald-chinned Hummingbird**로 표시한다.

`src/robingraph/retrieval/species_ko_names.json`은 출처로 검증한 고정 표시 자료다. ID·학명·원문 영명이 모두 일치할 때만 적용하고 `korean_name_status=source-reference`와 출처 URL을 반환한다. 기존 자동 번역 자료 `species_ko_translations.json`은 삭제했다. 아종과 상위 분류군의 이름에 종 국명을 적용하지 않는다. 상위 분류군의 기존 이름 정책은 별도로 유지한다.

이 변경은 표시 자료 수정이며 Neo4j의 원본 이름 레코드나 검색 별칭을 변경하지 않는다. 새 국명으로 검색할 수 있다는 보장은 없으며, 비교 버튼은 보존된 학명으로 조회한다. 새 분류 릴리스에는 출처 대응을 다시 확인해야 한다.

검증은 출처와 행 번호의 보존, 국명 교정, 미확인 이름의 영어 대체, 릴리스·학명·영명 불일치 차단, 종 분할의 잘못된 연결 방지, 카드·설명·비교에서 과거 자동 번역명 대신 영어 표시를 포함한다.
