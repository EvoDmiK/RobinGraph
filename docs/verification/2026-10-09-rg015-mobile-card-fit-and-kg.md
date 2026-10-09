# RG-405 모바일 화면 안에 카드 맞추기·체중 kg 표시

- 작업일: 2026-10-09
- 구현 커밋: `7627d5125fa40b244c05d4052c225925abdd84b1` (`origin/dev` push 완료)
- 요청: 모바일에서 카드 전체가 화면 안에 들어오도록 하고, 1,024g처럼 변환 가능한 체중은1.02kg으로 표시한다.
- 예시의 382g→328g은 오타로 보고 원래 382g을 보존한다는 해석을 사용자에게 안내했다. 1,000g 이상만 kg·소수 둘째 자리로 표시하고 그 미만은 g를 유지한다.

## 원인과 변경 전후

직전4048778는 자료 유무에 관계없이 팝업 외곽 크기를 통일했지만 카드에 min-height:100%만 지정했다. 공통grid의 내용 최소 높이가 팝업보다 커지면 카드 자체의 하단 테두리는 여전히 화면 밖에 내려갈 수 있었다. 실제 NAS TEST의320×568 화면에서dialog 하단552px·카드 하단780.875px·카드 높이756.875px·외부 scrollHeight773/clientHeight536을 확인했다.390×844는 콘텐츠가 짧으면 맞을 수 있어 작은 높이에서 따로 재현했다.

변경 후 모바일 카드 자체의 높이를 팝업 안에 고정하고 앞/뒷면 콘텐츠만 내부 스크롤한다. 닫기 버튼과 카드 테두리는 스크롤 밖에 고정하며, 사진·기본 정보·관찰·분포의 공통 자리를 유지한다. 짧은 화면에서는 사진 높이와 여백만 줄이고 긴 문장이나 자료를 잘라 버리지 않는다. 모든 내용을 무조건 한 화면에 넣거나 글씨 전체를 축소하는 변경은 아니다. PC는 기존 레이아웃과 팝업 스크롤 정책을 유지한다.

카드 앞면·뒷면·종 수준 참고 자료의 체중은 원래g 값이1,000 이상인 경우kg으로 표시한다. 예:1024g→1.02kg,1000g→1.00kg,1156g→1.16kg.382g·0g·이미kg인 값·다른 단위는 유지한다. 원본trait 값/단위/display와 답변 출처의g 수치를 변경하지 않는다. 서로 다른 출처의 측정은 각각 변환해 보존하고 아종 직접 값과 종 수준 참고 값도 합치지 않는다.

## 구현 파일과 설계

- `src/robingraph/api/static/styles.css`: 폭 600px 이하 또는 높이 600px 이하의 coarse pointer 환경에 모바일 규칙을 적용한다. dialog/card에 border-box와 제한 높이를 지정하고 자동 최소 높이를 min-height:0으로 끊는다. faces의 grid 행은 minmax(0,1fr), 각 면은 overflow:auto로 처리해 보이지 않는 면의 긴 내용이 앞면의 빈 스크롤을 만들지 않게 한다. safe-area inset과 dvh를 함께 반영하고 닫기는 absolute·44px·z-index5로 유광층4보다 앞에 둔다. 짧은 화면의 사진 높이·패딩·기본 정보 간격을 줄이며 스크롤바는 기존처럼 숨긴다.
- `src/robingraph/api/static/chat.js`: 면 전환과 재열기 시 양면 scrollTop을 초기화하고 도넛 툴팁의 임시 scroll guard를 새 스크롤 영역에도 연결한다. 각 면을 키보드로 포커스할 수 있어 Space 등 기본 스크롤을 사용하며, 카드 본인의 Enter/Space 뒤집기와 hidden/inert 처리는 유지한다. cardTraitValue는 카드용 체중만 변환한다. 원 value를 우선하고 value가 없으면 콤마 형식이 올바른 숫자 display를 읽으며, 유한한 값만 변환한다. 추정 표시를 유지하고 원 source heading은 변환 전 g 값을 기록한다.
- `tests/frontend/chat_ui.test.js`: 새 표시 계약과 카드 체중 경계·출처 보존·독립 측정·아종 reference·면 스크롤 초기화·툴팁 guard 정리를 검증한다.

