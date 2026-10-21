# Antigravity 역할 수신 확인 및 도감·채팅 UI 현황 점검 — 2026-10-15

## 요청 배경과 목표

사용자 지시로 `AGENTS.md`에 추가된 2026-10-15 공통 에이전트 역할 지침을 수신하고, Antigravity(dev-agy) 담당 영역의 역할을 확인한 후 정적 자산과 기존 검증 기록에 대한 최초 UI 현황 점검을 수행한다.

이번 점검의 목표는 다음과 같다:
1. **역할 수신 확인**: Antigravity의 담당 영역(도감 카드 앞뒤 전환, 비교·관계 탐색, 사진·출처 표시, PC·모바일 레이아웃과 접근성) 및 협업 규칙(생물학적 판단·출처 자의적 생성 금지, API 계약 준수, 실기기 미검증 명시, 운영 배포 승인 원칙 준수)을 확립한다.
2. **UI 현황 및 위험 점검**: 카드 조작, 모바일, 접근성, 출처 표시의 4대 영역에서 위험과 검증 공백을 최대 3개 우선순위로 정리하고, 확인된 사실/재현된 결함과 추정(잠재적 위험)을 명확히 구분한다.
3. **무변경 원칙 준수**: 이번 지시에 따라 애플리케이션 코드 수정, DB 쓰기, 서비스 재시작, 배포, Git commit/push/병합을 일절 수행하지 않고 현황 보고서만 작성한다.

## 확인된 역할과 수신 확인

`AGENTS.md`의 `Antigravity — 도감·채팅 UI·사용성 (dev-agy)` 지침을 읽고 다음 내용을 확인했다:

- **담당 영역**:
  - 도감 카드 앞뒤 전환, 비교·관계 탐색, 사진·출처 표시, PC·모바일 레이아웃 및 접근성.
  - 주요 대상: `src/robingraph/api/static/`의 HTML(`index.html`, `birds.html`), JS(`chat.js`, `birds.js`), CSS(`styles.css`) 및 관련 프런트엔드 테스트(`tests/frontend/*.test.js`).
- **데이터 표현 원칙**:
  - 화면에서 보전 등급, 국명/학명, 자료 부족, 아종 참고 범위를 API 의미대로 정확히 표시하며 화면 편의를 위해 자의적 생물학적 판단이나 출처를 임의 생성하지 않는다.
- **검증 구분 원칙**:
  - 키보드, 드래그·스와이프, 작은 화면 넘침, 움직임 줄이기(prefers-reduced-motion)를 변경 시 확인하되, API 모의 검사(Mock DOM), 실제 TEST 브라우저 검사(Chrome/Playwright), 물리 모바일 기기 검사를 엄격히 구분하여 보고한다.
- **운영 배포 승인 준수**:
  - 사용자 명시 승인 전 Production 배포 및 운영 서비스/DB 변경을 금지한다.

## 확인한 원인과 근거 (UI 현황 분석)

정적 자산(`chat.js`, `styles.css`, `index.html`, `birds.html`, `birds.js`)과 프런트엔드 테스트 자산(`tests/frontend/*.test.js`), 최근 작업 기록(`2026-10-10-*`, `2026-10-14-*`)을 분석하여 도출한 현황과 근거는 다음과 같다:

1. **테스트 체계 현황**:
   - `node --test tests/frontend/birds_ui.test.js`: 3건 통과.
   - `node --test tests/frontend/chat_ui.test.js`: 300건 통과.
   - 총 303건의 프런트엔드 단위 테스트가 통과 상태이나, 이는 Node.js 기반 모의 DOM(`createFakeElement`, `vm.runInNewContext`) 검사로 실제 브라우저 레이아웃 엔진이나 물리 터치 기기의 거동을 온전히 반영하지 못함.
2. **최근 UI 수정 이력과 잔존 한계**:
   - 2026-10-10 카드 뒷면 토글 시 배율 고정(`collapsedFitHeight`) 및 카드 소재 반사 무늬 고정(`--species-card-material-canvas-height`) 작업이 완료되어 TEST 및 Production에 배포됨.
   - 이전 작업 문서(`2026-10-10-card-material-toggle-stability.md`, `2026-10-10-card-toggle-stable-scale.md`)에 명시된 바와 같이, 모바일 검증은 Chrome CDP 에뮬레이션에 국한되었으며 실제 iPhone/Android, Safari, Firefox 실행 검증은 수행된 적이 없음.

