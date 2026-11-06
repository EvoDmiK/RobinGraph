---
created: 2026-11-05
date: 2026-11-05
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, n8n, bird-audio, production]
---

# [RG-507] 운영 n8n 새소리 하루 1종 수집

## 요약

사용자가 운영 n8n에 새소리 수집을 적용하고 하루 1종 자동 수집을 실행하도록 승인했다. 자동화 범위는 후보 수집·저장까지이며 사람의 청취·동정 검토와 공개는 별도 명시 절차로 유지한다. 기존 TEST 구현·검증 기록은 수정하지 않고 이번 운영 후속 기록과 분리한다.

NAS 내부 collection-only sidecar와 운영 PG 후보 스키마를 반영하고 실제 health·공개 경로 차단을 확인했다. 기존 공개 앱은 재시작·교체하지 않았다. 운영 n8n 수동 수집·중복 실행은 성공해 후보 1개를 검토 대기로 저장했다. 예약 실행 fixture에서 발견한 staticData cursor 보존 실패는 내장 Data Table로 전환해 검증했고, 최종 workflow를 매일 03:00 Asia/Seoul·1종 수집으로 활성화했다. 첫 실제 정기 수집 예정은 2026-11-06 03:00 KST이며 이 기록 시점에는 아직 발생하지 않았다. Git commit/push/merge는 승인 범위에 포함되지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 운영 수집 적용·하루 1종 자동 실행 | 후보 수집과 사람의 검토·공개를 분리 |
| 설계 | 운영 target guard·수집 전용 sidecar | 공개 앱과 분리, 호스트 포트 0, publish/media 비활성 |
| 코드 / 설정 | 수집 전용 sidecar·Data Table cursor | Claude backend, Antigravity workflow·배포, Codex 리뷰·통합 |
| 배포 | NAS sidecar·PG 0005 반영 | 공개 앱 ID·시작 시각·환경 hash·mount 유지 |
| 검증 | 통합 34개 통과·실제 수동 수집 | trigger 간 cursor 보존·발행 버전 일치 확인, 첫 정기 수집은 예정 |
| 형상 관리 | 별도 sidecar와 workflow 반영 | Git commit/push/merge 미실행 |

## 1. 작업 배경 및 문제 분석

앞선 TEST에서는 n8n 수동 수집과 참새 후보 1개 저장, 미검토 공개 차단, 인증 preview·native 재생, 중복 처리 및 Wait 재개를 검증했다. 이 결과는 운영에 후보가 저장되거나 운영 스케줄이 활성화됐다는 뜻이 아니다.

운영 앱은 TEST의 새소리 수집 구현과 같은 상태라고 가정할 수 없다. 운영의 기존 이미지 digest와 revision을 기준으로 필요한 runtime 8개 파일만 overlay한 sidecar를 만들었다. 관련 없는 미커밋 변경을 공개 앱에 승격하지 않았고, 기존 공개 앱을 그대로 두었다.

## 2. 해결 방안 및 설계

Claude는 backend 수집 전용 실행·운영 target guard·필요한 migration을 담당한다. Antigravity는 운영 n8n workflow·NAS 배포·실제 실행을 담당한다. Codex는 담당 결과 리뷰·통합·최소 리팩토링을, Writer는 문서·Obsidian·백로그 동기화를 맡는다.

- 매일 03:00 `Asia/Seoul`, 1종을 기본으로 한다. 운영 workflow는 collect/status만 수행하도록 제한한다. 422는 관측 가능한 skip을 남기고 다음 대상으로 진행하지만 429·5xx에서는 cursor를 진행시키지 않는다. staticData schedule 영속화 실측이 실패해 내장 n8n Data Table에 cursor를 저장하도록 수정했다. 앱 API·DB 스키마·sidecar rebuild를 추가하지 않고 실제 trigger 간 저장값 보존을 검증했다. 최종 main daily 활성화와 발행 버전 일치를 재조회했다.
- 자동 수집 후보는 미검토 상태로 저장한다. 자동 decode 성공을 사람의 청취·동정 승인으로 바꾸지 않는다.
- 사람의 검토와 공개는 별도 절차다. 운영 수집 승인만으로 임의 review/publish를 실행하지 않는다.
- 정확한 출처·라이선스·종 범위·원 metadata와 파일 hash를 보존한다.
- 외부 제한은 Retry-After·소량 처리·backoff를 지키고 gateway 오류·provider 응답·내부 오류를 분리한다.
- 내부 통신 경로·인증 저장 방식과 TLS 적용 여부는 실제 환경 기준으로 남기며 인증 값은 기록하지 않는다.

