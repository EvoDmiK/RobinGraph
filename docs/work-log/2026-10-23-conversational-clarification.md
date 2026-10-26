---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags: [worklog, robingraph, clarification, experimental]
---

# [RG-212 후속] 오타·애매한 표현 확인 후 원래 관계 질문을 이어가는 흐름 — 2026-10-23

## 요약

본 작업은 RG-212의 후속 확인 질문 구현이며 전체 시맨틱 일반화의 완성이 아니다. 사용자가 “청둥오리랑 비슷한 식생을 가진 새”처럼 의미가 애매하거나 “천둥오리”처럼 이름 확인이 필요한 질문을 입력하면, 의미와 종을 임의로 확정하지 않고 선택을 요청한다. 의미 선택 후에는 해당 단어만 바꾸고 나머지 조건을 유지한다. 종 후보를 선택하면 원래의 먹이·서식 환경 관계 질문을 이어간다.

식생은 식물 군집을 뜻할 수 있으므로 식성으로 자동 교정하지 않는다. “식성·먹이 생태 범주”와 “서식 환경”을 선택지로 제시하고 식물 군집 자체의 유사성 비교는 지원하지 않음을 알린다. 이름 오타 역시 기존 벡터 후보를 제시한 뒤 사용자의 선택을 기다린다. 지원하지 않는 복합 조건은 원문에 남겨 기존 가드로 처리하며 자료에 없는 관계를 추론하지 않는다.

상태는 **진행 중·TEST 실험**이다. 최초 독립 작성 16문항에서 CL-03·CL-04의 표현 미지원이 확인되어 표현 처리를 보완했고 같은 문항을 재검증한다. 최종 결과는 피드백 노출 회귀 검증으로 기록하며 미노출 정답률로 해석하지 않는다. 최종 영수증에서 실제 API 16문항·44요청과 브라우저 8시나리오·20 POST 요청을 확인했다. 브라우저는 모두 최종 answer 및 요청한 생태 관계 범주를 확인했으나, API 전체를 16/16 정답으로 평가하지 않는다. 이전 RG-212의 지원 문항 false hold 6건을 이번 작업에서 전부 해결했다고 주장하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 애매한 의미와 이름을 확인한 뒤 질문 계속 | 의미 선택과 종 후보 선택을 분리하고 원래 관계·다른 조건을 보존 |
| 설계 | 선택형 clarify 계약 | `ChatClarifyResult.choices`에 `{label, question}` 최대 3개, 빈 선택지는 직렬화에서 제외 |
| 호환성 | 기존 응답 형태 유지 | 선택지 기본값 빈 배열(`[]`); 기존 profile 후보 payload 유지, graph 후보에는 `route_intent: auto` 추가 |
| 안전한 이름 처리 | 공통 치환 헬퍼와 경계 검증 | 아종을 종으로 부분 치환하지 않으며 붙인 조건·중첩 종명·기존 이름의 부분 문자열 위험은 구체적 확인 질문 |
| UI | 선택 후 원래 질문 계속 | generic 선택 시 필터를 비우되 scope 유지; stale·busy 가드 적용 |
| 자동 검증 | 백엔드 115·프런트엔드 317 통과 | 아래 실제 실행 명령 기재; Writer가 재실행한 결과가 아닌 구현 담당 영수증 |
| 독립 검토 | offline 16문항·안전 7검사 | mock/가드 검토이며 실제 DB/API 검증과 구분 |
| 실제 검증 | API 16문항·44요청, 브라우저 8시나리오·20 POST | API는 피드백 노출 회귀; 브라우저 최종 answer 및 관계 범주 일치, 오류·overflow 0 |
| 배포 | TEST active/semantic | `8a18de290625` 이미지, 208개 소스 manifest 일치·healthy; Production·DB 쓰기·Git commit/push 없음 |

---

## 1. 작업 배경 및 문제 분석

사용자는 정규식이나 단일 표현 보완을 넘어, 이해하기 어려운 표현을 확인하면서 대화가 이어지기를 요청했다. “식생”을 곧바로 식성으로 취급하면 사용자 의도를 바꿀 수 있고, “천둥오리”를 청둥오리로 확정하면 종 식별을 건너뛰게 된다. 종을 선택한 뒤 단순 프로필로만 이동하면 원래 요청한 관계 조회도 잃는다.

