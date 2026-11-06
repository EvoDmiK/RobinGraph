# TEST 실제 브라우저 검증 보고서 (`dev-agy` / `task_05263f4aa88e`)

## 1. 검증 환경 및 개요
- **검증 일시:** 2026-10-28 (KST)
- **대상 URL:** `https://robingraph-test.dove-nest.com/chat` (실제 API 호출, 모의 API / 네트워크 인터셉트 미사용)
- **TEST 배포 스냅샷:**
  - 이미지: `robingraph-api:test-followup-69b19f6f5fed` (`linux/arm64`)
  - 릴리스: `/Users/kimdove/robingraph-test/releases/followup-69b19f6f5fed-f80a69` (`current` 심볼릭 링크 반영)
  - 정적 자산 해시: `chat.js` `ff13a283` (`dev-codex` 및 `main` 동일본)
  - 백엔드 헬스 상태: `neo4j (그래프 DB · 근거 기반 답변)`
- **브라우저 설정:**
  - Chromium (`chrome-headless-shell` 1248, macOS ARM64)
  - `--incognito --disable-application-cache --disk-cache-size=0` 및 CDP `Network.setCacheDisabled({ cacheDisabled: true })`
  - 제출 방식: 실제 키보드 `Enter` 이벤트(`Input.dispatchKeyEvent`)
  - 보안: 요청/응답의 `followup_context` 원문 토큰 및 `X-RobinGraph-Feedback-Token` 등 비밀값은 로그·보고서·스크린샷에 노출하지 않고 존재 여부 및 길이(`has_followup_context`, `followup_context_len`)만 검증함.

---

## 2. 핵심 연속 질의 검증 (`390x844` 모바일 & `1280x800` 데스크톱)

두 뷰포트(`390x844` `mobile: true` 및 `1280x800` `mobile: false`) 모두에서 동일한 4단계 연속 질의를 실제 API로 수행하여 동일하게 통과함을 확인했습니다.

| 단계 | 입력 질문 | 요청 페이로드 (`POST /chat`) | 응답 상태 / 조건 카드 (`.graph-query-conditions`) | 입력창 상단 `#followup-context-bar` | 관련 종 / 본문 결과 | 레이아웃 / 포커스 / 피드백 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1단계 (초기 질의)** | `숲에 사는 열매 먹는 새` | `intent: "auto"`, `species_scope: "all"`, `has_followup_context: false`, `has_items_field: false` | `답변` 배지 · `data-followup-status="initial"`<br>- **적용 조건**: `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함"]` | 표시됨 (`hidden: false`)<br>`현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함` | `관련 종 · 20종 이상` (`가면매`, `갈색지빠귀`, `검은다리솔새`, `검은등뻐꾸기`, `검은지빠귀` 등) | `horizontalOverflow: false`, `barFitsViewport: true`, `boxFitsViewport: true`, 포커스 `#question-input` 복귀, 피드백 버튼 3종 표시 |
| **2단계 (국내 조건 후속)** | `그중 한국에서 볼 수 있는 새는?` | `intent: "auto"`, `species_scope: "all"`, `has_followup_context: true` (len `314`), `has_items_field: false` | `답변` 배지 · `data-followup-status="applied"`<br>- **적용 조건** (`추가 조건: 국내 기록`): `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "국내 기록"]` | 표시됨 (`hidden: false`)<br>`현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 국내 기록` | `관련 종 · 20종 이상` (`갈색지빠귀`, `검은다리솔새`, `검은등뻐꾸기`, `검은지빠귀`, `굴뚝새` 등) | `horizontalOverflow: false`, `barFitsViewport: true`, `boxFitsViewport: true`, 포커스 `#question-input` 복귀, 피드백 버튼 3종 표시 |
| **3단계 (`empty` 결과 없음 보류)** | `그중 체중 5000g 이상인 새는?` | `intent: "auto"`, `species_scope: "all"`, `has_followup_context: true` (len `318`), `has_items_field: false` | `보류 (근거 부족)` 배지 · `data-followup-status="applied"`<br>- **그룹 1 (`이번 조회 조건`, `추가 조건: 체중 5000g 이상`)**: `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "체중 5000g 이상", "국내 기록"]`<br>- **그룹 2 (`다음 질문 유지 조건`)**: `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "국내 기록"]` (`체중 5000g 이상` 제외) | 표시됨 (`hidden: false`)<br>`유지된 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 국내 기록` (`체중 5000g 이상` 미포함) | `전체 조류 범위에서 조건 자료가 모두 있는 410종 중 조건(서식 환경 숲(Forest), 먹이 구성에 열매 포함, 체중 5000g 이상)에 맞는 종을 찾지 못했습니다.` | `horizontalOverflow: false`, `barFitsViewport: true`, `boxFitsViewport: true`, 포커스 `#question-input` 복귀, 피드백 버튼 3종 표시 |
| **4단계 (유지 토큰 기반 수치 재질의)** | `그중 체중 100g 이상인 새는?` | `intent: "auto"`, `species_scope: "all"`, `has_followup_context: true` (len `318`, 2단계 유지 토큰 그대로 전송), `has_items_field: false` | `답변` 배지 · `data-followup-status="applied"`<br>- **적용 조건** (`추가 조건: 체중 100g 이상`): `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "체중 100g 이상", "국내 기록"]` | 표시됨 (`hidden: false`)<br>`현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 체중 100g 이상 · 국내 기록` | `관련 종 · 10종` (`녹색비둘기`, `대륙점지빠귀`, `멧도요`, `뻐꾸기`, `어치` 등) | `horizontalOverflow: false`, `barFitsViewport: true`, `boxFitsViewport: true`, 포커스 `#question-input` 복귀, 피드백 버튼 3종 표시 |

