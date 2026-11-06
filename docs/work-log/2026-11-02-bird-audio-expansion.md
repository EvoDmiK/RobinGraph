---
created: 2026-11-02
date: 2026-11-02
project: RobinGraph
type: worklog
status: completed
task_id: RG-409
backlog_status: in_progress
tags: [worklog, robingraph, bird-audio]
---

# [RG-409] 새소리 지원 종 확대

## 요약

사용자 승인에 따라 자료를 검토하고 실제 CDN 재생을 확인한 **12종(기존 3종 + 신규 9종)**을 이번 공개 지원 범위로 확정했다. 앞서 자료 적합성을 확인한 14종 중 Picus canus·Corvus corone는 외부 음원 가용성 검증이 남아 공개 지원에서 제외한다. 종 동정·라이선스가 잘못된 자료라는 뜻은 아니다. 국내 기록 종이라는 사실은 흔한 텃새 또는 국내에서 녹음한 음원이라는 뜻이 아니다.

14종 시안의 TEST 배포·graph 반영·HTTP 검사와 최초 재생 실패 이력은 보존한다. 초기 7종과 후속 5종, 고유 12종의 재생을 확인하고 최종 verified catalog의 코드 검증·TEST 배포·graph 반영·HTTP 15건 검증까지 완료했다. RG-409는 진행 중이며 Production·Git commit·push·병합은 수행하지 않았다. 기존 3종 구현·앞면 컨트롤·등급별 색상 기록은 당시 이력으로 보존한다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 새소리 지원 종 확대 | 최종 공개 범위 기존 3종 + 신규 9종; 자료 검토 14종 이력 보존 |
| 설계 및 해결 방안 | 기존 import·graph·API 재사용 | 신판 source release·원 MIME·행별 조회 시각 보존 |
| 코드 / 설정 수정 | Python·자료·스크립트·registry·검사 | JS/CSS·API 필드 변경 없음 |
| 실서비스 배포 | 최종 12종 TEST verified | test-audio-expansion-3b02d8bd3db8 |
| 검증 및 테스트 | 최종 Python 65·HTTP 15/15·실재생 고유 12종 | graph 전체14 = 활성12 + 가용성 대기 시안2 |
| 형상 관리 | 미커밋 snapshot | Production·commit·push·병합 없음 |

## 1. 작업 배경 및 문제 분석

기존 MVP는 참새 Passer montanus·직박구리 Hypsipetes amaurotis·청둥오리 Anas platyrhynchos의 검토된 녹음을 제공했다. 사용자는 이 기능을 유지하면서 지원 종을 늘리도록 승인했다.

초기 약 15~20종은 조사 목표였고, 중간 후보 15종 중 순수 음원 guard에 맞지 않는 파일을 제외해 자료 적합성 검토를 마친 14종 시안을 만들었다. 실제 음원 가용성까지 확인한 최종 공개 범위는 12종이다. 숫자를 맞추기 위해 불확실한 동정이나 다른 종의 녹음을 대체하지 않았다. 검토한 파일 중 mp3가 포함돼 기존 고정 graph format 대신 원 MIME을 보존할 필요가 있었다.

## 2. 해결 방안 및 설계

### 최종 공개 범위 조정

최초 14종 시안에서 재생에 성공한 12종만 `commons-reviewed-2026-11-02-verified`로 제공하도록 catalog·source pin·테스트를 조정했다. Picus canus는 추가 Range 진단에서 다시 HTTP 429·Retry-After 600초, Corvus corone는 ORB이며 직접 HTTP 응답은 미확인이다. 추가 요청은 중단했다. 두 자료는 graph의 이전 release 시안으로 보존하고 삭제·policy 변경 없이 verified release 조회에서 제외했다. 최종 graph reader와 공개 HTTP에서 지원 12종 각 1개·보류 2종 각 0개를 확인했다.

### 최종 공개 지원 12종 목록

