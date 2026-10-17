# 후보 선택 후 질문을 종 이름으로 표시·NAS TEST 배포

## 요청 배경과 목표

사용자가 후보 선택 후 `Anas platyrhynchos에 대해 알고 싶어`라는 질문이 채팅에 들어가는 것을 보여주며 종 이름으로 표시하도록 요청했다. 검토 국명이 있는 후보는 `청둥오리에 대해 알고 싶어`처럼 읽을 수 있게 표시하고, 먹이 등 원래 질문 주제를 유지하는 것이 목표다. 실제 조회 대상은 선택한 후보 그대로 유지해야 한다.

## 확인한 원인과 변경 전후

API는 후보 확인용 question의 오타 이름을 정규 학명으로 바꾸어 반환했다. UI는 이를 `appendUserMessage(question)`와 실제 제출에 함께 사용하므로 학명이 사용자 말풍선에 그대로 나타났다. 검색 실패나 잘못된 종 조회 문제가 아니라, 식별용 질문과 사용자 표시가 같은 문자열을 사용하는 문제였다.

변경 후 후보의 검토된 `display_name`을 질문 표시용으로 사용한다. 후보 질문의 학명 부분만 표시 이름으로 바꾸고 나머지 문장은 그대로 둔다. 검토 국명이 없으면 기존 학명 표시를 유지한다. API가 반환한 확인용 질문과 profile 이름 필터는 학명을 그대로 사용하여 다른 종으로 해소되거나 고급 필터에 남은 이름으로 대상이 바뀌지 않게 했다.

| 선택 후 상황 | 사용자 말풍선 | 실제 조회 |
|---|---|---|
| 청둥오리 일반 질문 | 청둥오리에 대해 알고 싶어 | Anas platyrhynchos |
| 청둥오리 먹이 질문 | 청둥오리는 뭘 먹어? | 같은 종·diet 주제 |
| 표시 이름이 없는 후보 | 기존 학명 질문 | 같은 학명 |

표시와 실제 API 요청을 구분한다. POST의 question·filters.name은 기존 정규 학명이며 화면에만 국명 질문을 보여준다. 질문 원문, 확인 대화, busy/대화 초기화 guard, 영구 별칭을 저장하지 않는 정책은 그대로다. 후보 버튼의 국명·학명 병기, API 계약과 Neo4j 검색·색인 정책은 이번 변경 범위가 아니다.

## 변경 파일과 구현

- `src/robingraph/api/static/chat.js`: 기존 후보 콜백에 displayName을 전달한다. 표시 이름이 있으면 callback의 질문에서 학명 한 부분만 안전한 치환 함수로 바꾸어 appendUserMessage에 넣는다. 실제 submitQuestion에는 기존 question과 학명 필터를 전달한다. 말풍선은 기존 textContent 경로로 표시한다.
- `tests/frontend/chat_ui.test.js`: 먹이 확인 말풍선이 국명이고 학명이 드러나지 않는지, 실제 요청은 정규 학명인지 확인한다. 일반 질문도 국명으로 표시하고 이름이 없으면 학명으로 대체하는 검사를 추가했다.
- 실제 브라우저 검증 코드·JSON·스크린샷과 작업 기록을 추가했다. API/Python 소스·DB schema/data·벡터는 수정하지 않았다.

기존 Antigravity 후보 UI를 재사용한 Codex의 최소 통합 후속 수정이다. 이번 작은 표시 변경으로 별도 에이전트 구현 작업을 새로 배정하지 않았다.

## 검증 방법과 실제 결과

`node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`를 실행해 307개 전부 통과했다(실패·제외0). fake DOM·fixture 검사이며 실제 DB 검증과 구분한다. 새 검사 초기에 수집한 말풍선 텍스트에 기존 사용자 라벨 `나`가 포함되어 문자열 전체 비교가 실패했다. 검증 대상을 질문 부분으로 맞춘 뒤 다시 실행해 통과했다. 제품 코드의 실패를 fixture 결과로 감추지 않았다.

NAS TEST의 실제 DB/Jina/API를 사용하는 Chromium에서1280·390·320px를 검사했다. 각 화면의5회 채팅 요청, 총15회가 통과했다. API route mock은 사용하지 않았다.

1. 공백 정상 이름 질문 → 청둥오리 graph_normalized 답변.
2. 천둥오리 먹이 질문 → 후보 표시.
3. 후보를 Enter로 선택 → `청둥오리는 뭘 먹어?` 말풍선·같은 종의 diet 답변. 고급 필터에 까치가 남아 있어도 선택한 종의 학명으로 조회.
4. 천둥오리 일반 질문 → 후보 표시.
5. 후보 클릭 → `청둥오리에 대해 알고 싶어` 말풍선·Anas platyrhynchos 답변. 실제 POST question과 profile 이름 필터는 학명으로 유지됨을 캡처해 확인.

