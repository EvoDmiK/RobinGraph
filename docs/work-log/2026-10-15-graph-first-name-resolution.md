# RG-202: 그래프 우선 이름 해소와 벡터 후보 확인

> 후속 배포 완료: 사용자 재요청 후 SSH가 복구되어 NAS TEST 배포와 실제 API·Chromium 검증을 완료했다. 아래 SSH 대기 설명은 최초 구현 시점의 이력이다. 최신 배포·검증·운영 불변 증거는 [NAS TEST 배포 기록](2026-10-15-name-resolution-nas-test-deployment.md)을 따른다.

## 요청 배경과 목표

사용자는 HippoRAG처럼 문헌에서 개체·사실을 추출하는 기능보다, `흰뺨 검둥 오리에 대해 알고 싶어`에서 이름 표현을 기존 조류 노드에 연결하기를 원했다. 그래프에서 먼저 찾고 없을 때 이름 벡터로 후보를 찾아 확인한다. 질문 자체를 조류 노드나 영구 별칭으로 저장하지 않고 원문·이름 표현·의도·정규 taxon ID를 구분한다. 후속 요청에 따라 Codex 혼자 구현하지 않고 기존 Claude·Antigravity 워크트리와 협업했다.

이전 문헌 감사·합성 검색 기준선·MRR 수정은 유효한 별도 이력이다. 문헌 50문항과 PPR 도입은 현재 이름 해소 기능의 선행 조건이나 완료 기준이 아니다. Obsidian 전체·2xx 백로그에서 이 해석을 정정하고 이전 계획은 이력으로 보존한다.

## 담당과 전달

- Codex(dev-codex): API 계약·질문 라우팅·활성 그래프 후보 목록·CLI 연결, 결과 검토와 통합, 실제 TEST/Jina/API·브라우저 검증, 배포 준비와 기록.
- Claude(dev-claude): 이름 해소 모듈과 단위 검사, 벡터 오류·동시 요청·분류판 방어, 한국어 공백 이름·조사·분류군 접미사 파서. Task `task_7f04b228fb55`, `task_da62d48e14a0`, `task_5298d1606364`, `task_4bcc43c6e96e`의 성공 보고를 검토해 해당 파일만 복사 통합했다.
- Antigravity(dev-agy, 실제 경로 ../main): 후보 선택 UI·스타일·프런트엔드 검사. Task `task_b140309d5c20`, Dispatch `ctx_ff805e769494`의 성공 보고와 파일 3개를 받아 통합했다. 처음 배정한 파서 범위는 진행 중 Claude에 이관하고 UI로 한정했다. 실제 터미널에 표시된 모델은 Gemini 3.8 Flash·high다. Claude 모델은 이번 기록 작성 시 별도로 확인하지 않았으므로 추정하지 않는다.
- Orca Run `run_f7671a7305df`로 지시·진행·완료 보고를 관리했다. Git 워크트리 자동 동기화를 가정하지 않고 선택적으로 통합하며 다른 미커밋 파일을 보존했다.

## 확인한 원인과 변경 전후

기존 이름 조회와 한국어 질문 파서는 공백으로 나뉜 조류 이름을 충분히 처리하지 못했고, 그래프에 없는 오타를 조류 이름 벡터 후보로 확인하는 채팅 계약과 화면이 없었다. 전체 질문 임베딩으로 이를 대체하면 질문 의도와 조류 식별을 혼동한다.

변경 후에는 이름 표현을 추출해 기존 그래프 정확 조회를 하고, 한국어 이름 내부 공백을 정리해 다시 조회한다. 그래프 일치 때는 임베딩 호출이 없다. 두 경로 모두 미일치할 때만 이름 표현을 Jina 질문 임베딩으로 바꾸어 검토 국명 벡터와 비교한다. 후보는 자동 확정하지 않고 최대 3개 제시한다. 각 후보는 학명으로 그래프에서 다시 해소하여 ID·species rank·활성 concept set·분류판을 확인한다. 사용자가 선택하면 원래 먹이 등 주제를 유지한 학명 질문으로 기존 그래프 경로를 다시 거친다.

