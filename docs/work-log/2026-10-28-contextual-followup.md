---
created: 2026-10-28
date: 2026-10-28
project: RobinGraph
type: worklog
status: completed
task_id: RG-213
tags:
  - worklog
  - robingraph
  - contextual-followup
  - stateless-token
  - graph-query
  - test-verified
---

# [RG-213 / 검색·질의해석] 조건 유지 후속 질문 1단계: 단일 조건 추가·컨텍스트 서명 토큰·격리 검증 (1단계 구현 및 TEST 배포 검증 완료 · 운영 미반영) — 2026-10-28

> **문서 상태: 1단계 구현 및 TEST 배포 검증 완료 (운영 미반영)**  
> 직전 성공한 `taxon_traits` (`order_fruit` 포함) 조회의 조건 컨텍스트(분류군 범위, 형질 조건, 국내 기록 범위)를 유지한 채, 지시 표현(예: `"그중 한국에서 볼 수 있는 새는?"`)을 통해 **단일 조건 단위 하나**를 추가하는 후속 질문 1단계 파이프라인의 구현, TEST 환경 배포 및 실환경 엔드투엔드 검증을 완료하였다. (단, 전체 후속 대화 완결이 아니며 부정·비교·다중 조건 수정 등은 범위 밖으로 안전하게 clarify 처리됨).  
> 이번 1단계 설계에서는 서버 세션 테이블이나 조류 DB 쓰기 대신 `django.core.signing` 기반의 암호학적 서명 불투명 토큰(`followup_context`, salt: `robingraph.chat.followup`, 유효기간 1시간)을 클라이언트와 왕복(round-trip)하고, 클라이언트가 이전 조회 결과(`items`)를 재전송하지 않도록 설계하였다.  
> UI는 탭별 인스턴스 메모리 격리(`activeFollowupState`)를 통해 토큰을 관리하며 영구 저장소(`localStorage` 등)에는 저장하지 않는다. 관측성 및 보안 측면에서 MLflow 트레이스 상의 토큰은 `[redacted]`로 마스킹되고, 토큰이 포함된 모든 응답에는 `Cache-Control: no-store`가 강제된다.  
> 초기 v1 계약 대비 v2에서 `plan`(이번 실행/유지 계획)과 `retained`(다음 턴 최근 성공 계획) 객체 분리, 명시적 필터 충돌 거절(`route_conflict`), 탭별 격리 책임 명확화를 완비하였으며, 기존 마이그레이션 골든 오라클(`drf_parity_golden.json`)을 바이트 단위로 보존하였다.  
> 검증 결과: 백엔드 단위 스위트 총 1,359건 실행 중 1,319건 통과(40건 제외, 0건 실패/오류), 루트 Ponytail 미니멀 집중 회귀 56건(1.462초) 및 UI 단위 331건 전수 통과를 확인하였다. TEST 환경에 배포된 최종 이미지(`robingraph-api:test-followup-69b19f6f5fed`, 235개 소스 파일 해시 완전 일치)를 대상으로 실제 API 29회 HTTP 요청에 대한 30개 항목 검증 결과 **29 pass, 0 fail, 1 no_data(자료 부재 정상 보류 및 토큰 유지)**를 기록하였고, MLflow 33 트레이스 29건 전수 readback(토큰 유출 0건) 및 실제 브라우저(Headless Chromium 390px, 1280px) 4단계 체인과 4대 경계 시나리오 검증(가로 넘침 0, 피드백 3버튼 렌더링 공존)을 완수하였다. 조류 DB 쓰기 0건(`bird_db_writes: 0`), 운영 배포 없음(`production_changed: false`), Git 커밋/푸시 없음(`git_commit_push: false`, 워킹 트리에 실제 변경 유지)을 준수하였다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **원인 규명 / 요구사항** | 단일 턴 질의 성공 후 연속 조건 추가 요구 | 단일 턴 질의(예: "숲에 사는 열매 먹는 새") 성공 후, 연속해서 "그중 한국에서 볼 수 있는 새는?"과 같이 이전 조회 조건을 유지하며 단일 조건(지역, 형질, 분류군)을 누적 탐색하려는 기능 요구사항 대응 |
| **1단계 설계 원칙 및 방식** | 서명 토큰 왕복 및 고정 Cypher 재실행 설계 | - **1단계 설계 원칙**: 서버 세션 테이블 없이 `django.core.signing` 기반 불투명 서명 토큰(`followup_context`, salt: `robingraph.chat.followup`, 1시간 만료) 클라이언트 왕복, 이전 결과 목록(`items`) 재전송 및 브라우저 메모리 필터링 배제, 고정 Cypher 재실행(`re-execution`), 조류 DB 쓰기 0건<br>- **상세 구현 방식**: UI 탭 인스턴스 메모리 격리(브라우저 영구 저장소 배제), v2 `plan`과 `retained` 분리, `route_conflict` 거절, 트레이스 토큰 마스킹(`[redacted]`), `Cache-Control: no-store` 강제 |
| **코드 / 설정 수정** | 백엔드 10개 파일, 프런트엔드 4개 파일 | - 백엔드: `src/robingraph/api/followup.py` 신설(`followup_text`, `issue`, `read`, `extend`, `info`, `FollowupPlan`), `schemas.py`(DTO 정의), `services.py`(충돌 검사 및 트레이스 마스킹), `views.py`(no-store 헤더), `test_graph_followup.py` (19개 테스트 신설)<br>- 프런트엔드: `src/robingraph/api/static/chat.js` (v2 plan/retained 정규화, 탭 메모리 격리), `index.html` (접근성 상태 바), `styles.css` (반응형 칩), `chat_ui.test.js` (v2 단위/모의 테스트)<br>- 골든 보존: `drf_parity_golden.json` 바이트 단위 복원, `test_drf_parity.py` 프로젝션 분리 |
| **TEST 배포 및 릴리스** | TEST 환경 배포 완료 (운영 배포 없음) | - 소스 스냅샷: `snapshot-69b19f6f5fed` (235 파일, SHA256: `69b19f6f5fed1d9def1bb2e98f088d92bf32b216670edb6d749bf5da80bd89bf`, `root_mismatches[]` 0건)<br>- 배포 이미지: `robingraph-api:test-followup-69b19f6f5fed` (arm64, state: verified, container healthy)<br>- 릴리스: `/Users/kimdove/robingraph-test/releases/followup-69b19f6f5fed-f80a69` (current 교체 완료, 롤백 준비 보존)<br>- 운영(Production NAS) 무영향, Git commit/push 없음 |
| **검증 및 테스트** | 단위·집중 회귀·실 API·MLflow·실 브라우저 검증 완료 (통과/제외/자료부재 구분) | - 백엔드 단위: 총 1,359건 실행 중 **1,319건 통과, 40건 제외(skipped), 0건 실패/오류**<br>- 루트 Ponytail 집중 회귀: **56건 전수 통과** (1.462s, 4개 모듈 집중 검증)<br>- 프런트엔드 단위: **331건 전수 통과** (299.28ms)<br>- **실제 TEST API 29회 HTTP 요청 / 30개 판정**: **29 pass, 0 fail, 1 no_data(자료 부족 정상 보류 및 토큰 유지)**<br>- **MLflow 33 트레이스**: 29건 전수 readback 확인, 서명 토큰 유출 0건 (`[redacted]` 마스킹 검증)<br>- **실제 TEST 브라우저**: Chromium 390px / 1280px 4단계 체인 및 4대 경계 시나리오 전원 통과 (가로 넘침 0, 피드백 3버튼 공존) |
| **형상 관리** | 커밋·푸시 미수행 (워킹 트리에 실제 변경 유지) | 브랜치 작업 상태 보존, `commit` 및 `push` 미수행, DB 쓰기 0건 |