## 3. 주요 구현 내용

| 구현 / 설정 | 실제 반영 범위 |
| --- | --- |
| collection-only sidecar | 공개 앱과 분리된 `robingraph-audio-collector`, 필요한 runtime 8개 overlay |
| 운영 PG | `.99:5433 / robingraph / ingest`, `0005_audio_candidates.sql`로 table 1개·index 1개 추가 |
| 내부 네트워크 | `homelab_default`, host port 0, user `10001:10001`, read-only rootfs |
| NAS 저장 volume | `/volume3/Birds-Nest/docker-data/robingraph-audio/audio` |
| 자원 제한 | memory 512m, CPU 0.5 |
| 공개 경계 | health `prod`, `publication_enabled=false`; publish·public media 경로 404 |
| 기존 공개 앱 | container ID·started_at·image ID·환경 hash·mount 유지, 재시작 없음 |

운영 n8n의 기존 workflow 40개·credential 33개를 기준으로 전후 보존을 확인한다. self API key는 승인된 기존 credential 범위에서 hot API HTTP 200을 확인했으며 실제 값은 기록하지 않는다. 최종 workflow 생성·활성·발행 버전은 실제 영수증으로 확인했다. `n8n-final-inventory-comparison.json`에서 기존 workflow 40개는 모두 보존됐고 신규 3개(일일 수집 1개 활성·fixture 2개 비활성)가 추가됐다. credential은 33→34개로 신규 1개가 추가됐고 기존 33개의 ID·이름·종류와 31개의 cipher hash는 유지됐다. Gmail·Google Drive OAuth2 credential 2개의 hash 변경은 관측됐지만 원인은 미확정이며, 이번 작업에서 해당 두 credential 값을 읽거나 수정·사용한 횟수는 0이다. 기존 trigger 실행·갱신 시각상 자동 갱신 가능성만 있으므로 전체 불변·원인 확정·복원을 주장하지 않는다. 근거는 `oauth-hash-change-context.json`이다.

### 변경 파일과 실행 경로

runtime overlay는 `ingest/audio_collector.py`, `audio.py`, `audio_store.py`, `api/drf/audio_views.py`, `retrieval/recordings.py`, `commons_bird_recordings.json`, `ingest/migrations/0005_audio_candidates.sql`, `config/source-registry.json`의 8개다. `python -m robingraph.ingest.audio_collector`로 수집 전용 앱을 실행한다. 경로별 hash와 기존 base source 보존 근거는 `sidecar-promotion-manifest.json`에 보관했다. 해당 manifest의 mutation 0은 배포 전 작성 시점의 값이며 현재 운영 변경이 없다는 뜻이 아니다.

workflow 생성·관리 코드와 Production artifact는 기존 TEST artifact와 분리했고 최종 생성 검사에서 두 artifact 모두 일치했다. cursor는 Data Table의 prod key를 사용하며 staticData에 의존하지 않는다. 별도 header·오류 안내 문구 정리에는 로직 변경이 없었다.

## 4. 검증 및 테스트 결과

### 자동화 검사

최종 Codex 통합 focused 검사 34개(collector 3·audio 20·workflow 11)가 2.449초에 통과했다. 앞선 2.317초 실행과 중복 합산하지 않는다. 담당 backend 자체 23개와 exact production source 검사 3개는 범위가 겹치므로 합산하지 않는다. network-none 이미지 fixture는 provider 요청·DB 연결 없이 health 및 제한된 경로 동작을 확인했다. 앞선 TEST Python 99·UI 335는 기존 작업 이력이며 이번 운영 검증으로 합산하지 않는다.

graphify 최종 갱신은 9,823 nodes·21,405 edges이며 SQL parser 부재로 SQL 5개가 분석에서 빠졌다. 테스트 skip 수와 구분한다.

### 실제 운영 검증

