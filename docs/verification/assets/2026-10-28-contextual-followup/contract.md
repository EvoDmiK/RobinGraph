# 조건 유지 후속 질문 1단계: 최소 API 계약 (dev-claude, v2, 2026-10-28)

> **v2 변경 사항** (root 리뷰 msg_2d49503d032e 반영, v1은 `contract.v1.md`)
> - `followup`의 평평한 필드 `conditions/taxon/scope`를 `plan`(이번 응답이 실행했거나 유지한 계획)과 `retained`(반환 토큰이 다음 턴에 가져가는 최근 성공 계획) 두 객체로 나눴습니다.
> - `scope`는 이제 실제 실행 범위입니다(`all|korea|outside|unknown`).
> - 거절 사유 `route_conflict`를 추가했습니다.
> - 토큰이 있는 응답에는 항상 `Cache-Control: no-store`를 붙입니다. trace에는 토큰을 `[redacted]`로 남깁니다.
> - "탭마다 토큰이 다르다"는 보장 문구를 삭제했습니다. 같은 요청이면 같은 토큰이 나올 수 있으므로 격리는 UI의 탭별 메모리로 합니다.

Baseline: `/tmp/robingraph-followup-20261028/baseline.tar.gz` (root dev-codex, RG603 포함).

## 범위
- 직전에 **성공한** `taxon_traits` 조건 조회(`order_fruit` 포함)를 이어받습니다.
  - 지원하는 조건 단위 **하나**를 추가합니다.
  - 기존 조건(분류군 범위·형질 조건·국내 기록 범위)은 모두 유지합니다.
  - 추가 조건의 종류는 다음과 같습니다.
    - 먹이·서식지·형질 조건: `TRAIT_CONDITIONS` 어휘. 예: 열매 먹는, 습지에 사는, 체중 100g 이상
    - 분류군 범위: 예: 참새목, 까마귀과. 기존 조회에 분류군이 없을 때만 추가합니다.
    - 지역: 국내 기록(`species_scope=korea`). 예: 한국에서 볼 수 있는, 국내 기록된
- 범위 밖입니다.
  - 제외·부정("그중 열매 안 먹는"), 비교, 조건 교체·삭제, 여러 조건 동시 추가
  - 종 관계 kind(같은 속·먹이 공유 등)의 후속 질문, 임의 대화 메모리
  - 범위 밖이거나 모호한 추가 조건은 조회하지 않고 clarify합니다.
- 새 저장소나 세션 테이블은 없습니다. 서버는 상태를 저장하지 않습니다.

## 요청 `POST /v1/chat` (추가 필드 1개, 생략 가능)
```json
{"question": "그중 한국에서 볼 수 있는 새는?", "followup_context": "<직전 응답의 followup_context>", "species_scope": "all"}
```
- `followup_context: string | null`, 최대 4096자. 생략하거나 null이면 기존 동작과 같습니다.
- **후속 질문 판정:** 질문이 지시 표현으로 시작할 때만 후속 질문으로 다룹니다. 지시 표현만 있는 질문("그중", "그중?")도 후속 질문입니다. 컨텍스트가 없으면 `context_missing`, 있으면 `unresolved_addition`으로 clarify합니다.
  - 지시 표현: 그중·그 중(에서)(도)·이 중·그 가운데·그 새들 중·여기서·거기서·그 결과에서. "그럼/그러면"이 앞에 붙어도 됩니다.
  - 지시 표현이 없는 질문은 컨텍스트가 와도 **새 질문으로 처리**하고 컨텍스트를 무시합니다.
- 컨텍스트는 신뢰하지 않습니다.
  - 서버 서명(`django.core.signing`, 전용 salt)을 검증합니다. 유효기간은 1시간입니다.
  - 배포 target과 요청 `species_scope`가 일치해야 합니다.
  - 복원한 계획은 다시 검증합니다(`checked_conditions`, 분류군 표면 형식, 조건 수 상한).
  - 클라이언트가 보낸 조건·결과 목록은 받지 않습니다.