---

## 1. 작업 배경 및 문제 분석

### 1) 기능 요구사항 및 문제 정의
* RobinGraph 사용자가 조류 탐색을 수행할 때, 단일 턴 질의(예: `"숲에 사는 열매 먹는 새"`) 성공에 이어 `"그중 한국에서 볼 수 있는 새는?"`, `"그중 참새목은?"`과 같이 이전 조건들을 유지하며 추가 조건을 좁혀나가는 연속 탐색 요구사항이 존재함.
* 기존 시스템은 모든 질의를 독립적인 단일 턴 질의로 처리하므로, 지시 표현("그중", "이 중")이 포함된 질의가 인입되면 문맥 부재로 인한 어휘 파싱 실패(`clarify`)나 엉뚱한 전체 검색으로 빠지는 한계가 있었음.
* 이에 따라 직전 성공한 `taxon_traits` 질의의 조건 컨텍스트를 안전하게 보존하면서 단일 조건을 추가하는 **조건 유지 후속 질문 1단계(Contextual Follow-up Stage 1)** 기능이 요구됨.

### 2) 이번 1단계 설계 원칙 및 구현 방식
* 이번 1단계 구현에서는 다음과 같은 설계 원칙과 방식을 채택함:
  * **1단계 설계 원칙**:
    1. **무상태(Stateless) 토큰 방식 채택**: 서버 세션 테이블이나 별도 세션 스토어, 조류 DB 쓰기 없이 질의 처리를 완결하는 설계를 채택함.
    2. **결과 재전송 및 클라이언트 필터링 배제**: 이전 페이지의 조류 결과 목록(`items`)을 클라이언트가 재전송하거나 브라우저 메모리에서 임의로 필터링하지 않고, 병합된 조건 계획으로 쿼리를 재실행하도록 설계함.
    3. **읽기 전용 Cypher 재실행(`re-execution`)**: 병합된 전체 조건 계획으로 기존 고정 읽기 전용 쿼리(`graph_question_handler`)를 처음부터 다시 실행함.
  * **상세 구현 방식**:
    1. **암호학적 서명 불투명 토큰 왕복**: `django.core.signing`과 전용 salt(`robingraph.chat.followup`)를 사용하여 최근 성공 계획을 서명된 불투명 토큰(`followup_context`, 1시간 만료)으로 직렬화하고 클라이언트와 왕복(round-trip)함.
    2. **UI 탭 인스턴스 메모리 격리**: 브라우저 영구 저장소(`localStorage` 등)를 배제하고, 순수 탭별 메모리 변수(`activeFollowupState`)로만 토큰 수명주기를 관리함. 동일 질의에 대해 동일 토큰이 생성될 수 있으므로 탭 간 혼선 방지는 클라이언트 탭 인스턴스 메모리 격리가 담당함.
    3. **v2 Plan vs Retained 분리**: 이번 응답의 실행/유지 계획(`plan`)과 차기 턴으로 계승되는 최근 성공 계획(`retained`)을 객체 수준에서 명확히 분리함.
    4. **명시적 충돌 감지(`route_conflict`)**: 명시적 `intent`나 비어 있지 않은 `filters`가 함께 인입될 경우 기존 컨텍스트를 묵살하지 않고 `route_conflict` clarify로 안전하게 거절함.
    5. **보안 및 캐시 가드레일**: MLflow trace 상의 토큰 원문을 `[redacted]`로 마스킹하고, 토큰이 포함된 모든 응답에 `Cache-Control: no-store`를 강제 부여함.

