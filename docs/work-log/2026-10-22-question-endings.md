# [RG-203] 질의 공통 어미(_ASK) 확장 및 대규모 조합 검증 — 2026-10-22

> **문서 상태: TEST 검증 완료 (운영 배포 승인 대기)**
> RG-203 그래프 관계 질의 중 `"참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?"` 질의가 결정론적 파서의 공통 의문 종결 표현(`_ASK`) 미지원으로 인해 `clarify`(질문 종류 재선택 안내)로 응답하던 문제를 해결했다. 선행 단건 어휘 보완(`새중에서`, `나무열매`)의 공백을 체계적으로 극복하기 위해 공통 `_ASK` 정규식을 범용 의문 표현(`어떤게 있어`, `뭐가 있어`, `있을까`, `알고 싶어` 등)으로 확장하고, 664개 하위 케이스로 구성된 대규모 조합 회귀 검증을 도입했다. 전체 Python 테스트 1,062건(1,023 통과 / 39 skip / 0 fail), 실제 TEST 루프백 API 28건 전수 통과, 공개 TEST 서버 Playwright Chromium(1280px/390px) 2건 실측을 완료하고 신규 TEST 컨테이너(`robingraph-api:test-question-endings-203d19900989`)를 배포했다. DB 쓰기 및 운영 배포, Git commit/push는 일체 수행하지 않는다.

---

## 1. 발생 현상 및 원인 분석

### 발생 현상
- 사용자 재현 질문인 `"참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?"` 입력 시, 의도된 열매 먹이 종 목록 대신 `disposition: "clarify"`, `answer_text: "질문의 종류를 판단하지 못했습니다..."`가 반환됨 (`before.json` 확인).

### 원인 분석 및 배경 (`src/robingraph/retrieval/graph_questions.py`)
1. **공통 의문 종결 표현(`_ASK`) 미지원 (근본 원인)**:
   - 결정론적 파서의 공통 의문 표현 정규식 `_ASK`가 명령형(`알려줘`, `보여줘`) 및 단순 종결부(`?`, `은`, `는`) 위주로 구성되어 있어, 구어체 및 자연스러운 질문 종결부인 `"어떤게 있어"`, `"어떤 게 있어"`, `"뭐가 있어"`, `"알고 싶어요"` 등을 매칭하지 못함.
2. **단건 어휘 보완 반복의 공백 보완 필요성**:
   - 선행 작업에서 `"새 중에서"`, `"나무열매"` 등 명사구/조사 표현을 순차 보완했으나, 질문 뒤에 붙는 자연스러운 종결 어미가 누락되어 동일 질문군이 다시 실패하는 현상이 발생함.
   - 따라서 개별 종 예외나 특정 어휘의 땜질 처리가 아니라, 모든 그래프 질의 패턴이 공유하는 공통 `_ASK`를 확장하고 체계적인 조합 회귀 매트릭스를 구성해 검증한 조합의 누락을 보완함.

---

## 2. 주요 코드 변경 및 데이터 경계 처리

### 수정 파일: `src/robingraph/retrieval/graph_questions.py`
1. **공통 `_ASK` 패턴 확장**:
   - `(?:어떤|어느)\s*(?:게|것들?|종들?|새들?)(?:이|가)?`: `"어떤게 있어"`, `"어느 것이 있나요"`, `"어떤 새들이 있습니까"` 등 수용.
   - `뭐가|무엇이`: `"뭐가 있어"`, `"무엇이 있니"` 등 수용.
   - `있니|있어(?:요)?|있나요|있을까(?:요)?|있습니까|있는지|알고\s*싶어(?:요)?`: 다양한 서술/의문형 종결 어미 수용.
   - 이 공통 패턴은 `order_fruit`뿐만 아니라 `common_taxonomy`, `same_genus`, `korea_same_genus`, `specific_fruit`, `habitat_shared_diet`, `habitat_different_diet` 등 7개 그래프 질의 유형에 동일하게 적용됨.
2. **개별 종 예외 배제 및 무결성 유지**:
   - 개별 종에 대한 하드코딩 예외 처리 없음 (`no per-species special casing`).
   - 기존 데이터 조회 조건, Cypher 쿼리 구조, DB 스키마, UI 렌더링 계약 변경 없음.
   - `"나무열매"` 질의에 대한 `criterion='tree_fruit_share'` 보존 및 응답 제목 `(나무·풀 구분 없음)`, `limitations` 고지 그대로 유지.
   - 특정 식물 열매(`specific_fruit`, 감나무/직박구리 같은 열매) 질문은 계속해서 `insufficient_data` 정상 보류.
   - 질문 뒤에 무관한 술어나 추가 의도가 붙은 경우(예: `'기후변화에는 어떤 게 있어?'`, `'...어디에서 사냥해?'`)는 `_ASK`로 흡수하지 않고 `None`으로 엄격히 거부.

