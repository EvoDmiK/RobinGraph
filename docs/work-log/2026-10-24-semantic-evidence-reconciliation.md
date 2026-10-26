---
created: 2026-10-24
date: 2026-10-24
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags: [worklog, robingraph, semantic, evidence]
---

# [RG-212 후속] 실제 trace에서 확인한 원문 근거·관계·수치 오거절 보완 — 2026-10-24

## 요약

사용자가 직전 MLflow 관측에서 확인한 세 가지 오거절에 대해 “응 일단 그것들 고쳐줘”라고 요청했다. 이번 범위는 원문과 달라진 조건 surface, 같은 관계의 기준 종·관계 근거 누락, 엄격 수치 경계와 중복 제외 표현의 판정이다. 기존 trace에서 확인한 원인과 새 요청의 실제 결과를 분리해 기록한다.

1차 후보는 앱 2파일에서 감사 전 결정적 보정을 추가했다. 첫 실제 13문항 측정에서 원래 3문항은 엄격 판정으로 통과했고 신규 N02의 lexical 오인과 N05의 이름 자료 제약을 발견했다. 이어진 5문항 첫 재검증에서도 N02의 분류명 절단과 F02의 불완전한 기존 경로가 드러나 후속 보완을 적용했다. 최종 후보의 실제 8문항은 엄격 판정에서 지원 6/6·보류 2/2를 통과했다. 원래 세 오거절은 모두 답변으로 전환됐지만 한국명 “비둘기과” 이름 해소 문제는 남았다. 각 시도와 실패는 별도 파일로 보존하며 다음 재검증을 미노출 평가로 바꾸지 않는다.

RG-212 전체는 진행 중이다. 이번 작업은 TEST에만 반영했고 Production 배포·Git commit·push를 수행하지 않았다. 직전 관측 확장 자체와 이번 해석 수정도 별개의 작업으로 구분한다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 실제 trace 3개 오거절 보완 | 원문 surface 불일치, 같은 먹이 관계 근거, 수치 중복 제외 |
| 설계 및 해결 방안 | 원문 근거와 동치 조건 정규화 | 의미를 바꾸거나 감사·안전 검증을 무시하지 않는 범위 |
| 코드 / 설정 수정 | 감사 전 보정·lexical 형태 가드 | generation·semantic_graph_intent와 인접 extractor 문제 보완 |
| 실서비스 배포 | 최종 TEST `4ab67ddcd227` verified | healthy·기존 active/semantic 유지; 운영 미반영 |
| 검증 및 테스트 | 전체 Python 1,213 통과·40 skip·0 실패 | 최초 실패 보존, 실제 8문항은 피드백 노출 회귀 |
| 형상 관리 | dev-codex | 기존 dirty 보존, commit·push 없음 |

---

## 1. 작업 배경 및 실제 원인

직전 관측 확장으로 같은 요청의 계획·감사·검증을 연결한 결과, 아래 세 응답이 왜 보류됐는지 확인됐다. `docs/verification/assets/2026-10-24-semantic-evidence-reconciliation/baseline-traces.json`에 수정 전 실제 응답과 trace를 보존했다. 세 요청 모두 HTTP 200·clarify였으며 SDK trace state는 OK였다. HTTP·trace의 처리 성공이 질문 해석 성공을 의미하지 않는다.

| 사례 | 실제 확인한 수정 전 원인 | 기준 trace |
| --- | --- | --- |
| `known_false_hold` | 원문 “숲이 서식지로 기록돼 있고”를 계획에서 “숲이 서식지로 기록돼 있어”로 바꿈. 감사 true 이후 검증 `surface not in question` | `tr-25a6955f2f714933c5d74765c3b99f6a` |
| `shared_reference` | 같은 먹이 관계의 relation_text에 “먹이 생태 범주가”만 들어감. 감사 true 이후 검증 `shared_diet evidence` | `tr-8c9a25621398801737055cf40b4f6df8` |
| `numeric_restatement` | 계획은 `num_gt 180`인데 unresolved에 “180g인 기록은 제외해”가 남고 감사 false | `tr-c063baa14f51b7bf0d0cd83c8f8ba916` |

