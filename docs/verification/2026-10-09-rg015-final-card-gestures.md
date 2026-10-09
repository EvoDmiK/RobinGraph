# RG-405 최종 마무리 — 도넛 클릭 해제·카드 전체 영역 넘기기

- 작업일: 2026-10-09
- 사용자 요청: 뒷면 도넛 차트를 클릭되지 않게 만들고 모든 카드 영역에서 넘길 수 있게 한다. 이번 범위까지 처리하면 RG-405를 마무리한다.

## 배경·원인·완료 범위

기존 도넛은 각 조각을 버튼으로 노출하고 클릭·터치·키보드 활성화로 툴팁을 표시했다. 차트 전체에는 data-card-drag-exempt가 있었고 카드의 isDragExempt는 button·a·summary 및 button/link 역할을 넘기기 대상에서 제외했다. 이 때문에 뒷면에서 차트나 항목·비율 토글 위로 시작한 드래그는 카드 넘김으로 이어지지 않았다.

이번 수정은 RG-405의 마지막 요청으로 처리한다. 도넛의 클릭·탭·키보드 활성화를 제거하고 카드 안의 차트·사진·텍스트·버튼·링크·토글에서 가로 드래그를 허용한다. 버튼과 토글의 일반 클릭·탭은 유지한다. PC의 마우스 호버 설명은 유지한다. 닫기 X는 카드 밖의 별도 조작이며 기존 닫기 동작을 유지한다. 텍스트 입력·편집, 미디어 조작, 명시적 draggable/drag-exempt 요소는 기존 고유 동작을 보존한다. 현재 카드의 정보 표면은 이 예외에 해당하지 않는다.

## 변경 파일과 구현

`src/robingraph/api/static/chat.js`에서 buildDistributionChart의 차트 drag-exempt와 조각의 role=button·tabindex·aria-describedby, focus·click·pointerdown·keydown 활성화 리스너를 제거했다. SVG는 role=img와 비율 목록 안내를 가진 정적 그림으로 노출한다. 기존 항목·비율 details의 텍스트 목록은 키보드로 접근 가능하다.

호버는 pointerenter 중 pointerType=mouse이고 버튼을 누르지 않을 때만 표시한다. 조상 카드가 드래그 중이거나 애니메이션 중이면 툴팁을 다시 띄우지 않는다. pointerleave·pointercancel·차트 또는 카드의 pointerdown에서 툴팁을 비운다. 터치가 만드는 호환 마우스 이벤트로 툴팁이 남는 동작을 방지한다.

isDragExempt에서 button·a·summary와 button/link 역할을 제외했다. 일반 pointerdown을 막지 않아 정상 클릭·탭은 네이티브 동작을 유지한다. 수평 드래그가 활성화되면 기존 pointer capture와 capture 단계 click 억제를 사용한다. 넘김을 확정하지 못한 짧은 드래그도 끝의 클릭으로 토글·사진 이동이 발생하지 않으며 다음 정상 누르기는 다시 동작한다. 숨긴 면의 inert·aria-hidden, 두 손가락 전환·pointercancel·lostpointercapture·핀치 처리와 내부 무스크롤/전체 화면 맞춤은 보존한다.

`src/robingraph/api/static/styles.css`에서는 차트와 조각의 커서를 카드에서 상속하고 마우스 호버 강조를 hover:hover/pointer:fine 환경에 한정했다. 버튼처럼 보이는 조각 커서와 불필요한 focus-visible 강조는 제거했다. 사진·앞면 배치와 양면 높이는 수정하지 않았다.

`tests/frontend/chat_ui.test.js`는 정적 차트 계약과 실제 이벤트 동작에 맞게 기존 검사를 수정하고 차트 모든 표면 넘김, 버튼·링크·summary 탭 및 드래그/짧은 복귀 후 클릭 억제 회귀를 추가했다.

## 협업·자동 검증

pc_drag_popup_fix가 JS/CSS 구현·회귀·graphify 갱신을 맡고 card_selection_review가 읽기 전용 독립 검토를 수행했다. root는 실제 Chrome 마우스/터치 검증·NAS TEST 배포·문서/Obsidian·Git을 맡았다. 독립 검토에서 변경이 필요한 차단 문제는 없었다. 검토자가 권장한 비활성 사진 이동 버튼 위 드래그도 별도 브라우저 모의 응답으로 확인했다.

- `node --test tests/frontend/*.test.js`: **246 통과·실패0·건너뛰기0·취소0**. [실행 로그](assets/2026-10-09-RG015-final-frontend-tests.txt).
- `node --check src/robingraph/api/static/chat.js`와 `git diff --check` 통과.
- `graphify update .`: AST15/15,3837 노드·8172 간선·223 커뮤니티로 갱신. SQL 의존성/무심볼 및 community label 안내는 기존 성격의 경고이며 AST 갱신을 막지 않았다. 의미 추출 API는 호출하지 않았다.

## 배포 전 실제 브라우저 검증

실제 NAS API/DB 응답과 로컬 새 JS/CSS를 결합한 Chrome 검증5설정, 자료 없음 모의 API1설정, 사진 컨트롤 모의 API2설정의 **총8설정이 통과**했다. 물리 휴대폰과 구분하여 모바일은 Chrome CDP 네이티브 터치 이벤트 에뮬레이션으로 실행했다.

| 검증 | 화면 | 데이터 |
|---|---|---|
|PC|1280×900|실제 청둥오리 API/DB|
|모바일 세로|390×844,375×667,320×568|실제 청둥오리 API/DB|
|모바일 가로|844×390|실제 청둥오리 API/DB|
|자료 없음|390×844|traits·sections·images가 없는 모의 응답|
|사진 버튼|1280×900,390×844|캐시된 종 응답에 사진2개를 넣은 모의 응답|

