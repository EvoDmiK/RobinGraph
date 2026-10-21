# RG-701 후속: FastAPI 완전 제거(Django 단독 전환) — 2026-10-20

> **문서 상태: RG-701 진행 중 — 후속(Django 단독 전환) TEST 배포·실제 검증 완료, Production 승인 대기.** Root(Codex)가 코디네이터로 전달한 최종 증거와 dev-codex `docs/verification/assets/2026-10-20-rg701-complete/` 산출물(문서 담당이 **읽기 전용**으로 확인)을 근거로 한다. 문서 담당은 테스트·배포를 실행하지 않았다. Production 배포·commit/push는 없다. RG-701 항목 전체가 완료된 것은 아니다.

## 요약

- 작업 ID: **RG-701** (7xx 배포·인프라). 우선순위 **1 (최우선)** — 변경 없음.
- 상태: **진행 중** 유지 — 후속 TEST 배포·실제 API·브라우저·runner 갱신·runner 보호 장치·n8n·DB 사후 동일성 검증 완료. **Production 승인 대기**(사용자 명시 승인 전 운영 반영 없음).
- 사용자 요청: 설계 감사 + 테스트 + **Django로의 완전 교체**. 1차 전환에서 남겨 둔 (1) FastAPI 비교용 legacy 어댑터와 (2) 독립 AviList TEST runner(FastAPI)까지 포함한다.
- 결과: 정식 소스에서 `api/app.py`·`ingest_router.py` 삭제, 테스트는 네이티브 HTTPX ASGI 도우미 사용, 의존성 lock에 FastAPI·Starlette 없음. clean 환경 Python 1,029 실행·991 통과·38 건너뜀·0 실패, Node 317 통과. 새 TEST 이미지 `robingraph-api:test-rg701-django-only-0e15293544bb`(이미지 안 FastAPI·Starlette 없음)로 공개 앱과 AviList runner 교체, 실제 TEST API 5/5·공개 Chromium 6요청·runner `code_changed` → 재검토 바인딩 → `verified`·runner 실제 보호 장치 4건·n8n 7노드(CLI 0, `already_applied`)·TEST DB 전후 동일(벡터 855) 확인. 롤백은 mock 7건만, 실제 롤백 미실행.
- 요청 문구의 "교체"는 Production 승인이 아니다. Root가 "TEST 이후 별도 명시 승인"을 설명했고 AGENTS.md 운영 배포 승인 규칙을 따른다.
- 이전 기록 `docs/work-log/2026-10-20-rg701-django-drf-migration.md`와 백로그 등록 기록은 **수정하지 않았다**(당시 이력 보존).

## 요청 배경과 목표

- 배경: 1차 전환(같은 날)에서 공개 API 런타임은 네이티브 Django 5.2.18 + DRF 3.16.1로 바뀌었지만, FastAPI 앱(`api/app.py`)·`ingest_router.py`는 차등 비교 기준으로, 독립 AviList TEST runner는 FastAPI 그대로 남았고 `fastapi` 의존성도 설치돼 있었다. 1차 기록의 "남은 한계"에 이 둘이 후속 결정으로 적혀 있었다.
- 목표:
  1. FastAPI 어댑터 삭제 후에도 계약을 검증하도록, 삭제 **전에** 실제 FastAPI 응답을 고정 golden으로 캡처해 비교를 대체한다(Django 자기 자신과의 비교가 아님).
  2. 독립 AviList runner(`serve_avilist_pipeline`)를 Django ASGI로 이전한다.
  3. `pyproject.toml`·`uv.lock`에서 FastAPI·Starlette 의존성을 제거한다.
  4. TEST에서 실제 배포·검증 후 Production 승인을 요청한다.
- 범위 밖: Production 배포·운영 컨테이너·운영 DB, commit/push, core·source·bundle 정책 변경(정책은 TEST 전용 유지), Django ORM·데이터 마이그레이션 도입(없음).

## 역할 분담 (이번 후속)

