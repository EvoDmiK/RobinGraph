# RG-701 FastAPI → Django + Django REST Framework 전환 백로그 등록 — 2026-10-20

## 요약

- 작업 ID: **RG-701** (7xx 배포·인프라, 7xx의 첫 등록 작업)
- 우선순위: **1 (최우선 · 다음 착수 1순위)** — 이 백로그에서 P0 표기를 쓰지 않으므로 숫자 순위 1로 표기했다.
- 상태: **계획 (백로그 등록 · 미착수)** — 구현·진행 중이 아니다.
- 이번 작업 범위: 문서 작업(저장소 작업 기록 + Obsidian 백로그·작업기록 등록)만 수행했다. 전환 구현은 하지 않았다.

## 요청 배경과 목표

- 사용자가 Orca 코디네이터를 통해 "FastAPI에서 Django + Django REST Framework(DRF)로의 전환"을 RobinGraph 백로그의 최우선 작업으로 추가하도록 요청했다.
- 목표: 기존 백로그에 일치하는 항목이 있으면 재사용하고, 없으면 현재 카테고리 체계에 맞는 고유 RG ID를 부여한다. 최우선 순위·다음 착수 1순위·계획 상태로 등록하고, 배경·목표·단계별 하위 작업·완료 기준을 작성한다.
- 사용자는 백로그 등록만 요청했다. 전환 구현·서비스 재시작·DB 변경·운영 배포·commit/push는 이번 범위가 아니다.

## 확인한 근거

### 기존 백로그 중복 확인

- Obsidian `Work/RobinGraph/RobinGraph 작업 백로그.md` 전체를 읽었다. 등록 ID는 101·102·201·202·301·401~406·501~505·601·602이며 프레임워크 전환 항목은 없다.
- 볼트 전체 본문 검색(`Django OR DRF OR "REST Framework"`) 결과는 `Private/인프라/` 노트 2건(홈 인프라 구성 목록)뿐이며 RobinGraph 작업 항목이 아니다. 따라서 재사용할 항목이 없어 새 ID를 부여했다.

### ID와 카테고리 선택

- ID 체계: 첫 자리가 카테고리, 뒤 두 자리가 카테고리 내 등록 순번이다. 7xx·8xx·9xx는 등록 작업이 없었다.
- 7xx 배포·인프라(NAS·Docker·CI·환경 설정)를 주 카테고리로 정했다. 이 전환은 서버 런타임 프레임워크·의존성·Docker 실행 명령·CLI `serve`·Jenkins 파이프라인·TEST 통합과 롤백을 함께 바꾸므로 가장 큰 변경이 런타임·배포 쪽에서 일어난다고 판단했다. 운영 규칙("여러 카테고리에 걸치면 가장 큰 변경이 일어나는 쪽")에 따른 판단이며, 상세에 관련 카테고리(1xx·2xx·3xx·4xx·6xx·8xx)를 적었다.
- 7xx의 다음 번호는 701이다(기존 7xx 등록 작업 없음). ID 중복 없음.

### 현재 구현 확인 (main-2 워크트리 `07b1cf8` 기준, 읽기 전용)

- `pyproject.toml` 의존성: `fastapi>=0.115,<1`, `uvicorn[standard]>=0.30,<1`, `neo4j>=6,<7`, `psycopg[binary]>=3.2,<4`, `langchain-core`. 테스트 extra `httpx2`.
- `src/robingraph/api/app.py`(1,624줄)에 라우트와 채팅 오케스트레이션·응답 매핑이 함께 있다. 확인한 공개 라우트:
  - `POST /v1/answers`, `POST /v1/chat`, `POST /v1/search`, `GET /v1/observations`, `GET /v1/taxa/lineage`
  - `GET /v1/taxa/name-relations`, `/v1/taxa/related`, `/v1/taxa/similar`, `/v1/taxa/ecological-related`, `/v1/taxa/subspecies`, `/v1/taxa/profile`
  - `GET /health`, 정적·화면 경로 `/`, `/chat`, `/birds`, `/favicon.ico`, `/static/{asset_path:path}`
