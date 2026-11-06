---
created: 2026-10-27
date: 2026-10-27
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-603
tags: [worklog, robingraph, feedback, mlflow]
---

# [RG-603] 답변별 사용자 피드백과 MLflow trace 연결 — 2026-10-27

## 요약

답변에 피드백 자격 token이 있을 때 세 버튼을 표시하고, 별도 API로 해당 답변의 MLflow trace에 HUMAN `user_feedback` assessment를 저장하도록 구현했다. 최종 TEST `2e822237c9dc`에서 세 평가 버튼의 첫 클릭 3/3과 키보드 Enter 1건이 모두 200이었고, 실험 33의 고유 trace 4개에 원래 질문·마스킹한 응답·원 rating이 일치하는 assessment가 각각 하나씩 저장됐음을 재조회했다.

기존 chat JSON 본문은 유지하고 trace ID와 24시간 유효 서명 capability를 응답 헤더로 전달한다. feedback 실패는 기존 답변을 바꾸지 않으며 재시도 가능한 장애와 영구 오류를 구분해 안내한다. 초기 첫 제출 503/400, 하네스 오류와 진단 assessment 8건은 최종 4건과 분리해 보존했다. 자동화가 생성한 HUMAN 유형 평가를 실제 사용자의 gold로 표시하지 않는다.

RG-603은 진행 중(TEST 구현·검증 완료, 운영 승인 대기)으로 기록한다. 운영 배포·운영 실험 50 쓰기·Git commit/push·조류 DB 쓰기는 수행하지 않았다. RG-601·RG-602의 완료 상태와 RG-212 진행 중 및 잔여 문제는 변경하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 구현·현재 상태 | 경계 |
| --- | --- | --- |
| 요구사항 | 답변별 평가를 실제 trace와 연결 | 전체 질의 정확도 개선 작업 아님 |
| UI | token이 있는 답변에 세 버튼 | token 없는 과거 답변은 대상 아님 |
| API | POST /v1/chat/feedback | 기존 chat JSON 본문 불변 |
| 저장 | HUMAN user_feedback assessment | 실험·target·실제 root 검증 |
| 중복 | trace당 한 표, 같은 재시도 200·다른 값 409 | 단일 process lock; exactly-once 보장 아님 |
| 최종 검사 | Python 1,300 pass/40 skip, Node 326 pass | 실제 TEST assessment 4건 별도 재조회 |
| 배포·형상 | TEST 검증 완료·운영/Git 작업 없음 | 운영 승인 대기 |

---

## 1. 작업 배경 및 문제 분석

기존 trace는 시스템이 어떤 경로와 이유로 답변했는지 보여 주지만 사용자가 답변을 유용하게 여겼는지, 질문을 잘못 이해했다고 느꼈는지, 답변이 틀렸다고 판단했는지는 수집하지 않았다. 시스템 판단 태그와 사용자 판단을 별도로 남겨 같은 요청의 입력·처리·응답과 함께 확인할 필요가 있다.

RG-601은 자동 로깅, RG-602는 시스템 답변/미응답 사유 관측이다. 완료된 두 과제의 상태를 바꾸지 않고 사용자 평가라는 신규 범위로 RG-603을 분리했다. RobinGraph 경로의 정확 ID 검색과 상세 파일 부재로 중복을 확인했다. 기존 RG-212 미완료 질의 해석과 평가 한계 역시 이번 기능으로 완료 처리하지 않는다.

---

## 2. 해결 방안 및 설계

- 채팅 JSON 본문을 바꾸지 않고 trace ID와 서명 capability를 응답 헤더로 제공한다.
- token은 24시간 유효하며 기존 Django SECRET_KEY를 사용한다. 키가 안정적으로 유지되지 않으면 재시작 후 기존 token을 검증하지 못하므로 TEST private 환경에 stable key를 생성했다. 값은 문서·로그에 남기지 않는다.
- 피드백 API는 지정 실험 ID, 환경 target, 실제 trace root를 확인한 뒤 HUMAN assessment를 기록한다.
- trace당 한 평가를 허용한다. 같은 값의 재시도는 200, 이미 저장된 값과 다른 값은 409로 처리한다.
- 단일 process lock은 해당 프로세스 내 동시 중복을 줄이는 장치다. 여러 프로세스·MLflow 서버·네트워크 실패 전반의 exactly-once를 보장하지 않는다.
- UI는 400/422 영구 실패에 새 답변에서 다시 평가하라는 안내와 버튼 비활성화를 제공한다. 503/네트워크 장애는 재시도할 수 있고, 409는 이미 저장됐다고 안내하며 비활성화하되 어떤 평가가 저장됐는지 추측하지 않는다. 저장 장애는 feedback의 503과 UI 재시도로 분리하고 주 질문 응답을 보존한다. 피드백 처리에서 공개 `mlflow.flush_trace_async_logging()` 후 trace를 조회해 pending export를 기다리도록 보완했다. 이 대기는 피드백 경로에만 적용하며 채팅 경로는 변경하지 않았다.

