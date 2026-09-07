# RobinGraph n8n 운영 수집 런북

## 현재 상태

통합 워크플로우는 `workflow.dove-nest.com`의 Personal 프로젝트에 가져왔다. 워크플로우 이름은 `RobinGraph — reviewed operational ingest (inactive until approvals and CLI exist)`이며, 예약 실행과 게시를 하지 않은 비활성 초안이다.

2026-09-05 NAS n8n에서 Manual Trigger를 실행했다. 실행 엔진과 실패 분기는 정상 작동했으며 455ms에 종료됐다. 첫 SSH 노드인 `Acquire exclusive ingest lock — CLI required`에서 `Node does not have any credentials set` 오류가 발생해 원격 명령과 운영 데이터 변경은 없었다. n8n Credential 목록에서도 SSH Credential이 없음을 확인했다. 이후 운영자 요청에 따라 알림 노드는 SMTP에서 Discord Webhook으로 교체했다.

현재 실패 노드는 `continueRegularOutput`으로 실패 분기를 이어 가므로 실행 이력이 `Success`로 표시될 수 있다. 이는 데이터 수집 성공을 의미하지 않는다. 각 SSH 노드의 `code`, 실패 알림, redacted run manifest를 함께 확인해야 하며, 운영 전에는 실패 실행을 명시적으로 실패 상태로 끝내는 보완이 필요하다.

## 산출물

| 파일 | 용도 |
|---|---|
| `n8n/robingraph-operational-ingest.json` | Claude와 GPT-5.6 Terra 후보의 장점을 합친 최종 import 파일 |
| `n8n/candidates/claude-operational-ingest.json` | Claude 후보 |
| `n8n/candidates/terra-operational-ingest.json` | GPT-5.6 Terra 후보 |
| `docs/n8n/final-operational-ingest.md` | 후보 평가, 통합 설계, CLI 계약 |
| `docs/n8n/claude-candidate.md` | Claude 후보 설명 |
| `docs/n8n/terra-candidate.md` | Terra 후보 설명 |
| `scripts/generate_n8n_operational_ingest.py` | 최종 JSON 재생성 스크립트 |
| `tests/test_n8n_workflows.py` | import shape와 안전 경로 정적 검사 |

후보 점수는 Claude 70/100, GPT-5.6 Terra 72/100이다. 통합본은 Claude의 동시 실행 제어와 시각적인 gate 분기, Terra의 승인 manifest·immutable raw·quarantine·atomic activation 계약을 채택했다. 모든 SSH 단계 뒤에서 실제 `code`를 검사하고, lock 미획득 실행은 lock release를 호출하지 않는다.

## 실행 전 설정

### SSH Credential

n8n에서 SSH Credential을 만들고 모든 SSH 노드에 연결한다.

| 항목 | 값 |
|---|---|
| 이름 | `Mac mini RobinGraph ingest SSH` |
| Host | Mac mini의 private LAN 또는 Tailscale 주소 |
| Port | `22` |
| Username | 최소 권한의 `robingraph-ingest` 전용 사용자 |
| Authentication | Private Key |
| Private Key | Mac mini의 `authorized_keys`에 등록한 공개키와 짝을 이루는 개인키 |

전용 사용자는 sudo와 일반 관리 권한을 갖지 않아야 한다. 개인키와 passphrase는 n8n Credential store에만 저장한다.

### Mac mini 비대화식 SSH 환경

다음 값은 SSH로 원격 명령을 실행할 때도 읽혀야 한다. 아래 경로는 배포 환경에 맞게 바꾸며 `.env`, secret store 또는 권한을 제한한 원격 실행 wrapper에서 제공한다.

```sh
ROBINGRAPH_APP_DIR=/path/to/RobinGraph
ROBINGRAPH_SOURCE_REGISTRY=/path/to/source-registry.json
ROBINGRAPH_APPROVAL_MANIFEST=/path/to/approval-manifest.json
ROBINGRAPH_RAW_ROOT=/persistent/robingraph/raw
ROBINGRAPH_STAGING_ROOT=/persistent/robingraph/staging
ROBINGRAPH_QUARANTINE_ROOT=/persistent/robingraph/quarantine
ROBINGRAPH_INGEST_LOCK_DIR=/persistent/robingraph/locks
ROBINGRAPH_INGEST_LOCK_STALE_SECONDS=7200
```

