# RG-405 관찰 포인트와 자료 유무에 관계없는 카드 형식 통일

- 작업일: 2026-10-09
- 구현 커밋: `4048778ace88f2f05da5eccb98a48829e30bbe5e` (`origin/dev` push 완료)
- 요청: 앞면 하단의 빈 공간에 관찰 포인트를 넣고, 자료가 없는 종도 카드의 형식·크기를 통일한다.

## 배경과 확인한 원인

직전 f63cbc0는 한 카드의 앞·뒷면을 공통 grid에 배치해 두 면의 높이를 맞췄다. 그러나 팝업 자체의 높이는 종별 콘텐츠 길이에 따라 달랐고, 자료가 없는 기본 항목과 분포 차트는 DOM에서 생략했다. 따라서 양면은 같아도 서로 다른 종이나 자료가 부족한 카드 사이에서는 형식과 외곽 크기가 달라질 수 있었다. 앞면의 하단 안내를 제거한 뒤에는 대체 콘텐츠가 없어 여백도 남았다.

graphify 질의, buildSpeciesCard·buildCardTraitGrid·사진 갱신과 deferred enrichment 경로, 실제 API sections, Chrome 레이아웃을 확인했다. 관찰 포인트에 사용할 수 있는 출처 포함 appearance/fun_facts 문장이 기존 응답에 있으므로 새 모델 호출이나 종별 하드코딩 없이 이를 재사용한다. 측정치만 있는 appearance와 외부 추가 자료 실패 응답도 실제로 확인했다.

## 변경 전후 동작

앞면 아래에 ‘관찰 포인트’를 항상 배치한다. 출처가 확인된 외관 설명을 우선하여 최대 두 개를 표시하고, 부족하면 재미있는 사실을 ‘알아두기’로 보충한다. 관찰 문장의 숫자·암수·시기·조건을 임의로 삭제하거나 요약하지 않는다. 부리 길이(전체)·접은 날개 길이·꼬리 길이의 명시적 측정 라벨만 제외한다. 설명을 만들기 위한 추가 API 요청은 없다.

자료가 없는 항목은 ‘자료 없음’, 사진은 기존 사진 없음 슬롯, 분포는 ‘기록된 자료 없음’, 관찰 설명은 ‘출처가 확인된 관찰 자료가 아직 없습니다.’로 표시한다. 아종에는 부모 종의 외관을 그 아종의 고유 특징처럼 옮기지 않고 별도 미확인 안내를 표시한다. 더 알아보기 대기·실패·취소 상태도 구분하며, 실패·취소 후 사용할 수 없는 버튼을 다시 누르라는 안내가 남지 않도록 했다.

같은 화면 크기에서는 팝업 폭·높이를 공통으로 사용한다. 폭은 min(460px, 화면 폭−24px), 높이는 min(844px, 화면 높이−32px)이며 기존 padding·box sizing·max-height 규칙이 함께 적용된다. 앞·뒷면은 더 긴 내용의 높이를 공유하고 카드 자체는 팝업을 최소한 채운다. 사진 영역의 최소 높이와 기본 정보 네 행, 뒷면 분포 두 자리를 유지한다. 긴 문장·상세 펼침·작은 화면에서는 숨긴 스크롤바와 기존 내부 세로 스크롤을 사용한다. 실제 정보가 길어질 수 있으므로 모든 콘텐츠를 강제로 한 화면에 잘라 넣는 방식은 아니다.

## 파일별 구현

- `src/robingraph/api/static/chat.js`: CARD_BASIC_LABELS를 공유해 앞면 네 항목과 뒷면 누락 기본 항목 자리를 유지한다. buildCardTraitGrid의 ensureLayout은 주 카드에만 적용하며 아종의 참고 자료 그리드는 기존 정책을 따른다. 관찰 영역은 최대 두 개의 안전한 출처 포함 문장을 선별하고 중복 원문을 제거한다.
- 관찰 출처는 카드 내부에 표시하지 않고 기존 답변 출처에 연결되는 detached source slot에 보관한다. 원문·출처명/URL·라이선스·릴리스·locator·근거 ID·중첩 citation 등 제공된 메타데이터를 텍스트로 보존한다. 기존 단일 패널의 URL 중복 제거와 열림 상태를 사용한다.
- card.updateEnrichment는 명시적인 sections 교체·빈 배열·null을 반영하고 사진만 갱신하는 응답에는 관찰 설명을 보존한다. 초기 profile.sections는 지연 설명 비교가 끝나기 전에 변경하지 않는다. 사진 재시도도 기존 taxon·release·현재 화면 guard를 통과한 뒤 이 갱신 경로를 사용한다.
- `src/robingraph/api/static/styles.css`: 공통 팝업 크기·카드 flex·앞면 하단 관찰 영역·사진 최소 높이·빈 분포 슬롯·긴 문장 줄바꿈을 추가한다. 비활성 앞면도 공통 grid의 flex 레이아웃에 참여하며 inert·visibility·aria-hidden 제어는 유지한다.
- `tests/frontend/chat_ui.test.js`: 기본 네 행 기대값을 갱신하고, 정상/빈 자료/부분 자료/숫자 보존/측정 라벨 제외/아종/출처 메타데이터/지연 갱신/재시도 guard/실패·취소 안내의 회귀를 보강한다.