- `src/robingraph/api/ingest_router.py`: `APIRouter(prefix="/internal/v1/ingest", dependencies=[Depends(require_internal_bearer)])` 아래 `GET /active/{pipeline_id}`, `POST /begin`, `POST /{run_id}/append`, `/finalize`, `/fail`. Pydantic `response_model` 사용.
- 그 밖의 API 모듈: `jev_router.py`, `semantic_router.py`, `question_entities.py`(질문 라우팅 계층; 이름에 router가 있으나 HTTP 라우터인지는 이번에 확인하지 않았다).
- `src/robingraph/cli.py`가 `uvicorn.run("robingraph.api.app:app", ...)`로 서버를 띄우고, `Dockerfile` CMD는 `robingraph serve-fixture --host 0.0.0.0 --port 8000`, HEALTHCHECK는 `/health`이다.
- PostgreSQL: `src/robingraph/ingest/postgres.py`가 자체 `_schema_migration` 테이블과 `src/robingraph/ingest/migrations/0001~0004_*.sql`로 스키마를 관리한다. 따라서 Django 마이그레이션(auth/admin/contenttypes/sessions)과 이 테이블을 분리해야 한다.
- n8n 워크플로(`n8n/*.json`)는 내부 ingest 경로(`/internal/v1/ingest/begin`, `/internal/v1/ingest/active/reference-taxonomy-traits` 등)를 호출한다(외부 GBIF `.../v1/occurrence/search` 호출은 RobinGraph API가 아님). 전환 시 n8n 호환 검증이 필요하다.
- `tests/` 72개 파일 중 17개가 `TestClient` 또는 `fastapi`를 참조한다(`grep -l` 결과).
- Jenkins: `docs/jenkins-deployment.md`에 기본 `Jenkinsfile`·`ci/Jenkinsfile.production`(RobinGraph-PROD)·`ci/Jenkinsfile.test`가 기록되어 있다. main-2 워크트리에는 해당 Jenkinsfile이 없어 파일 내용은 확인하지 않았다.
- graphify: main-2에는 `graphify-out/`이 없어 graphify query를 사용하지 못하고 원문을 직접 읽었다.

이 확인은 **예비 분석**이다. 전체 전환 설계를 검증한 결과가 아니며, 엔드포인트별 응답·오류 형식의 전수 목록과 비동기·스트리밍 사용 여부는 착수 시 다시 확인해야 한다.

## 등록한 백로그 항목 (RG-701)

### 배경

- 현재 API는 FastAPI/Pydantic + uvicorn 기반이며, 검색(retrieval)·수집(ingest) 모듈은 프레임워크와 별도 Python 모듈로 존재한다.
- 사용자 요청으로 Django + DRF로 웹 계층을 전환한다. 성능 향상은 목표나 약속이 아니다.

### 목표

- 기존 공개·내부 API URL과 응답·오류 계약(필드·상태 코드·오류 본문)을 유지한 채 웹 프레임워크를 Django + DRF로 바꾼다.
- 조류 근거·데이터와 Neo4j 검색 로직을 그대로 재사용하고, 프레임워크와 무관한 서비스 계층을 만든다.

### 단계별 하위 작업