### 3) 초기 v1 설계의 한계와 v2 계약으로의 진화 (Contract Discrepancy)
* 루트 리뷰(msg_2d49503d032e) 과정에서 초기 v1 계약(`contract.v1.md`)의 여러 구조적 허점과 모호성이 식별되어 v2(`contract.md`)로 전면 개정됨:
  1. **Plan vs Retained 분리**: v1에서는 `followup.conditions/taxon/scope`라는 평평한 필드만 존재하여, 후속 질문 적용 후 결과가 없거나(`abstain`) 자료 부족인 경우 "이번에 실행한 조건"과 "다음 질문으로 이어질 유효한 조건"을 구분할 수 없었음. v2에서는 이를 `plan`(현재 응답 실행/유지 계획)과 `retained`(반환 토큰이 담은 최근 성공 계획) 객체로 명확히 분리함.
  2. **명시적 라우트/필터 충돌(`route_conflict`)**: v1에서는 후속 질문 요청 시 명시적 `intent`나 `filters`가 함께 인입될 경우의 처리 기준이 미흡했음. v2에서는 `intent`가 auto/profile이 아니거나 비어 있지 않은 `filters`가 함께 오면 기존 컨텍스트를 조용히 버리지 않고 `route_conflict` clarify로 안전하게 거절하도록 명시함.
  3. **보안 및 캐시 정책 강화**: 서명 토큰이 포함된 응답에 대해 피드백 활성화 여부와 무관하게 `Cache-Control: no-store`를 강제하고, MLflow 트레이스 로그 상의 토큰을 `[redacted]`로 마스킹하도록 규정함.
  4. **탭별 격리 책임 소재 정정**: v1의 "탭마다 토큰이 다르다"는 잘못된 보장을 폐기함. 동일한 질문과 조건에 대해서는 결정론적으로 동일한 서명 토큰이 발급될 수 있으므로, 탭 간 상태 혼선 방지는 UI의 인스턴스 메모리 격리 책무임을 명확히 규정함.

---

## 2. 해결 방안 및 상세 설계

### 1) 지시 표현(Marker) 감지 체계
* 후속 질문은 사용자의 질의가 명시적인 지시 표현으로 시작할 때만 판정됨:
  * 허용 지시 표현: `그중`, `그 중(에서)(도)`, `이 중`, `그 가운데`, `그 새들 중`, `여기서`, `거기서`, `그 결과에서` (접두사 `그럼/그러면` 허용).
  * 지시 표현만 단독으로 존재하는 질의(`"그중"`, `"그중?"`, `"여기서"`)도 후속 질문으로 분류되며, 컨텍스트가 없으면 `context_missing`, 컨텍스트가 있으면 추가 조건이 없으므로 `unresolved_addition`으로 clarify함.
  * 지시 표현이 없는 일반 질의는 요청에 `followup_context`가 포함되어 있더라도 **새 질문으로 간주**하고 컨텍스트를 안전하게 무시함.

