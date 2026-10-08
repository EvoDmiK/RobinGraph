# RG-016 MLflow 응답 구분·RG-015 마우스 드래그 카드 뒤집기

작업일: 2026-10-08 (KST). 브랜치: `dev`.

## 요청 배경과 범위

사용자가 오늘 RG-015까지 진행하도록 요청했다. 백로그의 권장 실행 순서인 RG-016 → RG-015에 따라 두 작업을 함께 처리했다. RG-014 HippoRAG 검색과 RG-017 한국 서식 토글은 대기 상태를 유지한다. 기존 최후순위 보류 작업의 재개는 이번 범위에 포함하지 않는다.

RG-016은 MLflow에서 정상 답변과 이름 미발견·추가 확인·조회 장애를 구별하는 작업이다. 신고 화면의 “박새에 대해 알고 싶어”는 HTTP 성공이어도 `profile=null`이므로 실행 성공과 유효한 답변 제공 여부를 따로 관측해야 한다. 제공 화면만으로 박새 자료가 없다고 확정하지 않는다. RG-015는 기존 버튼 외에 마우스 드래그로 도감 카드 앞·뒷면을 전환하는 작업이다.

## 원인과 변경 전후

### RG-016

기존 `_traced_route`는 응답의 의도·경로·disposition을 span attribute로 기록했다. MLflow Trace 목록에서 결과·사유별로 검색할 trace-level tag가 없었고 미응답 이유도 별도 코드로 수집하지 않았다.

이제 `/v1/chat`의 실제 응답 분기에서 `_why(reason, stage)`로 사유를 기록한다. 한국어 안내 문장을 파싱하지 않는다. 요청마다 새 `ContextVar` 수집기를 만들고 종료 시 토큰을 복원해 병렬 요청의 사유가 섞이지 않도록 한다. 기존 span attribute와 API 응답 모델은 유지하고 다음 trace tags를 추가한다.

| 태그 | 의미·값 |
|---|---|
| `response_disposition` | `answer`, `clarify`, `abstain`, `error` |
| `response_reason` | `none`, `taxon_not_found`, `intent_uncertain`, `ambiguous_name`, `filter_mismatch`, `evidence_not_found`, `observations_empty`, `handler_unavailable`, `upstream_error`, `unsupported_question`, `unknown` |
| `failure_stage` | `none`, `routing`, `name_resolution`, `retrieval`, `generation`, `validation`, `unknown` |
| `selected_intent` | `profile`, `taxonomy`, `observations`, `evidence`, `none` |
| `route_method` | `semantic`, `explicit`, `deterministic`, `jev`, `none` |
| `response_api_disposition` | 실제 ChatResponse의 기존 disposition |

태그 값은 허용 집합으로 제한한다. 질문·이름·인증 정보는 새 태그에 넣지 않는다. 정상 답변은 `none/none`, 분류할 수 없는 미응답은 `unknown/unknown`을 쓴다. 조회기 미설정과 외부 조회 실패는 모니터링 태그에서 `error`로 구별하되, 기존 HTTP 200 `abstain` 응답과 MLflow 실행 상태 `OK`를 강제로 바꾸지 않는다. HTTPException이 실제 전파되면 기존대로 trace 실행 상태가 `ERROR`가 된다.

추적 비활성 상태에서는 새 기록 경로가 동작하지 않고, span 시작 실패·태그 쓰기 실패도 API 응답을 바꾸지 않는다. 비-chat 라우트는 성공 시 기본 answer/none을 기록하고 HTTP 404·400/422·503에 상태코드 기반 사유를 기록한다.

### RG-015

기존 버튼으로만 뒤집던 카드에 마우스 주버튼의 좌우 Pointer Events 제스처를 추가했다. 수평 이동 6px 이상이며 수직 이동보다 충분히 클 때 활성화하고 pointer capture를 잡는다. 카드/팝업 폭의 25%(최소 40px)를 넘겨 놓으면 반대 면으로 전환하고, 짧게 끌면 원래 면으로 복귀한다. 활성화 중에는 이동량에 맞춰 회전한다.

제스처는 카드와 허용된 레이아웃 컨테이너의 빈 영역에서 시작한다. 텍스트·버튼·링크·입력·사진·contenteditable·native draggable·관련 role은 제외한다. 첫 구현에서 본문 선택이 드래그에 빼앗기는 문제를 주 담당이 발견하여 허용 목록 방식으로 수정했다. Shift 등 수정키를 누르지 않아도 일반 텍스트 선택이 유지된다. fine pointer 환경에서 “카드 빈 곳을 좌우로 끌어도 뒤집혀요” 안내를 표시한다.

