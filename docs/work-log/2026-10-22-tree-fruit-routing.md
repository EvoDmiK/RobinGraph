# [RG-203] '나무열매' 질의 라우팅 보완 및 TEST 배포 검증 — 2026-10-22

> **문서 상태: TEST 검증 완료 (운영 배포 승인 대기)**
> RG-203 그래프 관계 질의 중 `"참새목 새 중에서 나무열매를 먹는 새는?"` 질의가 결정론적 파서의 `"나무열매"` / `"나무 열매"` 별칭 미지원으로 인해 `clarify`(질문 종류 재선택 안내)로 응답하던 문제를 보완했다. `"새 중에서"` 표현은 선행 픽스에서 이미 지원되었으며, 이번 수정은 일반 열매 질의에 `"나무열매"` 및 `"나무 열매"` 어휘를 연계하되, 데이터 원천(EltonTraits)의 한계를 반영하여 응답 제목에 `(나무·풀 구분 없음)`을 상시 명시하고 해석 유의사항(limitations)을 제공하도록 구현했다. 단위 회귀 검사 51건(29+22) 전수 통과, 실제 TEST 환경 API 6건 실측, 공개 TEST 서버 Playwright Chromium(1280px/390px) 2건 실측 검증을 완료하고 컨테이너(`robingraph-api:test-tree-fruit-b1c6c45cd346`)를 배포했다. DB 쓰기 및 운영 배포, Git commit/push는 일체 수행하지 않는다.

---

## 1. 발생 현상 및 원인 분석

### 발생 현상
- 브라우저 실측 질문인 `"참새목 새 중에서 나무열매를 먹는 새는?"`을 입력했을 때, 결과 목록이 반환되지 않고 `disposition: "clarify"`, `answer_text: "질문의 종류를 판단하지 못했습니다..."`가 반환됨 (`before.json` 확인).

### 원인 분석 (`src/robingraph/retrieval/graph_questions.py`)
1. **`나무열매` / `나무 열매` 어휘 미지원 (근본 원인)**:
   - 결정론적 파서의 일반 열매(`order_fruit`) 패턴이 `"과실식"`, `"열매 섭식"`, `"열매를 먹는"`, `"열매 먹는"` 등만 수용하고, 일상적으로 널리 쓰이는 `"나무열매"` 및 `"나무 열매"` 표현을 일반 열매 검색의 별칭으로 지원하지 않아 패턴 매칭에 실패함.
   - *참고*: `"새 중에서"` 표현은 선행 버그 수정(2026-10-22)에서 `_ORDER_SCOPE`를 통해 이미 지원되었으며, 이번 수정에서 포함된 `"중 에서"`(공백 분리) 지원은 추가적인 견고성 보강일 뿐 본 문제의 근본 원인이 아님.
2. **데이터 한계와 명확한 경계 표기 필요성**:
   - 데이터 원천인 EltonTraits의 Diet-Fruit 지표 및 AVONET 형질은 목본류 열매(나무열매)와 초본류 열매(풀열매)를 세부적으로 구분하지 않음.
   - 따라서 `"나무열매"` 질의를 일반 열매 범주로 조회하되, **"나무열매만 먹는 종을 정확히 찾아냈다"고 왜곡 서술하지 않고 자료의 한계(`나무·풀 구분 없음`)를 사용자에게 명시**해야 함.

---

## 2. 주요 코드 변경 및 데이터 경계 처리

### 수정 파일: `src/robingraph/retrieval/graph_questions.py`
1. **정규식 패턴 어휘 확장**:
   - `_ORDER_SCOPE`에 공백 분리형 조사 `중\s*(?:에서|에)?` 지원 추가.
   - `order_fruit` 패턴의 `criterion` 그룹에 `(?:나무\s*)?열매`를 허용하여 `"나무열매"` 및 `"나무 열매"`를 수용.
