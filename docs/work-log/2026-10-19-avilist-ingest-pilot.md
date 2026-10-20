# AviList 단일 자료원 반복 수집 파이프라인 TEST 파일럿 — 2026-10-19

> 상태: **1차 수동 TEST pilot 완료**. 검색 쪽은 기존 검색 회귀만 확인했다. 새 projection과 n8n 연결은 구현하지 않았다.
> Production 반영·commit/push는 없다. 백로그 상태는 변경하지 않았다.

## 요청 배경과 목표

사용자가 대량 수집 작업에 앞서 Airflow를 새로 도입하지 않고 기존 n8n + PostgreSQL 구성으로
**자료원 하나에 대한 반복 가능한 수집 파이프라인**을 먼저 구현하도록 요청했고, 담당자 협업으로 진행했다.

- 목표: 공식 자료원 1개(AviList Explorer v2025b JSON)를 고정 SHA-256으로 받아, 결정적(deterministic)
  prepare → review 승인 → hash gate를 거친 뒤 TEST PostgreSQL에 별도 pilot dataset/source_record/pointer만
  저장한다. 같은 입력을 다시 실행하면 새 run 없이 no-op이 되어야 한다.
- 역할: Codex(dev-codex) root CLI·통합·TEST 실행, Claude(dev-claude) 코어 모듈·단위 테스트, 별도 Codex
  독립 reviewer의 read-only 검토와 agent 승인, Writer(main-2) 본 작업 기록·Obsidian 동기화.
- Airflow 미도입은 사용자 지시에 따른 것이며, 이 문서에서 Airflow와 비교 평가를 수행하지 않았다.

## 작업 경계 (이번 범위에 포함하지 않은 것)

- 새 종 분포 추론, 새 PG artifact의 도메인 projection(Neo4j/검색 자료 반영), 이름 벡터·임베딩 쓰기 없음.
- n8n schedule/workflow 연결은 구현하지 않았다. 수동 CLI 실행 파일럿이다. "반복"은 동일 입력 재실행의 멱등성
  (`already_applied`)을 뜻하며 주기 실행이 구현됐다는 의미가 아니다.
- Production 실행·배포, 앱 이미지 교체·앱 재시작, 컨테이너 rootfs 보안 설정 변경, commit/push/merge 없음.
- 백로그: RG-101(보류)·RG-406 전체 상태는 변경하지 않았고 작업 기록만 추가했다.
- Writer는 코드 수정·DB 쓰기·서비스 재시작을 하지 않았고 이 문서 외 저장소 파일을 변경하지 않았다.

## 자료원과 라이선스

