---
created: 2026-10-26
date: 2026-10-26
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags: [worklog, robingraph, semantic, record-query]
---

# [RG-212 후속] 기록 확인·조건 미적용 표현·특정 식물 먹이 기준 종 보완 — 2026-10-26


## 요약

최종 TEST `6a95918a5533`에서 기존 84문항은 82/84·26/28군, 원 gold12 노출 재검증은 10/12·3/4군, 신규 8의 노출 재검증은 8/8·동치 4/4였다. 초점 네 사례는 4/4, 1단계에 11/24였던 자료의 같은 문항 재검증은 24/24였다. 이 값들은 이미 공개된 문항을 보완한 회귀이며, 최초 신규 24의 11/24·신규 12의 8/12·신규 8의 5/8을 그대로 보존한다.

최신 전체 Python 검사는 1,320 실행·1,280 통과·40 skip·0 실패(25.338초), 독립 고유 72 methods 통과다. 남은 기존 84의 두 실패와 원 gold12의 두 평가작성 문제는 별도로 남긴다. 새 8은 대조 없는 동치쌍이어서 raw 전체군 0/4를 대조 포함 성능으로 해석하지 않는다.

이 작업은 앞서 남은 E04A·E04C·E05B·E08B 네 사례의 공통 질문 유형을 개선하는 범위다. 1단계에서는 초점 네 사례가 통과했지만 전체 회귀는 56/60·16/20군이었고, 당시 별도 새 24문항 첫 평가가 11/24·1/8군에 그쳤다. 네 문장만 통과한 결과로 종료하지 않고 같은 네 유형의 기록 확인·원문 근거·비율 미적용 metadata·식물 종 동일성 처리를 공통 보완했다.

단계별 최초 실패와 수정 후 회귀는 분리해 보존한다. RG-212는 진행 중이며 Production 배포·조류 DB 쓰기·Git commit/push로 범위를 확대하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 현재 상태 | 근거와 한계 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 네 사례에서 드러난 공통 질문 유형 보완 | 1단계 새 24문항의 9 false hold·4 보류 이유 오류 보존 |
| 설계 및 해결 방안 | 원문·조건 유형·질의 metadata 구분 | guard·감사 유지, 전체 조건 누락에는 감사 의존 한계 |
| 코드 / 설정 수정 | 앱 3파일 | semantic_graph_intent·graph_condition_extractor·generation |
| 실서비스 배포 | 최종 TEST `6a95918a5533` verified | 연결 장애 때 같은 TEST 이미지로 stop/start 복구, 운영 미반영 |
| 검증 및 테스트 | 기존 84=82/84·feedback 12=10/12·recheck 8=8/8 | 최초점수·gold문제·대조미설계 별도 보존 |
| 형상 관리 | dev-codex | 기존 dirty 보존, 운영·Git·DB 쓰기 범위 확대 없음 |

---

## 1. 작업 배경 및 문제 분석

선행 작업은 원래 실패 13건을 해결해 기존 36문항 회귀 36/36·12/12군을 통과했다. 그러나 별도 새 24문항 첫 평가에서 20/24·5/8군으로 다음 네 실패가 남았다.

| 기존 사례 | 확인된 원인 | 이번 공통 보완 범위 |
| --- | --- | --- |
| E04A | 올바른 범주값을 제안했으나 원문 기록 표현을 다른 surface로 바꿔 검증 거부 | 기록 확인 근거의 원문 보존 |
| E04C | 종 framing과 기록 확인 요청을 unresolved로 남김 | 조회 담화와 실제 조건 분리 |
| E05B | 비율 조건을 적용하지 말라는 요청을 unresolved로 남김 | 명시적 조회 조건 미적용 metadata |
| E08B | 식물 관련 “종까지”를 실제 기준 새로 오인 | 실제 먹는 주체·새 이름과 식물 종 비교 범위 구분 |

1단계의 초점 네 사례 통과 뒤에도 새로운 표현에서 실패가 많이 남았다. 그래서 1단계의 60문항과 당시 새로 측정한 24문항을 합친 84문항은 노출 회귀로 삼고, 별도 신규 12문항으로 처음 보는 표현을 검사하는 2단계를 진행했다. 이전의 최초 점수를 새 성공으로 덮어쓰지 않는다.