| 역할 | 워크트리 | 이번 후속 담당 (Root 전달) |
|---|---|---|
| Root (Codex, 총괄) | dev-codex | 정식 소스 통합, 독립 AviList runner의 Django ASGI 이전, 의존성 제거, clean 환경 검사, runner mock 33개, ASGI receive 단계 본문 상한 수정, TEST 배포·runner 코드 바인딩 갱신·통합 검증 |
| Claude (구현) | dev-claude | `api/app.py`·`ingest_router.py` 삭제, 테스트·import의 네이티브 ASGI 클라이언트 전환, 중복 replay 제거, 삭제 전 golden 캡처 |
| 검토자 `gpt-6.1-sol` | — | 독립 검토(사전 스풀링 본문 상한 회귀 발견), 최종 golden+runtime 재검토 |
| 문서 담당 (Claude) | main-2 (dev) | 이 문서, Obsidian 작업기록·RG-701 백로그 상태 (Obsidian 단독 쓰기) |

## 확인한 원인과 근거

### 1) legacy 비교 기준의 대체 — golden 캡처

- 삭제 전 캡처: `tests/fixtures/drf_parity_golden.json`, SHA-256 `5e57bf73f4e6106ac3e1f88a7e778e48ee723f31b3fcf6ea2eb4169777f2d6de`(145,098 bytes). `_meta.source`: "Legacy FastAPI create_app responses recorded by the RG-701 parity suite immediately before the FastAPI adapter was removed (dev-codex bc643ee working tree, 2026-10-20)".
- 구성: **HTTP 응답 273건 + ingest store-call 10건 = 캡처 기록 283건.** 테스트별 응답 수는 공개 API 7개 테스트 23·4·51·22·18·72·13, 정적 자산 35, ingest 33·2.
  - **정정 이력**: 초기 전달 문구 "응답 283 + store-call 10"은 부정확했다. 문서 담당이 파일 구조를 세어 질의했고 Root가 직접 재집계해 273 + 10으로 확인했다. 통합 산출물 `integrated-api.json`도 `response_records: 273`, `store_records: 10`이다.
- 통합 후 golden SHA는 dev-claude 캡처본과 dev-codex 정식본이 **동일**하다(문서 담당 `shasum` 확인, `integrated-api.json`의 `golden_sha256`과 일치). golden은 재생성하지 않았다.
- 의도한 변경 1건: 문서 페이지(docs/redoc) 두 곳의 favicon 기대 URL을 로컬 경로로 바꾼 docs/favicon 한정 변경(Root 전달). golden을 다시 만들지 않고 해당 기대값만 의도적으로 로컬로 둔다. 전체 테스트는 이 변경 **전에** 실행됐고, 변경 **후** API golden 테스트 19개(`api-contract-tests.log`: `Ran 19 tests` · `OK`)와 독립 검토자의 최종 golden+runtime 23개가 통과했다(23개는 Root 전달, 로그 미확인).
- 의미: 비교 기준이 실행 중인 Django 자신이 아니라 삭제 전 실제 FastAPI 응답이다. 의도적으로 계약을 바꾸면 golden도 함께 갱신해야 한다.

### 2) 독립 AviList runner의 Django ASGI 이전

- 대상: `scripts/serve_avilist_pipeline.py`(독립 TEST runner, 이전 FastAPI). 이전 원본은 `/tmp/rg701-complete/serve-before.py`, `compose-before.yml`로 보존(문서 담당 파일 존재 확인).
- runner mock 테스트 **33개** 통과 — 앱별 라우트 격리, 허용되지 않은 Host → 400, 이전 코드 fingerprint 승인 → 409, 새 Django ASGI 코드 fingerprint 바인딩, 실제 스트림 본문 64/65 경계·multi-chunk·잘못된 Content-Length, 인증 실패 시 본문 0바이트 읽기.
- Root 로그(문서 담당 읽기, 모두 `OK`): initial 26 → 30 → bounded 30 → stream 33 → native-client 33, 최종 `runner-tests.log` 33 실행(0.655초). 로그의 `409`(review_required·approval_missing·busy·approval_rejected·gate_failed·package_missing)·`500`(internal_error)은 의도된 거부·오류 사례다. 종류: **mock**.
- FastAPI·Starlette가 **설치되지 않은** clean venv에서도 runner mock 33개 실패 0(Root 보고).

### 3) 의존성 제거

