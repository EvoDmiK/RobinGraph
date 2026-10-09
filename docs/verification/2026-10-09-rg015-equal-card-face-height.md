# RG-015 카드 앞·뒷면 세로 높이 통일

- 작업일: 2026-10-09
- 구현 커밋: `f63cbc0503f232a4f2208b092a007f17c4a619bf` (`origin/dev` push 완료)
- 요청: 하단 안내를 제거한 뒤에도 앞면과 뒷면의 세로 길이가 같아야 한다.

## 원인과 변경 전후

직전128da7f는 앞면 안내를 제거했지만 비활성 면을 display:none으로 처리하는 기존 구조를 유지했다. 이 때문에 현재 면의 내용만 dialog 높이에 참여했고, 더 짧아진 앞면에서 뒷면으로 넘기면 카드 높이와 화면 안 위치가 달라졌다. 고정 안내 제거 시 양면 프레임 유지까지 확인하지 못했던 부분을 이번 요청으로 보완한다. graphify 질의와 buildSpeciesCard/showFace·면 숨김 CSS·실제 브라우저 레이아웃을 확인했다.

변경 후 두 면은 더 긴 쪽의 높이를 함께 사용한다. 화면에 맞춘 임의의 고정 픽셀 높이를 지정하지 않아 사진·긴 내용·측정값 펼침·화면 크기 변경에도 양면이 같은 공간을 차지한다. 작은 화면에서는 dialog의 기존 최대 높이와 세로 스크롤을 유지한다. 따라서 같은 카드의 양면 크기가 같다는 의미이며 모든 종의 카드가 하나의 고정 크기라는 뜻은 아니다.

## 변경 파일과 구현

`src/robingraph/api/static/chat.js`는 front/back section을 species-card-faces wrapper에 모았다. showFace는 기존 hidden·data-face·aria-label·scrollTop 초기화에 더해 inert와 aria-hidden을 함께 토글한다. 비활성 면은 높이 계산에만 참여하고 입력·키보드 포커스·접근성 탐색 대상에서 제외한다. 면 전환 시 도넛 툴팁 정리, 드래그·취소·유광·닫기·재열기 및 출처 통합 로직은 유지한다.

`src/robingraph/api/static/styles.css`는 두 면을 동일 grid-area에 놓고 긴 쪽 높이로 함께 늘린다. wrapper와 두 grid item의 min-width:0으로 작은 화면에서 가로 넘침을 방지한다. 숨긴 직계 면만 display:block·visibility:hidden·pointer-events:none으로 처리한다. 사진 figure·tooltip 등 다른 [hidden] 규칙은 변경하지 않는다. 앞면 하단 안내·구분선·버튼은 다시 만들지 않았다.

`tests/frontend/chat_ui.test.js`는 front/back의 직계 자식 탐색을 wrapper 내부 탐색으로 갱신하고 초기/전환의 inert·aria-hidden·공통 부모를 확인했다. 기존 드래그·사진 retry·출처·키보드 검사 내용은 유지한다. 실측 높이는 모의 DOM에서 확정할 수 없으므로 별도 실제 Chrome 검사로 확인한다.

## 협업과 검증

root가 구현·실행 검증·NAS TEST 배포·문서·Git을 담당했다. card_selection_review가 구현 전 접근 방식과 최종 diff를 읽기 전용 검토했다. 비활성 면의 숨김·포커스·입력, 사진/툴팁 숨김 범위, 출처·드래그·뷰포트 스크롤 보존을 확인했고 추가 수정이 필요한 차단 결함을 발견하지 못했다. 워커 실제 모델명은 별도로 확인하지 않았다.

- `node --test tests/frontend/*.test.js`: 최종 **231 통과, 실패0, 건너뜀0**. 초기 실행은229통과/2실패였으며 사진 관련 cardPart 헬퍼가 이전 직계 자식 구조를 가정한 것이 원인이었다. wrapper 내부 탐색으로 갱신한 뒤 전체 검사가 통과했다. 제품의 사진 retry 실패를 관찰한 것으로 기록하지 않는다. [최종 frontend 로그](assets/2026-10-09-RG015-height-frontend-tests.txt).
- node --check chat.js, git diff --check: 통과.
- graphify update .: exit0, **3774 nodes /8096 edges /228 communities**. 기존 SQL parser 경고와 커뮤니티 변경에 따른 hub 이름 자동 갱신 안내가 있었으며 의미 추출 API는 사용하지 않았다.
- 실제 NAS TEST API/DB + 로컬 새 JS/CSS 대체: **4설정 통과**. 1280×900 마우스,390×844 Pixel7 CDP 터치,320×640 터치,390×844 터치 reduced-motion이다. 각 설정에서 기본·측정값 펼침·resize·긴 사진 안내 UI 모의 갱신·실제 응답 사진 복원의5상태를 검사했다. 매 상태의 앞/뒷면 높이·위치와 dialog 크기가1px 이내로 일치하고 가로 넘침이 없었다. 숨긴 면에 programmatic focus를 요청해도 카드 포커스가 유지되는 것과 본문 드래그 전환·pageerror0도 확인했다. [실제 API+로컬 자산 결과](assets/2026-10-09-RG015-height-local-browser.json).