- **명시 조회 유형·필터와의 충돌:** 후속 질문에 `intent`가 auto·profile이 아니거나, 비어 있지 않은 `filters`가 함께 오면 컨텍스트를 검증한 뒤 `route_conflict`로 clarify합니다. 필터를 조용히 버리지 않습니다. 빈 `{"kind":"profile"}` 필터는 충돌이 아닙니다. 지시 표현이 없는 질문은 계속 컨텍스트를 무시하고 기존 경로로 처리합니다.
- **실행:** 기존 조건에 추가 조건을 더한 전체 계획으로 기존 고정 쿼리(`graph_question_handler`)를 **다시 실행**합니다. 이전 결과나 첫 페이지를 필터링하지 않습니다.

## 응답 `ChatResponse` (추가 필드 2개, 값이 없으면 JSON에서 생략)
```json
{"selected_intent": "profile", "route_method": "deterministic", "disposition": "answer",
 "answer_text": "...", "warnings": ["...국내 기록은 KOS 공식목록 가-1 또는 AviList 분포 문구 근거입니다..."],
 "result": {"kind": "graph_query", "payload": {"...기존 taxon_traits payload...": "..."}},
 "followup_context": "<불투명 토큰>",
 "followup": {"status": "applied", "reason": null,
              "root_question": "숲에 사는 열매 먹는 새",
              "added": "국내 기록",
              "plan":     {"conditions": ["서식 환경 숲(Forest)", "먹이 구성에 열매 포함"], "taxon": null, "scope": "korea"},
              "retained": {"conditions": ["서식 환경 숲(Forest)", "먹이 구성에 열매 포함"], "taxon": null, "scope": "korea"}}}
```
- `followup_context`는 불투명한 서명 토큰입니다.
  - 최근 성공 조회의 계획을 담습니다. 서명만 하고 암호화하지 않으므로 내용(질문·조건)은 클라이언트가 볼 수 있습니다. 인증 정보는 담지 않습니다.
  - 발급 조건은 아래 표를 따릅니다.
  - **UI 규칙:** 대화 탭마다 마지막 응답의 `followup_context`를 메모리에 저장하고, 응답에 이 필드가 없으면 지웁니다. 다음 요청에는 같은 탭의 값만 보냅니다. 다른 탭과 섞이지 않게 하는 것은 UI의 탭별 메모리 격리이며, 토큰 값은 탭마다 다르다는 보장이 없습니다. 영속 저장소(localStorage 등)에는 저장하지 않습니다.
  - 토큰이 있는 응답에는 피드백 기능 활성 여부와 상관없이 `Cache-Control: no-store`가 붙습니다. MLflow trace의 request·response에는 `followup_context`가 `[redacted]`로만 기록됩니다. 원 질문과 실행 계획(`graph_followup.*`)은 그대로 남습니다.
- `followup`은 요청이 후속 질문으로 판정됐을 때만 들어갑니다.
  - `status`는 `applied` 또는 `rejected`입니다.
  - `plan`은 이번 응답이 실행한 계획(applied)이거나 거절하면서 유지한 계획(rejected)입니다. 검증된 컨텍스트가 없으면 null입니다.
  - `retained`는 반환된 `followup_context`가 담은 계획, 즉 다음 턴에 이어지는 최근 성공 계획입니다. 토큰이 없으면 null입니다.
  - `scope`는 실제 실행 범위입니다. 처음부터 `korea·outside·unknown`으로 질문했다면 그 값이 그대로 표시됩니다.
  - **최소 표시 정보(UI):**
    - applied이면서 결과가 있으면 `plan`을 표시합니다(`plan == retained`).
    - **applied인데 결과가 없거나 자료가 부족하면** 두 계획이 다릅니다. "이번 조회 조건: plan" / "다음 질문은 이 조건으로 이어집니다: retained"처럼 둘을 구분해 표시합니다.
    - rejected이면 `answer_text`(유지한 조건 포함)와 `retained`를 표시합니다.

