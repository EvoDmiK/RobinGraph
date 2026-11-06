---
created: 2026-10-30
date: 2026-10-30
project: RobinGraph
type: worklog
status: completed
backlog_status: in_progress
task_id: RG-409
tags: [worklog, robingraph, bird-audio]
---

# [RG-409] 출처 기반 도감 새소리 듣기 — 2026-10-30

## 요약

사용자가 서비스에 새소리를 추가하는 설계 제안에 “좋아 그렇게 해줘”라고 답해 구현을 승인했다. 국내에서 볼 수 있는 참새·직박구리·청둥오리 3종의 확인된 Commons 녹음을 도감에서 수동 재생하는 MVP가 범위다. 해당 녹음의 채집 장소는 해외이므로 “국내 녹음”으로 표시하지 않는다.

코드 통합과 TEST 이미지 배포를 마쳤다. 실제 TEST 그래프 녹음 3건과 출처 관계 반영·재조회·반복 적용까지 확인했다. 실제 프로필 API 4건, 세 종의 CDN 음원 디코딩·재생, 자연어 채팅→도감→재생 흐름과 두 화면 크기의 재열기 검증을 완료했다. 사람이 귀로 들은 청취 확인은 하지 않았다. 운영 배포는 승인되지 않았다. 기존 새소리 백로그와 번호 중복이 없음을 확인해 RG-409로 등록했다. 현재 RG-409 상태는 **진행 중(TEST 구현·검증 완료 / 운영 승인 대기)**다. 이 작업기록의 completed는 TEST 범위 완료를 뜻한다.

## 작업 및 변경 결과 요약

| 구분 | 설계 / 확인 사실 | 현재 상태 |
| --- | --- | --- |
| 기능 | 도감 “새소리 듣기” | 통합 검사 완료 |
| 자료 범위 | 참새·직박구리·청둥오리 3종 Commons 녹음 | 공식 메타데이터 HTTP 200·BY/BY-SA 라이선스 확인 전달 |
| 그래프 | Recording 미디어 노드와 Taxon 관계 | 3건 반영·재조회·중복 없음 확인 |
| API | recordings·recording_availability | 실제 프로필 HTTP 4/4 통과 |
| UI | 수동 native audio·preload none·단일 재생 | 실제 CDN 재생·자연 채팅·종료·재열기 검증 완료 |
| 운영 | 승인 없음 | Production 미반영 |

## 1. 작업 배경 및 문제 분석

사진·형질 중심 도감에 출처가 확인된 소리 자료를 추가한다. 초기 범위는 확인 가능한 3종·녹음이며 자료가 없는 종이나 녹음 유형·날짜·장소를 생성하지 않는다.

| 대상 종 | 학명 | 기록 원칙 |
| --- | --- | --- |
| 참새 | Passer montanus | 종 식별·녹음 메타데이터 출처를 연결 |
| 직박구리 | Hypsipetes amaurotis | 국내에서 관찰되는 종과 녹음 장소를 구분 |
| 청둥오리 | Anas platyrhynchos | 해외 녹음을 국내 녹음으로 설명하지 않음 |

공식 Commons 조회는 2026-10-30T06:29:17.911783Z에 수행했다. 메타데이터 원본 응답 SHA256은 `df5d648d5666f9f6f9705a9ab5680871a086831d248b247e77199171759e8021`이다.