1. **계약 고정**: 현재 FastAPI 엔드포인트 전수 목록과 요청·응답·오류 계약(OpenAPI 스냅샷, 기존 테스트)을 기준선으로 고정한다.
2. **서비스 추출**: `src/robingraph/api/app.py`의 채팅 오케스트레이션·응답 매핑을 프레임워크 독립 서비스 모듈로 추출한다. FastAPI에서 먼저 동작을 유지하며 리팩터링한다.
3. **Django + DRF 골격**: 프로젝트 설정, URL·View·Serializer 계층을 추가한다. Serializer는 기존 Pydantic 계약과 같은 JSON을 내야 한다.
4. **데이터 계층 유지**: Neo4j 드라이버·검색·벡터 코드와 조류 근거·데이터를 그대로 사용한다. 기존 PostgreSQL SQL·스키마(`ingest/migrations`, `_schema_migration`)는 초기에는 그대로 두고, Django auth/admin 등 Django 자체 마이그레이션과 명시적으로 분리한다(별도 스키마·DB 또는 미사용 결정 포함).
5. **엔드포인트 이전 순서**: 조회(query: `/v1/taxa/*`, `/v1/search`, `/v1/observations`, `/health`) → 채팅(`/v1/chat`, `/v1/answers`) → 수집(`/internal/v1/ingest/*`, 내부 Bearer 인증 유지).
6. **정적 UI 재사용**: `src/robingraph/api/static/`과 `/`, `/chat`, `/birds`, `/favicon.ico`, `/static/...` 경로를 그대로 제공한다.
7. **실행·배포 갱신**: 테스트(`TestClient` 의존 17개 파일 포함), Dockerfile·HEALTHCHECK, CLI `serve`/`serve-fixture`, Jenkins 파이프라인, ASGI/WSGI 런타임을 갱신한다.
8. **TEST 통합·롤백**: TEST(M4 16GB Mac)에서 API 통합·브라우저·n8n ingest 호환 검증과 롤백 계획(이전 이미지·release 복귀)을 확인한다. Production은 사용자의 별도 명시 승인 후에만 진행한다.

### 완료 기준

- 기존 API URL과 응답·오류 계약이 기준선 스냅샷·계약 테스트와 일치한다.
- 채팅 오케스트레이션·응답 매핑이 프레임워크 독립 서비스로 분리되어 있다.
- Neo4j 검색·벡터 코드와 조류 근거·데이터가 바뀌지 않았다.
- 기존 PG 스키마·SQL 마이그레이션이 유지되고 Django 마이그레이션과 분리되어 있다.
- query → chat → ingest 순서로 이전되고 각 단계가 검증되었다.
- 정적 UI가 같은 경로에서 동작한다.
- 테스트·Docker·CLI·Jenkins·런타임이 갱신되었다.
- TEST에서 통합·브라우저·n8n 호환 검증과 롤백 계획을 확인했다. Production 반영은 별도 승인 후 진행한다.
- 성능 향상은 완료 기준이 아니며 약속하지 않는다. 성능 비교가 필요하면 별도 측정으로 기록한다.

### 비포함 범위 (이번 등록 작업)

- 전환 구현, 서비스 재시작, DB 쓰기·스키마 변경, TEST/Production 배포, commit/push/병합.

## 변경 전후

- 변경 전: 7xx 등록 작업 없음. 다음 착수 대기 표에는 RG-406(후속 대기)·RG-101(보류)만 있었다.
- 변경 후: RG-701을 최우선(1)·계획 상태로 추가하고 다음 착수 대기 표 맨 위에 넣었다. RG-406(우선순위 5, 상태 문구)·RG-101(보류)과 최후순위 보류 4건, 완료 항목은 바꾸지 않았다.

## 변경 파일

### 저장소 (main-2 워크트리)

- `docs/work-log/2026-10-20-django-drf-migration-backlog.md` (이 문서, 신규)
- 앱 코드·테스트·환경 설정·다른 워크트리 변경 없음.

### Obsidian

- `Work/RobinGraph/RobinGraph 작업 백로그.md`: 카테고리 표 7xx 수치, 카테고리별 보기 표에 701 행, 현황 대시보드 표 맨 위 RG-701 행, 신규 착수 대기 설명·표 맨 위 RG-701, `### RG-701` 안내 절, 7xx 안내 문장, 변경 이력 항목, frontmatter `updated`.
- `Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그.md`: 작업 현황 첫 항목, `### RG-701` 상세, 작업기록 링크, `updated`.
- `Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-FastAPI-Django-DRF-전환-백로그등록.md` (신규 작업기록)
- `Work/RobinGraph/작업기록/index.md`: 7xx 작업기록 수, `updated`.

## 검증 방법과 결과

- 저장 후 Obsidian 각 파일을 다시 읽어 RG-701 항목·우선순위·상태·링크와 RG-101·RG-406 기존 문구 보존을 확인했다(결과는 아래 "재조회 결과"에 기록).
- 코드 테스트·실제 DB/API·브라우저 검증은 해당 없음: 문서만 변경했고 앱 코드를 바꾸지 않았다.

### 재조회 결과

