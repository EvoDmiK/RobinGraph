# n8n AviList 파이프라인 매일 06시 스케줄·Docker 실행기 TEST 전환 — 2026-10-19

> 상태: **TEST n8n 매일 06:00 KST 스케줄 활성화, 실행기 Docker 컨테이너 전환·자동 재시작 복구 검증 완료**.
> 첫 실제 06:00 시계 발화 실행은 아직 관측하지 않았다(대신 CLI로 엔진 전체 실행 2회 성공). 물리 호스트 재부팅·OrbStack 전체 재시작은 실행하지 않았다.
> Production 반영·API 앱 이미지 교체·API 앱 재시작·DB 재시작·commit/push는 없다. 백로그 상태(RG-101 보류, RG-406)는 변경하지 않았다.

## 요청 배경과 목표

같은 날 기록한 두 작업은 이번 작업의 선행 이력이며 본문을 수정하지 않았다.

- [AviList 단일 자료원 TEST 파일럿](2026-10-19-avilist-ingest-pilot.md): 수동 CLI 실행, n8n 연결 범위 밖.
- [n8n AviList 워크플로 TEST 실행](2026-10-19-n8n-avilist-workflow.md): Manual Trigger 전용(`active=false`) 8노드 워크플로,
  실행기는 대화형 tools 세션의 native foreground 프로세스(PID 59159), 자동 시작·재부팅 복구·정기 스케줄 미구성으로 남겼다.

사용자가 이 파이프라인을 n8n으로 계속 진행하도록 요청했다. 자동 실행 주기를 묻는 질문(매일 06시 / 1시간 / 수동)에 사용자가
"응 그렇게 해줘"라고 답했고, 이를 첫 제안인 **매일 06시(KST)** 로 해석한다는 점을 채팅에 명시한 뒤 진행했다.

- 목표: (1) 워크플로에 매일 06:00 Asia/Seoul 스케줄 트리거를 추가하고 TEST n8n에서 실제 활성화한다.
  (2) 세션 의존 native 실행기를 재시작 정책이 있는 격리 Docker 컨테이너로 옮긴다.
  (3) 기존 prepare → verify(승인·hash gate) → apply fail-closed 계약과 멱등성(`already_applied`)을 유지한다.
- 역할: Codex(dev-codex, root) 구현·TEST 반영·통합 검증, 독립 검토(승인 파일 단일 bind의 stale inode 지적),
  Writer(main-2) 본 작업 기록·Obsidian 동기화.

## 이전 기록의 한계 중 이번에 해결한 것

이전 두 문서는 당시 상태의 역사 기록으로 그대로 둔다. 아래는 [n8n 워크플로 기록](2026-10-19-n8n-avilist-workflow.md)의
"남은 한계" 중 이번 작업으로 현재 해결된 항목이다.

| 이전 한계 | 현재 상태 |
|---|---|
| 2. 실행기가 대화형 tools 세션 프로세스(PID 59159)에 의존 | PID 59159가 정확한 대상임을 확인 후 종료. Docker 컨테이너 `robingraph-avilist-runner-test`(restart `unless-stopped`)로 전환 |
| 3. 스케줄 주기 미정, `active=false` | 매일 `0 6 * * *` Asia/Seoul 스케줄 노드 추가, TEST n8n에서 `active=true` readback 및 활성화 로그 확인 |
| 1. 실행기 자동 시작 미구성·재부팅 복구 미검증 | **부분 해결**: 컨테이너 프로세스 강제 종료 후 Docker 정책에 의한 자동 재시작·health 복원 확인. 물리 재부팅·OrbStack 전체 재시작은 미검증 |

LaunchAgent의 DB `OperationalError` 원인 조사 결과는 이번 증거에 없다(원인 미확인). 이번 작업은 LaunchAgent 대신 Docker 실행기를 사용했다.

## 작업 경계 (이번 범위에 포함하지 않은 것)

