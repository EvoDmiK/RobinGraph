---
created: 2026-10-24
date: 2026-10-24
project: RobinGraph
type: worklog
status: completed
task_id: RG-602
tags: [worklog, robingraph, mlflow, tracing]
---

# [RG-602 후속] 답변이 막힌 단계와 원인을 같은 MLflow trace에서 구분 — 2026-10-24

## 요약

사용자는 질문에 답하지 못했을 때 어느 단계에서 왜 멈췄는지 구분할 수 있기를 요청했다. 기존 MLflow 관측을 확장해 같은 요청의 원문·선택 경로·생성 계획·감사·실행 검증·최종 응답을 연결하고, 자료 부족·검색 결과 없음·기술 오류를 구별한다. 기존 응답 판정과 질의 해석의 동작 자체를 바꾸는 작업은 아니다.

RG-602의 2026-10-08 완료 범위는 이력으로 보존하고 이번 시맨틱 경로 관측을 후속 확장으로 기록한다. RG-212의 남은 해석 오류와 자료 한계를 해결했다고 표현하지 않는다. 앞선 trace 초기화 이후 사용 중인 실험 33 `robingraph-test`를 이어서 사용하며 새 trace 삭제는 하지 않는다.

앱 4파일과 새 검사 2파일로 구현했고 전체 Python 1,236개 중 1,196개 통과·40개 skip·실패 0을 확인했다. TEST 이미지 배포 후 healthy와 기존 active+semantic·MLflow 실험 33 설정을 확인했다. 실제 9사례에서 같은 요청의 원인 기록·최종 태그·태그 검색을 모두 재조회했다. 이는 답변 정확도 9/9가 아니며 관측 후속 범위의 검증 완료다. Production 배포·앱 설정 변경·commit·push는 수행하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 답변 중단 단계와 사유 구분 | 원문부터 최종 응답까지 같은 요청의 trace로 추적 |
| 설계 | 기존 MLflow 관측 확장 | 최종 결과 태그와 시맨틱 계획·감사·검증 span을 연결 |
| 코드 | 앱 4파일·새 검사 2파일 | tracing·서비스 결과와 계획·감사·검증 계측 |
| 검증 | 전체 Python 1,196 통과·40 skip | 실제 9사례의 원인 기록·동일 요청 연결·태그 검색 확인 |
| 배포 | TEST healthy | `test-blocked-tracing-54bb05bdd0b2`, 기존 실험 33 사용, trace 추가 삭제·운영 반영 없음 |
| 백로그 | RG-602 후속 연결 | RG-212 진행 중과 기존 완료 범위 보존 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

사용자 화면에서 “추가 확인 필요”나 자료 부족 응답만 보면 요청의 의미를 해석하지 못한 것인지, 감사·안전 검증에서 막혔는지, 조회는 됐지만 근거 자료가 없는 것인지 구분하기 어렵다. 이전 MLflow 태그는 최종 결과를 기록했지만 새 시맨틱 처리의 세부 판단을 같은 요청에서 따라갈 수 있도록 보강할 필요가 있었다.

### 확인 범위

이번 작업은 원인 관측이다. 실행 결과가 없는 경우를 오류로 임의 분류하거나, 보류를 성공으로 바꾸거나, 부족한 자료를 생성하지 않았다. 최종 기록은 실제 구현의 안정적인 사유 코드와 단계 정보를 사용한다. 아래 스키마와 결과는 전달받은 diff·실제 영수증을 대조했다.

---

## 2. 해결 방안 및 설계

1. 최종 응답의 disposition과 구체적 중단 사유를 기존 tracing 경로에 기록한다.
2. 시맨틱 계획 생성·감사·실행 검증을 세부 span으로 남겨 같은 request의 앞뒤 단계를 연결한다.
3. 자료 부족, 조회 결과 0, 기술 오류를 구분하되 기존 질문 해석·응답 동작을 유지한다.
4. 민감한 인증 정보를 trace나 문서에 추가하지 않는다. 원문·계획 기록의 실제 범위와 제한은 최종 구현대로 명시한다.
5. 실험 33을 이어서 사용하고 기존 trace를 다시 삭제하지 않는다. 새 관측이 실제 저장되는지는 TEST 요청과 MLflow 재조회로 확인한다.

기존 관측 체계를 재사용한다. 독립 검토에서는 로그 추가가 응답 결과를 바꾸거나 오류를 숨기지 않는지 확인한다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `src/robingraph/tracing.py` — 최종 태그·관측 필드 확장.
- `src/robingraph/api/services.py` — 같은 요청의 경로·최종 응답과 사유 연결.
- `src/robingraph/generation.py`, `src/robingraph/retrieval/semantic_graph_intent.py` — 계획·감사·실행 검증의 세부 span.
- `tests/test_graph_interpretation_tracing.py` — 백엔드 12 methods의 계획·감사·검증 계측 검사.
- `tests/test_graph_diagnostics.py` — 독립 5 methods의 응답·SDK 장애·동시 요청·이름 확인 검사.
- `docs/verification/assets/2026-10-24-blocked-response-tracing/` — 단위·독립 검사, TEST 요청, MLflow 실제 저장·재조회와 배포 증거.

