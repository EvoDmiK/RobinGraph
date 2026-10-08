# RG-015 후속 — 카드 정보의 글씨 선택 차단

작업일: 2026-10-08 KST. 구현 커밋: `570fd3fb386f412eacbd4c150ffe5b7541dd25c4`.

## 요청 배경과 목표

사용자가 카드 정보의 글씨를 드래그해 선택하지 못하게 요청했다. 카드 앞·뒷면과 중첩 출처 설명 전체에서 일반적인 마우스 드래그·더블클릭 선택을 차단하고 카드 넘기기·출처 펼치기·링크 포커스·입력창 선택을 유지하는 것이 목표다.

## 확인한 원인과 변경 전후

기존에는 실제 카드 드래그가 시작된 동안에만 `user-select:none`이 적용됐다. 평소 카드 제목과 설명은 브라우저 기본 정책에 따라 선택할 수 있었다. 이제 `.species-card, .species-card *`에 `user-select:none`과 `-webkit-user-select:none`을 상시 적용한다. 카드 밖의 채팅과 입력창에는 이 규칙을 적용하지 않는다.

카드 마우스 드래그의 시작 범위와 터치 스와이프·버튼 이벤트는 변경하지 않았다. 마우스 글씨 영역에서 새로 카드 회전을 시작하도록 확장하지 않았다. `pointer-events`나 `touch-action`·링크 이벤트를 차단하지 않았으며 `pan-y pinch-zoom`을 유지했다. `-webkit-touch-callout`·contextmenu·copy 차단은 추가하지 않았다.

## 변경 파일과 협업

- `src/robingraph/api/static/styles.css`: 카드와 모든 자식의 글씨 선택 차단 규칙 5줄 추가.
- `src/robingraph/api/static/chat.js`: 기존 ‘마우스 텍스트 선택을 보장한다’는 주석을 새 CSS 정책에 맞게 정정. 실행 로직 변경 없음.
- 이 문서와 `docs/verification/assets/2026-10-08-RG015-noselect-*.json`: 로컬 자산/실제 배포 자산의 검증 결과를 구분해 기록.
- 협업 에이전트 `card_selection_review`는 읽기 전용으로 카드 구조와 선택·입력 이벤트 범위를 검토했다. 앞·뒷면·summary·중첩 출처가 모두 적용 범위이고 버튼·링크·스크롤 정책의 변경이 없음을 확인했다. 구현·NAS·최종 브라우저 검증·문서·Git은 root가 수행했다.

## 검증 방법과 실제 결과

- `node --check src/robingraph/api/static/chat.js`: 통과.
- `node --test tests/frontend/*.test.js`: **203 통과, 0 실패, 0 건너뜀**. 기존 모의 DOM 회귀 검사이며 새 CSS 규칙을 그대로 복제하는 테스트는 추가하지 않았다.
- Python·전체 DB 회귀는 CSS와 주석 변경에 해당하지 않아 재실행하지 않았다. 브라우저의 실제 NAS `/v1/chat`·DB 응답을 사용한 검사는 전체 DB 회귀와 구분한다.
- 배포 전 로컬 JS/CSS 대체 검증: Chrome 1280px 마우스, 390px Pixel 7 터치 일반/reduced-motion **3설정 통과**, runner exit 0. [로컬 자산 결과](assets/2026-10-08-RG015-noselect-local-browser.json).
- 배포 후 서버 자산 검증: 같은 **3설정 통과**, runner exit 0. 로컬 route 대체·API mock 없이 실제 NAS TEST 파일·API/DB 응답으로 실행했다. [실제 서버 브라우저 결과](assets/2026-10-08-RG015-noselect-browser.json).

두 실행 모두 카드의 모든 자식 computed user-select=none, 앞·뒷면 마우스 드래그·더블클릭 후 selection 빈 문자열, 출처 details 펼침·출처 링크 키보드 포커스, Enter/Space·카드 좌우 드래그/스와이프·닫기/재열기를 확인했다. 일반 motion에서는 유광 반사광이 나타났고 reduced-motion에서는 기존 즉시 전환을 유지했다. 모바일 CDP touch 세로 스크롤은 배포 후 scrollTop 0→111/108로 증가했고 입력창 선택이 유지됐으며 pageerror는 0이다. WebKit용 속성은 추가했으나 Safari 실기 검증은 하지 않았다.

초기 검증기는 Enter 뒤 disabled 전환으로 포커스를 잃은 버튼에 Space를 보내고, Escape로 닫은 후 `dialog[open]` locator에서 CSS를 읽어 timeout이 발생했다. 각 키 전 재포커스와 닫기 전 CSS 저장으로 검증기만 수정했다. 협업 에이전트도 1280px의 앞/뒷면·키보드·마우스 회전·재열기 단계 통과와 닫힌 locator 문제를 확인했다. 최종 재실행은 통과했으며 초기 timeout을 제품 결함 또는 통과 검사로 계산하지 않는다.

## 배포·Git·그래프

구현 커밋은 `origin/dev` push 완료. 소스 패키지 SHA256은 `aa208c6d9d8fb496fd882c12578a05f230e613296a14fda5e04c4f841f725bbe`다. 인증 정보는 문서에 포함하지 않는다.

NAS TEST 이미지 `robingraph-api:test-rg015noselect-570fd3f`, 릴리스 `/home/kimdove/RobinGraph-rg015noselect-570fd3f`를 배포했다. 원격 패키지 SHA256·MANIFEST 검증과 `deploy_nas.sh deploy`·`verify`가 통과했다. 컨테이너 `robingraph-api-test`는 healthy, 이미지 OCI revision은 구현 전체 커밋과 일치한다. 공개 `/health`는 status=ok·mode=neo4j·deployment_target=test이다. 실제 브라우저 fetch로 공개 JS/CSS와 로컬 구현 파일의 바이트 일치를 확인했다. [배포·자산 증거](assets/2026-10-08-RG015-noselect-deployment.json). 이전 `robingraph-api:test-rg015gloss-f8a3771`과 릴리스는 롤백용으로 보존했으며 PROD는 변경하지 않았다.

`graphify update .` AST 갱신을 수행했다. 최초 갱신은 3,694 nodes·7,976 edges·209 communities였고 주석 정정 후 재실행은 코드 그래프 위상 변경 없음으로 끝났다. 기존 SQL 파서 미설치·커뮤니티 라벨 경고는 남았으며 의미 추출 API를 호출하지 않았다. 그래프 생성물은 저장소의 기존 추적 정책을 따른다.

## 한계와 후속 사항

이 변경은 일반 브라우저에서의 글씨 드래그 선택 방지다. 프로그램으로 DOM을 읽는 수집이나 개발자 도구·스크린샷을 차단하는 기능은 아니다. 물리 Android·iPhone/iPad·Safari/WebKit·Firefox·스크린 리더는 미검증이다. 이번 변경에서는 native pinch 확대·외부 사진 로딩·외부 출처 페이지 이동을 재검증하지 않았으며 기존 구현을 변경하지 않았다.

Obsidian의 RG-015 상세와 프로젝트 index에 같은 구현·검증·배포 결과를 연결한다. 대기·보류 작업을 재개하지 않는다.
