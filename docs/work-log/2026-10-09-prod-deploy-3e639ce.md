# PROD API 최신 버전 배포 (3e639ce) — 2026-10-09

## 요청 배경과 목표

같은 날 TEST의 Neo4j·PostgreSQL 데이터를 PROD로 이관했다(`2026-10-09-test-to-prod-migration.md`).
이어서 PROD API도 최신 버전으로 배포해 달라는 요청을 받았다. PROD 직접 접속은 사용자가 이미 허용했다.

## 배포 전 상태와 대상 버전 결정

| 항목 | PROD(배포 전) | TEST |
|---|---|---|
| 컨테이너 / 이미지 | `robingraph-api` / `robingraph-api:prod-local` | `robingraph-api-test` / `robingraph-api:test-rg015scroll-3e639ce` |
| 소스 커밋(OCI revision) | `62c07d8` (이미지 생성 2026-10-01) | `3e639ce` |
| 상태 | running, healthy | running, healthy |

- 대상은 **`3e639ce`**(마지막 코드 변경 `fix: fit desktop cards without scroll and align mobile borders`)다.
  TEST에서 이미 검증한 커밋이다. 이후 dev의 커밋은 문서뿐이고, `main`과 `3e639ce`는 코드 경로
  (`src`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `compose.nas.yml`, `scripts`, `config`, `data`)에 차이가 없다.
- `62c07d8` → `3e639ce`는 40개 파일, +61,864/−475줄(대부분 자료·UI)이다.
- PROD 체크아웃(`~/RobinGraph-rg001-20261002`)은 git 저장소가 아니라 배포 묶음에서 푼 것이다.
  `docs/nas-deployment.md` §9의 `package_nas_release.sh` 절차를 그대로 따랐다.

## 수행 내용

1. **릴리스 묶음 생성**: `sh scripts/package_nas_release.sh --ref 3e639ce`로 결정적 tar.gz와 manifest를 만들었다.
   아카이브 SHA-256 `6866f47a2f2fac2c8782d8e14cd49e5b8ac4c393fc61f4dfe5cb269a63be5c64`.
2. **전송과 무결성 확인**: `scp`가 이 NAS에서 되지 않아(이관 때와 동일) `ssh … "cat > file" < archive`로 전송했다.
   NAS에서 SHA-256이 manifest의 `archive_sha256`과 일치했고, 내장 `MANIFEST.txt`의 파일별 SHA-256 검증에서
   불일치 0건이었다.
3. **새 체크아웃**: `~/RobinGraph-3e639ce`에 풀고, 현재 PROD 체크아웃의 `.env.nas.prod`를 NAS 안에서 복사했다
   (권한 0600, 비밀 값은 화면과 문서에 출력하지 않음). 새 파일에서만 `ROBINGRAPH_IMAGE=robingraph-api:prod-3e639ce`,
   `ROBINGRAPH_VCS_REF=3e639ce51d9c247a244a2451adcb2a2e9da60a67`로 바꿨다. 기존 체크아웃과 그 env는 건드리지 않았다.
4. **점검**: `ROBINGRAPH_DEPLOY_TARGET=prod sh scripts/deploy_nas.sh preflight`는 "configuration is valid",
   `dry-run`은 이미지 `robingraph-api:prod-3e639ce`, `restart: unless-stopped`, 읽기 전용 루트, `no-new-privileges`,
   외부 네트워크 `proxy_manager`로 컨테이너가 교체됨을 보였다.
5. **배포**: `… deploy_nas.sh deploy` 한 번 실행. 이미지를 빌드해 `robingraph-api:prod-3e639ce`를 만들고
   `robingraph-api` 컨테이너를 recreate한 뒤 healthcheck를 통과했다("RobinGraph API is healthy").
   시작 14:21:41, 종료 14:22:15(약 34초, 빌드 포함).

## 검증 결과 (실제 PROD 컨테이너·DB 대상)

| 항목 | 결과 |
|---|---|
| `deploy_nas.sh verify` | `{"status":"ok","mode":"neo4j","deployment_target":"prod"}` |
| 컨테이너 | `robingraph-api:prod-3e639ce`, running, healthy, 재시작 0회, OCI revision `3e639ce51d9c247a244a2451adcb2a2e9da60a67` |
| `scripts/verify_api_deployment.py`(컨테이너 내부, `--lineage-name 대륙검은지빠귀 --expected-scientific-name 'Turdus mandarinus'`) | `passed: true`, `backend_reachable`·`contract_parity_ok` true, structural/schema/response drift와 canary 이슈 없음 |
| 경로 스모크(컨테이너 내부 HTTP, 읽기 전용) | `/chat` 200, `/static/chat.js` 200(219,258바이트), `/v1/taxa/lineage` 정상 |
| 종 프로필 조회 `/v1/taxa/profile` | 흰뺨검둥오리·대륙검은지빠귀 모두 taxon, lineage, 형질 13개, 이미지 2개, 보전 정보, 요약 반환 |
| 채팅 스모크(키 추가 후, `/v1/chat`) | `흰뺨검둥오리에 대해서 알려줘` → 200, 18.4초, `route_method: jev`, `selected_intent: profile`, `disposition: answer`, 경고 없음. `곤줄박이와 비슷한 새는?` → 200, 8.8초, `route_method: deterministic`, `disposition: answer`, 경고 없음 |
| 로그 | 시작 완료, `/health`·`/openapi.json`·lineage 모두 200 |

