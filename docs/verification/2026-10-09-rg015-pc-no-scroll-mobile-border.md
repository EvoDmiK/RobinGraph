# RG-015 PC 스크롤 제거·모바일 테두리 균일화

- 작업일: 2026-10-09
- 요청: 최종 완료 이후 남은 미세 스크롤을 없앤다. 사용자가 스크롤 대상을 PC로 명확히 했으며, 이어서 모바일 좌우 테두리도 위아래와 같은 굵기로 맞추도록 요청했다.

## 확인한 원인과 변경 전 동작

PC의 .species-popup은 고정 높이와 overflow:auto를 사용했고 fit wrapper는 display:contents였다. 이전 전체 카드 맞춤은 모바일에만 적용했다. 공통 앞·뒷면의 자연 높이가 팝업 내용 높이를 넘으면 숨긴 스크롤바가 보이지 않을 뿐 휠·키보드로 실제 스크롤할 수 있었다.

캐시된 청둥오리 응답을 모의 API로 반환한 변경 전 실제 Chrome 실측에서 PC1280×720은 dialog scrollHeight794/clientHeight688, 휠 후 scrollTop106이었다. PC1440×1080은 scrollHeight859/clientHeight844, 휠 후 scrollTop15로 사용자가 말한 작은 스크롤을 재현했다. 같은 모의 응답의1280×900은 스크롤0이었다. 따라서 모든 PC에서 항상 재현되는 문제로 기록하지 않는다. 전역 box-sizing:border-box가 이미 있어서 padding의 content-box 중복을 원인으로 삼지 않는다. [변경 전6설정](assets/2026-10-09-RG015-scroll-before-browser.json)은 모의 API 검증이며 실제 DB 호출로 합산하지 않는다.

모바일에서는 높이에 맞춰 카드가 축소돼도 팝업 외곽 폭이 원래 최대 폭을 유지했다. 특히 가로844×390에서 실제 카드와 팝업의 좌우 간격은140.08px, 위아래는12px였다. 이 수치는 [직전 배포 실제 API/DB 실측](assets/2026-10-09-RG015-final-browser.json)에서 확인했다. 세로375×667도 좌우8.85px 대 위아래8px로 약간 달랐다. 카드 자체의 border 선보다 그 바깥 팝업 배경의 빈 폭이 두꺼워 보이는 원인이었다.

변경 전 모바일 HTML의 scrollTop11/346은 팝업을 여는 버튼의 포커스 이동 시 이미 존재했고 휠 전후 같았다. 배경 스크롤 문제는 재현하지 않았으므로 근거 없이 html 전체 잠금이나 새 전역 이벤트 차단은 추가하지 않았다.

## 변경 파일·구현·변경 후 동작

`src/robingraph/api/static/chat.js`의 fitCard를 PC에도 적용한다. fit wrapper에서 변환 전 offsetWidth/offsetHeight와 가용 크기를 측정한다. PC는 기존 논리 폭과 팝업 폭을 유지하고 최소 높이는 현재 가용 높이로 설정한다. 긴 뒷면이나 펼친 details가 가용 높이를 넘을 때 전체 카드만 비례 축소한다. 적합한 자연 크기는 scale1을 유지한다. 숨긴 면을 포함한 공통 grid 계산은 양면 높이를 같게 보존한다.

모바일은 기존420px 논리 폭과780px 최소 높이 계산을 유지한다. 매번 dialog의 이전 inline width를 먼저 지워 CSS 최대 가용 폭에서 측정하고, 최종적으로 실제 축소된 카드 폭+원래 팝업 padding 폭으로 dialog 너비를 정한다. 좁힌 팝업의 폭을 다음 측정 기준으로 삼아 카드가 계속 줄어드는 피드백을 피한다. 기존 RAF 병합·ResizeObserver·load/toggle/viewport resize·닫기/삭제 cleanup과 visualViewport.scale>1.01일 때 재맞춤을 건너뛰는 핀치 보존은 유지한다.

`src/robingraph/api/static/styles.css`에서는 PC fit frame/surface를 실제 레이아웃 요소로 만들고 팝업·fit frame·사진 media/figure에 양축 overflow:clip을 사용한다. 스크롤바만 숨기는 대신 스크롤 컨테이너를 없애 휠·키보드·focus·프로그램 방식의 미세 스크롤도 방지한다. 사진의 가로 auto/snap도 해제하며 기존 이전/다음 버튼의 hidden figure 선택 방식은 유지한다. 전체 카드 fit이 먼저 내용을 수용하므로 긴 정보를 단순히 잘라내는 수정으로 끝내지 않는다.