이에 의미 확인 → 필요한 경우 종 확인 → 원래 관계 조회 순서를 구현했다. 질문의 일부만 교체하고 나머지 조건은 유지하므로 선택 이후에도 미지원 조건을 제거하거나 실행 가드를 우회하지 않는다. 아종 학명의 종명 부분만 바꾸는 치환과 중첩된 이름·조건을 삼키는 치환도 별도로 제한한다.

## 2. 해결 방안 및 설계

1. “식생”의 의미가 애매하면 조회 전에 선택지를 반환한다. 선택지는 식성·먹이 생태 범주 또는 서식 환경이며 원문에서 그 단어만 대체한다. 식물 군집 비교를 지원한다고 안내하지 않는다.
2. 이름이 정확하지 않으면 기존 벡터 후보를 보여 준다. 사용자 선택 전 청둥오리로 확정하지 않는다. 선택한 이름을 원래 질문에 안전하게 반영한 후 같은 관계 질문을 다시 처리한다.
3. graph 후보 선택은 `route_intent: auto`로 원래 질문을 재라우팅한다. 기존 profile 후보는 기본 동작과 payload를 유지한다.
4. 이름 치환은 graph와 profile에서 같은 헬퍼를 사용한다. 독립된 이름 경계를 확인하며 아종→종 부분 치환, 조건이 붙은 이름, 중첩 종명, 알려진 이름의 부분 문자열 위험은 구체적 clarify로 돌린다.
5. 기존 parser는 관계 범주 명사 앞의 “비슷한/같은/동일한”, “조류”, “보여줘/찾아줘/궁금해” 등의 제한된 표현 변화를 처리한다. 지원하지 않는 복합 조건은 그대로 유지한 후 기존 가드가 판정한다.

## 3. 주요 구현 내용

- [services.py](../../src/robingraph/api/services.py): 의미 선택 응답, 종 선택 뒤 원래 질문 계속 처리.
- [question_entities.py](../../src/robingraph/api/question_entities.py): 이름 치환 공통 헬퍼와 경계 확인.
- [schemas.py](../../src/robingraph/api/schemas.py): `ChatClarifyChoice`, 선택지·후보 라우팅의 추가 필드 계약.
- [species_questions.py](../../src/robingraph/retrieval/species_questions.py): 관계 범주·요청 표현 처리.
- `src/robingraph/api/static/`의 `chat.js`, `styles.css`: 확인 선택지 렌더링과 재요청, 필터·scope 및 stale·busy 상태 처리.
- [openapi.json](../../src/robingraph/api/drf/openapi.json), [openapi_ingest.json](../../src/robingraph/api/drf/openapi_ingest.json): 새 속성의 계약 정합 갱신.
- `tests/test_chat_clarification.py` 신규, `tests/frontend/chat_ui.test.js`, `tests/test_drf_parity.py`: 확인 흐름·UI·호환성 검증.

schemas와 OpenAPI의 기존 dirty 변경은 보존한다. 이번 작업은 새 속성에 필요한 정합 갱신 범위를 기록한다. 고정 migration gold는 바꾸지 않았다. `tests/test_drf_parity.py`에서는 기존 `ChatGraphResult` 처리처럼 추가된 `ChatClarifyChoice`·`choices`·`route_intent`만 gold 비교에서 제외했고, 별도 DTO/OpenAPI 동등성 검사는 유지한다.

담당은 root Codex가 backend·통합, `clarification_ui`가 UI, `clarification_review`가 독립 16문항·안전 7검사, Writer가 문서·Obsidian 기록이다. Writer는 코드·테스트·배포를 실행하지 않는다.

## 4. 검증 및 테스트 결과

### 자동화 테스트

백엔드 실행 명령:

```bash
PYTHONPATH=tests uv run --locked --extra test python -m unittest tests.test_drf_parity tests.test_chat_clarification tests.test_species_questions tests.test_graph_semantic_api tests.test_semantic_chat tests.test_semantic_graph_intent tests.test_taxon_name_resolution
```

구현 담당이 전달한 실제 결과는 `Ran 115 tests in 1.125s — OK`이다.

프런트엔드 실행 명령:

