---
created: 2026-11-05
date: 2026-11-05
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, n8n, bird-audio]
---

# [RG-507] n8n 새소리 수집·검토·허용 음원 저장

## 요약

사용자가 n8n 워크플로우를 통한 새소리 지원 확대를 승인했다. 수집 후보와 검토 상태를 관리하고, 저장한 자료를 비공개로 검토한 뒤 승인·공개 gate를 통과한 자료만 제공하며, 소량 처리와 backoff로 외부 요청 제한을 존중하는 흐름을 구현했다. 기존 RG-409의 도감 재생·검토 음원 catalog를 넘어서는 수집 자동화 범위다.

backend·workflow를 통합하고 TEST 앱 배포·추가 스키마 적용·실제 n8n Wait 재개·후보 수집과 중복 실행·인증 preview 및 미공개 차단을 검증했다. 참새 음원 1개를 저장했으며 `awaiting_review`로 남겼다. 실제 검토·공개는 수행하지 않았다. 인증된 TEST 저장 파일을 native Chromium control로 재생하고 기존 공개 음원 metadata 유지도 확인했다. RG-409의 공개12종 TEST 완료·2종 가용성 후속·운영 미승인 상태는 유지한다. 번호 규칙과 중복 검색 후 Codex 확인을 받아 RG-507로 신규 등록했다. 이번 작업기록은 TEST 구현·검증 완료를 뜻하며 백로그는 실자료 검토·공개와 운영 승인이 남아 `in_progress`다. 기본 수동 실행이며 주기 자동 수집은 별도 명시 활성화 전까지 꺼둔다. 저장·미리보기 성공은 새로운 공개 종 추가나 사람의 청취·승인을 의미하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | n8n으로 새소리 확대 처리 | 수집 후보·검토·허용 자료 저장·제공 |
| 설계 | 검토·공개 gate와 소량 처리 | 실패·재시도·CDN 요청을 구분 |
| 코드 / 설정 | 수집·검토·공개 상태 분리 | 내부 인증 API, 후보 DB, 파일 저장, workflow·관리 CLI |
| 실서비스 | TEST 수동 수집·저장 완료 | `.97` 영구 volume, `robingraph_test.ingest`, 참새 후보 1개 검토 대기 |
| 검증 | Python 99·UI 335 통과 | Wait `18180`, 수집 `18183`, 중복 `18184`, preview 인증·range와 미공개 차단 |
| 형상 관리 | TEST snapshot만 반영 | Production·Git commit/push/merge 미실행 |

## 1. 작업 배경 및 문제 분석

RG-409 수동 확대에서는 공식 출처 검토와 실제 음원 재생을 거쳐 공개12종을 확인했다. 14종 시안 중 2종은 CDN 가용성 검증이 남았다. 이번 작업은 더 많은 종을 무조건 공개하는 대신 후보 수집·검토 상태·허용 자료 저장·제공 절차를 반복 가능한 workflow로 만든다.

자료 동정·라이선스 적합성과 HTTP/CDN 가용성은 별개의 판정이다. 앞선 HTTP429와 Retry-After 경험은 설계 근거이며, 당시 결과를 이번 n8n 검증으로 재사용해 실행 완료를 주장하지 않는다.

## 2. 해결 방안 및 설계

Claude가 backend, Antigravity가 n8n·UI·TEST 배포를 구현하고, Codex는 결과 리뷰·통합·최소 리팩토링을 담당한다. Writer는 문서·백로그·동기화만 수행한다.

### 수동 소량 처리 계약