2026-10-20 Obsidian MCP로 저장 후 다시 읽어 확인했다.

- `Work/RobinGraph/RobinGraph 작업 백로그.md` (444 → 457줄, `updated: 2026-10-20`): 카테고리 표 7xx `1 | 14`, 카테고리별 보기 `**701** | — | … | 계획 (최우선 1 · 미착수)`, 현황 대시보드 첫 행 `RG-701 | 계획 (미착수) | 1 (최우선)`, 신규 착수 대기 표 첫 행 `1 (최우선) | RG-701 …`, `### RG-701` 안내 절, 2026-10-20 변경 이력 항목이 있다. RG-406 행(`… 운영 배포 대기 | 5 |`)·RG-101 행(`보류 (소규모 기준선 완료 · 실제 문헌 축적 후 재개) | 보류`)과 각 상세 절, 최후순위 보류 4건, 완료 항목·변경 이력은 원문대로 남아 있다.
- `Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그.md` (71줄): 작업 현황 첫 항목, `### RG-701` 상세(상태·우선순위·배경·단계 1~8·완료 기준·범위 밖·착수 시 확인·결과 기록 링크), 작업기록 목록 첫 링크를 확인했다. 기존 2026-10-17·18 항목은 원문대로다.
- `Work/RobinGraph/작업기록/index.md`: 7xx 작업기록 수 `14`(폴더 실제 작업기록 13개 + 신규 1개). 이전 값 `8`은 갱신되지 않은 수치였다.
- `Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-FastAPI-Django-DRF-전환-백로그등록.md` (76줄): 생성과 요약(ID·우선순위·상태)을 확인했다.
- Obsidian 앱 화면에서 링크를 직접 눌러 보는 검증은 하지 않았다. 위키링크 앵커는 대상 제목 문자열과 같은지 텍스트로 대조했다.

## 배포·커밋 정보

- 배포 없음(문서 작업). commit/push 없음. Root(Codex)가 이 로컬 기록을 검토 후 복사한다.

## 남은 한계와 후속 사항

- 위 현재 구현 확인은 예비 분석이며 전체 전환 설계를 검증한 것이 아니다. 착수 시 엔드포인트 전수 계약, 비동기 처리·스트리밍 여부, Pydantic 모델 수와 Serializer 대응, ASGI/WSGI 선택, Django 설정·비밀값 관리, Jenkinsfile 실제 내용을 확인한다.
- Django 마이그레이션 대상 DB·스키마 분리 방식은 착수 시 결정한다.
- 카테고리(7xx) 선택은 문서 담당의 판단이며 Codex 검토에서 바뀔 수 있다.
- 담당 에이전트·모델: 최초 등록 시점에는 미지정(착수 시 Codex 배정)이었다. 이 기록은 당시 이력이며 아래 2026-10-20 사전 배정으로 대체되었다.

## 담당 에이전트·모델 사전 배정 (2026-10-20 추가)

- 요청: 사용자가 Orca 코디네이터를 통해 RG-701의 담당 에이전트와 모델을 미리 배정하도록 요청했고, 코디네이터가 아래 배정을 승인해 전달했다. 문서 담당이 저장소·Obsidian 기록에 반영했다.
- RG-701의 우선순위 1(최우선·다음 착수 1순위)과 상태 계획(미착수)은 바꾸지 않았다. RG-101 보류·RG-406과 다른 항목 상태도 바꾸지 않았다.
- 공통 원칙: Codex와 Claude는 서로의 해당 코드를 독립 검토하고, UI 호환 담당은 소비 화면 검증을 제공하며, 문서 담당은 실제 증거만 기록한다.

"역할"은 작업 책임, "에이전트"는 실행 도구, "계획 모델"은 착수 시 선택할 모델 ID다. 셋은 서로 다른 항목이다.

