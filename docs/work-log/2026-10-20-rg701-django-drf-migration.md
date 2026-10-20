# RG-701 FastAPI → Django + DRF 전환 구현·TEST 배포 — 2026-10-20

> **문서 상태: RG-701 진행 중 — TEST 배포·검증 완료, Production 승인 대기.** 아래 결과는 Root(Codex)가 실제로 실행해 전달한 최종 증거와 dev-codex `docs/verification/assets/2026-10-20-rg701/`의 산출물(문서 담당이 읽기 전용으로 확인)을 근거로 한다. 문서 담당은 테스트·배포를 재실행하지 않았다. RG-701 항목 전체가 완료된 것은 아니다.

## 요약

- 작업 ID: **RG-701** (7xx 배포·인프라). 우선순위 **1 (최우선)** — 변경 없음.
- 상태: 계획 (미착수) → **진행 중 (TEST 배포·검증 완료 · Production 승인 대기)**.
- 착수 근거: 사용자가 Orca 코디네이터를 통해 구현 진행을 승인했다(사용자 지시 원문: "그렇게 진행해줘").
- 결과: 공개 API 런타임을 FastAPI에서 네이티브 Django 5.2.18 + DRF 3.16.1로 전환했다. 새 런타임은 FastAPI를 import하지 않는다. TEST(M4 16GB Mac)에 이미지 `robingraph-api:test-rg701-django-34f84c494c6a`를 배포해 healthy·실제 TEST API·공개 브라우저·n8n·DB 불변 검사를 통과했다.
- 범위 밖으로 남은 것: Production 배포(사용자 별도 승인 필요), commit/push, 롤백 실제 실행, 물리 모바일·물리 재부팅, AMD64 이미지 빌드, 네이티브 내부 ingest의 실제 DB 쓰기(fake 저장소 테스트만 수행).
- 선행 기록: 백로그 등록·담당 사전 배정은 `docs/work-log/2026-10-20-django-drf-migration-backlog.md`에 그대로 두었고 이 문서에서 다시 쓰지 않았다.

## 요청 배경과 목표

- 배경: RG-701은 2026-10-20 사용자 요청으로 최우선(1)·계획 상태로 등록되었고 같은 날 담당 에이전트·모델을 사전 배정했다. 이후 사용자가 구현 진행을 승인했다.
- 목표(백로그 정의): 기존 공개·내부 API URL과 요청·응답·오류 계약을 유지한 채 웹 계층을 FastAPI에서 Django + DRF로 전환한다. 조류 근거·데이터와 Neo4j 검색 로직을 재사용하고 프레임워크 독립 서비스 계층을 만든다. 성능 향상은 목표나 약속이 아니다.
- 승인 범위: 구현·검증·TEST 배포. Production·운영 컨테이너·운영 DB 변경은 AGENTS.md 운영 배포 승인 규칙에 따라 별도 명시 승인 전에는 하지 않는다. commit/push는 이번 지시 범위 밖이다.

## 역할 분담

| 역할 | 에이전트 | 모델 | 워크트리 (브랜치) | 담당 |
|---|---|---|---|---|
| 총괄·통합 (Root) | Codex | 현재 세션 모델 그대로(재설정하지 않음) | dev-codex | `django_api/settings.py`·`asgi.py`, CLI, 의존성, Docker·Jenkins, 통합 검증·TEST 배포 |
| 구현 | Claude | `claude-opus-5-5` (계획 모델) | dev-claude | 네이티브 DRF View·Serializer·URL·factory, 서비스 추출 |
| UI 호환 | Codex | `gpt-6.1-sol` (계획 모델) | main (dev-agy) | 정적 UI·API 소비 HTTP 호환 검사 |
| 독립 검토 | `gpt-6.1-sol` 검토자 | `gpt-6.1-sol` | — | 새 API·런타임·CLI·인프라 코드 전수 검토 |
| 문서 | Claude | `claude-opus-5-5` | main-2 (dev) | 저장소 기록·Obsidian 단독 쓰기·백로그 |