모의 검증은 없었다. 위 조회는 이관된 PROD Neo4j·PostgreSQL에 대한 실제 요청이다.
프런트엔드·Python 테스트 스위트는 이번에 다시 실행하지 않았다(소스 변경 없이 이미 TEST에서 검증된 커밋을 배포).

## 변경 전후 동작

- 변경 전: 10월 2일 시점의 `62c07d8` 화면·API. PROD DB는 이관 직후 TEST와 같은 데이터.
- 변경 후: 3e639ce의 카드 UI(PC 무스크롤, 모바일 균일 테두리, 도넛 차트, 관찰 포인트 등)와 API가 PROD에서 동작한다.

## 설정 차이와 남은 한계

- **외부 연동 키 추가(같은 날 후속)**: 처음 배포 때 PROD의 `.env.nas.prod`에는 Jev·Gemini 설정이 없었다. 사용자의 지시로
  최신 TEST env(`~/RobinGraph-rg015scroll-3e639ce/.env.nas.test`, 같은 커밋 3e639ce 배포에 쓴 파일)와 키 이름을
  비교해 PROD에 없던 11개를 NAS 안에서만 `~/RobinGraph-3e639ce/.env.nas.prod`에 추가했다
  (`GEMINI_API_KEY`, `JEV_API_KEY`, `ROBINGRAPH_GEMINI_MODEL`, `ROBINGRAPH_INTENT_ROUTER`, `ROBINGRAPH_JEV_*` 7개).
  TEST와 같은 값을 쓰므로 `ROBINGRAPH_INTENT_ROUTER=jev`, Gemini 모델은 TEST와 같은 값이다. 값은 출력하지 않았고 추가 전 파일은
  `.env.nas.prod.bak-before-keys`로 NAS에 보존했다. 기존 체크아웃(`~/RobinGraph-rg001-20261002`)의 env는 바꾸지 않았다.
  추가 후 `deploy`를 한 번 더 실행해 컨테이너를 재생성했고(healthy, 재시작 0), 컨테이너 환경에 네 키가 설정된 것을 이름만으로 확인했다.
  TEST와 PROD가 같은 외부 API 키를 공유하게 되므로 사용량·한도는 함께 소모되고, 한쪽 키를 폐기하면 양쪽에 영향이 있다.
- **MLflow 추적**: PROD는 `ROBINGRAPH_MLFLOW_TRACING=false`(실험 이름 `robingraph-prod`)로 그대로 뒀다.
- **외부 공개 도메인 확인 못 함**: 검증은 컨테이너 안에서 했다. 컨테이너 이름과 네트워크(`proxy_manager`)는
  그대로여서 NPM 라우팅이 유지될 것으로 보지만 공개 도메인으로 직접 열어 보지는 않았다.
- **브라우저 화면 검증 안 함**: 모바일·PC 카드 화면을 PROD 주소로 열어 확인하지 않았다.
- **짧은 중단**: 컨테이너 recreate 구간에 PROD API가 잠시 응답하지 않았다(수 초, 정확히 측정하지 않음).
- **NAS 정리**: `robingraph-nas-release-3e639ce….tar.gz`와 `~/RobinGraph-3e639ce`는 같은 날 `/volume3/Birds-Nest/backups/robingraph-deploy/releases/`, `/volume3/Birds-Nest/backups/robingraph-deploy/checkouts/RobinGraph-3e639ce`로 옮겼다.
  이전 PROD 체크아웃 `~/RobinGraph-rg001-20261002`와 이미지 `robingraph-api:prod-local`은 롤백용으로 보존한다.

## 롤백

이전 이미지 `robingraph-api:prod-local`(`62c07d8`, 로컬에 존재 확인)로 되돌리려면 NAS에서 다음을 실행한다.
`rollback`은 빌드·`down`·volume 삭제 없이 컨테이너만 교체하고 healthcheck를 기다린다.

```sh
cd ~/RobinGraph-3e639ce   # 옮겨진 뒤 경로: /volume3/Birds-Nest/backups/robingraph-deploy/checkouts/RobinGraph-3e639ce
ROBINGRAPH_DEPLOY_TARGET=prod sh scripts/deploy_nas.sh rollback robingraph-api:prod-local
```

이번 배포에서는 롤백을 실행하지 않았다.

## 배포·커밋 정보

- 배포 대상 소스 커밋: `3e639ce51d9c247a244a2451adcb2a2e9da60a67`(이미 `origin/dev`와 `main`에 있음)
- PROD 이미지 태그: `robingraph-api:prod-3e639ce`
- 이 문서는 `dev-claude` 브랜치의 문서 커밋이며 코드 변경은 없다. 인증 정보는 기록하지 않았다.