| 순서 | 단계·범위 | 역할 | 에이전트 | 계획 모델 (정확한 ID) | 워크트리 (브랜치) | 산출물 | 의존·순서 |
|---|---|---|---|---|---|---|---|
| 1 | 단계 1 계약 기준선·아키텍처 결정 | 총괄 책임 (accountable lead) | Codex | `gpt-6.1-sol` | dev-codex | 엔드포인트 요청·응답·오류 계약 기준선, ASGI 등 아키텍처 결정 기록 | 최초 착수 |
| 2 | 단계 2 프레임워크 독립 서비스 추출 | 구현 책임 (implementation lead) | Claude | `claude-opus-5-5` | dev-claude | `app.py` 채팅 오케스트레이션·응답 매핑의 서비스 모듈 (FastAPI 동작 유지) | 1 이후 |
| 3 | 단계 3·4 Django 설정·ASGI 환경·PG 마이그레이션 분리 | 총괄 책임 | Codex | `gpt-6.1-sol` | dev-codex | Django settings·ASGI 런타임, Django 마이그레이션과 기존 `_schema_migration`·ingest SQL 분리 | 1 이후 · 4의 선행 |
| 4 | 단계 5 DRF View·Serializer·URL 어댑터 (query → chat → ingest) | 구현 책임 | Claude | `claude-opus-5-5` | dev-claude | 단계별 DRF 어댑터와 의미 있는 계약 테스트. 내부 Bearer·API 입력 검증·오류 형식·Neo4j 검색·근거 보존 | 2·3 이후, query → chat → ingest 순 |
| 5 | 단계 6 정적 UI·API 소비 호환 | UI 호환 책임 | Codex (UI 역할 범위 유지) | `gpt-6.1-sol` | main (dev-agy) | 정적 경로·API 소비 호환과 키보드·모바일·브라우저 검사 결과. 재디자인·생물학적 판단 없음 | 4의 각 이전 단계 이후 |
| 6 | 단계 7·8 Docker·CLI·Jenkins·TEST 통합·검토 | 총괄 책임 | Codex | `gpt-6.1-sol` | dev-codex | Docker·CLI·Jenkins 갱신, TEST 통합·n8n 호환·롤백 계획, 통합 검토 | 4·5 이후. Production은 사용자 별도 명시 승인 후에만 |
| 상시 | 교차 검토 | 상호 독립 검토 | Codex ↔ Claude | 위와 동일 | dev-codex ↔ dev-claude | 상대가 작성한 해당 코드의 독립 검토 결과 | 각 단계 병합 전 |
| 상시 | 작업 기록 | 문서 담당 (Writer) | Claude | `claude-opus-5-5` | main-2 (dev) | 저장소 작업 기록·Obsidian·백로그, 실제 검증 증거만 정렬·기록 | 각 단계 증거 전달 후 |

- 모든 모델은 **향후 계획 선택**이다. 실행 중 모델 검증이나 설정 변경이 아니다. Root는 기존 dev-claude 세션 모델이 `claude-opus-5-5`임을 확인했다. `gpt-6.1-sol`은 사용 가능한 Codex 계획 모델이며 현재 어떤 세션이 이 모델로 실행 중이라는 주장은 아니다.
- main 워크트리(브랜치 dev-agy)의 제품명은 Antigravity지만 RG-701에서는 Codex를 계획 에이전트로 둔다. 기존 UI 역할 범위는 유지한다. 이는 RG-701 한정 선택이며 공통 AGENTS.md나 실행 중 세션 설정을 바꾸지 않는다.
- 이번 배정으로 구현·다른 에이전트 기동·서비스·DB·배포·commit/push를 시작하지 않았다.

### 배정 반영 파일과 재조회

- 저장소: 이 문서(main-2 워크트리)만 수정했다. dev-codex는 수정하지 않았다(Root가 검토 후 동기화).
- Obsidian: `Work/RobinGraph/RobinGraph 작업 백로그.md`(신규 착수 대기 표 RG-701 담당 칸·RG-701 안내 절·변경 이력), `Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그.md`(작업 현황·RG-701 담당 항목), `Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-FastAPI-Django-DRF-전환-백로그등록.md`(배정 절 추가·최초 미지정 문구 이력 표기).
- 저장 후 각 파일을 다시 읽어 배정 표·우선순위 1·계획(미착수)·RG-101/RG-406 문구 보존을 확인했다. 앱 코드·테스트·DB·배포 검증은 해당 없음(문서만 변경).
