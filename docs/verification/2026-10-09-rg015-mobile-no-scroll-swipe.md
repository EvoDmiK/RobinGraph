# RG-405 모바일 내부 스크롤 제거·사진 스와이프 복구

- 작업일: 2026-10-09
- 요청: 모바일에서 카드가 넘어가지 않는 문제를 고치고 카드 내부 스크롤을 없앤다.
- 직전 구현 `7627d51`의 내부 스크롤 방식을 이번 요청에 따라 변경한다. 이전 검증 기록은 당시 동작의 이력으로 보존한다.

## 원인과 변경 전후

변경 전 실제 NAS TEST의 390×844 Chrome 터치 에뮬레이션에서 사진 영역으로 시작한 좌우 스와이프는 앞면에 머물렀고, 제목에서 시작한 스와이프는 뒷면으로 넘어갔다. 모든 모바일 넘김이 실패한 것으로 일반화하지 않는다. 기존 JS는 터치 사진·장식 이미지·placeholder를 드래그 제외 대상으로 처리했다. 이를 제거한 첫 구현에서도 사진에서 pointerdown→pointermove→pointercancel이 재현됐다. 사진 media의 overflow-x:auto와 figure의 overflow:hidden이 가까운 스크롤 컨테이너를 만들어 카드 조상의 touch-action만으로는 브라우저의 기본 이동을 막지 못했다.

모바일은 사진·본문·빈 영역에서 좌우로 넘길 수 있게 변경한다. 사진 캐러셀의 기본 가로 스크롤은 막고 이전/다음 버튼을 유지한다. 버튼·링크·상세 토글·차트 등의 기존 조작은 카드 드래그에서 제외한다. 카드와 내부 요소에 pinch-zoom을 적용해 한 손가락 기본 이동을 막고 두 손가락 확대는 허용한다.

앞·뒷면은 자연 높이의 공통 grid를 유지하며, 카드 전체를 고정된 모바일 프레임 안에 비례 축소한다. 내부 스크롤이나 숨겨진 하단을 읽기 위한 스크롤이 필요하지 않도록 한다. 동일한 기본 논리 폭420px·최소 높이780px와 화면 비율 기준 최소 높이를 사용해 자료 없는 카드에도 공통 크기를 적용한다. 닫기 버튼은 축소 대상 밖에44px로 유지한다. 체중 kg 표시와 카드 밖 답변 출처 통합은 보존한다.

## 변경 파일과 구현

- `src/robingraph/api/static/chat.js`: 사진·placeholder·장식 그림의 터치 드래그 제외를 제거하고 팝업 조상을 탐색해 뒤집기·유광·드래그가 기존 dialog를 대상으로 동작하게 한다. 새 fit-frame/fit-surface가 비례 축소만 담당한다. offsetWidth/offsetHeight로 변환 전 크기를 측정해 반복 축소를 방지한다. 열기·내용 갱신·이미지 load·details toggle·ResizeObserver·window/visualViewport resize에서 rAF로 갱신한다. 사용자가 이미 pinch 확대 중이면 재맞춤을 건너뛴다. 닫기·재열기·대화 지우기에서 observer/listener/RAF를 정리한다.
- `src/robingraph/api/static/styles.css`: 모바일 내부 overflow:auto를 제거하고 전체 카드 fit 및 자식 touch-action을 적용한다. 사진의 native 가로 pan을 막고 PC의 기존 레이아웃은 유지한다. safe-area·dvh·낮은 높이의 coarse pointer 조건을 유지한다.
- `tests/frontend/chat_ui.test.js`: 모바일 전체 표시·사진 스와이프·가까운 스크롤 컨테이너·fit 반복 안정성·자료 갱신·pinch 보존·PC 복원·자원 정리·dialog 드래그 대상·대화 지우기 회귀를 검증한다.

## 협업과 검증

pc_drag_popup_fix가 구현과 회귀 테스트를 담당하고 card_selection_review가 독립 diff 검토를 맡았다. root는 실제 브라우저 재현·검증기·NAS TEST 배포·작업 문서·Obsidian·Git을 담당한다. 런타임 모델명은 별도로 확인하지 않는다.

독립 검토에서 차단 결함은 발견되지 않았다. 검토자는 소스 수정과 추가 실행을 수행하지 않았다.