- Production 실행·배포 없음, commit/push/merge 없음.
- 기존 TEST API 앱 컨테이너·이미지·DB 재시작/교체 없음. 실행기는 기존 TEST 앱과 **같은 기존 TEST image**를 사용하며 새 이미지를 빌드하지 않았다.
- TEST n8n은 스케줄 활성화 반영을 위해 `n8n-test` 컨테이너만 1회 재시작했다(아래 근거).
- n8n UI·public API key 사용 없음(사용 가능한 키 없음). n8n 공식 CLI 경로만 사용했다.
- 새 종 분포 추론·도메인 projection(`projection_performed=false`)·이름 벡터 쓰기 없음.
- Writer는 코드·설정 수정, DB 쓰기, 서비스 재시작을 하지 않았고 이 문서 외 저장소 파일을 변경하지 않았다. 워크트리의 기존 dirty 파일은 보존했다.

## 확인한 원인과 근거

- **세션 의존 실행기**: 이전 실행기는 tools 세션 종료 시 함께 사라지는 구조였다. 정기 스케줄을 켜면 06시 실행이 세션 상태에 좌우되므로 실행기를 컨테이너로 분리했다.
- **승인 파일 단일 file bind의 stale inode**: 독립 검토에서, `approval.json` 한 파일만 bind하면 호스트에서 파일을 교체(이동·재작성)할 때
  컨테이너가 이전 inode를 계속 볼 수 있다는 지적이 나왔다. 승인 취소가 실행기에 반영되지 않을 위험이므로 **승인 디렉터리 전체를 read-only로 bind**하는 방식으로 바꿨다.
  - 중요: 호스트의 기존 `base/approval.json`은 과거 복사본이다. 현재 runtime이 읽는 승인 파일은 `base/review/approval.json`(컨테이너 `/review/approval.json`)이다.
- **n8n 활성화 반영**: artifact JSON은 import 안전값으로 `active=false`를 유지한다. CLI `import:workflow` 후 `publish:workflow --id rgAvilistTest01`을 실행했고,
  CLI가 "실행 중인 서버 반영에는 restart가 필요하다"는 실제 출력을 냈다. 그래서 TEST n8n `execution_entity`의 new/running/waiting이 0건임을 확인한 뒤 `n8n-test`만 재시작했다.

## 변경 전후 동작

| 구분 | 변경 전 | 변경 후 |
|---|---|---|
| 트리거 | Manual Trigger만, `active=false` | Manual Trigger + 매일 06:00 KST Schedule Trigger, TEST n8n `active=true` |
| 워크플로 노드 | 8 | 9 (manual 1 + dailySchedule 1 + HTTP 3 + IF 3 + Stop and Error 1) |
| 워크플로 이름 | `... [TEST manual]` | `RobinGraph AviList reviewed pipeline [TEST daily]` |
| 실행기 | native foreground, tools 세션 PID 59159 | Docker `robingraph-avilist-runner-test`, restart `unless-stopped` |
| 승인 파일 경로 | 실행기 폴더 밖 `approval.json` | 호스트 `base/review/` 디렉터리 전체를 `/review`에 RO bind |
| 단계 계약·재시도 | IF 계약 검사, blind retry 없음 | 변경 없음 |
| DB 결과 | pilot run 1건 | 변경 없음(기존 run 재사용, before/after 동일) |

### 워크플로 구성

- ID `rgAvilistTest01`. `Manual TEST run`과 `Daily 06:00 KST`(scheduleTrigger, `cronExpression` `0 6 * * *`) 두 트리거가 모두 `Prepare pinned AviList`로 연결된다.
- 이후 `Prepare pinned AviList` → `Check prepare result` → `Verify approved artifact` → `Check verify result` → `Apply TEST pilot` → `Check apply result`.
  각 IF의 false 분기는 `Reject unexpected result`(Stop and Error). HTTP 대상은 `http://192.168.219.97:18001/{prepare,verify,apply}`.
- 설정: `executionOrder=v1`, `executionTimeout=900`, `timezone=Asia/Seoul`, 성공·오류 실행 데이터 모두 저장. 알림 노드 없음.

### 실행기 컨테이너 구성 (`compose.avilist-test.yml`)

- 호스트: 16GB M4 Mac(192.168.219.97), Docker context `orbstack`. 컨테이너 `robingraph-avilist-runner-test`.
- 이미지: 기존 TEST image(`ROBINGRAPH_AVILIST_IMAGE`로 지정). command `python -m scripts.serve_avilist_pipeline --host 0.0.0.0 --port 18001`.
- `network_mode: host`: 실제 컨테이너에서 127.0.0.1(localhost):8000의 TEST API가 healthy임을 확인했다.
- 사용자 non-root UID:GID `501:20`, `working_dir /code`, `PYTHONPATH=/code/src:/code`, `ROBINGRAPH_DEPLOY_TARGET=test`.
- 마운트: `/code` RO(검토한 코드 복사본), `/review` RO(승인 디렉터리 전체), `/state` RW(상태). rootfs read-only, `/tmp` tmpfs 64m,
  `cap_drop: ALL`, `no-new-privileges:true`, `init: true`, `restart: unless-stopped`, health check는 `/health`의 `deployment_target=test` 확인, json-file 로그 10m×3.