pointercancel, lostpointercapture, 창 blur/resize, 팝업 닫기·재열기, 대화 초기화 시 임시 스타일·capture·리스너·진행 상태를 해제한다. 드래그 후 발생하는 click은 한 번 억제하고 기존 뒤집기 버튼·키보드·aria-pressed와 보이는 면을 맞춘다. reduced-motion에서는 연속 회전을 생략하고 윤곽선 피드백 후 즉시 전환한다. 터치·펜은 마우스 뒤집기의 시작 조건에서 제외한다.

## 변경 파일과 역할

| 파일 | 구현 내용 |
|---|---|
| `src/robingraph/api/app.py` | 응답 분기의 구조화 사유, 라우트 태그 기록·예외 처리 |
| `src/robingraph/tracing.py` | ContextVar 수집기, 허용 값·결과 매핑, fail-open 태그 쓰기 |
| `tests/test_mlflow_response_tags.py` | 결과별 분기, 비활성·기록 실패·동시성, 실제 SDK 로컬 exporter 검증 |
| `scripts/verify_mlflow_response_tags.py` | TEST 요청 후 실제 MLflow 서버에서 태그 필터로 새 trace 검색 |
| `docs/mlflow-tracing.md` | 태그 의미·검색 예제·운영 한계 |
| `src/robingraph/api/static/chat.js` | 드래그 상태·임계값·회전·취소·조작 제외·안내 |
| `src/robingraph/api/static/styles.css` | 드래그 커서·피드백·fine pointer 및 reduced-motion 스타일 |
| `tests/frontend/chat_ui.test.js` | 제스처·취소·중복 click·선택 영역·기존 버튼 회귀 |

## 협업과 검토 근거

[orchestration 스킬](/Users/kimdove/.agents/skills/orchestration/SKILL.md)을 사용해 실제 Orca run `run_e82e62b9bbeb`에서 작업을 분담했다. Claude 워커가 서버 태그와 화면 구현을 각각 담당하고, Antigravity가 읽기 전용 독립 코드 검토를 맡았다. Codex 주 담당은 요구사항 대조·수정 지시·실제 DB·MLflow·NAS·브라우저·문서·Git을 통합했다. 런타임 receipt의 모델 필드가 null이므로 워커의 실제 모델명은 미확인으로 기록한다.

| 작업 | Task / 최종 Dispatch | 결과 근거 |
|---|---|---|
| 서버 구현 | `task_90ae62b90e92` / `ctx_17bfce61a2a6` | 구조화 사유·태그 구현, 로컬 SDK 테스트 보고 |
| 서버 테스트 격리 후속 | `task_f1fd6173c361` / `ctx_bcdbeeaa89a2` | 전역 mock 경쟁 수정, 모호한 이름·미지원 질문 보강 |
| 카드 구현 | `task_9f75a8004306` / `ctx_83e4e1f0253f` | 마우스 제스처 구현과 로컬 브라우저 보고 |
| 텍스트 선택 보존 후속 | `task_bcb0eede51a0` / `ctx_6da4002b4219` | 빈 영역 허용 목록, 텍스트·사진 제외, 181 frontend pass |
| 독립 검토 | `task_0dc75b85d4dd` / `ctx_0852b12d23e5` | 소스·테스트 검토, NAS 실서버 검증은 주 담당에게 남김 |
| 검토 기록 정정 | `task_7e7ff34b5671` / `ctx_027240cb63e3` | 테스트 집계·모델 확인·실행 범위 정정 및 최신 테스트 검토 |

최초 Codex 서버 워커 `ctx_7cd44e5eefe5`는 업데이트 안내창 때문에 agent_readiness 단계에서 시작 실패했다. 작업 실행 전 실패를 확인하고 같은 Task를 Claude로 재시도했다. 도구를 전역 업데이트하거나 사용자 소유 터미널을 닫지 않았다. 완료 보고 후 release를 요청한 워커 중 런타임이 user_takeover/external_terminal로 유지한 터미널은 그 소유권 판정을 따른다.

## 테스트 방법과 실제 결과