| 구분 | 내용 |
|---|---|
| 신규 수집 자료원(1개) | AviList Explorer v2025b JSON `https://explore.avilist.org/data/avilist-2025b.json` |
| 안내 페이지 | `https://www.avilist.org/checklist/v2025b/` |
| 라이선스 | CC BY 4.0 (`AVILIST_SOURCE` 기재값. Codex가 2026-10-19 공식 안내 페이지에서 Explorer 링크와 CC BY 4.0 명시를 웹으로 확인) |
| 고정 SHA-256 | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` (`AVILIST_SHA256`, 기존 pin) |
| 참조 자료(신규 수집 아님) | 기존 고정 KOS 2025 한국조류목록 v2.1 참조 bundle `src/robingraph/retrieval/species_ko_names.json`, SHA-256 `b660e125…66ba7a` (`KOS_SHA256`) |
| 분류판 | `TAXONOMY_RELEASE=v2025b`, `CONCEPT_SET_ID=rg:concept-set:avilist-v2025b` |

KOS 자료는 새로 내려받지 않았고 저장소에 고정된 bundle을 보조 입력으로만 사용했다. KOS의
`license_name`은 `null`이며 이용 안내 문구(`KOS_USE_NOTE`)만 보존한다. KOS를 CC BY로 재표기하지 않는다.
실제 PG readback에서도 `kos_license_name: null`, `kos_use_note_preserved: true`를 확인했다.

## 확인한 원인과 근거

- 기존에는 AviList 자료를 n8n 기준정보 workflow(`docs/n8n/reference-ingest.md`)와 수동 builder로 처리했고,
  자료원 단위로 review 승인·hash gate·PG pilot pointer를 묶어 재실행할 수 있는 경로가 없었다. 대량 작업 전에
  이 경로를 자료원 하나로 먼저 검증하는 것이 이번 작업의 이유다(사용자 요청).
- 공식 JSON 실제 다운로드(Codex, 실제 네트워크): 19,933,159 byte, 33,684행 / species 11,131, SHA-256이 기존
  pin과 일치. Writer는 재다운로드하지 않았다.
- approval의 의미: CLI gate의 approval은 신뢰된 로컬 운영자 파일의 hash binding(운영자 실수 방지)이며 인증
  서명이 아니다. 이번 승인은 agent 승인으로, 사용자의 Production 승인이나 인간 조류 전문가 검토가 아니다.
- 설치 코드 동일성: `install.json`의 TEST 설치 파일 SHA-256(builder `991d1bfc…`, runner `155b41d4…`,
  core `ae0a1140…`)이 현재 dev-codex 소스와 같음을 Writer가 `shasum -a 256`으로 대조했다. 기반 Git revision은
  `bc643ee9edef0fc58c605adde70b4808b7622ac5`이며 `uncommitted_pilot: true`, `test_tools_only: true`, `app_restart: false`다.

## 변경 전후 동작

- 변경 전: 위와 같이 자료원 단위 반복 실행 경로가 없었다.
- 변경 후:
  1. `prepare [--source PATH] --output DIR`: `--source`가 없으면 공식 URL을 받고, 다른 URL로 redirect되면 거부,
     25,000,000 byte 상한. builder로 bundle을 만들고(AviList·KOS SHA 불일치 시 실패) 코어의 `prepare_manifest`로
     manifest를 만든다. 코어는 형식 오류 행, 중복 species ID/이름, 변경된 source·로컬 입력, 변조된 bundle에
     fail-closed한다(코어 단위 테스트 기준). **출력 폴더가 이미 있으면 덮어쓰지 않고 실패하므로 기존 실행 폴더는
     재사용할 수 없다.** 결과 `review_required`.
  2. `apply --package DIR --approval FILE`: source로 bundle·manifest를 재계산해 바이트 단위로 대조(hash gate)하고
     `validate_approval`로 승인 파일을 검증한다. 이어 읽기 전용 runtime 검사를 한다. `--apply`가 없으면 `dry_run`으로
     끝나고 쓰기 lock에 들어가지 않는다.
  3. 읽기 전용 runtime 검사: TEST PG/Neo4j(`bolt://192.168.219.98:7687`) allowlist, 설치된
     `species_distribution.json`과 bundle 동일성, `/health`의 `deployment_target=test`, 활성 분류판이 pin과 같은지,
     이름 벡터 인덱스 `dry_run=True` 결과가 최신·호환인지(갱신 필요 시 쓰기 없이 실패), 고정 검색 회귀 4건
     (Kea outside/all answer, Keaa outside clarify, 청둥오리 korea answer; answer는 API 분포 status·evidence가
     승인 bundle과 같은지 대조), 검사 전후 활성 분류판·한국어 이름 dataset 불변.
     이는 **기존 검색 회귀**와 이름 인덱스 dry-run이며 새 PG artifact의 projection 검증이 아니다.
  4. `--apply`: `ROBINGRAPH_DEPLOY_TARGET=test`와 PG 대상 allowlist(host/port/database/user/schema)를 연결 전에
     확인하고, 연결 후 `current_database()/current_user`를 재확인한다. advisory lock으로 동시 실행을 막고, 기존
     pilot dataset이 있으면 source_id·`policy_status=allowed`를 확인한다. 같은 manifest의 release가 이미 활성이면
     provenance(content/manifest SHA)를 대조하고 `already_applied` no-op. 아니면 pilot dataset
     `rg:dataset:avilist-distribution-pilot` 아래 release·run을 만들고 bundle 전체를 source_record 1건으로 append한
     뒤 state version CAS로 pilot pointer를 활성화하며 cursor에 `projection_performed: false`를 기록한다.
     release/record URI는 `urn:robingraph:avilist-pilot:bundle:<bundle canonical sha256>`이고 실제 artifact는
     `source_record.payload`에 있다. 원문 URL·각 SHA·라이선스는 release metadata의 sources/inputs로 보존한다.
     append/activate 예외 시 활성 pointer를 다시 읽어 같은 run/release가 이미 커밋됐으면 `applied_reconciled`로
     처리하고(응답 유실 대비), 아니면 run을 실패 처리하며 활성화하지 않는다. 실패 기록이 원래 오류를 가리지 않는다.
     재시도 시 record ID는 manifest 해시 기반으로 같고 run ID만 새로 생성된다.

### approval 파일 (8개 필드)

`manifest_sha256`, `bundle_sha256`, `decision`, `reviewer`, `reviewer_type`, `reviewed_at`, `rationale`, `target`.
이번 값: `decision=approved`, `reviewer_type=agent`, `reviewed_at=2026-10-19T05:11:48Z`, `target=test`,
manifest `efa03d4e…4b29913f`, bundle `85919248…b44cc3`. rationale은 pinned source hash, KOS/generator 입력 hash,
manifest/bundle 결정적 재구성, 설치된 분포 자료와 동일, 기존 국외 6종 불변을 근거로 들고, 인간 승인·새 분포
판정·도메인 projection·Production 승인이 아니며 hash binding은 인증 서명이 아님을 명시한다.