Neo4j와 Jina 연결값도 Mac mini의 secret store나 `.env`에 둔다. 값의 형식은 저장소의 `.env.example`을 따른다.

```sh
NEO4J_URI=bolt://neo4j-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD='set-in-secret-store'
NEO4J_DATABASE=neo4j

ROBINGRAPH_JINA_ENDPOINT=https://embed.dove-nest.com/v1/embeddings
ROBINGRAPH_JINA_API_FORMAT=birdsnest
ROBINGRAPH_JINA_MODEL=jinaai/jina-embeddings-v3
ROBINGRAPH_JINA_DIMENSIONS=512
ROBINGRAPH_JINA_NORMALIZED=true
ROBINGRAPH_JINA_API_KEY='set-in-secret-store'
ROBINGRAPH_JINA_BATCH_SIZE=32
ROBINGRAPH_JINA_TIMEOUT_SECONDS=120
```

### Discord Webhook Credential

Discord 서버에서 알림을 받을 채널의 **채널 편집 → 연동 → 웹후크 → 새 웹후크 → 웹후크 URL 복사**를 선택한다. n8n에서 Discord Credential을 만들고 Connection Type을 Webhook으로 선택한 뒤 복사한 URL을 입력한다. Credential 이름은 `RobinGraph Operations Discord Webhook`을 사용한다.

모든 `Notify ...` Discord 노드에 같은 Credential을 연결한다. 성공, 수집 차단·실패, lock 미획득, lock 정리 실패가 같은 채널에 전송된다. 메시지는 2,000자 제한을 넘지 않도록 redacted summary를 최대 1,700자로 제한한다.

Webhook URL은 Discord 채널에 메시지를 쓸 수 있는 secret이다. JSON, 문서, Git 또는 n8n 일반 환경변수에 넣지 않고 n8n Credential store에만 저장한다.

## 남은 구현과 승인

현재 `src/robingraph/cli.py`에는 `robingraph ingest` 명령이 없다. Credential을 연결해도 CLI 호출에서 실패하므로 다음 명령군을 구현해야 한다.

```text
ingest lock acquire/release
ingest preflight
ingest fetch
ingest normalize
ingest validate
ingest resolve
ingest dedupe
ingest embed
ingest load
ingest verify
ingest activate
ingest summarize
```

source registry의 실제 source/release, approval manifest, taxonomy와 license 정책도 승인해야 한다. 이 조건이 준비되기 전에는 workflow를 Publish하거나 Schedule Trigger를 활성화하지 않는다.

## 검증 절차

정적 검사는 다음 명령으로 실행한다.

```sh
uv run --with pytest pytest tests/test_n8n_workflows.py -q
```

현재 결과는 `4 passed, 17 subtests passed`다. 세 workflow JSON은 n8n 2.37.10의 `import:workflow`에서도 정상적으로 import됐다.

운영 전에는 아래 순서로 검증한다.

1. SSH Credential로 `hostname`, `id`, `test -d "$ROBINGRAPH_APP_DIR"`, `uv --version`만 실행하는 연결 시험을 한다.
2. 미승인 synthetic source로 차단 시험을 실행하고 fetch와 activate가 호출되지 않았는지 확인한다.
3. 승인된 synthetic source로 전체 단계를 실행해 manifest, quarantine, candidate graph, quality gate, 알림, lock release를 확인한다.
4. gate 실패를 주입해 active release가 바뀌지 않는지 확인한다.
5. 동일 run 입력을 재실행해 중복 생성 없이 같은 결과가 나오는지 확인한다.
6. 검증이 끝난 뒤에만 workflow를 Publish하고 Schedule Trigger를 활성화한다.