- 모델은 코디네이터 전달 기준이다. UI 담당 세션은 모델 업데이트 프롬프트가 건너뛰어져 같은 터미널에서 재시도했다는 전달이 있었고, 실제 실행 모델은 문서 담당이 확인하지 않았다.

## 확인한 원인과 근거

### 설계 결정 (Root 전달 · 코드 확인)

- **Django는 상태 없이(stateless) 사용**: `src/robingraph/django_api/settings.py`에 `INSTALLED_APPS = ['rest_framework']`, `MIDDLEWARE = []`, `DATABASES = {}`, `APPEND_SLASH = False`, DRF 인증 클래스 없음·`AllowAny`·JSON 렌더러/파서만 둔다. auth/admin/session을 설치하지 않고 **Django 마이그레이션이 없다**. 기존 PostgreSQL 스키마는 `ingest/migrations/0001~0004_*.sql`과 `_schema_migration`이 계속 소유한다(백로그 단계 4의 분리 방식).
- 비밀값: `SECRET_KEY`는 환경 변수 `ROBINGRAPH_DJANGO_SECRET_KEY` 또는 실행 시 임의 생성값. 문서에 값은 기록하지 않는다.
- **네이티브 런타임**: 공개 API는 `robingraph.api.drf.create_django_app`가 만드는 `DjangoApiApplication`으로 실행한다. 런타임에서 FastAPI로 프록시하지 않는다.
- **legacy 보존**: 기존 FastAPI 앱·보조 함수는 전환 기간의 차등 비교 기준으로만 남긴다. 고정한 OpenAPI 문서(`api/drf/openapi.json`·`openapi_ingest.json`)는 전환 호환용이며, 앞으로 API를 바꾸면 이 스냅샷도 함께 갱신해야 한다.
- **범위 경계**: 별도 AviList TEST runner(독립 FastAPI TEST 서비스)는 설계상 전환하지 않았고 바뀌지 않았다.

### 착수 전 기준선

| 항목 | 값 | 산출물 |
|---|---|---|
| Python 전체 | `uv run --locked --extra test python -m unittest discover -s tests -q` → 999 실행 · 961 통과 · 38 건너뜀 · 0 실패 (23.058초, 오프라인/모의/fixture, 실제 DB opt-in 건너뜀) | `baseline-tests.json` |
| 공개 OpenAPI | 전환 전 스냅샷 | `openapi-before.json` |
| TEST DB (읽기 전용) | 이름 벡터 855개, 파일럿 수집 실행 1건(`succeeded`), 이름 카탈로그 fingerprint·기타 파이프라인 상태 해시 | `db-before.json` |
| TEST API·계약 | 실제 TEST API 5사례·health/OpenAPI/한국어 이름 lineage 계약 | `live-before.json`, `live-contract-before.json` |

### 배포 전 독립 검토에서 발견한 문제와 조치

검토자(`gpt-6.1-sol`)가 새 API·런타임·CLI·인프라 코드를 전수 읽고 실행했다(mock/fake 저장소 기반, 공유 DB 문제 아님).

- 확인된 사항: 네이티브 경로의 legacy 테스트 스위트 242 실행·1 건너뜀·0 실패, DTO 33개 클래스가 기존과 AST 수준 동일, 새 프로세스의 네이티브 import에 FastAPI 없음, 150ms 모의 호출 4건이 164ms에 완료(병렬 처리), 앱 2개 사이 handler 격리.
- 발견 1 — **대용량 수집 요청 차단**: Django 기본 `DATA_UPLOAD_MAX_MEMORY_SIZE`(2.5MiB) 때문에 정상 3MB ingest 요청이 기존 200 → 새 400으로 달라졌다(fake 저장소). 조치: 설정에 `DATA_UPLOAD_MAX_MEMORY_SIZE = None`(Root)으로 기존 정책 복원, 회귀 테스트 추가(Claude).
- 발견 2 — **허용되지 않은 Host 응답 불일치**: 200/500이 섞였다. 조치: 요청 초기에 `get_host()` 검증으로 일반 JSON 오류 본문과 `400`을 반환하고 테스트 추가(Claude, 후속 dispatch `ctx_7a2306379727`).
- 발견 3 — **Root 런타임 테스트의 순서 문제**: `DATABASES == {}` 정확 비교가 Django dummy backend 기본값 채움 뒤 맞지 않았다. 조치: dummy backend 단언으로 수정.