## 담당 영역 현황 점검: 3대 우선순위 위험 및 검증 공백

### 우선순위 1: 모바일 실기기(iOS Safari/Android Chrome) 환경의 팝업 뷰포트 맞춤(`fitCard`) 및 제스처 레이아웃 검증 공백
- **대상 파일**:
  - `src/robingraph/api/static/chat.js` (lines 3857-3932 `fitCard`, `mobileFit`, lines 3354-3456 pointer/drag 핸들러)
  - `src/robingraph/api/static/styles.css` (lines 942-950 `.species-popup`, `100dvh` 선언)
- **대상 동작**:
  - 작은 모바일 화면에서 도감 팝업(`dialog`)이 열릴 때 뷰포트 비율에 맞춰 축소(`scale`)하고 카드 전체를 한 화면에 표시하는 동작.
  - 모바일 가상 키보드 활성화/비활성화, 주소창 스크롤(동적 툴바 표시/숨김), 화면 회전(가로/세로), 핀치 줌 시 `visualViewport` 이벤트에 따른 안정적 재맞춤.
  - 카드 좌우 터치 스와이프(뒤집기)와 카드 내부 세로 스크롤(상세 정보 펼침 시 `data-fit-scroll="true"`) 간의 제스처 충돌 방지.
- **확인된 근거**:
  1. 기존 작업 문서 및 `AGENTS.md` 76행: 물리 모바일·Safari·Firefox 환경 검증은 수행되지 않은 상태로 후속 과제로 남아 있음.
  2. `chat.js`의 `fitCard`는 `dialog.style.width = ""`로 초기화한 후 `fitFrame.clientWidth`를 재측정하고 `dialog.style.width = (naturalWidth * scale + chrome) + "px"`를 적용함. 실제 iOS Safari에서는 `100dvh`와 동적 주소창 변화가 `ResizeObserver` 및 `visualViewport.resize`와 맞물려 미세 리플로우나 무한 루프(레이아웃 스래싱)를 유발할 수 있는 구조적 위험이 있음.
- **추정과 재현된 결함 구분**:
  - **추정 (잠재적 위험 / 검증 공백)**: 실제 모바일 기기의 동적 툴바 및 가상 키보드 반응 시 레이아웃 진동이나 프레임 오버플로우 가능성은 구조 분석에 기반한 "추정"이며, 현재 에뮬레이션 환경에서는 재현되지 않음.
  - **재현된 결함**: 현재 기준 재현된 버그는 없음 (실기기 검증이 전무한 공백 상태).