- 영속 host base: `/Users/kimdove/robingraph-test/pipelines/n8n-avilist-test` (state·code·approval). private `compose.env`와 별도 `service.env`(권한 0600)는 이미 준비되어 있으며,
  compose 파일 사본도 같은 곳에 보관했다. env 값·토큰은 기록하지 않는다.

## 변경 파일 (dev-codex, git 기준 미추적·미커밋)

| 파일 | 구분 | 내용 |
|---|---|---|
| `compose.avilist-test.yml` | 신규 | TEST 실행기 컨테이너 정의(위 구성) |
| `scripts/generate_n8n_avilist_pipeline.py` | 수정(이전 작업 대비) | 매일 06:00 KST Schedule Trigger 추가, 이름 `[TEST daily]`, 9노드 생성 |
| `n8n/robingraph-avilist-pipeline-test.json` | 수정(이전 작업 대비) | 재생성된 canonical 워크플로(artifact `active=false`) |
| `tests/test_n8n_avilist_pipeline.py` | 수정(이전 작업 대비) | 새 daily 계약 테스트(`test_daily_schedule_and_manual_trigger_without_notifications`) 포함 3건 |

API 앱 이미지·실행기 서비스 코드(`scripts/serve_avilist_pipeline.py`) 변경은 이번 범위에 없다.
이 문서: `docs/work-log/2026-10-19-n8n-daily-runner.md`(main-2, Writer 신규). 증거 자산은 root의 `docs/verification/assets/2026-10-19-n8n-daily/`
현재 12개 파일(JSON 9개: after, after-automatic-recovery, after-container-restart, before, missing-mounted-approval, network-auth, runner-recovery,
schedule-readback, summary / `runtime-activation.log`, `related-tests.log`, `graphify-update.log`)을 Writer가 직접 읽어 대조했다.

## 실제 실행 명령

아래는 이번 작업에서 이미 실행한 명령의 기록이다. 독자가 그대로 재실행하라는 안내가 아니다(특히 publish·restart는 대상 확인이 선행돼야 한다). 인증 값·키 원문은 기록하지 않는다.

```sh
# 관련 단위 테스트 (6개 모듈)
uv run --locked --extra test python -m unittest \
  tests.test_avilist_pipeline tests.test_avilist_pipeline_runner \
  tests.test_avilist_pipeline_service tests.test_n8n_avilist_pipeline \
  tests.test_postgres_ingest tests.test_species_scope -v

# 워크플로 JSON 재생성
uv run --locked python -m scripts.generate_n8n_avilist_pipeline

# 16GB M4 Mac 실행기 컨테이너 기동
docker --context orbstack compose \
  --env-file /Users/kimdove/robingraph-test/pipelines/n8n-avilist-test/compose.env \
  -f compose.avilist-test.yml up -d

# TEST n8n(32GB Mac) 워크플로 실행 — 해당 실행만 Task Broker 포트 분리
ssh -o BatchMode=yes -i <TEST SSH key path> kimdove@192.168.219.98 /usr/local/bin/docker exec \
  -e N8N_RUNNERS_BROKER_PORT=15679 -e N8N_RUNNERS_MODE=internal \
  n8n-test n8n execute --id=rgAvilistTest01 --rawOutput
```

- 스케줄 반영: n8n CLI `import:workflow` → `publish:workflow --id rgAvilistTest01`, 이후 TEST n8n의 진행 중 실행 0건 확인 후 `n8n-test` 컨테이너만 재시작.
- 기타 검증(아래 결과 항목): `git diff --check`, `docker compose config --quiet` 통과, `graphify update .` rc 0.

## 검증 방법과 실제 결과

### 단위 테스트 (mock/fixture 중심)

`related-tests.log`: `Ran 76 tests in 0.726s`, `OK` — **통과 76 / 실패 0 / 건너뛰기 0**. 전체 회귀 테스트가 아니다.