---

## 3. 테스트 및 검증 결과

### 1) 단위 및 회귀 자동화 테스트
- **대규모 조합 회귀 검증 (`tests/test_graph_questions.py`)**:
  - `test_fruit_wording_matrix_and_common_question_endings`:
    - 단일 테스트 메서드 내에서 총 **664개 하위 케이스(subcases)** 전수 검증 통과 (`not_independent_test_methods: true`).
    - 케이스 구성:
      1. 일반 열매 + 나무열매 조합: 7개 수식 그룹 x 6개 먹이 표현 x 12개 어미 = **504건**
      2. 특정 식물(감나무 등) 경계 보존: 7개 수식 그룹 x 12개 어미 = **84건**
      3. 기타 6대 그래프 질의 유형 x 12개 어미 = **72건**
      4. 무관한 질의 및 추가 의도 거부 = **4건**
- **API Mock 회귀 (`tests/test_graph_questions_api.py`)**:
  - `test_natural_question_ending_bypasses_semantic_fallback`:
    - 시맨틱 라우터로의 fallback을 우회하여 결정론적 그래프 핸들러로 라우팅됨을 검증 통과 (`router.classify` 미호출 확인).
    - graph handler에 `parsed.criterion='tree_fruit_share'`가 정상 전달되고 mock 응답 `answer` 반환 확인.
    - *주의*: `tree_fruit_share`는 내부 파서 기준이며 실제 API response payload의 criterion 필드는 `diet_distribution`임.
- **전체 Python 자동화 테스트 스위트 (`full-python-tests.log`)**:
  - 실행 명령: `uv run --locked --extra test --extra tracing python -m unittest discover -s tests`
  - 결과: **총 1,062건 실행 / 1,023건 통과 / 39건 skip / 0건 실패** (소요 시간: 22.632초).
  - *건너뜀(39건) 범위*: opt-in 통합 테스트 및 외부 RG-406 재현 번들 파일(`/tmp/rg406-avilist.json`) 부재에 따른 제외 포함 (**전부 opt-in이 아님**).
  - *환경 구분*: 단위/전체 Python 스위트는 Mock/Fixture 환경을 사용하며, 실서버 검증은 아래 실제 TEST 실측 결과로 구분함.
  - *프런트엔드 스위트*: UI 자산 무변경으로 프런트엔드 테스트 스위트는 미재실행.

### 2) 실제 TEST 환경 API 실측 (`actual-api.json`)
- 대상: 실제 배포된 TEST 컨테이너 루프백 엔드포인트 (`http://127.0.0.1:8000/v1/chat`, 모킹 없음)
- 결과: **총 28문항 전수 기대 결과 일치 (통과율 100%)**:
  1. 12개 어미 변형 x 일반 열매 / 나무열매 = **24문항**: 전부 `disposition: "answer"`, `kind: "graph_query"`, 최대 20종 표시 (성공).
  2. 특정 식물 / 같은 열매 질문 = **2문항** (`"참새목 새 중에서 감나무 열매를 먹는 새는 어떤게 있어?"`, `"숲에 사는 새 중 직박구리랑 같은 열매를 먹는 새는 어떤 게 있어?"`): `disposition: "abstain"`, `insufficient_data`, 0종 반환 (정상 보류).
  3. 선행 픽스 검증 질문 = **2문항** (`"참새목 새중에서 열매를 먹는 새는?"`, `"참새목 새 중에서 나무열매를 먹는 새는?"`): 정상 `answer`, 최대 20종 표시 (성공).
- *참고*: 반환된 20종은 응답 표시 상한(`limit=20`)이며 전체 종 수가 아님.

