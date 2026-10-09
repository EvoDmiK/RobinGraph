# RG-015 먹이 구성·활동 위치 도넛 차트와 플로팅 툴팁

- 작업일: 2026-10-09
- 상태: 구현·검증·NAS TEST 배포 완료
- 구현 커밋: `a8aa6c1d964f30b8ee866ac25c44ad13bcc26077` (`origin/dev` push 완료)
- 요청: 먹이 구성과 먹이 활동 위치를 작은 도넛 차트 두 개로 한 줄에 표시하고, 각 영역에 포인터를 올리면 항목명·비율을 플로팅으로 보여준다.

## 배경과 확인한 원인

직전 TEST 소스 `ddf002f`는 먹이 구성을 항목별 막대로, 먹이 활동 위치를 퍼센트 문자열로 표시했다. 항목이 많으면 뒷면이 길어지고 두 분포를 나란히 비교하기 어려웠다. 사용자 예시의 제목인 ‘먹이 구성’·‘먹이 활동 위치’를 기준으로 이번 두 차트의 대상을 정했다. 첨부된 Grafana 화면 자체는 이번 변경 범위에 포함하지 않았다.

graphify 관계 질의와 카드 생성·분포 표시·드래그 예외·출처 통합 코드를 확인했다. 분포 자료는 이미 trait.value에 개별 항목과 숫자 비율을 제공하므로 DB/API 변경 없이 프런트엔드에서 실제 수치에 맞는 SVG를 생성할 수 있었다. 기존 카드 전체 영역 드래그와 새 차트의 터치·키보드 입력이 충돌하지 않도록 차트를 조작 예외 영역으로 등록했다.

## 변경 전후 동작과 구현

`src/robingraph/api/static/chat.js`의 buildCardTraitGrid가 diet_distribution과 foraging_strata_distribution을 모아 두 열로 배치한다. 각 열에 제목과 최대120px 도넛을 표시한다. 서로 다른 자료의 분포는 합치지 않고 자료별로 보존하며 한쪽 자료가 없으면 기록된 자료 없음을 표시한다.

buildDistributionChart는 SVG의 실제 채워진 path로 각 항목을 만든다. 원의100%를 기준으로 원자료 퍼센트만큼 그리며 임의로 정규화하지 않는다. 합계가100% 미만이면 미기록 부분을 남긴다. 단일100%도 가운데 구멍이 있는 완전한 고리로 만든다. 음수·100초과·비수치·합계100초과 등 잘못된 분포는 원형 비율을 확정해 그리지 않고 원래 값과 안내를 제공한다. 0%는 면적을 만들지 않지만 상세 값 목록과 답변 출처 원자료에 남긴다. 미등록 항목명도 원문을 텍스트로 보존한다.

색상 영역에 마우스를 올리거나 터치하면 한국어 항목명과 실제 비율이 뜬다. 키보드 Tab 포커스도 같은 툴팁을 제공하고 Enter/Space 입력이 카드 전환으로 전파되지 않도록 한다. chart의 data-card-drag-exempt로 차트에서 시작한 조작과 본문 드래그를 구분한다. 툴팁은 pointercancel·포커스 이탈·회전·닫기·재열기·스크롤·창 크기 변경 등에 정리하고 임시 리스너도 해제한다.

`src/robingraph/api/static/styles.css`는 minmax(0,1fr) 두 열, 작은 SVG, 열 안에서 표시되는 플로팅 툴팁, 상세 값 목록·자료 안내를 추가한다. PC와320px 모바일에서도 두 차트가 한 줄에 놓인다. 카드 스크롤바 숨김과 필요한 세로 스크롤, 영어 보조 이름·학명·유광 효과 및 글씨 선택 차단은 유지한다. 카드 출처를 되살리지 않고 원래 display와 모든 원자료 항목을 기존 ‘답변 출처 보기’ 하나에 연결한다.

`tests/frontend/chat_ui.test.js`는 기존 막대 검사를 도넛 계약으로 갱신하고6개 회귀검사를 추가했다. 두 열·자료 대응·원비율·0%·미기록·100%·잘못된 값·미등록 항목·참고 범위·툴팁·드래그 분리·리스너 해제를 검사한다.

## 협업과 검증 결과

pc_drag_popup_fix가 JS/CSS·회귀검사·graphify 갱신을 담당했다. card_selection_review는 읽기 전용 독립 검토로 원비율·출처·0% 보존·예외값·입력 분리·리스너 정리를 확인했고 차단 결함을 발견하지 못했다. root는 실제 API/브라우저 검증·geometry fixture·패키지·기록·Git을 담당했다. 별도 워커 모델명은 확인하지 않았다.

