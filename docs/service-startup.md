# RobinGraph 서비스 실행 준비

작성일: 2026-10-14. 현재 공개 서비스 주소는 https://robingraph.dove-nest.com/chat이다. 이 문서는 최신 main을 반영한 dev-codex의 README, Python 설정, CLI, Dockerfile, NAS Compose를 기준으로 작성했다.

## 실행 방식과 필수 구성

| 실행 목적 | 필요한 것 | 제공 범위 |
|---|---|---|
| 로컬 fixture | Git checkout, uv, Python 3.12.13, uv.lock 의존성 | 합성 질문 평가와 채팅 셸. 실제 종 프로필·사진·관계 탐색 준비를 대신하지 않음 |
| 실제 종 서비스 | 위 환경 또는 Docker 이미지, Neo4j, PostgreSQL, 활성 데이터 | 종 이름·프로필·분류·관계·형질 조회 |
| NAS 공개 서비스 | Docker와 Compose, 외부 robingraph-edge 네트워크, 환경 파일, NPM, DNS·TLS | API 컨테이너를 프록시로 공개 |

FastAPI가 HTML·JS·CSS를 함께 제공하므로 별도 프런트엔드 빌드 서버는 필요하지 않다. Node.js는 프런트엔드 회귀 테스트에 사용한다. PostgreSQL은 수집 상태·활성 스냅샷과 분류판 관리에, Neo4j는 종과 근거 관계 조회에 필요하다. Compose는 이 DB들을 새로 생성하지 않는다.

## 1. 로컬 환경과 fixture 실행

uv를 설치하고 저장소 루트에서 실행한다. 설치 안내는 README의 로컬 실행 절을 참고한다. 프로젝트 Python은 .python-version의 3.12.13이며 시스템 Python 3.9로 실행하지 않는다.

```sh
uv sync --locked
uv run --locked robingraph validate-fixture
uv run --locked robingraph evaluate-fixture
uv run --locked robingraph serve-fixture
```

접속 주소는 http://127.0.0.1:8000/chat, 상태 확인은 /health, API 문서는 /docs이다. fixture 모드는 외부 DB·LLM 없이 실행하며 /health의 mode는 fixture이다.

## 2. 실제 종 서비스 설정

.env.example을 참고해 저장소 루트의 .env를 준비한다. 기존 파일이 있으면 덮어쓰지 않고 필요한 키를 추가한다. CLI는 현재 실행 디렉터리의 .env를 읽고 이미 설정된 환경 변수를 우선한다.

| 설정 | 필수 항목과 기본값 |
|---|---|
| Neo4j | NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD. NEO4J_DATABASE 기본값 neo4j |
| PostgreSQL | ROBINGRAPH_PG_HOST, ROBINGRAPH_PG_DATABASE, ROBINGRAPH_PG_USERNAME, ROBINGRAPH_PG_PASSWORD |
| PostgreSQL 추가 | ROBINGRAPH_PG_PORT 기본값 5432, ROBINGRAPH_PG_SCHEMA 기본값 ingest, ROBINGRAPH_PG_SSLMODE 기본값 prefer |

Neo4j URI는 Bolt 계열 주소를 사용한다. 실행 호스트 또는 API 컨테이너에서 양쪽 DB에 연결할 수 있어야 한다. 인증값은 .env에만 보관하고 커밋하지 않는다.

새 개발·TEST DB에 스키마가 없는 경우 다음 마이그레이션을 실행한다. 기존 운영 DB는 별도 승인과 변경 검토 없이 이 명령을 실행하지 않는다.

```sh
uv run --locked robingraph migrate-postgres
```

이후 [수집 런북](n8n/README.md)과 [PostgreSQL 수집 관리](postgres-ingest-control-plane.md)에 따라 분류판, 이름, 형질 등 필요한 자료를 적재하고 활성 스냅샷을 준비한다. 빈 DB나 합성 fixture 적재만으로 전체 종 서비스가 준비되지는 않는다.

```sh
uv run --locked robingraph verify-neo4j
uv run --locked robingraph verify-postgres
uv run --locked robingraph serve-neo4j
```

기본 바인딩은 127.0.0.1:8000이다. 컨테이너 실행은 Compose에서 0.0.0.0:8000을 지정한다.

## 3. 기능별 선택 설정

| 기능 | 설정 | 없을 때의 범위 |
|---|---|---|
| Jev 의도 분석 | JEV_API_KEY, ROBINGRAPH_INTENT_ROUTER=auto | auto는 기존 규칙·임베딩 경로를 사용 |
| 문헌 임베딩·벡터 검색 | ROBINGRAPH_JINA_ENDPOINT, ROBINGRAPH_JINA_MODEL, ROBINGRAPH_JINA_DIMENSIONS 및 필요 시 ROBINGRAPH_JINA_API_KEY | 해당 임베딩 경로에 필요한 설정과 색인 준비가 별도로 필요 |
| Gemini 근거 답변·추가 설명 | GEMINI_API_KEY, ROBINGRAPH_GEMINI_MODEL | Gemini 생성 기능을 사용할 수 없음 |
| MLflow 추적 | ROBINGRAPH_MLFLOW_TRACING=true, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT_NAME | 기본 API 실행에 추적 서버는 필수가 아님 |
| 수집 자동화 | n8n과 별도 ingest 환경 파일 | 이미 활성 데이터가 준비됐다면 요청마다 n8n을 실행할 필요는 없음 |

추적과 Gemini SDK/autolog를 사용할 로컬 환경은 아래 명령으로 설치·실행한다. NAS Dockerfile은 tracing 추가 의존성을 포함한다.