확정된 실제 결과는 다음과 같다.

| 검증 | 결과 | 근거 |
| --- | --- | --- |
| Production schema | `0005_audio_candidates.sql` 적용, 기존 ledger 0001~0004 checksum 유지, 직후 후보 0개 | `migrate-receipt.json` |
| 새 sidecar | healthy, health의 target prod·publication false | `start-receipt.json` |
| 비인증 내부 status | 401 | 동일 영수증 |
| publish/public media | 각 404 | 동일 영수증 |
| 기존 공개 앱 | 재시작 없음·동일 identity와 환경 유지 | build/start/migrate 영수증 |

이 배포 검증 시점의 provider 요청·graph publication은 0이었다. 이후 실제 n8n 수집 결과와 혼합하지 않는다. 최종 운영 n8n 실제 결과는 다음과 같다.

| 실행 / 검증 | 결과 |
| --- | --- |
| 수동 수집 `76267`·중복 `76280` | success, 참새 후보 1개 `awaiting_review` |
| Data Table trigger `76374`·`76375` | fixture key 1→2 저장·GET 재조회, provider 0, prod cursor 불변 |
| 최종 native graph status `76393` | 기존 후보 조회 success, 추가 수집·cursor 저장 없음 |
| workflow 활성화 | API 200·`active=true` |
| 발행 버전 | active/current 모두 `45fee2c2-a0ea-46e0-8a43-a8d5c65f4dec` |
| 발행 graph | canonical node·connection 일치, 19개 node ID 모두 고유 |
| runtime 설정 | timezone `Asia/Seoul`, 매일 03:00, 수집 1종 |
| 정리 | staticData/Data Table fixture 2개 모두 비활성 |