---

## 2. 해결 방안 및 경계

- 기록 확인 요청과 실제 범주·비교 조건을 구별하고 원문의 조건을 그대로 사용하도록 공통 schema 설명·prompt를 보완했다. 고정 요청 동사만 찾는 `_RECORD_REQUEST`와 실제 source record state·기록값 copula의 증명을 분리했다. 감사에도 schema 설명을 제공했다.
- 비율 차원·조회 대상·부정 연산의 component 문법으로 “비율을 검색 조건에 쓰지 말라”는 metadata를 처리했다. 생물학적 부정이나 실제 비율 제한을 임의 삭제하지 않는다.
- 공유 enum 값은 원문 field가 무엇인지 명시적으로 확인한다. 모호한 bare value를 어느 형질로든 임의 확정하지 않는다.
- 식물 종 명사와 정확한 동일성 predicate를 별개 원문 span으로 claim해 역순 표현도 처리했다. 다른 관계에 사용된 span과 추가 제약은 남긴다.
- 긍정 단서가 없는 부정 질문은 명시적 field·새 대상·NOT를 근거로 보류를 보존한다. 1단계 F03C의 누락을 자료/문서 guard 문제로 설명하지 않는다.
- 특정 식물 먹이 자료 부족을 응답하기 전에 이미 추출한 추가 조건이 있으면 clarify를 보존한다. 자료 한계라는 이유로 수치·부정·다른 조건을 삭제하지 않는다.

```text
원문·조건 유형·조회 설정 → 계획·근거 검증 → 독립 감사
→ 조건을 유지한 고정 그래프 조회 / 구체적 확인 / 명시적 자료 한계
```

전체 locality 또는 field가 모델 계획에서 완전히 빠지는 경우에는 감사 모델에 의존하는 한계가 있다. 일부 원문 조각을 확인한 사실만으로 모든 누락 조건을 결정론적으로 검증한다고 주장하지 않는다.

---

## 3. 주요 구현 내용

- `src/robingraph/retrieval/semantic_graph_intent.py` — 긍정 기록 확인의 typed equality와 원문 field를 증명한다. 실제 선택 rank·유지된 typed predicate·긍정 기록 확인 frame의 union coverage로 전체·분절 unresolved를 처리한다. 같은 field와 canonical/alias value의 유일한 원문 assignment 구간만 surface로 복구한다. 짧은 value 근거도 명시적 field가 유일할 때만 확장하고 trait/op/value는 바꾸지 않는다. 기존 실행 gate와 감사는 유지한다. category equality·no-share 조건과 조회 설정 문법으로 비율 미적용 metadata를 구분한다.
- `src/robingraph/retrieval/graph_condition_extractor.py` — 실제 먹는 주체 이름과 식물 종 동일성의 각 원문 span을 구별하고 추가 조건의 ambiguity·명시적 부정 cue를 보존한다.
- `src/robingraph/generation.py` — 공통 schema·prompt에 원문 복사, 근거 유형, metadata와 실제 제약의 구분을 명시하고 감사에 schema 설명을 제공한다.

변경한 테스트 파일은 다음과 같이 검증 범위로 묶었다.

- 식물 관계·기준 종·원문 순서: `tests/test_graph_fruit_reference_subject.py`, `tests/test_graph_plant_identity_order.py`.
- 기록 표현·부분 구간·coverage·field 증명·assignment: `tests/test_graph_recorded_queries.py`, `tests/test_graph_record_fragments.py`, `tests/test_graph_record_coverage.py`, `tests/test_graph_record_field_proof.py`, `tests/test_graph_record_assignments.py`.
- 질의 metadata·명시적 field·공유 enum·공통 source 계약: `tests/test_graph_query_dimension_metadata.py`, `tests/test_graph_explicit_field_binding.py`, `tests/test_graph_typed_enum_names.py`, `tests/test_graph_source_contract_followup.py`.

각 파일은 정상 조건뿐 아니라 추가 조건 누락·부정·field 오인·금지 요청을 함께 검사한다. 실제 API 검증과 모의 검사의 결과는 아래에 따로 구분했다.