| 구분 | 학명 | 최종 상태 |
| --- | --- | --- |
| 기존 3종 | Anas platyrhynchos; Hypsipetes amaurotis; Passer montanus | 실제 재생 확인·verified catalog 포함 |
| 신규 9종 | Ardea alba; Ardea cinerea; Dryocopus martius; Cuculus canorus; Fulica atra; Hirundo rustica; Motacilla alba; Nycticorax nycticorax; Streptopelia orientalis | 실제 재생 확인·verified catalog 포함 |
| 시안 유지 2종 | Picus canus; Corvus corone | 가용성 검증 대기·최종 앱 조회에서 제외 |

Codex가 최초 7종과 재시도 5종의 고유 재생 PASS 집합이 최종 catalog 12종 학명 집합과 정확히 같음을 확인했다. 이는 최종 배포 후 음원 12개를 다시 요청한 검사가 아니라 기존 실제 재생 근거와 최종 목록의 집합 대조다.

### 14종 자료 검토와 시안 이력

공식 Commons title·description·page/revision·저작자·라이선스를 검토하고 활성 AviList의 정확한 species와 연결했다. 한국조류학회 목록·AviList 분포 근거의 국내 기록 확인과 녹음 장소를 구분한다. 아종 분포 문구가 국내 근거에 포함돼도 녹음 관계는 확인된 species에만 연결한다.

당시 시안 catalog는 `commons-reviewed-2026-11-02`이며 14종·14파일이었다. 시안은 `application/ogg` 11개와 `audio/mpeg` 3개였고, 최종 verified 공개 목록은 OGG 9개와 MP3 3개다. 기존 3종의 raw dict·page/revision·원 조회 시각은 그대로 두고 신규 자료에 실제 조회 시각을 기록했다. Codex가 원본 3종 불변을 독립 assert로 확인했다.

공식 CC HTTP 3.0 URL은 공식 호스트의 정확히 같은 허용 경로에 한해 HTTPS로 정규화한다. 임의 URL 허용이나 raw metadata 변조로 확장하지 않는다. 날짜·지역·유형이 원문에 없으면 null을 유지한다.

### 검토 자료 14종 시안과 출처

기존 3종의 출처·라이선스는 10/30 작업기록과 catalog에 보존돼 있다. 아래는 14종 시안에 포함된 신규 11종의 검토 출처다. Picus canus·Corvus corone도 자료 검토표에는 남기되 최종 공개 지원에서는 제외했다. source-review의 exact species를 사용하며, manifest에서 국명이 null인 항목에 임의 국명을 붙이지 않았다.