### 2) 무상태(Stateless) 서명 토큰 라이프사이클
```
[클라이언트 UI (탭 메모리)]               [RobinGraph API 서버]
        │                                         │
        │ 1. 새 질문 ("숲에 사는 열매 먹는 새")     │
        ├────────────────────────────────────────>│
        │                                         │ 2. taxon_traits 성공 실행
        │                                         │ 3. 최근 성공 계획 django.core.signing 서명
        │ 4. 응답 + followup_context (토큰)        │
        │<────────────────────────────────────────┤
        │ (메모리에 토큰 저장)                      │
        │                                         │
        │ 5. 후속 질문 ("그중 한국에서 볼 수 있는 새는?")│
        │    + followup_context                   │
        ├────────────────────────────────────────>│
        │                                         │ 6. 토큰 서명·만료(1h)·scope 일치 검증
        │                                         │ 7. 추가 조건 파싱 및 계획 병합
        │                                         │ 8. 병합된 전체 계획으로 고정 Cypher 재실행
        │ 9. 응답 + 갱신된 followup_context        │
        │    + followup: {applied, plan, retained}│
        │<────────────────────────────────────────┤
```
* **토큰 무결성 가드**:
  * `django.core.signing`과 전용 salt(`robingraph.chat.followup`)를 사용하며 유효기간은 1시간으로 제한.
  * 토큰 디코딩 후 계획의 구조(`checked_conditions`, 분류군 표면 형식, 조건 수 상한)를 재검증하며, 알 수 없는 조건이나 주입 공격 시도는 `context_invalid`로 즉각 거절.
  * 요청된 `species_scope`와 토큰 내부의 `scope`가 불일치할 경우 `context_scope_mismatch`로 거절.

### 3) Plan vs Retained 상태 전이 매트릭스
* 후속 질의의 실행 결과에 따라 UI에 표출되는 계획과 차기 턴으로 계승되는 계획이 정밀하게 통제됨:

| 상황 | disposition | result.kind | followup.status / reason | 반환 followup_context | plan 표시 | retained 표시 |
|---|---|---|---|---|---|---|
| **새 질문 성공** | answer | graph_query | (미포함) | 신규 발급 토큰 | - | - |
| **새 질문 실패/기타** | abstain / clarify | graph_query / 기타 | (미포함) | null (UI 즉시 삭제) | - | - |
| **후속 질문 적용 성공** | answer | graph_query | applied / null | 신규 누적 계획 토큰 | 병합된 계획 | 병합된 계획 (plan == retained) |
| **후속 질문 적용했으나 결과 없음/부족** | abstain | graph_query | applied / null | **직전 입력 토큰 유지** | 이번 실행 계획 | 직전 성공 계획 (plan ≠ retained) |
| **후속 질문 컨텍스트 부재** | clarify | clarify | rejected / `context_missing` | null | null | null |
| **토큰 만료/위조/변조** | clarify | clarify | rejected / `context_invalid` | null | null | null |
| **스코프 불일치** | clarify | clarify | rejected / `context_scope_mismatch` | null | null | null |
| **명시적 intent/filter 충돌** | clarify | clarify | rejected / `route_conflict` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |
| **미지원 조건(부정/비교/관계)** | clarify | clarify | rejected / `unsupported_addition` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |
| **추가 조건 해석 불가(모호함)** | clarify | clarify | rejected / `unresolved_addition` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |
| **조건 다중 추가 시도** | clarify | clarify | rejected / `multiple_additions` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |
| **중복 조건 추가** | clarify | clarify | rejected / `duplicate_condition` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |
| **모순 조건 추가** | clarify | clarify | rejected / `conflicting_condition` | **직전 입력 토큰 유지** | 유지된 계획 | 유지된 계획 |

### 4) 마이그레이션 골든 오라클 무결성 보존
* `tests/fixtures/drf_parity_golden.json`은 Django-DRF 마이그레이션 당시의 OpenAPI 계약 기준선이므로, 이번 기능 추가로 인해 골든 파일을 오염시키지 않음.
* `tests/test_drf_parity.py`의 프로젝션 로직에서 신규 DTO 모델(`ChatFollowupInfo`, `ChatFollowupPlan`)과 필드들을 기존 `feedback`/`clarify` 패턴과 동일하게 pop하여 비교하고, 신규 스키마 자체의 정합성은 `test_component_schemas_match_the_pydantic_dtos`에서 독립적으로 검증함.

---

## 3. 주요 구현 내용

### 1) 백엔드 파일 수정 내역 (dev-claude & root Ponytail 간소화)

* **`src/robingraph/api/followup.py` (신규 모듈)**:
  * 상수: `_SALT = "robingraph.chat.followup"`, `_MAX_AGE = 3600`
  * 핵심 데이터 클래스 및 예외:
    * `FollowupPlan`: `root_question`, `rank`, `conditions`, `scope`, `turn`, `added`
    * `FollowupRejected`: 거절 사유 및 `plan` 보존, 사유별 프롬프트 매핑
  * 핵심 함수 (root 검토 반영):
    * `followup_text(question)`: `_MARKER` 정규식 매칭을 통한 지시어 감지 및 잔여 질의 분리
    * `plan_of(question, graph_question)`: 직전 실행된 `taxon_traits` 및 `order_fruit` 질의로부터 `FollowupPlan` 생성
    * `describe(plan, species_scope)` / `_shown(plan, species_scope)`: 계획 라벨 문자열 및 UI 표출 딕셔너리 구성
    * `info(status, species_scope, plan, retained, reason)`: v2 `ChatFollowupInfo` 규격 딕셔너리 생성
    * `issue(plan, species_scope)`: `django.core.signing.dumps` (salt: `robingraph.chat.followup`) 기반 서명 토큰 발급
    * `read(token, species_scope)`: `django.core.signing.loads` 검증, 배포 target 및 `species_scope` 대조, `checked_conditions` 재검증
    * `_addition(text)`: 추가 조건 단위 1개(형질, 분류군, 국내 범위) 추출 및 다중/미지원 검증
    * `extend(plan, text, species_scope)`: 기존 계획에 단일 조건을 안전하게 추가하여 새 `FollowupPlan` 반환
