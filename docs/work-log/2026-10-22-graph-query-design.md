# [RG-203] 그래프 답변 UI 디자인 정리 및 접기/목록 UX 개선 완료 — 2026-10-22

> **문서 상태: TEST 검증 완료 (운영 배포 승인 대기)**
> 사용자 승인에 따라 RG-203 그래프 관계 기반 질의응답 기능의 시각적 완성도와 사용성을 높이기 위한 후속 UI 디자인 정리 작업을 완료했다. Codex(root)가 JS 결과 목록 렌더링 및 네이티브 `<details>`/`<summary>` 접기 UX를 구현하고, Antigravity가 `styles.css` 스타일시트 디자인을 전담했으며, Codex가 PC 2열/모바일 1열 그리드 및 reduced-motion을 보완했다. TEST 환경(16GB Mac .97) 컨테이너 실제 배포(`robingraph-api:test-graph-ui-0d36c7d79044`), Node 프런트엔드 회귀 테스트 319건 전수 통과, 공개 TEST 서버 Playwright Chromium 10건 실측 검증(키보드 Enter 종별 근거 접기 및 summary.click() 유의사항 토글, 자료부족 문구 노출, 프로필 연동, 페이지 런타임 오류 0건, 가로넘침 없음)을 완료했다. DB 수정 작업 미수행 · 이번 UI 작업 별도 DB 감사는 미실행하였으며, 운영 배포 및 Git commit/push는 수행하지 않는다.

---

## 요약

- **배경 및 요구사항**:
  - RG-203 관계 질의응답(공통 분류, 동일 속, 서식지 겹침, 먹이 공유 등)은 최대 20종의 종 목록(`limit=20`, `has_more: true`), 분류학적 계층 경로(LCA), 출처 배지, 자료 부족 안내 등 다양한 구조화 정보를 출력한다.
  - 많은 종(최대 20종)이 반환될 때 세부 근거와 출처, 주의사항이 모두 펼쳐져 있으면 화면 스크롤이 지나치게 길어지므로, **종 목록은 우선적으로 전체 표시**하되 **종별 연결 경로·출처와 해석 유의사항을 네이티브 `<details>`/`<summary>`로 기본 닫힘 접기 처리**하여 탐색 효율과 가독성을 극대화했다.
- **역할 분담 및 실제 구현**:
  - **Codex (root)**:
    - `src/robingraph/api/static/chat.js`의 `buildGraphQueryAnswer` 함수 구현.
    - 종 목록 20개는 전체 표시(기본 n개 접기가 아님: 종 목록 우선 표출).
    - 종별 세부 연결 경로 및 근거(`item.paths`)를 네이티브 `<details class="graph-query-evidence">`로 접기 처리.
    - 안내 및 유의사항(`payload.text`, `payload.limitations`)을 `<details class="species-note graph-query-notes">`에 보존하여 접기 처리.
    - 자료 부족(`status: insufficient_data`) 또는 빈 결과(`status: empty`) 안내는 접지 않고 항상 노출(`species-answer-empty`).
    - PC 2열 그리드(`repeat(2, minmax(0, 1fr))`) / 모바일 1열 그리드(`1fr`), marker 커스텀, `prefers-reduced-motion: reduce` 트랜지션 해제 보완.
  - **Antigravity**:
    - `src/robingraph/api/static/styles.css`에 그래프 답변 전용 스타일 작성 (`chat.css`가 아닌 기존 `styles.css` 사용).
    - cream 톤의 종 카드 배경(`.graph-query-species-row`, `#f8f3e7`), 작은 이탤릭 학명(`.graph-query-latin`), 엔티티 버튼 스타일 및 여백 정돈.
    - 터치 44px 보장 주장은 하지 않음.