로컬 기본 설정에서 PC dialog 양면은793.875px,390px에서는773.875px,320px에서는608px로 각각 같았다. 카드 자체의 양면 높이도 PC769.875px,390px757.875px,320px756.875px로 각각 같았다.320px에서는 카드가 표시 영역보다 길어 기존 세로 스크롤이 필요하다. 사진 갱신 검사는 클라이언트의 공개 슬롯 갱신 메서드를 호출한 **UI 모의 검증**이며 실제 외부 사진 제공처의 지연 API 성공으로 합산하지 않는다.

## NAS TEST 배포

고정 소스 archive SHA256은 `44e6ba0bb80415fc0797dd9184b0d9bb896c73ba780c3eb55e939ea68ac0c19a`다. 원격 archive SHA256·MANIFEST를 검증한 뒤 이전 TEST 설정을 권한0600으로 재사용하고 이미지/VCS ref만 새 소스로 갱신했다. deploy_nas.sh deploy/verify exit0, 컨테이너 robingraph-api-test healthy, 이미지 OCI revision 전체 커밋 일치를 확인했다. TEST 이미지 `robingraph-api:test-rg015height-f63cbc0`, 릴리스 `/home/kimdove/RobinGraph-rg015height-f63cbc0`다. 이전128da7f 이미지·릴리스는 보존했고 PROD는 배포하지 않았다. [배포 무결성](assets/2026-10-09-RG015-height-deployment.json).

로컬 자산 대체 없이 실제 NAS TEST API/DB/JS/CSS로 **4설정·설정별5상태**의 양면 실측 검사를 재실행해 모두 통과했다. 기본/펼침/resize/사진 안내 UI 모의 갱신/복원에서 높이·위치·프레임 일치, 비활성 면 focus 차단, 새 wrapper 안의 뒷면 제목에서 시작한 마우스·터치 드래그 전환과pageerror0을 확인했다. 공개 JS/CSS 바이트가 소스와 같고 health status=ok·mode=neo4j·deployment_target=test임을 설정별로 확인했다. [실제 서버 높이 결과](assets/2026-10-09-RG015-height-browser.json).

추가 실제 서버 회귀는1280마우스·390touch **2설정**에서 도넛의 실제 영역별 툴팁·키보드·차트 미뒤집힘·본문 드래그·답변 출처 원자료/종평균 설명·앞면 문구/footer 없음·pageerror0을 확인했다. [추가 회귀 결과](assets/2026-10-09-RG015-height-compat-browser.json). 기존 검증 이력을 덮어쓰지 않도록 새 증거 경로로 저장했다. 최종 runner exit0이며 browser.close timeout 로그는 없었다. [모바일 앞면](assets/2026-10-09-RG015-height-front-390.png), [모바일 뒷면](assets/2026-10-09-RG015-height-back-390.png), [PC 앞면](assets/2026-10-09-RG015-height-front-1280.png), [PC 뒷면](assets/2026-10-09-RG015-height-back-1280.png).

## 한계와 기록 관리

물리 모바일·Safari/WebKit·Firefox·스크린 리더·모든 종/아종·모든 이미지 로딩 상태는 검증하지 않았다. 실제 DB 질문은 청둥오리 기본 정보이며 모바일 입력은 Chrome CDP 에뮬레이션이다. 실제 화면의 inactive focus 차단을 확인한 것이 스크린 리더 전체 시험을 대신하지 않는다. 외부 사진 전송 전체 성공을 확인한 작업도 아니다. Python 전체 DB 회귀는 JS/CSS 레이아웃 변경이므로 재실행하지 않았다. 추천 콘텐츠는 아직 추가하지 않았다.

Obsidian 상세·백로그 RG-015·프로젝트 index에 같은 구현·검증·배포 범위를 기록하며 기존 하단 안내 제거와 도넛 검증 이력을 보존한다. 신규 대기2건·최후순위 보류4건은 변경하지 않는다. 인증 정보는 포함하지 않는다.

배포 후 모바일390px 앞/뒷면 캡처를 직접 열어 동일한 프레임과 하단 여백·출처 안내 제거 유지를 확인했다. 실제 서버 기본390px dialog 높이는 양면773.875px로 같았으며, PC는 사진이 로딩된 상태에서 양면843.625px로 같았다. 이는 사진 상태까지 다르면 로컬 대체 검사 때와 전체 높이가 달라질 수 있지만 같은 상태의 양면 높이는 일치함을 보여준다.

Obsidian 갱신 뒤 다시 읽어 RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 본문 불변·index 연결·저장소와 상세 결과 일치를 확인했다. 이번 SSH master 연결을 종료했고 남은 headless Chrome 프로세스가 없음을 확인했다. 문서·JSON/PNG 증거를 구현과 별도 dev 커밋에 보관한다.