공백 이름은 최대 4개 토큰으로 제한하며 문장·지시어·접속 표현을 이름으로 임의 병합하지 않는다. 황새과의 `과`처럼 실제 분류군 이름 끝을 조사로 잘라 다른 종으로 조회하지 않는다. 기존 학명·영어·단일 국명·관찰·문헌 경로도 유지한다.

## 변경 파일과 구현

- `src/robingraph/retrieval/taxon_name_resolution.py`: 새 `TaxonNameResolver`. 그래프 우선, bounded 이름 벡터 후보, 활성 문맥 재검사, 유한 벡터·차원·프로필 확인, cosine 순위와 보류 처리. 1,000개 한도의 프로세스 메모리 LRU 캐시와 cold build single-flight 잠금으로 동시 첫 요청의 중복 임베딩을 방지한다.
- `src/robingraph/retrieval/taxonomy_lineage_neo4j.py`: 검토 국명과 활성 그래프의 ID·학명·허용 영어 이름·출처 정책이 일치하는 종 목록을 읽는다. 실제 v2025b 범위 850개다. 다른 분류판을 이 목록으로 대신 처리하지 않는다.
- `src/robingraph/cli.py`: 기존 Jina 클라이언트와 활성 분류 문맥을 resolver에 연결한다.
- `src/robingraph/api/app.py`: 선택적 `ChatResponse.entity_resolution` DTO, graph match와 profile ID·학명·문맥 대조, 벡터 후보 확인 응답, 원래 질문 주제 보존, 전체 질문 임베딩 방지와 의존성 오류 시 안전한 보류. 기존 `create_app` 호출은 resolver 없이도 동작한다.
- `src/robingraph/api/question_entities.py`, `src/robingraph/retrieval/species_questions.py`: bounded 공백 이름·조사·과/속/목 파서 보완.
- `tests/test_taxon_name_resolution.py`, `tests/test_entity_resolution_api.py`, `tests/test_taxon_name_catalog.py`, `tests/test_question_entities.py`: 새 회귀 검사.
- `src/robingraph/api/static/chat.js`, `styles.css`, `tests/frontend/chat_ui.test.js`: 후보 최대 3개·국명/학명 버튼, textContent 렌더링·키보드 선택·busy 방어. 통합 검토에서 Codex가 과거 고급 필터를 무시하는 확인용 payload와 대화 세대 guard를 추가하고, 44px 터치 높이·긴 이름 줄바꿈을 보완했다. 후보 점수는 화면에 표시하지 않는다.
- `docs/decisions/0008-graph-first-name-resolution.md`: 요청 범위·저장 경계·후보 기준·한계.
- `docs/verification/assets/2026-10-15-entity-resolution/`: 실제 Jina 조정·API smoke·브라우저 재실행 자산과 결과.

연결은 요청별 응답 정보다. 새 Query/Alias 노드, 영구 별칭, 이름 수집, DB 스키마·문헌 인덱스·저장 벡터 변경은 없다. 기존 전역 채팅/추적 체계가 응답을 기록할 가능성과 별개로 새 영구 연결을 만들지 않는다.

## 검증: 실제 실행과 결과

### 단위·계약 검사

`PYTHONPATH=src /tmp/robingraph-qa-python/bin/python -m unittest discover -s tests`를 실행했다. 884개 실행, 846개 통과, 실패 0, 38개 건너뛰기다. 실제 DB·외부 API를 요구하는 opt-in 검사 등은 건너뛴 상태이며 전체 884개를 실제 DB 검증으로 표현하지 않는다. 실행 로그는 `/tmp/robingraph-entity-resolution-unit.log`다. Claude 개별 전달 검사와 통합된 새 API·catalog 13개도 통과했다.

### 실제 TEST DB·Jina·HTTP

기존 TEST 환경을 사용하는 별도 검증 앱을 127.0.0.1:8001에 시작했다. 기존 로컬 TEST 8000과 Production 컨테이너를 재시작하지 않았다. 실제 활성 그래프에서 허용 후보 850개를 읽었다. `live-smoke.py`는 실제 HTTP 8회로 모두 통과했다. API route mock은 사용하지 않았다.