각 화면에서 후보 렌더링의 자동 전송 없음, 후보44px 높이, 키보드 선택, JS pageerror0, 가로 넘침 없음을 확인했다.390px 스크린샷에서도 국명 질문을 직접 확인했다. 화면 폭 에뮬레이션이며 물리 모바일 검사로 표현하지 않는다. SSH 포워딩으로 NAS 컨테이너에 직접 연결한 검사이고 공개 도메인 경유 검사는 아니다. 검증 후 포워딩을 해제했다.

배포된 `scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json`도 passed=true, backend_reachable=true, contract_parity_ok=true였다. Python 소스가 같고 runtime에서 chat.js만 달라 전체 Python896개 검사를 반복하지 않았다. 이전 Python 통과 결과를 이번에 재실행한 결과로 표시하지 않는다.

## NAS TEST 배포·소스 확인

기준 커밋 `434b6a4be8493f9b8bd85f477cbe8aca65ec7413` + 이전 협업 미커밋 overlay를 보존한 runtime 스냅샷이다. 직전0b3da8484953 스냅샷과138개 파일 해시를 비교해 chat.js만 달라짐을 확인했다. 이전 Neo4j 이름 벡터 이전·오타 보완·MRR 수정 등을 되돌리지 않았다. 비밀 환경 파일·AGENTS·MCP 설정은 포함하지 않았다.

- 스냅샷 SHA-256: `71b1b0f58a62b586f97faf671fd7370a8338d4e2fa310048797081cbd22e8770`.
- 아카이브 SHA-256: `bfa9566d58bcfe29099afbaad495a9c812b237e03a182d69b691d9d8ebb86794`.
- 릴리스: `/home/<nas-user>/robingraph-name-neo4j-71b1b0f58a62`.
- 이미지: `robingraph-api:test-name-neo4j-71b1b0f58a62`.
- 이미지 ID: `sha256:90b7ae5d64d4278fa64a96eb522a37e8c08268a969ce067b926bf56ecb6737eb`.
- OCI revision: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-name-neo4j-71b1b0f58a62`.
- TEST 컨테이너 ID: `0d5cc225311750266cb1206a681694e92f59acfff1b4054b13ee694259c3d861`.
- TEST 시작: `2026-10-15T10:26:25.357390565Z`, running·healthy.

legacy scp 전송 후138개 파일 해시를 원격에서 재검사했다. 기존 TEST 환경 사본에서 이미지·revision만 변경하여 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy`를 실행했다. 배포된 overlay12개 파일 해시도 manifest와 모두 일치했다. 재색인이나 DB 쓰기는 하지 않았다.

운영 컨테이너 ID `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`, 시작 `2026-10-10T06:07:33.413088244Z`, 이미지 `robingraph-api:prod-approved-ui-0681747`은 그대로임을 대조했다. Production 배포·재시작·DB 변경·commit/push/병합은 수행하지 않았다.

직전 TEST 이미지는 보존했다. 필요 시 새 릴리스에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-name-neo4j-0b3da8484953`로 되돌릴 수 있다. 실제 롤백은 하지 않았다.

## 기록·한계와 후속

증거는 `docs/verification/assets/2026-10-15-candidate-display-name/`의 재현 가능한 browser-live.js, NAS 브라우저·API 계약·release·검사 요약 JSON, 스크린샷이다. 로그는 `/tmp/robingraph-candidate-name-ui-tests.log`, `/tmp/robingraph-candidate-name-deploy.log`, `/tmp/robingraph-candidate-name-browser.log`에 있고 임시 파일의 영구 보관은 보장하지 않는다. 저장소와 Obsidian의 상세 기록·검증 결과를 일치시킨다.

Graphify AST 갱신은5,609노드·11,577엣지·317커뮤니티로 완료했고 git diff --check도 통과했다. SQL4개는 tree_sitter_sql 부재로 제외되고 문서 의미 추출은 AST 범위 밖이며 HTML은 커뮤니티 집계 화면이다. 후보 범위850종·일반 하한·자모 보완 등 검색 품질 조건을 이번 표시 변경에서 확대하지 않았다. 국명이 없는 실제 후보의 브라우저 경로는 fixture로만 검증했고 물리 기기·Safari·Firefox·공개 도메인은 이번 범위 밖이다.