1단계 앱 범위는 2파일이었으며 현재 최종 범위는 generation이 추가된 3파일이다. `services.py`와 API 계약 변경은 이번 범위에 없다. `task-source-scope.json`과 `app-changes.patch`에 다른 기존 dirty와 구분한 이번 변경을 기록했다.

`_record_field_matches`는 알려진 label의 긴 비중첩 구간을 우선하고, 선행 label이 정확히 하나이며 계획 trait와 같아야 증명한다. record reconciliation 진입·긍정 equality 복구·frame/union coverage·`_build`에서 공유한다. label 없는/모호한 기록 질문은 보류한다. 현재 `_build`의 field binding은 기록 동사 유무와 관계없이 모든 categorical 조건에 적용한다. negative whole/partial/rank-only/empty와 wrong-trait·empty-unresolved 반례를 검사했다.

현재 증거 루트는 `docs/verification/assets/2026-10-26-record-query-followup/`이다. 현재 자료는 `data/eval/graph_questions/question-families-v6/`의 기존 84·feedback 12·holdout 8이며, 같은 holdout 8의 후속 실행은 노출 recheck로 분리했다. v4·v5는 이전 단계 자료로 보존한다. v4의 회귀 헤더는 실제 60문항 provenance를 명확히 정정했지만 질문·request·expected는 불변이다. v5의 84문항도 이전 원문·expected를 그대로 합친 노출 회귀다.

---

## 4. 검증 및 테스트 결과

### 최종 검사·평가 범위

전체 Python은 `python -m unittest discover -s tests -v` 방식의 기존 검사를 사용했다. 최신 전체 검사 `unit-full.log`는 1,320 실행·1,280 통과·40 skip·0 실패(25.338초)다. skip은 전용·일회용 DB opt-in 미설정 또는 pinned 자료 부재로 실행하지 않은 검사다. 최신 후보는 독립 고유 72 methods PASS와 QA 승인을 받았다. 이전 독립 신규 24·기존 32 검사와 합산하지 않는다.

synthetic typed enum 질문에는 field 문맥을 추가했고, 여러 field에서 공유하는 모호한 bare value는 차단하도록 검사했다. 단위·mock·fixture와 실제 API 성능은 별개다. 최종 실제 결과는 기존 84=82/84·26/28군, feedback 12=10/12·3/4군, recheck 8=8/8·동치 4/4다. 각 split은 별도로 보고하며 최초 평가를 대체하지 않는다.

| 단계와 자료 | 문항 판정 | 질문군 판정 | 성격 |
| --- | --- | --- | --- |
| 1단계 기존 60 attempt1 | 57/60 | 17/20 | 피드백 노출 회귀 |
| 1단계 기존 60 attempt2 | 58/60 | 18/20 | 피드백 노출 회귀 |
| 1단계 기존 60 attempt3 | 56/60 | 16/20 | 초점 네 사례는 통과, 전체 네 실패 잔존 |
| 1단계 별도 새 24 최초 | 11/24 | 1/8 | 9 false hold·4 보류 이유 오류, 그대로 보존 |
| 2단계 기존 84 attempt1 | 80/84 | 25/28 | 앞선 60+24, 신규 독립 평가 아님 |
| 2단계 기존 84 attempt2 | 80/84 | 당시 원점수 보존 | 원문 assignment 복구 후 노출 회귀 |
| 최종 기존 84 | 82/84 | 26/28 | 같은 문항의 추가 노출 회귀 |
| 2단계 별도 새 12 최초 | 8/12 | 2/4 | 실패 4 중 gold 2문제·구현 2오류 구분 |
| 별도 새 8 최초 | 5/8 | 동치 정확 2/4, raw 전체군 0/4 | 대조 없는 구조의 raw군점수 한계 분리 |
| 원 gold12 feedback | 10/12 | 3/4 | gold 작성문제 2건 유지, 최초 8/12 불변 |
| 최종 동일 8 recheck | 8/8 | 동치 4/4·raw 전체군 0/4 | 최초 5/8 불변, 추가 미노출 패킷 없음 |

### Gold 작성·독립 검토