- n8n Config의 `after_taxon_id`를 명시 입력하고 최종 `next_cursor`를 출력한다. 수동 CLI 실행의 staticData 저장에 진행 상태를 의존하지 않는다.
- 기본 batch 1·최대5이며 주기 스케줄은 꺼둔다.
- 429를 받으면 남은 batch를 중단하고 정확한 Retry-After만큼 Wait한 뒤 status를 1회 조회해 deferred로 종료한다. 실제 원격 재시도는 다음 수동 실행에서 수행한다.
- 저장 위치는 TEST M4 전용 영구 volume `/var/lib/robingraph/audio`다. 현재 NAS 운영 파일 서비스는 변경하지 않는다.
- n8n 실제 버전 2.15.0과 TEST DB `n8n-test`를 확인했다. 인벤토리 비교에서 기존 workflow 36개·credential 37개는 불변이고 새 비활성 workflow 2개(audio·Wait fixture)와 credential 1개만 추가됐다. 인증 값은 문서에 기록하지 않는다.

### 내부 연결 경로와 초기 실행 실패

최초 공개 HTTPS 실행 `18181`은 stage에서 Cloudflare 502·Retry-After 60을 받고 실패했다. 이후 인증된 공개 status는 403, LAN status는 후보 없음 404였다. 실제 음원 제공자가 429를 반환한 사례로 기록하지 않는다. 지정 대기 시간을 존중한 뒤 고정 TEST LAN `http://192.168.219.97:8000`과 health TEST guard를 적용했으며 관련 fixture 7개가 통과했다. bearer 인증이 신뢰하는 LAN의 HTTP를 통과하므로 이 구간 TLS는 없다. LAN 실행 `18182`는 stage까지 도달했지만 backend의 Commons 요청이 502로 실패했다. 별도 허용된 metadata 읽기 1회에서 새 cached socket deadline 처리의 `OSError: [Errno 9] Bad file descriptor`가 재현돼 socket 처리 수정을 통합했다. 공개 게이트웨이의 `18181` 실패와 다른 원인이며 실제 provider 429는 관측하지 않았다. 이 시점 PG 후보는 0개다. 수정 후 source SHA256은 `2456506a398537a76c1ede2f899f2991d4cd0c4c74e5302d8252b980b294ab65`다. 수정 후 실제 collect `18183`과 중복 실행 `18184`가 성공했다.

### 검토와 공개 경계

후보·검토 승인·거절/보류·저장 성공·공개 여부를 구분한다. 출처·원자료 hash·동정 대상·license·원 metadata를 보존하며, 미검토 자료가 자동으로 공개되지 않는 경계를 실제 근거로 확인한다. 자동 디코딩 성공은 사람이 음원을 듣고 검토한 것과 다르다. 실제 수집 후보는 진짜 검토 근거가 없으면 `awaiting_review`로 남긴다. 공개 성공 검증은 격리 mock/fixture와 실제 검토 자료를 구분하며, fixture 승인으로 실제 원격 자료의 공개를 승인하지 않는다.

독립 리뷰에서 public media의 graph 공개 gate 누락을 발견해 배포 전 보완했다. PG의 공개 상태만으로 파일을 제공하지 않고 해당 graph 공개 근거도 확인한다. 실제 TEST 쓰기·공개 전에 발견한 코드 검토 결과이며, 실서비스에서 미승인 파일이 제공됐다고 단정하지 않는다.

## 3. 주요 구현 내용

| 파일 / 범위 | 구현 내용 |
| --- | --- |
| `src/robingraph/ingest/audio.py`, `audio_store.py` | 후보 발견·저장·검토·공개 처리, 중복·외부 제한·파일 검증 |
| `src/robingraph/ingest/migrations/0005_audio_candidates.sql` | 기존 ingest ledger 위에 후보 상태 저장 스키마 추가 |
| `src/robingraph/api/drf/audio_views.py`, `openapi_audio.json`, `application.py`, `urls.py` | 내부 인증 API와 비공개 preview, 승인 자료의 media 제공 |
| `src/robingraph/retrieval/recordings.py`, `cli.py`, `config/source-registry.json`, `.env.example` | 음원 조회·source 정책·실행 및 환경 계약 |
| `n8n/robingraph-audio-collection-test.json` | 수동 collect/status/review/publish 흐름과 cooldown Wait |
| `scripts/generate_n8n_audio_collection.py`, `scripts/manage_n8n_audio.py` | 재현 가능한 workflow 생성·검사와 TEST 관리 CLI |
| `src/robingraph/api/static/chat.js` | 허용된 저장 음원 경로를 기존 재생 UI와 연결 |
| `tests/test_audio_collection.py`, `test_postgres_ingest.py`, `test_n8n_audio_collection.py`, `tests/frontend/chat_ui.test.js` | 상태·저장·공개 gate·workflow·UI 회귀 |
| `docs/n8n/README.md` | 수동 운영 절차·batch/cursor·검토와 공개 분리·비밀값 취급 안내 |