- dev-codex `pyproject.toml`에 `fastapi`·`starlette` 없음, `uv.lock`에 `name = "fastapi"`·`"starlette"` 패키지 항목 0(문서 담당 grep). `django`·`djangorestframework`·`httpx2` 사용.
- 새 TEST 이미지 패키지 검사 `image-packages.json` = `{"fastapi": true, "starlette": true}`. **값 `true`는 "없음"(`importlib.util.find_spec(...) is None`)을 뜻한다**(Root 회신으로 확인). runner 갱신 산출물도 `legacy_packages_absent: true`.

### 4) 독립 검토에서 발견한 회귀와 조치

- 검토자 `gpt-6.1-sol`: 초기 Django runner 이전본에 **사전 스풀링 본문 상한 회귀** — 413을 반환하기 전에 본문 **12,288바이트를 이미 읽었다**.
- 조치(Root): ASGI `receive` 단계에서 본문 상한 적용. 독립 raw ASGI 사례 **8건** 통과, 검토자 targeted 검사 **15건** 통과, **남은 설계 차단 사항 없음**(Root 보고, 로컬 검사). runner 테스트의 64/65·multi-chunk·잘못된 Content-Length·인증 실패 0바이트가 회귀 테스트다.

### 5) runner 승인 바인딩 가드(코드 fingerprint) 갱신 — TEST 실제 실행

가드를 끄지 않고, 검토된 계획대로 실행했다(`runner-upgrade.json`, `state: verified`, `production_changed: false`).

| 단계 | 실제 결과 |
|---|---|
| 기준 probe (교체 전) | HTTP 200 `verified`, verify 단계, 검색 회귀 4건, projection 없음 |
| 이전 바인딩으로 새 코드 실행 | **HTTP 409 `code_changed`** (verify 단계, projection 없음) — 가드 작동 확인 |
| 고정 원본 재수집 | `source_refetched: true`, `package_byte_identical: true`, 고정 원본 SHA-256 `3b08845b…f132411` |
| manifest·bundle | 전후 동일: manifest `efa03d4ee4bdc19780c3a83ed994a6faf5637f814a82fe42c3b2640a4b29913f`, bundle `859192488fb24952e509937249351a5daf2266709f3326ecd20259e2a6b44cc3` |
| fingerprint 변화 | builder·core·runner 동일, service `7f8f0722…` → `dd2fc907…`, `django_asgi` `986eae57…` 신규 |
| 새 검토 바인딩 | 에이전트 검토(`reviewer_type: agent`), `reviewed_at` 2026-10-20T07:46:24Z, 검토 대상 transport fingerprint(service·django_asgi)를 승인 스키마와 분리된 영수증으로 기록(Root 전달). 서비스 정지 상태에서 바인딩 변경 |
| 새 바인딩 probe | **HTTP 200 `verified`**, 검색 회귀 4건, projection 없음 |

- 백업 디렉터리 `…/n8n-avilist-test/backups/django-only-0e15293544bb-96aaf6`, 새 코드 디렉터리 `…/code-releases/django-only-0e15293544bb`(TEST Mac 경로).
- runner 컨테이너의 이전 이미지는 `robingraph-api:test-rg406-outside-spelling-1c7cbbdaf1c7`(`sha256:44005f68…`)였고 새 이미지 ID는 `sha256:5b70ec99…68349`이다.
- **승인 주체 구분**: 새 바인딩은 독립 검토된 코드에 대한 **새 에이전트 승인**이며 **사람(human) 승인이 아니다**(Root 명시). 검토자는 최종 운영 스크립트(`upgrade-runner.py`, SHA-256 `6ba116460f86231a952e0646bca6a6fa1337ef8640f1f7f77158ccfd2cd1ed36` — 문서 담당 `shasum` 일치)를 정적 검토해 수락했고 targeted 23건이 통과한 뒤 해제됐다.
- 바인딩 갱신 뒤 실제 TEST runner 보호 장치 4건(`runner-live-guards.json`, `mocked: false`): Bearer 없음 → 401, 유효 Bearer + 65바이트 본문 → 413, runner에서 공개 API `/v1/search` → 404(앱 격리), 신뢰하지 않는 Host → 400. DB 쓰기 없음.

## 변경 전후 동작

