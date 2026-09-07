# Claude 운영 ingest 후보

상태: **후보 / 비활성**. 이 문서는 `n8n/candidates/claude-operational-ingest.json`의 운영 계약이다. n8n은 NAS에서 실행되고, Mac mini의 제한된 `robingraph-ingest` 계정에 SSH credential로 접속해 Python CLI만 호출한다. 원본·staging·quarantine·manifest는 NAS의 영속 볼륨을 Mac mini에 제한적으로 마운트한 경로에 두며, n8n 컨테이너 파일시스템이나 execution binary storage에는 두지 않는다.

## 현재 동작: 의도적인 fail-closed

이 저장소의 `src/robingraph/cli.py`에는 `robingraph ingest` 명령이 아직 없다. `implementation-readiness.md`의 source/release, taxonomy·license ADR, 실제 원본 필드, HermesAgent 계약은 미승인 또는 미확정이다. 따라서 이 JSON을 지금 import해 실행하면 lock 단계 또는 첫 preflight에서 실패하고, fetch 이후 단계와 활성화는 절대 진행되지 않는다. JSON은 `active: false`로 제공한다.

preflight는 scope별로 다음을 **모두** 만족한 registry 항목과 고정 release manifest가 존재할 때만 0으로 끝난다.

- taxonomy, observations, documents-media 각 scope에 적어도 한 항목이 있다.
- registry 검증이 통과하고 `enabled=true`, `license_policy_status=allowed`이다.
- release가 `approved` 상태이며 고정 release ID, license/terms snapshot, 원본 URI·SHA-256 계획, adapter 버전, source contract mapping을 가진다.

`review_required`, `restricted`, `denied`, 누락 또는 mutable-but-unsnapshotted release는 실패다. 이 판단은 n8n Code/IF 노드가 아니라 Python CLI와 버전 관리된 registry/approval manifest에 둔다.

## 워크플로우

`Manual Trigger`와 매일 02:00인 `Schedule Trigger`는 같은 순서로 실행된다. 첫 SSH 노드는 원자적 잠금을 얻고, 이미 실행 중이면 non-zero로 끝나 실패 알림 경로만 탄다. 잠금은 Mac mini의 영속 lock 디렉터리에서 run ID 소유권을 검증해 해제하며, stale lock은 manifest의 시작 시각과 명시된 TTL을 인식한 뒤에만 회수한다.

**n8n 레벨 동시 실행 방지**: workflow settings의 `concurrency: 1`이 기본 잠금 역할을 한다. CLI lock은 이중 보호이며 n8n 재시작 등 인프라 이벤트에도 대비한다.

성공 경로는 scope별 preflight, `fetch → normalize → validate → resolve → dedupe → embed → load → verify → [IF gate] → activate → summarize`다.

**품질 gate(Claude 후보 고유)**: `verify` SSH 노드는 `--exit-zero` 플래그로 항상 exit 0으로 끝나며 stdout에 JSON을 출력한다. Code 노드가 `gate_passed` 필드를 파싱하고, IF 노드가 true/false를 분기한다. gate가 false이면 `activate`를 호출하지 않고 실패 요약으로 라우팅한다. 이 분기는 n8n 실행 뷰에서 시각적으로 구분되며, gate 결과 없이 CLI exit code만 의존하는 것보다 가시성이 높다.

각 SSH 노드의 `continueErrorOutput` 두 번째 출력은 실패 요약과 HTTP webhook 알림으로 이어진다. 성공·실패 알림 후에도 lock release를 시도한다. n8n은 단계 간 값을 가공하지 않고 run ID와 환경 변수만 전달한다.

`verify` gate가 통과하기 전에는 `activate`가 호출되지 않는다. gate는 `data-contracts.md §13`의 필수 raw hash, blocked quarantine 0건, source/license 완전성 100%, graph referential integrity, name-resolution rate/변동 폭, embedding failure threshold, deterministic re-run equivalence를 검사한다. 검증 실패 후 candidate graph가 남아도 active release pointer는 바꾸지 않는다.

## 노드 목록 (22개)

