# [RG-203] 열매 질의 '새중에서' 라우팅 버그 수정 및 TEST 배포 검증 — 2026-10-22

> **문서 상태: TEST 검증 완료 (운영 배포 승인 대기)**
> RG-203 그래프 질의 중 "참새목 새중에서 열매를 먹는 새는?" 형태의 질문이 일반 열매(`order_fruit`) 대신 특정 식물 열매(`specific_fruit`)로 오분류되어 자료부족 안내(`insufficient_data`)로 응답하던 파서 정규식 버그를 수정했다. `src/robingraph/retrieval/graph_questions.py`에 공통 `_ORDER_SCOPE`를 도입하고 패턴 매칭 우선순위를 재조정했다. 단위 회귀 및 API Mock 검사(27+22건), 실제 TEST 환경 API 6건 실측, 공개 TEST 서버 Playwright Chromium(1280px/390px) 2건 실측 검증을 완료하고 컨테이너(`robingraph-api:test-fruit-routing-1a6f00caccaa`)를 배포했다. DB 쓰기 및 운영 배포, Git commit/push는 일체 수행하지 않는다.

---

## 1. 발생 현상 및 근본 원인 분석

### 발생 현상
- 브라우저 실측 스크린샷 질문인 `"참새목 새중에서 열매를 먹는 새는?"`을 입력했을 때, 참새목 중 열매를 먹는 20종 목록이 반환되지 않고 `title: "특정 열매 공유"`, `payload_status: "insufficient_data"`(자료 부족 안내)가 표출됨 (`before.json` 확인).

### 근본 원인 (`src/robingraph/retrieval/graph_questions.py`)
1. **과도한 plant 그룹 캡처**:
   - `specific_fruit` 패턴의 식물명 정규식 `(?P<plant>[가-힣]+)\s*열매`가 `"새중에서"`라는 조사·어미 표현을 식물 이름(`plant="새중에서"`)으로 잘못 캡처함.
2. **일반 목 열매 패턴의 어휘 누락**:
   - 일반 열매 질의(`order_fruit`) 패턴이 `"중"`, `"에서"`만 지원하고 `"새중에서"`, `"새 중에서"`, `"종 중에"` 등 분류군 뒤에 붙는 보조 표현을 수용하지 못함.
3. **패턴 판정 순서 미흡**:
   - 이전 코드에서 일반 열매(`order_fruit`) 매칭이 특정 식물(`specific_fruit`) 패턴보다 뒤에 위치하여, 오탐된 `specific_fruit`가 먼저 매칭됨.

---

## 2. 주요 코드 변경 및 해결 방안

### 수정 파일: `src/robingraph/retrieval/graph_questions.py`
1. **공통 `_ORDER_SCOPE` 정규식 정의**:
   ```python
   _ORDER_SCOPE = r'(?:에\s*속하는\s*)?(?:(?:새들?|종들?)\s*)?(?:중(?:에서|에)?|에서)'
   ```
   - `"새중에서"`, `"새 중에서"`, `"새들 중"`, `"종 중에"`, `"종들 중에서"`, `"에 속하는 새 중에서"` 등 다양한 자연어 범주 지정 표현을 안전하게 흡수하도록 일반화함.
2. **정규식 매칭 우선순위 재조정**:
   - 특정 식물 패턴(`specific_fruit`)보다 일반 목 열매 패턴(`order_fruit`)을 먼저 평가하도록 순서를 고정함.
   - 특정 식물 질문(예: `"참새목 새중에서 감나무 열매를 먹는 새는?"`)은 `plant="감나무"`로 정상 판정되어 기존 자료부족 안내(`insufficient_data`)가 그대로 유지됨.

---

## 3. 테스트 및 검증 결과

### 1) 단위 및 서비스 계층 회귀 검사
- **파서 단위 회귀 테스트 (`tests/test_graph_questions.py`)**:
  - `test_order_bird_group_words_are_not_mistaken_for_fruit_plants`: 5가지 표현(`'새중에서'`, `'새 중에서'`, `'종 중에'`, `'새들 중'`, `'에 속하는 새 중에서'`)에 대해 일반 열매(`order_fruit`) 및 특정 식물(`감나무`) 분기 10건 회귀 검증 통과.
- **API Mock 회귀 테스트 (`tests/test_graph_questions_api.py`)**:
  - `test_screenshot_order_bird_phrase_routes_to_general_fruit`: 스크린샷 질문이 `order_fruit`로 정상 라우팅되어 `answer`로 응답함을 검증 통과.
- **집중 테스트 스위트 실행 결과**:
  - `tests/test_graph_questions.py` + `tests/test_graph_questions_api.py`: **27건 전수 통과** (0 fail, 0 skip, 0.062s, `graph-tests.log`)
  - `tests/test_semantic_chat.py`: **22건 전수 통과** (0 fail, 0 skip, 0.238s, `semantic-tests.log`)
  - *비고*: 프런트엔드 UI 코드 무변경으로 프런트엔드 스위트 및 전체 Python 스위트는 재실행하지 않음.