신규 자료는 모두 모델 작성·모델 검토이며 사람 검토는 없다. Writer는 gold reviewer 역할에서만 본문을 읽고 앱·파서·새 테스트·trace·신규 패치를 보거나 실행하지 않은 상태에서 의미·동치/대조·분류 범위·부정/조회 설정을 검토했다. 질문 본문은 구현자에게 전달하지 않았다. 이 검토가 실제 자료 존재나 API 성공을 뜻하지 않는다.

| 자료 | 구성·검토 | 고정 SHA256 |
| --- | --- | --- |
| 1단계 새 24 | 8군·지원 18/보류 6(부정 2·특정식물 4), 5계급·5형질, peer PASS·수정요청 0 | `cb7259d87a1956c4a776924f1b257e09a35400cb117781f9825f10c3641fd776` |
| 2단계 새 12 | 4군·지원 8/보류 4(부정 2·특정식물 2), peer PASS | `7134f4c197fdc1ada0bc629b673f9c9107ec754992701fb99d4d752a14c35d73` |

2단계 새 12문항은 API 전에 기대 범위 계급 7필드·보류 expected4개 형식을 정정했고 질문·조건값은 변경하지 않았다. 여기에 기록한 새 자료에는 수치 비교 coverage가 없다. 기록값 확인 질문은 조건조회로 평가하며 일치 답변·검색 결과 없음·직접 자료 부족을 분리한다. 결과를 보고 수정·재실행한다면 노출 회귀로 표시한다.

### 1단계 실제 실패 이력 — 당시 결과 보존

**Attempt1:** E04A·E05B·E08B는 회복했고 E04C는 `["확인해 줘"]` 부분 unresolved 때문에 남았다. 증명된 긍정 기록 확인 원문 frame에 완전히 포함되는 유일한 fragment를 처리하도록 보완했으며 특정 문구 예외를 추가하지 않았다. 나머지는 V2-07B의 faithful true·nonempty issues 모순에 대한 기존 fail-closed와 V2-12B 자체 제외·생략 관계 근거 실패였다. 두 출력을 변경 전후 앱에 오프라인 재생해 같은 보류임을 확인했다. 새 API 호출이나 현재 패치 회귀의 증거로 계산하지 않았다. 첫 점수·정확한 HTTP root60·실패 3은 `regression-attempt1/`에 보존했다.

**Attempt2:** E04C와 V2-12B가 남았다. 당시 E04C unresolved가 rank·predicate·request 전체로 커져 단일 frame 포함 범위를 벗어났으므로 공통 union coverage 증명이 필요했다. 전체 결과는 `attempt2/`에 보존했다. 요청 범위는 네 공통 유형이며 기존 V2-12B를 별도 새 기능으로 확대하지 않았다.

**Attempt3:** 초점 네 사례는 통과했다. E04A는 답변, E04C·E05B는 조건 일치 검색 후 결과 없음, E08B는 정확한 특정 식물 먹이 자료 부족이었다. 나머지 실패는 V2-01B의 proposal null·interpretation_error(세부 원인 미확정), V2-11C의 원문 없는 surface, E06B·E07C 감사의 실제 threshold/habitat 누락 오판이었다. 마지막 세 출력의 baseline/최종 앱 오프라인 재생이 모두 같은 보류였으며 이 관측만으로 확률적 변동의 빈도를 일반화하지 않는다. 독립 재채점도 56/60·16/20군이었다.

당시 trace 조회에서 MLflow timeout이 발생했지만 첫 HTTP 60은 모두 저장돼 있었다. 31행 처리 시점부터 resume했고 `trace-resume-verification.json`에서 첫 응답 SHA 불변·새 POST 0을 확인했다. 정확한 HTTP root60을 재조회해 채점했으며 응답을 교체하지 않았다.

**당시 새 24 최초 평가:** 11/24·1/8군으로 독립 재채점도 같았고 평가기 오판은 확인되지 않았다. 네 문장 통과만으로 종료할 수 없어 같은 네 유형의 공통 보완을 계속했다. 해당 소스·평가 전체는 `phase1-first-evaluations/`에 복사 보존했다. 이때의 실패를 현재 새 12문항 평가와 혼합하지 않는다.

### 2단계 첫 84문항 실측과 후속 안전성 이력

