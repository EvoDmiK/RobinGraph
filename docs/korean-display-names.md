# 한국어 조류 표시명

2026-10-06 사용자 요청에 따라 자동 번역명을 제거했다. 한국조류학회의 **2025 한국조류목록 개정판 v2.1**을 우선하고, 국내 목록 밖의 종은 IOC 한국어 목록과 기관의 종별 자료에서 확인한 한국어 이름도 표시하며, 확인되지 않은 종은 원문 영어 이름으로 표시한다. 영어 이름도 없는 경우에만 학명을 사용한다. 기존 Wikidata 이름도 별도 출처에서 확인되지 않으면 종의 한국어 표시명으로 사용하지 않는다. 이 기준은 카드·설명·같은 속/과 목록·그래프 유사도 TOP3·생태 비교 목록에 공통으로 적용한다.

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

## 국내 목록 밖의 국명 보완 (같은 날 후속 수정)

국내 기록종 목록에 없다는 이유만으로 한국어 이름이 없다고 판단하지 않는다. 전체 활성 종을 IOC World Bird List v15.2의 한국어 열로 재대조하고, 서울대공원 조류 보유현황 45건의 종별 학명·한국어 이름도 확인했다. 학명과 활성 종 ID를 완전 일치시켜 **IOC 25종, 서울대공원 25종**을 추가했다. 현재 국명/한국어 표시명 **646종**, 영어 표시 **10,485종**이다.

자료는 [IOC 다국어 목록](https://www.worldbirdnames.org/new/ioc-lists/master-list-2/)과 [서울대공원 동물 보유현황](https://grandpark.seoul.go.kr/animal/animalList/ko/S001002002003.do?search_animal_cd=0101020000)이다. 기록별 출처 제목과 URL, IOC 시트·행 번호를 보존했다. 동물원 자료는 종별 참고 이름이며, 모든 이름을 한국의 공식 표준명이라고 주장하지 않는다. 괄호의 대체명과 사육 색상 표기는 원문 source_label에 보존하고 앞의 이름을 표시한다.

이미 다른 활성 종에 부여된 이름(예: Anthus rubescens의 ‘밭종다리’), 줄여 쓰거나 오타가 있는 학명, 종보다 아래의 사육형/아종, 국명 오타가 의심되는 기록은 추가하지 않았다. 제외 이유도 supplemental_rejected_candidates에 보존했다. 특히 동물원 자료의 A. poecilorhyncha를 흰뺨검둥오리로 확장하지 않는다. 현재 분류에서 흰뺨검둥오리는 Anas zonorhyncha다.

Nycticorax caledonicus는 IOC 한국어 열에도 이름이 없었고 이번에 확인한 기관 자료에서도 한국어 이름을 검증하지 못했으므로 영어를 유지한다. 검색 화면의 ‘붉은해오라기’는 그대로 적용하지 않는다. [국립생물자원관 자료](https://nibr.go.kr/aiibook/access/ecatalogt.jsp?Dir=1339&callmode=admin&eclang=ko&start=58&um=s)의 붉은해오라기는 Gorsachius goisagi다.

## 근연종 탐색 목록의 국명 우선 정렬 (2026-10-08)

같은 속·과 탐색은 위 검증표의 종 ID·학명·원자료 영어 이름이 모두 일치하는 후보를 먼저 보여준다. 검증표 대조와 정렬을 Neo4j의 목록 제한 **이전**에 적용해, 미검증 그래프 국명을 가진 후보 때문에 검증된 한국어 이름의 후보가 누락되는 문제를 해결했다. 국명이 없으면 영어 이름, 영어도 없으면 학명을 표시한다. 학명은 함께 제공하며 국명 출처·상태도 유지한다.

가중 점수로 고르는 비교 후보 TOP 3는 점수·학명·종 ID 순위를 유지한다. 한국어 이름이 있다는 이유로 낮은 점수의 종이 높은 점수의 종을 대체하지 않는다. TOP 3의 이름 표시는 동일한 검증 국명 우선 정책을 적용한다. 국명 자료 추가, 자동 번역, 원본 DB 이름·검색 별칭 변경은 이번 수정에 포함하지 않았다. 상세 원인·검증·배포는 [근연종 한국어 우선 기록](verification/2026-10-08-related-korean-priority.md)을 참고한다.
