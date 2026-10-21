# n8n AviList 검토 파이프라인 워크플로 TEST 실행 — 2026-10-19

> 상태: **TEST n8n 수동 워크플로 구현·실제 실행 검증 완료**. 정기 스케줄·실행기 자동 시작·재부팅 복구는 구성/검증하지 않았다.
> Production 반영·앱 이미지 교체·앱 재시작·commit/push는 없다. 백로그 상태(RG-101 보류, RG-406)는 변경하지 않았다.

## 요청 배경과 목표

같은 날 진행한 [AviList 단일 자료원 TEST 파일럿](2026-10-19-avilist-ingest-pilot.md)은 수동 CLI 실행이었고 n8n 연결은 범위 밖이었다.
사용자가 이 파이프라인을 **n8n 워크플로로 만들고 실제 TEST에서 실행**하도록 요청했다.

- 목표: 기존 prepare → verify(승인·hash gate) → apply 단계를 n8n이 순서대로 호출하되, 각 단계 응답 계약을 검사하고
  HTTP 오류나 계약 불일치 시 다음 단계를 실행하지 않는다(fail-closed). 같은 입력의 재실행은 기존 run으로 no-op(`already_applied`)이어야 한다.
- 역할: Claude(dev-claude) 단계 실행 서비스 `scripts/serve_avilist_pipeline.py`와 mock 테스트 26건 구현, Codex(dev-codex, root) 워크플로 생성기·워크플로 JSON·테스트 3건,
  TEST n8n 등록·실제 실행·통합 검증, 별도 Claude(main) 독립 검토, Writer(main-2) 본 작업 기록·Obsidian 동기화.

## 작업 경계 (이번 범위에 포함하지 않은 것)

- 정기 스케줄 실행 없음: canonical workflow는 `active=false`, Manual Trigger 전용이다.
- 실행기(runner) LaunchAgent 자동 시작 미구성, 재부팅 후 복구 미검증.
- n8n DB 직접 쓰기 없음. 기존 API key·project 정보는 원격 read-only 조회만 수행했다.
- 기존 n8n 컨테이너 재시작 없음, 앱 이미지 교체·앱 재시작 없음, Production 실행·배포 없음, commit/push/merge 없음.
- 새 종 분포 추론·도메인 projection(`projection_performed=false`)·이름 벡터 쓰기 없음.
- Writer는 코드·설정 수정, DB 쓰기, 서비스 재시작을 하지 않았고 이 문서 외 저장소 파일을 변경하지 않았다. 워크트리의 기존 dirty 파일은 보존했다.

## 확인한 원인과 근거

- 기존 파일럿은 사람이 CLI를 순서대로 실행하는 구조여서 n8n에서 호출할 HTTP 경계와 단계별 응답 계약이 필요했다.
- TEST n8n API 접근: 기존 API key 3개 중 1개는 만료, 2개는 서명 불일치로 사용할 수 없었다. 새 키 발급을 요청했으나,
  n8n이 공식 지원하는 CLI(`import:credentials`, `import:workflow`, `execute --id`) 경로로 등록·실행이 가능해 **새 API key는 추가하지 않았다**.
- 원격 CLI 실행 시 실행 중인 n8n의 Task Broker 포트 5679와 충돌했다. 해당 CLI 실행에만 `N8N_RUNNERS_BROKER_PORT=15679`,
  `N8N_RUNNERS_MODE=internal`을 지정해 분리했고 기존 n8n은 재시작하지 않았다.

## 변경 전후 동작

| 구분 | 변경 전 | 변경 후 |
|---|---|---|
| 실행 방식 | 수동 CLI 단계 실행 | TEST n8n 수동 워크플로가 실행기 HTTP API를 순서대로 호출 |
| 단계 경계 | 운영자 판단 | 각 HTTP 응답을 IF 노드가 계약 검사, 실패 시 Stop and Error |
| 재시도 | 해당 없음 | blind retry 없음(`retryOnFail=false`, `onError=stopWorkflow`) |
| 스케줄 | 없음 | 없음(`active=false`, Manual Trigger만) |
| DB 결과 | pilot run 1건 | 변경 없음(기존 run 재사용, before/after 동일) |