첫 84문항 회귀의 정확한 HTTP root84·고유 trace를 확인했고 80/84·25/28군이었다. 이전 새 24문항은 최초 11/24에서 노출 회귀 21/24로 바뀌었다. 첫 실패 13개 중 11개는 회복했지만 F01B·F01C가 남았고 F04A의 새로운 surface 변동 실패가 있었다. 나머지 V2-10B는 요청 범위 밖 사례이며 baseline/current에 저장 출력을 재생해 같은 보류임을 확인했다.

첫 84문항의 응답·로그·이미지·동결은 `phase2-attempt1/`에 보존했다. trace 시계차 때문에 검색 창을 start-10000으로 확장했으나, `independent-clock-resume-verification.json`에서 초기에 저장된 12 HTTP 응답의 SHA·본문·상태·elapsed 불변과 새 POST 없음을 확인했다. 이 처리를 새 실측이나 성공 응답 교체로 세지 않는다.

기록 관련 세 실패에 대해 동일 field·value의 유일한 원문 typed record assignment를 복구하는 공통 helper를 보완했다. QA는 미배포 후보에서 source offset3·단어 내부 label3·조회 금지 1 반례를 발견했고 로그를 보존한 뒤 수정했다. 이를 실제 API 오실행으로 단정하지 않는다. 반례 수정 후 중복 제외 65 methods를 통과했다. 당시 신규 12는 봉인 상태였고 이후 최초 결과는 아래에 별도로 보존했다.

### 2단계 두 번째 실측과 신규 12문항 gold 한계

원문 assignment 복구 후 기존 84문항 실측도 80/84였으며 `phase2-attempt2/`에 보존했다. 별도 신규 12문항 첫 결과는 8/12였다. 이후 의미 재판정에서 실패 4개 중 2개는 gold 작성 문제, 나머지 2개는 유효 구현 오류로 구분했다. 원본 gold와 8/12 점수는 그대로 유지하며 사후 수정 점수로 대체하지 않는다.

기존 alias에서 “먹이 범주”는 `trophic_niche`, “먹이 유형”은 `diet_category`다. 신규 12의 해당 군 01은 niche label과 category enum의 상충으로 단일 gold를 확정하기 어려웠고, 03은 여러 field에서 공유하는 enum이어서 diet_category만 정답으로 잡을 근거가 부족했다. 02는 canonical `diet_category`가 명시돼 명확했다. 작성자와 peer 모두 초기 imported alias mapping 검토를 놓친 한계를 인정했다. 근거는 `adjudication-label-ambiguity.json`·`adjudication-label-ambiguity-peer.json`이며 trace를 보지 않고 허용 vocabulary 상수로 재판정했다.

유효 구현 오류인 canonical field enum 요청어 지원·복합 식물 종 관계의 원문 claims, 기존 F04B의 기록값 조건형 원문 회복을 보완했고 QA 승인을 받았다. 당시 후속 TEST 후보를 배포했고 실제 결과는 최종 비교표에 별도로 기록했다.

### 별도 신규 8문항 사전 독립 검토

새 자료는 4개 동치쌍·8문항, 지원 4·보류 4다. 명시적 trait label/canonical identifier와 enum·계급·metadata/생물학적 부정·정확한 식물 종 동일성을 정적으로 검토했다. 대조 문항이 있는 앞선 3문항 군과 달리 각 군은 동치 2개만 있어 대조 검증을 포함했다고 주장하지 않는다.

API 전에 중복 case ID4개를 고쳤고 질문·expected는 바꾸지 않았다. 최종 SHA256 `147fd0710df809805e4687b45f46cb15aabc0434108b52ac23dc47564b67cac5`, unique IDs8, peer PASS다. 모델 작성·모델 검토이며 사람 검토는 없고 수치 비교 coverage도 없다. 앱 로직·패치·API·테스트·trace를 보지 않고 허용 상수·catalog만 참고했으며 본문은 구현자에게 전달하지 않았다. 당시 검토 후 첫 실측과 노출 재검증을 각각 수행했고 아래에 별도로 기록했다.

### 후속 공통 보완과 당시 미배포 QA 이력

