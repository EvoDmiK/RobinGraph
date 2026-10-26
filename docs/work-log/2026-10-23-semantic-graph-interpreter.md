---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags:
  - worklog
  - robingraph
  - semantic-interpreter
  - graph-intent
  - gemini
  - audit
  - experimental
---

# [RG-212 / 검색·질의해석] 시맨틱 그래프 인터프리터 실험 구현 및 검증: 벡터 예시 검색 ➔ LLM 계획 ➔ 독립 감사 ➔ 결정론적 검증 파이프라인 — 2026-10-23

> **문서 상태: 실험 구현 및 TEST 검증 진행 중 (본 작업은 프로덕션 완료가 아니며, TEST 환경 대상 실험 구현 및 독립 작성 28건 피드백 노출 회귀 검증 상태임; 직전 RG-211의 표면 정규식 어순 패치와 구별되는 핵심 시맨틱 해석 파이프라인 신설; 임의 자연어 일반화 완료 아님; Python 182/182 단위 테스트 통과, 실제 Gemini 독립 감사 변이 3/3 거부 검증, TEST 활성 배포 및 live API 28건 실사 완료; 솔직한 실측 기록 원칙 준수: supported 9/18 pass, 6 false holds, 3 unverifiable, hold 6/6 safe pass, preserve 3/4 pass; 브라우저 4/4 answer; 원본 496 데이터셋 불변, 조류 DB 쓰기 0건, 운영 미배포, Git commit/push 없음)**  
> 사용자 피드백("아니 질문들도 벡터로 연결되어 있다면서")에 따라, 정규식 단건 어휘/어순 보완(RG-211 등)의 구조적 한계를 극복하기 위해 **벡터 유사 예시 검색 ➔ LLM(Gemini) 구조화 계획 ➔ 동일 모델 기반 독립 fresh prompt 감사 ➔ 결정론적 슬롯/어휘/단위 검증 ➔ 기존 고정 Cypher 실행**으로 이어지는 다층 방어 시맨틱 인터프리터 파이프라인을 실험 구현하였다.  
> 본 작업은 사용자 질문을 그래프 노드에 영구 저장하거나 자동 학습시키는 구조가 아니며, 독립 감사 역시 확률적 LLM 호출로서 미등록 조건 누락을 항상 100% 증명할 수는 없다.  
> 독립 작성 28건 대상 피드백 노출 회귀 API 실측 결과, 안전 거절(hold 6/6)과 기존 라우터 보존(preserve 3/4)이 확인되었으나, 지원 대상 문항에 대해서는 6건의 false hold와 3건의 실행 계획 미표출(unverifiable)이 발생하여 실제 통과율은 9/18(50%) 수준으로 관측되었다. 이에 따라 본 구현은 모든 임의 자연어를 완벽히 해석하는 완료 상태가 아님을 투명하게 기록하고, `.env.example` 및 코드 기본값을 `lexical`로 유지한 채 TEST 환경에서만 `semantic`으로 검증을 진행하였다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 및 배경** | 정규식 어순 패치의 한계 극복 및 시맨틱 일반화 요구 | 사용자 질문의 자연스러운 어순·표현 다양성을 정규식으로 일일이 보완하던 방식(RG-211 등)을 탈피하고, LLM을 활용한 구조화된 질의 해석 엔진 도입 |
| **아키텍처 설계** | 5단계 Fail-Closed 방어 파이프라인 | 1) **유사 예시 검색**: 기존 45개 + 신규 13개(총 58개) 프로토타입 기반 k=5 유사 질의 검색 (상한 8개)<br>2) **Gemini 계획 제안**: 비신뢰 입력(질문, 예시) 기반 JSON 구조화 계획 생성<br>3) **독립 Semantic Audit**: **동일 Gemini provider/model**을 사용하되 검색 예시가 없는 fresh prompt로 양방향 충실도 독립 감사 (완전 독립 모델 아님)<br>4) **결정론적 가드**: 슬롯, 허용 어휘, 원문 스팬, 수치·단위 일치 검증<br>5) **고정 Cypher 실행**: 동적 Cypher 생성 금지, 기존 검증된 읽기 전용 쿼리만 실행 |
| **시스템 범위 및 환경 제어** | 15개 형질, 5대 계급, `shared_diet` 한정 | - 해석 대상: `taxon_traits`(15개 형질, 5대 계급), `shared_diet`(AVONET 대표 먹이 생태 범주), `habitat_shared_diet`. 기타 질의는 기존 lexical 처리<br>- 환경 플래그: `ROBINGRAPH_GRAPH_INTERPRETER` 신설 (`.env.example` 및 코드 기본값 `lexical`, TEST는 `semantic`) |
| **단위 및 변이 검증** | Python 182건 & 실제 Gemini 감사 변이 3건 거부 | - 단위 테스트: **182 / 182 통과** ([focused-python.log](../verification/assets/2026-10-23-semantic-graph-interpreter/focused-python.log), 1.532s)<br>- 감사 변이 실사: mock 계획 + **실제 Gemini 감사 호출** 3/3 거부 ([audit-mutations.json](../verification/assets/2026-10-23-semantic-graph-interpreter/audit-mutations.json): 미지원 조건 누락, 범위 누락, 조건 날조 거부 확인) |
| **실제 live API 실사** | 독립 작성 28건 피드백 노출 회귀 실서버 평가 ([summary.json](../verification/assets/2026-10-23-semantic-graph-interpreter/summary.json), [api-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/api-score.json)) | - **supported (18건)**: **9 pass / 6 fail / 3 unverifiable** (6건 false hold, 3건 관계 질의 성공이나 계획 echo 부재로 unverifiable 판정)<br>- **hold (6건)**: **6 / 6 pass** (미지원 조건, OR 연산, 계절 질의 clarify 처리)<br>- **preserve (4건)**: **3 / 4 pass** (프로필·학명·일반안내 3건 기존 라우터 정상 보존; 비교 질의 1건은 본문 clarify이나 `selected_intent` 메타 차이로 fail 판정) |
| **브라우저 QA (Playwright)** | 뷰포트 반응형 실사 4건 전원 통과 | Chromium 390px, 1280px 각 2건(수치 조건, 관계 조건) 전원 answer 정상 렌더링 ([browser.json](../verification/assets/2026-10-23-semantic-graph-interpreter/browser.json), 오류 0, 오버플로 없음, `physical_mobile: false`) |
| **배포 및 거버넌스** | TEST 컨테이너 배포 및 운영 무영향 | TEST 이미지 `robingraph-api:test-taxonomic-traits-6612c870e85a` 배포 및 active 확인 ([test-release.json](../verification/assets/2026-10-23-semantic-graph-interpreter/test-release.json)). 운영(Production NAS) 무영향, 조류 DB 쓰기 0건 (`bird_db_writes: 0`), Git commit/push 없음 |