## 계약과 변경 전후 동작

- 유지한 계약: `POST /v1/answers`, `/v1/chat`, `/v1/search`, `GET /v1/observations`, `/v1/taxa/lineage`, `/v1/taxa/{name-relations,related,similar,ecological-related,subspecies,profile}`, `/health`, `/openapi.json`, 정적 `/`·`/chat`·`/birds`·`/favicon.ico`·`/static/...`, 내부 `/internal/v1/ingest/*`(내부 Bearer).
- 변경 전: `robingraph.api.app`의 FastAPI/Pydantic 앱을 uvicorn으로 실행.
- 변경 후: `serve-fixture`는 `robingraph.django_api.asgi:application`, `serve-neo4j`·`serve-ingest`는 `robingraph.api.drf.create_django_app(...)`을 uvicorn으로 실행. TEST 컨테이너 명령은 `robingraph serve-neo4j --host 0.0.0.0 --port 8000`.
- 응답 동등성: 같은 fixture로 기존 FastAPI(포트 18011)와 새 Django(포트 18012)를 로컬 실제 소켓으로 띄워 95사례의 전체 JSON(`error: null` 포함)·바이트·MIME·cache·location 헤더·경로 traversal 처리를 비교해 **95/95 일치**.
- 의도한 동작 변화: 잘못된 Host 값은 일치 경로·없는 경로·끝 슬래시·정적·ingest 경로 모두 일반 JSON `400`으로 통일(기존 200/500 혼재 해소).
- 전환 전부터 있던 동작(새 문제 아님): 기존 공개 서버에서도 끝 슬래시 경로는 `307`로 `http` 주소에 리다이렉트된다.

## 변경 파일과 구현 내용

dev-codex 작업 트리(미커밋) 기준이다. 이 작업 트리에는 이전 작업(RG-406·Jenkins·AviList 등)의 미커밋 변경도 섞여 있어, 아래는 문서 담당이 RG-701 관련으로 확인한 파일만 적는다. 이미지에 들어간 전체 소스는 `test-release.json`의 파일별 SHA-256으로 고정되어 있다.

### 신규

- `src/robingraph/django_api/settings.py`, `asgi.py`, `__init__.py` — 상태 없는 Django 설정·ASGI 진입점 (Root).
- `src/robingraph/api/drf/` — `application.py`(131줄, factory·`DjangoApiApplication`), `views.py`(366줄), `serializers.py`(181줄), `urls.py`(147줄), `validation.py`(122줄), 고정 OpenAPI·문서 페이지(`openapi.json`, `openapi_ingest.json`, `docs.html`, `redoc.html`, `oauth2_redirect.html`) (Claude).
- `src/robingraph/api/schemas.py`(346줄), `services.py`(1,495줄), `ingest_service.py`(387줄) — 프레임워크 독립 DTO·채팅 오케스트레이션/응답 매핑·수집 서비스 (Claude).
- `tests/test_django_runtime.py`(58줄), `tests/test_drf_legacy_suite.py`(78줄), `tests/test_drf_parity.py`(480줄).

### 수정