내부 `/internal/v1/audio`의 `targets`, `discover`, `stage`, `status`, `review`, `publish`를 분리했다. 후보 ID는 학명과 정확한 파일 제목에서 계산하고 이미 저장된 비보류 후보를 원격 재수집 없이 반환하는 경로를 fixture로 검증했다. 실제 반복 실행에서는 같은 ID·hash·결과를 확인했으며 provider 요청 0회는 패킷 캡처로 측정하지 않았다. 내부 preview는 인증된 `GET/HEAD`와 단일 byte range를 제공한다. 공개 media는 파일 hash 기반 경로를 사용하며 저장 파일이 존재한다는 사실만으로 공개하지 않는다.

작업 재현 및 운영 명령은 `docs/n8n/README.md`에 모았다. 토큰은 workflow JSON이나 문서에 넣지 않고 저장 credential을 사용한다. 승인·게시 API가 존재하는 것과 실제 자료의 사람이 검토한 근거가 있다는 것은 구분한다.

## 4. 검증 및 테스트 결과

### 자동화 검사

socket 수정 후 최종 전달 결과는 Python 99·UI 335 통과다. Python 99에는 workflow 검사 8개가 포함되며 중복 합산하지 않는다. Python 94·97은 앞선 중간 실행이고 UI 335는 동작 변경 없이 기존 실행 결과를 유지한 것이다. 실제 TEST 자료 수집·쓰기 성공을 뜻하지 않는다. 최종 Python은 99개·3.082초·실패 0·skip 0이며 Codex의 실제 실행 도구 출력으로 확인했다. 별도 root stdout 파일은 저장되지 않아 로그 파일을 만들어 실행 증거라고 부르지 않는다. UI도 실제 실행 도구 출력 기준 335 통과·실패 0·skip 0이다.

```sh
PYTHONPATH=src:tests uv run --locked --extra test python -m unittest tests.test_audio_collection tests.test_recordings tests.test_species_profile tests.test_drf_parity tests.test_ingest_api tests.test_postgres_ingest tests.test_n8n_audio_collection -q
node --test tests/frontend/chat_ui.test.js
uv run graphify update .
```

 graphify는 9,752 nodes·21,231 edges·510 communities로 갱신됐다. SQL parser 부재로 SQL 5개 분석이 건너뛰어졌으며 테스트 skip 수와 다르다.

### 실제 TEST workflow·자료·제공 검증

확정된 실제 결과:

| 검증 | 실제 결과 | 증거 |
| --- | --- | --- |
| TEST 앱 | ARM64 이미지 배포 verified, network-none fixture smoke·배포 source manifest 검증 | `test-release.json` |
| PostgreSQL | NAS `.99:5433`의 `robingraph_test`, schema `ingest` 확인 후 `0005_audio_candidates.sql`만 추가; 적용 직후 후보 0개 | `test-audio-migration-receipt.json` |
| n8n Wait | execution `18180`, CLI 시작→서버 재개 성공. 설정 70초, 실제 71.435초, `deferred` 종료 | `wait-fixture-status.json` |
| Wait의 검증 한계 | fixture로 외부 요청 0·remote retry 0. 실제 CDN 429 응답 검증과 다름 | 동일 증거 |

### 수집·저장·중복 실행과 공개 차단