- **권장 검증**:
  - 물리 iOS 기기(Safari) 및 Android 기기(Chrome)에서 실제 TEST 환경(https://robingraph-test.dove-nest.com/chat)에 접속하여 실측:
    1. 도감 카드 팝업 상태에서 스크롤에 따른 동적 URL바 출현/소멸 시 카드 크기 유지 및 여백 안정성 확인.
    2. 질문 입력창 터치로 가상 키보드가 팝업된 상태에서 모달 다이얼로그의 위치 및 닫기 버튼 접근성 확인.
    3. 상세 토글을 연 상태에서 세로 스크롤과 가로 스와이프 간의 터치 간섭 여부 실기기 확인.

---

### 우선순위 2: 카드 플립(앞/뒷면 전환) 시 키보드 접근성 및 포커스 유실(Focus Drop) 위험
- **대상 파일**:
  - `src/robingraph/api/static/chat.js` (lines 3079-3095 `showFace`, lines 3265-3270 keydown 핸들러)
  - `src/robingraph/api/static/styles.css`
- **대상 동작**:
  - 키보드 탐색 사용자(Tab 키)가 카드를 포커스한 후 Enter 또는 Space 키로 카드를 뒤집을 때, 또는 뒷면의 상세 토글/링크를 탐색한 후 다시 카드를 뒤집을 때의 포커스 유지 및 이전.
  - 스크린 리더(VoiceOver, TalkBack, NVDA) 사용자가 카드를 뒤집었을 때 활성 면의 정보를 즉시 탐색할 수 있도록 보장하는 포커스 흐름.
- **확인된 근거**:
  1. `chat.js`의 `showFace(showBack)` 실행 시 비활성 면에 대해 `front.inert = !!showBack; back.inert = !showBack;`, `front.hidden = showBack; back.hidden = !showBack;` 속성이 토글됨.
  2. W3C HTML 및 WAI-ARIA 명세에 따르면, 포커스를 가진 요소나 그 상위 요소가 `inert` 또는 `hidden` 처리되면 브라우저는 포커스를 강제로 `document.body`(또는 다이얼로그 루트)로 리셋함.
  3. 현재 코드상 `showFace` 내부에 포커스를 새로 표시되는 면(`front` 또는 `back`, 또는 상위 `card`)으로 명시적으로 이동(`focus()`)시키는 로직이 없음.
  4. `tests/frontend/chat_ui.test.js`의 테스트(5505행)는 순수 가상 DOM 이벤트 디스패치만 검사할 뿐 브라우저 네이티브의 inert/hidden 시 blur 동작을 모의하지 못함.
- **추정과 재현된 결함 구분**:
  - **추정 (잠재적 접근성 결함)**: 뒷면의 토글/링크를 탐색하던 키보드 사용자가 카드를 앞면으로 뒤집을 때 포커스가 페이지 최상단(body)으로 날아가 탭 순서를 처음부터 다시 탐색해야 하는 포커스 유실 위험은 브라우저 표준 명세 분석에 기반한 "추정"임.
  - **재현된 결함**: 단위 테스트에서는 failure가 발생하지 않음(가상 DOM 환경의 한계). 실제 브라우저 키보드 탭 순서 인터랙션 검증을 통해 포커스 잔류 여부를 실측해야 함.
- **권장 검증**:
  - 실제 데스크톱 브라우저(macOS Safari, Chrome)에서 마우스 없이 Tab/Shift+Tab 키로만 조작:
    1. 질문 제출 -> 답변 카드 포커스 -> Enter 플립 -> 포커스가 뒷면 내부로 자연스럽게 이동하는지 확인.
    2. 뒷면 `summary`(측정값 더 보기) 포커스 상태에서 카드를 다시 앞면으로 뒤집었을 때 포커스가 `card`로 유지되는지 확인.
    3. macOS VoiceOver 환경에서 카드 플립 시 `aria-label` 갱신 문구가 정상 낭독되는지 확인.

---

### 우선순위 3: 출처 표시·보전 등급 렌더링 계약 안정성 및 `index.html` 표기 잔존 불일치
- **대상 파일**:
  - `src/robingraph/api/static/chat.js` (lines 1059-1148 `conservationInfo`, `birdbaseReferenceInfo`, lines 1370-1440 `buildCombinedAnswerSources`)
  - `src/robingraph/api/static/index.html` (lines 116-121 disclaimer)
  - `src/robingraph/api/static/birds.html` / `birds.js`
- **대상 동작**:
  - 보전 등급(IUCN Red List / BIRDBASE 2024 / 까치 매뉴얼 오버라이드) 배지 표시 및 출처 연결.
  - 아종(subspecies)과 모종(species)의 형질 데이터 혼동 방지 및 "추정값", "자료 부족", "비율 자료 없음" 안내 표기.
  - `index.html`의 안내 문구 및 레거시 `birds.html` 간의 UI/표현 일관성.
- **확인된 근거**:
  1. `chat.js`의 보전 등급 로직은 데이터 무결성을 위해 매우 엄격한 하드코딩 핀(SHA-256 해시, 특정 행 번호, 특정 릴리스 문자열 등)을 검증함. 만약 백엔드(Claude 담당)에서 데이터셋을 갱신하거나 응답 스키마를 미세 변경하면 프런트엔드에서 즉시 `null`을 반환하고 `unconfirmed`로 fallback됨. 이는 에이전트 간 API 계약 조율이 필수적인 결합 지점임.
  2. `docs/work-log/2026-10-14-service-domain-cleanup.md`에서는 "채팅 주소의 테스트 UI 표기는 채팅 UI로 수정했다"고 기록되어 있으나, `src/robingraph/api/static/index.html` 117행에는 여전히 `<p id="app-disclaimer" class="disclaimer">이 화면은 수동 검증용 테스트 UI입니다...</p>` 문구가 남아 있음(`git grep` 확인).
  3. `birds.html`과 `birds.js`는 초기 프로토타입 형태의 단순 테이블 레이아웃을 유지하고 있어, 현재 메인인 `index.html` + `chat.js`의 카드 시스템(3D 회전, 위험 등급 팔레트, 종합 출처 패널, 아종 주의 문구)과 동기화되어 있지 않음.
- **추정과 재현된 결함 구분**:
  - **재현된 결함 / 확인된 코드 불일치**: `src/robingraph/api/static/index.html` 117행에 "수동 검증용 테스트 UI" 문구가 실제로 남아 있음(코드 검색으로 100% 확인).
  - **추정 (협업 위험)**: 백엔드의 보전/형질 데이터 릴리스 업데이트 시 UI 렌더러가 엄격한 해시 검증 불일치로 보전 등급을 유실할 위험은 "추정(잠재적 변경 취약점)"임.
- **권장 검증**:
  - 프런트엔드-백엔드 통합 API 검증: 백엔드에서 반환하는 실제 프로필 payload(원앙, 까치, 청둥오리 등)를 mock 없이 주입했을 때 보전 등급 및 출처 아코디언이 누락 없이 정상 렌더링되는지 확인.
  - `index.html` 117행 문구를 서비스 환경에 맞게 정리하는 최소 변경 검토 (향후 작업 지시 시).
  - `birds.html`의 유지 필요성 또는 채팅 UI(`/chat`)로의 일원화 방안을 Codex와 협의.

## 변경 전후 동작 및 파일 변경

- **변경 전후 동작**: 해당 없음. 이번 지시는 역할 정립과 현황 점검으로 새로운 기능 구현, 기존 코드 수정, 서비스 재시작, 배포, DB 쓰기를 일절 수행하지 않는다.
- **변경 파일과 구현 내용**:
  - 신규 작성: `docs/work-log/2026-10-15-antigravity-baseline.md` (본 작업 보고 문서).
  - 앱 소스 코드(`src/robingraph/api/static/*`) 및 테스트 코드는 변경하지 않음.

## 검증 방법과 실제 결과

- **실제 실행한 테스트 범위**:
  - `node --test tests/frontend/birds_ui.test.js`: 3 통과, 0 실패, 0 취소, 0 건너뜀 (63.4ms).
  - `node --test tests/frontend/chat_ui.test.js`: 300 통과, 0 실패, 0 취소, 0 건너뜀 (263.4ms).
  - 총합 303건 통과.
- **검증 성격 구분**:
  - 위 테스트는 Node.js 내장 테스트 러너 기반의 단위/모의(Mock DOM) 검증이며, 실제 DB/API 또는 실제 브라우저(렌더링 엔진) 검증이 아님.
  - 실제 DB 쓰기, 외부 API 호출, 신규 브라우저 자동화 검사는 실행하지 않음.
- **정적 파일 정합성 확인**:
  - `git grep -n "테스트 UI"` 실행으로 `src/robingraph/api/static/index.html:117` 잔존 확인.
  - `git status`를 확인하여 워크트리 변경이 본 보고 문서 작성 외에 없음을 확인.

## 배포·커밋 정보

- **커밋 및 push**: 수행하지 않음 (지침 준수).
- **TEST / Production 배포**: 수행하지 않음.
- **운영 배포 승인 원칙 준수**: 사용자의 명시적 승인 전까지 운영 환경에 대한 어떠한 배포나 컨테이너 재시작, DB 변경도 수행하지 않는다.

## 남은 한계와 후속 사항

1. **실기기 미검증**: iOS Safari 및 Android 실기기에서의 터치 제스처, 동적 툴바, 가상 키보드 반응 검증이 남아 있음.
2. **보조공학 실측 필요**: 스크린 리더(VoiceOver) 및 키보드 전용 환경에서 포커스 유실 여부 실측 필요.
3. **후속 작업 제안**:
   - `index.html`의 "수동 검증용 테스트 UI" 문구 정리 (Codex 협의 후 최소 변경).
   - 키보드 플립 시 포커스를 활성 면으로 명시적 이동시키는 보완책 검토.
   - Claude의 백엔드 스키마 점검 결과와 연계하여 보전 등급 및 출처 표시 계약 일치 확인.