2. **`tree_fruit_share` 기준 보존 및 한계 고지**:
   - 정규화된 표현이 `"나무열매"`로 시작할 경우 `criterion='tree_fruit_share'`로 식별.
   - 응답 제목(title)에 `(나무·풀 구분 없음)` 접미사를 상시 추가:
     - 예: `"참새목 중 열매를 먹는 종 (나무·풀 구분 없음)"`
   - 응답 유의사항(`limitations`) 첫 머리에 안내 문구 삽입:
     - `"나무열매만 먹는 종을 구분한 자료는 없습니다. 아래 목록은 나무와 풀을 구분하지 않은 열매 먹이 범주를 참고한 결과입니다."`
3. **특정 식물 질문 격리 유지**:
   - `"참새목 새 중에서 감나무 열매를 먹는 새는?"` 등 구체적 식물명이 포함된 질문은 계속해서 `specific_fruit`(`plant="감나무"`)로 판정되어 기존 자료부족(`insufficient_data`) 상태를 보존.

---

## 3. 테스트 및 검증 결과

### 1) 단위 및 회귀 자동화 테스트
- **파서 단위 회귀 (`tests/test_graph_questions.py`)**:
  - `test_tree_fruit_variants_and_split_josa_preserve_plant_boundary`: 4개 분류군 조사 조합 x 2개 열매 어휘(`나무열매`, `나무 열매`) 8건 파서 검증 및 응답 한계 문구 검증 통과.
- **API Mock 회귀 (`tests/test_graph_questions_api.py`)**:
  - `test_tree_fruit_question_routes_with_explicit_category_boundary`: graph handler에 `parsed.criterion='tree_fruit_share'`를 전달하고 mock 응답은 `answer`로 반환됨을 검증 통과 (tree_fruit_share는 내부 파서 기준이며 실제 API payload criterion은 diet_distribution임).
- **테스트 스위트 실행 결과**:
  - `tests/test_graph_questions.py` + `tests/test_graph_questions_api.py`: **29건 전수 통과** (0 fail, 0 skip, 0.066s, `graph-tests.log`)
  - `tests/test_semantic_chat.py`: **22건 전수 통과** (0 fail, 0 skip, 0.235s, `semantic-tests.log`)
  - **합계 51건 전수 통과** (단위 스위트는 Mock/Fixture 환경 사용)
  - *비고*: 프런트엔드 UI 에셋 무변경으로 프런트엔드 스위트 및 전체 Python 스위트는 미재실행.

### 2) 실제 TEST 환경 API 실측 (`actual-api.json`)
- 대상: 실제 배포된 TEST 컨테이너 루프백 엔드포인트 (`http://127.0.0.1:8000/v1/chat`, 모킹 없음)
- **6문항 전수 기대 결과 일치**:
  1. `"참새목 새 중에서 나무열매를 먹는 새는?"`: `answer`, `title: "... (나무·풀 구분 없음)"`, 최대 20종 표시 (성공)
  2. `"참새목 새 중 에서 나무 열매를 먹는 새는?"`: `answer`, `title: "... (나무·풀 구분 없음)"`, 최대 20종 표시 (성공)
  3. `"참새목 새중에서 열매를 먹는 새는?"`: `answer`, `title: "참새목 중 열매를 먹는 종"`, 최대 20종 표시 (성공)
  4. `"참새목 중 열매를 먹고 사는 새는?"`: `answer`, `title: "참새목 중 열매를 먹는 종"`, 최대 20종 표시 (성공)
  5. `"참새목 새 중에서 감나무 열매를 먹는 새는?"`: `abstain`, `insufficient_data`, `title: "특정 열매 공유"`, 0종 반환 (정상 보류)
  6. `"숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?"`: `abstain`, `insufficient_data`, `title: "특정 열매 공유"`, 0종 반환 (정상 보류)
  - *참고*: 반환된 20종은 응답 표시 상한(`limit=20`)이며 전체 종 수가 아님(`not_total_species_count: true`).