---

## 1. 작업 배경 및 문제 분석

### 1) 사용자 요구사항 및 기존 정규식의 한계
- 직전 RG-211(먹이 생태 공유 어순 지원) 등에서 사용자가 자연스럽게 입력한 질의(`"까치랑 같은 먹이 생태를 가진 새를 알려줘"`)가 단순 어순 차이로 인해 clarify로 거절되는 현상이 반복됨.
- 사용자는 *"질문들도 벡터로 연결되어 있다고 들었는데 왜 어순 변경만으로 거절되는가"*라는 의문을 제기하였음.
- 정규식 기반 어휘 추출(`extract_graph_intent`)은 표현이 조금만 바뀌어도 매칭되지 못하고, 매번 어순과 동의어를 사후 패치해야 하는 유지보수 한계에 봉착함.

### 2) 시스템 아키텍처 현실과 시맨틱 파이프라인의 필요성
- 실제 코드 분석 결과, 질문이 벡터 검색에 자동으로 연결되어 질의를 풀어내는 것이 아니라, 어휘 분석이 실패하면 `execution_gate == "not_graph"`에 의해 **임베딩 호출 0건으로 조기 종료**되는 구조였음.
- 이에 따라 **자연어 질문의 의미 구조를 해석하여 정형화된 `GraphIntent`로 변환하되, 임의의 SQL/Cypher 생성을 허용하지 않고 사전 정의된 읽기 전용 쿼리로 실행을 제한하는 시맨틱 인터프리터**가 요구됨.