| 항목 | 변경 전 (1차 전환 후) | 변경 후 (이번 후속) |
|---|---|---|
| 공개·내부 API 런타임 | 네이티브 Django + DRF | 동일 |
| FastAPI legacy 어댑터 | 비교 기준으로 존재 | 정식 소스에서 삭제 |
| 계약 비교 | 로컬 FastAPI ↔ Django 실제 소켓 95사례 + legacy 스위트 replay(242) | 삭제 전 FastAPI 응답 golden 273 + store-call 10, replay 제거(`test_drf_legacy_suite.py` 삭제) |
| 테스트 클라이언트 | FastAPI `TestClient` | 네이티브 HTTPX ASGI 도우미 (`tests/asgi_client.py`) |
| 독립 AviList runner | FastAPI | Django ASGI, TEST 실제 교체·`verified` |
| runner 본문 상한 | — | ASGI `receive` 단계에서 적용 |
| 의존성·이미지 | `fastapi` 설치(런타임 미import) | lock·이미지 모두 FastAPI·Starlette 없음 |
| 문서 페이지 favicon | 기존 URL | 로컬 경로 (의도된 변경) |
| Django DB·마이그레이션 | 없음 | 없음 |
| core/source/bundle 정책 | TEST 전용 | TEST 전용 유지, manifest·bundle 해시 불변 |

## 변경 파일과 구현 내용

모두 **미커밋** 작업 트리다. 이미지에 들어간 전체 소스는 `test-release.json`의 파일별 SHA-256(183개)으로 고정돼 있다.

- 정식 소스 통합(dev-codex, `integrated-api.json` 기준)
  - 삭제: `src/robingraph/api/app.py`, `src/robingraph/api/ingest_router.py`, `tests/test_drf_legacy_suite.py`.
  - dev-claude에서 반영: `src/robingraph/api/services.py`, `schemas.py`, `ingest_service.py`, `drf/application.py`, `scripts/evaluate_jev_intents.py`, `tests/asgi_client.py`, `tests/fixtures/drf_parity_golden.json`, `tests/test_drf_parity.py`, `tests/test_django_runtime.py`, `tests/test_api.py`, `test_ecological_relations.py`, `test_entity_resolution_api.py`, `test_favicon.py`, `test_ingest_api.py`, `test_jev_router.py`, `test_mlflow_response_tags.py`, `test_mlflow_tracing.py`, `test_name_relations.py`, `test_name_relations_integration.py`, `test_related_species.py`, `test_semantic_chat.py`, `test_search_cli.py`, `test_similar_species.py`, `test_similar_species_korean_priority.py`, `test_species_profile.py`, `test_species_questions.py`, `test_species_scope_api.py`, `test_subspecies.py`.
- Root(dev-codex): `scripts/serve_avilist_pipeline.py`(Django ASGI), runner 테스트, `pyproject.toml`·`uv.lock`, 배포·갱신 도구(`deploy-test.py`, `upgrade-runner.py` — 증거 폴더에 보존).
- main-2(문서 담당): `docs/work-log/2026-10-20-rg701-django-only.md`(이 문서, 신규). 다른 기록은 수정하지 않았다.

## 검증 방법과 실제 결과

