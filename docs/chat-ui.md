# RobinGraph 채팅 테스트 UI

`src/robingraph/api/static/`에 있는 정적 자산(`index.html`, `styles.css`,
`chat.js`)은 사람이 수동으로 `GET /health`와 `POST /v1/chat`를 눈으로
확인해 볼 수 있는 대화형(conversation-style) 테스트 화면이다. 별도의
프론트엔드 앱 스택(번들러, 프레임워크, 빌드 단계)이 아니며, FastAPI가
그대로 서빙할 수 있는 순수 HTML/CSS/바닐라 JS 3개 파일뿐이다.

## 통합 채팅 경로

`POST /v1/chat`은 기존 API를 대체하지 않는 추가 경로다. `question`은 공백이
아닌 최대 2,000자이며 `intent`는 `auto`, `taxonomy`, `observations`,
`evidence` 중 하나다. 명시 모드는 임베딩 없이 기존의 계통·관찰·문헌 조회
핸들러를 바로 사용한다. `auto`만 Jina 임베딩의 `retrieval.passage` 능력
프로토타입과 `retrieval.query` 질문 벡터를 비교한다. 임베딩 설정/제공자/형식,
신뢰도 또는 승자 차이가 불확실하면 조회하지 않고 안전한 한국어 추가 확인
응답을 반환한다. 유사도는 검색 경로 선택 신호일 뿐 사실을 생성하지 않는다.

응답의 `result`는 `kind`가 `taxonomy`, `observations`, `evidence`, `clarify`
중 하나인 판별 유니온이다. taxonomy에는 AviList 출처·릴리스·개념집합과 순서가
보장된 계통을, observations에는 기존 공개/비공개 좌표 및 출처 매퍼 결과를,
evidence에는 원문 발췌·인용·채널·hybrid fallback 경고를 담는다. 관찰 필터는
분류 키, 학명, 장소, 날짜, 1–10개의 제한만 제공하며 좌표나 미지원 일반명
필터는 노출하지 않는다. 관찰일이나 개념집합 릴리스를 검색/수집 기준시점으로
표시하지 않는다. 명시적 evidence 요청은 임베딩을 완전히 우회해 fulltext로
조회하고, `auto`가 evidence를 선택한 경우에만 hybrid 검색과 그 fallback
경고가 적용될 수 있다. 필터 없는 관찰 전체 조회는 실행하지 않는다.

## 정직하게 밝혀둘 것: LLM이 아니다