### 워크플로 구성

- ID `rgAvilistTest01`, 이름 `RobinGraph AviList reviewed pipeline [TEST manual]`, 8노드:
  Manual Trigger 1 + HTTP Request 3 + IF 3 + Stop and Error 1.
  - `Manual TEST run` → `Prepare pinned AviList` → `Check prepare result` → `Verify approved artifact` → `Check verify result`
    → `Apply TEST pilot` → `Check apply result`; 각 IF의 false 분기는 `Reject unexpected result`(Stop and Error).
- HTTP 노드: 실행기 `http://192.168.219.97:18001/{prepare,verify,apply}`에 POST, 본문 `{}` 고정(입력 파라미터 없음), timeout 240000ms, JSON 응답.
- 인증: n8n에 저장된 `httpHeaderAuth` credential(ID `rgAvilistHeader01`, 이름 `RobinGraph AviList TEST runner`)의 Bearer 헤더. **토큰 값은 기록하지 않는다.**
- IF 검사: `stage`, `status`(prepare=`prepared`, verify=`verified`, apply=`applied`/`already_applied`/`applied_reconciled`),
  `manifest_sha256` 형식·단계 간 일치, `projection_performed === false`, 최종 apply의 release identity를 검사한다.
- 설정: `executionOrder=v1`, `executionTimeout=900`, `timezone=Asia/Seoul`, 성공·오류 실행 데이터 모두 저장.

## 변경 파일 (dev-codex 신규 5개, 미커밋)

| 파일 | 담당 | 내용 |
|---|---|---|
| `scripts/serve_avilist_pipeline.py` | Claude | prepare/verify/apply 단계 HTTP 실행 서비스(Bearer 인증, 공개 health) |
| `tests/test_avilist_pipeline_service.py` | Claude | 서비스 mock 테스트 26건(인증·본문·단계 응답·409 차단 등) |
| `scripts/generate_n8n_avilist_pipeline.py` | Codex | 워크플로 JSON 결정적 생성기(`--check`로 저장 파일과 일치 확인) |
| `n8n/robingraph-avilist-pipeline-test.json` | Codex | canonical 워크플로 정의 |
| `tests/test_n8n_avilist_pipeline.py` | Codex | 워크플로 구조·계약 테스트 3건 |

이 문서: `docs/work-log/2026-10-19-n8n-avilist-workflow.md`(main-2, Writer 신규). 증거 자산은 root의
`docs/verification/assets/2026-10-19-n8n-avilist/`의 현재 11개 파일(after/before/execution-history/missing-approval/runner-deployment/
success-first/success-second/summary/workflow-readback JSON 9개, `related-tests.log`, `graphify-update.log`)을 직접 읽어 대조했다.

## 실제 실행 명령

인증 값·키 ID 원문은 기록하지 않는다.

```sh
# 관련 단위 테스트 (6개 모듈)
uv run --locked --extra test python -m unittest \
  tests.test_avilist_pipeline tests.test_avilist_pipeline_runner \
  tests.test_avilist_pipeline_service tests.test_n8n_avilist_pipeline \
  tests.test_postgres_ingest tests.test_species_scope -v

# 워크플로 JSON 생성 결과와 저장 파일 일치 확인
uv run --locked python -m scripts.generate_n8n_avilist_pipeline --check

# TEST n8n(32GB Mac) 워크플로 실행 — 해당 실행만 Task Broker 포트 분리
ssh -o BatchMode=yes -i <TEST SSH key path> kimdove@192.168.219.98 /usr/local/bin/docker exec \
  -e N8N_RUNNERS_BROKER_PORT=15679 -e N8N_RUNNERS_MODE=internal \
  n8n-test n8n execute --id=rgAvilistTest01 --rawOutput
```

- 등록은 n8n 공식 CLI `import:credentials` / `import:workflow`로 수행했다. import에 쓴 토큰 포함 JSON은 로컬·원격 양쪽에서 삭제했다.
- Python 명령은 모두 `uv run --locked`로 프로젝트 잠금 환경에서 실행했다(시스템 python 3.9 직접 실행이 아님).
  단위 테스트 모듈 목록은 `related-tests.log`의 테스트 ID와 일치한다. `generate --check` 결과는 별도 로그 자산이 없어 Codex 보고(통과)에 근거한다.
