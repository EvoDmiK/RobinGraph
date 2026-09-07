# RobinGraph n8n 네이티브 수집 런북

## 현재 상태

최종 산출물은 `n8n/robingraph-operational-ingest.json`이다. 이 워크플로우는 SSH나 외부 RobinGraph CLI를 호출하지 않는다. n8n 기본 노드가 GBIF REST API를 직접 호출하고 데이터를 검증한 뒤 Neo4j HTTP Query API에 적재한다.

워크플로우 이름은 `RobinGraph — native GBIF ingest to Neo4j (inactive until credentials verified)`이다. Credential과 Neo4j 주소를 확인하기 전까지 비활성 상태로 유지한다.

## 워크플로우가 직접 하는 일

```mermaid
flowchart LR
  T[Manual / daily trigger] --> C[Build run configuration]
  C --> G[GBIF HTTP pagination]
  G --> H[SHA-256 each page]
  H --> N[Normalize / validate / dedupe]
  N --> Q{Quality gates}
  Q -->|pass| DB[Neo4j Query API atomic upsert]
  Q -->|fail| F[Discord failure]
  DB --> V{Response counts verified}
  V -->|pass| S[Advance cursor]
  V -->|fail| F
  S --> D[Discord success]
  F --> E[Fail execution]
```

수집 범위는 다음과 같다.

| 항목 | 값 |
|---|---|
| Source | GBIF Occurrence Search API |
| Country | `KR` |
| Taxon | Aves, GBIF key `212` |
| 상태 | 좌표가 있고 `PRESENT`인 occurrence |
| 라이선스 | CC0 1.0, CC BY 4.0 |
| 최초 기간 | 최근 30일 |
| 다음 기간 | 직전 검증 성공일 이후, 시작일 포함 |
| 페이지 | 300건, 최대 20페이지, 요청 간 200ms |
| 최대 실행량 | 6,000 occurrence |

GBIF가 제공하는 관찰, 외부 분류 개념, 공개 장소, source/license provenance와 허용된 미디어 메타데이터를 적재한다. 이미지 파일 자체는 내려받지 않는다. 승인된 AviList crosswalk가 없으므로 GBIF 분류 키는 정식 `Taxon`이 아니라 `ExternalTaxonConcept`로 보존한다.

페이지 한도에 도달했는데 `endOfRecords=true`가 아니면 부분 결과를 적재하지 않고 실패시킨다. 날짜 범위를 줄이거나 페이지 상한을 검토한 뒤 다시 실행한다.

## import 후 필수 설정

### 1. Neo4j HTTP 주소

`Build run configuration` Code 노드에서 다음 값을 n8n 컨테이너가 접근할 수 있는 주소로 바꾼다.

```javascript
neo4j_query_url: 'http://REPLACE_WITH_NEO4J_HOST:7474/db/neo4j/query/v2'
```

Bolt 주소인 `bolt://...:7687`은 HTTP Request 노드에서 사용할 수 없다. n8n과 Neo4j가 같은 Docker network라면 보통 `http://neo4j:7474/db/neo4j/query/v2`이고, 서로 다른 장비라면 n8n 컨테이너에서 접근 가능한 private LAN 또는 Tailscale 주소의 HTTP 7474 포트를 사용한다. 인터넷에 Neo4j 7474 포트를 공개하지 않는다.

### 2. Neo4j Credential

n8n에서 **HTTP Basic Auth** Credential을 만들고 이름을 `RobinGraph Neo4j HTTP`로 지정한다.

| 항목 | 값 |
|---|---|
| User | Neo4j 최소 권한 writer 사용자 |
| Password | 해당 Neo4j 사용자 비밀번호 |

이 Credential을 `Atomic upsert to Neo4j Query API` 노드에 연결한다. username/password를 workflow JSON이나 Code 노드에 넣지 않는다.

### 3. Discord Credential

Discord 서버에서 알림 채널의 **채널 편집 → 연동 → 웹후크 → 새 웹후크 → 웹후크 URL 복사**를 선택한다. n8n에서 Discord Credential의 Connection Type을 Webhook으로 선택하고 이름을 `RobinGraph Operations Discord Webhook`으로 지정한다.

같은 Credential을 `Notify success`, `Notify failure` 노드에 연결한다. Webhook URL은 n8n Credential store에만 저장한다.

## 처리 및 안전 규칙

- GBIF API 요청 단계에서 CC0와 CC BY 4.0만 요청하고, 변환 단계에서도 라이선스를 다시 확인한다.
- 공개 API가 반환한 좌표만 사용한다. 원좌표나 비공개 좌표 필드는 만들지 않는다.
- 좌표 오류, 필수 ID·날짜·분류 누락, 음수 수량은 quarantine 메타데이터로 분리한다.
- GBIF page JSON은 정규화 전에 Crypto 노드로 SHA-256을 계산한다. Neo4j에는 source URI와 page hash만 저장한다.
- occurrence는 GBIF ID로 실행 내 중복 제거하고 Neo4j에서는 `MERGE`한다.
- Cypher 문자열은 고정되어 있고 모든 외부 값은 `$observations`, `$media`, `$quarantine` 파라미터로 전달한다.
- 관찰·미디어·quarantine·active release 갱신은 하나의 Neo4j implicit transaction에서 실행한다.
- HTTP 202만 신뢰하지 않고 반환 count와 active release를 입력값과 대조한다.
- 검증 성공 뒤에만 n8n의 증분 cursor를 갱신한다.
- 품질 gate 또는 Neo4j 검증 실패는 Discord 알림 후 `Stop And Error`로 끝나 실행 이력도 실패가 된다.
- source JSON의 workflow `concurrency`는 1이다. NAS Public API 배포에서는 이 UI 전용 필드가 제외되므로 운영 Publish 전에 UI에서 1로 설정됐는지 확인한다.