## 실제 실행 명령

관련 단위 테스트(dev-codex):

```sh
uv run --locked --extra test python -m unittest tests.test_avilist_pipeline tests.test_avilist_pipeline_runner tests.test_postgres_ingest tests.test_species_scope -v
```

검토 패키지 생성(출력 폴더가 이미 있으면 실패하므로 기존 실행 폴더는 재사용할 수 없다):

```sh
uv run --locked --extra test python -m scripts.run_avilist_pipeline prepare --source /tmp/rg-avilist-pipeline/avilist-2025b.json --output /tmp/rg-avilist-pipeline/review-package
```

TEST 앱 컨테이너 안에서 dry-run:

```sh
docker --context orbstack exec -e PYTHONPATH=/tmp/rg-avilist-pilot/src:/tmp/rg-avilist-pilot -w /tmp/rg-avilist-pilot robingraph-api-test python -m scripts.run_avilist_pipeline apply --package review-package --approval approval.json
```

실제 쓰기와 재실행(같은 명령에 `--apply`, 두 번 실행):

```sh
docker --context orbstack exec -e PYTHONPATH=/tmp/rg-avilist-pilot/src:/tmp/rg-avilist-pilot -w /tmp/rg-avilist-pilot robingraph-api-test python -m scripts.run_avilist_pipeline apply --package review-package --approval approval.json --apply
```

## 변경 파일

최종 코드 변경 4개(모두 dev-codex 미추적 신규, 미커밋):

| 파일 | 담당 | 내용 |
|---|---|---|
| `src/robingraph/ingest/avilist_pipeline.py` | Claude 작성 → Codex 통합 | canonical bytes, `prepare_manifest`, `validate_approval`, fail-closed 입력 검사 |
| `tests/test_avilist_pipeline.py` | Claude | 코어 11개 (fixture 10 + 실제 고정 source 1) |
| `scripts/run_avilist_pipeline.py` | Codex | root CLI(prepare/apply), TEST allowlist·lock·정책·응답 유실 reconcile |
| `tests/test_avilist_pipeline_runner.py` | Codex | runner 15개 (mock) |

검증 산출물 14개: dev-codex `docs/verification/assets/2026-10-19-avilist-pilot/`
(`install.json`, `prepare.json`, `approval.json`, `before.json`, `dry-run.json`, `negative-gates.json`, `apply.json`,
`reapply.json`, `after-dry-run.json`, `after.json`, `record-readback.json`, `summary.json`, `related-tests.log`,
`graphify-update.log`).
본 문서: main-2 `docs/work-log/2026-10-19-avilist-ingest-pilot.md`. dev-codex의 다른 dirty 파일(Jenkins·RG-406 등)은
이번 작업과 별개다.

## 검증 방법과 실제 결과

Writer는 위 산출물을 dev-codex에서 직접 읽어 수치를 대조했다. 실행 자체는 Codex가 했다.

