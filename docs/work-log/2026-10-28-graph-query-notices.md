---
created: 2026-10-28
date: 2026-10-28
project: RobinGraph
type: worklog
status: completed
task_id: RG-213-UI
tags:
  - worklog
  - robingraph
  - graph-query
  - notice-ui
  - test-verified
---

# [RG-213 후속 UI / 검색·그래프 질의] 그래프 질의 안내·유의사항 단일 영역 통합 및 중복 제거 (TEST 배포 검증 완료 · 운영 미반영) — 2026-10-28

> **문서 상태: UI 개선 및 TEST 배포 검증 완료 (운영 미반영)**  
> 그래프 질의(`graph_query`) 결과 렌더링 시 `payload.limitations`와 최상위 `answer.warnings`의 중복 안내 문구를 단일 접힘 영역(`.graph-query-notes`)으로 일원화하고, 주황색 경고 테마를 중립 색조로 정돈한 후속 UI 개선을 완료하였다.  
> TEST 환경 배포(`notice-ui-dc72ada65dbf-46b2cc`) 후 실제 API 2회 호출(8/8 pass) 및 Headless Chromium(390px, 1280px) 실환경 렌더링 검증을 마쳤으며, 운영(Production NAS) 배포 및 Git 커밋·푸시는 수행하지 않았다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 및 원인** | 안내 문구 중복 노출 및 과도한 경고 색조 정돈 | `payload.limitations`와 `answer.warnings`의 2중 출력 경로로 인한 동일 문구 중복 및 주황색 경고 박스 노출 문제 해결 |
| **설계 및 해결 방안** | 단일 접힘 영역 통합 및 중립 테마 전환 | 그래프 질의 시 외곽 `.warnings` 목록을 억제하고, 내부에서 `Array.from(new Set(...))`으로 중복 제거 후 카운트 표시, 배경/테두리 중립화 |
| **수정 파일** | 3개 파일 (JS 1, CSS 1, Test 1) | `chat.js`, `styles.css`, `tests/frontend/chat_ui.test.js` |
| **TEST 배포** | TEST 전용 배포 완료 (운영 배포 없음) | 이미지 `robingraph-api:test-notice-ui-dc72ada65dbf`, 릴리스 `notice-ui-dc72ada65dbf-46b2cc` (healthy) |
| **검증 결과** | 단위 333건, 실 API 8/8, 실 브라우저 2종 통과 | 프런트엔드 단위 333 pass(0 fail, 0 skip), 실 API 8 pass, Chromium 390px/1280px 중복 제거 및 무넘침 확인 |
| **형상 관리** | 커밋·푸시 미수행 (워킹 트리 유지) | 운영 NAS 미배포, Git commit/push 없음, DB 쓰기 0건 |

---

## 1. 작업 배경 및 원인 분석

### 발생 현상
* 그래프 질의(`kind: "graph_query"`) 응답 화면에서 "EltonTraits 먹이 구성...", "AVONET 범주값..." 등과 같은 데이터 한계 안내 문구가 접힌 안내 카드 내부와 답변 하단 외곽 경고 목록에 중복으로 출력됨.
* 또한 `.graph-query-notes`의 배경 및 테두리가 기권/경고용 주황색 톤(`--color-abstain-bg`, `--color-warning`)으로 적용되어 일반적인 데이터 참고 안내임에도 불필요한 시스템 경고 인상을 줌.

### 원인 분석: 2가지 출력 경로
1. **경로 1 (`buildGraphQueryAnswer`)**: `payload.limitations` 배열을 읽어 접힌 `<details class="species-note graph-query-notes">` 내부에 리스트로 출력.
2. **경로 2 (`appendAssistant`)**: 최상위 `answer.warnings`를 별도 분기 없이 읽어 메시지 하단에 `<ul class="warnings">` 리스트로 추가 출력.
* 백엔드가 일관성을 위해 limitations와 warnings 양쪽에 공통 안내를 제공하면서 프런트엔드에서 동일 문구가 두 번 렌더링되는 구조적 원인이었음.

---

## 2. 해결 방안 및 구현 내용

### 수정 및 추가 파일 목록
* `src/robingraph/api/static/chat.js`: 그래프 질의 시 외곽 warnings 억제 및 내부 중복 제거 로직 추가
* `src/robingraph/api/static/styles.css`: `.graph-query-notes` 색상 중립화 및 여백·줄바꿈 정돈
* `tests/frontend/chat_ui.test.js`: 중복 제거/카운트 및 비그래프 경고 보존 단위 테스트 2건 추가