| 모듈 | 건수 | 성격 |
|---|---|---|
| tests.test_avilist_pipeline | 11 | fixture 중심, 실제 자료원 1건 |
| tests.test_avilist_pipeline_runner | 15 | mock |
| tests.test_postgres_ingest | 7 | mock/정적 |
| tests.test_species_scope | 14 | fixture |
| (이전 소계) | 47 | |
| tests.test_avilist_pipeline_service | 26 | mock |
| tests.test_n8n_avilist_pipeline | 3 | 워크플로 구조·새 daily 계약 |

- 실제 자료원 파일을 읽는 테스트는 core 1건(`RealSnapshotTest.test_rebuild_matches_installed_bundle_and_is_deterministic`)뿐이다.
- 로그의 `unauthorized (StageFailure)`, `409 Conflict`, `401 Unauthorized`, `500` 출력은 거부·오류 경로를 의도적으로 검사하는 테스트의 기대 출력이다.
- 정적 검사: `git diff --check`, `docker compose config --quiet` 통과(Codex 보고, 별도 로그 자산 없음).

### 실행기 컨테이너 격리 확인 (actual, 16GB M4 Mac)

- 전환 전: native 실행기 PID 59159가 정확한 대상임을 확인한 뒤 종료했다.
- 컨테이너 내부에서 `/code`·승인 경로 쓰기 거부, `/state` 쓰기 허용, `core.__file__`이 `/code/src` 아래임을 실행으로 확인했다.
- `runner-recovery.json`: mounts `/code` RW=false, `/review` RW=false, `/state` RW=true, `read_only_rootfs=true`, `network_mode=host`, `user=501:20`.
- `network-auth.json`(32GB Mac `n8n-test` 컨테이너에서 실행기로 probe): `health_status=200`, 토큰 없는 stage 호출 `401`, `test_n8n_network_probe=true`.

### 스케줄 활성화 확인 (actual TEST n8n)

- `schedule-readback.json`: workflow `rgAvilistTest01`, `active=true`, 이름 `RobinGraph AviList reviewed pipeline [TEST daily]`, 노드 9,
  timezone `Asia/Seoul`, cron `0 6 * * *`, `runtime_activation_log_confirmed=true`, `artifact_imports_inactive_then_explicit_publish=true`. 저장 설정이 artifact와 일치한다.
- `runtime-activation.log`: `Activated workflow "RobinGraph AviList reviewed pipeline [TEST daily]" (ID: rgAvilistTest01)`.
- **첫 실제 06:00 시계 발화 실행은 미관측**(`first_clock_trigger_run_observed=false`). 엔진 전체 경로는 아래 CLI 실행 2회로 확인했다.

### 승인 디렉터리 취소(negative) 확인 (actual)

- 실제 호스트 `base/review/approval.json`을 이동한 상태에서 n8n 워크플로를 1회 실행했다.
- `missing-mounted-approval.json`: CLI exit 1, error 있음, 마지막 노드 `Verify approved artifact`. 실행 노드는 Manual → Prepare(`prepared`, reused) → Check → Verify까지이며
  verify가 **409(승인 없음)** 로 차단되어 **Apply는 실행되지 않았다**. 이후 `finally`로 승인 파일을 복원했음을 확인했다.
- 디렉터리 RO bind 덕분에 호스트 측 파일 이동이 컨테이너에 즉시 반영됨을 이 실행으로 확인했다(단일 file bind의 stale inode 문제 해소).

### 실행기 복구와 워크플로 성공 (actual)

| 순서 | 동작 | 결과 |
|---|---|---|
| 1 | 수동 `docker restart` 1회 | 이후 n8n 전체 실행 성공 1회(`after-container-restart.json`) |
| 2 | 컨테이너 내 정확한 서비스 PID 6의 cmdline 검증 후 SIGKILL | Docker 정책이 자동 재시작, `restart_count=1`, health 복원, 수동 `docker start` 미사용(`runner-recovery.json`) |
| 3 | 자동 복구 후 n8n 전체 실행 | 성공 1회(`after-automatic-recovery.json`) |

