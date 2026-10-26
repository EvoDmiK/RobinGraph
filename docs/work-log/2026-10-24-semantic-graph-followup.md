---
created: 2026-10-24
date: 2026-10-24
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags: [worklog, robingraph, semantic, evaluation]
---

# [RG-212] 시맨틱 그래프 질의의 보류 원인 보완과 실제 재평가 — 2026-10-24

## 요약

사용자가 전날 작업을 이어가도록 요청해 미완료 상태인 RG-212 시맨틱 질의 해석을 재개했다. 직전 TEST에 기존 28문항을 실제로 다시 실행해 지원 문항의 false hold 6건·검증 불가능 3건과 기존 동작 비교 1건의 차이를 재현했다. 이전 문서의 완료 문구를 근거로 성공을 가정하지 않고 이번 실행을 변경 전 기준선으로 삼았다.

백엔드 원인 규칙을 보완하고, 실제 서식 환경·먹이 관계 쿼리가 성공한 뒤 실행한 조건을 확인할 수 있는 `execution_summary`를 추가했다. 이 값은 기존 자유형 API payload의 추가 필드이며 화면에 새로 표시하지 않는다. 결과가 나왔다는 사실과 요청한 조건을 실행했다는 사실을 구분해 평가할 근거를 보강했다.

기존 28문항의 지원 결과는 변경 전 9 pass / 6 fail / 3 unverifiable에서 최종 16 pass / 1 fail / 1 unverifiable로 개선됐다. 최종 보류 기대 6/6과 기존 동작 유지 4/4도 통과했다. 새 독립 20문항의 첫 측정은 지원 7/12 pass·5 false hold, 보류 기대 6/6, 기존 동작 2/2였다. 이 수치는 1차 후보의 결과이며 독립 문항에 맞춘 재튜닝·재평가를 하지 않는다. RG-212는 진행 중이고 전체 자연어 해석 완료로 주장하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 기존 시맨틱 보류 재현 | 실제 TEST 28문항 before 확보; 6 false hold·3 unverifiable·기존 동작 1건 차이 |
| 설계 및 해결 방안 | 원인 규칙 보완·실행 증거 | 원문 조건을 버리지 않고 판정하며 실제 관계 쿼리 뒤 실행 요약 기록 |
| 코드 / 설정 수정 | 앱 3파일·검사 2파일 | 의미 해석·모델 지침·실행 요약, 조건 재서술·그래프 응답 검사 |
| 실서비스 배포 | TEST 1차 후보 후 최종 후보 검증 | 기존 active+semantic 유지, 운영 semantic 활성화 승인 아님 |
| 검증 및 테스트 | before/after·새 독립 평가 분리 | 기존 피드백 문항을 미노출 정확도로 보고하지 않음 |
| 형상 관리 | dev-codex 미커밋 snapshot | 기존 dirty 보존, commit·push·운영 배포 없음 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

전날 검증된 기능 묶음은 운영에 active+lexical로 반영됐지만, TEST의 실험적 semantic 해석에는 지원 가능한 질문을 보류하는 사례와 실행 조건을 평가하기 어려운 결과가 남아 있었다. 이번 요청은 해당 미완료 개선의 재개다. 사람 검토 미완료 과제나 다른 기능 상태를 완료로 바꾸는 작업이 아니다.

### 확인한 근거

`docs/verification/assets/2026-10-24-semantic-graph-followup/api-before.json`은 실제 TEST 응답이며 `response_mocking: false`, `bird_db_writes: 0`을 기록한다. 기존 28문항에서 재현한 결과를 이번 변경 전 기준선으로 사용했다. 원인별 수정 내용과 변경 후 결과는 아래에 실제 diff·실행 영수증에 맞춰 기록했다.

서식 환경·먹이 관계의 경우 목록만으로는 어떤 조건이 실제 쿼리에 전달됐는지 검토하기 어렵다. 따라서 실행 완료 후 조건 요약을 별도로 제공하되, 이 요약만으로 생태 데이터 전체의 정확성을 보증하지 않는다.

---

## 2. 해결 방안 및 설계

1. 기존 문항을 다시 실행해 false hold와 평가 근거 부족을 분리한다. 원인을 확인한 규칙만 수정하고 특정 문장을 정답으로 하드코딩하지 않는다.
2. 원문 조건·종·부정·수치 등을 유지하는 안전 검증을 전제로 실제 지원 범위를 개선한다. 모호하거나 미지원인 조건을 제거해 조회하지 않는다.
3. `_habitat_diet`의 실제 쿼리가 성공한 뒤 `execution_summary`를 추가해 실행한 질의 조건을 확인한다. 독립 리뷰에서 추가 필드의 범위를 점검했다.
4. 수정에 노출된 기존 28문항과 새 독립 20문항을 별도로 평가한다. 새 문항을 보고 구현을 다시 바꿨다면 그 시점 이후 결과는 회귀로 표시한다.
5. TEST와 운영의 모드를 구분한다. 어제 운영 배포 이력은 완료된 lexical 범위이며 이번 semantic 개선을 운영에 적용했다는 뜻이 아니다.