두 차트 각각의 조각·중앙·자료 라벨·항목·비율 summary·펼친 목록과 뒷면 다른 details summary에서 가로 드래그 후 앞면 전환을 확인했다. 드래그 전후 summary open 상태가 같아 의도하지 않은 토글이 없었다. 단순 summary 클릭/탭은 펼쳐졌으며 카드는 뒷면을 유지했다. PC 호버는 표시되고 누르는 즉시 사라졌으며 클릭 후 다시 활성화되지 않았다. 모바일 탭은 툴팁을 표시하거나 카드를 뒤집지 않았다.

별도 사진2개 모의 응답에서 활성 다음 버튼과 비활성 이전 버튼 위 드래그가 모두 카드를 뒤집었고 사진 번호는 유지됐다. 정상 다음 버튼 클릭/탭은 사진 번호를 바꾸고 카드는 앞면을 유지했다. 실제 API의 사진 제공 결과에 의존하지 않도록 모의 응답임을 분리한다. 초기 검증기는 뒤집힌 비표시 앞면의 innerText를 빈 문자열로 읽어 사진 변경으로 오판했다. photoCount.textContent로 수정 후 앱 변경 없이 PC/모바일 모두 재통과했다.

사진·본문 양면 넘김, 카드/닫기의 화면 포함, 양면 동일 높이, 모바일 세로 제스처 후 내부 스크롤0, 화면 resize, 상세 펼침 fit, 닫기/다시 열기와 pageerror0을 확인했다. 기존 앞면 관찰 포인트와 빈 간격 축소도 유지했다. [기본6설정](assets/2026-10-09-RG015-final-local-browser.json), [사진 컨트롤2설정](assets/2026-10-09-RG015-final-controls-local-browser.json).

## 커밋·NAS TEST 배포

구현 `217685fe7cd367ddbf04cf1f0a6234d4421e6dd9`를 origin/dev에 push했다. archive SHA256 `f8101a0f1b6f764f5782165113847501347520cf9410ab068db0a3a666c54585`와 원격 MANIFEST를 확인하고 기존 TEST 환경파일을0600으로 재사용했다. 이미지/VCS ref만 갱신했다. deploy_nas.sh deploy/verify는 exit0, 컨테이너는 running/healthy, OCI revision은 구현 전체 커밋과 같고 health=status ok/mode neo4j/deployment_target test다. Compose의 buildx 미설치 안내는 classic builder로 성공했다.

이미지 `robingraph-api:test-rg015final-217685f`, 릴리스 `/home/kimdove/RobinGraph-rg015final-217685f`. 이전 `robingraph-api:test-rg015frontfill-1d0647c`는 보존했다. PROD 배포는 수행하지 않았다. [배포 무결성·health](assets/2026-10-09-RG015-final-deployment.json).

## 배포 후 실제 브라우저 검증

배포된 JS/CSS로도 기본6설정과 사진 컨트롤2설정의 **총8설정 모두 통과**했다. 실제 API/DB5와 모의 응답3을 구분한다. 모든 설정에서 공개 JS/CSS 바이트가 로컬 구현과 같고 health=status ok였다. 두 차트 각각의 조각·중앙·라벨·목록·summary 넘김과 정상 탭, PC 호버/누름 해제·모바일 탭 비활성, 활성/비활성 사진 버튼 드래그 및 정상 사진 이동, 양면 fit·내부 무스크롤·resize·재열기·pageerror0을 다시 확인했다. 자료 없음은 차트가 생성되지 않는 상태에서도 카드 형식·넘김·fit을 유지했다. [기본6설정](assets/2026-10-09-RG015-final-browser.json), [사진 컨트롤2설정](assets/2026-10-09-RG015-final-controls-browser.json).

[390px 뒷면](assets/2026-10-09-RG015-final-mallard-back-390x844.png)을 직접 열어 두 차트와 카드/닫기의 화면 포함을 확인했다. 이벤트 변경으로 사진·관찰 포인트·뒷면 정보 배치는 유지한다.

## 한계·후속 작업

물리 휴대폰·Safari/WebKit·실제 노치/주소창 움직임·외부 이미지 전체와 DB 모든 종은 이번에 검증하지 않았다. CSS/브라우저 이벤트 수정이므로 Python 전체 DB 회귀는 새로 실행하지 않았다. 실제 API/DB 검증은 위의5설정이며 사진 컨트롤/자료 없음3설정을 실제 DB 검증으로 합산하지 않는다. 입력·편집·미디어/명시적 드래그 영역의 고유 동작은 의도적으로 보존한다. 인증 정보는 문서에 기록하지 않는다.

사용자가 정한 이번 범위까지 RG-405를 최종 완료로 관리한다. 새 요청이 없으면 RG-405 추가 변경에 착수하지 않는다. 신규 대기 RG-202·RG-406과 최후순위 보류 RG-102·RG-503·RG-504·RG-505의 상태는 유지한다.

이번 작업의 SSH master와 브라우저 검증 프로세스를 종료했다. 구현과 검증 문서는 별도 커밋으로 origin/dev에 저장한다. Obsidian 작업기록·백로그·작업기록 index에 같은 결과를 기록하고 저장 후 읽어 RG 상세17개·목차 대상 누락0·대기/보류6개 상세 불변을 확인한다.

Obsidian 상세·백로그·작업기록 index 저장 후 전체 읽기 일치를 확인했다. RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 불변이며, 저장소의 증거 링크는 모두 실제 파일을 가리킨다.