## 협업과 자동 검증

pc_drag_popup_fix가 JS·CSS·회귀 테스트 구현을 담당했다. card_selection_review가 읽기 전용 최종 diff 검토를 수행했으며 차단 결함은 발견하지 않았다. 검토에서 나온 지연 조회 실패·취소 후 pending 안내 잔존 문제는 구현 담당자가 수정하고 회귀를 추가했다. root는 실제 API/브라우저 검증, NAS TEST 배포, 문서·Obsidian·Git을 담당했다. 워커의 실제 런타임 모델명은 별도로 확인하지 않았다.

- `node --test tests/frontend/*.test.js`: **237 통과 / 실패 0 / 건너뜀 0**. root 재실행도 같은 결과다. 단일 chat_ui 파일은234개이며 전체 frontend237개와 구분한다.
- `node --check src/robingraph/api/static/chat.js`, `git diff --check`: 통과.
- `graphify update .`: exit0, **3785 nodes / 8111 edges / 227 communities**. 기존 SQL parser 미설치 관련4개 경고와 무심볼 파일2개 안내가 있었으며 코드 AST 갱신은 완료했다. 의미 추출 API는 사용하지 않았다.

## 실제 브라우저 검증

로컬 JS/CSS를 대체한 실제 NAS TEST API/DB 검사와, 배포 후 실제 서버 JS/CSS 검사 결과는 아래에 별도로 기록한다. API·사진을 모의한 빈 자료 검증을 실제 DB 성공으로 합산하지 않는다.

로컬 새 JS/CSS + 실제 NAS TEST API/DB에서는 **6설정 통과**했다. 청둥오리1280×900 마우스·390×844 터치·320×640 터치·390×844 터치 reduced-motion과 흰뺨검둥오리390터치·곤줄박이390터치다. 각 설정에서 관찰 원문과 원출처 대응, 기본·측정값 펼침·resize·긴 사진 안내 UI 모의 갱신·실제 응답 복원의5상태에 대한 양면 높이/위치 일치, 가로 넘침 없음, 비활성 면 포커스 차단, 뒷면 본문 드래그 전환과 pageerror0을 확인했다. 기본 dialog 높이는1280px 화면에서844px,390px에서812px,320px에서608px였으며390px 세 종은 같은 크기였다. [실제 API+로컬 자산 결과](assets/2026-10-09-RG015-observation-local-browser.json).

빈 자료 검증은 Chrome에서 API 응답과 사진SVG를 모의했다. 정상·전체누락·부분자료/0값·추가자료대기·아종·긴문장/HTML문자열6케이스를1280마우스·390터치로 **12건 통과**했다. 모든 케이스에서 동일한 dialog 위치/폭/높이, 양면 같은 높이, 기본 네 행·사진 자리·분포 두 자리 유지,0g와 미기록50% 보존, 없는 비율을 실제 차트로 위장하지 않음, 아종 부모 설명 미차용, 삽입 문자열 미실행, 자동 추가 API요청0을 확인했다. 관찰 교체/삭제와 사진만 갱신할 때의 보존도 공개 UI 갱신 메서드로 검사했다. [로컬 자산+모의 자료 결과](assets/2026-10-09-RG015-observation-fixture-local-browser.json).

초기 실제 응답에는 ‘외관 특징과 재미있는 사실의 추가 자료를 현재 조회할 수 없습니다.’ 경고와 측정치3개만 있어 관찰 원문이 없었다. UI는 미확인 안내를 올바르게 표시했으나 검증기가 무조건 관찰 항목1개 이상을 가정해 실패했다. 이후 상태별 기대값을 구분했으며 재조회에서는 실제 출처 포함 설명이 돌아와 최종6설정 모두 관찰 문장 표시까지 통과했다. 별도 NAS 읽기 전용 검사에서 백과 원문 조회도 성공했다. 외부 제공처의 최초 실패 원인을 단정하거나 백엔드 수정으로 복구했다고 기록하지 않는다. 다른 초기 검사에서는 흰뺨검둥오리에 포커스 가능한 차트가 없는데 [tabindex]만 찾는 검증기 선택자가 timeout되어 summary 등 실제 포커스 대상까지 포함하도록 정정했다. 최종 완료 결과와 이러한 검증기 가정 실패를 구분한다.