닫기 X는 카드 비례 축소 밖에서44px의 absolute 버튼으로 유지한다. PC는12px, 기존 모바일 규칙은8px 위치를 쓴다. 카드 넘김·도넛 클릭 해제/PC 호버·정상 토글 탭·사진 선택·글씨 선택 차단·내용·체중 표시는 수정하지 않는다. PC 원래 외곽 폭은 유지하므로 높이가 부족해 비례 축소할 때 PC 좌우 여백까지 위아래와 같게 만들지는 않는다. 모바일 외곽 폭만 요청에 맞춰 좁힌다.

`tests/frontend/chat_ui.test.js`의 PC 자연 스크롤/fit 없음 기대를 새 동작으로 바꾸고, PC 자연 크기→긴 상세 맞춤→복원과 모바일 좁힌 외곽의 반복 측정에도 누적 축소가 없는 회귀를 추가한다.

## 협업과 자동 검증

pc_drag_popup_fix가 JS/CSS·회귀·graphify를 담당하고 card_selection_review가 읽기 전용 독립 검토를 수행했다. root는 변경 전 재현·실제 Chrome 휠/키보드/터치/포커스·간격 측정·NAS TEST 배포·문서/Obsidian·Git을 맡았다. 독립 검토에서 변경이 필요한 차단 문제는 발견하지 않았다.

- frontend 전체 **248 통과·실패0·건너뛰기0·취소0**. [실행 로그](assets/2026-10-09-RG015-scroll-frontend-tests.txt).
- node --check chat.js·git diff --check 통과.
- graphify update .: AST15/15,3845 노드·8178 간선·224 커뮤니티. 기존 SQL parser 미설치4·no-symbol 안내2 및 community label 안내가 있으며 AST 갱신은 완료했다. 의미 추출 API는 사용하지 않았다.

## 배포 전 실제 브라우저 검증

[기본9설정](assets/2026-10-09-RG015-scroll-local-browser.json)은 실제 NAS API/DB와 로컬 새 자산을 결합한7설정과 모의 API2설정으로 구분한다.

| 구분 | 화면 | 데이터 |
|---|---|---|
|PC|1280×720,1440×1080,1280×900|실제 청둥오리 API/DB|
|모바일 세로|390×844,375×667,320×568|실제 청둥오리 API/DB|
|모바일 가로|844×390|실제 청둥오리 API/DB|
|자료 없음|390×844|traits·sections·images 없음 모의 응답|
|긴 상세|1280×720|설명 길이를 늘리고 사진2개를 넣은 모의 응답|

9설정 모두 양면에서 휠 상하/좌우, PageDown·End·ArrowDown·PageUp·Home, Tab10회 이동 후 팝업·frame·surface·card·faces·각 면·사진 media의 scrollTop/scrollLeft가0이었다. 각 요소에 scrollTop/scrollLeft=40을 대입해도0을 유지했다. 배경 루트 스크롤은 테스트 시작 위치와 같았다. 닫기와 카드 전체가 화면에 포함되고 카드가 팝업 안에 들어오는지 확인했다.

항목·비율 토글과 다른 상세 정보를 실제 클릭해 펼치고, 펼친 내용 하단까지 카드 안에 들어오는지 확인했다. 특히 긴 상세 모의 응답은 fit으로 전체 내용이 수용되고 닫으면 원래 크기로 되돌아온다. 도넛 영역/자료 없는 카드 제목과 사진 영역의 실제 마우스·CDP 터치 넘김, 높이 변경 후 복원, 닫기/다시 열기, pageerror0을 확인했다.

| 화면 | 변경 후 좌우 간격(px) | 변경 후 위아래 간격(px) |
|---|---:|---:|
|390×844|8.00/8.00|8.00/8.01|
|375×667|8.00/7.99|8.00/8.00|
|320×568|8.00/8.00|8.00/8.00|
|가로844×390|12.00/12.00|12.00/12.00|

모바일 fit 배율은390px .833333,375px .793590,320px .666667,가로 .428205로 직전과 같았다. 테두리를 얇게 보이게 하려고 카드 내용이나 글씨를 더 축소하지 않았다. PC1280×900은scale1,720px 높이는 .862338,1080px 높이는 .979689로 자연 내용이 넘는 경우만 맞췄다. 이 배율은 이번 실제 응답의 측정값이며 모든 종의 고정 배율은 아니다.

