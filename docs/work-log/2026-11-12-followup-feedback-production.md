---
created: 2026-11-12
date: 2026-11-12
project: RobinGraph
type: worklog
status: completed
task_id: RG-213, RG-603
tags: [worklog, robingraph, followup, feedback, production]
---

# [RG-213·RG-603] 후속 조건·답변 피드백 운영 검증 완료

## 요약

사용자가 추천 작업 1번인 후속 질문 조건 유지와 피드백의 운영 MLflow 연결 확인·백로그 정리를 요청했다. 11/11 새소리 제외 운영 배포에 두 기능 코드가 이미 포함됐으므로 이번에는 재배포 없이 실제 공개 UI·운영 API·MLflow 실험50을 검증했다. RG-213은 단일 조건 추가 1단계 범위, RG-603은 답변별 세 rating 연결 범위에서 완료했다.

공개 Chromium에서 조건 유지·빈 결과 복구4턴과 안전 거절8건, 총12개 chat 응답을 확인했다. helpful/misunderstood/incorrect 첫 제출3건(Enter1건 포함)은 모두200이었다. 같은 값 재시도3건은200, 다른 값3건은409, 변조1건은400이었다. 동일12 trace의 질문·응답·후속 속성·마스킹 및 평가3건의 정확한 연결을 운영 실험50에서 재조회했다. 자동화가 생성한 HUMAN 유형 평가는 사람의 Gold가 아니다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 코드 배포 후 운영 연결 검증 공백 | 기존 백로그의 운영 승인 대기 상태를 실제 검증으로 마무리 |
| 설계 및 해결 방안 | 실제 UI + 정확한 trace ID 재조회 | 새 기능 개발·새 데이터셋 평가와 구분 |
| 코드 / 설정 수정 | 앱 수정 없음 | 검증 도구·영수증·기록·백로그만 추가/갱신 |
| 실서비스 배포 | 기존 앱 유지 | 재시작·image/env 교체·조류 DB 쓰기 명령 없음 |
| 검증 및 테스트 | 실제 운영12 chat·피드백3개 연결 | 1280/390px, 예외/가로 넘침0 |
| 형상 관리 | dev-codex 미커밋 | commit/push/merge·이력 변경 없음 |

## 1. 작업 배경 및 문제 분석

두 기능의 TEST 구현·검증은 완료됐고 11/11 별도 source snapshot에 포함돼 NAS에 배포됐다. 그러나 RG-213·603 백로그는 운영 미반영/승인 대기라는 과거 상태였고 운영 실험50의 실제 assessment 저장·재조회는 미실행이었다. 코드가 존재한다는 사실만으로 운영 검증을 완료로 표시하지 않고 이번 요청에 따라 확인했다.

## 2. 해결 방안 및 설계

1. NAS 읽기 전용 사전 검사에서 target=prod, 기존 image·container·시작 시각, 건강 상태, `/v1/chat/feedback`, 실험50 이름 `robingraph-prod`를 확인했다.
2. 임시 Chromium 프로필에서 공개 `/chat`를 실제 사용했다. fetch wrapper는 응답·상태 관측만 하고 원래 요청/응답을 반환하며 API를 mock하지 않는다. 서명 capability는 브라우저 메모리에만 두고 산출물에는 `[redacted]`로 기록했다.
3. 공개 UI의 단일 조건 추가·세 feedback 버튼(1건은 Enter) 및 실제 API의 안전 거절·재시도 계약을 확인했다.
4. 캡처한12 trace ID만 SDK `mlflow.get_trace`로 재조회했다. 검증 대상에만 `validation_phase=production_followup_feedback_acceptance`, `automated_test_feedback=true`, `verification_run` 태그를 남기고 재조회했다. 다른 trace와 평가를 수정하지 않았다.
5. 앱 ID·image·시작 시각을 대조해 이번 검사 동안 교체·재시작이 없었음을 확인했다. 조류 도메인 DB 마이그레이션·자료 쓰기 명령은0이다. MLflow의 자동 trace·검증 평가3건·대상 태그는 의도된 관측 쓰기다.

## 3. 주요 구현 내용

실행 앱 코드는 바꾸지 않았다. 다음 검증 도구와 결과는 `docs/verification/assets/2026-11-12-followup-feedback-production/`에 보관한다.

- `verify-browser.cjs` — 공개 UI·API 및 토큰 비기록 검사.
- `preflight.py`, `preflight.json` — 운영 대상과 실험 확인.
- `readback_inside.py`, `readback_nas.py` — 정해진 trace·평가 대조 및 제한된 태그.
- `browser-results.json`, `trace-readback.json`, `runtime-after.json`, `summary.json` — 실제 결과.
- `production-1280.png`, `production-390.png`, `build-*.log` — 화면·실행·실패 이력.
- `docs/backlog/RG-213.md`, `RG-603.md` — 1단계 및 피드백 기능 완료 범위와 한계.

불투명 followup/feedback token, 서명 키·Jenkins 인증값은 증거로 저장하지 않았다.

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

새 앱 코드가 없으므로 전체 단위 suite는 재실행하지 않았다. 검증 Python 파일의 AST 파싱, Node 구문 검사와 실행 중 assert를 사용했다. 이전 TEST 및 11/11 배포의 단위 통과 수를 이번 검사 수에 합산하지 않는다. 아래는 fixture/mock이 아닌 실제 운영 대상 검사다.