| 검증 | 결과 | 증거 |
| --- | --- | --- |
| 최초 성공 수집 | execution `18183`, `success`, `Passer montanus` 1개 `awaiting_review` | `collect-after-eof-fix-receipt.json` |
| 중복 실행 | execution `18184`, 같은 candidate ID·파일 SHA·원 metadata 반환 | `collect-repeat-receipt.json` |
| 실제 파일 | 289,857 bytes, SHA256 `eb776d11526454947d8a392a5b09f2da657b9c0bd5c6e4297e72016ff191a403` | 수집·preview 영수증 |
| 비인증 preview | 401 | `private-preview-http.json` |
| 인증 HEAD·range | HEAD 200, `audio/ogg`, 289,857 bytes; range 206, 128 bytes, `OggS` 확인 | 동일 증거 |
| 미공개 media | GET·HEAD 모두 404 | 동일 증거 |

후보는 정확한 `Passer montanus`와 `File:Passer montanus.ogg`의 조합이다. 원출처 page `16592315`, revision `1031017614`, 기존 metadata 조회 시각·hash, 제작자·CC BY-SA 3.0·2011-09-20·Moscow region, Russia·Calls를 보존했다. 기존 metadata 조회 시각을 이번 다운로드 시각으로 바꾸지 않는다. 한국 종의 녹음이라고 해서 국내 녹음으로 표시하지 않는다.

이번 실측은 pinned 참새 후보 1개 경로다. 임의 종의 자동 발견·전체 종 확장이나 최대 5개 batch의 실제 운영 처리를 완료했다고 일반화하지 않는다. `next_cursor=null`, `publication_automatic=false`였으며 다음 batch cursor 자동 저장에 의존하지 않는다. preview HTTP 검증 자체의 외부 CDN 요청은 0이었다. 공개 성공 경로는 mock/fixture 검증과 구분하며 실제 review/publish는 실행하지 않았다.

실측 후 workflow를 기본 `action=collect`, `limit=1`, 빈 `scientific_name`·`file_title`·`after_taxon_id`로 복원했다. 검토 관련 flag는 모두 false, `active=false`다. 복원 후 실행하지 않았다. 따라서 pinned 참새 실측과 일반 targets 시작 설정의 준비 상태를 구분한다. `workflow-final-config.json`에서 canonical 입력 일치와 자동 승인·공개 없음이 확인됐다.

독립 최종 상태 재조회에서 실제 TEST PG 후보 1개·`awaiting_review`·review 필드 없음·published 0, container 파일 289,857 bytes 및 SHA256·원 Commons SHA1·OggS 일치를 확인했다. 반복 전후 `metadata_fetched_at`·`updated_at`과 기존 pin raw/정규화 metadata·조회일이 유지됐다. Neo4j의 새 저장 source Recording/Evidence는 각 0개이고 기존 active pin 12개를 유지했다. 이 독립 검증의 provider 추가 요청·쓰기·실제 review/publish는 모두 0이다. 증거는 `final-independent-state-receipt.json`이다.

### 실제 브라우저 범위

인증된 TEST cache 파일을 읽어 격리 Chromium native control로 재생했다. HTTP 200·`audio/ogg`·289,857 bytes, `preload=none`, `autoplay=false`이며 재생 후 `readyState=4`, `currentTime=0.374616`, duration 11.001333초, decoded bytes 16,750, media error 없음이었다. CDN 추가 요청은 0이다. 이는 비공개 실제 파일의 브라우저 디코딩·재생 검사이며 자연 채팅/도감 UI 전체 흐름이나 사람의 청취 검증이 아니다.

첫 900ms 대기 관측에서는 `currentTime=0`으로 검사가 실패했다. `private-preview-browser-first-observation.json`에 보존하고 재생 시간 증가를 확인한 최종 `private-preview-browser.json`과 구분한다. 이 중간 결과를 삭제하거나 첫 시도부터 통과했다고 기록하지 않는다.

실제 basic-profile POST 15건에서 기존 지원 12종은 각 음원 1개, 가용성 후속 2종과 기존 미지원 1종은 각 0개로 확인했다. API metadata만 검증했고 사진·CDN·외부 음원 재생 요청은 하지 않았다. 수집한 참새도 기존 종이므로 이번 작업으로 공개 지원 종 수가 증가하지 않았다.