| 입력/행동 | 실제 결과 | 첫 측정 시간 |
|---|---|---:|
| 흰뺨검둥오리에 대해 알고 싶어 | graph_exact, Anas zonorhyncha 답변 | 0.473초 |
| 흰뺨 검둥 오리에 대해 알고 싶어 | graph_normalized, 동일 조류 답변 | 0.461초 |
| 흰뺨검둥오려에 대해 알고 싶어 | vector 후보·clarify, 자동 profile 없음 | cold 27.681초 |
| 위 후보 학명 질문으로 확인 | 그래프 정확 조회·동일 taxon ID | 0.278초 |
| 흰뺨검둥오려는 뭘 먹어? | vector 후보·clarify | warm 0.983초 |
| 위 후보 확인 | 동일 종의 diet 답변, 주제 보존 | 0.231초 |
| 우주선에 대해 알고 싶어 | abstain, 후보·profile 없음 | 0.701초 |
| 까치에 대해 알려줘 | graph_exact, Pica serica | 0.364초 |

`live-smoke.json`에 응답 식별 정보와 시간을 보관한다. 성능 분포나 전체 정확도 추정이 아닌 이 실행의 관측치다.

추가 실제 HTTP 3회도 통과했다(`spacing-family-smoke.json`). 이름 내부 연속 공백은 동일 종으로 해소했고, 공백 이름의 먹이 질문은 diet를 유지했다. `황새과 정보 알려줘`는 clarify로 응답하여 황새라는 종으로 잘못 확정하지 않았다. 이는 황새과의 상세 프로필 지원을 검증한 결과가 아니다.

### 이름 벡터 조정

`vector-calibration.json`은 실제 Jina 7사례의 순위 실측이다. 조정 probe에서만 하한을 풀어 raw top 후보를 관측했다. 한국어 검토 이름만 문서 텍스트로 사용했을 때 흰뺨검둥오려의 정답 0.3549, 흰뺨 검둥 오랴 0.2879, 청둥오려 0.3321이었다. 비교한 우주선·아무새 등의 최대값은 약 0.20 이하였다. 이에 후보 제시 하한 0.25로 조정했다. 이는 작은 조정 집합이며 독립 최종 평가나 정답 확률이 아니다. 왜가릐와 영문 학명 오타 Pica sercia는 하한을 통과하지 못했다. 오타 전반의 해소를 보장하지 않는다.

### UI·브라우저·배포

`node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`의 306개가 모두 통과했다(실패·건너뛰기 0). fake DOM·fixture 검증이며 실제 브라우저와 구분한다. 후보 렌더링만으로 추가 요청하지 않음, 안전한 텍스트·점수 비표시, 선택 후 원문과 확인 질문 유지, busy 중 무시, 과거 다른 종 필터 무시, 대화를 지운 뒤 이전 후보 클릭 무시를 확인했다. Antigravity가 전달 전 검사에서 발견한 fake DOM의 type attribute 표현을 보완했고, 최종 통합 검사에서 실패는 없었다.

실제 TEST DB/Jina/API를 사용하는 Chromium의 1280·390·320px 각 3회 채팅 요청도 통과했다. 공백 이름 → 정확한 조류, 오타 먹이 질문 → 후보 → Enter 키 확인 → 동일 taxon·diet 답변이었다. 고급 필터에 까치를 남겨도 후보 학명으로 조회했고 후보 렌더링 때 자동 전송이 없었다. JS pageerror 0, 가로 넘침 없음이다. 후보의 44px 터치 높이와 선택 전 화면도 추가 검사했다. `browser-live.js`, `browser-live.json`, 후보/결과 스크린샷으로 재현할 수 있다. 후보 화면 확인을 추가하면서 브라우저 검사를 재실행했다. 화면 폭 에뮬레이션이며 물리 모바일 검사로 표현하지 않는다. 사진·외관 등 외부 추가 자료 전체의 성공을 확인한 검사는 아니며, 일부 추가 자료 조회 실패 경고가 화면에 표시된 상태에서도 대상·먹이 답변은 검증했다.