- SSH는 `BatchMode`와 operator가 보관한 TEST SSH 키 파일을 `-i`로 지정해 실행했다. 키 경로 원문·키 내용·인증 값은 기록하지 않는다.

## 검증 방법과 실제 결과

### 단위 테스트 (mock/fixture 중심)

`related-tests.log`: `Ran 76 tests in 0.818s`, `OK` — **통과 76 / 실패 0 / 건너뛰기 0**.

| 모듈 | 건수 |
|---|---|
| tests.test_avilist_pipeline | 11 |
| tests.test_avilist_pipeline_runner | 15 |
| tests.test_postgres_ingest | 7 |
| tests.test_species_scope | 14 |
| (기존 소계) | 47 |
| tests.test_avilist_pipeline_service (신규, mock) | 26 |
| tests.test_n8n_avilist_pipeline (신규) | 3 |

- 실제 자료원 파일을 읽는 테스트는 core 1건(`RealSnapshotTest.test_rebuild_matches_installed_bundle_and_is_deterministic`)뿐이며 나머지는 fixture/mock이다.
- 로그의 `unauthorized (StageFailure)`, `409 Conflict`, `401 Unauthorized` 출력은 인증·승인 거부를 의도적으로 검사하는 테스트의 기대 출력이다.
- 전체 회귀 테스트, 브라우저에서의 워크플로 실행은 **미검증**.

### TEST n8n 실제 실행 (actual)

- 대상: 32GB Mac(192.168.219.98) `n8n-test` 컨테이너(loopback 5678), n8n DB `n8n-test` — 실제 대상 확인 후 진행.
- 등록 범위: owner 사용자의 개인 project에만 새 workflow·credential 등록. 워크플로 readback(`workflow-readback.json`):
  `active=false`, 노드 8, `stored_definition_matches_artifact=true`, 배포 방식 "supported n8n CLI import, TEST only".

| 실행 | 결과 | 마지막 노드 | 단계 결과 |
|---|---|---|---|
| 성공 1회차 (`success-first.json`) | CLI exit 0, error 없음 | Check apply result | prepare `prepared`(reused=true) → verify `verified`(search regression 4 통과) → apply `already_applied` |
| 성공 2회차 (`success-second.json`) | CLI exit 0, error 없음 | Check apply result | 1회차와 동일 |
| 승인 누락 negative (`missing-approval.json`) | CLI exit 1, error 있음 | Verify approved artifact | prepare `prepared` 후 verify에서 **409(승인 없음) 차단**, Apply 미실행 |

- 두 성공 실행 모두 동일 identity: manifest `efa03d4ee4bdc19780c3a83ed994a6faf5637f814a82fe42c3b2640a4b29913f`,
  bundle `859192488fb24952e509937249351a5daf2266709f3326ecd20259e2a6b44cc3`,
  release `rg:release:avilist-pilot:efa03d4e…913f`, 기존 run `avilist-pilot-cdf8b630-def1-4283-8125-f6d349e0cbcb`. 모든 단계 `projection_performed=false`.
- prepare 집계: active_species 11131, korea 592(KOS만 490 / AviList만 1 / 양쪽 101), outside 6, unknown 10533, KOS GA2 unknown 5,
  AviList 한국 텍스트 거부 종 44·행 46.
- negative 방법: 실행기 자체 폴더의 승인 파일을 일시 분리해 1회 실행하고, `finally`로 복원했음을 확인했다.
- n8n 실행 이력(`execution-history.json`, read-only 조회): `rgAvilistTest01`에 저장된 실행은 **success 2 / error 2**, 실행 방법 `n8n execute --id`(CLI).
  error 2건은 초기 LaunchAgent 실행기의 DB `OperationalError` 1건과 승인 누락 negative 1건이다. Task Broker 포트 충돌은 워크플로 실행 전 CLI 오류여서 이력에 포함되지 않는다.
  CLI 실행 이력이 n8n DB에 저장된 것은 확인했으나 UI에서의 실행은 미검증이다.