독립 안전 검사 SF10에서 야간 조건이 모의 계획에서 누락되는 사례를 발견했다. 활동 시간 조건을 미지원 조건으로 검출해 VETO하도록 보완했고, 실제 handler 검사에서 해당 provider를 호출하지 않는 것을 확인했다. 12개 안전 사례의 통과를 모든 알 수 없는 조건 누락의 일반적 보증으로 표현하지 않는다.

기존 28문항의 알려진 실패를 후속 보완할 때는 관계 원문의 기준 종과 조사 부분이 빠진 경우의 fallback에만 유일한 원문 스팬 복구를 적용하고, 감사 단계가 서로 모순되는 판정을 내리지 않도록 지침을 정합화했다. 유일성 검사는 새 fallback에 한정하며 기존 direct span의 첫 일치 동작까지 바꾼 것은 아니다. 일반적 조건 제거·안전 검사 우회로 구현하지 않는다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `src/robingraph/retrieval/semantic_graph_intent.py` — 시맨틱 계획 검증·조건 처리와 활동 시간 미지원 VETO.
- `src/robingraph/generation.py` — 구조화 의미 해석·감사 지침 보완. 동일 조건의 재서술과 모순된 판정을 구분하며 실제 감사 거부를 무시하지 않는다.
- `src/robingraph/retrieval/graph_questions.py` — `_habitat_diet` 실제 쿼리 성공 후 `execution_summary` 추가. 자유형 payload의 추가 필드이며 UI 새 표현 없음.
- `tests/test_graph_questions.py`, `tests/test_semantic_restatements.py` — 실행 요약과 조건 재서술·안전 검증 회귀.
- `docs/verification/assets/2026-10-24-semantic-graph-followup/` — before/after 실제 API, 독립 문항과 평가, TEST 배포·검증 자료.

### 변경 전후 기준

| 원인 | 변경 전 문제 | 변경 후 처리와 경계 |
| --- | --- | --- |
| 같은 종의 반복 언급 | 같은 종을 반복한 표현을 불필요한 추가 엔티티나 조건으로 보류 | 같은 기준 종의 반복을 허용하되 다른 종의 조건을 제거하지 않음 |
| “모아 줘” 요청 어미 | 명령 표현을 종 이름 “모아”로 오인할 수 있음 | 요청 문맥의 명령어를 종 조건으로 넣지 않음 |
| 기준 종 자체 제외 | “청둥오리 말고” 등의 자기 제외를 새로운 미지원 부정으로 처리 | 기준 종 자기 제외만 동치로 허용; 다른 대상·조건의 제외는 유지 |
| 엄격 수치 경계의 동치 | 같은 경계를 다시 쓴 부정·비교 표현을 모순으로 보류 | 엄격 경계가 실제로 같은 경우만 허용하며 범위를 넓히지 않음 |
| 먹이 비중 재서술 | 비중 0 초과 조건의 재서술이 누락되거나 다른 조건으로 판단 | 원래 비중 조건과 의미를 보존하며 특정 먹이 종으로 확대하지 않음 |
| 일반 비교 질문 | semantic 경로의 불필요한 보류로 기존 비교 응답을 유지하지 못함 | 기존 일반 비교 라우팅으로 복귀해 원래 동작 보존 |
| 관계 기준 종 스팬 누락 | 알려진 fresh13의 관계 원문에서 기준 종·조사 일부가 누락 | 새 fallback에 한해 유일한 원문 스팬만 복구; 기존 직접 스팬 첫 일치 정책은 유지 |
| 감사 판정 정합성 | 알려진 fresh09의 동치 조건에 모순된 감사 판정 | 프롬프트 정합성 보완; 실제 audit false를 강제로 승인하지 않음 |

특정 식물 종의 먹이 자료 부족과 미지원 활동 시간 조건을 이 변경으로 우회하지 않는다. 실제 검색 결과와 실행 요약은 평가 증거이며 질문의 모든 의미를 이해했다는 보증이 아니다.

---

## 4. 검증 및 테스트 결과

### 변경 전 실제 TEST 기준선