* **`src/robingraph/api/schemas.py`**:
  * `ChatRequest`: `followup_context: Optional[str] = None` (최대 4096자)
  * `ChatFollowupPlan`: `conditions: list[str]`, `taxon: Optional[str]`, `scope: SpeciesScope`
  * `ChatFollowupInfo`: `status`, `reason`, `root_question`, `added`, `plan`, `retained`
  * `ChatResponse`: `followup_context: Optional[str]`, `followup: Optional[ChatFollowupInfo]` (None일 경우 직렬화에서 제외)
* **`src/robingraph/api/services.py`**:
  * 후속 질문 분기 로직: `route_conflict` 검사, 토큰 검증, 계획 병합 및 재실행 파이프라인 연동
  * 트레이스 마스킹: `_trace_payload` 내부에서 `followup_context`를 `"[redacted]"`로 치환하여 토큰 원문 로깅 차단
* **`src/robingraph/api/drf/views.py`**:
  * 토큰이 포함된 응답에 대해 피드백 설정 여부와 관계없이 `Cache-Control: no-store` 헤더 강제 부여
* **`src/robingraph/tracing.py`**:
  * 허용 사유(`followup_context_missing`, `followup_context_invalid`) 및 단계(`followup`) 화이트리스트 등록
* **`src/robingraph/api/drf/openapi*.json`**:
  * `ChatFollowupInfo`, `ChatFollowupPlan` 스키마 및 프로퍼티 등록
* **`tests/test_drf_parity.py`**:
  * 신규 모델/필드 프로젝션 제외 처리로 골든 오라클 보존
* **`tests/test_graph_diagnostics.py`**:
  * 트레이스 토큰 `[redacted]` 검증 및 토큰 생성 시각 차이에 따른 플레이크 방지(값 대신 존재 여부 검사)
* **`tests/test_graph_followup.py` (신규 테스트)**:
  * 18개 API 시나리오 및 1개 트레이싱 마스킹 테스트(총 19개) 구현

### 2) 프런트엔드 파일 수정 내역 (dev-agy, Contract v2 최종)

* **`src/robingraph/api/static/index.html`**:
  * `#chat-form` 내부 `#question-input` 상단에 접근성 준수 상태 표시 바 정적 추가:
    ```html
    <div id="followup-context-bar" class="followup-context-bar" role="status" aria-live="polite" hidden></div>
    ```
* **`src/robingraph/api/static/chat.js`**:
  * Contract v2 전용 정규화: `FOLLOWUP_SCOPE_LABELS`, `FOLLOWUP_REASONS`(`route_conflict` 포함) 정의, v1 flat 객체 거부
  * 탭 인스턴스 격리 상태 관리(`activeFollowupState`): 브라우저 영구 저장소 배제, 탭 메모리 격리
  * `buildFollowupSummary`:
    * 후속 성공: `적용 조건` 및 `추가 조건: <added>` 뱃지 표시
    * 후속 abstain: `이번 조회 조건`(`plan`)과 `다음 질문 유지 조건`(`retained`)을 두 그룹으로 명확히 분리 표출
    * 후속 거절: 복구 가능 사유에 대해 `유지된 조건`(`retained`) 표시
  * `buildChatPayload`: `followup_context` 포함 및 클라이언트 `items` 재전송 엄격 배제
  * 레이스 컨디션 방어: `submitGen !== requestGeneration || scopeGen !== conversationGeneration` 가드로 비동기 콜백 오염 차단
* **`src/robingraph/api/static/styles.css`**:
  * `.followup-context-bar` 및 `.graph-query-conditions` 스타일 정의 (`overflow-wrap: anywhere;`, 반응형 및 다크모드 대응)
* **`tests/frontend/chat_ui.test.js`**:
  * 계약 기반 신규 단위/모의 테스트 (Contract v2 시나리오 포함)

---

## 4. 검증 및 테스트 결과

### 1) 백엔드 자동화 단위 및 회귀 테스트 (통과)
* **실행 명령**:
  ```sh
  uv run --locked --extra test --extra tracing python -m unittest discover -s tests -p test_graph_followup.py
  uv run --locked --extra test --extra tracing python -m unittest discover -s tests
  ```
* **실제 검증 결과**:
  * 신규 후속 질문 테스트: **Ran 19, OK**
  * 백엔드 전체 테스트 스위트: **총 1,359건 실행: 1,319건 통과, 40건 제외(skipped), 0건 실패/오류** ([backend-report.md](../verification/assets/2026-10-28-contextual-followup/backend-report.md))
  * 골든 마이그레이션 오라클: `tests/fixtures/drf_parity_golden.json` 변경 0건 보존 확인