---

## 3. 회귀 및 경계 동작 검증 (`1280x800` 데스크톱)

1. **`route_conflict` (타 조회 유형 선택 시 후속 질문 충돌 안내 및 토큰 보존)**
   - **조작:** 4단계 직후 `#chat-intent`를 `"taxonomy"`(`분류·하위군`)로 변경하고 `그중 한국에서 볼 수 있는 새는?`을 키보드 `Enter`로 제출.
   - **실제 결과:**
     - 배지: `추가 확인 필요` (`abstain_type: "clarify"`)
     - 안내 문구: `이전 조건 조회를 이어가려면 개별 종 필터나 다른 조회 유형을 비우고 다시 질문해 주세요. 유지한 조건: 서식 환경 숲(Forest), 먹이 구성에 열매 포함, 체중 100g 이상, 국내 기록.`
     - 카드 상태: `.graph-query-conditions[data-followup-status="rejected"]`, `유지된 조건`: `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "체중 100g 이상", "국내 기록"]`
     - 하단 상태바: `#followup-context-bar` 숨겨지지 않고 유지됨 (`유지된 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 체중 100g 이상 · 국내 기록`).
2. **새 주제 전환 (`청둥오리에 대해 알려줘`)**
   - **조작:** `#chat-intent`를 `"auto"`로 복원한 뒤 `청둥오리에 대해 알려줘` 제출.
   - **실제 결과:** `청둥오리 Mallard (Anas platyrhynchos)` 종 프로필 카드 및 근거 기반 답변이 렌더링되고, 이전 조건 조회 맥락이 해제되어 `#followup-context-bar`가 즉시 숨김 처리됨 (`hidden: true`, `textContent: ""`).
3. **`대화 지우기` (`#clear-button`)**
   - **조작:** `숲에 사는 열매 먹는 새` 조회로 `#followup-context-bar`가 표시된 상태에서 `#clear-button` 클릭.
   - **실제 결과:** `#history` 내 메시지 0건(`emptyStateVisible: true`), `#followup-context-bar` 숨김(`hidden: true`, `textContent: ""`), `#status-text`에 `"대화 기록을 지웠습니다."` 안내 표시.