- **자동화 및 브라우저 검증 결과**:
  - **Node 프런트엔드 테스트**: `node --test tests/frontend/*.test.js` 기준 **319건 전수 통과 / 0건 skip / 0건 fail (244.43ms)**.
    - CSS 첫 실행 시 318 pass / 1 fail 발생: 기존 정성평가 상자 테스트가 CSS 파일 후반 전체를 스캔하다가 무관한 `user-select: none`을 탐지함. 불필요한 그래프 전용 선언을 제거한 후 최종 319건 전수 통과.
  - **Playwright Chromium 실제 TEST 검증**: 1280px 데스크톱 및 390px 모바일 뷰포트 대상 **10건 검사 전수 통과**.
    - 네이티브 `<details>` 기본 닫힘 상태 확인.
    - 키보드 `Enter` 키로 종별 근거(`item.paths`) 접기 열기/닫기 동작 확인, `summary.click()`으로 유의사항(`notes`) 접기 토글 동작 확인.
    - 열린 후 출처 링크 가시성 확인.
    - 자료 부족(`insufficient_data`) 핵심 문구 항상 노출 확인.
    - 종 버튼 클릭 시 `profile` 패널 전환 확인.
    - 가로 넘침 없음 (`document.documentElement.scrollWidth > innerWidth === false`).
    - `pageerror` 이벤트 전무 (0건). 콘솔 이벤트는 `browser.cjs`에서 pageerror만 수집하여 별도 미검증.
  - **Python 테스트**: 순수 프런트엔드 JS/CSS 표현 변경이며 브라우저에서 실제 TEST API 호출이 검증되었으므로 전체 Python 스위트는 재실행하지 않음 (`python_suite_rerun: false`).
- **TEST 환경 배포 및 형상 관리**:
  - 이미지 교체 순서: `29bfdd0c4bfa` (초기 CSS) → `7fd3009c5eeb` (CSS 불필요 user-select 제거) → **`0d36c7d79044` (JS 줄끝 공백 정리 후 최종 이미지)**.
  - 최종 이미지: `robingraph-api:test-graph-ui-0d36c7d79044` (상태: `verified`).
  - 소스 SHA: `0d36c7d7904463e562473f8829f17ce2f555aa954ff0d274bd0e090f3c3f5d5b`.
  - 베이스 리비전: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷 기반 TEST 빌드).
  - 릴리스 디렉터리: `/Users/kimdove/robingraph-test/releases/graph-ui-0d36c7d79044-6ca51e`.
  - 롤백 미실행 (`rollback_executed: false`), DB 수정 작업 미수행 · 이번 UI 작업 별도 DB 감사 미실행, 운영 배포 및 Git commit/push 없음 (`production_changed: false`, `git_commit_push: false`).

---

## 작업 및 변경 결과 요약

| 구분 | 계획 및 설계 사항 | 최종 TEST 검증 결과 (2026-10-22) |
| --- | --- | --- |
| **JS 렌더링 및 접기 UX** | 종 목록 우선 표출 + 세부 경로/주의사항 네이티브 접기 | 구현 완료 (`src/robingraph/api/static/chat.js`의 `buildGraphQueryAnswer`) |
| **CSS 전용 스타일시트** | cream 카드, 이탤릭 학명, PC 2열/모바일 1열, reduced-motion | 작성 완료 (`src/robingraph/api/static/styles.css` 후반부) |
| **Node 프런트엔드 테스트** | 319개 전체 단위/DOM 테스트 회귀 검증 | **319건 전수 통과 / 0 skip / 0 fail** (244.43ms, 불필요 user-select 제거 후 통과) |
| **Python 회귀 테스트** | 백엔드 코드 무변경 확인 | 미재실행 (`python_suite_rerun: false`, 순수 UI 변경 및 브라우저 실측 완료) |
| **TEST 환경 배포** | 16GB Mac .97 앱 컨테이너 실제 배포 | `robingraph-api:test-graph-ui-0d36c7d79044` (상태: `verified`) |
| **실제 브라우저 검증** | Playwright Chromium 데스크톱(1280) 및 모바일(390) | **10건 검사 전수 통과** (Enter 종별 근거 접기 / summary.click() 유의사항 토글, 자료부족 노출, 가로넘침 없음, pageerror 0) |
| **DB 및 패키지 무결성** | FastAPI/Starlette 부재 확인 | `image-packages.json` (`fastapi: true, starlette: true`), DB 수정 작업 미수행 · 이번 UI 작업 별도 DB 감사 미실행 |
| **운영 배포 및 형상 관리** | 운영 배포 배제 및 Git 커밋/푸시 배제 | 운영 변경 없음(`production_changed: false`), Git 커밋/푸시 없음(`git_commit_push: false`) |

---

## 1. 주요 구현 내용

### 1) JavaScript 렌더링 구조 (`src/robingraph/api/static/chat.js`)
- **함수**: `buildGraphQueryAnswer(doc, payload, options)`
- **종 목록 우선 표출**:
  - API 응답의 `payload.items`를 순회하며 20개 종을 모두 목록으로 표출 (`.graph-query-species`).
  - 종 목록 자체를 n개로 잘라 접는 임의의 상태 토글은 적용하지 않음 (사용자가 원하는 종을 즉시 확인할 수 있도록 우선 표시).
