# RG-701 main 통합·Production 배포 (Django 단독 런타임) — 2026-10-20

> **문서 상태: Production 배포·실제 검증 완료 (Jenkins `RobinGraph-PROD` #3 SUCCESS).** Root(Codex)가 Git·Jenkins·앱 배포를 실행했고, 문서 담당은 dev-codex `docs/verification/assets/2026-10-20-production-django/` 산출물과 Git ref를 **읽기 전용**으로 확인했다. 문서 담당은 commit/push/merge/배포·앱/설정 수정을 하지 않았다. 아래 수치는 산출물 파일과 Root의 코디네이터 전달(2026-10-20 08:52Z–08:57Z)을 근거로 하며 출처를 표에 구분했다.

## 요약

- 작업 ID: **RG-701** (7xx 배포·인프라), 우선순위 1 (변경 없음).
- 사용자 지시: TEST 결과 확인 후 **git push, main 병합, Production 배포를 명시 승인**(코디네이터 전달). AGENTS.md 운영 배포 승인 규칙의 "명시 승인"에 해당한다.
- 결과:
  - Git: 커밋 `e3a8bda`(네이티브 Django 전환, 269 files) + `770495a`(과거 배포 로그 5개 줄 끝 공백 정리). main을 `770495a13fe7c7431c2d66cbf41a1080272d42f0`으로 **fast-forward**, dev-codex·main push 성공.
  - Jenkins: `RobinGraph-PROD` checkout을 `dev-codex` → `main`으로 바꾼 뒤 build **#3 SUCCESS**(203,615ms). 빌드 안에서 Python 1,029 실행·991 통과·38 건너뜀, Node 317 통과, ARM64+AMD64 이미지 게시, AMD64 fixture 기동 smoke 통과.
  - Production: NAS `robingraph-api`가 이미지 `ghcr.io/evodmik/robingraph@sha256:336ace7938471bdcdf2be1bfac904a33aa1cfd20987ed945c4ed5a74632f005d`, revision `770495a…2f0`로 교체됨. healthy, 네이티브 Django ASGI, FastAPI·Starlette 없음. 내부 API health·OpenAPI·lineage 200, drift 없음. 공개 URL Chromium 6/6 통과.
  - 운영 DB: 앱만 교체했다. 감시 범위(ingest 상태 해시·Taxon 33,694·이름 벡터 0/카탈로그 비어 있음)가 전후 바이트 동일하다. **DB 전체 체크섬이 아니다.** TEST DB 복사·backfill·마이그레이션·운영 n8n 변경 없음.
- TEST 검증(clean 1,029/991/38, Node 317 등)은 이전 기록의 **과거 증거**로 따로 정리했다. 현재 preflight와 Jenkins·Production 실제 증거와 섞지 않는다.

## 요청 배경과 목표

- 배경: RG-701 후속(FastAPI 완전 제거·Django 단독 전환)은 TEST에서 실제 API·브라우저·runner·n8n·DB 불변 검증을 마쳤고 Production 승인 대기였다(`docs/work-log/2026-10-20-rg701-django-only.md`).
- 목표:
  1. dev-codex의 검증된 작업을 커밋해 main에 병합·push한다.
  2. Jenkins Production 파이프라인의 checkout 대상을 `dev-codex`에서 `main`으로 바꾼다.
  3. 기존 admin 승인 gate를 거쳐 NAS Production 앱을 교체하고 실제로 검증한다.
- 범위 밖: 운영 DB 스키마·데이터 변경(이번 전환에는 Django ORM 마이그레이션이 없다), TEST DB 복사, 운영 n8n 워크플로 변경, 문서 담당의 Git·Jenkins·앱 조작.

## 역할 분담

| 역할 | 워크트리 | 이번 담당 |
|---|---|---|
| Root (Codex, 총괄) | dev-codex | 커밋, main 병합·push, Jenkins 설정 전환·빌드, 승인 gate 제출, Production 교체·검증, 증거 산출 |
| 문서 담당 (Claude) | main-2 (dev) | 이 문서, Obsidian 작업기록·RG-701 백로그(단독 쓰기). Git·배포·앱/설정 수정 없음 |

## 과거 TEST 증거 (이력 — 이번에 재실행하지 않음)

출처: dev-codex `docs/verification/assets/2026-10-20-rg701-complete/` (문서 담당 읽기 확인, 파일 시각 2026-10-20 16:32–16:50). 상세는 `docs/work-log/2026-10-20-rg701-django-only.md`.

| 구분 | 결과 | 종류 | 근거 |
|---|---|---|---|
| Python 전체 (clean venv, FastAPI·Starlette 미설치) | 1,029 실행 · 991 통과 · 38 건너뜀 · 0 실패 (22.324초) | 오프라인 fixture/mock, 외부 통합 opt-in 건너뜀 | `python-tests.log` `OK (skipped=38)` |
| 프런트엔드 Node | 317 통과 · 0 실패 · 0 건너뜀 | mock | `frontend-tests.log` |
| API golden (favicon 변경 후) | 19 통과 | fixture | `api-contract-tests.log` |
| runner mock | 33 통과 | mock | `runner-tests.log` |
| `django check` | 문제 없음 | 정적 | `django-check.log` |
| golden | 응답 273 + store-call 10, SHA `5e57bf73…6d2de`, 재생성 없음 | fixture | `integrated-api.json`, `summary.json` |
| TEST 배포 계약 | health·OpenAPI·lineage 200, drift 없음, `contract_parity_ok` | 실제 TEST API | `deployment-verification.json` |
| 실제 TEST API | 5/5 | 실제 TEST DB/API | `live-api.json` |
| 공개 TEST 브라우저 | Chromium 1280·390·320 × 2 = 6 통과, page error 0, 응답 mocking 없음 | 실제 TEST URL, 물리 기기 아님 | `browser.json` |
| 런타임 증명 | 앱·runner 컨테이너 같은 이미지 `sha256:5b70ec99…68349`, 네이티브 Django ASGI, FastAPI·Starlette 없음 | 실제 TEST 컨테이너 | `runtime-proof.json` |
| runner 실제 보호 장치 | 401·413·404·400 4/4 | 실제 TEST runner | `runner-live-guards.json` |
| n8n | CLI exit 0, 7노드, apply `already_applied` | 실제 n8n TEST | `django-only-n8n.json` |
| TEST DB 전후 | 동일(`unchanged: true`), 이름 벡터 855 | 실제 TEST DB 읽기 | `db-comparison.json` |
| 롤백 | mock 7/7, **실제 롤백 미실행** | mock | `operator-rollback-mocks.json` |

- `summary.json`의 `production_changed: false`, `commit_push_performed: false`는 **TEST 시점** 상태다. 이후 커밋·배포는 아래 절에 따로 기록한다.
- TEST의 이름 벡터 855개는 **TEST DB 값**이다. Production에는 이름 벡터가 없다(아래 참조).

## 현재 preflight (2026-10-20 17:50–17:52 KST)

| 항목 | 값 | 근거 |
|---|---|---|
| dev-codex 커밋 | `e3a8bda` feat: migrate API and ingestion runner to native Django (269 files, 누적 검증 변경 + README 기술 스택), `770495a` docs: normalize recorded deployment output whitespace (5 files) | 문서 담당 `git log`/`git show --stat` 읽기 |
| dev-codex 작업 트리 | clean (`git status --short` 0줄) | 문서 담당 확인 |
| 병합 전 main | `eca1d56`, dev-codex의 조상 | 문서 담당 `git rev-parse`·`merge-base --is-ancestor` |
| 병합·push | main fast-forward → `770495a13fe7c7431c2d66cbf41a1080272d42f0`, dev-codex·origin/main push 성공 | `git-publication.json` (원격 `refs/heads/dev-codex`·`refs/heads/main` 모두 `770495a…`), 문서 담당 로컬 확인: `main` = `origin/main` = `origin/dev-codex` |
| preflight 테스트 | 29 실행 · OK (실제 실행) | `preflight-tests.log` |
| 비밀값·경로 검사 | 커밋 후보 271파일: 인증 정보 일치·민감 경로·10MiB 초과 없음 | Root 전달 |
| 공백 정리 | `770495a`는 과거 배포 로그 5개의 줄 끝 공백만 정리. 고정 docs HTML 3개는 HTTP golden 계약을 유지하려고 기존 공백을 의도적으로 남김. 현재 변경 `git diff --check` 통과 | Root 전달 |
| Jenkins 설정 | Production job을 일시 비활성한 뒤 inline 파이프라인 checkout을 저장소 `main`으로 변경, Declarative lint 후 실행 | `jenkins-start.json` (`checkout: main`, `pipeline_validated: true`), Root 전달 |

- preflight 로그의 `Name relationship lookup failed (RuntimeError)`는 테스트가 일부러 유도한 오류 경로의 로그다. 결과는 `OK`다(이전 API golden 로그와 같은 형태).
- preflight 29개의 모듈 구성은 로그에 이름이 없다. 아래 명령 기록(Root 전달)에 따르면 네 모듈이다.

## Jenkins 빌드와 승인 gate (실제)

| 항목 | 값 | 근거 |
|---|---|---|
| job / build | `RobinGraph-PROD` #3, `result: SUCCESS`, `building: false`, 203,615ms | `jenkins-build-3.json`, `jenkins-summary.json` |
| checkout | `main` @ `770495a13fe7c7431c2d66cbf41a1080272d42f0` | `approval.json`, `production-release.json` |
| 빌드 안 테스트 | Python 1,029 실행 · 991 통과 · 38 건너뜀, Node 317 통과 | `jenkins-summary.json` — **이번 Jenkins 실제 실행**(과거 TEST 실행과 별개) |
| 이미지 | ARM64+AMD64 게시, AMD64 fixture 기동 smoke 통과. 불변 digest `sha256:336ace7938471bdcdf2be1bfac904a33aa1cfd20987ed945c4ed5a74632f005d` | `approval.json`, Root 전달 |
| Jenkins 산출물 | `image-metadata.json`, `production-release.json` | `jenkins-build-3.json` |
| 승인 gate | 기존 admin 승인 gate(`ApproveProduction`)에 사용자 명시 승인을 근거로 제출, 콘솔에서 "Approved by admin" 후 `Deploy and verify NAS Production` 단계 진입 확인 | `approval.json` (`jenkins_admin_gate_submitted`·`gate_console_confirmed: true`), Root 전달 |

- **승인 주체 구분**: gate 제출은 Root가 사용자의 명시 승인을 근거로 했다. 사용자가 Jenkins UI에서 새로 누른 것이 아니다.
- **중간 정정**: Root의 첫 전달(08:54Z)은 "승인 제출·approval.json 저장"이라고 했으나 곧 정정했다(08:54:30Z). 소문자 gate id 요청은 404, 다른 submit 요청은 400으로 **상태 변화가 없었다**. 대문자 `ApproveProduction` `proceedEmpty`가 성공했고 콘솔에서 확인한 뒤에 `approval.json`을 저장했다(08:55Z). 중복 승인은 없다고 Root가 보고했다.

## Production 배포 결과 (실제)

| 항목 | 값 | 종류 | 근거 |
|---|---|---|---|
| 배포 revision | `770495a13fe7c7431c2d66cbf41a1080272d42f0` | 실제 Production | `production-release.json` (`production_verified: true`) |
| 이미지 | `ghcr.io/evodmik/robingraph@sha256:336ace7938471bdcdf2be1bfac904a33aa1cfd20987ed945c4ed5a74632f005d` (로컬 image ID `sha256:957d679e…8bf4`) | 실제 NAS 컨테이너 | `runtime-proof.json` |
| 런타임 | 컨테이너 `robingraph-api` healthy, `native_django_asgi: true`, FastAPI·Starlette 없음(`true` = 없음), revision 일치 | 실제 Production 컨테이너 | `runtime-proof.json` |
| health | `status: ok`, `mode: neo4j`, `deployment_target: prod`, `taxonomy_release: fixture-avlist-2025` | 실제 Production API | `runtime-proof.json` |
| 내부 API 계약 | Jenkins #3 Deployment 단계의 실제 결과: `/health`·`/openapi.json`·`/v1/taxa/lineage?name=청둥오리` 모두 200, structural/schema/response drift·canary 문제 없음, `contract_parity_ok: true`, `passed: true` (lineage 릴리스 `v2025b`) | 실제 Production 내부 API (NAS 컨테이너 `127.0.0.1:8000`) | `internal-api-verification.json` (Root가 #3 Deployment 단계 출력만 추출) |
| 공개 브라우저 | `https://robingraph.dove-nest.com`, Chromium 1280·390·320 × 2질의 = 6/6 통과, page error 0, 가로 넘침 없음, 응답 mocking 없음, 스크린샷 3장 | 실제 공개 Production URL, **물리 기기 아님** | `browser.json`, `browser.cjs`, `django-{1280,390,320}.png` |
| DB 전후 | `db-before.json` = `db-after.json` 바이트 동일(문서 담당 `cmp`), `unchanged: true` | 실제 운영 DB **읽기 전용**, 감시 범위만 | `db-comparison.json` |

- 브라우저 질의: `Anas platyrhynchos`(scope `korea`)와 `흰뺨검둥오리`(scope `all`). 둘 다 `disposition: answer`를 기대한다. `browser.cjs`는 각 응답 JSON에 학명(`Anas platyrhynchos` / `Anas zonorhyncha`)이 포함되는지와 `scrollWidth > innerWidth`가 거짓인지(가로 넘침 없음)를 assert한다(문서 담당 스크립트 읽기).
- health의 `taxonomy_release: fixture-avlist-2025`는 `/v1/answers`·`/v1/search` 처리 릴리스 값이다. TEST 검증기가 기록한 것처럼 AviList lineage 릴리스와는 다른 데이터 영역이다.
- DB 비교 범위(`db-comparison.json` `scope`): ingest 상태 fingerprint `5a5eee35…1a866b`, `pg_database: robingraph`, Taxon 33,694, TaxonNameVector 0·카탈로그 fingerprint 비어 있음. `not_full_database_checksum: true` — **DB 전체가 동일하다고 주장하지 않는다.**
- **Production에는 이름 벡터가 없다(0).** TEST의 855개는 TEST DB 값이며 Production에 있다고 기록하지 않는다. 이번 배포는 벡터를 채우지 않았다.

## 운영 DB 관련 사용자 결정 (이번 배포 중)

- 배포 진행 중 사용자가 TEST DB를 Production으로 복사하자고 요청했다가 곧바로 그게 바람직한지 되물었다(Root 전달).
- Root는 TEST DB 전체 복사를 하지 않고 운영 DB를 그대로 두며, 필요한 데이터셋은 선택적으로 따로 검토하자고 설명했다. 이번 배포는 **앱 교체만** 진행했다.
- 결과: TEST DB 복사·backfill·마이그레이션·파이프라인 DB 쓰기·운영 n8n 워크플로 변경 **없음**(`approval.json` `test_db_copy_performed: false`, `db-comparison.json` `test_database_copied: false`).
- 후속: 운영 이름 벡터·카탈로그 등 데이터셋을 반영할지는 데이터셋별로 출처·범위를 검토한 뒤 **별도 승인**으로 정한다. 이 문서는 그런 반영을 새 요구사항으로 정하지 않는다.

## 변경 전후 동작 (Production)

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 배포 소스 브랜치 | Jenkins checkout `dev-codex` | `main` (`770495a`) |
| 운영 이미지 | digest `sha256:100e4aa30fd8981ebb631ced8c4bfecd95e71fcdb6d90cc5026e42f11b333ead` | digest `sha256:336ace79…2f005d` |
| API 런타임 | 이전 운영 이미지 런타임(RG-701 이전 운영 릴리스) | 네이티브 Django + DRF ASGI, FastAPI·Starlette 미설치 |
| 운영 DB | Taxon 33,694, 이름 벡터 0 | 감시 범위 동일 |
| 운영 n8n | — | 변경 없음 |

- 이전 운영 이미지의 내부 런타임 구성은 이번 증거에 없어 문서 담당이 확인하지 않았다.

## 변경 파일과 구현 내용

- 앱·설정·CI(Root, dev-codex 커밋 `e3a8bda`): RG-701 1차·후속의 누적 변경 전체(Django 설정·ASGI, DRF 뷰, 서비스 추출, FastAPI 어댑터 삭제, AviList runner Django ASGI 이전, `pyproject.toml`·`uv.lock`, Dockerfile·Jenkinsfile, README 기술 스택, 테스트·golden 등 269 files). 세부 목록은 이전 기록 2건과 `git show --stat e3a8bda`를 따른다.
- `770495a`: 과거 배포 로그 5개의 줄 끝 공백만 정리.
- Jenkins job 설정(저장소 밖): inline 파이프라인 checkout을 `main`으로 변경.
- main-2(문서 담당): `docs/work-log/2026-10-20-main-production-django.md` 신규. 이전 기록(`2026-10-20-rg701-django-only.md`, `2026-10-20-rg701-django-drf-migration.md`, 백로그 등록 기록)은 **수정하지 않았다**.

## 검증 방법과 실제 결과 (구분)

| 구분 | 범위 | 통과 / 실패 / 건너뜀 | 종류 |
|---|---|---|---|
| 과거 TEST (16:32–16:50) | 위 "과거 TEST 증거" 표 | 위 표 참조 | 오프라인 mock/fixture + 실제 TEST |
| preflight | 29 테스트 | 29 / 0 / 0 | 오프라인 |
| Jenkins #3 | Python 전체, Node, AMD64 smoke | 991 / 0 / 38 · 317 / 0 / 0 · 통과 | 오프라인 fixture/mock (빌드 환경) |
| Production 런타임 | 컨테이너·health·패키지·revision | 통과 | 실제 Production |
| Production 내부 API | health·OpenAPI·lineage 3 경로 + drift 검사 | 3 / 0 / 0, drift 없음 | 실제 Production |
| Production 브라우저 | 6 요청 | 6 / 0 / 0 | 실제 공개 URL, 데스크톱 Chromium 폭 조절 |
| Production DB | 감시 범위 3항목 | 동일 | 실제 운영 DB 읽기 전용 |
| 실제 롤백 | — | **미실행** | — |

- 문서 담당은 테스트·배포를 다시 실행하지 않았다. `cmp`·`git rev-parse`·파일 읽기로만 대조했다.

### 실제 사용한 명령 기록 (Root 전달)

아래는 이번 증거를 만든 **당시 명령의 기록**이며 다시 실행하라는 지시가 아니다. `/tmp/rg701-complete/*.py`는 Jenkins 설치·실행과 운영 확인용 일회성 운영 스크립트이므로 그대로 재실행하지 않는다. 인증 값은 기록하지 않는다. 문서 담당은 이 명령들을 실행하지 않았다.

```sh
# preflight (29 tests)
PYTHONPATH=tests .venv/bin/python -m unittest test_registry_prod_deployment test_registry_test_deployment test_django_runtime test_drf_parity -q
# 커밋·push·main fast-forward
git add -A; git commit; git push origin dev-codex
git -C /Users/kimdove/Desktop/RobinGraph merge --ff-only dev-codex
git -C /Users/kimdove/Desktop/RobinGraph push origin main
# Jenkins 파이프라인 lint·설치·실행 (일회성 운영 스크립트)
python3 /tmp/rg701-complete/start-production.py
# Jenkins #3 빌드 안 CI
uv run --locked --extra test --extra tracing python -m unittest discover -s tests
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
# Production 확인
python3 /tmp/rg701-complete/prod-runtime.py
python3 /tmp/rg701-complete/nas-readonly.py docs/verification/assets/2026-10-20-production-django/db-after.json
node docs/verification/assets/2026-10-20-production-django/browser.cjs
```

- preflight 29개는 `test_registry_prod_deployment`·`test_registry_test_deployment`·`test_django_runtime`·`test_drf_parity` 네 모듈이다(Root 전달 명령 기준).
- 내부 API 결과(`internal-api-verification.json`)는 별도 명령이 아니라 Jenkins #3 Deployment 단계 출력에서 추출했다(Root 전달).

## 롤백 기준

- 이전 운영 이미지 digest `sha256:100e4aa30fd8981ebb631ced8c4bfecd95e71fcdb6d90cc5026e42f11b333ead`와 백업 환경 파일을 보존했다(Root 전달). **실제 롤백은 실행하지 않았다.** 롤백도 운영 변경이므로 별도 승인이 필요하다.

## 배포·커밋 정보

- 커밋: `e3a8bda`, `770495a` (dev-codex). main fast-forward, `origin/main` = `origin/dev-codex` = `770495a13fe7c7431c2d66cbf41a1080272d42f0` (릴리스 문서 커밋 전 시점).
- Production: Jenkins `RobinGraph-PROD` #3 SUCCESS, NAS `robingraph-api` 교체·실제 검증 완료.
- 공통 AGENTS.md: Root가 Jenkins 상태 단락(과거 dev-codex·#2 → main polling·#3 Django SUCCESS·DB 복사 없음)을 고쳐 네 워크트리(dev-codex·dev-claude·main·main-2)에 같은 단락을 전파했다. Root의 인프라 문서 변경이며 Root 최종 문서 커밋에 포함한다. 문서 담당은 AGENTS.md를 수정하지 않았다.
- 배포 후 처리(Root 전달, 이 문서 작성 시점에 진행 중): 성공 **후** Jenkins를 잠시 멈추고 최종 릴리스 문서를 commit/push한 뒤 main polling을 복원하고 `CHECK_ONLY`로 실행해 문서 커밋이 두 번째 배포를 일으키지 않게 한다. 이 처리의 결과는 이 문서에서 확인하지 않았다.
- 같은 최종 릴리스 문서 커밋에 Root가 README(현재 기술 스택·TEST+Production 범위)와 `docs/jenkins-deployment.md`(현재 main 절: #3 SUCCESS, 이 기록 링크) 수정을 포함한다(Root 전달). 문서 변경이며 배포된 runtime `770495a`는 바뀌지 않는다. 이 커밋의 해시는 이 문서 작성 시점에 확인하지 않았다.
- main-2 문서는 미커밋이다. Root가 검토한 뒤 dev-codex에 반영한다.

## 남은 한계와 후속 사항

- **미검증**: 건너뛴 외부 통합 테스트 38건(실제 DB 쓰기 포함), 물리 모바일·Safari·Firefox, 물리 재부팅, 실제 롤백, 네이티브 ingest의 실제 운영 DB 쓰기.
- 운영 DB 비교는 감시 범위만 다룬다. DB 전체 동일성은 확인하지 않았다.
- Production 이름 벡터 0: 그래프 우선 이름 해소의 벡터 후보 경로는 운영에서 데이터가 없다. 데이터셋 반영은 별도 검토·승인 대상이다.
- AviList runner·n8n은 TEST 전용이며 Production에서 바꾸지 않았다.
- Jenkins main polling 복원·`CHECK_ONLY` 문서 커밋 소비 결과는 Root 확인 대상이다.