이 화면은 Hermes를 포함한 어떤 생성형 언어모델(LLM)도 사용하지 않는다.
기존 `/v1/answers`의 `answer_text`는 `QuestionService`
(`src/robingraph/slice.py`)가 그래프 근거를 결정론적 규칙으로 조합한다.
`/v1/chat`은 기존의 계통·관찰·문헌 핸들러 결과와 고정 한국어 설명만
반환하며, 근거가 부족하면 추측 대신 `disposition: "abstain"` 또는
`"clarify"`로 답변을 보류한다
([current-implementation.md](current-implementation.md)의 "Hermes 연동은
후속" 메모 참고). UI는 이 사실을 배너 문구로 명시적으로 드러내고,
Hermes/LLM이 이 화면의 답변을 만든다고 암시하는 문구는 두지 않는다.
Hermes(또는 다른 LLM)가 실제로 연동되면 이 문구부터 갱신해야 한다.

## 화면 구성과 상호작용

- **조회 유형과 필터**: 자동/분류/관찰/근거 모드를 선택할 수 있고 선택한
  명시 모드의 입력만 보인다. 관찰과 근거 결과 제한은 1–10으로 제한된다.
  자동 모드는 질문 외 필터를 보내지 않는다.
- **질문 입력**: `textarea#question-input`. `Enter`로 전송, `Shift+Enter`로
  줄바꿈(`chat.js`의 `keydown` 핸들러). `maxlength=2000`으로
  `QuestionRequest.question`의 서버 측 상한(2,000자)과 맞췄다. 한국어 등
  IME(입력기)로 글자를 조합하는 도중에는 `event.isComposing`이 `true`인
  동안 `Enter`를 눌러도 전송하지 않는다 — 일부 IME가 조합을 확정하는
  키 입력도 `Enter`로 보고하기 때문에, 이 가드가 없으면 조합 확정만
  하려던 `Enter`가 질문을 조기에 전송해버릴 수 있다. 조합이 끝난
  직후(`isComposing`이 다시 `false`)의 `Enter`는 평소대로 전송하고,
  `Shift+Enter`는 조합 상태와 무관하게 항상 줄바꿈만 한다. 요청이 끝나
  입력과 버튼이 다시 활성화된 뒤에만 질문 입력으로 포커스를 되돌리며,
  IME 조합 중이거나 요청 진행 중에는 포커스를 강제로 옮기지 않는다.
- **전송/지우기**: `button#send-button`(`type="submit"`, 폼 제출과 동일)과
  `button#clear-button`(`type="button"`, 클릭 시 대화 기록만 초기화).
- **진행 표시**: 요청 중에는 `#spinner`가 보이고, `#status-region`
  (`role="status" aria-live="polite"`)에 "답변을 불러오는 중입니다…"가
  뜨며, 입력/버튼이 비활성화된다.
- **대화 기록(page-session)**: `#history`(`role="log" aria-live="polite"`)
  는 이 탭이 열려 있는 동안만 유지되는 순수 JS 배열(`messages`)을
  반영한다. `localStorage`/`sessionStorage`/쿠키/서버 저장 어디에도 쓰지
  않으며, 두 `fetch` 호출은 모두 `credentials: "omit"`으로 실행되어
  기존 동일 오리진 쿠키도 보내거나 새 쿠키를 처리하지 않는다. 따라서
  새로고침하거나 "대화 지우기"를 누르면 사라진다 — 이 UI에는 영속성도
  로그인도 없다.
- **백엔드 모드 명시**: 로드 시 `GET /health`를 호출해 `mode`를
  `formatBackendMode`로 사람이 읽을 수 있는 한국어 문구로 바꿔
  `#backend-mode-value`에 표시한다 — `"fixture"`는
  "fixture (합성 데이터 · 문헌 검색 미지원)", `"neo4j"`는
  "neo4j (그래프 DB · 근거 기반 답변)", 그 밖의 비어 있지 않은 문자열은
  "지원되지 않는 모드: <원문 그대로>", 그 외(누락·빈 문자열·문자열이
  아닌 값)는 "확인 불가"로 표시한다. `/health` 호출 자체가 실패하면
  "확인 불가 (질문 API는 계속 시도할 수 있음)"으로 표시할 뿐 추측하지
  않는다.
- **disposition/보류(fail-closed)**: `formatDisposition`이 인식하는
  값은 `"answer"`("답변"), `"abstain"`("보류 (근거 부족)"),
  `"clarify"`("추가 확인 필요") 세 가지뿐이며, 오직 이 셋만 답변으로
  렌더링된다. `disposition`이 누락됐거나 이 셋과 정확히 일치하지 않는
  값(알 수 없는 문자열, 오타, 타입 오류 등)이면 `answer_text`와 원본
  상태 값을 모두 화면에 노출하지 않고, 고정된 안전 문구("지원되지 않는
  응답 형식을 받았습니다. 다시 시도해주세요.")를 오류 메시지로 보여준다
  (`sanitizeErrorMessage({ kind: "unsupported-response" })`) — 신뢰할
  수 없는 백엔드 응답 필드를 그대로 화면에 반영하지 않기 위한
  fail-closed 설계다.
- **citations/locator/license**: 각 `citations[]` 항목의 `source_id`,
  `locator`, `license_name`을 모두 표시한다. `source_url`이 안전한
  절대 `http(s)` URL일 때만 클릭 가능한 링크로 만들고, 그렇지 않으면
  (`javascript:`, `data:`, 프로토콜 상대 URL 등) 링크를 만들지 않고
  일반 텍스트로만 보여준다 — 아래 "보안 결정" 참고.
- **warnings**: `warnings[]`를 목록으로 그대로 노출한다(예: hybrid
  검색이 fulltext로 대체됐다는 경고 등, 다른 엔드포인트와 동일한 패턴).
- **오류 처리**: 네트워크 실패, 그리고 HTTP 상태 코드
  400/401/403/404/422/429/503 각각에 대해 짧고 정직한 **고정** 한국어
  메시지를 보여준다(`sanitizeErrorMessage`). 서버가 함께 보낸 `detail`
  문자열은 400/422를 포함해 **어떤 상태 코드에서도 읽지도, 화면에
  보여주지도 않는다** — 이 UI 입장에서 `detail`은 신뢰할 수 없는
  입력이며(비밀 값, 내부 URL·경로, 제어 문자, 임의 길이의 텍스트가 섞여
  들어올 수 있음), 화면에 노출해도 되는 정직한 문구인지 매 상태 코드마다
  검증하는 대신 아예 참조하지 않는 편이 안전하다. 위 목록에 없는 그 밖의
  상태 코드는 "서버 오류가 발생했습니다 (상태 코드 N)"으로 뭉뚱그린다.
  원본 예외 메시지나 스택 트레이스는 절대 화면에 그대로 노출하지 않는다.

## 접근성: 명도 대비(WCAG 2.1 AA)

`#send-button`(전송 버튼)의 글자색과 배경색, 그리고 `.disposition-answer`/
`.disposition-abstain`/`.disposition-clarify` 배지의 글자색과 배경색은
라이트·다크 모드 모두 WCAG 2.1 AA 기준(일반 텍스트 4.5:1 이상)을 만족
한다. `styles.css`는 이를 위해 `--send-button-text`,
`--badge-answer-text`, `--badge-abstain-text` 커스텀 프로퍼티를 두어
버튼·배지 배경이 테마별로 바뀔 때 글자색도 함께 바뀌도록 했다(예: 다크
모드에서 `--color-accent`가 밝은 초록으로 바뀌므로 전송 버튼 글자는
흰색 대신 어두운 글자색을 쓴다). `tests/frontend/chat_ui.test.js`가
`styles.css`의 실제 선언을 파싱해 각 조합의 대비를 계산하고 4.5 이상인지
검증한다 — 색상 값을 바꿀 때는 반드시 이 테스트를 다시 통과시켜야 한다.

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
- **동일 오리진만 호출**: `chat.js`는 `/health`, `/v1/chat` 두
  상대 경로만 `fetch`하며, 코드 안에 절대 URL 리터럴이 전혀 없다
  (테스트가 소스에 `http://`/`https://` 문자열이 없는지 검사한다).
  두 호출 모두 `credentials: "omit"`을 명시하므로 동일 오리진의 기존
  쿠키를 전송하거나 응답의 `Set-Cookie`를 처리하지 않는다. 이 화면은
  CORS 없이, 이 API를 서빙하는 오리진에서 열릴 때만 동작하도록 설계했다.
- **입력·비밀정보 없음**: 이 화면은 인증도, API 키 입력도, 어떤 비밀도
  다루지 않는다. 질문 텍스트만 그대로 서버로 보낸다.

## 서버 통합

`create_app()`은 `/`와 `/chat`에서 채팅 셸을, `/static/`에서 JS·CSS를
제공한다. 같은 앱 팩터리를 쓰는 `serve-fixture`와 `serve-neo4j`에 모두
적용되며, `pyproject.toml`의 package-data 설정이 wheel에도 세 정적 자산을
포함한다. 요청마다 `index.html`, `chat.js`, `styles.css` 세 파일을 모두
일반 파일·0바이트 초과·읽기 가능 상태인지 같은 열린 파일 설명자에서 확인한 뒤
읽은 바이트를 응답한다. 따라서 패키지에서 자산이 누락되거나 일부만 있거나,
0바이트이거나, 읽을 수 없더라도 API와 `/health`는 시작하고 UI 경로만 내부 파일
경로를 노출하지 않는 고정 일반 HTTP 503으로 실패한다.

## 로컬에서 눈으로 확인하기

```sh
uv run --locked robingraph serve-fixture
```

`http://127.0.0.1:8000/` 또는 `http://127.0.0.1:8000/chat`을 열면 같은
오리진에서 `/health`, `/v1/chat`를 호출하는 화면을 확인할 수 있다.
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
- `chat.js`가 `/health`, `/v1/chat` 외의 URL을 호출하지 않는다.
- 최소 DOM의 실제 `fetch` 호출을 캡처해 두 요청의 URL이 정확히 상대
  경로이고 각각 `credentials: "omit"`인지 확인한다.
- `sanitizeUrl`이 `javascript:`/`data:`/프로토콜 상대 URL 등 위험한
  스킴을 모두 거부하고, 정상적인 `http(s)` URL만 통과시킨다.
- `formatDisposition`, `sanitizeErrorMessage`가 정직하고 안전한 한국어
  문구를 만들며, 원본 오류를 그대로 노출하지 않는다. 비밀 값·내부
  URL·경로·제어 문자·매우 긴 텍스트가 섞인 적대적인 `detail` 페이로드를
  400/422에 주더라도 고정 문구만 나오고 원본 값은 전혀 새어 나오지
  않는다.
- 전송 버튼과 답변/보류/추가 확인 배지의 글자·배경 대비를
  `styles.css`의 실제 선언에서 계산해 라이트·다크 모드 모두 WCAG 2.1
  AA(4.5:1) 이상인지 검증한다.
- `chat.js`의 `keydown` 핸들러를 실제 이벤트 경로 그대로(가짜
  DOM에 `keydown`을 디스패치 → `preventDefault`/`form.requestSubmit()`
  → `submit` 핸들러 실행) 구동해, `Enter`(조합 중 아님)는 전송하고
  `event.isComposing`이 `true`인 동안의 `Enter`는 무시하며,
  `Shift+Enter`는 조합 상태와 무관하게 항상 줄바꿈만 하는지 확인한다.
  같은 경로에서 요청이 끝난 뒤에만 포커스를 복원하고, 진행 중 또는 IME
  조합 중에는 포커스를 빼앗지 않는지도 확인한다. Playwright 등 브라우저
  없이 순수 Node 객체로 구현한 최소 DOM이다.
- 실제 `submit` 이벤트 경로에서 악의적 또는 형식이 잘못된 2xx payload가
  오면 고정 오류만 렌더링되고 공격자 제공 disposition/answer/warning 텍스트가
  결과에 남지 않는지 확인한다.
- `index.html`에 필요한 인터랙션 요소·접근성 라벨
  (`question-input`, `send-button`, `clear-button`, `history`,
  `backend-mode-value`, `status-region`, `role="log"`,
  `role="status"`, `aria-live`, `Shift+Enter` 안내 등)이 실제로
  존재한다.
- `index.html`이 Hermes/LLM을 이 화면의 답변 생성 주체로 주장하지
  않는다(부정문으로만 언급한다).

Python API 계약 테스트(`tests/test_api.py`)는 fixture와 모의 Neo4j 모드의
페이지·정적 자산 경로, 자산 누락 시 안전한 503, 기존 답변 계약을 함께 검사한다.