배포 전 추가2설정(실제 API/DB390×844·긴 상세 모의1280×720)에서 네이티브 핀치1.5배 확대 중 fit 유지, 확대 해제 후 fit 복원과 사진 다음/이전 버튼의 정상 선택·복귀도 통과했다. [추가 검사](assets/2026-10-09-RG015-scroll-edge-local-browser.json). 기본9설정과 같은 조건의 보강 실행이며 고유 화면 수를 더하지 않는다.

## 배포 후 실제 브라우저 검증

[배포 자산9설정](assets/2026-10-09-RG015-scroll-browser.json)도 모두 통과했다. 실제 API/DB7·모의 API2를 구분한다. 공개 JS/CSS 바이트는 구현 소스와 같고 모든 설정에서 health=status ok였다. 양면 휠·키보드·Tab·프로그램 스크롤0, 배경 위치 유지, 펼친 상세 fit, 넘김, resize·재열기·pageerror0을 다시 확인했다. 모바일 세로/가로 네 방향 간격은1px 이내로 같고 기존 fit 배율을 유지했다. 390px 실제 응답의 네이티브 핀치 확대/해제와 긴 상세 모의 응답의 사진 이전/다음 버튼도 통과했다.

PC720px와 모바일 가로 화면 스크린샷을 직접 열어 전체 카드와 닫기가 화면에 들어오고 모바일 네 방향 테두리가 균일한 것을 확인했다. [PC 뒷면](assets/2026-10-09-RG015-scroll-mallard-back-1280x720.png), [모바일 가로 뒷면](assets/2026-10-09-RG015-scroll-mallard-back-844x390.png).

## 커밋·배포

구현 `3e639ce51d9c247a244a2451adcb2a2e9da60a67`를 origin/dev에 push했다. archive SHA256은 `6866f47a2f2fac2c8782d8e14cd49e5b8ac4c393fc61f4dfe5cb269a63be5c64`다. 원격 archive SHA/MANIFEST를 확인하고 기존 TEST 환경파일을0600으로 재사용했다. 이미지/VCS ref만 바꿨다. NAS deploy_nas.sh deploy/verify는 exit0, 컨테이너 running/healthy·OCI revision 일치·health status=ok/mode=neo4j/deployment_target=test를 확인했다. Compose buildx 미설치 안내는 classic builder로 성공했다.

이미지 `robingraph-api:test-rg015scroll-3e639ce`, 릴리스 `/home/kimdove/RobinGraph-rg015scroll-3e639ce`. 이전 `robingraph-api:test-rg015final-217685f`는 보존했다. PROD 배포는 하지 않았다. [배포 무결성·health](assets/2026-10-09-RG015-scroll-deployment.json).

## 한계·남은 작업

브라우저는 Chrome이며 모바일은 CDP 터치 에뮬레이션이다. 물리 휴대폰·Safari/WebKit·실제 노치/주소창 동작·외부 사진/전체 종 DB는 전수 검증하지 않았다. 긴 내용과 짧은 화면은 카드 전체를 비례 축소하므로 작은 글씨가 될 수 있으며, 전체 설명은 채팅 본문에서도 볼 수 있다. PC 외곽 폭은 유지한다. 이번 변경은 UI 레이아웃/스크롤 수정이므로 Python 전체 DB 테스트는 다시 실행하지 않는다. 인증 정보는 기록하지 않는다.

RG-015 최종 완료 상태에서 사용자가 요청한 두 후속 보완만 처리한다. 신규 대기 RG-014·RG-017 및 최후순위 보류 RG-002·RG-010·RG-011·RG-012의 상태는 유지한다. 추가 작업은 별도 지시 전 착수하지 않는다.

배포 검증9설정의 통과 JSON 저장과 Chrome 종료 후 검증기의 browser.close 대기가 끝나지 않아 남은 해당 Node 프로세스만 종료했다. 이 정리 단계 종료를 검증 항목 실패나 미실행으로 숨기지 않는다. 실제 브라우저 항목은 모두 실행·통과했으며 남은 headless Chrome은0개, 이번 SSH master도 종료했다. 후속 검증기의 종료 대기는 제한시간을 두도록 보완했다.

Obsidian 상세·백로그·작업기록 index 저장 후 전체 읽기 일치를 확인했다. RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 불변을 검증했다. 저장소 증거 링크는 실제 파일 존재를 확인했고, 구현과 기록은 별도 커밋으로 origin/dev에 저장한다.