| 학명 | Commons 출처 | 저작자 | 라이선스 | MIME |
| --- | --- | --- | --- | --- |
| Ardea alba | [공식 파일](https://commons.wikimedia.org/wiki/File:Ardea_alba_-_Great_Egret_XC131650.ogg) | Jonathon Jongsma | cc-by-sa-3.0 | application/ogg |
| Ardea cinerea | [공식 파일](https://commons.wikimedia.org/wiki/File:Ardea_cinerea_-_Grey_Heron_XC432231.mp3) | Joost van Bruggen | cc-by-sa-4.0 | audio/mpeg |
| Dryocopus martius | [공식 파일](https://commons.wikimedia.org/wiki/File:Black_woodpecker_Dryocopus_martius_female_drumming.ogg) | SanoAK: Alexander Kürthy | cc-by-sa-4.0 | application/ogg |
| Cuculus canorus | [공식 파일](https://commons.wikimedia.org/wiki/File:Cuculus_canorus.ogg) | Vladimir Yu. Arkhipov, Arkhivov | cc-by-sa-3.0 | application/ogg |
| Fulica atra | [공식 파일](https://commons.wikimedia.org/wiki/File:Fulica_atra_-_Eurasian_Coot_XC467829.mp3) | Mikko Heikkinen | cc-by-sa-4.0 | audio/mpeg |
| Hirundo rustica | [공식 파일](https://commons.wikimedia.org/wiki/File:Hirundo_rustica_-_Barn_Swallow_-_XC83449.ogg) | Jonathon Jongsma | cc-by-sa-3.0 | application/ogg |
| Motacilla alba | [공식 파일](https://commons.wikimedia.org/wiki/File:Motacilla_alba_-_White_Wagtail_XC466458.mp3) | Pascal Christe | cc-by-sa-4.0 | audio/mpeg |
| Nycticorax nycticorax | [공식 파일](https://commons.wikimedia.org/wiki/File:Nycticorax_nycticorax_-_Black-crowned_Night_Heron_-_XC99573.ogg) | Jonathon Jongsma | cc-by-sa-3.0 | application/ogg |
| Picus canus | [공식 파일](https://commons.wikimedia.org/wiki/File:Picus_canus.ogg) | Vladimir Yu. Arkhipov, Arkhivov | cc-by-sa-3.0 | application/ogg |
| Streptopelia orientalis | [공식 파일](https://commons.wikimedia.org/wiki/File:Streptopelia_orientalis.ogg) | boppochan | cc-by-sa-3.0 | application/ogg |
| Corvus corone | [공식 파일](https://commons.wikimedia.org/wiki/File:XC24828_-_Zwarte_Kraai_-_Corvus_corone.ogg) | Sander Pieterse | cc-by-sa-4.0 | application/ogg |

공식 metadata batch 조회 시각은 `2026-11-02T07:45:47.514604+00:00`, 응답 SHA는 `784c5cda92240ed36a635a39ce43a69820c601328d44aff393f0513686169772`다. 초기 병렬 검색은 HTTP 429를 받아 중단했고 반복 검색하지 않았다. 이후 공식 category에서 파일 제목을 확인해 metadata batch를 조회했다.

### 제외한 자료

| 후보 | 제외 근거 |
| --- | --- |
| Anas crecca | description에 “Identification uncertain; probably a teal”이 있어 검증된 종 음원으로 채택하지 않음 |
| Pica serica | Pica pica 음원을 다른 종의 대체물로 사용하지 않음 |
| Parus cinereus | Parus minor 음원을 다른 분류 개념으로 대체하지 않음 |
| Garrulus glandarius | MIME은 application/ogg지만 width 1280·height 720이므로 기존 순수 오디오 guard에 부적합; 중단 지시 이후 추가 대체 검색 없음 |

## 3. 주요 구현 내용

| 파일 | 변경 내용 |
| --- | --- |
| `src/robingraph/retrieval/commons_bird_recordings.json` | 시안은 원본3+신규11, 최종은 원본3+재생 확인 신규9로 한정 |
| `src/robingraph/retrieval/recordings.py` | 신판 SOURCE_RELEASE, 원 MIME, 공식 동일 경로 라이선스 URL 정규화 |
| `scripts/import_reviewed_recordings.py` | 신판 catalog를 기존 import 경로에 반영 |
| `config/source-registry.json` | 검토 출처 신판 등록 |
| `tests/test_recordings.py` | 확대 catalog·기존 자료 보존·format/license 회귀 검사 |

API 필드는 추가하지 않았다. JS/CSS와 앞면 컨트롤·뒷면 출처·등급별 팔레트는 변경하지 않았다. UI 담당은 별도로 catalog를 검토해 원자료에 없는 날짜·location이 null이고 당시 시안에 검토한 14종만 포함됨을 확인했다. 최종 12종은 Codex가 재생 PASS 집합·catalog·실제 API의 모든 녹음 필드를 대조해 일치 확인했다.

## 4. 검증 및 테스트 결과

### 자동화·fixture

```sh
PYTHONPATH=src:tests uv run --locked --extra test --extra tracing python -m unittest tests.test_recordings tests.test_species_profile tests.test_birdbase_traits tests.test_drf_parity -q
uv run graphify update .
```

- 14종 시안 Codex 통합 Python **65 통과·0 실패·0 건너뜀**, 1.657s.
- 최종 verified 12종 코드에 같은 명령 재실행: **65 통과·0 실패·0 건너뜀**, 1.843s. 두 실행을 합산하지 않는다. 근거는 `root-python-tests-verified12.log`; graphify 최종 12종 갱신도 exit 0이다.
- backend의 recordings·profile 검사 38 통과는 별도 실행 범위이며 65에 합산하지 않는다.
- dry-run 14개·쓰기 0. 이는 실제 DB 반영 성공 검사와 구분한다.
- network-none fixture smoke·실제 manager verify 통과. graphify exit 0이며 기존 SQL parser 경고는 유지됐다.
- JS/CSS가 변경되지 않아 frontend 338건은 이번에 재실행하지 않았다. 직전 등급 색상 작업의 실행 이력과 분리한다.

### 14종 시안의 실제 TEST graph 쓰기·반복 검증

쓰기 전 `bolt://192.168.219.98:7687` / `neo4j` / `rg:concept-set:avilist-v2025b` / `v2025b`를 확인하고 Codex가 해당 TEST catalog 반영 범위를 승인했다. 기존 자료 3개를 공개 필드 백업한 뒤 guarded upsert를 두 번 실행했다.

| 확인 항목 | 실제 결과 |
| --- | --- |
| Recording / EvidenceUnit | 각각 3 → 14 |
| HAS_RECORDING / SUPPORTED_BY | 각각 3 → 14 |
| 두 번째 import 후 개수 | 각 14 유지, 노드·관계 중복 0 |
| 실제 reader | 14종 모두 각 1개 |
| 실제 아종 조회 / 전체 아종 연결 | Anas platyrhynchos platyrhynchos 0개 / 아종 연결 0 |
| 대상 14 Taxon 속성 SHA | 전후 동일 |
| 다른 source Media/Evidence | source별 개수 동일 |
| vector index 2개 | identity·설정 동일, 삭제·교체 없음 |

대상 Taxon 속성 SHA는 `46197c700e42f7b144af054df7012470c61082dfb97916bd1a9bb9eff391658c`다. 이 검사는 전체 DB checksum 동일을 주장하지 않는다. PostgreSQL·Production 쓰기는 수행하지 않았다.

기존 3종 ID와 source payload(조회 시각·metadata hash 포함)는 보존됐다. graph projection에서는 MediaAsset의 `format`이 고정 `audio/ogg`에서 원 MIME `application/ogg`로 바뀌었고, Media/Evidence의 `source_release`가 10/30에서 11/02로 전환됐다. 따라서 기존 graph 모든 필드가 불변이라는 뜻은 아니다. 실제 전환 목록과 공개 백업은 영수증에 보관했다.

### 최종 verified 12종 TEST graph 반영

`test-verified-expansion-import-receipt.json`에서 실제 지원12종 reader 각1개, Picus canus·Corvus corone 각0개를 확인했다. graph 전체 Recording/Evidence/HAS_RECORDING/SUPPORTED_BY는 각각14개를 유지하며, 그 구성은 active verified12 + 이전 시안 보존2다. 두 보류종은 기존 속성·관계를 모두 보존하고 삭제하지 않았다.

이번 최종 반영에서 12종의 source_release가 `commons-reviewed-2026-11-02`에서 `commons-reviewed-2026-11-02-verified`로 전환됐다. 기존3 payload는 그대로이고 아종 연결·중복0, 대상 Taxon 속성·다른 source 개수·vector identity 보존을 확인했다. 전환 전 원시안14의 공개 백업은 `verified-fourteen-graph-backup.json`에 남겼다. PostgreSQL·Production 쓰기나 실제 롤백은 하지 않았다.

### 실제 HTTP·브라우저

14종 시안의 실제 GET 프로필 검사는 지원 14종 각각 녹음 1개 available, 미지원 Treron sieboldii는 0개 no_licensed_recording으로 총 15개 프로필을 확인했다. 이 결과는 음원 실제 재생 성공과 별개다.

첫 실제 native 재생 검사는 **14종 중 7개 통과·7개 실패**였다. Cuculus canorus는 10초 timeout, 나머지 6개는 MediaError 4였고 최초 시점에는 서버 응답을 포착하지 못했다. 후속 브라우저 진단에서는 실패 7개 모두 ORB 차단이 관측됐다. 대표 Cuculus canorus의 CDN range GET은 **HTTP 429·text/html·Retry-After 600초**, 응답 시작은 HTML doctype으로 확인됐다. 오디오 코덱 불일치로 단정하지 않는다. 직접 429 응답을 포착한 범위는 대표 1개이며 나머지 6개의 ORB 관측과 구분한다.

대표 응답 증거는 `single-cdn-response.json`이다. 08:03:03 UTC 응답 이후 추가 CDN 요청을 중단했다. Retry-After가 지난 08:13:47 UTC부터 실패 7개만 about:blank의 단일 native audio·사진/프로필 요청 없이 20초 간격으로 재검증했다. 실제 재시도에서 5개 통과·2개 실패였으며 처음 성공한 7개는 재시도하지 않았다. 처음 실패한 7개 결과는 원본으로 보존하고 후속 재검증으로 덮어쓰지 않는다. 후속 결과 고유 5종의 재생이 추가 확인돼 초기 7종과 합쳐 고유 12종 재생이 확인됐다. Picus canus·Corvus corone의 가용성은 남아 있어 14종 모두 재생 성공으로 기록하지 않는다. 최초 14종 harness의 single-play·DOM 제거·대화 지우기 후반 검사는 음원 접근 불가로 미실행이며 이전 UI 검사 성공과 분리한다.

| API 확인 국명 / 학명 | 첫 재생 | 후속 재생 | 최종 공개 |
| --- | --- | --- | --- |
| 참새 / Passer montanus | 통과 | 미실행(최초 통과) | 지원 |
| 직박구리 / Hypsipetes amaurotis | 통과 | 미실행(최초 통과) | 지원 |
| 청둥오리 / Anas platyrhynchos | 통과 | 미실행(최초 통과) | 지원 |
| 중대백로 / Ardea alba | 통과 | 미실행(최초 통과) | 지원 |
| 왜가리 / Ardea cinerea | 통과 | 미실행(최초 통과) | 지원 |
| 까막딱다구리 / Dryocopus martius | 통과 | 미실행(최초 통과) | 지원 |
| 뻐꾸기 / Cuculus canorus | 실패 | 통과 | 지원 |
| 물닭 / Fulica atra | 실패 | 통과 | 지원 |
| 제비 / Hirundo rustica | 실패 | 통과 | 지원 |
| 알락할미새 / Motacilla alba | 실패 | 통과 | 지원 |
| 해오라기 / Nycticorax nycticorax | 실패 | 통과 | 지원 |
| 청딱다구리 / Picus canus | 실패 | 실패 | 가용성 검증 대기 |
| 멧비둘기 / Streptopelia orientalis | 통과 | 미실행(최초 통과) | 지원 |
| 까마귀 / Corvus corone | 실패 | 실패 | 가용성 검증 대기 |

위 국명은 실제 API 응답에서 확인한 값이며 추측해 붙이지 않았다.

별도 실제 자연 채팅 “참새에 대해 알려줘” → 팝업의 native 재생·출처 버튼 Enter 이동·summary 초점·전환 정지 검사는 5개 항목이 통과했다. 390/1280 재열기·넘침 검증도 별도 결과로 보존한다. 이 LC 참새 흐름의 성공은 신규 11종 전체 음원의 성공을 뜻하지 않는다.

### 최종 verified release 공개 HTTP 확인

최종 앱·graph 반영 후 `POST /v1/chat`의 basic-profile 경로에 `defer_enrichment=true`, `defer_discovery=true`를 사용해 **15/15**를 확인했다. 지원 12종은 각1개 `available`, Picus canus·Corvus corone와 기존 미지원 Treron sieboldii는 각0개 `no_licensed_recording`이었다. 모든 프로필은 enrichment_pending이며 이 검사는 추가 CDN·사진·재생 요청0이다. API의 `available`은 현재 release에 연결된 허가 자료가 있다는 뜻이며 향후 외부 CDN 가용성 보증은 아니다.

최종 API의 녹음 필드가 현재 catalog와 정확히 일치하고, 공개 catalog12가 실제 디코딩 PASS 고유12와 같으며, 배포 runtime238개 SHA가 root 소스와 일치함을 Codex가 독립 assert로 확인했다. diff check도 통과했다. 최종 배포 후 음원12를 다시 요청한 것으로 중복 계산하지 않는다.

### 근거 보관

`docs/verification/assets/2026-11-02-bird-audio-expansion/`에 선정·제외·source fetch, target manifest, backend/root 검증, TEST import 영수증·기존3 공개 백업, 배포·실제 브라우저 및 동기화 증거를 선별 보관했다. 인증 정보·원본 API 토큰은 기록하지 않는다.

## 5. 배포 및 형상 관리

### 최신 verified 12종

| 항목 | 최종 결과 |
| --- | --- |
| image | `robingraph-api:test-audio-expansion-3b02d8bd3db8` |
| release | `audio-expansion-3b02d8bd3db8-eaa42b` |
| source SHA | `3b02d8bd3db8a89cd1c362c2075490e02d85e1bdda6a981942b53b046982ac1f` |
| image ID | `sha256:64a8702f70d89f40f656948136060674281662a64dcf4dc45e93c662edbd5da8` |
| source release | `commons-reviewed-2026-11-02-verified` |
| 상태 | TEST verified, source runtime238개 |

### 14종 시안 배포 이력

아래는 최신 배포로 대체된 시안이며 `test-release-candidate14.json`으로 보존했다.

| 항목 | 실제 결과 |
| --- | --- |
| 대상 | TEST / ARM64 / 238 runtime 파일 |
| image | `robingraph-api:test-audio-expansion-6bd648548a2d` |
| release | `audio-expansion-6bd648548a2d-6057ac` |
| source SHA | `6bd648548a2d21dfb71abbc5512bbe7cda82ffaf56e2643398a103d5c826f111` |
| image ID | `sha256:c48e2b1dfba50750f2a9a79724938f554607eb9065c405f9f2227db9fc9aba06` |
| 이전 release | `audio-tier-color-705c2dfd89d0-7b0a43` |
| 상태 | verified; network-none fixture·manager verify 통과 |
| Production·Git | 운영 배포·commit·push·병합 미실행 |

## 6. 한계 및 후속 과제

- RG-409는 운영 승인 대기다. 자료 확대 TEST 완료와 운영 반영을 구분한다.
- SOURCE_RELEASE가 전환됐으므로 TEST 앱 이미지만 구판으로 되돌리면 옛 reader가 요구하는 release와 맞지 않아 녹음이 표시되지 않을 수 있다. 향후 TEST 롤백에는 구 catalog source projection 복원도 필요하다. 공개 백업을 남겼으며 실제 롤백은 실행하지 않았다.
- 국내 기록/분포 확인은 현재 서식 여부·흔함·텃새/철새 구분·국내 녹음 여부를 보증하지 않는다.
- 다른 종의 음원 대체, 아종 자동 연결, 원자료에 없는 국명·날짜·지역 생성은 하지 않았다.
- 사람의 실제 청취·물리 기기·Safari·Firefox 검증은 별도 증거가 없는 한 미실행이다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-409|RG-409 출처 기반 도감 새소리 듣기]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/2026-10-30-RG409-출처기반-도감새소리|최초 3종 구현·TEST 검증]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/2026-11-02-RG409-새소리앞면컨트롤|앞면 컨트롤·등급별 색상 후속]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