- `src/robingraph/api/app.py`(1,734줄 변경, 대부분 삭제)·`src/robingraph/api/ingest_router.py`(380줄 변경) — 로직을 서비스로 옮기고 얇은 legacy 어댑터로 축소.
- `src/robingraph/cli.py` — 위 실행 진입점 전환.
- `pyproject.toml`·`uv.lock` — `django>=5.2,<5.3`, `djangorestframework>=3.16,<3.17` 추가(설치 5.2.18 / 3.16.1). 공유 DTO가 직접 의존하므로 `pydantic>=2.12,<3`도 명시 추가(설치 2.13.5). 기존 `fastapi` 의존성은 legacy 비교·AviList runner용으로 남아 있다.
- `Dockerfile`, `Jenkinsfile`, `ci/Jenkinsfile.production`, `ci/Jenkinsfile.test`(기존 미추적 TEST 파이프라인) — `python -m django check --settings=robingraph.django_api.settings` 검사 단계 추가.
- `scripts/verify_api_deployment.py`(7줄 변경), `README.md`(Root 담당 현재 런타임 문장).

### 문서 담당 (main-2)

- `docs/work-log/2026-10-20-rg701-django-drf-migration.md` (이 문서, 신규). 선행 등록 기록은 수정하지 않았다. `docs/deployment-profile.md`의 과거 FastAPI 아키텍처 제안도 수정하지 않았다(아래 "배포 프로필 메모" 참고).

## 검증 방법과 실제 결과

### 최종 결과 (`summary.json`: "TEST deployed and verified; Production approval pending")

| 구분 | 결과 | 종류 | 산출물 |
|---|---|---|---|
| Python 전체 | 1,262 실행 · 1,223 통과 · 39 건너뜀 · 0 실패 (27.690초) | 오프라인 fixture/mock, 외부 통합 opt-in 건너뜀 | `python-tests-final.log` |
| 프런트엔드 Node | 317 통과 · 0 실패 · 0 건너뜀 | mock | `frontend-tests.log` |
| HTTP 동등성 | 95/95 | 로컬 실제 소켓 + fixture | `http-parity-final.json` |
| `django check` / `git diff --check` | 문제 없음 / 0 | 정적 | — |
| Host·3MB 회귀 + 변이 검증 | 통과. Host 검증 제거 시 하위 테스트 7개 실패, 메모리 상한 해제 제거 시 3MB 테스트 실패 | mock(fake 저장소) | — |
| Docker 전체 소스 ARM64 빌드 | 통과(`django check` 포함) | 실제 빌드 | — |
| 격리 fixture smoke | `--network none`에서 통과 | 실제 컨테이너 | — |
| TEST 앱 교체 | 앱만 재생성 → healthy → `manage.sh verify` 통과 | 실제 TEST | `test-release.json` |
| 런타임 확인 | `DjangoApiApplication`, Django 5.2.18, DRF 3.16.1, FastAPI 미import, healthy | 실제 TEST 이미지 | `runtime-after.json` |
| 실제 TEST API 5사례 | 전후 각 5/5 통과: Kea(all·outside → answer), Keaa(outside → clarify), Anas platyrhynchos(korea → answer), lineage | **실제 TEST DB/API** | `live-before.json`, `live-after.json` |
| 계약 검사 | health·OpenAPI·`청둥오리` lineage 200, schema/response drift 없음, `contract_parity_ok` | **실제 TEST API** | `live-contract-after.json` |
| 공개 브라우저 | Chromium 1280·390·320 × 2질의 = 6 채팅 요청 통과, JS 오류 0, 넘침 없음, `/birds` 200, 스크린샷 | **실제 공개 TEST URL**, 응답 mocking 없음, 물리 기기 아님 | `browser.json`, `django-1280.png`·`django-390.png`·`django-320.png` |
| n8n | `n8n-test` 워크플로 `rgAvilistTest01` 7노드 전체, CLI exit 0, prepare `reused`·verify 검색 회귀 4건 통과·apply `already_applied`, projection 없음 | **실제 n8n TEST** | `n8n-after.json` |
| DB 불변 | 전후 스냅샷 동일: 이름 벡터 855개, 카탈로그·기타 파이프라인 해시, 파일럿 실행 1건 | **실제 TEST DB 읽기** | `db-before.json`, `db-after.json` |
| graphify | `graphify update` rc 0, 6,576 nodes · 13,829 edges · 389 communities | — | `graphify-update.log` |