### 결과 확인 흐름

```text
같은 요청
→ 원문·라우팅
→ 구조화 계획
→ 감사와 실행 검증
→ 실제 조회 여부·결과
→ 답변 / 확인 필요 / 자료 부족 / 검색 결과 없음 / 기술 오류
```

모든 단계가 모든 요청에서 실행되는 것은 아니다. 의미 선택처럼 조회 전 확인하는 요청은 모델 계획·감사 span 없이 routing 결과로 끝날 수 있다. 실제 실행 단계는 같은 trace의 span으로 구분한다.

### 최종 태그와 단계별 span 계약

| 기록 위치 | 필드·span | 의미 |
| --- | --- | --- |
| 최종 태그 | `response_disposition`, `response_reason`, `failure_stage`, `response_api_disposition`, `selected_intent`, `route_method` | 기존 키 유지; 허용 enum 값으로 응답 결과·중단 원인·경로 필터링 |
| 추가 중단 단계 | `interpretation`, `semantic_audit`, `plan_validation` | 계획 해석·감사·실행 계획 검증을 분리 |
| 선택 경로 | `graph_intent.selection` | `selected_interpreter`로 실제 선택한 해석 경로 기록 |
| 계획 | `graph_intent.plan` | 파싱된 제안 계획을 outputs에 기록 |
| 감사 | `graph_intent.audit` | 감사 outputs와 `judgment_source=model`; 모델 판단임을 명시 |
| 검증 | `graph_intent.validation` | 입력과 거부 reason·`rejection_detail` 기록 |
| 기존 라우트 | `graph_intent.route` | GraphIntent outputs, `graph_intent.block_reason`, `graph_intent.block_stage`로 최종 경로와 연결 |

사유 enum의 정의는 `tracing.py`의 `RESPONSE_REASONS`를 따른다. 자유 문장 원인·모델 의견은 기존 길이 제한·민감한 키의 값 마스킹을 적용한 span에 남기며 최종 태그에 임의 문자열을 넣지 않는다. 자유 문장 속 모든 비밀값이 제거된다는 보장은 아니다. 기록은 해당 시스템이 차단한 이유를 보여 주며 객관적으로 정확한 해석이라는 보증이 아니다. MLflow SDK trace state가 OK여도 서비스의 `response_disposition`은 error·clarify·abstain으로 별도 유지한다.