| 검증 | 환경·실행 범위 | 결과 |
|---|---|---|
| 전체 Python 1차 | 실제 Neo4j·임시 PostgreSQL schema·고정 아종 출처 캐시, `/tmp/rg013-integration-rerun.py` | 633 실행, 631 통과·2 실패·0 건너뜀 |
| 전체 Python 수정 후 | 같은 실제 DB runner, 새 임시 schema 생성·종료 시 삭제 | 633 통과·0 실패·0 건너뜀, 37.205초 |
| 전체 frontend | `node --test tests/frontend/*.test.js`, 모의 DOM | 181 통과·0 실패·0 건너뜀 |
| 태그 단위/모의 | 허용 값, 모든 결과 코드, 장애·비활성·8스레드 격리 | 전체 Python 통과에 포함 |
| 실제 MLflow SDK | SDK 3.14.0, exporter를 로컬 캡처; 서버·네트워크 미사용 | 실제 TraceInfo.tags와 HTTP 200 `OK`, HTTPException `ERROR`, 병렬 격리 통과 |
| 로컬 Chrome | Claude 워커, 합성 프로필 정적 페이지, 320·390·1280px 및 reduced-motion | 드래그·복귀·blur·선택·이미지 제외 통과; NAS 증거와 구별 |
| 지식 그래프 | `graphify update .` AST-only | 3,638 nodes·7,908 edges·205 communities 갱신 |
| diff 공백 검사 | `git diff --check` | 통과 |

1차 실제 DB 테스트의 두 실패는 서비스 검색 코드의 변경이 아니라 새 동시성 테스트에서 전역 `neo4j_hybrid.search` patch를 각 스레드가 열고 닫은 경쟁 때문이었다. 종료 순서에 따라 모의 검색 함수가 전역에 남았다. patch를 executor 바깥에서 한 번 적용하고 종료 후 원래 함수의 identity를 확인하도록 수정했다. 수정 후 같은 실제 DB 전체 테스트가 건너뜀 없이 통과했다. 이 실패 이력을 최종 통과 수치로 덮어쓰지 않는다.

워커의 선택 연동 비활성 전체 실행은 총 633개 중 35개 건너뜀을 포함한다. 이를 “633 통과 + 35 건너뜀”으로 합산하지 않는다. 완료 판단은 주 담당이 실행한 실제 DB 633/633 결과를 따른다. 테스트 중 외부 모델 응답은 모의이며, 실제 SDK exporter 검증 역시 실제 MLflow 서버 저장 검증과 구별한다.

graphify는 SQL parser 의존성이 없어 SQL 4개를 추출하지 못했다는 경고를 냈다. 이번 Python/JS AST 변경의 갱신은 완료했고 유료 semantic label 재생성은 실행하지 않았다.

[검증 집계·배포 메타데이터](assets/2026-10-08-RG015016-test-summary.json)에서 1차 실패와 최종 결과를 함께 확인할 수 있다.

## NAS TEST·MLflow 실서버·브라우저

소스 커밋 `75377ca`의 TEST 이미지를 빌드·교체하고 `deploy_nas.sh verify`와 container health를 확인했다. 소스 archive SHA와 파일별 manifest를 검증했고 실제 image label `org.opencontainers.image.revision`이 전체 구현 커밋과 일치했다. health의 fixture 분류 릴리스 표시는 활성 종 응답의 분류판을 대신하는 증거로 사용하지 않았다.

### 실제 MLflow 저장·검색

NAS container의 SDK와 실제 MLflow 서버는 모두 3.14.0이며 experiment는 `robingraph-test`(33)이다. container 내부의 실제 HTTP API로 요청했고 조회기를 모의로 바꾸지 않았다. 검증 스크립트 2건과 5스레드 병렬 배치 6건에서 저장 trace의 입력·태그·실행 상태를 대조하고 서버 태그 필터로 다시 조회했다. 정상 answer와 다른 사유의 trace가 해당 필터에서 제외되는 것도 확인했다.

| 실제 요청 | API 결과 / trace 태그 | 실제 trace ID |
|---|---|---|
| 박새에 대해 알고 싶어 | `abstain / taxon_not_found / name_resolution`, profile 없음 | `tr-e7fe5bb586dcca15401b94fbe4d1c24e` |
| 청둥오리 profile | `answer / none / none`, profile 있음 | `tr-a654d47d9988fc5c5c4807f475772875` |
| 별도 미등록 이름 | `abstain / taxon_not_found / name_resolution` | `tr-3976224f8d47a3aae4ab20ccf54d4da7` |
| 까마귀 profile | `clarify / ambiguous_name / name_resolution` | `tr-d3cd9b92f1f3bf8e0b712cdf107ac9bd` |
| 청둥오리 먹이 질문 + 박새 필터 | `clarify / filter_mismatch / validation` | `tr-dd5b0f523f354e8ea5c263b87a26c14a` |
| 없는 지역의 관찰 기록 | `abstain / observations_empty / retrieval` | `tr-af4781ebac276e38efc09c57baa81c95` |
| 관찰 필터 누락(저장소 검증기) | `clarify / filter_mismatch / validation` | `tr-d5cb069660821170154777c6538a17ec` |
| 미등록 이름(저장소 검증기) | `abstain / taxon_not_found / name_resolution` | `tr-ba05a0238be1fa711dfc86c80e773128` |