| 구분 | 결과 | 종류 | 근거 |
|---|---|---|---|
| Python 전체 (clean 환경) | 1,029 실행 · 991 통과 · 38 건너뜀 · 0 실패 (22.324초) | 오프라인 fixture/mock, 외부 통합 opt-in 건너뜀 | `python-tests.log` (`OK (skipped=38)` 확인) |
| 프런트엔드 Node | 317 통과 · 0 실패 · 0 건너뜀 | mock | `frontend-tests.log` |
| favicon 변경 후 API golden | 19 통과 | fixture | `api-contract-tests.log` |
| 독립 검토자 최종 golden+runtime | 23 통과 | 로컬 | Root 전달 |
| runner mock | 33 통과 (clean venv에서도 0 실패) | mock | `runner-tests.log` |
| 본문 상한 raw / targeted | 8 / 15 통과, 설계 차단 없음 | 로컬 | Root 전달 |
| golden 무결성 | SHA 불변, 응답 273 + store-call 10, 재생성 없음 | fixture | `integrated-api.json`, 문서 담당 `shasum` |
| 이미지 패키지 | FastAPI·Starlette 없음 | 실제 이미지 | `image-packages.json` (true = 없음) |
| 공개 앱 TEST 배포 | release `state: verified`, 격리 fixture smoke(`--network none`) 통과 | **실제 TEST** | `test-release.json` |
| 배포 계약 검사 | health·OpenAPI·`청둥오리` lineage 200, schema/response drift 없음, `contract_parity_ok` | **실제 TEST API** | `deployment-verification.json` |
| 실제 TEST API | 5/5: Kea outside·all → answer, Keaa outside → clarify, Anas platyrhynchos korea → answer, lineage | **실제 TEST DB/API** | `live-api.json` |
| 공개 브라우저 | Chromium 1280·390·320 × 2질의 = 6 통과, page error 0, 응답 mocking 없음, 스크린샷 3장 | **실제 공개 TEST URL**, 물리 기기 아님 | `browser.json`, `django-{1280,390,320}.png` |
| runner 코드 바인딩 갱신 | 409 `code_changed` → 재수집 동일 → 재검토 바인딩 → 200 `verified`·검색 회귀 4 | **실제 TEST runner** | `runner-upgrade.json` |
| TEST DB 기준선(변경 전) | 이름 벡터 855, 카탈로그 fingerprint `a96ed6f8…19f4c1`, 기타 파이프라인 해시 `5a5eee35…1a866b`, 파일럿 `succeeded` 1건 | **실제 TEST DB 읽기** | `db-before.json` |
| 런타임 증명 | 두 컨테이너(`robingraph-api-test`, `robingraph-avilist-runner-test`) 모두 같은 이미지 `sha256:5b70ec99…68349`, healthy, 네이티브 Django ASGI(`DjangoApiApplication` / runner `PipelineApplication`), FastAPI·Starlette 없음 | **실제 TEST 컨테이너** | `runtime-proof.json` |
| runner 실제 보호 장치 | 4/4: 401·413(65바이트)·404 격리·400 Host, DB 쓰기 없음 | **실제 TEST runner** | `runner-live-guards.json` |
| 실제 n8n 실행 | CLI exit 0, 7노드 전체(Manual → Prepare → Check → Verify → Check → Apply → Check), prepare `prepared`·`reused`, verify `verified`·검색 회귀 4, apply `already_applied`(기존 run `avilist-pilot-cdf8b630-…`), projection 없음, 오류 없음 | **실제 n8n TEST** | `django-only-n8n.json` |
| TEST DB 사후 동일성 | `db-before.json` = `db-after.json` 바이트 동일(문서 담당 `cmp` 확인), `unchanged: true`, 이름 벡터 855 | **실제 TEST DB 읽기 전용 스냅샷** | `db-comparison.json` |
| 롤백 운영 스크립트 mock | 7/7 (success·stop 실패(실행 중/정지)·inspect 실패·승인 복원 실패·감사 실패·잘못된 이미지 → `rolled_back`/`rollback_unverified` 기대 상태) | **mock** (격리 AST, 실제 Docker·DB·롤백 없음) | `operator-rollback-mocks.json` |
| `django check` | 문제 없음 | 정적 | `django-check.log` |
| graphify update | 6,611 nodes · 14,142 edges · 401 communities | — | `graphify-update.log` |

- lineage 검사의 health `taxonomy_release`(`fixture-avlist-2025`)와 lineage 릴리스(`v2025b`)가 다른 것은 서로 다른 데이터 영역이라 정상이라고 검증기가 기록했다(1차와 같음).
- 실행 수 변화: 1차 최종 1,262 → 1,029. legacy 스위트 네이티브 재실행(replay)과 FastAPI 비교 테스트를 golden 기반 테스트로 대체한 결과다(Root 전달 · 세부 차이는 문서 담당이 대조하지 않았다).
- 건너뜀 38건: 외부 통합 opt-in 검사(실제 DB 등). 이번에 다시 켜지 않았다.

### 재현 명령 (실제 사용한 명령의 기록)

아래는 이번 증거를 만든 **당시 명령의 기록**이며, 그대로 다시 실행하라는 지시가 아니다. 특히 `deploy-test.py`·`upgrade-runner.py` 등 운영 스크립트는 일회성 보호 장치(이전 바인딩 409 확인, 바인딩 원자 갱신)를 포함하므로 맹목적으로 재실행하지 않는다. 운영·증명·mock 스크립트 원본은 증거 폴더에 보존돼 있다.