### 3) 실제 공개 TEST 서버 브라우저 실측 (`browser.json`, `browser.cjs`)
- 대상: `https://robingraph-test.dove-nest.com/chat` (Playwright Headless Chromium)
- **1280px 데스크톱 및 390px 모바일 실측 (각 1건, 총 2건 통과)**:
  - 재현 대상 스크린샷 질문(`"참새목 새 중에서 나무 열매를 먹는 새는 어떤게 있어?"`) 입력 시 20종 카드 목록 정상 표출 (`fixed-1280.png`, `fixed-390.png` 캡처).
  - 응답 패널 내 `참새목 중 열매를 먹는 종` 및 `(나무·풀 구분 없음)` 문구 정상 노출 확인 (`tree_grass_limit_title_visible: true`).
  - 가로 넘침 없음 (`scrollWidth > innerWidth === false`).
  - `pageerror` 0건 (콘솔 이벤트는 미수집).
  - *한계*: 물리 모바일 기기 및 Safari, Firefox 브라우저는 미검증.

---

## 4. TEST 환경 배포 영수증 (`test-release.json`)

- **대상 인프라**: 16GB Mac mini .97 (`robingraph-api-test`, OrbStack)
- **배포 상태 (`state`)**: `verified` (컨테이너 헬스체크 통과)
- **최종 배포 이미지 (`image`)**: `robingraph-api:test-question-endings-203d19900989`
- **소스 SHA256 (`source_sha256`)**: `203d199009891d892caecfddd129cd68b5cb9d19611c43f269baf509c6fe750e`
- **베이스 리비전 (`base_revision`)**: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷)
- **릴리스 디렉터리 (`release`)**: `/Users/kimdove/robingraph-test/releases/question-endings-203d19900989-1aeccb`
- **이전 이미지**: `robingraph-api:test-tree-fruit-b1c6c45cd346`
- **이전 릴리스**: `/Users/kimdove/robingraph-test/releases/tree-fruit-b1c6c45cd346-da9d5c`
- **보조 검증**: `fixture_network_none_smoke: true` (격리 픽스처 스모크 통과), `manage.sh verify` 통과, 소스 manifest 일치(`source_manifest_matches: true`), `graphify update .` 통과, UI 에셋 무변경, DB/인덱스 무변경 (쓰기 0건), 새 기술/특정 식물 데이터 추가 없음, 운영 무변경, Git commit/push 없음.

---

## 5. 한계 및 유의사항

1. **유한 결정론 문법의 한계**:
   - 본 수정은 결정론적 정규식 파서의 공통 의문 패턴을 대폭 확장한 것이며, 자연어로 유입될 수 있는 모든 표현 형식을 완전히 커버한다고 확언할 수 없음.
2. **미검증 환경**:
   - UI 마크업/스타일 무변경으로 프런트엔드 테스트 스위트는 재실행하지 않음.
   - 실제 물리 모바일 기기 및 Safari, Firefox 브라우저에서의 렌더링은 별도 검증되지 않음.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
- 선행 작업기록:
  - 선행 기능 구현: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-관계-기반-질의응답-착수|RG-203 그래프 관계 질의응답 착수]]
  - 선행 UI 디자인: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-그래프-답변-UI-디자인-정리|RG-203 그래프 답변 UI 디자인 정리]]
  - 선행 버그 수정: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-열매-질의-라우팅-버그-수정|RG-203 열매 질의 '새중에서' 라우팅 버그 수정]]
  - 선행 보완 작업: [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-22-RG203-나무열매-질의-라우팅-보완|RG-203 '나무열매' 질의 라우팅 보완]]
- 검증 요약: [summary.json](../verification/assets/2026-10-22-question-endings/summary.json)
- 수정 전 clarify 응답 증거: [before.json](../verification/assets/2026-10-22-question-endings/before.json)
- 실제 TEST API 실측 (28문항): [actual-api.json](../verification/assets/2026-10-22-question-endings/actual-api.json)
- 브라우저 검증 결과: [browser.json](../verification/assets/2026-10-22-question-endings/browser.json)
- 브라우저 검증 스크립트: [browser.cjs](../verification/assets/2026-10-22-question-endings/browser.cjs)
- 전체 Python 테스트 로그: [full-python-tests.log](../verification/assets/2026-10-22-question-endings/full-python-tests.log)
- 배포 영수증: [test-release.json](../verification/assets/2026-10-22-question-endings/test-release.json)
- 데스크톱 스크린샷: [fixed-1280.png](../verification/assets/2026-10-22-question-endings/fixed-1280.png)
- 모바일 스크린샷: [fixed-390.png](../verification/assets/2026-10-22-question-endings/fixed-390.png)
- **실제 검증 자산 보존 위치** (`dev-codex`):
  `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-22-question-endings/`
