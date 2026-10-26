---
created: 2026-10-24
date: 2026-10-24
project: RobinGraph
type: worklog
status: completed
task_id: null
tags: [worklog, robingraph, mlflow, tracing]
---

# MLflow 기존 trace 정리와 새 관측 시작 — 2026-10-24

## 요약

사용자가 “기존 mlflow trace들을 지우고 새로운걸로 시작”하도록 명시적으로 요청했다. RobinGraph의 `robingraph-test`(실험 33)와 `robingraph-local`(실험 34)에서 기준 시각 이전 trace만 삭제 대상으로 고정했다. 실험 자체·run·dataset과 다른 프로젝트는 대상에서 제외했다.

기준 시각은 2026-10-24 04:36:01.404 UTC, 한국 시간 13:36:01.404다. TEST의 대상 trace 5,512개를 삭제했고 local은 삭제 대상이 없었다. 두 실험 모두 기준 시각 이전 잔여 trace가 0임을 재조회했다. 실험 active 상태와 run ID 집합(TEST 3개·local 0개)은 그대로였고 기존 평가 dataset도 재조회됐다. 실제 TEST 인사 요청으로 새 trace가 OK·10 spans로 생성되는 것을 확인했다.

이번 작업은 관측 기록의 초기화다. 앱 코드·설정·배포를 바꾸거나 거절 원인의 구조화 로깅을 새로 구현하는 작업이 아니다. 관련 기능이나 백로그의 완료 상태도 바꾸지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 기존 RobinGraph trace 삭제 | 사용자 명시 요청에 따라 새 기록부터 관측 |
| 범위 | 실험 33·34의 기준 시각 이전 trace | 실험·run·dataset·다른 프로젝트 보존 |
| 삭제 전 확인 | TEST 5,512개, local 0개 | 고정 cutoff와 trace ID inventory 저장 |
| 실제 처리 | 대상 5,512개 삭제·잔여 0 | 실험·run 보존, 기존 dataset 재조회, 새 trace OK·10 spans 확인 |
| 코드·배포 | 변경 없음 | 앱·환경 설정·운영 배포·commit·push 없음 |

---

## 1. 작업 배경 및 범위 확인

기존 질의·평가 trace가 누적된 상태에서 사용자가 새 관측을 시작하기 위해 이전 trace의 삭제를 요청했다. 이를 프로젝트 전체 MLflow 데이터 삭제로 확대하지 않고, RobinGraph 관련 실험 두 개의 과거 trace로 한정했다.

삭제 전 `inventory.json`에 대상 실험 ID·이름, trace ID 목록과 개수, 기존 run ID 목록, cutoff를 저장했다. trace 본문이나 인증 정보는 문서에 넣지 않는다. 기준 시각 이후 생성된 기록은 이번 삭제 대상으로 추가하지 않는다.

---

## 2. 처리 방식

1. `https://mlflow.dove-nest.com`에서 대상 실험과 기존 trace를 읽어 확인했다.
2. 삭제 기준 `cutoff_ms=1792816561404`와 대상 ID를 고정했다.
3. inventory의 명시적인 trace ID를 100개씩 `delete_traces`로 전달했다. 같은 cutoff로 재조회해 기준 시각 이전 잔여 0을 확인했다.
4. 실험·run·dataset을 삭제하지 않고 다른 프로젝트로 범위를 넓히지 않는다. 기존 로깅 흐름은 유지한다.

사용자가 명시한 삭제 요청이 근거이며, 단순 역할 배정으로 수행한 작업이 아니다. 임시 uv 환경의 기존 MLflow SDK 3.14를 사용했으며 앱 의존성·설정을 수정하지 않았다. 수치는 실제 MLflow API 응답과 재조회로 기록했다.

---

## 3. 변경 파일과 실행 증거

앱 코드·설정 변경은 없다. 아래 문서와 증거 파일만 추가한다.

- `docs/verification/assets/2026-10-24-mlflow-trace-reset/inventory.json` — 삭제 전 대상·cutoff·run 목록. `delete_experiments`, `delete_runs`, `delete_datasets`는 모두 false.
- `docs/verification/assets/2026-10-24-mlflow-trace-reset/delete-receipt.json` — 삭제 수, 기준 시각 이전 잔여, 실험 active·run ID 보존 확인.
- `docs/verification/assets/2026-10-24-mlflow-trace-reset/new-trace-verification.json` — 실제 새 trace의 OK·10 spans와 기존 dataset 재조회 확인.
- `docs/work-log/2026-10-24-mlflow-trace-reset.md` — Codex 검토 후 반영하는 작업 기록.