### 2) 실제 TEST 환경 API 실측 (`actual-api.json`)
- 대상: 실제 배포된 TEST 컨테이너 루프백 엔드포인트 (`http://127.0.0.1:8000/v1/chat`, 모킹 없음)
- **6문항 전수 기대 결과 일치**:
  1. `"참새목 새중에서 열매를 먹는 새는?"`: `answer`, `title: "참새목 중 열매를 먹는 종"`, 20종 반환 (성공)
  2. `"참새목 새 중에서 열매를 먹는 새는?"`: `answer`, 20종 반환 (성공)
  3. `"참새목 종 중에 열매를 먹는 새는?"`: `answer`, 20종 반환 (성공)
  4. `"참새목 중 열매를 먹고 사는 새는?"`: `answer`, 20종 반환 (성공)
  5. `"참새목 새중에서 감나무 열매를 먹는 새는?"`: `abstain`, `insufficient_data`, 0종 반환 (정상 보류)
  6. `"숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는?"`: `abstain`, `insufficient_data`, 0종 반환 (정상 보류)

### 3) 실제 공개 TEST 서버 브라우저 실측 (`browser.json`, `browser.cjs`)
- 대상: `https://robingraph-test.dove-nest.com/chat` (Playwright Headless Chromium)
- **1280px 데스크톱 및 390px 모바일 실측**:
  - 스크린샷 문제 질문(`"참새목 새중에서 열매를 먹는 새는?"`) 전송 시 20종 카드 목록 정상 표출 (`fixed-1280.png`, `fixed-390.png` 캡처)
  - 가로 넘침 없음 (`scrollWidth > innerWidth === false`)
  - `pageerror` 0건 (콘솔 이벤트는 미수집)
  - *비고*: 외부 direct urllib 호출 시 HTTP 403이 관측되었으나, 실제 공개 브라우저 POST 및 로컬 TEST loopback API는 정상 200 통과함 (발생 계층 및 원인은 미확인 상태로 유지). 물리 모바일 기기는 미검증.

---

## 4. TEST 환경 배포 영수증 (`test-release.json`)

- **대상 인프라**: 16GB Mac mini .97 (`robingraph-api-test`, OrbStack)
- **배포 상태 (`state`)**: `verified`
- **최종 배포 이미지 (`image`)**: `robingraph-api:test-fruit-routing-1a6f00caccaa`
- **소스 SHA256 (`source_sha256`)**: `1a6f00caccaa3acb411b44f4a39171be46decc37716c0481136297099339c135`
- **베이스 리비전 (`base_revision`)**: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷)
- **릴리스 디렉터리 (`release`)**: `/Users/kimdove/robingraph-test/releases/fruit-routing-1a6f00caccaa-568651`
- **이전 이미지**: `robingraph-api:test-graph-ui-0d36c7d79044`
- **보조 검증**: `fixture_network_none_smoke: true`, `manage.sh verify` 통과, UI 에셋 무변경, DB/인덱스 무변경 (쓰기 0건), 운영 무변경, Git commit/push 없음.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
- 선행 작업기록:
  - 선행 기능 구현: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-관계-기반-질의응답-착수|RG-203 그래프 관계 질의응답 착수]]
  - 선행 UI 디자인: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-답변-UI-디자인-정리|RG-203 그래프 답변 UI 디자인 정리]]
- 검증 요약: [summary.json](../verification/assets/2026-10-22-fruit-question-routing/summary.json)
- 수정 전 오분류 증거: [before.json](../verification/assets/2026-10-22-fruit-question-routing/before.json)
- 실제 TEST API 실측: [actual-api.json](../verification/assets/2026-10-22-fruit-question-routing/actual-api.json)
- 브라우저 검증 결과: [browser.json](../verification/assets/2026-10-22-fruit-question-routing/browser.json)
- 브라우저 검증 스크립트: [browser.cjs](../verification/assets/2026-10-22-fruit-question-routing/browser.cjs)
- 단위 테스트 로그: [graph-tests.log](../verification/assets/2026-10-22-fruit-question-routing/graph-tests.log)
- 시맨틱 챗 테스트 로그: [semantic-tests.log](../verification/assets/2026-10-22-fruit-question-routing/semantic-tests.log)
- 배포 영수증: [test-release.json](../verification/assets/2026-10-22-fruit-question-routing/test-release.json)
- 데스크톱 스크린샷: [fixed-1280.png](../verification/assets/2026-10-22-fruit-question-routing/fixed-1280.png)
- 모바일 스크린샷: [fixed-390.png](../verification/assets/2026-10-22-fruit-question-routing/fixed-390.png)
- **실제 검증 자산 보존 위치** (`dev-codex`):
  `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-22-fruit-question-routing/`