F04B의 기록값+조건형 원문 회복, 명시적 canonical field code 자체를 근거로 인정하는 처리, 식물 종 명사 수식어와 동일성 선택 clause의 공통 claim, 미사용 비율 component 문법을 보완했다. 특정 질문 답변을 저장해 재사용하는 변경이 아니다.

미배포 QA 중 canonical field 조회 금지 요청을 허용하는 반례를 발견해 부정 활용 guard를 추가했고, 이어 “인지 말해줘” 정상 요청을 잘못 막는 회귀를 발견했다. 활용형 범위를 제한해 금지와 정상 요청 모두 검사를 통과했다. 이 미배포 실패 이력을 보존하며 실제 API 오실행으로 표현하지 않는다.

v6 평가 자료는 기존 84 회귀, 원 gold를 유지한 기존 12 노출 재검증, 별도 신규 8 첫 평가로 분리한다. 원래 신규 12의 8/12 점수와 gold 작성 문제는 유지하고 각각 별도 raw metric으로 기록한다. 새 8 SHA도 변경하지 않았다.

### 신규 8문항 최초 결과와 노출 재검증 전환

신규 8 첫 실측은 5/8·wrong hold reason3건이었다. 원래 gold와 strict score는 그대로 보존했다. raw 전체군 점수는 0/4인데, 이 자료는 대조 문항 없이 동치 2개만 구성돼 평가기의 `contrast_distinguished`가 구조적으로 false이기 때문이다. 동치 판정은 2/4였으며 raw 0/4를 의미 해석이 모두 실패했다는 뜻으로 해석하지 않는다. 반대로 대조 검증이 수행됐다고 주장하지 않는다.

`phase3-first-evaluations/`에 최초 응답·점수·manifest를 보존했다. 이후 canonical habitat NOT 단서·식물 종 동일성 재진술·관계절의 식물 관계를 lexical 공통 로직으로 보완했다. QA 고유 72와 전체 1,320 실행·1,280 통과·40skip·0실패(25.338초)를 확인했다. 이후 최종 TEST에 배포했고 실제 노출 재검증 결과는 아래와 같다.

같은 8의 재실행은 recheck split의 피드백 노출 회귀로만 표시한다. v6 현재 manifest의 feedback-exposed 상태는 갱신하되 원래 first manifest snapshot은 보존했다. 추가 unseen 패킷은 만들지 않는다. 기존 84와 원 gold12의 feedback 재검증을 포함해 세 split을 별도 보고한다.

앞선 82/84 시도의 두 실패 중 F03B는 모델이 trophic_niche를 share로 잘못 매핑해 정상 보호 검증이 차단한 경우다. V2-10B는 numeric predicate tail 검증에서 보류됐다. 둘 다 baseline/current 오프라인 재생에서 같은 보류임을 확인했다. 모델 오제안을 정상 차단한 사실과 지원 질문에 답하지 못해 평가상 실패한 사실을 구분한다. 이 작업으로 전체 RG-212가 완료됐다고 선언하지 않는다.

### 최종 실제 결과와 TEST 연결 복구

최종 기존 84는 82/84·26/28군이었다. 초점 E04A·E04C·E05B·E08B는 4/4 통과했고, 원래 최초 11/24였던 자료는 동일 문항 노출 회귀에서 24/24였다. 원 gold12 재검증은 10/12·3/4군이며 gold 작성문제 2개를 그대로 남겼다. 신규 8 재검증은 8/8·동치 4/4였지만 대조 미설계 때문에 raw 전체군 0/4를 유지한다. 정답 자료·원점수·평가기 구조를 바꿔 전부 통과한 것처럼 집계하지 않는다.

최종 기존 84의 잔여 실패는 V2-07A의 감사 거부와 V2-10B의 수치 경계 guard 보류다. 두 저장 출력을 원래 앱과 현재 앱에 오프라인 재생해 같은 보류를 확인했다. 이번 패치의 신규 회귀라는 근거와 지원 질문에 답하지 못한 평가상 실패를 구분하며 RG-212 전체 완료로 선언하지 않는다. 이전 82/84의 F03B 모델 오매핑 실패와 최종 V2-07A 감사 거부를 서로 바꿔 기록하지 않는다.