### 3) 실제 공개 TEST 서버 브라우저 실측 (`browser.json`, `browser.cjs`)
- 대상: `https://robingraph-test.dove-nest.com/chat` (Playwright Headless Chromium)
- **1280px 데스크톱 및 390px 모바일 실측 (각 1건, 총 2건 통과)**:
  - 스크린샷 질문(`"참새목 새 중에서 나무열매를 먹는 새는?"`) 전송 시 20종 카드 목록 정상 표출 (`fixed-1280.png`, `fixed-390.png` 캡처).
  - 응답 제목 내 `(나무·풀 구분 없음)` 문구 정상 노출 확인 (`visible_tree_grass_limitation_title: true`).
  - 가로 넘침 없음 (`scrollWidth > innerWidth === false`).
  - `pageerror` 0건 (콘솔 이벤트는 미수집). 물리 모바일 기기는 미검증.

---

## 4. TEST 환경 배포 영수증 (`test-release.json`)

- **대상 인프라**: 16GB Mac mini .97 (`robingraph-api-test`, OrbStack)
- **배포 상태 (`state`)**: `verified` (컨테이너 헬스체크 통과)
- **최종 배포 이미지 (`image`)**: `robingraph-api:test-tree-fruit-b1c6c45cd346`
- **소스 SHA256 (`source_sha256`)**: `b1c6c45cd3467dbf34114508f8e10dc1a30095481d2b33bf9dfd2efcb619d777`
- **베이스 리비전 (`base_revision`)**: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷)
- **릴리스 디렉터리 (`release`)**: `/Users/kimdove/robingraph-test/releases/tree-fruit-b1c6c45cd346-da9d5c`
- **이전 이미지**: `robingraph-api:test-fruit-routing-1a6f00caccaa`
- **보조 검증**: `fixture_network_none_smoke: true` (격리 픽스처 스모크 통과), `manage.sh verify` 통과, UI 에셋 무변경, DB/인덱스 무변경 (쓰기 0건), 새 기술/특정 식물 데이터 추가 없음, 운영 무변경, Git commit/push 없음.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
- 선행 작업기록:
  - 선행 기능 구현: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-관계-기반-질의응답-착수|RG-203 그래프 관계 질의응답 착수]]
  - 선행 UI 디자인: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-답변-UI-디자인-정리|RG-203 그래프 답변 UI 디자인 정리]]
  - 선행 버그 수정: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-열매-질의-라우팅-버그-수정|RG-203 열매 질의 '새중에서' 라우팅 버그 수정]]
- 검증 요약: [summary.json](../verification/assets/2026-10-22-tree-fruit-routing/summary.json)
- 수정 전 clarify 응답 증거: [before.json](../verification/assets/2026-10-22-tree-fruit-routing/before.json)
- 실제 TEST API 실측: [actual-api.json](../verification/assets/2026-10-22-tree-fruit-routing/actual-api.json)
- 브라우저 검증 결과: [browser.json](../verification/assets/2026-10-22-tree-fruit-routing/browser.json)
- 브라우저 검증 스크립트: [browser.cjs](../verification/assets/2026-10-22-tree-fruit-routing/browser.cjs)
- 단위 테스트 로그: [graph-tests.log](../verification/assets/2026-10-22-tree-fruit-routing/graph-tests.log)
- 시맨틱 챗 테스트 로그: [semantic-tests.log](../verification/assets/2026-10-22-tree-fruit-routing/semantic-tests.log)
- 배포 영수증: [test-release.json](../verification/assets/2026-10-22-tree-fruit-routing/test-release.json)
- 데스크톱 스크린샷: [fixed-1280.png](../verification/assets/2026-10-22-tree-fruit-routing/fixed-1280.png)
- 모바일 스크린샷: [fixed-390.png](../verification/assets/2026-10-22-tree-fruit-routing/fixed-390.png)
- **실제 검증 자산 보존 위치** (`dev-codex`):
  `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-22-tree-fruit-routing/`