```bash
node --test tests/frontend/chat_ui.test.js
```

전달 결과는 317 pass, 0 fail이며 fake DOM 단위 검사다. 백엔드는 mock/unit/ASGI 검사이며 실제 DB 검증이 아니다. Writer는 이 테스트들을 재실행하지 않았다.

### 독립 offline·mock 검토

[independent-offline.json](../verification/assets/2026-10-23-conversational-clarification/independent-offline.json)은 16문항에 대해 의미 선택 시 단어만 치환하는지, 확인 전 조회를 하지 않는지, 복합 조건을 우회하지 않는지 또는 애매하지 않은 질문에 메뉴를 강제하지 않는지를 확인한다. 16개 기록은 passed이나 일부는 “애매한 메뉴를 만들지 않음” 검사이며 모든 문항의 최종 관계 조회 성공을 의미하지 않는다.

[safety-recheck.json](../verification/assets/2026-10-23-conversational-clarification/safety-recheck.json)은 offline/mock 7검사이며 live DB/API 호출이 없다. 중첩 이름, 붙인 조건·종명, 아종을 종으로 소비하는 치환, 분류·지리 조건이 붙은 표현에서 7건 passed를 기록한다. 이 표본으로 모든 임의 표현의 안전성을 보장하지 않는다.

### 실제 API 단계와 피드백 노출

[first-api-results.json](../verification/assets/2026-10-23-conversational-clarification/first-api-results.json)은 response mocking 없이 16문항을 실행한 최초 기록이다. CL-03·CL-04에서 표현 미지원이 발견되었다. 이후 일반적인 활용형·요청 표현을 보완하고 같은 16문항을 재검증하므로 최종 결과는 피드백 노출 회귀 검증이다. 최초 독립 작성과 개선 후 회귀를 분리하며 미노출 정답률로 표기하지 않는다.

[api-results.json](../verification/assets/2026-10-23-conversational-clarification/api-results.json)은 실제 HTTP JSON 응답 16문항·44요청이며 `response_mocking: false`다. [summary.json](../verification/assets/2026-10-23-conversational-clarification/summary.json)에서 실행 수와 평가 유형을 확인했다.

| 확인 사례 | 최종 관측 |
| --- | --- |
| CL-01·CL-02 | 식성·서식 환경 양 선택지에서 최종 answer |
| CL-03 | 공백 및 “보여줘” 표현 보완 후 최종 answer |
| CL-04 | 학명과 “식생인 조류 … 궁금해” 표현에서 양 선택지 최종 answer |
| CL-09·CL-10 | 오타 이름 후보를 선택한 뒤 원래 관계의 answer |
| CL-14 | shared habitat answer |

복합 부정·수치·복수 종·관찰 조건·서식 환경과 숲 조건의 결합 일부는 여전히 hold 또는 API 안내의 한계가 있다. 16문항은 모두 정답으로 채점한 결과가 아니며 API 16/16 정답률로 표시하지 않는다. [legacy-api-baseline.json](../verification/assets/2026-10-23-conversational-clarification/legacy-api-baseline.json)과 [legacy-api-shadow.json](../verification/assets/2026-10-23-conversational-clarification/legacy-api-shadow.json)의 기존 shadow 7질의 fingerprint는 동일했다. 이를 active 모드의 모든 질문 보존 증거로 확대하지 않는다.

### 실제 브라우저 검사

[first-browser.json](../verification/assets/2026-10-23-conversational-clarification/first-browser.json)은 Chromium 390px·1280px × 정확한 이름/오타 이름 × 먹이/서식 환경의 8시나리오 기록이다. 정확한 이름은 의미 선택 뒤 관계 조회, 오타 이름은 의미 선택 뒤 종 후보 선택을 거쳐 관계 조회한다. `physical_mobile: false`이므로 물리 모바일 기기 검증이 아니다.

최종 [browser.json](../verification/assets/2026-10-23-conversational-clarification/browser.json)은 8시나리오·20 POST 요청이다. 390px·1280px × 청둥오리/천둥오리 × 먹이/서식 환경 흐름 모두 최종 answer와 `ecological_related`의 요청 범주 일치를 확인했다. page error 0, overflow 0이다. 의미 선택과 오타 종 후보 선택을 거쳐 원래 관계 조회로 이어지는 실제 UI/API 흐름을 확인한 결과다.

