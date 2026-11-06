# Follow-up Condition-Keeping Chat UI Report (`dev-agy`, Contract v2)

## 1. 작업 개요 및 배경
- **역할 및 워크트리:** `dev-agy` (`/Users/kimdove/orca/workspaces/RobinGraph/main`, 브랜치 `dev-agy`)
- **사전 백업:** `/tmp/robingraph-followup-20261028/dev-agy-backup/` (`HEAD`, `files.txt`, `tracked.diff`, `pre-baseline-owned-files.tar.gz`)
- **기준선 및 계약:** `/tmp/robingraph-followup-20261028/baseline-x/` (`src/robingraph/api/static/*`, `tests/frontend/*`) 및 `/tmp/robingraph-followup-20261028/contract.md` **v2** (root `dev-codex` / `dev-claude` `ChatFollowupPlan`·`ChatFollowupInfo` 스키마 기준)

## 2. Contract v2 변경 파일 및 구현 내용 (`Ponytail` 단순화 반영)
1. `src/robingraph/api/static/index.html`
   - `#chat-form` 상단에 활성/유지 조건 안내 상태 바(`<div id="followup-context-bar" class="followup-context-bar" role="status" aria-live="polite" hidden></div>`) 추가.
2. `src/robingraph/api/static/chat.js`
   - **v1 호환 코드 전면 제거 및 v2 전용 정규화:**
     - `FOLLOWUP_SCOPE_LABELS` (`{ korea: "국내 기록", outside: "국외 분포", unknown: "한국 분포 미확인" }`) 및 `FOLLOWUP_REASONS` (`"route_conflict"` 포함 9개 사유) 정의.
     - `followupPlanItems(plan)`: v2 `ChatFollowupPlan` (`{ conditions: string[], taxon: string|null, scope: "all"|"korea"|"outside"|"unknown" }`)에서 분류군·조건·범위 라벨(`국내 기록` / `국외 분포` / `한국 분포 미확인`) 추출.
     - `normalizeFollowupSummary(followup)`: top-level `followup.conditions`가 있는 v1 객체는 즉시 거부(`null`)하고, v2 `followup.plan` 및 `followup.retained`만 정규화.
   - **메시지 버블 내 조건 표시 (`buildFollowupSummary`):**
     - 초기 성공 그래프 답변(`followup == null`): `initialGraphItems(payload, speciesScope)`로 `적용 조건` 칩 표시 (`outside`/`unknown`/`korea` 범위 라벨 포함).
     - 후속 질문 성공(`applied` + `answer`): `적용 조건` 및 `추가 조건: <followup.added>` 뱃지와 함께 `followup.plan` 표시.
     - 후속 질문 결과 없음/자료 부족(`applied` + `abstain`, `empty` / `insufficient_data`): **두 그룹으로 명확히 분리 표시**:
       1. `이번 조회 조건` (+ `추가 조건: <followup.added>`): `followup.plan` (시도된 추가 조건 포함)
       2. `다음 질문 유지 조건`: `followup.retained` (미적용 추가 조건 제외, 다음 턴에 유지되는 조건만 표시)
     - 후속 질문 거부(`rejected`): `followup.retained`가 있는 복구 가능 사유(`route_conflict`, `unsupported_addition`, `unresolved_addition`, `multiple_additions`, `duplicate_condition`, `conflicting_condition`)에서는 `유지된 조건` 표시, 문맥 소멸 사유(`context_missing`, `context_invalid`, `context_scope_mismatch`)에서는 조건 박스를 생략.
   - **다음 턴 활성 조건 바(`#followup-context-bar`) 갱신 원칙:**
     - 오직 서버가 응답한 `followup.retained`(또는 초기 base graph `answer`의 조건)만 기준으로 갱신하며, 실패/abstain/reject 시 이전 클라이언트 라벨을 추측하거나 재사용하지 않음.
   - **요청 전송 및 Ponytail 단순화:**
     - `buildChatPayload(question, intent, values, speciesScope, followupContext)`: 5번째 인자 `followupContext`만 정규화하여 부착(`values.followup_context` 중복 분기 제거). 일반 폼 전송 시 `intent`가 `taxonomy`이거나 필터가 설정된 경우에도 `followup_context`를 그대로 전달하여 서버가 검증 후 `route_conflict` clarify와 `retained` 조건을 반환할 수 있도록 처리. 반면 종/후보/선택지 버튼 클릭(`payloadOverride`)은 `followup_context`를 포함하지 않고 독립 질의로 전환.
     - `init(doc, win)`에서 불필요한 `#followup-context-bar` 동적 DOM 생성 fallback 제거(`index.html` 및 테스트 `REQUIRED_IDS`에 정적 선언).