실측 중 OrbStack published port 연결 장애가 발생했다. CLOSE_WAIT/FINWAIT 16,263 owner 관측 뒤 TEST 앱만 stop/start했고 같은 이미지·source를 유지한 채 2쌍으로 줄어 로컬·공개 health 200이 복구됐다. 누적 원인은 확정하지 않았다. `port-proxy-recovery/independent-port-recovery-verification`에서 이미 저장된 35 HTTP의 SHA·본문·상태·elapsed 불변과 재POST35건 없음이 독립 확인됐다. 새로 요청하지 않은 pending 문항만 이어 실행했다. 연결 복구를 모델 응답 실패 수정이나 성공 응답 교체로 표현하지 않는다.

최종 독립 검증 `independent-final-metrics.json`은 regression 84·followup 12·recheck 8과 별도 first 8의 고유 trace 112개·HTTP 200·root 원문 일치를 확인했다. root outputs는 저장 HTTP 응답에 기존 마스킹을 적용한 값과 일치했으며, 마스킹 전 전체 payload가 동일하다는 주장은 하지 않는다. 각 최초 응답을 보존했고 검증자의 새 API 호출은 0이었다. 포트 복구 때의 35개 응답, 과거 점수 5건의 행·counts·gold 불변, 최신 독립 72 methods 승인 소스의 해시 일치도 재확인했다.

Read-only root 확인 flag를 응답 메타에 추가한 뒤 점수 메타의 response-file hash가 오래된 상태로 남은 것을 발견했다. `score-before-root-readback` 원본을 보존하고 같은 gold·평가기·응답으로 재채점해 행별 판정과 counts가 같음을 확인했다. `root-readback-score-provenance.json`에 이 provenance 정정을 기록했으며 새 API 호출은 0이었다. 응답 의미나 정답을 바꿔 점수를 올린 정정이 아니다.

### MLflow 저장·재조회