- **네이티브 `<details>`/`<summary>` 접기 UX**:
  - 종별 세부 연결 경로(`item.paths`): `<details class="graph-query-evidence">`로 감싸 기본 닫힘으로 렌더링.
  - 공통 연결 경로(`payload.paths`): `<details class="graph-shared-paths graph-query-evidence">`로 감싸 접기.
  - 안내 및 유의사항(`payload.text`, `payload.limitations`): `<details class="species-note graph-query-notes">`로 감싸 본문 최하단에 배치.
  - 출처 및 근거 자료(`payload.sources`): `<details class="species-answer-sources">`로 접기.
- **자료 부족 안내 상시 노출**:
  - `payload.status === "insufficient_data"` 또는 `"empty"`인 경우, 안내 문구(`payload.text`)를 접지 않고 `<p class="species-answer-empty">`로 즉시 가시화.

### 2) CSS 스타일시트 디자인 (`src/robingraph/api/static/styles.css`)
- **카드 및 타이포그래피**:
  - `.graph-query-species-row`: 따뜻한 cream 톤 배경(`var(--color-bg, #f8f3e7)`), 테두리(`var(--color-border, #e3dac4)`), 호버 시 부드러운 강조 효과.
  - `.entity-candidate-button`: 굵은 초록 계열 폰트(`var(--color-accent, #2f6f4f)`), 종 이름 클릭 시 프로필 패널 연동.
  - `.graph-query-latin`: 작은 이탤릭체 학명 스타일(`font-style: italic; font-size: 0.82rem; color: var(--color-muted, #726a56)`).
- **반응형 그리드 레이아웃**:
  - 데스크톱(기본): `display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem;` (PC 2열).
  - 모바일(`@media (max-width: 480px)`): `grid-template-columns: 1fr;` (모바일 1열 전환, 버튼 너비 100%).
- **접근성 및 모션 대응**:
  - `@media (prefers-reduced-motion: reduce)`: 카드 및 버튼 트랜지션 해제.
  - 키보드 포커스 링: `:focus-visible`에 2px outline 적용.

---

## 2. 검증 및 테스트 결과

### 1) Node 프런트엔드 자동화 테스트 (`frontend-tests.log`)
- **실행 명령어**: `node --test tests/frontend/*.test.js`
- **실행 결과**:
  - 총 테스트 수: **319개**
  - **통과: 319개** / **건너뜀(skip): 0개** / **실패: 0개**
  - 실행 시간: **244.42775ms**
- **초기 실패 및 해결 이력**:
  - 첫 실행 시 318 pass / 1 fail 발생: 기존 `tests/frontend/chat_ui.test.js` 정성평가 상자 테스트가 CSS 파일 후반 전체를 정규식으로 스캔하다가, 그래프 답변 전용 스타일에 포함되었던 무관한 `user-select: none` 속성을 감지함.
  - 그래프 답변 UI에 불필요한 `user-select` 선언을 제거한 후 재실행하여 319건 전수 통과.

### 2) 실제 TEST 실서버 브라우저 검증 (`browser.json`, `browser.cjs`)
- **실행 환경**: Playwright Headless Chromium (`https://robingraph-test.dove-nest.com/chat`, `reducedMotion: 'reduce'`)
- **응답 모킹**: 없음 (`response_mocking: false`, 실제 배포된 TEST 컨테이너 호출)
- **물리 기기 여부**: `physical_mobile: false` (Chromium 뷰포트 에뮬레이션)
- **10건 브라우저 검사 결과**:
  1. 1280px 데스크톱: 청둥오리-흰뺨검둥오리 관계 질의 통과 (출처 링크 6개, 오류 0건).
  2. 1280px 데스크톱: 참새목 열매 질의 통과 (출처 61개, 키보드 Enter로 종별 evidence 접기 열기/닫기 확인, summary.click()으로 notes 토글 확인, `graph-query-1280.png` 캡처).
  3. 1280px 데스크톱: 숲 직박구리 특정열매 자료부족 통과 (`status: insufficient_data`, 자료부족 안내 문구 visible 확인).
  4. 1280px 데스크톱: 한국기록 같은속 profile 의도 질의 통과 (출처 16개).
  5. 1280px 데스크톱: 종 버튼 클릭 시 `profile` 패널 전환 통과.
  6. 390px 모바일: 청둥오리-흰뺨검둥오리 관계 질의 통과 (1열 레이아웃, 출처 6개).
  7. 390px 모바일: 참새목 열매 질의 통과 (1열 레이아웃, `graph-query-390.png` 캡처).
  8. 390px 모바일: 숲 직박구리 특정열매 자료부족 통과 (자료부족 문구 visible 확인).
  9. 390px 모바일: 한국기록 같은속 profile 의도 질의 통과 (출처 16개).
  10. 390px 모바일: 종 버튼 클릭 시 `profile` 패널 전환 통과.