- lineage 계약 검사의 health `taxonomy_release`(`fixture-avlist-2025`)와 lineage 릴리스(`v2025b`)가 다른 것은 서로 다른 데이터 영역이라 정상이라고 검증기가 기록했다.
- 실행 수가 기준선(999)보다 정확히 263개 많다: Django 런타임 4 + DRF 동등성 17 + legacy 스위트 네이티브 재실행 242 (Root 전달).

### 중간 실패·건너뛰기 (숨기지 않고 기록)

- 계약 검증기를 처음 실행했을 때, 구현 담당의 `schemas` 모듈이 통합되기 전이라 `ModuleNotFoundError`가 났다. 통합 뒤 해결됐고, 이때 앱 배포는 시도하지 않았다(`preflight-notes.json`).
- 공개 health를 Python 기본 `urllib`로 요청하면 `403`, `curl` GET은 `200`, 내부 health는 `200`이었다. 실제 공개 브라우저 검사는 통과했다. 앱 장애로 보지 않는다(403의 원인은 확인하지 않았다).
- 중간 통합 회귀(1,260 실행·1,221 통과·39 건너뜀)는 Host·3MB 테스트 추가 전 값이며 최종값으로 대체됐다.
- 건너뜀 39건: 외부 통합 opt-in 검사(실제 DB 등). 이번 실행에서 다시 켜지 않았다.

## TEST 배포와 롤백

| 항목 | 값 |
|---|---|
| 대상 | TEST — M4 16GB Mac 앱 (`https://robingraph-test.dove-nest.com`, NAS 프록시 → Mac:8000) |
| 새 이미지 | `robingraph-api:test-rg701-django-34f84c494c6a` |
| 소스 해시 | `34f84c494c6a100a73674a5c25be599d52a50431a2a5af264f4deb7688f4370a` (미커밋 전체 소스 스냅샷, 기준 HEAD `bc643ee9edef0fc58c605adde70b4808b7622ac5`) |
| 새 release | `/Users/kimdove/robingraph-test/releases/rg701-django-34f84c494c6a-4f4628` (`state: verified`) |
| 이전 이미지 (롤백 기준) | `robingraph-api:test-rg406-outside-spelling-1c7cbbdaf1c7` |
| 이전 release (롤백 기준) | `/Users/kimdove/robingraph-test/releases/rg406-outside-spelling-1c7cbbdaf1c7` |
| 롤백 | 이전 release·이미지를 보존했고 자동 복구 경로를 준비했다. **실제 롤백은 실행하지 않았다.** |
| 변경하지 않은 것 | TEST DB·Neo4j·n8n 위치, DB 스키마, 도메인 이름 벡터, Jenkins job 실행, 독립 AviList FastAPI TEST runner |

## 배포 프로필 메모

`docs/deployment-profile.md`에 있는 FastAPI 기반 아키텍처 설명은 당시 제안 기록으로 그대로 둔다. 2026-10-20 기준 현재 구현은 다음과 같다(이 메모는 Root가 필요하면 해당 문서에 날짜를 붙여 옮긴다).

> 2026-10-20 (RG-701): 공개 API 런타임은 Django 5.2.18 + DRF 3.16.1 네이티브 ASGI 앱(`robingraph.api.drf`, 설정 `robingraph.django_api.settings`)이다. Django DB·마이그레이션은 사용하지 않고 PostgreSQL 스키마는 기존 SQL 마이그레이션이 소유한다. TEST에서 검증했으며 Production은 아직 FastAPI 이미지다(별도 승인 대기). 독립 AviList TEST runner는 FastAPI로 남는다.

## 배포·커밋 정보

- TEST: 위 이미지로 앱만 교체·검증 완료.
- Production: **변경 없음**(`production_changed: false`). 운영 반영은 사용자 명시 승인 후 별도로 진행한다.
- commit/push: 없음. Jenkins job 실행 없음. AMD64 이미지 빌드 없음.

## 남은 한계와 후속 사항