| 검사 | 결과 | 증거 |
| --- | --- | --- |
| 기본 조회→국내 기록→5000g 빈 결과→100g 재조회 | 4/4 | 최근 성공한 숲·열매·국내 조건 유지, 5000g 조건은 다음 성공 계획으로 전달하지 않음 |
| missing/forged/scope mismatch/negation/multiple/conflict/duplicate/route conflict | 8/8 | HTTP200의 clarify와 정확한 rejected reason, 조건을 조용히 버리지 않음 |
| 세 rating 첫 제출 | 3/3 HTTP200 | helpful Enter1건, 나머지 두 값 click |
| 같은 값 재시도 | 3/3 HTTP200 | 새로운 평가가 중복 생성되지 않음 |
| 다른 값 재시도 | 3/3 HTTP409 | 기존 평가 유지 |
| 변조 feedback token | 1/1 HTTP400 | 저장 거절 |
| MLflow 질문·응답·후속 속성·마스킹 | 12/12 | 원 요청/HTTP 응답과 exact trace root 대조 |
| MLflow assessment | 3/3 | 각 trace에 HUMAN `user_feedback`, source `robingraph-web`, 원 rating과 일치하는 평가 하나 |
| UI 초기화·화면 | 통과 | 범위 변경·대화 지우기 초기화, 1280/390×960, JS 예외·가로 넘침0 |

검증 chat POST는 총12, feedback POST는 총10(신규평가3+동일재시도3+충돌3+변조1)이다. 재조회 단계의 chat/feedback POST는 각각0이다. 재조회에서는 실험50만 읽고 검증 대상 trace의 태그만 썼다.

### 검증 도구의 최초 실패 및 보완

- 로컬 인증 helper의 모듈 이름 충돌은 명시적 importlib 모듈 로딩으로 해결했다. Jenkins 실행 전 오류다.
- Jenkins #1의 사전 검사는 운영의 `mlflow-tracing` 경량 설치에 `MlflowClient`가 없어 실패했다. 앱 기능 장애가 아니다. 공식 실험 REST GET으로 확인하도록 도구만 보정했고 #2 SUCCESS였다.
- #3은 public 결과를 포함한 Groovy 문자열이65535자 제한을 넘어 실행 전 실패했다. 검증 입력을 압축해 #4에서12 trace·평가3개 재조회에 성공했다. 이 재실행은 chat·feedback을 새로 보내지 않았다.

## 5. 배포 및 형상 관리

- 기존 운영 image: `ghcr.io/evodmik/robingraph@sha256:997ce4f410605011a17924b8ea1784849282f8931c22a27c4a11aa706c16e65f`.
- 기존 container: `f62ab640cd9548bc959470feb7cae1bee8fb66b3291c90b809076b00d1dfde92`.
- 기존 시작 시각 UTC: `2026-11-11T08:36:14.785896403Z`. 검사 전후 동일·healthy.
- Jenkins 전용 검증 job: `RobinGraph-Followup-Feedback-Verification`, 사전 검사#2·재조회#4 SUCCESS. 배포 job이 아니며 완료 후 비활성화했다.
- 기존 배포 source SHA: `5bf5c154475d9332ae8c2e8b35959c287bbfa3aecf6146c341768059077d0890`. 기반 revision5056ccba는 신규 기능 commit이 아니다.
- 이번 재배포·앱 재시작·설정 변경·조류 DB 쓰기 명령·commit/push/merge 없음. 실제 MLflow trace/평가는 요청된 기능 검증의 의도된 쓰기다.

## 6. 한계 및 후속 과제

자동 검증의 HUMAN 평가는 실제 사람의 판단·Gold·모델 정답률을 뜻하지 않는다. RG-205 사람 검토와 RG-212 일반화 과제는 유지한다. 1단계는 단일 조건 추가이며 부정·조건 교체·다중 추가·장기 기억으로 범위를 확대하지 않았다.

물리 스마트폰·Safari/Firefox·실제1시간/24시간 만료 대기·다중 탭 동시 조작·MLflow 장애 강제 주입·분산 exactly-once·전체 DB checksum은 이번 운영 검사에서 미실행이다. 기존 TEST/mock에 있는 만료·실패 회귀와 구분한다. 최초 응답부터 성공한3건의 연결 검증이며 모든 사용자 요청의 성능·저장 성공을 보장하지 않는다. 새소리 RG-409·507 상태와 다른 백로그 본문은 보존했다.

## 관련 문서

- [11/11 새소리 제외 운영 배포](2026-11-11-approved-non-audio-production.md)
- [최초 후속 질문 TEST 기록](2026-10-28-contextual-followup.md)
- [최초 피드백 TEST 기록](2026-10-27-chat-feedback.md)
- [[Work/RobinGraph/백로그 상세/RG-213|RG-213 1단계]] · [[Work/RobinGraph/백로그 상세/RG-603|RG-603]]
- MLflow 공식 [REST API](https://mlflow.org/docs/latest/api_reference/rest-api.html), [Tracing fluent API](https://mlflow.org/docs/latest/api_reference/_modules/mlflow/tracing/fluent.html).