| 검증 | 종류 | 결과 |
|---|---|---|
| 공식 JSON 다운로드·크기·행/종 수·SHA pin 대조 | 실제 네트워크 | **통과** (19,933,159 byte, 33,684행, 11,131 species, SHA 일치) |
| 관련 unittest (위 명령) | fixture/mock 중심 + 실제 고정 source 1건 | **47 통과 · 실패 0 · skip 0** = 코어 11(fixture 10 + 실제 source 1) + runner 15(mock) + 기존 21(`test_postgres_ingest` 7 + `test_species_scope` 14). `related-tests.log`의 `Ran 47 tests ... OK`와 모듈별 개수를 Writer가 확인 |
| prepare (고정 source) | 실제 실행 | `review_required`, manifest SHA-256 `efa03d4ee4bdc19780c3a83ed994a6faf5637f814a82fe42c3b2640a4b29913f`. counts: active 11,131 / korea 592 (KOS만 490·AviList만 1·둘 다 101) / outside 6 / unknown 10,533 / KOS 가-2 unknown 5 / AviList 한국 문구 거부 44종·46행 |
| 독립 reviewer 검토·승인 | read-only agent 리뷰 | approval 8개 필드 기록, `decision=approved`, `reviewer_type=agent` (위 절 참조). 인간 승인·Production 승인 아님 |
| TEST before 스냅샷 | 실제 TEST DB (읽기) | 이름 벡터 855, catalog fingerprint `a96ed6f8…19f4c1`, 다른 pipeline 상태 digest `5a5eee35…21a866b`, pilot run 0 |
| apply dry-run | 실제 TEST DB/API (읽기) | `dry_run`, 이름 인덱스 inventory 855·reused 855·to_embed 0·stale 0·schema/constraint compatible·catalog_current true, 기존 검색 회귀 4건 통과, `projection_performed=false` |
| negative gates | 실제 실행 | approval 누락·잘못된 approval·bundle 변조·production 대상 4건 모두 차단, `write_attempted=false` |
| apply 실제 쓰기 | 실제 TEST PG 쓰기 | `applied`, release `rg:release:avilist-pilot:efa03d4e…4b29913f`, run `avilist-pilot-cdf8b630-def1-4283-8125-f6d349e0cbcb`, state_version 1, 같은 readiness 검사 통과 |
| 재실행 | 실제 TEST PG | `already_applied`, 같은 release·run (새 run 없음) |
| after 스냅샷·요약 | 실제 TEST DB (읽기) | pilot run 1(succeeded)·record 1, 다른 pipeline 상태 digest before와 동일, 이름 catalog fingerprint 동일, 벡터 855 유지, 새 임베딩 0 |
| record readback | 실제 TEST PG (읽기) | 저장 bundle digest 일치, payload = 준비 bundle, sources/inputs 보존, KOS license_name null·use_note 보존 |
| graphify update . | 로컬 | rc 0, **6,076 nodes / 12,656 edges / 364 communities** (`graphify-update.log`의 `Rebuilt` 줄을 Writer가 확인). SQL parser 미설치·community label 갱신 안내는 앱 실패가 아니다 |
| 전체 Python / Node UI | — | **미실행** (변경 범위상 관련 47개만 실행). 전체 회귀 통과로 표현하지 않는다 |

fixture/mock 단위 검사와 실제 TEST DB/API 검증을 구분한다. 47개 중 실제 자료를 쓰는 것은 코어의 고정 source
1건뿐이며, PG 동작은 위 실제 TEST 실행 산출물로만 확인됐다.

## 실행 환경과 보관 경로

- 실행 위치: TEST 기존 앱 컨테이너 `robingraph-api-test`의 `/tmp/rg-avilist-pilot` 별도 코드 경로. 컨테이너는
  read-only rootfs이므로 보안 설정을 바꾸지 않고 tmpfs `/tmp`에 tar stream으로 추출해 설치했다.
- 컨테이너 `/tmp` 경로는 **컨테이너가 다시 생성되면 사라진다**. 호스트 보관본:
  `/Users/kimdove/robingraph-test/pipelines/avilist-pilot-20261019` (`approval.json`, `INSTALL.json`, `review-package`,
  `scripts`, `src` 존재를 Writer가 확인).
- 도구 이력: Writer 작업은 처음 Codex 세션으로 배정됐으나 startup agent-update-prompt 실패로 같은 Task를
  Claude 세션으로 재시도했고, 이 문서는 재시도 세션(main-2 Writer)이 작성했다. 앱·데이터 결과와 무관하다.

## 배포·커밋 정보

- TEST: 앱 배포 아님. 앱 이미지 교체·재시작 없음. TEST PG `ingest` 스키마에 pilot dataset/release/run 1건/record 1건/
  pointer만 기록됐다. 롤백은 실행하지 않았다.
- Production: 대상 아님, 변경 없음. Jenkins 운영 job 실행 없음.
- commit/push/merge: 없음. 코드 4개 파일과 산출물은 dev-codex 미추적 상태다.

## 남은 한계와 후속 사항

- n8n schedule 연결, 새 artifact의 도메인 projection, 두 번째 자료원, 대량 수집 적용은 별도 범위다.
- source_record가 bundle 전체를 1건으로 저장하므로 행 단위 diff/증분 적재는 검증되지 않았다.
- `verify_runtime`은 TEST API `http://127.0.0.1:8000`을 가정하므로 TEST 앱 컨테이너 안에서 실행해야 한다.
- 승인은 agent hash binding이며 인증 서명이 아니다. 인간 전문가 검토 절차는 별도로 정해야 한다.
- 전체 Python/Node 회귀, 운영 환경 실행, 컨테이너 재생성 후 호스트 보관본으로 재설치하는 절차의 검증은 하지 않았다.
- 이 결과를 다른 자료원이나 Production 수집 경로로 일반화하지 않는다. 인증 정보는 기록하지 않았다.
- Obsidian: `Work/RobinGraph/작업기록/1xx DB·저장소/2026-10-19-AviList-단일자료원-수집파일럿-TEST.md`에 같은 내용을
  기록하고 재조회했다. 백로그 상태는 변경하지 않았다.
