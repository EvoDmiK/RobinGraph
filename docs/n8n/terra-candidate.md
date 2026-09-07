# Terra 운영 ingest 후보

상태: **후보 / 비활성**. 이 문서는 `n8n/candidates/terra-operational-ingest.json`의 운영 계약이다. n8n은 NAS에서 실행되고, Mac mini의 제한된 `robingraph-ingest` 계정에 SSH credential로 접속해 Python CLI만 호출한다. 원본·staging·quarantine·manifest는 NAS의 영속 볼륨을 Mac mini에 제한적으로 마운트한 경로에 두며, n8n 컨테이너 파일시스템이나 execution binary storage에는 두지 않는다.

## 현재 동작: 의도적인 fail-closed

이 저장소의 `src/robingraph/cli.py`에는 `robingraph ingest` 명령이 아직 없다. 또한 `implementation-readiness.md`의 source/release, taxonomy·license ADR, 실제 원본 필드, HermesAgent 계약은 미승인 또는 미확정이다. 따라서 이 JSON을 지금 import해 실행하면 첫 preflight 이전의 lock 단계 또는 preflight에서 실패하고, fetch 이후 단계와 활성화는 절대 진행되지 않아야 한다. JSON은 `active: false`로 제공한다.

preflight는 scope별로 다음을 **모두** 만족한 registry 항목과 고정 release manifest가 존재할 때만 0으로 끝난다.

- taxonomy, observations, documents-media 각 scope에 적어도 한 항목이 있다.
- registry 검증이 통과하고 `enabled=true`, `license_policy_status=allowed`이다.
- release가 `approved` 상태이며 고정 release ID, license/terms snapshot, 원본 URI·SHA-256 계획, adapter 버전, source contract mapping을 가진다.
- 후보 taxonomy release와 policy/gate 설정이 승인된 조합이다.

`review_required`, `restricted`, `denied`, 누락 또는 mutable-but-unsnapshotted release는 실패다. 이 판단은 n8n Code/IF 노드가 아니라 Python CLI와 버전 관리된 registry/approval manifest에 둔다.

## 워크플로우

`Manual Trigger`와 매일 02:00인 `Schedule Trigger`는 같은 순서로 실행된다. 첫 SSH 노드는 원자적 잠금을 얻고, 이미 실행 중이면 non-zero로 끝나 실패 알림 경로만 탄다. 잠금은 Mac mini의 영속 lock 디렉터리에서 run ID 소유권을 검증해 해제하며, stale lock은 manifest의 시작 시각과 명시된 TTL을 사람 검토 가능한 audit 이벤트로 남긴 뒤에만 회수한다.

성공 경로는 source별 preflight, `fetch → normalize → validate → resolve → dedupe → embed → load → verify/gate → activate → summarize`다. 각 SSH 노드의 `continueErrorOutput` 두 번째 출력은 실패 요약과 SMTP 알림으로 이어진다. 성공·실패 알림 후에도 lock release를 시도한다. n8n은 단계 간 값을 가공하지 않고 run ID와 환경 변수만 전달한다.

`verify`가 통과하기 전에는 `activate`가 호출되지 않는다. gate는 data contract §13의 필수 raw hash, blocked quarantine 0건, source/license 완전성 100%, graph referential integrity, name-resolution rate/변동 폭, embedding failure threshold, deterministic re-run equivalence를 검사한다. 검증 실패 후 candidate graph가 남아도 active release pointer는 바꾸지 않는다.

## 필요한 CLI 계약 (아직 구현 대상)

모든 명령은 stdout에 비밀값·원문·정밀 좌표를 출력하지 않고, 성공 시 한 줄 JSON summary, 실패 시 안정적인 error code를 stderr에 출력하며 0 이외의 종료 코드로 실패한다. `--run-id`는 모든 manifest·quarantine·metric의 공통 키다. 존재하는 fixture 관련 `robingraph` 명령과 혼동하지 않도록, 아래 명령은 구현 전까지 노드 이름에 `CLI contract required`라고 표시했다.