4. **분포 범위(`species_scope`) 변경 시 맥락 초기화 및 `국외 분포` 후속 질의**
   - **조작:** `숲에 사는 열매 먹는 새` 조회 후 `#species-scope-outside`(`국외 분포 검토`) 라디오 선택 -> 이어서 `숲에 사는 새` -> `그중 열매를 먹는 새는?` 순서로 연속 질의.
   - **실제 결과:**
     - `#species-scope-outside` 전환 즉시 `#followup-context-bar`가 숨김 처리되고(`afterScopeBarHidden: true`, `afterScopeBarText: ""`), `#status-text`에 `"분포 범위 기준을 ‘국외 분포 검토’(으)로 변경했습니다. 입력 중인 질문은 유지됩니다."` 표시.
     - `숲에 사는 새` (`species_scope: "outside"`, `has_followup_context: false`): `관련 종 · 3종` (`North Island Brown Kiwi`, `North Island Kokako`, `Okarito Kiwi`), 조건 칩 `["서식 환경 숲(Forest)", "국외 분포"]`.
     - `그중 열매를 먹는 새는?` (`species_scope: "outside"`, `has_followup_context: true`): `관련 종 · 1종` (`North Island Brown Kiwi`), 조건 카드(`추가 조건: 먹이 구성에 열매 포함`) 및 `#followup-context-bar`에 `["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "국외 분포"]` 정상 표시.
5. **RG603 피드백 버튼 공존 및 반응형/접근성**
   - 모든 응답 버블(일반 답변, `empty` 보류, `route_conflict` 추가 확인 필요, 종 상세 안내) 하단에 `["도움됐어요", "질문을 잘못 이해했어요", "답변이 틀렸어요"]` 피드백 버튼 3종이 정상 렌더링됨.
   - `390x844` 및 `1280x800` 모든 단계에서 가로 넘침 없음(`documentElement.scrollWidth <= clientWidth`), `.graph-query-conditions` 및 `#followup-context-bar`가 뷰포트 폭 내부에 완전히 수납됨(`barFitsViewport: true`, `boxFitsViewport: true`), 칩 줄바꿈(`flex-wrap: wrap`) 정상 동작.

---

## 4. 증적 파일 경로
- **구조화 검증 결과 JSON:** `./browser-verification-results.json`
- **검증 스크립트:** `/tmp/robingraph-followup-20261028/run-test-browser.cjs` (실행 원본)
- **스크린샷 (`./screenshots/`):**
  - 모바일 (`390x844`):
    - `./screenshots/mobile_390x844-1-initial.png`
    - `./screenshots/mobile_390x844-2-korea.png`
    - `./screenshots/mobile_390x844-3-empty-5000g.png` (답변 하단 + 피드백 버튼 + 하단 `#followup-context-bar`)
    - `./screenshots/mobile_390x844-3-empty-5000g-conditions.png` (`.graph-query-conditions` `이번 조회 조건` / `다음 질문 유지 조건` 2그룹 카드 + 하단 `#followup-context-bar` 동시 노출)
    - `./screenshots/mobile_390x844-4-numeric-100g.png`
  - 데스크톱 (`1280x800`):
    - `./screenshots/desktop_1280x800-1-initial.png`
    - `./screenshots/desktop_1280x800-2-korea.png`
    - `./screenshots/desktop_1280x800-3-empty-5000g.png` (답변 하단 + 피드백 버튼 + 하단 `#followup-context-bar`)
    - `./screenshots/desktop_1280x800-3-empty-5000g-conditions.png` (`.graph-query-conditions` `이번 조회 조건` / `다음 질문 유지 조건` 2그룹 카드 + 하단 `#followup-context-bar` 동시 노출)
    - `./screenshots/desktop_1280x800-4-numeric-100g.png`
    - `./screenshots/desktop-5-route-conflict.png`
    - `./screenshots/desktop-6-new-topic.png`
    - `./screenshots/desktop-7-scope-outside.png`

---

## 5. 한계 및 미검증 범위
- **물리 모바일/태블릿 실기기 터치 검증 미실행:** 이번 검증은 TEST URL(`https://robingraph-test.dove-nest.com/chat`)을 대상으로 Chromium 실제 브라우저 엔진의 `390x844` 모바일 에뮬레이션 및 `1280x800` 데스크톱 뷰포트에서 수행되었으며, iOS Safari / Android Chrome 물리 단말기에서의 실기기 터치·가상 키보드 인터랙션 검사는 수행하지 않았습니다.
