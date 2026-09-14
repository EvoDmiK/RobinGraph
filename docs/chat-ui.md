# RobinGraph 채팅 테스트 UI

`src/robingraph/api/static/`에 있는 정적 자산(`index.html`, `styles.css`,
`chat.js`)은 사람이 수동으로 `GET /health`와 `POST /v1/answers`를 눈으로
확인해 볼 수 있는 대화형(conversation-style) 테스트 화면이다. 별도의
프론트엔드 앱 스택(번들러, 프레임워크, 빌드 단계)이 아니며, FastAPI가
그대로 서빙할 수 있는 순수 HTML/CSS/바닐라 JS 3개 파일뿐이다.

## 정직하게 밝혀둘 것: LLM이 아니다

이 화면은 Hermes를 포함한 어떤 생성형 언어모델(LLM)도 사용하지 않는다.
`answer_text`는 `QuestionService`(`src/robingraph/slice.py`)가 그래프
근거를 결정론적 규칙으로 조합해 만든 문자열이며, 근거가 부족하면
추측 대신 `disposition: "abstain"`으로 답변을 보류한다
([current-implementation.md](current-implementation.md)의 "Hermes 연동은
후속" 메모 참고). UI는 이 사실을 배너 문구로 명시적으로 드러내고,
Hermes/LLM이 이 화면의 답변을 만든다고 암시하는 문구는 두지 않는다.
Hermes(또는 다른 LLM)가 실제로 연동되면 이 문구부터 갱신해야 한다.

## 화면 구성과 상호작용

- **질문 입력**: `textarea#question-input`. `Enter`로 전송, `Shift+Enter`로
  줄바꿈(`chat.js`의 `keydown` 핸들러). `maxlength=2000`으로
  `QuestionRequest.question`의 서버 측 상한(2,000자)과 맞췄다.
- **전송/지우기**: `button#send-button`(`type="submit"`, 폼 제출과 동일)과
  `button#clear-button`(`type="button"`, 클릭 시 대화 기록만 초기화).
- **진행 표시**: 요청 중에는 `#spinner`가 보이고, `#status-region`
  (`role="status" aria-live="polite"`)에 "답변을 불러오는 중입니다…"가
  뜨며, 입력/버튼이 비활성화된다.
- **대화 기록(page-session)**: `#history`(`role="log" aria-live="polite"`)
  는 이 탭이 열려 있는 동안만 유지되는 순수 JS 배열(`messages`)을
  반영한다. `localStorage`/`sessionStorage`/쿠키/서버 저장 어디에도 쓰지
  않으므로 새로고침하거나 "대화 지우기"를 누르면 사라진다 — 이 UI에는
  영속성도 로그인도 없다.
- **백엔드 모드 명시**: 로드 시 `GET /health`를 호출해 `mode`
  (`"fixture"` 또는 Neo4j 백엔드 이름)를 `#backend-mode-value`에 그대로
  표시한다. 실패하면 "확인 불가"로 표시할 뿐 추측하지 않는다.
- **disposition/보류**: `AnswerResponse.disposition`이 `"answer"`면
  "답변" 배지, `"abstain"`이면 "보류 (근거 부족)" 배지를 붙인다
  (`formatDisposition`). 알 수 없는 값이 오더라도 그대로 텍스트로 보여줄
  뿐 화면이 깨지지 않는다.
- **citations/locator/license**: 각 `citations[]` 항목의 `source_id`,
  `locator`, `license_name`을 모두 표시한다. `source_url`이 안전한
  절대 `http(s)` URL일 때만 클릭 가능한 링크로 만들고, 그렇지 않으면
  (`javascript:`, `data:`, 프로토콜 상대 URL 등) 링크를 만들지 않고
  일반 텍스트로만 보여준다 — 아래 "보안 결정" 참고.
- **warnings**: `warnings[]`를 목록으로 그대로 노출한다(예: hybrid
  검색이 fulltext로 대체됐다는 경고 등, 다른 엔드포인트와 동일한 패턴).
- **오류 처리**: 네트워크 실패와 4xx/404/422/503/그 외 5xx를 구분해
  짧고 정직한 한국어 메시지로만 보여준다(`sanitizeErrorMessage`).
  원본 예외 메시지나 스택 트레이스는 절대 화면에 그대로 노출하지 않는다.

## 보안 결정

- **`innerHTML`/`insertAdjacentHTML`/`document.write`/`eval` 미사용**:
  모든 동적 콘텐츠는 `textContent`/`createElement`로만 DOM에 들어간다.
  이 규칙은 `tests/frontend/chat_ui.test.js`가 소스 코드를 정적으로
  검사해 강제한다.
- **`source_url` 스킴 검증(`sanitizeUrl`)**: `textContent`만으로는 막을 수
  없는 남은 주입 경로가 하나 있다 — 근거 문서의 `source_url`이 악의적인
  값(`javascript:...`)이라면 그걸 그대로 `<a href>`에 넣었을 때 클릭 시
  실행될 수 있다. `sanitizeUrl`은 절대 `http(s)` URL만 통과시키고, 그 외
  스킴이나 프로토콜 상대 URL(`//evil/x`)은 `null`을 반환해 호출부가
  일반 텍스트로만 렌더링하게 만든다.
- **동일 오리진만 호출**: `chat.js`는 `/health`, `/v1/answers` 두
  상대 경로만 `fetch`하며, 코드 안에 절대 URL 리터럴이 전혀 없다
  (테스트가 소스에 `http://`/`https://` 문자열이 없는지 검사한다).
  이 화면은 CORS 없이, 이 API를 서빙하는 오리진에서 열릴 때만 동작하도록
  설계했다.
- **입력·비밀정보 없음**: 이 화면은 인증도, API 키 입력도, 어떤 비밀도
  다루지 않는다. 질문 텍스트만 그대로 서버로 보낸다.

## 서버 통합

`create_app()`은 `/`와 `/chat`에서 채팅 셸을, `/static/`에서 JS·CSS를
제공한다. 같은 앱 팩터리를 쓰는 `serve-fixture`와 `serve-neo4j`에 모두
적용되며, `pyproject.toml`의 package-data 설정이 wheel에도 세 정적 자산을
포함한다. 패키지에서 자산이 누락되더라도 API와 `/health`는 시작하고 UI
경로만 내부 파일 경로를 노출하지 않는 일반적인 HTTP 503으로 실패한다.

## 로컬에서 눈으로 확인하기

```sh
uv run --locked robingraph serve-fixture
```

`http://127.0.0.1:8000/` 또는 `http://127.0.0.1:8000/chat`을 열면 같은
오리진에서 `/health`, `/v1/answers`를 호출하는 화면을 확인할 수 있다.
Neo4j 테스트 인스턴스가 준비된 경우에는 `serve-neo4j`로 같은 URL을 쓴다.
`index.html`을 `file://`로 직접 열면 동작하지 않는 것이 정상이다.

## 테스트

브라우저 자동화(Playwright/Selenium/CDP 등)는 쓰지 않는다. 대신
`tests/frontend/chat_ui.test.js`가 Node 내장 테스트 러너로 다음을
확인한다:

```sh
node --test tests/frontend/chat_ui.test.js
```

- `chat.js`의 실행 코드(주석 제외)에 `innerHTML` 등 주입 경로가 없다.
- `chat.js`가 `/health`, `/v1/answers` 외의 URL을 호출하지 않는다.
- `sanitizeUrl`이 `javascript:`/`data:`/프로토콜 상대 URL 등 위험한
  스킴을 모두 거부하고, 정상적인 `http(s)` URL만 통과시킨다.
- `formatDisposition`, `sanitizeErrorMessage`가 정직하고 안전한 한국어
  문구를 만들며, 원본 오류를 그대로 노출하지 않는다.
- `index.html`에 필요한 인터랙션 요소·접근성 라벨
  (`question-input`, `send-button`, `clear-button`, `history`,
  `backend-mode-value`, `status-region`, `role="log"`,
  `role="status"`, `aria-live`, `Shift+Enter` 안내 등)이 실제로
  존재한다.
- `index.html`이 Hermes/LLM을 이 화면의 답변 생성 주체로 주장하지
  않는다(부정문으로만 언급한다).

Python API 계약 테스트(`tests/test_api.py`)는 fixture와 모의 Neo4j 모드의
페이지·정적 자산 경로, 자산 누락 시 안전한 503, 기존 답변 계약을 함께 검사한다.