- 두 성공 실행 모두 CLI exit 0, error 없음, 마지막 노드 `Check apply result`, 실행 노드 7개(Manual → Prepare → Check → Verify → Check → Apply → Check).
- 단계 결과: prepare `prepared`(reused=true) → verify `verified`(search regression 4 통과) → apply **`already_applied`**. 모든 단계 `projection_performed=false`.
- identity 불변: manifest `efa03d4ee4bdc19780c3a83ed994a6faf5637f814a82fe42c3b2640a4b29913f`,
  bundle `859192488fb24952e509937249351a5daf2266709f3326ecd20259e2a6b44cc3`,
  release `rg:release:avilist-pilot:efa03d4e…913f`, 기존 run `avilist-pilot-cdf8b630-def1-4283-8125-f6d349e0cbcb`.
- prepare 집계: active_species 11131, korea 592(KOS만 490 / AviList만 1 / 양쪽 101), outside 6, unknown 10533, KOS GA2 unknown 5,
  AviList 한국 텍스트 거부 종 44·행 46.

### DB 불변 확인 (actual TEST PG)

`before.json`과 `after.json`이 완전히 동일하다: 기존 source PG pilot run `succeeded` 1건(record 1), name vector 855,
name catalog fingerprint `a96ed6f8…19f4c1`, 다른 pipeline 상태 SHA-256 `5a5eee35…a866b`.

### 종합 (`summary.json`)

`schedule_active=true`, `n8n_live_activation_confirmed=true`, `automatic_crash_recovery_tested=true`, `post_recovery_workflow_success=true`,
`approval_directory_revocation_test_passed=true`, `workflow_successes=2`, `tests_passed=76`, `pg_and_vector_state_unchanged=true`,
`physical_reboot_tested=false`, `first_clock_trigger_run_observed=false`, `production_changed=false`, `app_restarted=false`,
`test_n8n_restarted_for_activation=true`, `commit_push=false`.

### graphify

`graphify update .`: rc 0, **6204 nodes / 12972 edges / 384 communities**(`graphify-update.log`). tree_sitter_sql 미설치 경고, 무심볼 파일 경고,
커뮤니티 라벨 변경 안내는 그래프 생성 실패가 아니다.

## 보안·자격 증명 처리

- Bearer 토큰은 n8n credential 저장소와 실행기 측 private `service.env`(0600)에만 있다. 문서·증거 자산에 토큰·키·env 값이 없다.
- 실행기는 non-root, rootfs RO, 모든 capability drop, no-new-privileges로 실행되며 코드·승인 경로에 쓸 수 없다.
- 토큰 없는 stage 호출은 401로 거부됨을 실제 n8n 컨테이너에서 확인했다. `/health`만 공개다.

## 배포·커밋 정보

- TEST 반영: 16GB M4 Mac에 실행기 컨테이너 기동(기존 TEST image 재사용), TEST n8n에 workflow CLI import·publish, `n8n-test` 컨테이너 1회 재시작.
- 재시작하지 않은 것: 기존 TEST API 앱, TEST DB(PG/Neo4j), Production 전부.
- Production: 변경 없음. 운영 반영은 AGENTS.md의 운영 배포 승인 규칙을 따른다.
- 커밋: commit/push 없음. 변경 파일은 dev-codex에서 git 기준 미추적 상태다.
- 백로그: RG-101 보류, RG-406 상태 변경 없음.

## 남은 한계와 후속 사항

1. 첫 실제 06:00 KST 시계 발화 실행은 아직 관측하지 않았다. 다음 06시 이후 n8n 실행 이력으로 확인이 필요하다.
2. 물리 호스트 재부팅·OrbStack 전체 재시작은 공유 TEST API를 건드리지 않기 위해 실행하지 않았다(미검증).
3. `unless-stopped`는 Docker 데몬이 시작된 뒤의 복구 정책이다. 재부팅 후 복구는 Mac 로그인과 OrbStack 기동에 의존한다.
4. 호스트의 `base/approval.json`은 과거 복사본이며 현재 runtime은 `base/review/approval.json`을 사용한다. 승인 변경 시 혼동하지 않아야 한다.
5. 전체 회귀 테스트 미실행. 관련 단위 테스트는 core 실제 자료원 1건 외 fixture/mock 중심이다.
6. n8n UI·public API 경로는 사용 가능한 키가 없어 쓰지 않았다. 기존 API key 상태는 정리하지 않았다.
7. 새 artifact의 도메인 projection은 여전히 범위 밖이다.