3. `src/robingraph/api/static/styles.css`
   - `.followup-context-bar`, `.graph-query-conditions`, `.graph-query-conditions-header`, `.graph-query-conditions-label`, `.graph-query-condition-added`, `.graph-query-condition-list`, `.graph-query-condition-chip` 반응형/다크모드/줄바꿈(`min-width: 0`, `overflow-wrap: anywhere`) 스타일 정의.
4. `tests/frontend/chat_ui.test.js`
   - `REQUIRED_IDS` 및 `index.html` 필수 마커에 `followup-context-bar` 추가.
   - 모든 후속 질문 테스트 fixture를 Contract v2로 전면 교체하고 다음 시나리오를 검증:
     - (1) `initial -> korea -> 추가 숫자(체중 100g 이상)` -> 일반 질문 전환
     - (2) `empty` (`체중 5000g 이상`)에서 버블 내 `이번 조회 조건`(`plan`)과 `다음 질문 유지 조건`(`retained`) 분리 표시 및 `#followup-context-bar`에서 미적용 숫자 조건이 제외되는지 검증
     - (3) `route_conflict` (`intent="taxonomy"` 상태에서 지시어 후속 질문 전송 시 토큰 및 `retained` 유지)
     - (4) `outside` (`국외 분포`) 및 `unknown` (`한국 분포 미확인`) scope 라벨 표시
     - (5) `clear`, `species_scope` 변경, `stale` 응답 폐기, 탭 간 격리, 종 버튼 클릭 시 초기화, RG603 `feedback` 버튼 공존, v1 flat payload 거부 검증.

## 3. 검증 방법 및 실제 결과
1. **프런트엔드 단위/통합 테스트 (Node test runner):**
   - 실행 명령: `node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`
   - 결과: **331 tests, 331 passed, 0 failed** (`duration_ms: 261.18ms`)
2. **실제 Python 백엔드(`dev-codex` `ApiService`) 응답과의 E2E 계약 검증 (Python + Headless Chromium):**
   - `dev-codex`의 `ApiService` (`graph_intent_mode="active"`)에서 실제 생성·직렬화한 `ChatResponse.model_dump(mode="json")` 응답(`/tmp/robingraph-followup-20261028/v2-python-responses.json`)을 로컬 HTTP 서버로 서빙하고 Headless Chromium (`390x844` 모바일 / `1280x800` 데스크톱)에서 검증:
     - `afterInitial`: `"현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함"`
     - `afterConflict` (`route_conflict`): `"유지된 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함"`
     - `afterKorea`: `"현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 국내 기록"`
     - `afterEmpty` (`체중 5000g 이상` empty):
       - `#followup-context-bar`: `"유지된 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 국내 기록"` (미적용 숫자 조건 미포함 확인)
       - 버블 라벨: `["이번 조회 조건", "다음 질문 유지 조건"]`
       - 버블 칩 목록: `[["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "체중 5000g 이상", "국내 기록"], ["서식 환경 숲(Forest)", "먹이 구성에 열매 포함", "국내 기록"]]`
     - `afterNumeric` (`체중 100g 이상` 재시도 성공): `"현재 적용 조건: 서식 환경 숲(Forest) · 먹이 구성에 열매 포함 · 체중 100g 이상 · 국내 기록"`, 가로 스크롤 오버플로 없음(`overflow: false`).
3. **패치 및 산출물 검증:**
   - `patch -p1 --dry-run -d /tmp/robingraph-followup-20261028/baseline-x < /tmp/robingraph-followup-20261028/ui.patch`: 4개 파일 모두 충돌 없이 clean apply 확인.
   - `uv run graphify update .`: AST 그래프 갱신 완료 (`5196 nodes, 10761 edges, 290 communities`).

## 4. 산출물 경로
- 패치: `/tmp/robingraph-followup-20261028/ui.patch`
- 수정본 파일 사본: `/tmp/robingraph-followup-20261028/ui-files/`
- Python v2 응답 검증 스냅샷: `/tmp/robingraph-followup-20261028/v2-python-responses.json`
- 보고서: `/tmp/robingraph-followup-20261028/ui-report.md`