### 2) 루트 Ponytail 미니멀 집중 회귀 테스트 (통과)
* **실제 실행 명령**:
  ```sh
  PYTHONPATH=tests uv run --locked --extra test --extra tracing python -m unittest \
    tests.test_graph_followup \
    tests.test_chat_feedback \
    tests.test_drf_parity \
    tests.test_graph_diagnostics
  ```
* **실제 결과**:
  * **Ran 56 tests in 1.462s, OK** ([root-focused-tests.log](../verification/assets/2026-10-28-contextual-followup/root-focused-tests.log))
  * 집중 대상: 신규 후속 질문 API/트레이싱(19건), RG603 피드백 및 헤더(15건), OpenAPI 스키마/골든 프로젝션(18건), 루트 트레이스 마스킹/진단(4건).

### 3) 프런트엔드 자동화 단위 테스트 (통과)
* **실행 명령**:
  ```sh
  node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
  ```
* **실제 결과**:
  * **331 tests, 331 passed, 0 failed** (299.28ms, [root-ui-tests.log](../verification/assets/2026-10-28-contextual-followup/root-ui-tests.log), [ui-report.md](../verification/assets/2026-10-28-contextual-followup/ui-report.md))
  * Contract v2 전용 플로우, abstain 시 plan/retained 분리 표시, route_conflict 토큰 보존, 탭 격리 전수 통과.

### 4) 실제 TEST 환경 배포 및 Live API 실사 (통과)
* **배포 정보** ([test-release.json](../verification/assets/2026-10-28-contextual-followup/test-release.json), [test-release-report.md](../verification/assets/2026-10-28-contextual-followup/test-release-report.md)):
  * 배포 대상: 로컬 TEST 서버 (`https://robingraph-test.dove-nest.com`)
  * 소스 해시: `69b19f6f5fed1d9def1bb2e98f088d92bf32b216670edb6d749bf5da80bd89bf` (235개 소스 파일 완전 일치 확인)
  * 이미지: `robingraph-api:test-followup-69b19f6f5fed` (arm64, ID: `sha256:4c3a532d0f71be6d31bc411db28503a0107bfd0cbe033be72dcb376c6d646a48`)
  * 배포 검증: isolated fixture smoke (`--network none --read-only`) 통과, container `healthy`, `manage.sh verify` 통과.
* **실제 TEST API 29회 HTTP 요청 / 30개 검증 항목 판정 결과** ([evaluation.json](../verification/assets/2026-10-28-contextual-followup/evaluation.json), [responses.json](../verification/assets/2026-10-28-contextual-followup/responses.json)):
  * **결과 요약**: **29 pass / 0 fail / 1 no_data** (30개 평가 키 전수 충족)
  * **1) 체인 질의 (3 pass)**:
    * `chain.base` ("숲에 사는 열매 먹는 새"): 6,898종 중 1,775종 answer, 신규 토큰 발급 (pass)
    * `chain.korea` ("그중 한국에서 볼 수 있는 새는?"): 410종 중 48종 answer, 기존 조건 유지 + `korea` 스코프 적용, KOS/AviList 경고 표출, 누적 토큰 발급 (pass)
    * `chain.number` ("그 새들 중 체중 100g 이상인 새는?"): 410종 중 10종 answer, 숲+열매+체중100g 누적, `korea` 스코프 유지 (pass)
  * **2) 분류군 계급별 질의 (3 pass, 1 no_data)**:
    * `rank.order` (참새목 1,115/3,983 pass), `rank.family` (직박구리과 47/81 pass), `rank.genus` (Turdus 51/60 pass)
    * `rank.species` ("그중 Hypsipetes amaurotis에 속하는 새"): 그래프 내 형질 자료 부재로 인한 **`no_data` (`insufficient_data`) 정상 보류 및 직전 성공 토큰 유지** (답변 성공이 아니며 계약대로 정상 처리됨)
  * **3) 독립 조건 질의 (3 pass)**:
    * `indep.wetland.fish` (172/6,898 pass), `indep.seed.korea_scope_kept` (35/164 pass), `indep.order_fruit.wing` (1,015/3,978 pass)
  * **4) 컨텍스트 오류 처리 (5 pass)**:
    * `ctx.missing`, `ctx.forged`, `ctx.garbage`, `ctx.scope_mismatch`: clarify 거절 및 토큰 미발급 (pass)
    * `ctx.bare` ("그중?"): `unresolved_addition` clarify 거절 및 직전 토큰 보존 (pass)
  * **5) 추가 조건 오류 처리 (6 pass)**:
    * `add.negation`, `add.unresolved`, `add.multiple`, `add.conflict`, `add.duplicate`: 규정된 거절 사유 clarify 및 직전 토큰 보존 (pass)
    * `add.route_conflict`: 프로필 필터 존재 시 clarify 거절 및 직전 토큰 보존 (pass)
  * **6) 빈 결과 복귀 처리 (2 pass)**:
    * `empty.followup` ("체중 5000g 이상"): 0건 empty 보류, 입력 토큰 유지 (pass)
    * `empty.next_uses_retained` ("그중 한국에서 볼 수 있는 새는?"): 109/239 answer, 체중 조건 배제 후 직전 성공 조건(참새목+숲+korea) 유지 조회 성공 (pass)
  * **7) 새 독립 질의 전환 (2 pass)**:
    * `new.standalone_graph`, `new.other_kind`: 컨텍스트 무시 및 독립 처리 (pass)
  * **8) 응답 헤더 가드 (2 pass)**:
    * `headers.no_store_with_token`: 모든 토큰 응답 `Cache-Control: no-store` 적용 확인 (pass)
    * `headers.feedback_kept`: RG603 피드백 토큰 및 Trace-Id 헤더 공존 확인 (pass)
  * *비고: 만료 토큰 거절은 1시간 경과 필요로 인해 라이브에서는 미실행(단위 테스트로 검증).*