실제 배포 JS/CSS/API/DB에서도 같은 **6설정이 통과**했다. PC 첫 응답은 추가 자료 실패로 관찰 상태 unavailable, 나머지5설정은 실제 출처 포함 두 문장의 ready 상태였다. 두 경우 모두 카드 프레임과 기본 자리 유지·양면5상태·비활성 focus·드래그·pageerror0을 통과했다. 기본 dialog 높이는844/812/608px이며390px 세 종은812px로 일치했다. 실제 공개 JS/CSS 바이트가 로컬 커밋과 같고, 각 설정의 health가status=ok·mode=neo4j·deployment_target=test임을 확인했다. [실제 서버 결과](assets/2026-10-09-RG015-observation-browser.json).

배포 자산을 사용하는 모의API/사진SVG 검사도 동일12건 모두 통과했다. 실제 DB나 사진 제공처의 자료 없는 종12건을 검사한 것으로 표현하지 않는다. [배포 자산+모의 자료 결과](assets/2026-10-09-RG015-observation-fixture-browser.json). 실제 API/서버 자산의 추가 회귀1280마우스·390터치2설정에서 작은 도넛2개 한 줄 배치·각 실제 구간의 항목/원비율 툴팁·키보드·차트 드래그 미뒤집힘·본문 드래그·출처의 원자료/종평균 설명 보존·앞면 footer 없음·pageerror0도 통과했다. [도넛·출처 회귀 결과](assets/2026-10-09-RG015-observation-compat-browser.json).

배포 후 모바일 앞면과 자료 없는 뒷면 캡처를 직접 열어 형식·공통 프레임·관찰 영역·빈 분포 안내를 확인했다. [실제 모바일 앞면](assets/2026-10-09-RG015-observation-mallard-front-390.png), [실제 모바일 뒷면](assets/2026-10-09-RG015-observation-mallard-back-390.png), [모의 자료 없음 앞면](assets/2026-10-09-RG015-observation-fixture-missing-front-390.png), [모의 자료 없음 뒷면](assets/2026-10-09-RG015-observation-fixture-missing-back-390.png). 최종 브라우저 runner들은 exit0이며 browser.close timeout은 없었다.

## 배포·Git과 남은 한계

구현 커밋은 origin/dev에 push했다. NAS TEST용 고정 소스 archive SHA256은 `5b282e920c9d889788bfeb7e63e22d2125820a40ca4cbea5776d2cadc8d8c8be`다. 원격 archive SHA256·MANIFEST 확인 후 이전 TEST 설정을 권한0600으로 재사용하고 이미지/VCS ref만 갱신했다. deploy_nas.sh deploy/verify는exit0, 컨테이너robingraph-api-test는running/healthy, 이미지OCI revision은전체 소스커밋과 일치한다. TEST 이미지`robingraph-api:test-rg015observation-4048778`, 릴리스`/home/kimdove/RobinGraph-rg015observation-4048778`다. 이전이미지`robingraph-api:test-rg015height-f63cbc0`와 릴리스는 보존했고 PROD는 배포하지 않았다. [배포 무결성/health](assets/2026-10-09-RG015-observation-deployment.json). [최종 frontend 로그](assets/2026-10-09-RG015-observation-frontend-tests.txt).

검증 JSON/PNG와 상세 문서는 구현 이후 별도 docs 커밋으로 origin/dev에 push한다. API키·NAS 인증 정보는 패키지와 문서에 포함하지 않는다.

물리 모바일, Safari/WebKit·Firefox, 스크린 리더 전체, 모든 종/아종과 외부 사진 전송 전체 성공은 검증 대상에 포함하지 않는다. 모바일 입력은 Chrome CDP 에뮬레이션이다. Python 전체 DB 회귀는 클라이언트 JS/CSS 변경이므로 재실행하지 않는다. 외부 관찰 자료 조회가 실패하거나 근거가 없으면 관찰 문장을 만들지 않고 같은 영역에 안내를 표시한다. 아종 자체 자료 확장이나 신규 콘텐츠 생성은 이번 범위에 포함하지 않는다.

저장소·Obsidian 상세·백로그 RG-405·프로젝트 index에 구현·실제 검증·배포 결과를 맞추고 기존 작업 이력을 보존한다. 신규 대기2건·최후순위 보류4건은 변경하지 않는다. 인증 정보는 기록하지 않는다.


Obsidian 상세·백로그·index를 저장 후 다시 읽어 상세 본문과 저장소 기록 일치, RG 상세17개 중복 없음, 목차 내부 링크 누락0, 대기/보류6개 상세 본문 불변을 확인했다. 문서의 모든 증거 링크가 실제 파일에 연결됨을 검사했다. 이번 작업의 SSH master 연결을 종료했고 남은 headless Chrome 프로세스는0개였다.