---

## 2. 아키텍처 및 안전 검증 파이프라인 설계

시맨틱 그래프 인터프리터는 5단계의 엄격한 Fail-Closed 파이프라인으로 설계되었다:

```
[사용자 자연어 질문]
        │
        ▼
1. [k=5 유사 예시 검색] ── (기존 45개 + 신규 13개 = 58개 프로토타입 기반 벡터 검색, 상한 8개)
        │
        ▼
2. [Gemini 계획 제안]   ── (질문과 예시는 비신뢰 데이터 취급, 구조화 JSON 제안)
        │
        ▼
3. [독립 Semantic Audit]── (동일 Gemini 모델 사용, 검색 예시가 없는 Fresh Prompt로 양방향 충실도 감사)
        │
        ▼
4. [결정론적 가드 검증] ── (원문 스팬, 슬롯 허용 어휘, 수치·비교 연산자, 단위 일치 검사)
        │
        ▼
5. [고정 Cypher 실행]   ── (검증 완료된 경우에만 기존 사전 정의된 읽기 전용 쿼리 실행)
```

### 핵심 설계 및 안전 가드레일 원칙
1. **동일 Provider/Model 기반 독립 Fresh Prompt 감사**:
   - 감사는 후보 계획을 생성한 LLM과 **동일한 Gemini provider/model**을 사용함 (완전 독립 모델이 아님).
   - 단, 후보 생성 시 주어졌던 few-shot 검색 예시를 일체 배제한 **fresh context**로 질문과 제안된 계획만 대조하여, 예시 편향이나 잘못된 엔티티 복제를 독립적으로 걸러내도록 설계함.
2. **안전 감사의 확률적 한계 인정**:
   - LLM 기반 안전 감사는 본질적으로 확률적이므로, 질문에 포함된 미등록 제약 조건이나 미묘한 뉘앙스 누락을 항상 100% 완벽하게 증명할 수는 없음.
3. **질문의 비영구화 (No Auto-Training / No Permanent Storage)**:
   - 인입된 사용자 질문을 벡터 DB의 영구 노드로 저장하거나 자동 학습 데이터로 축적하지 않음.
4. **지원 스코프 제한 및 Fallback**:
   - 지원 범위: 15개 형질, 5대 분류 계급, `shared_diet`(AVONET 대표 먹이 생태 범주), `habitat_shared_diet`.
   - 기타 질의 유형(공통 계통, 한국 서식 속 등)은 기존 lexical 파서가 담당함.
5. **환경 설정 분리**:
   - `.env.example` 및 코드 기본값을 `ROBINGRAPH_GRAPH_INTERPRETER=lexical`로 유지하며, TEST 환경에서만 `semantic`으로 활성화하여 점진적 검증을 수행함.

---

## 3. 주요 구현 내용

### 1) 주요 파일 수정 내역
* **신규 모듈**: [semantic_graph_intent.py](../../src/robingraph/retrieval/semantic_graph_intent.py) — 시맨틱 인터프리터 계약(`rg-semantic-v1`), 13개 신규 프로토타입(`SEMANTIC_PROTOTYPES`), 어휘·스팬·수치 결정론적 검증기, `graph_intent_handler` 구현
* **수정 모듈**:
  * [generation.py](../../src/robingraph/generation.py): `GeminiAnswerer.propose_structured_graph_intent` 구현 (후보 제안 생성 및 independent fresh semantic audit 호출)
  * [cli.py](../../src/robingraph/cli.py): `ROBINGRAPH_GRAPH_INTERPRETER` 환경 플래그 처리, 58개 예시 기반 `interpretation_router` 및 `graph_plan_handler` 연동
  * [services.py](../../src/robingraph/api/services.py): 서비스 레이어 시맨틱 인터프리터 연동
  * [application.py](../../src/robingraph/api/drf/application.py): DRF 애플리케이션 핸들러 연동
  * [graph_semantic_router.py](../../src/robingraph/retrieval/graph_semantic_router.py): 프로토타입 라우팅 확장
  * [graph_questions.py](../../src/robingraph/retrieval/graph_questions.py): 먹이/서식지 질문 관계 핸들러 정합
  * [graph_intent_schema.py](../../src/robingraph/retrieval/graph_intent_schema.py): 실행 게이트 연계
  * [.env.example](../../.env.example): `ROBINGRAPH_GRAPH_INTERPRETER=lexical` 기본값 선언