### 5) MLflow 33 트레이스 실환경 Readback (통과)
* **실행 명령 및 결과** ([trace-readback.json](../verification/assets/2026-10-28-contextual-followup/trace-readback.json)):
  * 29개 트레이스 전수 readback 확인: 실험 33(`robingraph-test`), 질문 원문 일치 확인.
  * **보안 토큰 마스킹 검증**: 요청/응답 `followup_context`는 **`[redacted]`로 완벽 마스킹**됨 (서명 패턴 `.eJ…`, `eyJ…` 유출 0건).
  * 트레이스 속성: `graph_followup.status`, `.reason`, `.root_question`, `.added`, `.turn`, `.canonical_plan` 정상 기록 확인.
  * 태그 검증: `validation_phase=followup_acceptance`, `automated_test=true` 전수 부여 확인.

### 6) 실제 TEST 브라우저 E2E 검증 (통과)
* **검증 환경** ([browser-report.md](../verification/assets/2026-10-28-contextual-followup/browser-report.md), [browser-verification-results.json](../verification/assets/2026-10-28-contextual-followup/browser-verification-results.json)):
  * URL: `https://robingraph-test.dove-nest.com/chat` (실제 TEST 배포 환경, 모의 인터셉트 0건)
  * 엔진: Chromium (`chrome-headless-shell` 1248, ARM64)
  * 뷰포트: `390x844` (모바일), `1280x800` (데스크톱)
* **실제 검증 시나리오 및 결과**:
  * **4단계 연속 질의 체인 (모바일/데스크톱 동일 통과)**:
    1. 1단계 ("숲에 사는 열매 먹는 새"): 적용 조건 칩 노출, `#followup-context-bar` 노출 (`desktop_1280x800-1-initial.png`, `mobile_390x844-1-initial.png`)
    2. 2단계 ("그중 한국에서 볼 수 있는 새는?"): `추가 조건: 국내 기록` 뱃지 및 상태바 갱신 (`desktop_1280x800-2-korea.png`, `mobile_390x844-2-korea.png`)
    3. 3단계 ("그중 체중 5000g 이상인 새는?"): `보류 (근거 부족)` 배지, 버블 내 `이번 조회 조건`(`plan`)과 `다음 질문 유지 조건`(`retained`) 두 그룹 분리 표시, `#followup-context-bar`에서 미적용 5000g 제외 및 직전 조건 유지 (`desktop_1280x800-3-empty-5000g.png`, `desktop_1280x800-3-empty-5000g-conditions.png`, `mobile_390x844-3-empty-5000g.png`, `mobile_390x844-3-empty-5000g-conditions.png`)
    4. 4단계 ("그중 체중 100g 이상인 새는?"): 누적 조건(10종) 정상 조회 및 상태바 갱신 (`desktop_1280x800-4-numeric-100g.png`, `mobile_390x844-4-numeric-100g.png`)
  * **회귀 및 경계 시나리오 (데스크톱 실사)**:
    * `route_conflict`: 타 조회 유형 선택 시 충돌 안내 표출, 상태바 및 유지 토큰 정상 보존 (`desktop-5-route-conflict.png`)
    * 새 주제 전환: `청둥오리` 검색 시 이전 조건 맥락 즉시 해제 및 상태바 숨김 (`desktop-6-new-topic.png`)
    * 대화 지우기: `#clear-button` 클릭 시 상태바 즉시 숨김 및 메시지 초기화
    * `species_scope` 국외 전환: 라디오 변경 즉시 맥락 초기화, 국외 분포 후속 질의 정상 동작 (`desktop-7-scope-outside.png`)
  * **피드백 버튼 공존 및 반응형**:
    * 모든 응답 버블 하단에 RG603 피드백 3종 버튼 공존 확인 (버튼 렌더링 확인; 실제 피드백 저장은 별도 미실행).
    * `390x844` 및 `1280x800` 전 단계 가로 오버플로 0건 (`horizontalOverflow: false`), 접근성 포커스 `#question-input` 정상 복귀.