| 위치 | 노드 이름 | 타입 | 역할 |
|---|---|---|---|
| (-1320, 20) | Schedule Trigger — daily 02:00 | scheduleTrigger | 매일 02:00 KST(cron `0 2 * * *`, timezone Asia/Seoul) |
| (-1320, 180) | Manual Trigger | manualTrigger | 수동 실행 진입점 |
| (-1080, 100) | Acquire exclusive ingest lock | ssh | run ID 소유권 lock 획득. 실패 시 error output으로 실패 경로 |
| (-820, 100) | Preflight taxonomy | ssh | taxonomy scope: enabled, policy=allowed, release approved 검증 |
| (-560, 100) | Preflight observations | ssh | observations scope 동일 검증 |
| (-300, 100) | Preflight documents-media | ssh | documents-media scope 동일 검증 |
| (-40, 100) | Fetch approved sources | ssh | 승인된 source에서 raw fetch, SHA-256·manifest 기록 |
| (220, 100) | Normalize staging Parquet | ssh | source adapter → canonical UTF-8 Parquet |
| (480, 100) | Validate + quarantine rows | ssh | 행 오류 격리, release-wide 오류는 blocked severity |
| (740, 100) | Resolve taxonomy | ssh | accepted/ambiguous/unmatched 분류, fuzzy 자동 병합 없음 |
| (1000, 100) | Dedupe without deletion | ssh | 원본 삭제 없이 duplicate group + representative 기록 |
| (1260, 100) | Embed allowed chunks only | ssh | allowed·chunk_allowed 청크만 Jina 호출 |
| (1520, 100) | Idempotent graph load | ssh | deterministic key로 upsert, active pointer 변경 안 함 |
| (1780, 100) | Verify candidate — exits 0, stdout JSON | ssh | gate 평가 후 JSON 출력, **항상 exit 0** |
| (2040, 100) | Parse quality gate JSON | code | stdout JSON → `gate_passed`, `gate_results`, `summary` 필드 추출 |
| (2300, 100) | IF: quality gate passed? | if | `gate_passed === true` 이면 activate 경로, 아니면 실패 경로 |
| (2560, 100) | Activate only verified release | ssh | 동일 run의 verified manifest 재확인 후 atomic pointer swap |
| (2820, 100) | Execution summary succeeded | ssh | source별 카운트, duration, active release JSON 출력 |
| (3080, 100) | Notify success via webhook | httpRequest | `$env.ROBINGRAPH_ALERT_WEBHOOK_URL`에 JSON POST |
| (420, 420) | Execution summary failed | ssh | blocked reason 포함 실패 요약 JSON 출력 |
| (680, 420) | Notify failure or blocked preflight via webhook | httpRequest | 동일 webhook에 실패 JSON POST |
| (3340, 260) | Release exclusive ingest lock | ssh | 성공·실패 모든 경로가 최종 수렴, run ID 소유권 검증 후 해제 |

## 필요한 CLI 계약 (아직 구현 대상)

아래 명령은 `src/robingraph/cli.py`에 존재하지 않는다. 노드 이름에 `CLI contract required`를 표시했으며, 구현 전까지 이 워크플로우를 활성화하면 첫 번째 SSH 노드에서 실패한다.

모든 명령은 stdout에 비밀값·원문·정밀 좌표를 출력하지 않고, 안정적인 error code를 stderr에 출력하며 0 이외의 종료 코드로 예상치 못한 실패를 표시한다. `--run-id`는 모든 manifest·quarantine·metric의 공통 키다.