| 평가 | 확인 결과 | 해석 |
| --- | --- | --- |
| 지원 18문항 before | 9 pass / 6 false hold / 3 unverifiable | 오늘 실제 실행 결과; 이전 성공을 재사용하지 않음 |
| 보류 기대 6문항 before | 6/6 pass | 안전한 보류 기대값과 일치 |
| 기존 동작 유지 4문항 before | 3 pass / 1 fail | 계약·메타데이터 기대 비교이며 별도 구분 |
| 응답 모의·조류 DB 쓰기 | 모의 없음·쓰기 0 | `api-before.json` 기록 |

### 변경 후·독립 평가

| 자동 검사 | 실제 결과 | 범위 |
| --- | --- | --- |
| 1차 후보 전체 Python | 1,218 실행: 1,178 통과 / 40 skip / 0 실패, 23.119초 | 전날 39 skip과 혼용하지 않음 |
| 최종 후보 전체 Python | 1,219 실행: 1,179 통과 / 40 skip / 0 실패, 24.379초 | `uv run --locked --extra test python -m unittest discover -s tests -v`; tracing extra 미포함 |
| 백엔드 관련 회귀 | 137 통과 | 단위·계약 검사 |
| execution_summary 관련 검사 | 24 통과 | Codex가 실행한 그래프 응답 검사 |
| 평가기 검사 | 합성 12개 통과 | 평가 코드 자체의 검증, 실제 질의 정확도 아님 |
| 독립 안전 검사 | 12/12 통과 | 활동 시간 누락 발견·VETO 보완 후 검사, 알려지지 않은 조건 전체 보증 아님 |
| 최종 감사 반례 | 3/3 reject | 후보 계획은 모의, auditor는 실제 모델; 전체 요청의 end-to-end 검증과 구분 |
| 코드 그래프·공백 검사 | `graphify update .` 종료 0, `git diff --check` 통과 | `graphify-update-final.log`; 기능 검사와 별도 |

| 실제 API 평가 단계 | 지원 문항 | 보류 기대 | 기존 동작 유지 |
| --- | --- | --- | --- |
| 기존 28문항 변경 전 | 9 pass / 6 fail / 3 unverifiable | 6/6 pass | 3/4 pass |
| 기존 28문항 1차 수정 | 14 pass / 3 fail / 1 unverifiable | 6/6 pass | 4/4 pass |
| 새 독립 20문항 첫 측정 | 7/12 pass / 5 false hold | 6/6 pass | 2/2 pass |
| 기존 28문항 최종 후보 | 16 pass / 1 fail / 1 unverifiable | 6/6 pass | 4/4 pass |

최종 실패 `fresh01`의 원문은 “참새목 안에서 골라 줘. 숲이 서식지로 기록돼 있고 과일도 먹는 새를 찾고 있어.”다. 실제 HTTP 응답은 기준 종·관계를 확인하지 못했다는 잘못된 clarify로 남았다. 별도 provider 호출에서 성공한 관측이 있어도 이 실패를 성공으로 덮어쓰지 않았다.

`fresh16`의 원문은 “까치랑 AVONET 먹이 생태 범주가 일치하는 다른 조류를 찾아줘요.”다. Pica serica 종 선택 뒤 직접 생태 자료가 없어 `insufficient_data`였고 평가상 unverifiable로 남겼다. 해석 오류인 fresh01과 데이터 근거 부족인 fresh16을 같은 실패 유형으로 취급하지 않는다. 알려진 `fresh09`·`fresh13`은 이번 최종 실제 API에서 통과했다. `final-score.json`에 이 분류를 보존하며 전체 28문항을 전부 정답으로 보고하지 않는다.

`audit-mutations-final.json`의 3개 반례는 후보 계획을 모의로 주입하고 실제 auditor를 호출해 모두 거부한 검사다(`candidate_mocking: true`, `audit_mocking: false`). 실제 모델을 사용한 것은 감사 단계이며 실제 요청 전체의 성공률로 계산하지 않는다.

독립 20문항의 baseline은 변경 전 TEST active+semantic에서 실행했다. 개발자는 raw 문항을 보지 않은 상태에서 SHA를 고정하고 1차 코드 동결 후 평가했다. 첫 실패는 `independent-first-failure-review.json`에 보존하며 해당 문항에 맞춘 재튜닝·재평가를 하지 않는다. 그 후 알려진 28문항을 보완한 최종 후보를 새 20문항으로 다시 검증한 것은 아니므로 첫 측정 수치를 최종 후보의 미노출 정확도라고 표기하지 않는다.

### 실제 공개 TEST 화면

`https://robingraph-test.dove-nest.com/chat`에서 Chromium 390/1280px × 정상명/오타명 × 먹이/서식 환경의 8개 흐름이 모두 통과했다. 실제 응답으로 의미 선택·필요 시 종 후보 확인·관계 답변, 출처 키보드 조작·도감 팝업·비교와 가로 넘침을 확인했다. 증거는 `browser-final.log`, `browser.json`이다. UI 코드를 바꾸지 않아 Node 전체 UI 검사는 재실행하지 않았다.