## 검증 순서

1. workflow를 import하고 비활성 상태를 유지한다.
2. `Build run configuration`의 Neo4j Query API URL을 수정한다.
3. Neo4j HTTP Basic Auth와 Discord Webhook Credential을 연결한다.
4. Manual Trigger로 실행한다.
5. `Fetch GBIF Korea Aves pages`에서 `statusCode=200`과 `body.results`를 확인한다.
6. `Normalize, validate and deduplicate GBIF`의 `ready_to_load`, count, `failure_reason`을 확인한다.
7. Neo4j 응답 검증 노드에서 `load_ok=true`와 입력·출력 count 일치를 확인한다.
8. Discord 성공 알림과 Neo4j의 `IngestionRun`, `IngestState`, `Observation`을 확인한다.
9. 합성 오류 레코드와 잘린 pagination을 주입해 실패 알림 및 cursor 미갱신을 확인한다.
10. 검증이 끝난 뒤에만 Publish와 Schedule Trigger 활성화를 검토한다.

## 로컬 검증 결과

- 생성 스크립트 Python 문법 검사 통과
- 모든 Code 노드와 Neo4j body expression JavaScript 문법 검사 통과
- 2026-09-07 기준 GBIF 실 API의 2026-08-08~2026-09-07 한국 조류 CC0/CC BY 표본: 19 occurrence, 정규화 19, 허용 미디어 11, quarantine 0
- `docker.n8n.io/n8nio/n8n:stable` import 시험 통과
- 같은 n8n stable 컨테이너에서 Manual Trigger 실행: GBIF HTTP → SHA-256 → 정규화 → quality gate까지 실제 실행해 19/19건 통과. Neo4j placeholder/Credential이 없는 단계는 실패 분기와 `Stop And Error`로 종료됨
- GitHub Actions의 Neo4j Community 2026.07.1에서 통합본의 동일 Cypher를 합성 관찰 1건으로 실행해 observation 1, media 0, quarantine 0과 active release 반환을 검증함
- 저장소 정적 테스트는 source pagination, SHA-256, SSH 부재, parameterized Neo4j transaction, fail-closed 분기와 secret 부재를 검사한다.

## NAS Public API 배포 결과

- 2026-09-07 기존 workflow `Mw9tbGM9vyzu6X1F`를 사용자 상태 디렉터리에 백업하고 15-node 네이티브 workflow로 교체했다. SSH node는 0개이며 배포 뒤 inactive 상태를 유지했다.
- NAS Docker network의 `http://neo4j:7474/db/neo4j/query/v2`에서 기존 `Neo4j` credential로 `RETURN 1`을 실행해 HTTP 202 성공 응답을 확인했다.
- 실제 trigger execution `17238`에서 GBIF source 19건, observation 19건, media 11건, quarantine 0건과 `load_ok=true`를 확인했다. cursor 갱신과 Discord `전서구` 성공 알림까지 모든 노드가 성공했다.
- 테스트 직후 workflow를 inactive로 되돌리고 schedule을 `0 2 * * *`로 복원했다.

프로젝트 루트의 Git 제외 `.env`에 `ROBINGRAPH_N8N_API_URL`, `ROBINGRAPH_N8N_API_KEY`, `ROBINGRAPH_N8N_WORKFLOW_ID`를 둔다. 다음 명령은 Credential과 inactive 상태를 확인하고 배포 계획만 출력한다.

```bash
python3 scripts/deploy_n8n_operational_ingest.py
```

`--apply`를 붙이면 inactive workflow를 백업한 뒤 교체한다. 백업은 `~/.local/state/robingraph/n8n-backups/`에 권한 `0600`으로 저장한다.

```bash
python3 scripts/deploy_n8n_operational_ingest.py --apply
```

NAS 배포는 기존 `Neo4j` credential, `Nesty API 키` Discord Bot credential과 NestControl의 `전서구` 채널을 연결한다. Public API가 UI 전용 `concurrency` 필드를 허용하지 않아 API payload에서는 이 필드를 제외한다.

## 산출물

| 파일 | 용도 |
|---|---|
| `n8n/robingraph-operational-ingest.json` | n8n 네이티브 최종 import 파일 |
| `scripts/generate_n8n_operational_ingest.py` | 최종 JSON 재생성 스크립트 |
| `scripts/deploy_n8n_operational_ingest.py` | n8n Public API 점검·백업·배포 스크립트 |
| `tests/test_n8n_workflows.py` | import shape와 안전 경로 정적 검사 |
| `docs/n8n/final-operational-ingest.md` | 후보 재평가와 통합 설계 판단 |
| `n8n/candidates/claude-operational-ingest.json` | Claude 후보 원본, SSH/CLI 중심이라 배포하지 않음 |
| `n8n/candidates/terra-operational-ingest.json` | Terra 후보 원본, SSH/CLI 중심이라 배포하지 않음 |

GBIF API 계약은 [GBIF Occurrence API](https://techdocs.gbif.org/en/openapi/v1/occurrence)를, Neo4j 요청과 implicit transaction 동작은 [Neo4j Query API](https://neo4j.com/docs/query-api/current/query/)를 따른다.