기존 실험 33의 [기록 질의 공통 보완 평가 run](https://mlflow.dove-nest.com/#/experiments/33/runs/0ef42977885444df85a8d6ac1bacdbbe)은 FINISHED다. `mlflow-evaluation.json`에서 저장과 artifacts 재조회를 확인했다. 최종 regression 84·followup 12·first 8·recheck 8의 raw metric을 분리하고, 이전 first 24=11/24·first 12=8/12·first 8=5/8과 원 gold 한계를 보존했다. 모델 평가가 공개된 뒤의 recheck를 새로운 독립 성능으로 표시하지 않았다.

### 1단계 로컬 안전성·회귀 이력 — 당시 검사

| 당시 단계 | 전체 실행/통과/skip | 시간 | 독립·모의 확인 |
| --- | --- | --- | --- |
| 초기 통합 | 1,302 / 1,262 / 40 | 23.982초 | 원인 3 baseline clarify→수정 answer; 반례 포함 16 mock probes=1method, fruit23methods |
| 부분 frame 포함 보완 | 1,303 / 1,263 / 40 | 24.868초 | 독립 신규 10·기존 32 |
| union 후보 | 1,304 / 1,264 / 40 | 25.256초 | 356 mock probes 이후 독립 안전반례 1 발견 |
| field 증명 보완 | 1,305 / 1,265 / 40 | 24.970초 | 독립 신규 16·기존 32·영구record4 |
| 2단계 첫 후보 | 1,314 / 1,274 / 40 | 24.413초 | 독립 신규 24·기존 32, scoped source 승인 |
| 기록값 복구 후보 | 1,315 / 1,275 / 40 | 24.448초 | 중복 제외 독립 65 methods, QA 승인 |
| canonical/식물 관계 보완 후보 | 1,319 / 1,279 / 40 | 24.400초 | 독립 고유 68 methods, QA 승인 |
| 최종 lexical 공통 보완 후보 | 1,320 / 1,280 / 40 | 25.338초 | 독립 고유 72 methods, QA 승인 |

표의 전체 결과는 각 시점 0실패였지만 별도 독립 검사에서 발견한 결함은 따로 남겼다. 중복되는 methods/probes를 합산하지 않는다. 초기 독립 신규 8·기존 32·영구 record 1/fruit 2 통과의 당시 source SHA는 `regression-attempt1/independent-final-signoff.json`과 `phase1-first-evaluations/independent-final-signoff.json`에 보존했다. 루트의 최신 `independent-final-signoff.json`은 현재 소스의 고유 72 methods 검사 근거다. field 보완 이후 근거는 `independent-source-review.json`이다. graphify 갱신도 당시 수행했다.

초기 fruit 검사에서는 유효한 수치 조건 누락 1을 발견했고 ambiguity 유지 수정 후 23methods를 통과했다. `fruit-unit-initial.log`·`fruit-unit.log`를 모두 보존했다.

Union 후보의 독립 QA는 같은 `Omnivore`가 trophic_level/trophic_niche에 유효해 잘못된 field도 증명으로 오인하는 반례 1을 발견했다. 후보는 당시 미배포였고 `record-union-guards.log`·`record-union-before-field-proof/`에 보존했다. 실제 API 오실행으로 기록하지 않는다. 이후 `_record_field_matches`와 whole/partial/rank-only/empty 부정·wrong-field 검사로 보완했다. 이전 mock/전체 통과가 이 발견을 지우지 않는다.

---

## 5. 배포 및 형상 관리

- **최종 TEST 이미지**: `robingraph-api:test-record-query-followup-6a95918a5533`, verified.
- **최종 전체 소스 SHA256**: `6a95918a55332aa0195c07bf4e5a9c60a7cb006b67fd56d255d683f22c72c922`.
- **복구**: TEST 연결 장애로 같은 이미지·source의 앱만 stop/start했다. 로컬·공개 health 200을 확인했고 누적 원인은 미확정이다.
- **실제 평가**: 최종 84=82/84, feedback 12=10/12, recheck 8=8/8. 최초 신규 8점수 5/8·원 gold12점수 8/12는 보존했다.
- **범위**: Production·commit/push·조류 DB 쓰기 없음. 다른 기존 dirty는 보존한다. 최종 전체 source hash·HEAD 불변, healthy 및 MLflow readback을 확인했다. 전체 조류 DB checksum 불변 감사는 수행하지 않았다.

### 이전 이미지 식별자 — 배포 이력

2단계 첫 후보는 `robingraph-api:test-record-query-followup-083d06b49825`, 전체 source SHA256 `083d06b4982592e0c11c290d3ec4657454d1bfc97946824ba606e33529abdae0`였고 verified·code freeze 후 첫 84문항을 측정했다.

| 1단계 후보 | 소스 SHA256 | 릴리스·당시 확인 |
| --- | --- | --- |
| `6c8e05ad15da` | `6c8e05ad15da889ac6d0af89e6dcf4225ed12d5bf03087ac69500094221d3cd2` | `record-query-followup-6c8e05ad15da-8f56eb`, verified·active/semantic |
| `8dd578c3076c` | `8dd578c3076ce0acfa566579ceb37141107878a926754e7fb64b69a10d7631f4` | 당시 두 번째 실측 후보 |
| `aaf802327b68` | `aaf802327b682a54cd3997b873a710354b1438bb71f81785e693b48e7040ed12` | `record-query-followup-aaf802327b68-800066`, 당시 healthy·source/gold/HEAD 불변 |

당시 로컬·공개 health 200·neo4j 및 network-none fixture smoke를 확인했다. 이 표는 과거 배포 근거이며 현재 상태는 위의 최종 6a95918a5533 이미지다.

---

## 6. 한계 및 후속 과제

- RG-212 진행 중을 유지한다. 네 공통 유형의 개선이 전체 질의 지원 완료를 뜻하지 않는다.
- 전체 field/locality 누락의 감사 모델 의존, 모델 gold의 사람 검토 부재, 자료의 제한된 표현 coverage를 유지한다.
- 기존 국명 해소·직접 자료 부족·지원하지 않는 조건은 실제 해결 근거 없이 완료로 바꾸지 않는다.
- 실브라우저 UI 검증은 UI 코드 변경이 없어 이번에 실행하지 않았다. 실제 HTTP/API·trace 검증과 브라우저 상호작용 검증을 혼동하지 않는다. 물리 모바일 검사도 수행하지 않았다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-26-RG212-조건경계-13건보완-신규24평가|선행 13건 보완과 남은 새 실패 4건]]
