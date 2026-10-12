# 공개 저장소 민감정보 점검과 문서 마스킹 — 문서 전용

## 요청과 목표

사용자가 프로젝트 폴더에 민감정보가 있는지 점검을 요청했다. 점검 결과를 보고한 뒤 수정을 요청했고, 이어서 "일단 문서 위주로 수정"하도록 범위를 좁혔다. 이 저장소(`EvoDmiK/RobinGraph`)는 GitHub에서 **PUBLIC**이다(`gh repo view --json visibility` 확인). 목표는 공개 문서에 남은 내부 인프라·개인 식별 정보를 placeholder로 바꾸는 것이다. 코드·배포 설정·운영 동작은 바꾸지 않는다.

## 점검 범위와 결과

- 추적 파일 999개 전체(jsonl, `docs/verification/assets/2026-10-07-RG010-processing-ledger.jsonl.gz` 포함)와 전체 커밋 317개의 git 히스토리를 검사했다.
- **실제 비밀값은 발견되지 않았다.** `sk-ant-`, `sk-proj-`, `AKIA…`, `ghp_`, `github_pat_`, `AIza…`, `PRIVATE KEY`, `hf_`, `xox[bp]-` 패턴과 `*_API_KEY/PASSWORD/SECRET/TOKEN=값` 할당을 현재 파일과 히스토리 전체에서 찾았다.
- `.env`, `.env.nas*` 실제 파일은 디스크에도 히스토리에도 없다. 히스토리에 추가된 env류 파일은 example 세 개뿐이며, 비밀값 칸은 비어 있다.
- `tests/frontend/chat_ui.test.js`의 `sk-live-…`, `AKIAIOSFODNN7EXAMPLE…`과 `fixture-test-only`, `gemini-secret-key` 등은 마스킹 동작을 검사하는 테스트용 가짜 값이다.
- 공개 저장소 기준으로 정리가 필요한 정보:
  - NAS SSH 접속 정보(계정@LAN IP, SSH 포트)
  - 내부 IP(NAS, 임베딩 서버)와 Tailscale 노드명
  - 내부 서비스 도메인(MLflow, 임베딩)
  - Discord guild/channel ID
  - n8n Neo4j credential ID(이름으로 다시 조회해 덮어쓰므로 ID만으로는 접근 불가)
  - 개인 이메일, 로컬 Mac 호스트명, 계정명이 들어간 경로

## 변경 내용

### 수정 파일

`docs/` 아래 문서·검증 기록 106개와 `.env.example`, `.env.nas.example`, `.env.nas.ingest.example` 세 개를 수정했다. `docs/verification/assets/`의 JSON 기록도 포함한다. 치환 규칙은 다음과 같다.

| 원래 값 종류 | 치환 결과 |
|---|---|
| NAS SSH `계정@IP`, 포트 | `<nas-user>@<nas-host>`, `<ssh-port>` |
| NAS LAN IP / 임베딩 서버 LAN IP | `<nas-host>` / `<embedding-host>` |
| NAS·Mac 계정명(경로 포함 `/home/…`, `/Users/…`, `/Volumes/…/orca/…`) | `<nas-user>` |
| 로컬 Mac 호스트명과 그 계정 | `<local-user>@<local-host>.local`, `<local-user-2>@<local-host>.local` |
| 개인 이메일 | `<maintainer-email>` |
| Tailscale 노드명 3개 | `<tailscale-storage-node>`, `<tailscale-portainer-node>`, `<tailscale-graph-node>` |
| MLflow·임베딩 도메인 | `mlflow.example.com`, `embed.example.com` |
| Discord guild/channel ID | `<discord-guild-id>`, `<discord-channel-id>` |
| n8n Neo4j credential ID(문서 언급) | `__SET_ON_IMPORT__` |
| `.env*.example`의 임베딩 endpoint | `http://embedding.example.internal:8765/v1/embeddings` |

`.env.*.example`은 값 칸만 placeholder·빈칸으로 바꾼 템플릿이라 런타임에 영향이 없다. compose 기본값과 배포 스크립트 기본값은 그대로이므로 운영 동작도 바뀌지 않는다.

### 의도적으로 변경하지 않은 것