새 테스트·빌드·graphify 갱신은 해당하지 않는다. 코드 변경이 없으며 이번 검증 대상은 실제 MLflow 기록의 삭제·보존 범위다.

---

## 4. 실제 검증 결과

| 대상 실험 | 삭제 전 trace | 삭제 전 run | 삭제·재조회 |
| --- | --- | --- | --- |
| 33 `robingraph-test` | 5,512 | 3 | 5,512개 삭제, cutoff 이전 잔여 0, run ID 집합 동일·실험 active |
| 34 `robingraph-local` | 0 | 0 | 0개 삭제, cutoff 이전 잔여 0, run ID 집합 동일·실험 active |

실제 MLflow API를 대상으로 확인하며 모의 데이터로 삭제 성공을 판단하지 않는다. 삭제 후 trace가 새로 기록될 수 있으므로 전체 목록이 영구적으로 0이라는 뜻으로 해석하지 않는다. 이번 cutoff 이전 대상의 삭제 여부와 이후 새 관측을 구분한다.

### 삭제 후 새 기록과 보존 확인

- 실제 TEST 앱에 인사 요청을 한 번 보내 새 trace `tr-356aa8a1330c20bac8a1dda87ae4743a`가 생성되고 상태 OK·10 spans인 것을 확인했다. HTTP 응답 상세를 별도 저장하지 않아 HTTP 200을 검증했다고 기록하지 않는다.
- 기존 평가 dataset `d-9b84fb796702487a90cbf57e754995a8`을 재조회해 존재를 확인했다. 모든 dataset의 내용 체크섬 감사까지 수행한 것은 아니다.
- 첫 dataset 조회는 ID를 positional name 인수로 전달해 실패했다. `dataset_id` 키워드로 바로잡아 조회에 성공했으며 데이터가 없어 발생한 실패가 아니다. 새 HTTP 요청을 반복하지 않고 이미 생성된 trace를 다시 조회했다.
- Writer는 Codex가 실행한 실제 영수증을 읽어 기록했다. Writer가 삭제나 확인용 요청을 다시 실행한 것은 아니다.

---

## 5. 배포 및 형상 관리

- **대상 서비스**: MLflow `https://mlflow.dove-nest.com`.
- **사용자 승인**: 기존 trace를 지우고 새로 시작하라는 명시 요청.
- **실제 변경**: 대상 trace 삭제. 실험·run·dataset 삭제는 실행하지 않았다.
- **앱 배포·재시작**: 없음. 기존 TEST·Production 앱 및 로깅 설정을 변경하지 않는다.
- **Git**: commit·push·merge 없음. 기존 dirty 변경 보존.

---

## 6. 한계 및 후속 사항

- trace 삭제가 앱의 질문 해석·거절 원인·관측 필드 품질을 개선한 것은 아니다. 거절 원인 구조화 로깅 구현 완료로 기록하지 않는다.
- 실험·run·dataset 삭제와 다른 프로젝트 정리는 이번 범위가 아니다.
- 삭제된 trace를 가리키던 과거 링크는 더 이상 조회할 수 없다. run·dataset 자체의 보존과 그 안에 있을 수 있는 기존 trace 참조의 가용성은 서로 다른 사항이다.
- 새 trace는 실제 TEST 인사 요청으로 확인한 검증용 기록이다. 실사용자의 일반 트래픽이나 이후 모든 질의의 로깅 품질 검증으로 확대하지 않는다.
- Writer는 최종 영수증을 반영한 scratch와 같은 Obsidian 본문을 저장하고 재조회로 일치를 확인했다. 관측·평가 인덱스에는 기록 링크만 추가하고 기존 본문·백로그 상태를 보존했다. 저장소 파일은 Codex 최종 검토 후 반영한다.

---

## 관련 문서

- [MLflow 공식 trace 삭제 API 안내](https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/delete-traces/)
- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/6xx 관측·평가/작업 백로그|관측·평가 작업기록]]