| 명령 | 입력/필수 보장 | 성공 조건 / 실패 조건 |
|---|---|---|
| `ingest lock acquire/release` | run ID, lock dir, stale TTL | 원자적 단일 소유권. 다른 owner면 acquire는 `LOCK_HELD`; release는 owner가 일치할 때만 수행한다. |
| `ingest preflight` | registry, scope, enabled/policy/approved-release 요구 | registry schema와 해당 source/release approval manifest를 검증한다. 하나라도 없거나 불일치하면 `PREFLIGHT_BLOCKED`. |
| `ingest fetch` | 승인 registry, raw root | 승인된 release만 받고 immutable raw object·SHA-256·retrieval time을 manifest에 기록한다. |
| `ingest normalize` | run staging root | source adapter가 canonical UTF-8 Parquet과 contract provenance를 만든다. |
| `ingest validate` | run ID, quarantine root | 행 오류는 quarantine; release-wide contract 오류는 blocked severity로 기록한다. |
| `ingest resolve` | 승인 taxonomy release | `accepted/ambiguous/unmatched/rejected`와 rule version을 기록하며 fuzzy match는 자동 병합하지 않는다. |
| `ingest dedupe` | run ID | 원본을 삭제하지 않고 duplicate group과 representative·rule version을 기록한다. |
| `ingest embed` | embedding profile | `allowed`이고 chunk/embedding이 허용된 데이터만 Jina에 보낸다. profile/revision/dimension을 manifest에 고정한다. |
| `ingest load` | candidate release | 결정적 source/release/external ID 키로 idempotent upsert만 하며 active pointer는 변경하지 않는다. |
| `ingest verify` | candidate release, quality gates | 위 gate를 평가하고 검증된 candidate manifest를 만든다. 실패는 `QUALITY_GATE_FAILED`. |
| `ingest activate` | run ID, candidate release | 같은 run의 verified manifest와 모든 gate를 재확인한 뒤 atomic active pointer swap만 한다. |
| `ingest summarize` | run ID, status | source별 input/allowed/quarantine/dedupe/embed/load counts, duration, candidate/active release, blocked reason을 redacted JSON으로 출력한다. |

## 배포 전 설정

Import 후 다음 credential 이름을 실제 n8n credential으로 매핑한다. JSON에는 password, private key, SMTP secret, API token, URL을 넣지 않는다.

- `Mac mini RobinGraph ingest SSH`: `robingraph-ingest` 전용 SSH credential. 이 계정은 CLI executable과 지정된 NAS mount, Neo4j/Jina 환경 참조만 접근할 수 있고 interactive shell·임의 sudo 권한은 없다.
- `RobinGraph Operations SMTP`: 성공/실패 알림 전용 SMTP credential.

Mac mini 서비스 환경에는 `ROBINGRAPH_SOURCE_REGISTRY`, `ROBINGRAPH_RAW_ROOT`, `ROBINGRAPH_STAGING_ROOT`, `ROBINGRAPH_QUARANTINE_ROOT`, `ROBINGRAPH_INGEST_LOCK_DIR`, `ROBINGRAPH_INGEST_LOCK_STALE_SECONDS`, `ROBINGRAPH_TAXONOMY_RELEASE`, `ROBINGRAPH_CANDIDATE_RELEASE`, `ROBINGRAPH_EMBEDDING_PROFILE`, `ROBINGRAPH_QUALITY_GATES`를 설정한다. n8n에는 알림 수신자용 `ROBINGRAPH_ALERT_FROM`, `ROBINGRAPH_ALERT_TO`만 환경 참조로 둔다. Jina/Neo4j/source API credential은 n8n에 복제하지 않고 Mac mini의 서비스 secret store 또는 환경 참조를 CLI가 해석한다.

Import 전에는 n8n 버전에서 SSH, Schedule Trigger, Email Send 노드가 사용 가능한지 확인하고, SSH node가 `resource: command`를 지원하는지 staging instance에서 검증한다. n8n 공식 문서는 Execute Command 등 host-code 실행 노드를 security audit의 risky node로 분류하므로, 이 후보는 SSH 전용 계정, private network, workflow edit 권한 최소화, execution data redaction으로 제한한다. [n8n security audit](https://docs.n8n.io/hosting/securing/security-audit/)

## 장단점과 운영 전제

장점은 n8n이 일정·수동 실행·관측 가능한 실행 이력·알림을 제공하면서 Python의 테스트 가능한 데이터 계약을 침범하지 않는다는 점이다. Mac mini에서 Neo4j/Jina와 가깝게 실행하고 NAS에는 영속 원본/manifest만 두므로 현재 deployment profile과도 맞는다.

단점은 SSH와 NAS mount의 가용성이 pipeline의 단일 운영 의존성이며, n8n의 `continueErrorOutput`은 CLI가 올바른 non-zero exit와 redacted error를 내는 것에 의존한다는 점이다. 동시에 n8n은 source-level 재시도·변환·비밀 관리를 맡지 않으므로 CLI idempotency, lock, manifest, gate 구현과 Prometheus metrics가 선행되어야 한다.

운영 시작 전에는 approval manifest와 실제 source sample을 code review하고, staging n8n에서 preflight가 의도적으로 막히는 경우와 승인된 synthetic source가 정상적으로 전 단계·success/failure notification·lock cleanup을 통과하는 경우를 각각 검증한다. 이후에도 source/release 또는 policy 변경은 새 approval manifest와 candidate release를 만들며 기존 active release를 덮어쓰지 않는다.