## 협업·검증 범위

pc_drag_popup_fix가 구현과 회귀 테스트를 맡고 card_selection_review가 읽기 전용 최종 diff를 검토했다. 새 스크롤 영역의 초기화·툴팁 해제·포커스·유광/닫기 겹침과 체중의 원자료 보존을 확인했으며 차단 결함은 발견하지 않았다. root는 실제 브라우저 재현·실측·NAS TEST 배포·문서·Obsidian·Git을 맡았다. 워커의 실제 런타임 모델명은 별도로 확인하지 않았다.

- frontend전체: **240 통과 / 실패0 / 건너뜀0**. 체중12경계케이스, 다중 원자료/종 수준 참고 변환과 원g 출처 보존, 내부 스크롤·툴팁·키보드 검사가 포함된다.
- node --check chat.js, git diff --check: 통과.
- graphify update .: exit0, **3794 nodes /8121 edges /217 communities**, AST16/16. 기존SQL dependency경고4개·무심볼 안내2개이며 의미 추출 API는 사용하지 않았다.

## 실제 브라우저 재현·검증

[변경 전 실제 서버 실측](assets/2026-10-09-RG015-mobile-fit-before-browser.json)은390×844와320×568 두 설정이다.320px에서는 카드 하단이780.875px까지 내려갔다. 새 카드에서는 같은320×568의카드 하단이544px,dialog 하단552px,외부scrollHeight/clientHeight가536/536으로 바뀌어 프레임 전체가 화면 안에 남는다. 앞면과 뒷면은같은높이를사용한다.

검증은 실제 NAS TEST API/DB의 청둥오리 PC1280×900·모바일390×844/375×667/320×568/412×915/가로844×390과 흰뺨검둥오리390×844의 **7설정**, 모의 API 전체 자료 없음390×844와 1024g320×568의 **2설정**을 구분한다. 모든 설정에서 프레임/닫기 버튼의 viewport 포함·양면 높이 일치·가로 넘침 없음·상세 펼침·제목 드래그·닫기/재열기·pageerror0을 확인한다. 모바일에서는 긴 관찰을 넣는 UI 모의 갱신으로 내부 스크롤/면 전환 초기화·native 세로 터치·viewport 높이80px 축소/복원을 검사하고, 도넛이 있으면 내부 scroll 때 툴팁 해제를 검사한다. 모의 API와 긴 설명 UI 갱신을 실제 자료 성공으로 합산하지 않는다.

초기 기본 레이아웃9설정은 통과했으나 native 세로 터치를 보강한 검사에서 가로 화면 스크롤이0으로 기록됐다. 앱 JS를 제거한 최소 재현과 dialog 없는 단독 scroll div에도 동일 현상이 있었고 portrait 대조는 통과했다. CDP 합성 스크롤은 같은 DOM 좌표에 Position out of bounds를 반환했다. 기기 폭/높이뿐 아니라 screenOrientation을 포함한 Emulation.setDeviceMetricsOverride를 명시하자 같은 코드·178px 스크롤 영역에서 native scrollTop0→109, 합성 scrollTop101이 확인됐다. root 검증기는 세로/가로 방향과 기기 크기를 모두 명시하도록 수정했다. 앱 소스를 이 현상 때문에 수정하지 않았으며 기존 실패는 테스트 환경 설정 오류로 구분한다.

실제 NAS API/DB + 로컬 새 JS/CSS 대체는 최종 **9설정 모두 통과**했다. 실제 API7·모의 API2를 구분하며 모바일8설정 모두 native 세로 터치·프레임 고정·resize·면 전환 초기화를 확인했다. 실제 흰뺨검둥오리는1.16kg, 모의1024g은1.02kg, 청둥오리843.42g은 g로 표시됐다. [로컬 검사 결과](assets/2026-10-09-RG015-mobile-fit-local-browser.json).