```text
chat 응답 + trace ID/서명 token 헤더
→ 해당 답변의 피드백 버튼 → POST /v1/chat/feedback
→ 환경·실험·root·서명 검증 → HUMAN user_feedback assessment
```

---

## 3. 주요 구현 내용

### 사용자 값

| UI | 저장 값 |
| --- | --- |
| 도움됐어요 | helpful |
| 질문을 잘못 이해했어요 | misunderstood |
| 답변이 틀렸어요 | incorrect |

### 파일·계약

- `src/robingraph/tracing.py` — trace 연결, capability와 assessment 처리.
- `src/robingraph/api/services.py`, `schemas.py`, `drf/serializers.py`, `drf/urls.py`, `drf/views.py` — feedback 요청 계약·라우팅·응답 헤더.
- `src/robingraph/api/drf/openapi.json`, `openapi_ingest.json` — 신규 API 계약 반영.
- `src/robingraph/api/static/chat.js`, `styles.css` — 답변별 버튼·전송 결과·재시도 상태.
- `.env.example`, `.env.nas.example` — 필요한 설정 안내. 인증값은 포함하지 않는다.
- `tests/test_chat_feedback.py` — 최종 API mock 13 methods.
- `tests/frontend/chat_ui.test.js`, `tests/test_drf_parity.py` — UI 결과 상태·경로/모델 등록 회귀 검사.

증거는 `docs/verification/assets/2026-10-27-chat-feedback/`에 보존했다.

| 증거 | 확인 내용 |
| --- | --- |
| `test-release.json` | 최종 이미지·source manifest·TEST 실험 33·서명 키 지속 설정 여부 |
| `browser-results.json`, `keyboard-results.json` | 실제 세 버튼·키보드 첫 전송·재시도·오류·화면 검사 |
| `assessment-readback.json` | 최종 4 trace와 assessment 대응·이전 진단 8건 분리 |
| `test-experiment-preflight.json`, `test-window.json` | TEST 실험 확인과 검증 창 |
| `async-export-first/`, `conditional-flush-first/`, `pre-terminal-ui/` | 초기 후보·실패 및 중간 검증 이력 |
| `desktop-*.png`, `mobile-feedback.png` | Codex가 시각 확인한 실제 TEST 화면 |

서명 token·SECRET_KEY 값 자체는 기록하지 않는다.

---

## 4. 검증 및 테스트 결과

### 최종 자동 검사

| 검사 | 결과 | 성격 |
| --- | --- | --- |
| Python 전체 | 1,340 실행·1,300 통과·40 skip·0 실패, 25.470초 | 로컬 단위·회귀 |
| Node frontend | 326 통과·0 실패, 248.186ms | UI 자동 검사 |
| 신규 API 검사 | mock 13 methods 통과, 0.270초 | 실제 MLflow 쓰기와 구분 |

40 skip은 기존 pinned 자료 또는 전용/일회용 DB opt-in 조건으로 실행하지 않은 검사이며 통과로 합산하지 않는다.

초기 malformed JSON 검사는 기존 계약의 422를 오래된 400 기대로 검사해 실패했고 기대값을 기존 계약에 맞췄다. 첫 전체 검사 3실패는 신규 path/model 레지스트리 등록 누락을 보완해 해결했다. 이 이력은 실제 TEST 장애와 구분한다.

### 첫 TEST 관측과 후속 보완 이력

첫 TEST image 식별자 13ed에서 helpful/misunderstood/incorrect native assessment 저장, 동일 재전송 200·다른 값 409를 확인했다. 첫 vote가 503으로 끝나 2~3번 재시도가 필요했고 후속 조건부 flush 후보에서는 첫 400도 관측했다. 독립 SDK 코드 분석상 `get_trace(flush=True)`는 조건부 flush이므로 부분 trace가 먼저 조회되는 경계가 가능했다. 다만 실제 첫 실패의 부분 root payload를 직접 포착하지 않았고 진단용 fresh local 요청은 200이었다. 따라서 관측과 코드 분석에 근거한 보완이지 첫 400의 내부 payload 원인을 확정한 것은 아니다. 이 첫 제출 실패를 최종 성공으로 덮어쓰지 않는다.

source root 부재는 token 오류로 취급하지 않고 503으로 구분했다. 실제 잘못된 target만 구체적인 FeedbackTargetError의 400, SDK ValueError는 503으로 처리한다. 공개 `mlflow.flush_trace_async_logging()` 후 `get_trace`를 호출하도록 보완해 피드백 경로의 pending 큐 전체를 기다린다. 단일 trace만 기다리는 처리 또는 분산 exactly-once 보장으로 설명하지 않는다.

partial trace·first flush 회귀를 포함한 최종 API 13 methods와 전체 1,340개 검사를 완료했다. 초기 전체 1,338개(1,298 pass·40 skip) 결과와 구분한다. 브라우저 하네스에서 Fetch의 status를 함수로 잘못 호출한 오류 2번도 최초 로그에 보존했으며 앱 결함으로 세지 않는다.