- frontend: **244 통과 / 실패0 / 건너뜀0**, [실제 로그](assets/2026-10-09-RG015-no-scroll-frontend-tests.txt).
- node --check와 git diff --check 통과.
- graphify update .: exit0, AST14/14,3811 nodes/8149 edges/217 communities. 기존 SQL 의존성 경고4개·무심볼 안내2개. 의미 추출 API는 사용하지 않는다.
- [변경 전 실제 서버 재현](assets/2026-10-09-RG015-no-scroll-before-browser.json): 사진 swipe 실패·제목 swipe 성공, 양면 overflow:auto.
- [실제 API/DB+로컬 새 JS/CSS](assets/2026-10-09-RG015-no-scroll-local-browser.json): **9설정 모두 통과**. 실제 API/DB7설정과 모의 API2설정을 구분한다. 실제 자료는 PC1280×900, 청둥오리390×844·375×667·320×568·가로844×390·동작 축소390×844, 흰뺨검둥오리390×844다. 모의 자료는 전체 없음/체중만 있음390×844다.
- 각 설정에서 사진·앞면 본문·뒷면 제목 스와이프 양방향, 카드/닫기 viewport 포함, 앞·뒷면 같은 높이, 닫기/재열기·pageerror0을 확인했다. 모바일8설정에서 native 세로 이동에 scrollTop0·면 유지, 정보 하단의 카드 범위 포함, 상세 펼침 재맞춤·viewport 축소/복원을 검사했다. 도넛이 있으면 포커스 툴팁/Enter가 카드 넘김을 일으키지 않는지 확인했다.
- 390×844에서 실제 청둥오리/흰뺨검둥오리와 자료 없음/부분 자료 모두 카드350×795.99px로 같았다.320×568은280×520px, 가로844×390은179.85×334px로 전체를 표시했다. 가로 화면에서는 글씨도 작아진다는 한계를 아래에 기록한다.
- [별도 모의 자료 native pinch 검사](assets/2026-10-09-RG015-no-scroll-pinch-local-browser.json): 브라우저 확대1→1.5000002, fit scale0.8333333 유지, 앞면 유지. 실제 DB/API 성공으로 합산하지 않는다.

초기 새 구현의 실제 사진 swipe는 브라우저 pointercancel로 실패했고 위의 사진 스크롤 컨테이너 정책 수정 후 통과했다. 상세 펼침 검사에서 Playwright boundingBox에는 bottom 필드가 없는데 사용한 검증기 오류도 발견했다. y+height로 정정했으며 이 오류 때문에 앱 코드를 수정하지 않았다. CDP에는 deviceMetrics·screenOrientation을 명시해 세로/가로 실제 compositor 좌표를 맞춘다.

## 구현 커밋·NAS TEST 배포

구현 커밋 `198ebca821917258df5d8e4f8ed29b4a16f1fcfa`를 origin/dev에 push했다. 패키지 SHA256은 `823f9caa5a3ba33903d12ff12d034a6c4250a0e8b0b285697a79d8a06383f5e1`이다. 원격 archive SHA256과 MANIFEST를 검증하고 이전 TEST 환경파일을0600으로 재사용했다. 이미지와 VCS ref만 변경했으며 deploy_nas.sh deploy/verify exit0이다. 컨테이너 robingraph-api-test는 running/healthy, OCI revision은 구현 전체 커밋과 일치하고 API health는 status=ok/mode=neo4j/deployment_target=test다. 이미지 `robingraph-api:test-rg015noscroll-198ebca`, 릴리스 `/home/kimdove/RobinGraph-rg015noscroll-198ebca`다. 이전 `robingraph-api:test-rg015mobilefit-7627d51`은 보존했다. PROD는 배포하지 않았다. [배포 증거](assets/2026-10-09-RG015-no-scroll-deployment.json).

## 배포 자산 최종 브라우저 검증

실제 NAS TEST에서 제공하는 JS/CSS로 동일한 **9설정 모두 통과**했다. 실제 API/DB7·모의 API2의 구분은 로컬 검사와 같다. 공개 자산은 모든 설정에서 저장소 파일과 바이트 단위로 일치하고 health status=ok였다. 양면/사진/본문 넘김·무스크롤·화면 안 프레임·resize·상세 토글·차트 조작·닫기/재열기·pageerror0을 확인했다. [배포 서버 결과](assets/2026-10-09-RG015-no-scroll-browser.json).

[320px 앞면](assets/2026-10-09-RG015-no-scroll-mallard-front-320x568.png)과 [390px 뒷면](assets/2026-10-09-RG015-no-scroll-mallard-back-390x844.png)을 직접 열어 카드 전체·닫기·관찰 포인트·도넛·상세 토글의 포함을 확인했다. 실제 화면에 사진이 표시된 사례가 있으나 외부 사진 전송 성공 전체를 검증한 것으로 기록하지 않는다.

## 한계와 후속 사항

높이가 매우 짧거나 내용이 길면 전체 정보가 들어가도록 글씨도 비례 축소된다. 상세 설명은 카드 밖 대화에서도 읽을 수 있다. 모든 내용을 큰 글씨로 유지하면서 스크롤 없이 작은 화면에 넣는 정책은 아니다. 실제 사진의 외부 전송 성공 전체·물리 휴대폰·Safari/WebKit·실제 노치와 주소창 이동은 검증 범위에 포함하지 않는다. 이 변경은 JS/CSS 카드 동작이므로 Python 전체 DB 회귀를 새로 실행하지 않는다. 인증 정보는 문서에 기록하지 않는다.

이번 작업의 SSH master를 종료했고 남은 headless Chrome은0개다. 구현과 검증 문서는 별도 커밋으로 origin/dev에 저장한다. Obsidian 상세·백로그·프로젝트 index에 같은 구현·검증·배포 결과를 반영하며, 기존 완료 이력과 신규 대기2건·최후순위 보류4건은 보존한다.

Obsidian 저장 후 다시 읽어 상세 본문·백로그·index의 계획한 내용 일치, RG 상세17개 중복 없음, 목차 내부 링크 누락0, 신규 대기/최후순위 보류6개 상세 불변을 확인했다. 저장소 증거 링크의 실제 파일 존재도 검증한다.