위 요청은 모두 HTTP 200, trace 실행 상태 `OK`였다. 이는 유효한 조류 설명 제공 여부와 별개다. **박새는 이번 확인에서도 미발견 상태이며, 새 태그로 구별 가능해진 것이다. 박새 자료나 이름 연결을 보완한 작업으로 기록하지 않는다.** 조회기 미설정·외부 조회 오류·근거 없음·미지원 질문·의도 불명·태그 쓰기 실패는 모의 조회기/로컬 실제 SDK 테스트에서 검증했다. 실제 NAS의 정상 조회기나 외부 제공처를 일부러 중단시키지는 않았다.

초기 실서버 검증기는 박새가 정상 조회될 것으로 가정했고, Pydantic이 추가한 기본값까지 요청 dict 전체가 같아야 trace를 찾도록 작성해 실패했다. 실제 박새 응답을 보류로 기록하고 요청의 제공 필드를 재귀적으로 대조하도록 검증기를 수정했다. 또한 일반 profile 질문은 기존 필터 우선 동작을 따르므로 필터 충돌 검증은 실제 충돌 분기가 있는 먹이 질문으로 실행했다. 서비스의 이름 해소나 조회 정책을 변경해 검증 결과를 맞추지 않았다.

[실제 서버 배치 결과](assets/2026-10-08-RG016-nas-traces.json), [저장소 검증기 결과](assets/2026-10-08-RG016-verifier.json).

### MLflow 화면에서 찾기