| 상황 | disposition | result | followup.status / reason | followup_context |
|---|---|---|---|---|
| 새 질문, taxon_traits/order_fruit 조회 성공(`payload.status=answer`) | answer | graph_query | (없음) | 새 토큰. 서명이 실패하면 토큰 없이 정상 답변 |
| 새 질문, 그 밖의 모든 응답(빈 결과·자료 부족·clarify·비그래프) | 기존 | 기존 | (없음) | 없음(UI가 지움) |
| 후속 질문, 적용 후 결과 있음 | answer | graph_query | applied | 새 토큰(누적 계획) |
| 후속 질문, 적용했지만 결과 없음·자료 부족 | abstain | graph_query | applied(`plan` ≠ `retained`) | 입력 토큰 유지(최근 성공 계획) |
| 후속 질문, 컨텍스트 없음 | clarify | clarify | rejected / `context_missing` | 없음 |
| 후속 질문, 서명 오류·만료·형식 오류·target 불일치 | clarify | clarify | rejected / `context_invalid` | 없음 |
| 후속 질문, 토큰과 요청의 `species_scope`가 다름(다른 탭이나 설정 변경) | clarify | clarify | rejected / `context_scope_mismatch` | 없음 |
| 후속 질문에 명시 intent(auto·profile 외)나 비어 있지 않은 filters가 함께 옴 | clarify | clarify | rejected / `route_conflict` | 입력 토큰 유지 |
| 추가 조건이 부정·제외·지원하지 않는 관계·종 관계 kind | clarify | clarify | rejected / `unsupported_addition` | 입력 토큰 유지 |
| 추가 조건을 해석하지 못함(미해석 어휘·모호함) | clarify | clarify | rejected / `unresolved_addition` | 입력 토큰 유지 |
| 조건 단위를 둘 이상 추가 | clarify | clarify | rejected / `multiple_additions` | 입력 토큰 유지 |
| 이미 적용된 조건(국내 범위 중복 포함) | clarify | clarify | rejected / `duplicate_condition` | 입력 토큰 유지 |
| 모순되는 조건·분류군이 이미 있음·국외/미확인 범위에 국내 추가 | clarify | clarify | rejected / `conflicting_condition` | 입력 토큰 유지 |

- clarify `answer_text`는 거절 이유와 유지한 조건을 말합니다. 조건을 빼고 조회하지 않습니다.
- **국내 범위:** 기존 `species_scope=korea` 분포 근거로 실행합니다. 응답 limitations에 기존 `korea_record` 문구를 추가합니다. "볼 수 있는"을 텃새나 현재 서식으로 해석하지 않습니다.
- 기존 필드·RG603 피드백 헤더(`X-RobinGraph-Trace-Id`, `X-RobinGraph-Feedback-Token`, `Cache-Control: no-store`)는 그대로 유지합니다.

## 관측
- 기존 `graph_intent.route` trace span의 attributes를 씁니다.
  - `graph_followup.status`, `.reason`, `.root_question`, `.added`, `.turn`, `.canonical_plan`
- 거절 사유는 기존 `_why(reason, "followup")`로 outcome에 남깁니다.

## 검증 계획
- **mock/unit 테스트:**
  - 분류·먹이·서식지 기반 조회에 지역·먹이·서식지·분류군 추가, 기존 조건 유지(실행된 GraphQuestion 확인)
  - 컨텍스트 없음, 위조·만료·형식 오류·scope 불일치
  - 실패·빈 결과 뒤의 후속 질문, 새 질문 전환
  - 지원하지 않는 추가·부정 추가, 기존 단일 질문 회귀, RG603 헤더 유지
- **실제 API:** root 리뷰 뒤 TEST(읽기 전용)에서 진행합니다. 이번 제출은 unit/mock 증거입니다.