*(참고: `schemas.py`는 이전 작업의 dirty 변경사항으로 이번 태스크의 수정 범위에 포함되지 않음).*

---

## 4. 검증 및 테스트 실측 결과

### 1) Python 단위 테스트 검증
- **명령어**:
  ```bash
  PYTHONPATH=tests uv run --locked --extra test python -m unittest tests.test_semantic_graph_intent tests.test_graph_questions tests.test_graph_intent_schema tests.test_graph_semantic_api tests.test_gemini_generation tests.test_graph_semantic_router tests.test_taxon_traits tests.test_taxon_traits_api tests.test_graph_condition_extractor tests.test_search_cli
  ```
- **결과**: `Ran 182 tests in 1.532s — OK` ([focused-python.log](../verification/assets/2026-10-23-semantic-graph-interpreter/focused-python.log))
- **내용**: 10개 핵심 모듈 182개 테스트 전원 통과, 모의 환경 기반 회귀 무결성 확인.

### 2) 독립 감사 변이(Mutation) 검증 실사 ([audit-mutations.json](../verification/assets/2026-10-23-semantic-graph-interpreter/audit-mutations.json))
후보 제안은 모킹하고 **감사는 실제 Gemini API를 직접 호출**하여 비정상 계획 차단 여부를 검증함:
- `unknown-condition-omitted` (미지원 조건 고의 누락): **실제 감사 거절 (`audit_rejected`)**
- `scope-omitted` (분류 범위 고의 누락): **실제 감사 거절 (`audit_rejected`)**
- `condition-invented` (질문에 없는 조건 고의 날조): **실제 감사 거절 (`audit_rejected`)**
➔ 3개 변이 표본 전원 거부 확인 (`candidate_mocking: true`, `audit_mocking: false`, `bird_db_writes: 0`).

### 3) 단계별 계획 생성 및 회귀 평가 추이
독립 작성된 28건 테스트 케이스를 기반으로 단계별 평가를 수행하였음. 최초 평가 이후 해당 문항을 개선에 참고했으므로 최종 API 결과는 피드백 노출 회귀 검증이며 미노출 일반화 성능이 아님. 계획 평가와 실제 API 평가는 판정 기준과 단계가 달라 단일 성능 수치로 합산하지 않음:

| 단계 | 평가 유형 | Supported (18건) | Hold (6건) | Preserve (4건) | 비고 |
| --- | --- | --- | --- | --- | --- |
| **1차 실측** | 최초 독립 계획 생성 ([final-first-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/final-first-score.json)) | 7 / 18 (38.9%) | 5 / 6 (1건 감사 예외) | API 검증 필요 (4건) | 계획 아티팩트 수준 평가 |
| **2차 실측** | 중간 피드백 노출 회귀 ([final-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/final-score.json)) | 10 / 18 (55.6%) | 5 / 6 | API 검증 필요 (4건) | 프롬프트/규칙 보정 반영 |
| **최종 실측** | live TEST API 실서버 평가 ([api-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/api-score.json)) | **9 pass / 6 fail / 3 unverifiable** | **6 / 6 pass** | **3 / 4 pass** | 로컬 컨테이너 대상 실서버 호출 |

### 4) live TEST API 28건 실사 평가 ([summary.json](../verification/assets/2026-10-23-semantic-graph-interpreter/summary.json), [api-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/api-score.json))
TEST 활성 컨테이너(로컬 포트 `http://127.0.0.1:8000/v1/chat`, 공개 도메인 아님)를 대상으로 독립 작성 28건 질의를 실측 평가함:

#### 카테고리별 실측 결과
1. **Supported 질의 (18건)**:
   - **9건 통과 (Pass)**: 복합 서식지+먹이(`fresh-01`), 습지 오리과(`fresh-02`), 하천 고기 Ardea(`fresh-03`), 참새 씨앗 비율(`fresh-04`), 체중 수치 조건(`fresh-07`), 날개 길이 조건(`fresh-08`, `fresh-10`), 아종 체중 조건(`fresh-12`) 등 정상 해석 및 실행.
   - **6건 실패 (False Holds / Clarify)**: `fresh-05`, `fresh-09`, `fresh-11`, `fresh-13`, `fresh-15`, `fresh-16`. 엄격한 감사 또는 어휘 매핑 경계로 인해 지원 대상 문항임에도 안전 거절(clarify) 처리됨.
   - **3건 검증 불가 (Unverifiable)**: `fresh-14`, `fresh-17`, `fresh-18`. 관계 쿼리 실행 결과는 answer로 정상 반환되었으나, API 응답에 실행 계획 세부 내역이 echo되지 않아 채점 기준상 자동 성공 판정을 유보함.
2. **Hold 질의 (6건)**:
   - **6 / 6 통과 (안전 거절 확인)**: 부정 조건(`fresh-19`), OR 조건(`fresh-20`), 계절 조건(`fresh-21`), 주관적 미지원 형질(`fresh-22`), 대명사 지칭(`fresh-23`), 종 수준 먹이(`fresh-24`) 전원 clarify 처리 확인.
3. **Preserve 질의 (4건)**:
   - **3 / 4 통과**: 단일 프로필(`fresh-25`), 학명 질문(`fresh-26`, taxonomy 정상 answer), 일반 안내(`fresh-28`)가 그래프 질의로 오인되지 않고 기존 라우터로 정상 위임됨.
   - **1건 실패 (`fresh-27`)**: 까치와 직박구리 비교 질문에 대해 베이스라인과 활성 응답 모두 clarify 텍스트를 정상 반환했으나, 메타데이터 차이(`selected_intent: null` vs `profile`)로 인해 채점 실패 처리됨 (비교 응답 자체가 실패한 것이 아님).

### 5) Playwright 반응형 브라우저 검사 ([browser.json](../verification/assets/2026-10-23-semantic-graph-interpreter/browser.json))
- **도구**: Playwright (Headless Chromium)
- **검증 환경**: 공개 TEST URL (`https://robingraph-test.dove-nest.com/chat`)
- **시나리오**: 수치 조건(`"몸무게 700g 이상인 새를 오리과에서 추려 줄래요?"`) 및 관계 조건(`"숲을 서식지로 쓰는 새로 좁혀 줘. 그중 직박구리와 AVONET 먹이 생태 범주가 같은 다른 새가 궁금해."`) = **4 / 4 전원 answer 렌더링 통과**
- **품질**: `page_errors: []`, `overflow: false`, `response_mocking: false`.
- **증거 스크린샷**: [numeric-390.png](../verification/assets/2026-10-23-semantic-graph-interpreter/numeric-390.png), [numeric-1280.png](../verification/assets/2026-10-23-semantic-graph-interpreter/numeric-1280.png), [relation-390.png](../verification/assets/2026-10-23-semantic-graph-interpreter/relation-390.png), [relation-1280.png](../verification/assets/2026-10-23-semantic-graph-interpreter/relation-1280.png).
- **한계 명시**: `physical_mobile: false` (물리 모바일 기기/Safari/Firefox 미실행).

---

## 5. 배포 및 형상 관리 상태

- **실제 통합 작업 경로**: `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex`
- **문서 교정 범위**: 기존 Writer 초안을 바탕으로 작성한 검토본이며 원본 워크트리 수정과 Obsidian 동기화는 수행하지 않음. 이번 교정에서는 Obsidian 템플릿을 조회하지 않았으며 템플릿 준수를 새로 검증했다고 주장하지 않음.