- **레이아웃 및 오류**:
  - `document.documentElement.scrollWidth > innerWidth === false` (가로 넘침 전무).
  - `page_errors: 0` (페이지 런타임 오류 0건, 콘솔 이벤트는 `browser.cjs`에서 pageerror만 수집하여 별도 미검증).

### 3) TEST 환경 컨테이너 배포 영수증 (`test-release.json`)
- **대상 환경**: 16GB Mac `.97` (`robingraph-api-test`, OrbStack 컨테이너)
- **배포 상태 (`state`)**: `verified`
- **최종 배포 이미지 (`image`)**: `robingraph-api:test-graph-ui-0d36c7d79044`
- **소스 SHA256 (`source_sha256`)**: `0d36c7d7904463e562473f8829f17ce2f555aa954ff0d274bd0e090f3c3f5d5b`
- **베이스 리비전 (`base_revision`)**: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷)
- **릴리스 디렉터리 (`release`)**: `/Users/kimdove/robingraph-test/releases/graph-ui-0d36c7d79044-6ca51e`
- **이전 이미지 교체 이력**:
  1. `29bfdd0c4bfa` (초기 CSS)
  2. `7fd3009c5eeb` (CSS 불필요 user-select 제거)
  3. `0d36c7d79044` (JS 줄끝 공백 정리 후 최종 교체)
- **보조 검증**:
  - `fixture_network_none_smoke: true` (네트워크 단절 픽스처 스모크 통과)
  - `rollback_executed: false` (롤백 미실행)
  - `production_changed: false` (운영 환경 무변경)
  - `image-packages.json`: `{"fastapi": true, "starlette": true}` (부재 확인, `manage.sh verify` 통과)

---

## 3. 한계 및 후속 과제

1. **단일 턴 처리 유지**:
   - UI 디자인 및 접기 UX 개선은 프런트엔드 표현 계층에 한정되며, 질문 간 문맥 이어가기나 대화 상태 기억은 기존 RG-203 원칙대로 향후 후속 과제로 분리 유지됨.
2. **물리 모바일 기기 검증**:
   - Playwright Chromium 390px 뷰포트 에뮬레이션 상에서 가로 넘침 없음 및 키보드/마우스 동작을 확인했으나, 실제 물리 스마트폰에서의 터치 조작 검증은 향후 물리 환경 검증 절차에 따름.
3. **운영 배포 승인 대기**:
   - TEST 검증은 전수 완료되었으며, 사용자 명시 승인 전까지 운영 배포 및 Git commit/push는 일체 수행하지 않음.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
- 선행 작업기록: [docs/work-log/2026-10-22-graph-relationship-qa.md](2026-10-22-graph-relationship-qa.md)
- 검증 요약: [summary.json](../verification/assets/2026-10-22-graph-query-design/summary.json)
- 브라우저 실측 결과: [browser.json](../verification/assets/2026-10-22-graph-query-design/browser.json)
- 브라우저 검증 스크립트: [browser.cjs](../verification/assets/2026-10-22-graph-query-design/browser.cjs)
- 프런트엔드 테스트 로그: [frontend-tests.log](../verification/assets/2026-10-22-graph-query-design/frontend-tests.log)
- 배포 영수증: [test-release.json](../verification/assets/2026-10-22-graph-query-design/test-release.json)
- 데스크톱 스크린샷: [graph-query-1280.png](../verification/assets/2026-10-22-graph-query-design/graph-query-1280.png)
- 모바일 스크린샷: [graph-query-390.png](../verification/assets/2026-10-22-graph-query-design/graph-query-390.png)
- 패키지 부재 점검: [image-packages.json](../verification/assets/2026-10-22-graph-query-design/image-packages.json)
- 실제 검증 자산 보존 위치 안내 (`dev-codex`): `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-22-graph-query-design/`