[MLflow TEST Traces](https://mlflow.dove-nest.com/#/experiments/33/traces)에서 `tags.response_reason = 'plan_validation_rejected'` 또는 `tags.failure_stage = 'semantic_audit'`로 해당 원인을 검색하고, 같은 trace의 plan·audit·validation span을 확인한다.

---

## 4. 검증 및 테스트 결과

### 자동화 검사

| 검사 | 실제 결과 | 범위 |
| --- | --- | --- |
| 전체 Python | 1,236 실행: 1,196 통과 / 40 skip / 0 실패, 23.819초 | `uv run --locked --extra test --extra tracing python -m unittest discover -s tests -v`; skip을 통과에 포함하지 않음 |
| 독립 검사 5 methods | 응답 18유형·SDK 장애 72조합·동시 요청 4개·이름 확인 4상태 및 예외 | 모의 응답·SDK 상황에서 기존 API 동작 보존과 관측 분리 검사 |
| 추가 독립 검사 2 methods | 실제 하위 전송 경로를 모의한 7상황·실패 뒤 정상 요청 | 하위 계측·격리 검사, 실제 MLflow 서버 검증 아님 |
| 코드 그래프·공백 검사 | graphify 갱신·최종 `git diff --check` 통과 | 기능·응답 정확도 검사와 별도 |

이전 작업의 성공 수치를 이번 결과로 재사용하지 않는다. 독립 matrix는 사전 설계이고 실제 실행 결과와 구분한다. 단위·모의 검사 통과를 실제 모델/API·DB 정확도로 해석하지 않는다.

### 실제 TEST·MLflow 검증

`live-traces.json`의 최종 9사례와 `live-traces-resume.log`에서 같은 요청의 원인 기록·최종 태그·태그 검색이 9/9 통과한 것을 확인했다. 실제 서버·모델 응답을 모의하지 않았고 trace를 삭제하지 않았다. Codex가 실행한 실제 영수증을 Writer가 조회한 결과이며 Writer가 새 요청을 보내 재검증한 것은 아니다.

| 실제 응답 분류 | 사례 수 | 관측된 사유 |
| --- | --- | --- |
| 정상 answer | 1 | 정상 답변의 경로·최종 결과 |
| 검색 결과 없음 | 1 | `no_matching_results` |
| 자료 부족 | 1 | `insufficient_data` |
| 확인 필요 clarify | 6 | `ambiguous_conditions`, `filter_mismatch`, `unresolved_conditions`, `plan_validation_rejected` 2건, `semantic_audit_rejected` |

기술 오류·SDK 장애 등은 독립 모의 검사에서 검증했으며 이번 실제 9사례에 기술 오류가 발생한 것으로 표현하지 않는다. 정상적인 미응답·자료 부족과 실제 오류를 같은 이유로 묶지 않는다. 이 검사는 관측 결과의 기록·연결 여부이며 답변 정확도 9/9 또는 일반화 점수가 아니다.

### 같은 요청에서 확인한 실제 중단 원인

- `known_false_hold` (`tr-25a6955f2f714933c5d74765c3b99f6a`): 원문 “숲이 서식지로 기록돼 있고”가 계획의 surface에서 “숲이 서식지로 기록돼 있어”로 바뀌었다. 감사는 true였지만 이후 검증에서 `surface not in question`으로 거부됐다. 같은 요청의 계획·감사·검증을 연결해 확인했다.
- `shared_reference` (`tr-8c9a25621398801737055cf40b4f6df8`): relation_text에 “먹이 생태 범주가”만 추출됐다. 감사는 true였지만 검증에서 `shared_diet evidence`로 거부됐다.
- `numeric_restatement` (`tr-c063baa14f51b7bf0d0cd83c8f8ba916`): 계획은 `num_gt 180`인데 unresolved에는 “180g인 기록은 제외해”가 남았고 감사는 false였다. 모델의 issues도 span에 보존했다. 이 감사 판단이 옳다는 보증으로 보고하지 않는다.

위 원인을 이번 계측 작업에서 수정하지 않았다. 추후 해석 보완에 사용할 근거이며 현재 false hold가 해결됐다는 뜻이 아니다.

### 검증기 실패와 재조회

첫 의미 선택 사례는 최초 30초 조회창에서 trace를 찾지 못했으나 앱은 HTTP 200을 반환했고, 이후 태그 필터로 해당 trace의 존재를 확인했다. 검증기의 시작 시각 여유를 1초, 대기를 90초로 늘려 재실행했다. 시계 차이인지 저장 지연인지 정확한 원인은 확정하지 않았다.

마지막 9번째 사례는 처음 조회할 때 `response_api_disposition` 태그가 없거나 기대값과 달라 검증 assertion이 실패했다. 같은 trace를 다시 읽은 뒤 clarify 일치를 확인했고, 완료 태그가 준비될 때까지 기다리도록 검증기를 보완했다. `--resume`으로 새 HTTP 요청 없이 마지막 trace의 검증을 마쳤으며 앞선 8사례는 재실행하지 않았다. 이 보완 때문에 앱 코드를 다시 수정하지 않았다.

---

## 5. 배포 및 형상 관리

- **대상**: TEST 앱·MLflow 실험 33 `robingraph-test`.
- **이미지**: `robingraph-api:test-blocked-tracing-54bb05bdd0b2`, healthy.
- **소스 SHA256**: `54bb05bdd0b2530e17ee14bdfc7933ae95ee100a14e7aaf4e18d63f1a53bd8f5`.
- **기준 HEAD·릴리스**: `834c5353ca45f0640152ca4849548cd48818b266` 기반 미커밋 snapshot, `/Users/kimdove/robingraph-test/releases/blocked-tracing-54bb05bdd0b2-ecdfc5`.
- **실제 runtime**: test·active·semantic, `ROBINGRAPH_MLFLOW_TRACING=true`, `MLFLOW_EXPERIMENT_NAME=robingraph-test`. 기존 설정 유지이며 새 실험 생성·모드 전환이 아니다.
- **Production**: 이번 작업의 운영 배포·재시작·이미지 교체 없음.
- **Git**: 별도 commit·push·merge 없이 기존 dirty 변경을 보존한다.
- **MLflow**: 기존 실험 사용, 새 trace 삭제 없음. 앞선 trace 초기화와 이번 코드 계측은 별개 작업이다.
- **데이터·설정**: 실제 질의 해석 동작·DB 자료·로깅 설정을 변경하지 않았다. 관측 필드만 확장했고 source manifest가 실제 워크스페이스와 일치함을 확인했다.

---

## 6. 한계 및 후속 사항

- 중단 원인을 기록하는 것과 그 원인을 해결하는 것은 다르다. 기존 false hold·직접 자료 부족과 RG-212 미완료 범위를 완료 처리하지 않는다.
- 로그만으로 원문 조건의 완전한 보존이나 모든 생물학적 근거의 정확성을 보장하지 않는다.
- 실제로 실행하지 않은 실패 유형·브라우저·실기기·운영 환경 검증은 추정하지 않는다.
- 최종 증거를 반영한 scratch와 같은 Obsidian 본문을 저장하고 재조회로 일치를 확인했다. RG-602 결과 링크와 6xx 인덱스에 기록 링크만 추가했으며 기존 본문·완료 범위와 RG-212 진행 중 상태를 보존했다. 저장소 반영은 Codex 최종 검토 후 수행한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-602|RG-602 기존 완료 범위]]
- [[Work/RobinGraph/작업기록/6xx 관측·평가/2026-10-24-MLflow-trace-초기화|선행 trace 초기화]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-24-RG212-시맨틱-보류원인-보완-실제재평가|RG-212 후속 평가와 남은 한계]]