- **앱 통합 브랜치**: `dev-codex` (코드 통합, 검증, TEST 배포)
- **문서 작업 브랜치**: `dev` (`main-2` 워크트리)
- **TEST 배포 상태**:
  - 컨테이너: `robingraph-api-test` (ARM64 Mac .97)
  - 배포 이미지: `robingraph-api:test-taxonomic-traits-6612c870e85a`
  - 소스 SHA-256: `6612c870e85a61cb429ee412ca827e22e4de3dabb433cf41248298d68b42fd8d`
  - 릴리스: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-6612c870e85a-3909c9`
  - 모드: `active`, 인터프리터: `semantic`, 런타임 검증: 208개 파일 정상 ([test-release.json](../verification/assets/2026-10-23-semantic-graph-interpreter/test-release.json))
- **거버넌스 준수**:
  - 운영(Production NAS) 환경 배포 없음 (`production_changed: false`)
  - 조류 DB 쓰기 연산 0건 (`bird_db_writes: 0`)
  - Git commit 및 push 없음

---

## 6. 한계 및 후속 과제

1. **임의 자연어 지원율의 현실적 한계 (Not 100% Generalization)**:
   - 실제 피드백 노출 회귀 평가에서 지원 문항 18건 중 9건(50%)만 통과하였으며, 6건의 false hold가 발생함.
   - LLM 계획과 감사가 매우 보수적으로 동작하여, 약간의 어휘 차이나 표현 어순에서도 안전을 우선하여 clarify로 빠지는 경향이 확인됨. 모든 임의 자연어가 즉시 성공하는 상태가 아니며, 향후 추가적인 미노출 독립 평가를 통한 검증이 필요함.
2. **검증 표본의 한계**:
   - 거절 검증은 hold 표본 6건과 실제 Gemini 감사 변이 3건에 한정된다. 이 결과로 높은 안전성, 모든 미지원 조건의 차단 또는 환각 방지를 일반적으로 입증하지 않는다.
3. **API 실행 계획 Echo 누락 (Unverifiable 3건)**:
   - 관계 질의(`shared_diet`) 실행 시 응답 payload에 실제 실행된 계획이 완전히 포함되지 않아 기계 판독 검증에서 유보 처리됨. API 응답 스키마의 plan echo 보강 필요.
4. **과거 496건 평가 자산 정책 유지**:
   - 본 실험 구현으로 인해 과거 496건 MLflow GenAI 평가 자산은 재실행하거나 수치를 재인용하지 않으며, 기존 불변 기록으로 보존함.

---

## 관련 문서 및 검증 자산

- **검증 자산 디렉터리**: [docs/verification/assets/2026-10-23-semantic-graph-interpreter/](../verification/assets/2026-10-23-semantic-graph-interpreter/)
  - [summary.json](../verification/assets/2026-10-23-semantic-graph-interpreter/summary.json) (최종 검증 종합 상태 요약 영수증)
  - [api-score.json](../verification/assets/2026-10-23-semantic-graph-interpreter/api-score.json) (28건 실API 채점 영수증)
  - [test-release.json](../verification/assets/2026-10-23-semantic-graph-interpreter/test-release.json) (TEST active 배포 영수증)
  - [focused-python.log](../verification/assets/2026-10-23-semantic-graph-interpreter/focused-python.log) (Python 182건 단위 테스트 통과 영수증)
  - [audit-mutations.json](../verification/assets/2026-10-23-semantic-graph-interpreter/audit-mutations.json) (실제 Gemini 독립 감사 변이 차단 영수증)
  - [browser.json](../verification/assets/2026-10-23-semantic-graph-interpreter/browser.json) (Playwright 4개 시나리오 렌더링 결과)
  - [numeric-390.png](../verification/assets/2026-10-23-semantic-graph-interpreter/numeric-390.png), [numeric-1280.png](../verification/assets/2026-10-23-semantic-graph-interpreter/numeric-1280.png)
  - [relation-390.png](../verification/assets/2026-10-23-semantic-graph-interpreter/relation-390.png), [relation-1280.png](../verification/assets/2026-10-23-semantic-graph-interpreter/relation-1280.png)
- **관련 코드**:
  - [semantic_graph_intent.py](../../src/robingraph/retrieval/semantic_graph_intent.py)
  - [generation.py](../../src/robingraph/generation.py)
  - [cli.py](../../src/robingraph/cli.py)
  - [services.py](../../src/robingraph/api/services.py)
  - [application.py](../../src/robingraph/api/drf/application.py)
- **이전 작업 문서**:
  - [2026-10-23-shared-diet-expression.md](./2026-10-23-shared-diet-expression.md) (RG-211)
  - [2026-10-23-diet-display-alias.md](./2026-10-23-diet-display-alias.md) (RG-210)