물리 모바일 기기·Safari·Firefox는 실행하지 않았다. 키보드·스와이프·움직임 줄이기도 별도 실행 증거가 없는 한 검증 완료로 표시하지 않는다.

## 5. 배포 및 형상 관리

- 통합 경로·브랜치: `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex`, `dev-codex`.
- 배포 대상: TEST 앱·빌드 Mac(.97)만. Production 배포·재시작·이미지 교체 없음.
- 최종 이미지: `robingraph-api:test-taxonomic-traits-8a18de290625`.
- 소스 SHA-256: `8a18de290625caff6e45664db0454c6e6d32f3d056bf263216eb3eab92659ab2`.
- [test-release.json](../verification/assets/2026-10-23-conversational-clarification/test-release.json)은 snapshot 배포 기록이며 최종 상태는 [runtime-verification.json](../verification/assets/2026-10-23-conversational-clarification/runtime-verification.json) 및 summary로 확인했다. 208개 파일 source manifest 일치, `healthy`, `ROBINGRAPH_GRAPH_INTERPRETER=semantic`, `ROBINGRAPH_GRAPH_INTENT_MODE=active`, 대상 `test`다. 중간 shadow 기록과 최종 active 상태를 구분한다.
- 활성화 근거: [activation-gates.json](../verification/assets/2026-10-23-conversational-clarification/activation-gates.json). 중간 gate 통과와 최종 사용자 흐름 실측을 구분한다.
- 조류 DB 쓰기 없음. 공유 벡터 인덱스 삭제·교체 없음. Git commit/push 없음.
- 문서는 상세 작업 기록과 Obsidian에 동일 내용으로 저장하고 원문 일치를 재조회했다. 메인 백로그 기존 RG-212 행과 카테고리 작업 기록 링크를 갱신했으며 다른 항목과 기존 링크를 보존했다.

## 6. 한계 및 후속 과제

- 이번 구현은 의미·종 확인 후 관계 질문을 잇는 제한된 흐름이며 전체 자연어 일반화 완료가 아니다.
- 식물 군집 유사성, 미지원 복합 조건, 자료가 없는 관계는 지원 범위에 새로 포함하지 않는다.
- 이전 RG-212의 6 false hold 전체를 이번 변경의 해결 실적으로 합산하지 않는다.
- 동일 16문항 재검증은 피드백 노출 회귀이다. 넓은 표현의 일반화 평가는 별도 미노출 문항과 판정 기준으로 진행해야 한다.
- 반환된 참조 데이터는 별도 DB oracle로 독립 재계산하지 않았다. 실제 응답·관계 범주 확인과 데이터의 독립 전수 대조를 구분한다.
- 확정된 [api-review.json](../verification/assets/2026-10-23-conversational-clarification/api-review.json)의 독립 리뷰는 핵심 CL-01·02·03·04·09·10·14에서 AVONET 범주와 출처를 확인했다. CL-05 식성 분기는 원앙 1종의 Forest·Herbivore aquatic 및 source paths를 확인했으며 서식 환경 분기는 hold였다.
- CL-06·13·15의 양 선택지, 합계 6분기는 부정·복합 조건 보류의 안내가 부족했다. CL-05 서식 환경 분기와 CL-08은 retry-later였고, CL-07은 180g 수치 조건에 대한 안내가 없었다. 안전 보류 여부와 별개로 사용성 한계가 남아 있으며 전부 정답으로 간주하지 않는다.
- Obsidian 저장 후 원문 일치를 재조회했다. RG-212는 진행 중·TEST 실험 상태를 유지했다. Production 반영은 별도 명시 승인 대상이다.

## 관련 문서

- [RG-212 시맨틱 그래프 인터프리터 실험 기록](./2026-10-23-semantic-graph-interpreter.md)
- [검증 자산 디렉터리](../verification/assets/2026-10-23-conversational-clarification/)
- Obsidian `Templates/worklog.md`, `Templates/backlog-item.md`를 이번 세션에서 조회한 구조를 기준으로 작성했다. 새 RG 번호는 할당하지 않고 RG-212 후속으로 기록한다.