- 전체 frontend `node --test tests/frontend/*.test.js`: **231 통과, 실패0, 건너뜀0**. 모의 DOM 검사이며 root와 구현 담당자가 각각 실행했다. [실행 로그](assets/2026-10-09-RG015-donut-frontend-tests.txt).
- node --check 구현·테스트 및 git diff --check: 통과.
- 실제 NAS TEST API/DB + 로컬 새 JS/CSS 대체: **4설정 통과**. 1280×900 마우스,390×844 Pixel7 CDP 터치,320×640 터치,390×844 터치 reduced-motion이다. 청둥오리의 실제 식단5개·활동 위치3개를 설정별로 검사해 **32개 영역**의 항목명·비율·툴팁 화면 경계를 확인했다. 한 줄 배치·가로 넘침 없음·숨긴 스크롤바·키보드 포커스/Enter·차트 입력 미뒤집힘·본문 드래그 뒤집힘·회전 시 툴팁 제거·단일 출처와 원자료 URL/표시 보존·pageerror0을 확인했다. [실제 API+로컬 자산 결과](assets/2026-10-09-RG015-donut-local-browser.json).
- 실제 Chrome DOM + **모의 초기 API** geometry fixture: **3건 통과**. 식단40/10/50와 활동 위치50/50, 양쪽 단일100% 고리의 채움/중앙 구멍, 식단20/30의 나머지50% 및 활동 위치120/-20의 비정규화 fallback을 확인했다. 실제 DB에 이 특수 분포를 적재한 검사는 아니다. [모의 API 결과](assets/2026-10-09-RG015-donut-fixture-local.json).

초기 fixture 검증기는 data-component가 있는 path와 상세 목록 li를 함께 세어 실패했다. 실제 SVG segment만 선택하도록 검증기 선택자를 고친 뒤3건이 통과했다. 초기320px 터치 검증은 고리 안쪽 경계에 가까운 채움 좌표에서 native tap 대상이 path가 아닌 SVG로 기록돼 툴팁 대기가 실패했다. 스크롤 안정화만으로 해결되지 않았고 제품 결함으로 확정할 근거는 없었다. 검증기를 각 segment의 중간 각도·고리 중간 반지름으로 바꾸고 isPointInFill을 먼저 확인한 뒤 실제 입력을 보내4설정이 통과했다. 최종 검사 성공과 초기 검증기 실패를 구분한다.

[PC 화면](assets/2026-10-09-RG015-donut-local-1280.png), [390px 화면](assets/2026-10-09-RG015-donut-local-390.png), [320px 화면](assets/2026-10-09-RG015-donut-local-320.png), [모션 감소 화면](assets/2026-10-09-RG015-donut-local-390-reduced.png)을 저장했다. root가390/320 캡처를 직접 열어 두 차트·툴팁을 확인했다. 390px 기본 카드의 dialog 높이는774px였고320px에서는 내용773px/표시608px로 세로 스크롤이 필요했다. 모든 화면에서 뒷면 전체가 한 번에 보인다는 의미는 아니다.

graphify update .는 AST 갱신 exit0, **3760 nodes /8082 edges /198 communities**다. 기존 SQL parser 미설치 경고가 있었고 의미 추출 API는 사용하지 않았다. 생성물은 기존 추적 정책을 따른다.

## 배포 준비와 실제 서버 상태

`sh scripts/package_nas_release.sh --output-dir /tmp/rg013-release`로 위 구현 커밋에 고정한 archive·manifest를 만들었다. archive SHA256은 `2b38c358add5adc8adb681513a51c57b2892478e5d2c06635547431b285a025e`다. 로컬 준비 경로는 `/tmp/rg013-release/robingraph-nas-release-a8aa6c1d964f30b8ee866ac25c44ad13bcc26077.tar.gz`이며 `/tmp/rg015-donut-deploy.py`에 같은 소스의 TEST 배포 절차를 준비했다. 임시 경로는 영구 보관을 보장하지 않으므로 사라지면 동일 커밋에서 패키지를 재생성해야 한다.