위 기준선은 실제 서버·모델 응답이며 모의가 아니다. 이전 trace를 새 수정의 성공 증거로 재사용하지 않는다.

---

## 2. 해결 방안 및 설계

1. 조건 근거를 원문과 대조해 처리한다. 모델의 의역을 원문에 없는 새 조건으로 허용하지 않으며, 실제 원문 근거로 정규화할 수 있는 경우와 그렇지 않은 경우를 구분한다.
2. 같은 관계 표현은 기준 종과 관계 근거를 함께 확인한다. 다른 종이나 다른 관계를 같은 것으로 취급하지 않는다.
3. 수치 조건은 엄격 경계와 중복 제외가 실제로 동치일 때만 정리한다. 비동치 범위·단위·다른 조건을 삭제하지 않는다.
4. 실제 감사 거부나 미지원 조건을 무조건 승인하는 방식으로 우회하지 않는다. 원래 질의와 근거를 유지하는지 검증한다.

### 보정 범위와 실패 시 동작

- 같은 긍정 존재 조건의 말끝만 의역됐을 때 내용 부분은 원문 그대로 유지하고, 원문에서 유일한 `있고/있으며/있는` 구간을 복구한다. 임의 동의어 변환이나 새 조건 추론은 하지 않는다.
- `shared_diet`의 불완전한 먹이 관계 근거는 원문의 동일 기준 종·조사·같음 표현까지 유일하게 연결되는 경우에만 확장한다. 접두어만 우연히 겹친 텍스트를 같은 근거로 사용하지 않는다.
- `taxon_traits`의 unresolved 항목은 기존 `_checked_exclusions`가 엄격 수치 경계의 중복으로 증명한 제외만 제거한다.
- 수정한 후보는 기존 `_build`와 `execution_gate`를 통과해야 한다. 실패하면 unresolved를 포함한 원래 계획과 빈 보정 내역을 반환한다. 임시 로컬 검증에서 생긴 관측 상태도 원래 요청에 새지 않도록 복원한다.
- 감사에는 실행 후보인 `proposed_plan`과 보정 내역을 전달하고 필요할 때 원래 초안도 함께 제공한다. 실제 audit false는 계속 거부하며 추가 모델 재시도로 승인 결과를 얻지 않는다.

독립 리뷰에서 “열대숲”과 “숲”처럼 부분 문자열만 겹칠 수 있는 위험을 지적해 경계를 강화했다. 이를 이미 실제 요청에서 안전 검사를 우회한 결함으로 단정하지 않는다. 마지막 유일한 prefix 확인 변경 이후의 검사 범위는 아래에 따로 기록한다.

첫 실제 신규 N02의 false hold는 보정기 내부가 아니라 앞선 lexical 추출에서 발생했다. “기록되어 있고 열매도…”의 형태를 식물·종 조건으로 오인한 경우를 최소 형태 가드로 제한한다. 이번 새 실패를 기록한 `live-traces.json`을 보존했고 수정 후 결과를 별도 회귀로 측정했다.

5문항 첫 재검증에서 드러난 두 문제도 구분했다. N02는 semantic 경로까지 들어갔지만 모델이 “까마귀속”을 “까마귀”로 잘라 감사 true 뒤 `_taxa_kept`에서 거부됐다. 유일한 catalog 기반 원문 상위 분류명이 모델 값 뒤에 목·과·속 한 글자를 붙인 경우에만 복구하도록 제한한다. F02는 서식지 조건이 남은 불완전한 `order_fruit` 경로가 semantic 후보 허용 목록에서 빠졌다. 불완전한 해당 경로만 semantic으로 넘기고 기존 veto와 완전한 legacy 경로는 유지한다. 최종 실제 재검증에서 두 요청 모두 조건을 유지한 답변으로 전환됐다.

---

## 3. 주요 구현 내용

### 수정 파일 및 최종 동작