### DB 불변 확인 (actual TEST PG)

`before.json`과 `after.json`이 완전히 동일하다: pilot run `succeeded` 1건(record 1), name vector 855,
name catalog fingerprint `a96ed6f8…19f4c1`, 다른 pipeline 상태 SHA-256 `5a5eee35…a866b`. 워크플로 실행으로 새 run·벡터·fingerprint 변화가 없었다.

### 실행기와 실패 분리

- 실제 실행기: native M4(192.168.219.97):18001. root 고정 코드 복사본 `/Users/kimdove/robingraph-test/pipelines/n8n-avilist-test/code`,
  상태(state)는 별도 폴더, 승인 파일은 그 밖의 `approval.json`.
- `runner-deployment.json`: target test, mode "native foreground; no automatic startup", `app_image_unchanged=true`, `app_restart=false`.
  기록된 4개 파일(`scripts/serve_avilist_pipeline.py`, `scripts/run_avilist_pipeline.py`, `scripts/build_species_distribution.py`,
  `src/robingraph/ingest/avilist_pipeline.py`)의 SHA-256이 dev-codex 현재 파일과 일치함을 Writer가 `shasum -a 256`으로 확인했다.
- LaunchAgent로 실행했을 때 DB `OperationalError`가 발생했다. 같은 env 일치를 확인한 뒤 foreground tools 세션에서 같은 verify가 성공했다.
  **원인은 단정하지 않는다.** 실패한 LaunchAgent는 bootout했고 plist는 시작 폴더에서 빼 private 보관했다.
- 현재 작동 중인 실행기는 tools 세션(session 17212 / PID 59159)이다. 자동 시작 미구성, 재부팅 복구 미검증.

### 독립 검토와 graphify

- 별도 Claude(main) 독립 검토: 차단 결함 없음(Codex 전달 결과).
- `graphify update .`: rc 0, 6186 nodes / 12953 edges / 372 communities(`graphify-update.log`). sql 의존성 미설치 경고·무심볼 파일 경고는 그래프 생성 실패가 아니다.

## 보안·자격 증명 처리

- Bearer 토큰은 n8n credential 저장소와 실행기 측 TEST `service.env`(권한 0600)에만 있다. 문서·로그 자산에 값이 없다.
- import용 토큰 JSON은 로컬과 원격 양쪽에서 삭제했다.
- Orca 브라우저에서 사용자 요청으로 `http://127.0.0.1:15678/workflow/rgAvilistTest01`을 열었다(SSH forward 15678 → 32GB Mac localhost:5678).
  현재 로그인 화면이며 로그인은 대행하지 않았다.

## 배포·커밋 정보

- 배포: TEST n8n에 workflow·credential CLI import, TEST 실행기 코드 복사본 배치만. 앱 이미지 교체·재시작 없음, Production 없음.
- 커밋: 없음(commit/push 미수행). 구현 5개 파일은 dev-codex 신규(미커밋) 상태다.
- 백로그: RG-101 보류, RG-406 상태 변경 없음.

## 남은 한계와 후속 사항

1. 실행기 자동 시작(LaunchAgent) 미구성·재부팅 복구 미검증. LaunchAgent의 DB `OperationalError` 원인 조사 필요.
2. 현재 실행기는 대화형 tools 세션 프로세스(PID 59159)에 의존하므로 세션 종료 시 워크플로 HTTP 단계가 실패한다(fail-closed).
3. 스케줄 주기가 정해지지 않아 정기 스케줄은 미구성이다(`active=false`).
4. 브라우저 UI에서의 수동 실행·로그인 후 화면 확인은 미검증(로그인 화면까지만 확인). CLI 실행 이력이 n8n DB에 저장된 것은 확인했다.
5. 전체 회귀 테스트 미실행. 새 artifact의 도메인 projection은 여전히 범위 밖이다.
6. 기존 n8n API key 상태(만료 1, 서명 불일치 2)는 정리하지 않았다.
7. dev-codex 신규 5개 파일은 미커밋이며 commit/push와 Production 반영은 수행하지 않았다.