공개 publisher 성공은 mock 검사와 실제 TEST Cypher `EXPLAIN` 범위다. 실제 graph publish 쓰기, 사람의 청취·검토 승인과 운영 공개는 하지 않았다.

## 5. 배포 및 형상 관리

- 최종 TEST 이미지: `robingraph-api:test-n8n-audio-2456506a3985`.
- 최종 Source SHA256: `2456506a398537a76c1ede2f899f2991d4cd0c4c74e5302d8252b980b294ab65` (246 runtime 파일).
- 최종 Release: `n8n-audio-2456506a3985-479298`, ARM64, `verified`.
- Image ID: `sha256:3111a3e3b31956b8173ba0febefbfe089aa80ee57006e000f1f9efb0d46629ed`.
- n8n workflow ID: `rgAudioCollectionTest01`, 비활성·수동 실행 상태 유지.

- 초기 TEST 이미지: `robingraph-api:test-n8n-audio-fe45fcd86e2c` (socket 수정 전 이력).
- 초기 Source SHA256: `fe45fcd86e2cc707d787c9127ebec481c805ac396454cfb53f5354c5ef9f7426` (246 runtime 파일).
- 초기 Release: `n8n-audio-fe45fcd86e2c-f2c05a`, 상태 `verified`.
- Base revision: `34fbcdc259f066a8dd4e23e50fd18ac46e195818`. 미커밋 snapshot 배포이며 이번 commit/push/merge는 수행하지 않았다.
- TEST M4 host 저장 경로 `/Users/kimdove/robingraph-test/media/audio`를 container `/var/lib/robingraph/audio`에 연결한다. private env의 실제 값은 기록하지 않는다.
- 기존 signing key와 feedback experiment `33` 유지. Production 변경 없음.
- 증거: `docs/verification/assets/2026-11-05-n8n-bird-audio/`.

최초 실패 실행과 초기 배포 영수증은 삭제하지 않고 이력으로 보존했다. Production 배포·운영 workflow 활성화·Git 작업은 이번 승인에 포함되지 않는다.

## 6. 한계 및 후속 과제

실제 검토자가 비공개 preview에서 종 동정·녹음 내용을 확인하고 명시적으로 승인한 뒤 별도 publish해야 한다. 이번 자동 검사는 사람의 청취·승인 기록을 만들지 않았다. RG-409의 검증된 12종과 미검증 2종은 기존 상태를 보존한다. 이번 작업의 자동화 구현과 실제 자료 검토·공개 완료를 구분한다. 주기 실행은 비활성이며 cursor를 다음 수동 실행에 직접 옮겨야 한다. 이번에는 pinned 1종만 수집했고 일반 discovery 전체 범위·최대 5종 동시 batch·실제 provider 429는 미검증이다. 물리 기기·Safari·Firefox·사람의 실제 청취는 실행하지 않았다. 운영 전환과 실제 review/publish는 후속 승인·검토 범위다.

### 재현 자산

영수증·재현 스크립트는 `docs/verification/assets/2026-11-05-n8n-bird-audio/`에 보존했다. `deploy_n8n_audio_test.py`, `migrate_test_audio.py`는 실제 TEST 변경을 포함하는 당시 실행 자산이고 재조회 용도로 무조건 재실행하지 않는다. `verify-preview-http.py`, `verify-private-preview.cjs`, `verify-existing-support.cjs`는 실제 HTTP·cache 재생·기존 metadata 검증을 재현한다. 필요한 private env는 해당 환경에서 읽으며 비밀값은 파일에 내장하지 않았다. 임시 경로에서 실행했던 원본을 보존한 것이므로 새 실행에서는 출력 경로·대상과 환경을 먼저 확인한다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 범위·완료 기준]]

- [[Work/RobinGraph/백로그 상세/RG-409|RG-409 도감 새소리]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/2026-11-02-RG409-새소리지원종확대|수동 자료 확대·CDN 제한·검증 이력]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