| 명령 | 필수 인수 | 성공 조건 / 실패 조건 |
|---|---|---|
| `ingest lock acquire` | `--run-id`, `--lock-dir`, `--stale-after-seconds` | 원자적 단일 소유권. 다른 owner면 exit 1. stale lock은 TTL 초과 후에만 회수하고 audit 이벤트 남김 |
| `ingest lock release` | `--run-id`, `--lock-dir` | owner가 일치할 때만 해제. 불일치면 exit 1 |
| `ingest preflight` | `--registry`, `--scope`, `--require-enabled`, `--require-policy`, `--require-approved-release`, `--run-id` | registry schema 검증, source/release approval manifest 검증. 하나라도 불충족이면 exit 1(`PREFLIGHT_BLOCKED`). `review_required`·`restricted`·`denied`·미승인 release는 실패 |
| `ingest fetch` | `--run-id`, `--registry`, `--raw-root` | 승인된 release만 수집. immutable raw object·SHA-256·retrieval time·retrieval manifest 기록 |
| `ingest normalize` | `--run-id`, `--staging-root` | source adapter → canonical UTF-8 Parquet + provenance 필드 |
| `ingest validate` | `--run-id`, `--quarantine-root` | 행 오류 quarantine; release-wide contract 오류는 `blocked` severity로 기록. blocked > 0이면 exit 1 |
| `ingest resolve` | `--run-id`, `--taxonomy-release` | `accepted/ambiguous/unmatched/rejected`와 rule version 기록. fuzzy match 자동 병합 없음 |
| `ingest dedupe` | `--run-id` | 원본 삭제 없이 duplicate group·representative·rule version 기록 |
| `ingest embed` | `--run-id`, `--embedding-profile` | `license_policy_status=allowed`이고 `embedding_allowed=true`인 청크만 Jina 호출. profile·revision·dimension을 manifest에 고정 |
| `ingest load` | `--run-id`, `--target-release` | deterministic `source_id/source_release/external_id` 키로 idempotent upsert. active release pointer 변경 없음 |
| `ingest verify` | `--run-id`, `--candidate-release`, `--quality-gates`, **`--exit-zero`** | gate 평가 후 **항상 exit 0**, stdout에 `{"gate_passed": bool, "gate_results": {...}, "summary": "..."}` JSON 출력. SSH 연결 실패·예외는 exit 1. `--exit-zero`가 없으면 terra 호환(`gate_passed=false` 시 exit 1)이 되어 이 워크플로우에서는 IF 분기가 동작하지 않음 |
| `ingest activate` | `--run-id`, `--candidate-release` | 동일 run의 verified manifest와 gate를 재확인 후 atomic active pointer swap |
| `ingest summarize` | `--run-id`, `--status` | source별 input/allowed/quarantine/dedupe/embed/load counts, duration, candidate/active release, blocked reason을 redacted JSON으로 stdout 출력 |

## 배포 전 설정

Import 후 다음 credential 이름을 실제 n8n credential로 매핑한다. JSON에는 password, private key, API token, secret URL을 넣지 않는다.

- **`Mac mini RobinGraph ingest SSH`**: `robingraph-ingest` 전용 SSH credential. 이 계정은 CLI executable과 지정된 NAS mount, Neo4j/Jina 환경 참조만 접근할 수 있고 interactive shell·임의 sudo 권한은 없다.

n8n 인스턴스 환경 변수:

| 변수 | 용도 |
|---|---|
| `ROBINGRAPH_ALERT_WEBHOOK_URL` | 성공·실패 알림 수신 webhook (Slack, Mattermost, PagerDuty 등 JSON POST 수신 가능한 엔드포인트) |

Mac mini 서비스 환경 변수 (CLI가 해석):

| 변수 | 용도 |
|---|---|
| `ROBINGRAPH_SOURCE_REGISTRY` | source registry JSON/디렉터리 경로 |
| `ROBINGRAPH_RAW_ROOT` | raw 원본 저장 루트 (NAS 마운트 경로) |
| `ROBINGRAPH_STAGING_ROOT` | staging Parquet 루트 |
| `ROBINGRAPH_QUARANTINE_ROOT` | quarantine 출력 루트 |
| `ROBINGRAPH_INGEST_LOCK_DIR` | lock 파일 디렉터리 |
| `ROBINGRAPH_INGEST_LOCK_STALE_SECONDS` | stale lock 회수 TTL (초) |
| `ROBINGRAPH_TAXONOMY_RELEASE` | 승인된 taxonomy release ID |
| `ROBINGRAPH_CANDIDATE_RELEASE` | 이번 실행의 candidate release ID |
| `ROBINGRAPH_EMBEDDING_PROFILE` | embedding profile 식별자 (모델·차원·task 포함) |
| `ROBINGRAPH_QUALITY_GATES` | quality gate 설정 경로 또는 JSON 문자열 |