```sh
uv sync --locked --extra tracing
uv run --locked --extra tracing robingraph serve-neo4j
```

## 4. NAS TEST 실행 준비

Docker daemon과 Compose가 사용 가능해야 한다. robingraph-edge 외부 네트워크를 준비하고 API와 Neo4j·NPM의 연결을 확인한다. PostgreSQL과 외부 API도 컨테이너에서 도달 가능해야 한다. 네트워크 구성은 [NAS 배포 런북](nas-deployment.md)을 따른다.

.env.nas.test가 없을 때만 .env.nas.example을 복사한다. 권한을 600으로 설정하고 TEST DB 연결값, ROBINGRAPH_API_MODE=serve-neo4j, TEST 전용 ROBINGRAPH_IMAGE 태그를 지정한다. n8n API 키와 적재 자격정보는 별도 .env.nas.ingest에 둔다.

```sh
chmod 600 .env.nas.test
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh preflight
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh dry-run
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh verify
```

TEST는 robingraph-test Compose 프로젝트와 robingraph-api-test 컨테이너를 사용한다. 공개 도메인에 자동 연결되지 않으며 내부 주소는 http://robingraph-api-test:8000이다. 현재 공개 도메인은 운영 robingraph-api:8000을 가리킨다. Compose는 호스트 포트를 공개하지 않고 expose만 사용하므로 공개 접속에는 NPM과 DNS·TLS 구성이 필요하다.

운영 환경 파일은 .env.nas.prod로 분리한다. 사용자가 TEST 결과를 확인하고 운영 반영을 명시적으로 승인한 후에만 운영 배포·재시작·이미지 교체·DB 변경을 진행한다.

## 5. 실행 후 검증

### 현재 Mac의 로컬 TEST

로컬 TEST는 `.env.nas.test`와 저장소의 `compose.local-test.yml`을 사용한다. 포트는 `127.0.0.1:8000`이며 프로젝트와 컨테이너는 항상 TEST로 고정된다.

```sh
sh scripts/deploy_local_test.sh deploy
sh scripts/deploy_local_test.sh verify
```

`deploy`는 최신 코드의 이미지를 빌드하고 실행한다. 이미지가 이미 있으면 `start`로 빌드 없이 시작할 수 있다. `status`와 `stop`도 지원한다. 이 명령은 원본 TEST DB 주소를 사용하므로 컨테이너에서 직접 DB에 연결할 수 있어야 한다.

2026-10-14 현재 이 Mac의 OrbStack 로그인 시 자동 시작을 활성화했고 TEST의 Docker 재시작 정책은 `unless-stopped`다. 재부팅 뒤 사용자 로그인과 OrbStack 시작 후, 명시적으로 중지하지 않은 컨테이너는 다시 실행하도록 설정했다. 실제 Mac 재부팅 검증은 수행하지 않았다.

2026-10-14 후속 점검에서 사용자 OrbStack 재시작 후 Neo4j·PostgreSQL·Jina에 컨테이너 직접 TCP 연결이 모두 성공했다. 위 `start`로 원본 .env.nas.test와 저장소의 로컬 포트 설정을 적용했고, 임시 중계 프로세스를 종료했다. 실제 API 18개 검사와 Chromium 프로필 채팅을 통과했다. 현재 TEST는 /tmp 중계나 Compose override에 의존하지 않는다. macOS 권한 토글이 실제 원인이었는지는 확인하지 않았으며 실제 Mac 재부팅 검증은 별도다.

/health의 status=ok와 mode를 확인한다. NAS에서는 deployment_target이 선택한 환경과 같은지도 확인한다. health의 taxonomy_release만으로 활성 AviList나 종 자료 준비를 판정하지 않는다.

```sh
uv run --locked python scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json
```

검증기는 기본 공개 주소로 https://robingraph.dove-nest.com을 사용하며 OpenAPI와 실제 분류 계통 응답을 로컬 계약과 비교한다. 실제 서비스에서는 청둥오리 프로필, 비슷한 새, 아종, 두 종 비교를 조회하고 결과·근거·사진·관계 탐색을 확인한다. 문헌 생성 기능은 실제 검색·모델 응답을 별도로 확인한다. 모의 단위 테스트 통과를 실제 DB/API 검증으로 계산하지 않는다.

## 이번 정리의 검증·배포·한계

요청은 미커밋 도메인 정리의 push와 서비스 실행 요건 정리이다. 새 런타임 구현이나 DB 변경은 없고, 본 문서에서 안내한 설치·서버 시작·마이그레이션·TEST 배포 명령은 이번 작업에서 실행하지 않았다. 이전 점검에서 공개 운영 /health와 /chat HTTP 200, 프런트엔드 회귀 303개 통과를 확인했다. 현재 작업 환경은 uv와 프로젝트 Python 의존성이 없어 Python 단위 테스트를 실행하지 못했다. 앞선 도메인 변경 Python 문법 검사와 git diff --check는 통과했고 Graphify AST 갱신을 완료했다.

현재 호스트의 DB 연결·인증값, Docker 상태, 활성 스냅샷 전체, 모델 API 연결은 새로 확인하지 않았다. 실제 서비스 실행 전 해당 환경에서 위 순서대로 확인해야 한다. 실행 준비 문서는 비밀값을 포함하지 않으며, 운영 배포와 main 병합은 이번 요청에 포함하지 않는다. 커밋·push 결과는 채팅 완료 안내로 확인한다.