```sh
# 오프라인 전체 (clean venv: FastAPI·Starlette 미설치)
PYTHONPATH=tests /tmp/rg701-complete/venv/bin/python -m unittest discover -s tests -q
node --test tests/frontend/*.test.js
# favicon 변경 후 API golden / 검토자 golden+runtime
PYTHONPATH=tests /tmp/rg701-complete/venv/bin/python -m unittest test_drf_parity -q
PYTHONPATH=tests /tmp/rg701-complete/venv/bin/python -m unittest test_drf_parity test_django_runtime -q
# TEST 배포·runner 바인딩 갱신 (일회성 운영 스크립트)
python3 /tmp/rg701-complete/deploy-test.py
python3 /tmp/rg701-complete/upgrade-runner.py
# 실제 검증
node docs/verification/assets/2026-10-20-rg701-complete/browser.cjs
python3 /tmp/rg701-complete/execute-n8n.py django-only-n8n
python3 /tmp/rg701-complete/runtime-proof.py
python3 /tmp/rg701-complete/snapshot-after.py
python3 /tmp/rg701-complete/runner-live-guards.py
python3 /tmp/rg701-complete/test-operator-rollback.py
graphify update .
```

- 명령은 Root가 전달한 형태이며 검토자 명령의 인터프리터 경로는 Root 전달 기준으로 같은 venv로 적었다(문서 담당 재실행 없음). 인증 값은 기록하지 않는다. 로컬 개발 환경에서도 `uv sync`로 FastAPI가 제거됐다(Root 전달).

### 중간 실패·정정 (숨기지 않고 기록)

- 초기 Django runner의 사전 스풀링 본문 상한 회귀(위 4) — 수정 후 재검증 통과.
- golden 집계 문구 오류(283 응답 → 273 응답 + 10 store-call) — Root 재집계로 정정.
- 전체 테스트는 docs/favicon 변경 전 실행이며, 변경 후에는 API golden 19·검토자 23으로 확인했다(전체 재실행 아님).

## TEST 배포와 롤백

| 항목 | 값 |
|---|---|
| 대상 | TEST — M4 16GB Mac 앱(`https://robingraph-test.dove-nest.com`, NAS 프록시 → Mac:8000)과 독립 AviList TEST runner |
| 새 이미지 | `robingraph-api:test-rg701-django-only-0e15293544bb` (`sha256:5b70ec99…68349`) |
| 소스 해시 | `0e15293544bb20ca862e04201d5be40bbeab56e7a31a36851b6aec4f4c144718` (미커밋 소스 스냅샷, 기준 HEAD `bc643ee9edef0fc58c605adde70b4808b7622ac5`) |
| 새 release | `/Users/kimdove/robingraph-test/releases/rg701-django-only-0e15293544bb-3d3455` (`state: verified`) |
| 공개 앱 이전 이미지·release (롤백 기준) | `robingraph-api:test-rg701-django-34f84c494c6a`, `…/releases/rg701-django-34f84c494c6a-4f4628` |
| runner 이전 이미지·백업 | `robingraph-api:test-rg406-outside-spelling-1c7cbbdaf1c7`, 백업 `…/backups/django-only-0e15293544bb-96aaf6` |
| 롤백 | 이전 이미지·release·runner 백업 보존. 운영 롤백 스크립트는 mock 7건만 통과. **실제 롤백·실제 장애 주입은 실행하지 않았다.** |
| 변경하지 않은 것 | TEST DB·Neo4j·n8n 위치, DB 스키마, 이름 벡터, manifest·bundle·고정 원본, Jenkins job, Production |

- **1차 TEST 이미지 상태의 대체**: 1차 이미지(`test-rg701-django-34f84c494c6a`)는 런타임에서 FastAPI를 import하지 않았지만 `fastapi`가 **설치되어 있었다**. Root 확인에 따라 이 FastAPI 설치 이미지는 활성 TEST 컨테이너 두 곳(공개 앱·runner) 모두에서 새 이미지로 **대체(superseded)**되었다. 1차 이미지는 롤백 기준 이력으로 보존된다. 1차 기록 본문은 바꾸지 않았다.

## 배포·커밋 정보

