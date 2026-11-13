---
created: 2026-11-09
date: 2026-11-09
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, n8n, bird-audio, review]
---

# [RG-507] 운영 수집 점검·음원 검토 화면

## 요약

11월 8·9일 운영 하루 최대 5종 예약 실행을 읽기 전용으로 확인했다. 11/8은 2개 저장·3개 후보 없음으로 수집을 마쳤고 cursor를 저장했다. 11/9는 2개 저장·1개 후보 없음 뒤 제공자 요청 제한으로 1개를 보류하고 나머지 1개는 시도하지 않았다. n8n 자체 실행은 두 번 모두 success지만 11/9 수집 결과는 deferred이며 cursor를 진행시키지 않았다.

현재 운영 후보는 8개다. 파일이 있는 7개는 awaiting_review이고 모두 파일 SHA256이 일치한다. Falco tinnunculus 1개는 deferred·파일 없음이다. 사람의 검토와 공개는 수행하지 않았다. 사용자 승인에 따라 [TEST 검토 화면](https://robingraph-test.dove-nest.com/audio-review)을 구현·배포하고 실제 TEST 참새 후보 1개의 인증·미리듣기를 검증했다. 운영 후보 8개를 TEST로 복사하지 않았다. 운영 후보에 연결하는 화면 배포는 아직 하지 않았으며 별도 승인이 필요하다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 현재 근거 |
| --- | --- | --- |
| 요구사항 | 5종 예약 결과 점검·후보 검토 화면 | 11/8·9 실제 실행·운영 후보 읽기 감사 |
| 설계 | 읽기 전용 별도 인증·목록/필터/페이지/미리듣기 | 승인·공개·재시도 쓰기 버튼 제외 |
| 코드 / 설정 | 후보 GET·private preview 권한·static 화면 | 구현·검증 완료 |
| 실서비스 | TEST에 검토 화면 배포 완료 | 운영 화면 반영 승인 없음 |
| 검증 | 운영 감사·최종 회귀·실제 TEST 확인 | Python 54·UI 348 통과, 1280/390 실제 재생 |
| 형상 관리 | 미커밋 source snapshot | commit/push 없음 |

## 1. 작업 배경 및 문제 분석

11/7 변경한 하루 5종은 처리 대상 상한이며 성공 저장 5건 보장이 아니다. 이번 감사로 실제 저장·후보 없음·제공자 제한과 미시도를 구분했다. 저장 후보를 확인하려면 API·파일·출처를 따로 봐야 했으므로 읽기 전용 검토 화면으로 모으기로 했다.

Codex 리뷰에서 수집 시각과 출처 근거 조회 시각을 혼동할 수 있는 표시를 확인했다. 수집 시각은 data.metadata_fetched_at에서 전달하는 collected_at으로 구분하고, recording.evidence.retrieved_at은 출처 근거 시각으로 유지하도록 보완하고 회귀 검사를 통과했다. 기존 참새 자료의 출처 조회일을 이번 수집일로 표시하지 않는다.

## 2. 해결 방안 및 설계

Claude는 후보 목록 GET·기존 private preview의 별도 읽기 권한·환경 연결·API guard와 시험을 담당한다. Antigravity는 목록·필터·페이지·미리듣기·출처를 표시하는 static 화면을 담당한다. Codex는 계약·보안·시각 의미를 리뷰하고 통합 및 TEST 검증을 맡는다. Writer는 최종 근거 확인 후 저장소와 Vault를 기록한다.

- 읽기 전용 토큰은 메모리에서만 사용하며 URL·브라우저 storage에 저장하지 않는다.
- 기존 ingest 키로 후보 목록을 조회하는 권한은 허용하지 않는다.
- 승인·공개·재시도 API 쓰기 버튼을 만들지 않는다.
- TEST 실자료 1개로 동작을 검증한다. 운영 후보 8개를 TEST로 복사하지 않는다.
- 운영 후보를 새 화면에서 확인하는 배포는 별도 승인 후 진행한다.

## 3. 주요 구현 내용

| 파일 / 범위 | 구현 내용 |
| --- | --- |
| `api/drf/audio_views.py`, `openapi_audio.json`, `urls.py` | 후보 GET와 읽기 전용 인증·입력 검증·기존 preview 권한 분리 |
| `api/drf/application.py`, `views.py`, `api/services.py`, `cli.py`, `.env.example` | 화면 경로·설정 연결·별도 읽기 키 전달 |
| `ingest/audio.py`, `audio_collector.py`, `audio_store.py` | 후보 목록/저장 자료 조회·필터·페이지·수집 시각 전달 |
| `api/static/audio-review.html`, `.css`, `.js` | 목록·상태 필터·페이지·미리듣기·출처 표시, 키 메모리 보관과 연결 해제 |
| `tests/test_audio_review.py`, `tests/frontend/audio_review_ui.test.js` | 권한 경계·시간 의미·목록/재생/정리 회귀 |

위 소스 경로는 `src/robingraph/` 기준이다. 승인·공개·재시도 버튼은 없으며 읽기 키로 해당 쓰기 API를 호출해도 거부된다. 인증 실행 helper·키 파일·raw env는 문서 증거에 복사하지 않았다.

## 4. 검증 및 테스트 결과

### 실제 운영 읽기 감사

| 날짜 / 실행 | KST 실행 시간 | 결과 | cursor |
| --- | --- | --- | --- |
| 11/8 · 82125 | 03:00:00.230~03:00:12.275 | n8n success / 수집 finished, 2개 저장·3개 후보 없음 | 저장: avilist-taxon:v2025b:1083 |
| 11/9 · 84322 | 03:00:00.072~03:00:12.925 | n8n success / 수집 deferred, 2개 저장·1개 후보 없음·1개 제공자 제한·1개 미시도 | 저장하지 않음: 앞선 1083 유지 |

11/9 결과에 next_cursor가 반환돼도 cursor_saved=false이므로 실제 Data Table 진행으로 해석하지 않는다. 실제 prod 행은 11/8 저장값을 유지했다. active/current 버전은 d8f1c0c4-a745-4ed2-97f1-3388b7331f00으로 일치했다.

현재 PG robingraph.ingest의 파일 있는 검토 대기 종은 Passer montanus, Jynx torquilla, Picus canus, Dryocopus martius, Tetrastes bonasia, Dendrocopos leucotos, Dendrocopos major의 7개다. 모두 파일 SHA256 일치·review 필드 없음이다. Falco tinnunculus는 provider_rate_limited로 deferred이며 파일이 없다. 이번 감사 자체 DB 쓰기·provider 수집 호출·재실행·설정 수정·운영 배포는 0이다.

근거: docs/verification/assets/2026-11-09-bird-audio-review/audit-executions.json, audit-candidates.json, audit-summary.json.

### 운영 후보 목록 (감사 시점)

| 학명 | 상태 | 원출처 |
| --- | --- | --- |
| `Passer montanus` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Passer_montanus.ogg) |
| `Jynx torquilla` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Jynx_torquilla_-_Eurasian_Wryneck_XC561861.mp3) |
| `Picus canus` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Picus_canus_-_Grey-headed_Woodpecker_XC310918.mp3) |
| `Dryocopus martius` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Dryocopus_martius_-_Black_Woodpecker_XC311605.mp3) |
| `Tetrastes bonasia` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Tetrastes_bonasia_-_Hazel_Grouse_XC103672.mp3) |
| `Dendrocopos leucotos` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Feh%C3%A9rh%C3%A1t%C3%BA_fakop%C3%A1ncs_dob_-_Dendrocopos_leucotos.ogg) |
| `Dendrocopos major` | 검토 대기 · 파일 SHA256 일치 | [Commons](https://commons.wikimedia.org/wiki/File:Dendrocopos_major_-_Great_Spotted_Woodpecker_XC542957.mp3) |
| `Falco tinnunculus` | 제공자 제한 보류 · 파일 없음 | 저장된 recording 없음 |

새 국명은 생성하지 않았다. 링크는 원출처 확인용이며 각 파일의 사람 청취·동정·공개 승인을 뜻하지 않는다. 파일이 없는 보류 건은 원 음원의 확보 성공으로 세지 않는다.

### 최종 자동화·실제 TEST 검사

재현 명령:

```sh
PYTHONPATH=src:tests uv run --locked --extra test python -m unittest tests.test_audio_review tests.test_audio_collection tests.test_audio_collector tests.test_django_runtime tests.test_drf_parity -q
node --test tests/frontend/audio_review_ui.test.js tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
```

실제 브라우저는 `node /tmp/robingraph-audio-review-20261109/verify-review-browser.cjs`로 실행했다. 키를 비밀 파일에서 메모리로 읽는 이 실행 helper는 증거 폴더에 복사하지 않았고, 인증값 없는 결과 JSON·캡처만 보관했다.

최종 수집 시각 보완 후 Codex Python 54/54 통과·실패 0·skip 0·1.944초, 프런트엔드 348/348 통과·실패 0·skip 0·344.161625ms다. 중간 Python 1.974초 결과와 합산하지 않았다. 이 단위 검사는 mock/fixture이며 아래 실제 TEST와 구분한다.

| 실제 TEST 검증 | 결과 |
| --- | --- |
| 인증 | 무키 401, 기존 ingest 키 목록 401, 읽기 키 목록 200, 잘못된 limit 422 |
| 쓰기 차단 | 읽기 키로 stage/review/publish POST 각 401; 차단 probe 3회, 실제 권한·자료 쓰기 0 |
| 대상 | TEST 참새 `Passer montanus` 후보 1개·awaiting_review, 운영 자료 복사 0 |
| 1280px native 재생 | readyState 4, currentTime 0.293799, decoded 14,601 bytes |
| 390px native 재생 | readyState 4, currentTime 0.266783, decoded 14,070 bytes |
| 오디오 | 두 화면 duration 11.001333초·오류 없음, 클릭 전 자동 다운로드 0, 인증 blob 단일 재생 |
| 정리 | 빈 필터 전환 시 pause/remove/revoke, 연결 해제 시 키·목록 제거, storage 0 |
| 화면·네트워크 | overflow 0·page error 0·외부 CDN 요청 0 |

`actual-review-browser.json`과 실제 화면 캡처 2장이 근거다. Codex가 실제 캡처를 시각 검토했다. 별도 `ui-fixture-browser.json`과 fixture 캡처 2장은 합성 API와 무음 WAV를 이용한 로컬 headless Chromium 검사이며 실제 TEST 재생 수치에 포함하지 않았다. 물리 청취·종 동정·실기기·Safari/Firefox는 검증하지 않았다.

`graphify update .`는 exit 0, 9,942 nodes·21,623 edges·533 communities다. SQL parser 누락으로 SQL 5개가 분석되지 않았으며 테스트 skip과 구분한다.

## 5. 배포 및 형상 관리

TEST ARM64 이미지 `robingraph-api:test-audio-review-f94bade119bd`, source SHA `f94bade119bd69faddbb28c6ff4dde24d525af8dde7e8057a2b9be2288aac973`의 251개 파일 snapshot을 배포했다. base HEAD는 `9ddea52`이며 미커밋 source snapshot이다. network-none fixture와 실제 TEST health/API 확인을 통과했다. 직전 `n8n-audio-2456506a3985` 배포는 보존했고 롤백은 실행하지 않았다. 영수증은 `test-release.json`이다.

화면 주소는 https://robingraph-test.dove-nest.com/audio-review 이다. TEST 호스트의 별도 읽기 키는 `/Users/kimdove/robingraph-test/private/audio-review.key`에 mode 600으로 보관한다. 권한 있는 사용자가 해당 파일에서 키를 확인해 화면에 입력하며 값 자체를 URL·문서·로그·Git에 복사하지 않는다. 이번 문서에는 경로만 기록했다.

운영 수집 workflow·DB는 읽기 감사만 했고 검토 화면을 운영에 배포하지 않았다. 후보 승인·공개 및 Git commit/push는 수행하지 않았다. 기존 11/7 미커밋 문서와 과거 이력은 보존했다.

## 6. 한계 및 후속 과제

- 두 번의 실제 5종 batch는 장기간 반복 안정성 보장이 아니다. 11/9 제공자 제한과 미시도를 그대로 보존한다.
- 저장·자동 디코딩·파일 hash 확인은 사람의 동정·청취·출처 검토를 대신하지 않는다.
- 후보 7개 검토 대기·1개 deferred를 성공 수집 8개로 합산하지 않는다.
- RG-507은 진행 중을 유지한다. RG-409와 11/5·6·7의 역사 기록은 보존한다.
- 운영 후보에 대한 화면 연결·Production 배포와 실제 사람 검토·공개는 후속 승인/검증 범위다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 수집·검토·저장]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