[experiment 33 Traces](https://mlflow.dove-nest.com/#/experiments/33/traces)에서 다음 순서로 조회한다.

1. `Filters` → Field `Tags`.
2. Key `response_reason`, Operator `=`, Value `taxon_not_found`.
3. `Apply filters`를 누르면 박새·미등록 이름처럼 이 사유가 기록된 trace만 표시된다.
4. trace를 열어 상단 `Tags` 영역에서 태그를 확인한다. 처음 한 태그와 `+5`처럼 나머지 태그 개수가 표시될 수 있으며, `+5`를 열면 나머지 사유·단계·결과 태그가 표시된다.

실제 Chrome에서 위 조작으로 미등록 trace ID가 목록에 나타나고 상세가 열리는 것을 확인했다. 브라우저가 보낸 실제 query에도 `tags.response_reason = 'taxon_not_found'`가 포함됐다. 결과별 조회는 Key를 `response_disposition`으로 바꿔 `answer`, `clarify`, `abstain`, `error`를 사용한다. SDK 검색에서도 같은 태그 식을 사용할 수 있다.

[필터 설정 화면](assets/2026-10-08-RG016-mlflow-filter-settings.png), [필터 결과 화면](assets/2026-10-08-RG016-mlflow-filter-results.png), [trace 상세 태그 화면](assets/2026-10-08-RG016-mlflow-trace-tags.png), [브라우저 확인 결과](assets/2026-10-08-RG016-mlflow-ui.json). 필터 적용·목록·상세 열기는 실제 Playwright 클릭으로 확인했다. 상세 태그 팝오버의 추가 확인은 MLflow의 신규 기능 안내 tooltip이 포인터를 가려 버튼의 DOM click으로 열었으며 물리적 포인터 시험과 구별한다.

### 실제 NAS 카드 브라우저 검증

Chrome에서 실제 `/v1/chat` 응답으로 만든 청둥오리 카드를 사용했다. 320·390·1280px와 1280px reduced-motion에서 짧은 드래그 원복, 좌우 뒤집기, 일반 텍스트 선택, blur/resize/pointercancel 취소, Escape 닫기·재열기, Enter/Space 버튼 전환, aria/보이는 면·잠김 해제·가로 넘침 없음을 확인했다. 일반 모드에는 연속 회전이 있고 reduced-motion에는 없는 것도 대조했다. 페이지 JS 오류는 0건이다.

별도 실제 NAS 확인에서 카드 밖 release, 실제 사진 위 드래그로 뒤집히지 않음, 다음 사진 버튼, 출처 링크 새 창, 출처 면 스크롤, lost capture 정리, 대화 지우기 후 카드 제거가 통과했다. 마우스·사진 버튼·링크·스크롤은 실제 Playwright 입력이고 blur/resize/pointercancel/lost capture와 touch 시작 제외는 DOM 이벤트 주입이다. 물리적 창 전환·모바일 터치 시험으로 확대 해석하지 않는다.

브라우저 검증기는 cleanup 상태를 속성 삭제로 가정한 것을 실제 `false` 값에 맞췄고, 고정 시간 대기 대신 애니메이션 종료 후 버튼이 풀리는 상태를 기다리게 했다. 사진 전환은 첫 DOM 이미지의 URL 변경이 아니라 현재 보이는 figure의 이미지 교체로 확인했다. 검증기 수정이며 제품 코드의 추가 수정은 없다.

[화면 폭별 결과](assets/2026-10-08-RG015016-browser.json), [기존 조작·경계 조건 결과](assets/2026-10-08-RG015-nas-edges.json), [320px 화면](assets/2026-10-08-RG015016-card-320.png), [390px 화면](assets/2026-10-08-RG015016-card-390.png), [1280px 화면](assets/2026-10-08-RG015016-card-1280.png), [reduced-motion 화면](assets/2026-10-08-RG015016-card-1280-reduced.png).

## 커밋·배포 정보

- 구현 커밋: `75377ca5d61a5a8cee139fd9144722bdfa366a8e`.
- 배포 전 TEST 이미지: `robingraph-api:test-rg013-f0fed63` (healthy 확인).
- 배포 후 TEST 이미지: `robingraph-api:test-rg015016-75377ca` (healthy·verify 통과), release `/home/kimdove/RobinGraph-rg015016-75377ca`.
- 배포 대상: NAS TEST `robingraph-api-test`, [TEST 채팅](https://robingraph-test.dove-nest.com/chat).
- PROD 배포·데이터 변경은 이번 작업에 해당하지 않는다. 실제 DB 테스트는 테스트 fixture와 임시 schema를 사용한다.
- 소스 패키지 SHA-256: `ca4aa4e90718205174274e529690b9299f0734b7ea0cae5a566a98bdef5c8e16`. 패키지와 각 파일 manifest 검증 후 배포한다. 인증 정보는 패키지에 포함하지 않고 기존 NAS TEST 환경 파일을 내부에서 복사한다.
- 구현 커밋 `75377ca`의 `origin/dev` push를 확인했다. 검증 문서·증거는 후속 문서 커밋으로 같은 브랜치에 기록한다. 실행 이미지의 revision은 위 구현 커밋을 가리키며 뒤의 문서 커밋과 구별한다.

## 작업 관리 문서 동기화

Obsidian의 `Work/RobinGraph/2026-10-08-RG015-RG016-MLflow태그-드래그카드-NAS-TEST배포.md`에 같은 핵심 구현·실제 검증·배포 정보와 한계를 기록했다. 백로그의 RG-016·RG-015 상세를 완료 구역으로 이동하고 목차·현황표·대기 표·변경 이력을 함께 갱신했다. 프로젝트 `index.md`에도 작업 기록 링크를 추가했다. 저장 후 각 문서를 다시 읽어 저장 내용 일치를 검사했다.

작업 상세 ID 17개가 각각 한 번 있고 모든 목차 대상 제목이 존재하는지 확인했다. 기존 최후순위 보류 RG-002·RG-010·RG-011·RG-012와 신규 대기 RG-014·RG-017의 상세 본문은 변경 전과 동일하게 보존했다. 현재 집계는 진행 중 0건·신규 대기 2건·최후순위 보류 4건·완료 RG 11건과 기존 카드 효과 1건이다. 완료 워커는 release 또는 재사용으로 정산했으며 마지막 조회에서 reclaimable worker는 0개다.

## 남은 한계와 후속

기존 trace를 소급 분류하지 않는다. 비-chat HTTP 오류 사유는 상태코드 기반 근사이며 개별 upstream 예외의 의미까지 모두 세분화한 것은 아니다. 생성 모델 실패 후 기존 retrieval 답변으로 폴백해 정상 답변이 되는 경우에는 최종 답변 결과를 기록한다. 단순히 내부 하위 span이 실패했다는 이유만으로 최종 answer를 error로 바꾸지 않는다.

실제 터치 기기·트랙패드 하드웨어·Safari·Firefox는 검증 대상에 포함하지 않았다. 모바일 폭에서 Playwright 마우스로 확인한 결과와 DOM 이벤트로 취소를 주입한 결과를 물리적 모바일 터치 시험으로 표현하지 않는다. 터치 스와이프는 이번 기능 범위가 아니다. 한국 서식 토글·HippoRAG·전체 이름/번역 검토는 해당 백로그에서 별도 착수한다.