최초 NAS SSH는 **Connection refused**였다. 당시 업로드·배포 전에 공개 TEST를 확인했고 JS/CSS 모두 이전 ddf002f와 같고 새 a8aa6c1 파일과 달랐다. 공개 health는 정상 TEST였다. [배포 전 연결 거부·자산 비교 증거](assets/2026-10-09-RG015-donut-deployment-pending.json)는 당시 상태를 보존한 기록이며 최종 상태를 뜻하지 않는다.

사용자가 SSH를 열었다고 응답한 뒤 같은 고정 패키지를 업로드했다. 원격 SHA256·MANIFEST를 확인하고 기존 TEST 설정을 권한0600으로 재사용해 이미지와VCS ref만 갱신했다. deploy_nas.sh deploy/verify exit0, 컨테이너 robingraph-api-test healthy, Docker 이미지 OCI revision이 구현 전체 커밋과 일치함을 확인했다. TEST 이미지 `robingraph-api:test-rg015donut-a8aa6c1`, 릴리스 `/home/kimdove/RobinGraph-rg015donut-a8aa6c1`이며 이전 ddf002f 이미지·릴리스는 롤백용으로 보존했다. PROD는 배포하지 않았다.

로컬 자산 대체 없이 실제 NAS TEST API/DB/JS/CSS로 같은 **4설정·32개 영역** 검사를 재실행해 통과했다. 한 줄 배치·한국어 이름/원비율 툴팁·화면 경계·터치·키보드·차트 미뒤집힘·본문 드래그·회전 정리·단일 답변 출처 보존과pageerror0을 확인했다. 공개 JS/CSS 바이트가 로컬 소스와 같고 health status=ok·mode=neo4j·deployment_target=test임을 설정별로 확인했다. [실제 서버 브라우저 결과](assets/2026-10-09-RG015-donut-browser.json), [배포 무결성 결과](assets/2026-10-09-RG015-donut-deployment.json).

서버 JS/CSS를 그대로 사용하고 초기 API만 모의로 대체한 geometry fixture **3건**도 통과했다. 이는 실제 DB의 특수 비율 검증으로 합산하지 않는다. [배포 자산+모의 API 결과](assets/2026-10-09-RG015-donut-fixture-browser.json). 모든 최종 runner exit0이고 browser.close timeout 로그는 없었다. [배포된390px 화면](assets/2026-10-09-RG015-donut-390.png), [PC 화면](assets/2026-10-09-RG015-donut-1280.png), [320px 화면](assets/2026-10-09-RG015-donut-320.png), [모션 감소 화면](assets/2026-10-09-RG015-donut-390-reduced.png)을 저장했다.

## 한계와 후속 사항

물리 모바일·Safari/WebKit·Firefox·스크린 리더·모든 조류/하위 팝업·전체 DB 회귀는 실행하지 않았다. 실제 입력은 Chrome 마우스와 Pixel7 CDP 터치 에뮬레이션이며 실제 DB 질문은 청둥오리 기본 정보다. Python 전체 DB 회귀는 JS/CSS 변경이므로 재실행하지 않았으며 frontend231개와 혼동하지 않는다. 외부 사진 전송 전체 성공을 검증한 작업도 아니다. 새 차트 표면에서 시작하는 native 세로 스크롤은 별도 측정하지 않았다.

요청 범위의 후속 배포 단계까지 완료했다. 향후 물리 기기나 다른 브라우저에서 경계 영역 터치 차이가 재현되면 실제 입력 대상을 기록해 추가로 점검한다. 로컬 자산 검증·모의 API 검사와 실제 배포 서버 검증을 각각 구분해 보존한다.

Obsidian 상세 기록·백로그 RG-015 현황·프로젝트 index에 동일한 구현·검증·배포 완료 범위를 연결한다. 기존 RG-015 배포 이력은 보존하며 신규 대기 RG-014/RG-017과 최후순위 보류 RG-002/RG-010/RG-011/RG-012는 변경하지 않는다. 인증 정보는 문서에 포함하지 않는다.

배포 후390px 화면을 직접 열어 도넛 두 개와 한국어 플로팅 항목을 확인했다. Obsidian 갱신 뒤 다시 읽어 상세 문서와 저장소의 핵심 결과 일치, RG 상세17개 중복 없음, 목차 내부 링크 누락0, 신규 대기·보류6개 상세 본문 불변, 프로젝트 index 연결을 확인했다. 이번 작업의 SSH master 연결은 종료했다. 구현과 검증 문서·PNG/JSON 증거를 dev에 별도 커밋으로 보관하며 실행 이미지는 위 구현 커밋에 고정한다.