- TEST: 위 이미지로 공개 앱·runner 교체, 실제 API·브라우저·runner 바인딩·보호 장치·n8n·DB 사후 동일성 검증 완료(`summary.json`).
- Production: **변경 없음**(`production_changed: false`). 이번 사용자 요청은 Production 승인이 아니다.
- commit/push: 없음(`commit_push_performed: false`, 승인되지 않음). Jenkins job 실행 없음. AMD64 이미지 빌드 없음.

## 남은 한계와 후속 사항

- **Production 승인 대기**: TEST 최종 증거 후 사용자 명시 승인 필요. 운영 반영 시 운영용(AMD64 포함) 이미지, 운영 승인 gate, 운영 검증이 별도로 필요하다. RG-701은 그때까지 진행 중이다.
- golden은 고정 기준이므로 의도된 API 변경 시 갱신 절차가 필요하다.
- 전체 테스트 이후의 docs/favicon 변경은 부분 재검사(19·23)만 했다.
- **미검증**: 물리 모바일·Safari·Firefox, 물리 재부팅, AMD64 이미지, 실제 롤백·실제 장애 주입, 건너뛴 실제 DB 통합 테스트 38건, 네이티브 내부 ingest의 실제 DB 쓰기.
- runner 바인딩은 에이전트 승인이다. 사람 검토가 필요하다고 판단되면 별도로 요청한다.
- **미커밋**: TEST 이미지는 미커밋 소스 스냅샷이다. 커밋 시 `test-release.json`의 파일 해시와 대조해야 한다.

## Obsidian 동기화와 재조회

- 대상(문서 담당 단독 쓰기): 신규 `Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-Django-단독-전환.md`, `Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그.md`, `Work/RobinGraph/RobinGraph 작업 백로그.md`, `Work/RobinGraph/작업기록/index.md`.
- 초안 동기화(2026-10-20, Obsidian MCP): 신규 작업기록 생성, 7xx 백로그 작업 현황 첫 항목·RG-701 상태 문장·결과 기록 링크·작업기록 목록 추가. 전체 백로그 카테고리 표 7xx 작업기록 15 → 16, 카테고리별 보기·현황표 상태 문구, 진행 중 작업 안내·RG-701 안내 절 후속 문단·변경 이력 최상단 항목 추가. 작업기록 index 7xx 15 → 16. 재조회로 반영 문구를 확인했다.
- 최종 동기화(2026-10-20, Obsidian MCP): 작업기록 노트를 이 문서와 같은 본문(요약~남은 한계)으로 갱신하고 상태 callout을 "TEST 배포·실제 검증 완료, Production 승인 대기"로 바꿨다(`status: in-progress` 유지). 7xx 백로그 작업 현황 첫 항목·RG-701 상태 문장·작업기록 링크 제목, 전체 백로그 카테고리별 보기·현황표·진행 중 안내·RG-701 안내 절 후속 문단(최종 결과 선두 추가)·변경 이력 최상단(최종 항목 신규, 초안 항목은 이력으로 유지)을 최종 결과로 갱신했다.
- 저장 후 재조회: 작업기록 노트 전체 재조회 215줄 — n8n·DB·런타임 증명·보호 장치·롤백 mock 행, 재현 명령 절, 에이전트 승인(사람 승인 아님) 문구, 1차 이미지 대체 문구 확인. 볼트 전체 본문 검색 `"증거 대기"` 결과 0건(대기 문구 잔존 없음). 7xx 백로그·전체 백로그 RG-701 행 문구를 재조회로 확인했다.
- 1차 이미지(FastAPI 설치) 상태의 "대체" 표시는 새 작업기록에만 두었고 1차 기록 본문은 수정하지 않았다.
- 보존: 1차 구현 기록·등록 기록 본문, 기존 변경 이력 항목, 담당 배정 표, RG-406·RG-101 등 다른 작업 상태는 수정하지 않았다. 링크는 텍스트로 대조했고 Obsidian 화면 클릭 검증은 하지 않았다.
- 참고: 볼트 검색에서 `Dev/자동화/초안-RG701-Django-단독-전환.md` 등 "자동 증류 초안" 노트가 보인다. 문서 담당이 만들지 않았고(별도 자동화로 보임) 수정하지 않았다.