### 핵심 구현 상세
* **`chat.js`**:
  * `isGraphQuery` 플래그를 도입하여 그래프 질의일 때는 외곽 `warnList` 생성을 건너뜀 (`var warnings = (!isGraphQuery && Array.isArray(answer.warnings)) ? answer.warnings : []`).
  * `buildGraphQueryAnswer` 옵션으로 `warnings: answer.warnings`를 전달하며, limitations와 warnings 배열을 결합하고 유효한 문자열을 trim·빈 값 제거한 뒤 `Array.from(new Set(...))`으로 중복 제거한다.
  * 요약 제목에 중복 제거된 고유 항목 개수 반영 (`안내 및 유의사항 (N)`).
* **`styles.css`**:
  * `.graph-query-notes`: 테두리를 `var(--color-border, #dcd6c8)`로, 배경을 `var(--color-surface, #ffffff)`로 변경.
  * `summary`: 텍스트 색상을 `var(--color-muted, #6e6757)`로 변경.
  * `ul`, `li`: 패딩 및 여백 미세 조정, `word-break: keep-all; overflow-wrap: anywhere;` 적용으로 모바일 뷰포트 가로 넘침 방지.

---

## 3. 검증 및 테스트 결과

### 1) 단위 테스트 (로컬 Node)
* **실행 명령**: `node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`
* **결과**: 총 **333건 통과 (0 fail, 0 skip, 0 cancelled, 264.57ms)** (333건 통과는 `chat_ui.test.js`와 `birds_ui.test.js` 합산 실행 결과이며, 단독 `chat_ui.test.js`는 329건 통과)
  * 신규 1: `buildGraphQueryAnswer consolidates limitations and options.warnings without duplicate entries and counts them` 통과.
  * 신규 2: `appendAssistant merges graph_query warnings inside graph-query-notes and omits external warnings list while keeping non-graph warnings` 통과.

### 2) 실서버 API 검증 (`https://robingraph-test.dove-nest.com/v1/chat`)
* **실행 도구**: `verify_notice_ui_live.py` (TEST 환경 실제 HTTP 호출)
* **결과**: 2회 질의(기본 숲 열매 새, 후속 한국 새) 대상 **8개 항목 전수 통과 (8/8 pass)**.
  * `warnings_unique: true` 확인, follow-up 토큰 반환·no-store·trace/피드백 헤더 존재를 확인했고 원문 토큰은 증거에 기록하지 않음. 이번 MLflow trace readback은 미실행.

### 3) 실환경 브라우저 검증 (Headless Chromium CDP)
* **실행 도구**: `run-notice-browser.cjs` (실제 TEST 배포 웹 UI 접속)
* **검증 뷰포트**:
  1. **Mobile (390×844)**: 터치 탭 인터랙션 검증.
  2. **Desktop (1280×800)**: 키보드 Enter 포커스 인터랙션 검증.
* **검증 결과**: 양 뷰포트 모두 **전 항목 통과 (passed: true)**.
  * 기본 상태에서 접힘 유지(`collapsed_by_default`), 외곽 `.warnings` 0개 확인.
  * 클릭/Enter 시 정상 펼침, 원본 10개(5 limitations + 5 warnings)가 중복 없이 5개로 단일 렌더링됨.
  * 가로 넘침 0건(`docHorizontalOverflow: false`), 피드백 3개 버튼 공존 유지.
* **보존 증거**: `docs/verification/assets/2026-10-28-graph-query-notices/` 내 4개 화면(`mobile/desktop` collapsed & expanded) 및 결과 JSON.

---

## 4. 배포 및 형상 관리

* **대상 환경**: TEST 환경 전용 (`robingraph-test`)
* **배포 승인**: Root 승인 (msg_2fbf1bf9c445)
* **배포 이미지**: `robingraph-api:test-notice-ui-dc72ada65dbf` (arm64, healthy)
* **릴리스 경로**: `/Users/kimdove/robingraph-test/releases/notice-ui-dc72ada65dbf-46b2cc`
* **소스 스냅샷**: `snapshot-dc72ada65dbf` (235개 파일 해시 일치, base: `318e7731fda8`)
* **운영 반영 및 Git**:
  * Production NAS 배포 없음 (`production_changed: false`).
  * Git `commit` 및 `push` 미수행 (`git_commit_push: false`, 워킹 트리 작업 상태 유지).
  * DB / Neo4j / n8n 쓰기 0건.

---

## 5. 한계 및 미검증 범위

* **물리 모바일 기기 미검증**: 실제 물리 스마트폰 검사는 생략하고 Chromium CDP 터치 에뮬레이션으로 대체함.
* **기타 브라우저**: WebKit(Safari), Gecko(Firefox) 렌더링 검사는 수행하지 않음.
* **백엔드 스위트 생략**: 프런트엔드 3개 파일 한정 변경으로 Python 백엔드 전체 회귀(1,359건) 재실행은 생략함.

---

## 관련 문서

- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-28-조건-유지-후속-질문-1단계|선행 작업: RG-213 조건 유지 후속 질문 1단계]]
- [[Work/RobinGraph/RobinGraph 작업 백로그#RG-213|RobinGraph 작업 백로그 (RG-213)]]