---

## 5. 배포 및 형상 관리

* **대상 환경**: 로컬 TEST 환경 배포 완료 (`https://robingraph-test.dove-nest.com`)
* **릴리스 정보**:
  * 릴리스 디렉터리: `/Users/kimdove/robingraph-test/releases/followup-69b19f6f5fed-f80a69` (`current` 심볼릭 링크 전환 완료)
  * 배포 이미지: `robingraph-api:test-followup-69b19f6f5fed` (arm64, ID: `sha256:4c3a532d0f71be6d31bc411db28503a0107bfd0cbe033be72dcb376c6d646a48`)
  * 이전 릴리스(롤백 대비 보존): `/Users/kimdove/robingraph-test/releases/chat-feedback-2e822237c9dc-2377c8` (`robingraph-api:test-chat-feedback-2e822237c9dc`)
  * 이전 임시 스냅샷(`159a52fc4b8c`)은 UI 미포함 준비본으로 최종 배포에서 폐기됨.
* **소스 해시 검증**:
  * 베이스라인 커밋: `318e7731fda8b85560b7e8d464b0f4f2c92439d1`
  * 최종 스냅샷: `snapshot-69b19f6f5fed` (235개 소스 파일 해시 완전 일치, `root_mismatches[]` 0건)
  * `source_sha256`: `69b19f6f5fed1d9def1bb2e98f088d92bf32b216670edb6d749bf5da80bd89bf`
  * `followup_module_sha256`: `80d47cc72cce65173d6a938ff64b56a90d46c3cd86cc04eb24388fe0ce1285ef`
  * `chat_js_sha256`: `ff13a283ab784b2e8cc4c4f3d77611b71b0aabb4c48c09718aaeb14d96aa5afb`
* **거버넌스 준수**:
  * 프로덕션 무영향: `production_changed: false` (NAS 운영 컨테이너 무변경)
  * 조류 DB 쓰기: 0건 (`bird_db_writes: 0`)
  * 형상 관리: Git `commit`, `push`, `merge` 미수행 (`git_commit_push: false`, 워킹 트리에 실제 변경 유지)

---

## 6. 한계 및 후속 과제

1. **단일 조건 추가 한정 (Stage 1 Scope)**:
   * 본 1단계 구현은 `taxon_traits` 질의에 대한 단일 조건(지역, 형질 어휘, 분류군) 추가만을 지원함.
   * 다중 조건 동시 추가(`multiple_additions`), 부정/제외 표현("그중 열매 안 먹는"), 조건 교체 및 삭제는 지원하지 않으며 안전하게 `clarify` 거절됨.
2. **종 관계 질의(Kinship) 후속 연계 미지원 (추가 확인 필요)**:
   * "까치와 먹이 생태가 같은 새" 등 관계 기반 질의(`shared_diet`, `kinship`)에 대한 후속 질문은 1단계 지원 범위 밖임. 선행 관계 질의에 토큰이 발급되지 않은 경우 `context_missing`으로, 토큰이 존재하더라도 관계 질의 조건 추가 시도시 지원 범위 밖으로 처리되므로 추가 확인이 필요함.
3. **Korea 조건 적용 시 본문 문구 통일 과제 (알려진 표시 한계)**:
   * 국내 기록 조건(`korea`) 적용 후 실제 조회 범위는 Korea로 정상 한정되고 plan/scope 칩 및 KOS 공식목록 안내 문구가 정확히 표시되지만, 기존 쿼리 핸들러가 반환하는 `answer_text` 본문 문구가 여전히 `"전체 조류 범위…"`로 출력되는 표시상의 한계가 있음. 현재 기능과 무관한 전면 문구 리팩토링은 이번 작업에서 배제하였으며, 본문 문구 통일은 후속 개선 과제로 분리함.
4. **프로덕션 배포 사용자 명시 승인 게이트**:
   * 본 기능은 TEST 환경 검증 단계까지 완료되었으며, 사용자 명시 승인 전에는 프로덕션(NAS) 배포를 진행하지 않음.
5. **실환경 검증 범위 한계**:
   * 브라우저 실환경 검증은 Linux/Mac 환경의 Chromium 헤드리스(`390x844`, `1280x800`)로 수행되었으며, 물리 모바일 기기 실기기, Safari, Firefox 브라우저 및 라이브 환경에서의 1시간 만료 토큰 거절(시간 대기 필요)은 실환경 미실행(단위 테스트로 검증 대체).

---

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-시맨틱-그래프-인터프리터-실험-구현|RG-212 시맨틱 그래프 인터프리터 실험 구현]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-28-그래프-질의-안내-UI-정리|후속 UI 정리: 그래프 질의 안내·유의사항 단일 영역 통합 및 중복 제거 (2026-10-28)]]
- [후속 UI 정리 작업 기록](2026-10-28-graph-query-notices.md)