NAS는 192.168.219.99:99 SSH가 두 차례 모두 Connection refused로 접속되지 않았다. 22도 거부되며 웹 80·443은 응답했다. 인증 단계 이전 실패이므로 비밀번호 오류로 판단하지 않는다. 이 기능을 NAS에 배포했다고 기록하지 않는다. 이전 RG-202 감사 배포와 구분한다. 변경된 접속 정보가 있는지 사용자에게 질문하고 독립 검증과 패키지 준비를 계속했다.

배포 가능한 runtime 패키지는 기준 커밋 `434b6a4be8493f9b8bd85f477cbe8aca65ec7413`의 기존 allowlist 패키지에 이번 source 8개 및 이전 MRR·감사 2개를 덮어써 만들었다. 비밀 환경 파일·MCP·AGENTS·개발 문서는 포함하지 않는다. runtime 136개 파일의 SHA-256를 최종 tar에서 다시 확인했다. `SOURCE_MANIFEST.json`에는 기준 커밋과 미커밋 overlay 목록·파일 해시를 담았다. `release.json`은 deployed=false다.

- 배포 준비 파일: `/tmp/robingraph-name-release/robingraph-name-resolution-1f6a427222c3.tar.gz`.
- 파일 스냅샷 SHA-256: `1f6a427222c379791aea94df3550c554cbffe081404bff2b71d705215decef7a`.
- 아카이브 SHA-256: `dec78177217f8adbbbac9a2f938c5ed3a3cb804bbcd4cc9a3479008255f630f7`.
- 제안 이미지 태그: `robingraph-api:test-name-resolution-1f6a427222c3`. 실제 빌드·배포 이미지가 아니다.

Orca 완료 메시지의 Task/Dispatch를 대조하고 모든 작업을 성공 결과로 정산했다. 외부에서 시작한 두 터미널은 worker-release 결과 retained/external_terminal로 사용자가 계속 쓸 수 있게 남았다. 회수 대기(reclaimable) worker는 0개다.

## 배포·커밋과 남은 한계

아직 이 기능의 NAS TEST 배포는 완료되지 않았다. Production 배포·재시작·운영 DB 변경과 Git commit/push/병합은 수행하지 않았다. 소스는 미커밋이며 이전 문헌 감사·MRR 변경도 보존한다.

Graphify AST 갱신은 5,463노드·11,236엣지·337커뮤니티로 완료했다. 5,000노드 초과에 따라 HTML은 커뮤니티 집계 화면이다. SQL 추출 의존성 `tree_sitter_sql` 부재로 SQL 4개는 그래프에 기여하지 않았고, 문서 의미 추출은 이번 AST 갱신 범위 밖이다. 애플리케이션 DB 검증의 누락으로 혼동하지 않는다. 커뮤니티 이름 145개는 변경된 hub 기준으로 재지정됐다. 최종 브라우저 검증 자산 변경 후에도 갱신했고 수치는 같았다. `git diff --check`가 통과했다.

로컬 확인용 앱은 `http://127.0.0.1:8001/chat`에 유지했다. 이는 임시 검증 프로세스이고 Docker/NAS 배포나 물리 재부팅 후 자동 복구를 의미하지 않는다. 기존 로컬 TEST 8000은 교체하지 않았다. 종료가 필요하면 `/tmp/robingraph-name-resolution-shadow.pid`의 PID가 `serve-neo4j --port 8001` 프로세스인지 확인한 뒤 그 프로세스에만 종료 신호를 보낸다. NAS SSH 복구 후 준비한 스냅샷으로 TEST에 배포하고 원격 API·이미지 소스 해시·Production 불변을 다시 확인하는 일이 남았다.

초기 벡터 후보 범위는 검토 국명 850개 종이다. 전체 분류군·아종·영어 오타를 포함하는 전역 이름 검색이 아니다. 정확한 학명·이름은 기존 그래프 해소 범위를 따른다. 캐시는 프로세스 재시작 후 다시 구축하며 첫 벡터 요청이 약 28초 걸린 실측 한계가 있다. 후보 하한은 확대 검증이 필요하고, 실기기 모바일·Safari·Firefox·운영 부하·물리 재부팅은 이번 확인 범위가 아니다. 영구 별칭이나 사전 구축 색인은 실제 필요와 별도 요청에 따라 결정한다.