- `src/robingraph/retrieval/semantic_graph_intent.py` — `reconcile_graph_plan` 추가. 원문 어미·같은 기준 종 관계·엄격 경계 중복 제외를 보정하고 기존 검증 실패 시 원문 계획을 유지한다. 후속으로 한국어 목·과·속 보존 프롬프트, 유일한 catalog 기반 상위 분류명 접미사 복구와 불완전한 order_fruit 경로 처리를 보완했다.
- `src/robingraph/generation.py` — 기존 계획 생성과 감사 사이에서 보정 실행. `graph_intent.reconciliation` span에 원래 입력·후보 출력·`evidence_reconciliations`를 기록하고 감사에 원래 초안과 보정 내역을 전달한다.
- `tests/test_graph_evidence_reconciliation.py` — 새 회귀 8 methods. 기존 판정과 안전 검증을 재사용하는 범위를 검사한다.
- `tests/test_graph_plant_word_boundaries.py` — 4 methods·96 matrix로 lexical 형태 경계를 검사한다.
- `tests/test_semantic_rank_and_order_followup.py` — 5 methods로 분류명 보존·불완전 경로 처리를 검사한다.
- `src/robingraph/retrieval/graph_condition_extractor.py` — 첫 실제 N02에서 확인된 인접 lexical 형태 오인을 최소 가드로 보완한다. 관련 회귀 검사를 추가했다.

최종 범위는 앱 3파일과 테스트 3파일이다. 1차 앱 diff는 두 Python 파일이었으며 N02 보완으로 extractor가 추가됐다. 자유로운 질의·범위·이름·값 변경이나 UI 기능을 추가하지 않는다. `implementation.patch` 등 단계별 차이를 보존해 최종 범위를 구분한다.

### 처리 순서 예시

```text
모델 계획 → 원문·기존 검증으로 제한한 결정적 보정 → 실제 감사
           → 기존 계획 검증 → 지원 범위의 그래프 조회
```

기존 감사 false를 true로 덮어쓰지 않는다. 추가 모델 재시도, 임의 국명 생성, 특정 식물 먹이 자료 생성은 하지 않았다.

### 작업 증거

- `docs/verification/assets/2026-10-24-semantic-evidence-reconciliation/baseline-traces.json` — 세 원인의 실제 수정 전 응답·관측 근거.
- `implementation.patch`, `test-release.json` — 범위를 제한한 코드 차이와 TEST 배포 영수증.
- `live-traces.json`, `first13-strict-review.json` — 첫 실제 13문항과 엄격 판정.
- `final-traces.json`, `final5-attempt1-strict-review.json` — 이어진 5문항의 첫 재검증과 실패 보존.
- `followup-traces.json` — 마지막 후보의 실제 8문항 회귀; 앞선 실패를 덮어쓰지 않음.
- `docs/work-log/2026-10-24-semantic-evidence-reconciliation.md` — Codex 검토 후 저장소에 반영할 상세 기록.

---

## 4. 검증 및 테스트 결과

### 수정 전

| 범위 | 결과 |
| --- | --- |
| 기존 실제 3사례 | 모두 clarify; 계획 검증 거절 2건·감사 거절 1건 |
| 응답 모의·조류 DB 쓰기 | `response_mocking: false`, `bird_db_writes: 0` |

### 수정 후

실행 명령은 `uv run --locked --extra test --extra tracing python -m unittest discover -s tests -v`이며 출력은 `followup-python-tests.log`에 저장했다. 전체 Python은 기존 단위·회귀와 mock·fixture·offline 검사를 실행했다. 실제 서버·모델 호출 결과는 아래 별도 표로 구분했다.