Jina·Neo4j·source API credential은 n8n에 복제하지 않고 Mac mini의 서비스 secret store 또는 환경 참조를 CLI가 해석한다.

## HTTP Request 노드 버전 호환

`Notify` 노드는 `n8n-nodes-base.httpRequest` v4.2의 `contentType: "raw"` + `rawContentType: "application/json"` + `body` 표현식을 사용한다. n8n 버전에 따라 이 파라미터 이름이 다를 수 있다. 동작 확인 전 staging n8n에서 import 후 빈 webhook URL로 테스트한다. 파라미터가 맞지 않으면 해당 노드의 `body` 파라미터 이름을 `rawBody` 또는 `jsonBody`로 수정하거나, `n8n-nodes-base.emailSend` 노드로 대체한다.

## 장단점과 운영 전제

### 장점

- n8n이 일정·수동 실행·관측 가능한 실행 이력·알림을 제공하면서 Python의 테스트 가능한 데이터 계약을 침범하지 않는다.
- quality gate 통과 여부가 n8n 실행 뷰에서 IF 분기로 시각화된다. gate 결과를 stdout JSON으로 n8n에서 확인할 수 있어 CLI exit code만으로 판단하는 방식보다 디버깅이 쉽다.
- HTTP webhook 알림은 notification target을 n8n credentials 없이 교체할 수 있다(환경 변수만 변경).
- `concurrency: 1` 설정과 CLI lock 이중 보호로 동시 실행 위험을 낮춘다.
- Mac mini에서 Neo4j/Jina와 가깝게 실행하고 NAS에는 영속 원본/manifest만 두므로 현재 deployment profile(`deployment-profile.md`)과 맞는다.

### 단점

- SSH와 NAS mount 가용성이 pipeline의 단일 운영 의존성이다.
- `verify`가 `--exit-zero`로만 동작하도록 CLI 계약이 변경된다. terra 후보(`exit 1` on gate fail)와 CLI contract가 다르므로 두 워크플로우를 동시에 사용하려면 CLI가 flag를 분기 처리해야 한다.
- n8n의 `continueErrorOutput`은 CLI가 올바른 non-zero exit와 redacted error를 내는 것에 의존한다.
- Code 노드(Parse quality gate)의 JavaScript를 n8n 버전 변경 시 독립적으로 관리해야 한다.
- 동시에 n8n은 source-level 재시도·변환·비밀 관리를 맡지 않으므로 CLI idempotency, lock, manifest, gate 구현과 Prometheus metrics가 선행되어야 한다.

### 운영 시작 조건

- `implementation-readiness.md`의 미완료 항목이 모두 체크된다.
- approval manifest와 실제 source sample을 code review한다.
- staging n8n에서 preflight가 의도적으로 막히는 경우(미승인 source)와 승인된 synthetic source가 정상적으로 전 단계·quality gate IF·success notification·lock cleanup을 통과하는 경우를 각각 검증한다.
- `ingest verify --exit-zero`의 동작을 단독으로 검증한다.
- 이후에도 source/release 또는 policy 변경은 새 approval manifest와 candidate release를 만들며 기존 active release를 덮어쓰지 않는다.

### Terra 후보와의 비교

| 항목 | Terra | Claude |
|---|---|---|
| 동시 실행 방지 | CLI lock | `concurrency: 1` + CLI lock |
| quality gate 분기 | CLI exit code → continueErrorOutput | verify exit 0 + Code 노드 + IF 노드 |
| gate 가시성 | n8n 실행 이력에서 error output 경로 | IF 노드 true/false 분기로 시각화 |
| 알림 방식 | SMTP (emailSend) | HTTP webhook (httpRequest) |
| 알림 credential 의존성 | `RobinGraph Operations SMTP` credential 필요 | 환경 변수 1개만 필요 |
| verify CLI 계약 | exit 1 on gate fail | exit 0 always + `--exit-zero` flag 필요 |
| 추가 n8n 노드 수 | 없음 | Code 1개, IF 1개 (+2) |