브라우저 첫 실행은 임시 도구 경로가 정리돼 실행 준비 단계에서 실패했다. 임시 npm 도구를 복구한 뒤 실제 검사를 실행했으며 앱 응답 실패로 집계하지 않는다. 물리 모바일·Safari·Firefox는 미실행이다.

---

## 5. 배포 및 형상 관리

- **1차 TEST 후보**: `robingraph-api:test-rg212-followup-6a185ada6006`, 릴리스 `/Users/kimdove/robingraph-test/releases/rg212-followup-6a185ada6006-f4c1f5`, source SHA `6a185ada6006ae7d5fe4e3ac0b90121cb7ab3102da862ae4869e770d7902274b`.
- **최종 TEST 후보**: `robingraph-api:test-rg212-followup-7e6e163c66ce`, source SHA `7e6e163c66ce4c9d6fe3eefa9c67fc07a1e2ff5473333df9e213567103ffe328`, healthy. 릴리스 `/Users/kimdove/robingraph-test/releases/rg212-followup-7e6e163c66ce-0b1652`. `runtime.json`에서 test·active·semantic을 확인했다.
- **소스 검증**: 최종 release manifest와 실제 워크스페이스 소스가 일치했다. graphify 최종 갱신은 8,176 nodes·17,785 edges로 완료됐으며 이 수치를 질의 정확도로 해석하지 않는다.
- **기준 HEAD**: `834c5353ca45f0640152ca4849548cd48818b266` 기반 미커밋 snapshot이며 이번 변경 커밋으로 표현하지 않는다.
- **런타임**: 기존 TEST active+semantic 유지. 앞선 TEST는 Ponytail 리팩토링 이미지다. 새 운영 semantic 활성화가 아니다.
- **브랜치**: `dev-codex`. 다른 작업의 dirty 변경을 보존한다.
- **Git·운영**: commit·push·Production 배포 없음. 일반적인 계속 요청을 새로운 Production 배포 승인으로 해석하지 않았다.
- **전날 운영 이력**: 2026-10-23 Jenkins PROD #8, 커밋 `33c0b67ef6a0ab23e3f3d20f6112ee38d43ba83b`, active+lexical로 검증된 완료 기능을 반영했다. semantic LLM 계획·감사는 비활성이다.
- **문서 사실 정정**: 전체 백로그·2xx 인덱스·RG-203/206/207/208 상세의 현재 “운영 미배포/향후 승인” 문구를 전날 PROD #8 active+lexical 배포 근거에 맞게 정정했다. 기존 완료 범위·사람 검토 미완료 상태와 날짜별 과거 기록은 보존했고, 6문서 모두 저장 후 원문 일치를 확인했다.

---

## 6. 한계 및 후속 과제

- RG-212는 진행 중이다. 이번 개선으로 전체 의미 해석·모든 자연어·모든 조류 데이터 검증이 완료됐다고 주장하지 않는다.
- 기존 28문항은 피드백에 노출된 회귀다. 독립 20문항의 생성·노출·수정 시점을 구분해 실제 평가 성격을 남긴다.
- 실행 요약은 쿼리 실행 증거다. 원문 의미의 완전한 보존이나 결과 데이터 정확성을 독립적으로 보증하지 않는다.
- 기존 fresh01의 HTTP false hold 1건, fresh16의 직접 자료 한계, 독립 첫 평가에서 나온 지원 문항 false hold 5건을 후속으로 남겼다. 별도 호출의 성공 사례로 실패를 덮어쓰지 않는다.
- Python skip 40개는 고정 원자료·전용 DB·opt-in 검사 범주이며 `python-tests-final.log`의 사유를 따른다. 확인하지 않은 tracing 원인으로 추정하지 않는다. 운영 배포는 미실행이며 물리 모바일·Safari·Firefox·DB 전체 체크섬 감사도 별도 수행했다고 주장하지 않는다.
- 저장소 반영용 scratch와 동일한 Obsidian 기록을 저장하고 재조회로 일치를 확인했다. RG-212 현재 검증 행과 인덱스 링크를 실제 결과로 갱신했으며 진행 중 상태를 유지했다. 다른 기능·사람 검토의 상태는 보존했다. 저장소 파일 반영은 Codex 최종 검토 후 수행한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-시맨틱-그래프-인터프리터-실험-구현|선행 semantic 실험]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-검증된-그래프-질의-확인흐름-운영-배포|전날 검증된 기능 active+lexical 운영 배포]]