실제 workflow는 [RobinGraph Audio Collection PROD](https://workflow.dove-nest.com/workflow/rgAudioCollectionProd01)다. ID는 `rgAudioCollectionProd01`이다. runtime 설정을 직접 재조회했고 history에는 settings snapshot이 없으므로 history에 동일 설정이 있었다고 주장하지 않는다. Data Table과 workflow의 project는 `YvRaBfnmwjtcKmfS`로 일치한다.

첫 정기 수집은 2026-11-06 03:00 KST 예정이며 아직 관측하지 않았다. 실제 수동 수집 성공, 별도 trigger fixture 영속화, 스케줄 활성 설정을 검증한 사실을 첫 daily 실행 성공으로 합쳐 보고하지 않는다.

### 운영 후보 독립 상태 확인

최종 독립 읽기 검증에서 운영 `robingraph.ingest` 후보 1개 `awaiting_review`·review 필드 없음·published 0, 파일 1개 289,857 bytes를 확인했다. SHA256 `eb776d11526454947d8a392a5b09f2da657b9c0bd5c6e4297e72016ff191a403`과 원 Commons SHA1이 일치한다. 인증 preview HEAD 200·range 206(128 bytes), 비인증 401, publish·public media 404였다.

Neo4j stored Recording/Evidence는 0개다. 기존 공개 앱 ID·시작 시각·환경 hash·mount는 불변이다. TEST DB를 복사하지 않았고 운영에서 새 metadata 조회 시각을 기록했다. 독립 검증은 추가 provider 요청이나 쓰기를 하지 않았다. 출처 저장·자동 decode 검증이 사람의 청취·동정 승인이라는 뜻은 아니다. 근거는 `final-independent-state-receipt.json`이다.

### 실제 수집 성공과 예약 cursor 실패 이력

운영 수동 collect execution `76267`과 repeat `76280`은 성공했고 후보 1개는 `awaiting_review`다. 실제 review/publish 성공으로 해석하지 않는다.

별도 활성 5초 schedule fixture는 trigger execution 9개가 모두 성공 상태였지만 각 실행의 counter가 계속 1이었고 persisted staticData는 null이었다. `static-cursor-fixture.json`·`static-cursor-counters.json`의 판정은 `passed=false`다. 실행 success만으로 cursor 영속화 성공을 주장하지 않는다. 당시 fixture를 비활성화하고 main daily workflow도 비활성으로 유지한 뒤 수정·재검증했다.

이 현상은 현재 운영 n8n 2.15 구성에서 관측한 결과다. 외부 runner 등 특정 구성 요소가 원인이라는 증거는 아직 없으므로 원인을 단정하지 않는다. Codex는 내장 n8n Data Table을 사용하는 대안을 선택했고 담당자가 구현했다. 내장 Data Table `RobinGraph Audio PROD cursor`를 생성하고 `prod`의 초기 cursor를 빈 문자열로 seed했다. Table ID는 `J49mL4EifvZ0Pres`, project는 `YvRaBfnmwjtcKmfS`이며 string column 2개 `cursor_key`·`after_taxon_id`를 사용한다. 다른 table 변경은 0이다. 최초 API 요청의 공백 encoding 문제로 400이 발생했지만 생성 전·쓰기 0이었고 encoding 수정 후 생성에 성공했다. Table 생성 자체와 별도로 실제 반복 trigger fixture를 검증했다. execution `76374`에서 fixture key가 1, `76375`에서 2가 됐고 GET row 재조회에서도 저장값을 확인했다. 운영 `prod` key의 빈 cursor는 그대로였으며 fixture는 종료 후 비활성화했다. provider 요청은 0이다. `datatable-cursor-fixture.json`은 이 결과를 보존한다. 이후 main daily 활성화는 최종 영수증과 active-version 재조회로 확인했다. 앞선 실패 파일과 수치는 보존한다.

workflow 통합 중 Prepare Summary 노드 이름만 바뀌고 이전 UUID가 남아 중복 ID가 발견됐다. 최초 회귀 검사는 전체 19개 대비 unique 18개로 실패했고, 기존 `node_id` helper를 재사용해 19개 고유 ID로 수정했다. 최종 34개 focused 검사와 두 artifact 생성 검사가 통과했다. TEST workflow artifact는 byte 단위로 변경되지 않았다. 이 문제는 실제 수집 자료 오류로 기록하지 않는다.

## 5. 배포 및 형상 관리

- Base Production image: `ghcr.io/evodmik/robingraph@sha256:963b4836ccf77155a8ca94efa105e66c60f799d05e75f6ae6c5b6ce710b05edc`.
- Base revision: `5056ccba9e75a891cc133a6f371b49deb5dbc598`.
- 새 sidecar image: `robingraph-audio-collector:prod-3cfe50a76a47`, AMD64.
- Image ID: `sha256:375dbedd980550b27103829e96a882e181ef9837208cee5cc0e68dbe7c1d79da`.
- Runtime overlay 8개이며 기존 base source는 보존했다.
- 운영 DB에 승인된 추가 스키마만 반영했고 공개 앱 교체·재시작은 없었다. 수동 수집·상태 조회 및 workflow 활성화까지 확인했다.
- 증거 보관: `docs/verification/assets/2026-11-05-n8n-bird-audio-production/`.

Git commit/push/merge는 이번 요청에 포함되지 않아 수행하지 않았다. 기존 TEST 배포·수동 실행 기록은 역사로 보존한다.

## 6. 한계 및 후속 과제

자료 수집 자동화는 사람의 청취·종 동정·자료 공개 검토를 대신하지 않는다. 이번 구현으로 공개 지원 종 수가 늘었다고 추정하지 않는다. RG-409의 공개 12종·가용성 후속 2종은 TEST의 기존 범위다. 운영 공개 앱은 revision `5056ccba9e75a891cc133a6f371b49deb5dbc598`로 보존되어 이번 수집 적용이 운영 도감에 12종 재생 UI를 반영한 것은 아니다. RG-507의 운영 수집은 사용자 승인을 받아 반영했고 사람의 검토·공개는 대기하며, RG-409의 운영 승인 상태는 변경하지 않는다. 운영 수집 적용·예약 활성화 범위는 완료했으나 실제 사람의 검토·공개가 남아 RG-507 상태는 `in_progress`로 유지한다. RG-507 수집 부분을 운영 미승인으로 표기하지 않는다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 수집·검토·저장]]
- [[Work/RobinGraph/작업기록/5xx 데이터·분류·이름/2026-11-05-RG507-n8n-새소리수집검토저장|앞선 TEST 구현·검증 기록]]
- [[Work/RobinGraph/백로그 상세/RG-409|RG-409 도감 새소리]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