| 검사 단계 | 실제 결과 | 실행 범위 |
| --- | --- | --- |
| 1차 유일 prefix 패치 전 전체 Python | 1,244 실행: 1,204 통과 / 40 skip / 0 실패, 27.346초 | 최종 한 줄 패치까지 전체 재실행한 결과로 표현하지 않음 |
| 1차 마지막 패치 후 대상 회귀 | 8 methods 통과 | 최종 코드의 보정 검사 |
| 1차 마지막 패치 후 독립 검사 | normalizer 7·audit 2 통과 | 로컬 fixture·offline 검증, 실제 서버/모델 검증과 별도 |
| 최종 보완 후 전체 Python | 1,253 실행: 1,213 통과 / 40 skip / 0 실패, 27.539초 | `followup-python-tests.log` |
| 최종 독립 검사 | rank-route 4 methods·기존 reconcile 7 통과 | 조건 누락 차단 포함, 실제 8문항은 별도 측정 |
| 최종 코드 그래프 갱신 | 8,359 nodes·18,290 edges·458 communities | `followup-graphify-update.log`; 질의 정확도 아님 |

첫 실제 TEST 평가는 원래 3문항과 지원 신규 6·보류 신규 4를 합한 13문항으로 실행했다. 독립 리뷰의 엄격 판정은 지원 7 pass / 2 fail, 보류 4/4 pass다. 원래 3문항은 모두 통과했고 신규 지원은 4/6 통과했다. N02 lexical 오인과 N05 이름 해소 실패를 모두 실패로 보존한다. 동결 문항 16개 중 10개를 live용으로 골랐고 inclusive equality 2개는 normalizer guard에서만 검사한다. 실제 호출하지 않은 문항을 live 성공 수에 포함하지 않는다.

N05는 한국명 “비둘기과”의 name resolution이 `not_found`였다. `0.3kg→300g` 엄격 경계와 중복 제외의 의미 해석은 맞았지만 실제 API에서 종 범위를 확인하지 못했으므로 지원 성공으로 세지 않는다. 별도 inventory에서 family Columbidae의 한국명 값 “비둘기”를 확인했지만, 최종 실제 F05 API의 taxon은 `korean_name: null`, `korean_name_source_url: null`이고 학명은 `Columbidae`다. 따라서 현재 서비스 국명을 “비둘기”라고 단정하지 않는다. 확정한 사실은 “비둘기과” 요청의 실제 조회 실패이며, 자료 조회와 API의 검증된 이름 노출은 구분한다. 이번 해석 보정 범위를 넘어 한국명 자료를 수정하지 않는다. 정규 학명으로 보충 확인하더라도 원래 N05의 성공으로 바꿔 기록하지 않는다.

N02를 본 뒤 보완한 최종 측정은 피드백 노출 회귀다. 첫 실패를 삭제하거나 최종 성공으로 덮어쓰지 않으며 새 독립 일반화 정확도로 보고하지 않는다.

추가 5문항의 첫 재검증은 지원 1 pass(F05 Columbidae 정규 학명) / 2 fail, 보류 2/2 pass였다. N02는 잘린 분류명, F02는 불완전한 legacy 경로 때문에 여전히 실패했다. `final-traces.json`에 이 시도를 그대로 보존했고, 보완 후 결과는 `followup-traces.json`에 별도 기록했다. F05 학명 성공을 한국명 N05의 성공으로 대체하지 않는다.

### 최종 실제 TEST 회귀와 관측 한계

최종 8문항은 앞선 결과를 보고 보완한 피드백 노출 회귀다. 실제 API와 같은 요청의 MLflow trace를 독립 검토했으며 서버·모델 응답 모의는 없었다. 8개 HTTP 응답은 모두 200이고 trace ID도 서로 달랐다.

| 단계 | 지원 문항 | 보류 문항 | 해석 |
| --- | --- | --- | --- |
| 첫 실제 13문항 | 7 통과·2 실패 | 4/4 통과 | 원래 3개 통과, 신규 지원 4/6 |
| 이어진 5문항 첫 재검증 | 1 통과·2 실패 | 2/2 통과 | N02 분류명 절단·F02 경로 실패 보존 |
| 마지막 8문항 | 6/6 통과 | 2/2 통과 | 앞선 원래 3개와 재검증 5개, 새로운 미노출 평가 아님 |