| 종 | Commons 파일 / 저작자 | 라이선스 | 원자료 녹음 날짜·장소·유형 |
| --- | --- | --- | --- |
| 청둥오리 | [Anas platyrhynchos - Mallard - XC62258.ogg](https://commons.wikimedia.org/wiki/File:Anas_platyrhynchos_-_Mallard_-_XC62258.ogg), Jonathon Jongsma | CC BY-SA 3.0 | 2010-09-14 13:53, Powderhorn Park, Minneapolis, MN; 유형 미기재 |
| 직박구리 | [Hypsipetes-amaurotis-2025-05-20-282617142.ogg](https://commons.wikimedia.org/wiki/File:Hypsipetes-amaurotis-2025-05-20-282617142.ogg), karliatje | CC BY 4.0 | 2025-05-20, Izu, Japan; 유형 미기재 |
| 참새 | [Passer montanus.ogg](https://commons.wikimedia.org/wiki/File:Passer_montanus.ogg), Vladimir Yu. Arkhipov, Arkhivov | CC BY-SA 3.0 | 2011-09-20, Moscow region, Russia; Calls |

날짜는 원자료 `DateTimeOriginal`이며 업로드 날짜를 녹음 날짜로 대체하지 않는다. 원자료 메타데이터 revision·file SHA1·metadata SHA256은 출처 보고서와 고정 bundle에 남겼다.

자료의 접근 가능·라이선스 허용과 브라우저에서 실제 재생되는지는 별도 검증이다. 자동화가 playback 이벤트를 확인한 것과 사람이 음원을 귀로 청취한 것도 구분한다.

## 2. 해결 방안 및 설계

녹음은 Taxon 속성의 임의 문자열로 합치지 않고 별도 `MediaAsset:Recording` 노드 및 `HAS_RECORDING` 관계로 연결한다. provenance와 source registry를 통해 출처·라이선스·원자료 식별을 보존한다.

```text
확인된 Commons 녹음·라이선스·원 메타데이터
→ Recording 미디어 노드 / HAS_RECORDING / Taxon
→ profile.recordings + recording_availability
→ 도감 native audio 수동 재생
```

UI는 `preload="none"`으로 시작하며 자동 재생하지 않는다. 하나의 음원만 재생하고 팝업 닫기 등 종료 동작에서 정지한다. creator·license·date·location·type은 원 메타데이터가 있을 때만 표시한다. 날짜나 위치를 업로드 시점·종 분포로 임의 보충하지 않는다.

## 3. 주요 구현 내용

| 파일 | 역할 |
| --- | --- |
| `src/robingraph/retrieval/recordings.py` | 확인된 녹음 자료·그래프 관계·프로필 조회 |
| `src/robingraph/retrieval/commons_bird_recordings.json` | 3종 Commons 고정 메타데이터 bundle |
| `src/robingraph/retrieval/species_profile.py` | recordings와 recording_availability 제공 |
| `src/robingraph/cli.py`, `scripts/import_reviewed_recordings.py` | 검토 녹음 반영 진입점 |
| `config/source-registry.json` | 녹음 출처 정책 등록 |
| `src/robingraph/api/static/chat.js`, `styles.css` | 수동 audio·메타데이터·재생 생명주기 UI |
| `tests/test_recordings.py`, `tests/frontend/chat_ui.test.js` | 녹음 자료/조회·UI 회귀 |

최종 앱 snapshot은 238파일이다. API 구조 추가는 녹음 목록과 가용성에 한정하고 기존 종·아종 자료 범위를 녹음이 있다는 이유로 확대하지 않는다.

## 4. 검증 및 테스트 결과

### 검증 재현 명령

```sh
PYTHONPATH=src:tests uv run --locked --extra test --extra tracing python -m unittest tests.test_recordings tests.test_species_profile tests.test_birdbase_traits tests.test_drf_parity -q
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
uv run graphify update .
```

### 현재 확인된 근거

root가 공식 Commons 메타데이터 3개 HTTP 200 및 BY/BY-SA 라이선스 확인을 전달했다. Writer가 별도 API·DB·오디오 재생을 실행한 것은 아니다.

- root 통합 Python 60 통과·0 실패·0 skip: `root-python-tests-final.log`.
- root UI 337 통과·0 실패·0 skip: `root-ui-tests.log`.
- backend 자체 74 통과는 별도 검사 범위이며 root 60과 합산하지 않는다.
- graphify root 갱신 exit 0, AST 완료. SQL parser 미설치 경고 4건은 남았다.
- TEST ARM64 이미지 빌드·network-none fixture smoke·실제 manage verify 통과. fixture 성공을 실제 DB 쓰기나 오디오 재생 성공으로 세지 않는다.

### 실제 TEST 그래프 반영

읽기 전용 사전 확인에서 TEST Neo4j `192.168.219.98:7687`, database `neo4j`, concept set `rg:concept-set:avilist-v2025b`, taxonomy release `v2025b`를 확인했다. 대상 종 ID는 청둥오리 `avilist-taxon:v2025b:544`, 직박구리 `avilist-taxon:v2025b:23698`, 참새 `avilist-taxon:v2025b:29772`다.

`test-recordings-import-receipt.json`은 녹음 0→3, evidence unit 0→3, HAS_RECORDING 0→3, SUPPORTED_BY 0→3을 기록한다. 두 번째 apply 후 각 3개로 유지되어 중복 노드·관계는 0이었다. 대상 Taxon 3개의 속성 hash는 전후 같았다. 이 검사는 대상 Taxon 속성 비교이며 전체 DB checksum 감사가 아니다.

실제 reader는 세 종 각각 녹음 1개를 반환했다. 아종 `Anas platyrhynchos platyrhynchos`는 0개였고 해당 source의 전체 아종 연결도 0개였다. 종 녹음을 아종으로 임의 상속하지 않았다. 이 영수증의 쓰기 검증 대상은 TEST 그래프이며 별도 PG provenance 실제 쓰기까지 검증했다고 확대하지 않는다.

### 실제 TEST API

`test-live-basic-profile.json`의 실제 HTTP 4/4가 통과했다. 청둥오리·직박구리·참새는 `recording_availability=available`이고 각각 검토 녹음 1개다. 까마귀는 `no_licensed_recording`, 0개다. 네 응답 모두 기존 basic profile·요약·18개 형질과 photos_pending 상태를 함께 확인했다. 이 상태는 사진 로딩 완료 검증을 뜻하지 않는다.

### 실제 프로필 API → 배포 렌더러 → CDN 재생

`browser-results.json`은 실제 GET 프로필을 기존 배포 카드/팝업 렌더러에 전달한 통합 검사다. 자연어 채팅 흐름과 구분한다. 세 종의 저작자·제목·라이선스·선택 메타데이터가 원자료와 일치했고 녹음 없는 녹색비둘기는 명시적인 자료 없음 안내를 표시했다.

재생 전 세 control은 preload none·autoplay false·paused true였고 음원 URL 네트워크 요청은 0이었다. 실제 native control 클릭 후 세 종 모두 readyState 4, media error 없음, currentTime 증가와 decodedBytes 양수를 확인했다.

| 실제 음원 | 관측 재생 시간 | 디코딩 bytes | 닫기 |
| --- | ---: | ---: | --- |
| 참새 | 0.535초 | 21,287 | pause·currentTime 0 |
| 직박구리 | 0.362초 | 4,816 | pause·currentTime 0 |
| 청둥오리 | 0.325초 | 8,671 | pause·currentTime 0 |

다른 카드 재생 시 단일 재생, DOM 제거와 대화 지우기 시 정지도 실제 media 상태로 확인했다. 이 단계의 초기 flip probe는 단일 재생 검사 때문에 첫 음원이 이미 정지해 있어 활성 재생 정지의 근거로 사용하지 않았다. 해당 조건은 아래 자연 채팅 검사로 확인했다.

### 실제 자연어 채팅 → 도감 → 재생

`chat-browser-results.json`은 “참새에 대해 알려줘”를 실제 채팅에 제출해 자연 생성된 팝업을 연 검사다. 렌더러 주입이나 API·음원 mock을 사용하지 않았다. native control 클릭으로 readyState 4·currentTime 0.302853을 확인했고 보이는 오류는 없었다. DOM에 숨긴 오류 안내 문장이 있는 것과 실제 오류 표시를 구분했다.

재생 중 Enter로 앞면을 전환하자 pause·currentTime 0이 됐다. 자연 채팅·디코딩 재생·표시 오류 없음·활성 재생 뒤집기 정지의 4개 검사가 통과했다. 같은 팝업에서 분포·오디오 details를 펼친 뒤 닫고 재열기를 390×844·1280×800에서 확인했다. 각 scale은 0.833333·0.785639로 유지되고 앞면·접힌 토글로 돌아왔으며 가로 넘침이 없었다. root가 실제 채팅 모바일 스크린샷을 시각 검토했다.

브라우저는 Chromium headless CDP 에뮬레이션이다. 사람의 청취·물리 모바일·Safari·Firefox는 미실행이다. provider 실패 UI와 악성 URL 거절은 Node 검사로 확인했으며 실제 외부 제공자를 고장 내어 검증하지 않았다. 검증용 Chromium은 종료했다.

### 근거 보관

선별 원본 영수증·결과·로그·스크린샷은 `docs/verification/assets/2026-10-30-bird-audio/`에 복사했다. Commons 출처 보고서, TEST 대상 확인·반복 반영 영수증, 프로필 API, 두 브라우저 단계, 배포 영수증을 별도로 보관했다. 전체 API 응답·서명 토큰·계정 인증 값은 저장하지 않았다. 임시 작업 위치는 `/tmp/robingraph-bird-audio-20261030/`다.

## 5. 배포 및 형상 관리

| 항목 | 확인 값 |
| --- | --- |
| TEST 이미지 | `robingraph-api:test-bird-audio-4f72d7ddf66a` |
| release | `bird-audio-4f72d7ddf66a-fc16b3` |
| 소스 SHA256 | `4f72d7ddf66a40ef4301e6d0c913102ec0bc953bd78415f1051f075c09c9270c` |
| 이미지 ID | `sha256:74b08fb5548ee49ca3fa180baf857d20541eeab196f8951d0447ccd7926a9ce0` |
| 기준 revision | `34fbcdc259f066a8dd4e23e50fd18ac46e195818` — 이번 기능 commit 아님 |
| snapshot | 238파일, ARM64, verified; 최종 root 소스와 배포 manifest 전부 SHA 일치 |
| 직전 release | `popup-reopen-4b7da236983b-c5dbd5` |
| 환경 | TEST intent active·실험 33·기존 signing key 보존 |

- 실제 TEST DB 쓰기: root가 위 대상을 확인한 뒤 3개 검토 녹음과 출처 관계를 반영·재조회했다. Production 변경 없음.
- Production: 승인 없음·미반영.
- commit·push: 이번 기능은 미커밋·미push 상태다.
- Writer: main-2/dev 문서와 Obsidian·백로그 동기화만 수행. root 파일·앱·환경·배포·DB 변경 없음.
- 최종 `git diff --check` 통과, 배포 이후 runtime 소스 변경 목록은 비어 있다.

## 6. 한계 및 후속 과제

- 3종의 출처 확인 녹음 MVP이며 전체 조류의 소리 자료 확보를 뜻하지 않는다.
- 국내 종과 국내 녹음을 혼동하지 않는다. 원자료에 없는 설명을 보완 생성하지 않는다.
- 외부 미디어의 접근 가능성과 라이선스·저작자 표시를 함께 유지한다.
- 실제 청취·물리 기기·Safari·Firefox는 미검증이다. 재생 시간·디코딩을 확인한 것이 사람의 소리 식별이나 음질 검증을 대신하지 않는다.
- 관련 백로그는 진행 중(TEST 구현·검증 완료 / 운영 승인 대기)으로 갱신했다. 전날 완료한 RG-214·407·408과 다른 기존 상태는 유지한다.

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/작업 백로그|도감·채팅 UI 작업 목록]]
- [[Work/RobinGraph/백로그 상세/RG-409|RG-409 범위·완료 기준]]