- `scripts/`, `tests/`, `compose.nas.yml`, `n8n/*.json`: 처음에는 코드 기본값 제거까지 수정했다. 사용자가 범위를 문서로 좁혀 `git checkout`으로 되돌렸다. 이 파일들에는 아래 값이 아직 남아 있다.
  - Discord ID 기본값: `compose.nas.yml`, `scripts/deploy_n8n_*.py`
  - NAS SSH 기본값: `scripts/audit_trait_coverage.py`
  - n8n credential ID: `scripts/generate_n8n_*.py`, `n8n/*.json`
  - MLflow 도메인: `tests/test_mlflow_configuration.py`
- 공개 서비스 도메인(`robingraph.dove-nest.com`, `robingraph-test.dove-nest.com`, `aviary.dove-nest.com`)은 외부에 공개된 접속 주소라 유지했다.
- n8n credential 이름(`Neo4j`, `Nesty API 키` 등)은 이름일 뿐 비밀값이 아니라 유지했다.
- git 히스토리: 과거 커밋에는 원래 값이 남아 있다. 완전히 지우려면 `git filter-repo`와 force push가 필요하며, 되돌리기 어려운 작업이라 사용자 결정 전에는 하지 않는다.

### 알려진 불일치

`docs/n8n/README.md`는 credential ID를 `__SET_ON_IMPORT__`로 적지만, 되돌린 `n8n/*.json`에는 실제 ID가 남아 있다. 배포 스크립트가 credential을 이름으로 조회해 ID를 덮어쓰므로 동작에는 영향이 없다.

## 검증 방법과 결과

- 잔존 검색: 위 값 전부에 대한 `git grep`을 `docs/`와 `.env*.example`에서 실행했고 0건이었다.
- Python unittest(`uv run --locked --extra test python -m unittest discover -s tests`, Python 3.12.13, Windows):
  - 825개 실행, 49개 건너뜀, 실패 12건, 오류 19건.
  - 변경 전 원본(stash 상태)에서도 **똑같은 31건**이 실패했다. 목록을 `comm`으로 비교한 결과 이번 변경으로 새로 생긴 실패는 없다.
  - 확인한 대표 실패는 `test_trait_crosswalk`의 CRLF/LF 바이트 비교다. Windows 체크아웃 환경 문제로 보이며, 나머지 실패 원인은 조사하지 않았다.
- 프론트엔드 `node --test tests/frontend/chat_ui.test.js`: 300개 중 298개 통과, 2개 실패(#7, #56). 원본에서도 같은 2개가 실패해 기존 문제다.
- 모두 로컬 단위·계약 테스트다. 실제 DB/API/NAS 검증은 하지 않았다(문서 변경이라 해당 없음).
- `docker compose config` CI 단계는 로컬에서 실행하지 않았다.

## 작업 중 사고와 복구

테스트 기준선을 비교하려고 `git stash`를 쓰는 동안 사용자가 `README.md`를 편집했다. 이 편집과 겹쳐 `stash pop`이 한 번 실패했다. stash 항목은 보존되어 있었고, 다음 순서로 복구했다.

1. 현재 README를 백업했다.
2. README를 HEAD로 되돌린 뒤 stash를 복원했다. 문서 마스킹 변경은 모두 돌아왔다.
3. README는 사용자가 **마지막으로 저장한 상태(백업)**로 되돌렸다.

stash 시점의 README에는 57~59행 끝에 줄바꿈용 공백 두 칸을 넣은 편집이 있었다. 사용자의 최신 저장본에서는 이 공백 대신 목록 앞에 빈 줄이 들어가 있어, 최신 저장본을 기준으로 삼았다. README에는 민감정보가 없어 이번 마스킹 대상이 아니다.

## 배포·커밋

커밋, push, TEST/운영 배포는 하지 않았다. 문서 변경이라 배포 대상이 아니다. 커밋은 사용자 검토 후 진행한다.

## 남은 한계와 후속 사항

1. 코드·설정에 남은 값(위 "의도적으로 변경하지 않은 것")을 정리할지 결정해야 한다.
   - Discord ID 기본값을 지우려면 먼저 NAS `.env.nas.ingest`에 `ROBINGRAPH_DISCORD_GUILD_ID`, `ROBINGRAPH_DISCORD_CHANNEL_ID`가 있는지 확인해야 한다.
2. 히스토리 재작성(`git filter-repo` + force push) 여부를 결정해야 한다.
3. Obsidian 작업기록에는 아직 반영하지 않았다.