- **Production 승인 대기**: 운영 반영 시 운영용 이미지(AMD64 포함) 빌드, 운영 승인 gate, 운영 검증이 별도로 필요하다.
- **롤백 미실행**: 경로만 준비했다. 실제 롤백 리허설이 필요하면 별도로 수행한다.
- **미검증**: 물리 모바일 기기·Safari·Firefox, 물리 재부팅, 네이티브 내부 ingest의 실제 DB 쓰기(fake 저장소 테스트만), AMD64 이미지.
- **legacy 정리**: FastAPI legacy 어댑터·고정 OpenAPI는 전환 호환 기준으로 남아 있다. 제거 시점과 `fastapi` 의존성 제거는 후속 결정이다. 앞으로 API를 바꾸면 고정 OpenAPI 스냅샷도 갱신해야 한다.
- **독립 AviList TEST runner**: FastAPI 그대로다(이번 범위 밖).
- **미커밋 상태**: TEST 이미지는 미커밋 소스 스냅샷이다. 커밋할 때 `test-release.json`의 파일 해시와 대조해야 같은 소스임을 보장할 수 있다.
- **백로그 상태**: 백로그 완료 기준 중 Production 단계가 남아 RG-701은 진행 중(TEST 검증 완료·Production 승인 대기)으로 둔다. 항목 전체 완료로 옮기지 않는다.

## 진행 경과 (시간순, UTC)

- 06:40 Root 아키텍처·초기 증거: 의존성·stateless 설정·CLI 전환, Root 런타임/CLI 테스트 2개 통과, UI Node 317 통과, HTTP 95사례 비교 도우미 준비(Django 대상 미실행).
- 06:42 Root 정정: `asgi.py`는 `robingraph.api.drf`를 import한다. 초기 초안의 `.application` import는 폐기됐다. 문서 담당의 초기 관찰 중 빠진 파일 관련 내용은 실패가 아니어서 이 문서에서 제외했다.
- 06:52 독립 검토 결과·수정 착수(위 발견 3건).
- 06:53 HTTP 동등성 95/95(통합 전 overlay, `http-parity-overlay.json`).
- 06:58 통합 회귀 1,260/1,221/39/0, `http-parity-integrated.json` 95/95.
- 07:00 최종 코드·테스트 1,262/1,223/39/0, TEST 빌드 시작.
- 07:02 TEST 배포·전체 검사 통과(최종 증거).

## Obsidian 동기화와 재조회

- 대상: `Work/RobinGraph/RobinGraph 작업 백로그.md`, `Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그.md`, `Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-FastAPI-Django-DRF-전환-구현.md`(신규), `Work/RobinGraph/작업기록/index.md`(7xx 작업기록 수 14 → 15).
- 초기 단계 재조회: 전체 백로그에 `진행 중 작업` 구역·목차, 카테고리별 보기·현황표·대기 표·RG-701 안내 절·변경 이력 반영, RG-406·RG-101 행과 기존 등록·배정 이력 원문 유지를 확인했다. 7xx 백로그 상태·링크와 index 수치도 확인했다.
- 최종 단계 재조회(2026-10-20, Obsidian MCP): 구현 노트 158줄(`status: in-progress`, 최종 검증 표·TEST 배포/롤백 표 포함). 전체 백로그 479줄 — 카테고리별 보기 701 `진행 중 (최우선 1 · TEST 배포·검증 완료 · Production 승인 대기)`, 현황표 `진행 중 (TEST 검증 완료 · Production 승인 대기) | 1 (최우선)`, 진행 중 작업 구역·대기 표·RG-701 안내 절의 TEST 결과 문단·변경 이력 최상단 항목을 확인했고 RG-406·RG-101 행은 원문 그대로다. 7xx 백로그 96줄 — 작업 현황 첫 항목·RG-701 상태·작업기록 링크를 확인했고 담당 배정 표는 바뀌지 않았다. 작업기록 index 7xx `15`. 링크는 텍스트로 대조했고 Obsidian 화면 클릭 검증은 하지 않았다.
- 저장소 기록과 Obsidian 노트의 핵심 수치·이미지·롤백 기준·한계는 같은 내용으로 맞췄다.