실제 배포 자산으로도 **9설정 모두 통과**했다. 실제 API/DB7설정·모의 API2설정을 구분한다. 모바일8설정에서 프레임 고정·native 세로 터치·resize·긴 자료 내부 스크롤·면 전환 초기화가 통과했고, 가로844×390도 포함한다. 앞/뒷면 체중이 같고 kg 변환된 값의 원래 g 출처도 남아 있음을 실제 DOM에서 확인했다. 모든 설정에서 공개 JS/CSS가 소스와 바이트 단위로 같고 health status=ok·mode=neo4j·deployment_target=test임을 확인했다. 최종 runner exit0, pageerror0이며 브라우저 종료 timeout은 없었다. [실제 서버 검사 결과](assets/2026-10-09-RG015-mobile-fit-browser.json).

배포 후 [320px 작은 화면 앞면](assets/2026-10-09-RG015-mobile-fit-mallard-front-320x568.png)과 [390px 뒷면](assets/2026-10-09-RG015-mobile-fit-mallard-back-390x844.png), [실제 체중 kg 표시](assets/2026-10-09-RG015-mobile-fit-spotbill-front-390x844.png)를 직접 열어 카드 외곽과 고정 닫기 버튼·기본 정보·표시 단위를 확인했다. 작은 화면의 긴 정보는 내부 스크롤로 읽는다.

## NAS TEST 배포·Git

구현7627d51은origin/dev에push완료했다. 고정소스archive SHA256은`941b1f890fa4cdb83dea62f75844154ad977dee3116ca467d2cf6686d32ba461`이다. 원격 archive SHA256·MANIFEST를 검증한 뒤 이전 TEST 설정을 권한0600으로 재사용하고 이미지/VCS ref만 새 소스로 갱신했다. deploy_nas.sh deploy/verify는 exit0, 컨테이너 robingraph-api-test는 running/healthy, 이미지 OCI revision은 전체 구현 커밋과 일치한다. 이미지 `robingraph-api:test-rg015mobilefit-7627d51`, 릴리스 `/home/kimdove/RobinGraph-rg015mobilefit-7627d51`이다. 이전 `robingraph-api:test-rg015observation-4048778` 이미지·릴리스는 보존했다. PROD는 배포하지 않았다. [배포 무결성·health](assets/2026-10-09-RG015-mobile-fit-deployment.json).

[최종frontend로그](assets/2026-10-09-RG015-mobile-fit-frontend-tests.txt).

## 한계와 기록 관리

모바일 입력은Chrome CDP 에뮬레이션이다. 물리 휴대폰·Safari/WebKit·Firefox·실제 노치 safe-area·모바일 브라우저 주소창의 실제 움직임·스크린리더 전체·모든 종/아종과 외부 사진 전송 전체 성공은 확인하지 않았다. viewport resize와dvh 반응은 실제 주소창 동작 전체 시험과 구분한다. Python 전체 DB 회귀는 JS/CSS 카드 표시 변경이므로 재실행하지 않는다. 외부 추가 자료가 없거나 실패하면 기존 미확인 안내를 유지한다.

저장소와Obsidian 상세·백로그RG-405·프로젝트index의 핵심 결과를 맞추고, 이전 관찰 포인트/자료 없는 카드 형식 통일 기록을 보존한다. 신규 대기2건·최후순위 보류4건은 변경하지 않는다. 인증 정보는 문서에 포함하지 않는다.


Obsidian 상세·백로그·index 저장 후 다시 읽어 상세 본문 일치·RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 불변을 확인했다. 증거 링크가 실제 파일에 연결됨을 검사했고 이번 SSH master를 종료했다. 남은 headless Chrome은0개다. 검증 문서와 JSON/PNG 증거는 구현 이후 별도 docs 커밋으로 origin/dev에 보관한다.