마지막 R01·N02·F02는 분류 범위와 숲 조건·열매 비중 0 초과를 유지했다. R02는 같은 기준 종의 먹이 생태 관계, R03은 180g 초과, 학명 보충 F05는 300g 초과를 확인했다. F03은 `insufficient_data/abstain`, F04는 `negated_conditions/clarify`로 남아 지원하지 않는 요청을 임의 답변하지 않았다. 이 두 응답은 답변을 내지 않았음을 보여주지만 내부 DB 읽기가 전혀 없었다는 증거는 아니다.

보정 규칙별 실관측도 구분했다. `predicate_ending`은 첫 13문항 R01에서 관측됐다. 최종 R02에서 `reference_relation`, 최종 R03·F05에서 `strict_bound_restatement`를 관측했다. 최종 N02 모델은 정확한 원문 분류명을 냈으므로 `rank_suffix` 복구 자체의 최종 live 실행은 관측하지 못했고 해당 분기는 결정론 검사 근거만 있다.

`followup8-strict-review.json`은 API 실행 결과와 같은 요청의 해석 판정을 별도로 확인한다. 별도 DB 레코드 재조회는 수행하지 않았으며, 희귀한 변형이나 모델의 반복 실행 신뢰성을 일반화하지 않는다. UI 코드 변경이 없어 이번에 Node 전체·브라우저·물리 모바일 검사를 재실행하지 않았다. 40 skip은 opt-in·입력 자료 부재 등의 제외이며 통과 수에 넣지 않았다.

---

## 5. 배포 및 형상 관리

- **최종 대상**: TEST 한정, 이미지 `robingraph-api:test-evidence-reconcile-4ab67ddcd227`, 배포 verified·healthy. 기존 active/semantic과 tracing을 유지했고 working tree와 release manifest가 일치했다.
- **소스 SHA256**: `4ab67ddcd227bf42a85cc6a9e689f7b6feab7aebea6fd2ba22a62ac6f6122f91`.
- **릴리스**: `/Users/kimdove/robingraph-test/releases/evidence-reconcile-4ab67ddcd227-0c06fe`. 1차 `5432a53d88ea`, 2차 `545524582ddc`, 마지막 후보를 각각 별도 영수증에 보존했다. 작업 시작 전 TEST는 `test-blocked-tracing-54bb05bdd0b2`였다.
- **기준 HEAD**: `834c5353ca45f0640152ca4849548cd48818b266` 기반 미커밋 snapshot. 이번 변경을 커밋한 해시가 아니다.
- **브랜치**: `dev-codex`, 기존 dirty 변경 보존.
- **Production**: 배포·재시작·이미지 교체 없음.
- **Git**: commit·push·merge 없음.
- **데이터**: 조류 DB 쓰기 0. 자료 생성·백필·마이그레이션·인덱스 교체는 실행하지 않았다. 전체 DB checksum 불변 감사는 수행하지 않았다.

---

## 6. 한계 및 후속 사항

- RG-212 전체 진행 중을 유지한다. 세 원인의 보완이 전체 자연어·모든 조건·모든 분류군의 의미 해석 완료를 뜻하지 않는다.
- 기존 독립 20문항의 불확실한 결과와 직접 생태 자료 부족은 이번 작업 범위가 아니다. 과거 평가 수치를 새로운 성공으로 바꾸지 않는다.
- 실제 감사 모델 판단은 관측된 판단이지 객관적 정답의 보증이 아니다. 안전 반례와 실제 요청 결과를 함께 기록한다.
- 한국명 “비둘기과”의 이름 해소 실패는 남아 있다. 학명 성공과 같은 결과로 취급하지 않으며 별도 이름 자료 점검이 필요하다.
- 상세 기록을 Obsidian에 반영하고 RG-212 관련 링크를 갱신한 뒤 저장 내용과 로컬 원문을 재조회해 일치시켰다. 다른 작업의 상태와 기존 평가 기록은 보존했다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/6xx 관측·평가/2026-10-24-답변중단-원인-MLflow-관측-확장|실제 중단 원인 3개를 확인한 관측 작업]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-24-RG212-시맨틱-보류원인-보완-실제재평가|선행 RG-212 평가와 남은 한계]]