### 실제 TEST 브라우저·MLflow 검증

최종 실제 브라우저에서 helpful/misunderstood/incorrect 세 값의 첫 클릭은 모두 200이었다. 각 동일 값 재전송은 200, 다른 값 재전송은 409, 변조 token은 400을 확인했다. 키보드 Enter로 제출한 추가 1건도 첫 시도 200이었다. 실제 서버와 MLflow를 사용했으며 응답 mock이 아니다.

1280px와 390px에서 가로 넘침과 JS page error는 없었고 Codex가 스크린샷을 확인했다. 물리 모바일·Safari/Firefox 검사는 수행하지 않았다. 자동 UI 회귀의 400/422 영구 실패·503/네트워크 재시도 확인을 실제 서버 장애를 일으킨 검사로 표시하지 않는다.

`assessment-readback.json`의 최종 4개 고유 trace는 TEST 실험 33에 속했다. 각각 원 질문·기존 마스킹/길이 제한을 적용한 HTTP 응답·원 rating과 일치하는 HUMAN assessment가 정확히 하나였으며, 이 readback 단계의 새 chat 요청과 feedback POST는 모두 0이었다. 본문 전체를 마스킹 없이 보관했다는 뜻은 아니다.

이전 개발·하네스·진단 평가 8건은 `prior_test_window_records`에 따로 보존하고 최종 4건 성공 수에 합산하지 않았다. 자동화가 사용자 버튼을 실행한 것이므로 source_type HUMAN을 실제 사람 평가나 gold로 해석하지 않는다. 운영 실험 50에는 쓰지 않았다.

첫 TEST 배포 preflight는 기존 환경이 ID 없이 NAME만 지정된 상태에서 하네스가 ID 키를 기대해 KeyError로 실패했다. 환경을 바꾸기 전 발생한 하네스 오류이며, 서버에서 TEST 실험 이름과 ID 33 대응을 확인한 뒤 ID를 명시해 해결했다.

### 독립 후검

`independent-review.json`은 PASS였다. 리뷰어는 release 파일 해시 234개, 첫 제출 4건과 assessment 대응 4건을 재확인했다. 신규 API 호출·DB/Git 쓰기는 0이며 별도의 실제 질문 재실행으로 합산하지 않는다. 단일 process lock·분산 exactly-once 미보장·물리 모바일 미검증·운영 미배포 한계도 유지했다.

### 피드백 검토 사용법

1. 답변 아래에서 세 평가 중 하나를 선택한다. 저장 실패 안내가 재시도를 허용할 때만 같은 답변에서 다시 제출한다.
2. MLflow의 해당 실험에서 `user_feedback` assessment를 확인하고 연결된 원 trace의 질문·응답·처리 단계를 함께 읽는다. 현재 확인 환경은 [TEST 실험 33](https://mlflow.dove-nest.com/#/experiments/33)이다.
3. 사람이 원문과 근거를 검토해 실제 개선 대상인지 판단한 뒤 TEST case request로 추가한다. 피드백만으로 정답을 확정하거나 모델 자동 학습·자동 배포를 수행하지 않는다.

---

## 5. 배포 및 형상 관리

- **현재 범위**: 구현과 TEST 검증.
- **TEST 최종 이미지**: `robingraph-api:test-chat-feedback-2e822237c9dc`, verified.
- **소스 SHA256**: `2e822237c9dc795a18b2eba23d353d178bf989eefec01042d5377d2146a6401e`.
- **기준 revision**: `318e7731fda8b85560b7e8d464b0f4f2c92439d1`; 미커밋 snapshot.
- **TEST 설정**: 실험 ID 33 명시·private env에 stable Django signing key 설정, 실제 키 값 미기록.
- **Production**: 배포 미승인·미실행.
- **Git commit/push/merge**: 미실행.
- **조류 DB 쓰기**: 없음. TEST MLflow assessment 기록은 이 기능 검증을 위한 의도된 쓰기이며 운영 실험 50은 변경하지 않았다.
- **인증**: SECRET_KEY·서명 token의 실제 값을 보관하지 않는다.

---

## 6. 한계 및 후속 과제

- HUMAN assessment는 평가 출처 유형이다. 사용자의 판단이 객관적 gold나 모델 답변의 참/거짓 검증을 자동 보장하지 않는다.
- trace당 한 표이며 사용자별 다중 투표·투표 변경·자유 의견 수집으로 범위를 확대하지 않는다.
- 서명 capability 소지와 유효기간 검증은 로그인 사용자 본인 확인과 다르다.
- 단일 process lock과 재시도 계약은 분산 exactly-once 보장이 아니다.
- 운영 배포는 별도 명시 승인이 필요하며 RG-212 진행 중 상태는 유지한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-601|RG-601 자동 로깅]]
- [[Work/RobinGraph/백로그 상세/RG-602|RG-602 시스템 답변·보류 원인 구분]]
