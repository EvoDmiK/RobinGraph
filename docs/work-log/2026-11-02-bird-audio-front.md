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

# [RG-409] 새소리 재생 컨트롤을 도감 앞면으로 이동

## 요약

사용자 승인에 따라 새소리 재생 컨트롤을 도감 앞면 사진 바로 아래로 옮기고, 녹음 출처·라이선스·메타데이터는 뒷면에 유지했다. 앞면의 출처 버튼을 누르면 같은 카드의 뒷면 녹음 정보를 열고 초점을 이동한다. 기존 플레이어 한 개를 재사용하며, 앞면에서 뒷면으로 이동할 때 재생을 정지한다.

TEST 배포와 실제 CDN 재생·자연 채팅·출처 버튼 키보드 이동·390/1280 화면 재열기 검증을 완료했다. RG-409는 **진행 중 — TEST 구현·검증 완료 / 운영 승인 대기**다. 2026-10-30 최초 구현 기록은 당시 이력으로 보존하며, 이번에는 Production 배포·Git commit·push·병합을 수행하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 사진을 보며 바로 재생 | 컨트롤은 앞면, 자세한 출처는 뒷면이라는 사용자 승인 |
| 설계 및 해결 방안 | 기존 플레이어 재배치 | 한 개의 audio DOM, 고유 출처 연결, 재생면 이탈 시 정지 |
| 코드 / 설정 수정 | 앱 2개·검사 1개 파일 | chat.js, styles.css, frontend 회귀 검사 |
| 실서비스 배포 | TEST verified | 최신 test-audio-tier-color-705c2dfd89d0, ARM64; 앞면 배치·고정색 이력도 보존 |
| 검증 및 테스트 | 모의 DOM 338 통과·실제 재생 검증 | 실제 GET→렌더러 3종과 자연 채팅 1종을 구분 |
| 형상 관리 | 미커밋 snapshot | Production·commit·push·병합 없음 |

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

기존 RG-409 MVP는 뒷면에 새소리 재생과 녹음 정보가 함께 있었다. 사용자는 재생 컨트롤을 앞면 사진 아래에 두고 녹음 출처는 뒷면에 남기도록 요청했다. 이는 새 녹음을 추가하거나 API를 확장하는 작업이 아니라 도감 안의 정보 배치 변경이다.

### 원인 분석 / 설계 검토

기존 정지 조건은 오디오가 뒷면에 있는 구조를 전제로 했다. 컨트롤만 앞면에 옮기면 뒷면 이동 시 재생이 유지될 수 있으므로, 재생면을 떠나는 방향을 함께 바꿔야 했다. 출처를 뒷면에 유지하되 앞면에서 바로 이동할 수 있는 실제 버튼과 명확한 접근성 연결도 필요했다.

독립 backend 검토는 기존 API·출처 필드·완료 diff를 읽고 추가 수정 없이 승인했다. 이 검토 자체는 테스트나 브라우저를 재실행한 결과가 아니다.

## 2. 해결 방안 및 설계

기존 플레이어 DOM 한 개를 앞면 사진 뒤로 이동하고, 뒷면에는 기존 제목·저작자·원문 URL·라이선스·원자료 날짜·지역·소리 유형을 유지했다. 앞면의 “출처: 뒷면” 버튼은 카드별 고유 `aria-controls`를 사용한다. 버튼 작동 시 뒷면 표시 → 출처 details 열기 → summary 초점 이동 순서로 처리한다.

수동 재생·`controls`·`preload=none`·autoplay 없음·기존 URL 필터를 보존했다. 기존 정지 훅을 활용해 앞면→뒷면 전환, 팝업 닫기, 다른 종 재생, 카드 제거, 대화 지우기에서 정지·초기화한다. Codex 통합 검토에서 별도 추상화 없이 최소 diff를 채택했다. 사진만 갱신하는 경우 녹음을 보존하고, 명시적 빈 녹음 배열은 양면 항목과 기존 재생 상태를 함께 정리한다.

## 3. 주요 구현 내용

| 파일 | 변경 내용 |
| --- | --- |
| `src/robingraph/api/static/chat.js` | 기존 플레이어 이동, 출처 버튼·고유 연결·초점 처리, `showFace(showBack)` 시 정지. 22줄 추가·6줄 삭제 |
| `src/robingraph/api/static/styles.css` | 앞면 재생 영역 배치 3줄 추가 |
| `tests/frontend/chat_ui.test.js` | 앞면 컨트롤·중복 없음·출처 이동과 초점·양면 정리·재생면 이탈 검증. 30줄 추가·3줄 삭제 |

API·Python·녹음 데이터·DB는 이번 변경 대상이 아니다. 기존 메타데이터 필터와 오류 표시의 의미를 유지하며 오류 UI는 플레이어가 있는 앞면으로 이동했다.

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

```sh
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
uv run graphify update .
```

- Codex 통합 frontend 검사: **338 통과·0 실패·0 건너뜀**, 280.800833ms. 모의 DOM 기반이며 실제 오디오 청취 검사가 아니다.
- graphify 갱신 exit 0. 기존 SQL parser 경고는 남았으며 앱 검증 실패로 해석하지 않는다.
- UI만 변경해 Python 검사는 이번에 재실행하지 않았다. 10/30의 Python·실제 그래프 검증을 이번 실행 수에 합산하지 않는다.
- 독립 backend 리뷰: 추가 변경 요청 없음. 별도 테스트 재실행 0회, 실제 브라우저 검사는 UI 담당이 수행했다.

### 실제 프로필 API → 배포 렌더러 → CDN

Chromium headless shell에서 실제 TEST 프로필 GET 결과를 배포된 카드 렌더러에 넣어 검증했다. 이 단계는 자연어 채팅 흐름과 구분한다. API·음원 응답을 모의하지 않았다.

| 종 | 앞면 / 뒷면 audio | 재생 후 currentTime | readyState | 실제 decoded bytes |
| --- | --- | --- | --- | --- |
| 참새 Passer montanus | 1 / 0 | 0.529915s | 4 | 20,731 |
| 직박구리 Hypsipetes amaurotis | 1 / 0 | 0.305637s | 4 | 4,370 |
| 청둥오리 Anas platyrhynchos | 1 / 0 | 0.315625s | 4 | 8,359 |

재생 전 음원 요청 0건, preload none, autoplay false, paused true를 확인했다. 세 종 모두 native 컨트롤 클릭으로 재생 시간이 증가하고 미디어 오류 없이 디코딩됐다. 닫기 후 pause·time 0, 다른 녹음 시작 시 기존 녹음 정지, 출처 이동·DOM 제거·대화 지우기의 실제 정지·초기화를 확인했다.

녹음 미지원 Treron sieboldii는 앞면 audio가 없고 빈 컨트롤 영역이 숨겨지며, 뒷면 자료 없음 안내는 유지됐다. 집계 검사 10개 및 세 음원의 재생·종료·배치 검사가 통과했다.

### 실제 자연어 채팅 → 팝업 → 재생·출처

실제 “참새에 대해 알려줘” 질문으로 생성된 팝업을 열었다. 이 단계는 렌더러 주입 없이 자연 채팅 경로를 사용했다. 앞면 사진 바로 아래 audio 1개·뒷면 0개를 확인하고 native 컨트롤로 재생했다. currentTime 0.329893s까지 증가했으며 표시된 오류는 없었다.

출처 버튼에 초점을 두고 실제 Enter 입력을 보내자 뒷면 녹음 details가 열리고 summary로 초점이 이동했다. 재생 중 오디오는 pause·time 0으로 초기화됐다. 자연 흐름 검사 5개가 통과했다.

| 화면 | 재열기 scale | 확인 결과 |
| --- | --- | --- |
| 390 × 844 | 0.833333 유지 | 앞면 복귀·토글 접힘·가로 넘침 없음 |
| 1280 × 800 | 0.780693 유지 | 앞면 복귀·토글 접힘·가로 넘침 없음 |

분포·출처를 펼친 뒤 닫고 다시 열어 검사했다. UI 담당이 앞면·뒷면 스크린샷을 검토했고 Codex는 실제 모바일 앞면 스크린샷을 별도로 시각 검토했다. 이는 물리 모바일 기기나 사람의 실제 청취 검증을 뜻하지 않는다.

### 근거 보관

`docs/verification/assets/2026-11-02-bird-audio-front/`에 root 단위검사 로그, graphify 로그, UI patch, 독립 리뷰, 배포 영수증, 두 브라우저 JSON과 보고서, 스크린샷 및 Writer 동기화 영수증을 보관했다. 전체 API 응답·서명 토큰·인증 정보는 복사하지 않았다.

## 5. 배포 및 형상 관리

| 항목 | 실제 결과 |
| --- | --- |
| 대상 | TEST, ARM64 |
| 이미지 | `robingraph-api:test-audio-front-7e50d05866d5` |
| image ID | `sha256:4291388962e24bb16e546e3686ea89d7855ad429122b933805eb74295b8beec7` |
| release | `audio-front-7e50d05866d5-108cdf` |
| source SHA | `7e50d05866d519c5482a7e563e76588a2b7887781364f89daa1e6f64747d1fd0` |
| 이전 release | `bird-audio-4f72d7ddf66a-fc16b3` |
| 검증 | network-none fixture smoke·실제 manager verify·source manifest 검증 통과 |
| 환경 | graph active·feedback experiment 33 유지, signing key 보존 |
| 형상 관리 | base revision `34fbcdc259f066a8dd4e23e50fd18ac46e195818` 기반 미커밋 snapshot; 새 기능 commit SHA가 아님 |

238개 runtime 파일 중 변경은 JS/CSS 2개다. 최종 runtime SHA가 root 소스와 모두 일치하고 diff check가 통과했음을 Codex가 확인했다. Production·DB 변경·Git commit·push·병합은 수행하지 않았다. 2026-10-30 원래 배포 기록은 덮어쓰지 않고 이번 후속 release를 별도 기록했다.

### 같은 날 후속: 네이티브 오디오 색상 조정

사용자 요청으로 `styles.css`만 추가 수정했다. 오디오 배경과 WebKit media-controls panel을 카드의 연두색 `#e3f2c4`로 맞추고 `color-scheme: light`, 키보드 `focus-visible`의 2px `#233d1c` outline을 지정했다. JS·재생 동작·API·DB는 변경하지 않았다.

동일 frontend 명령을 다시 실행해 **338 통과·0 실패·0 건너뜀**, 279.53175ms를 확인했다. 앞선 338건과 별도 실행이며 합산하지 않는다. graphify exit 0, network-none fixture와 실제 manager verify가 통과했다.

실제 자연 채팅으로 참새 팝업을 열어 native 재생 readyState 4·오류 없음, audio/panel computed color `rgb(227, 242, 196)`를 확인했다. 출처 버튼 키보드 이동·정지·390/1280 재열기가 통과했고, 두 화면에서 키보드 focus outline의 solid `rgb(35, 61, 28)`도 확인했다. Codex가 모바일 스크린샷을 시각 검토했다. 물리 청취·실기기·Safari·Firefox는 이번에도 미검증이다. Safari·Firefox 등에서 해당 vendor pseudo-element가 지원되지 않으면 내부 패널은 플랫폼 기본색을 유지할 수 있다.

이 고정색 단계의 TEST는 `robingraph-api:test-audio-color-da7e1cbc2b1a`, release `audio-color-da7e1cbc2b1a-68a19d`다. source SHA는 `da7e1cbc2b1a7870078bf5d9fa48591d40710b7fada8a66cc16b70df04a04d78`, image ID는 `sha256:2d1a7f59136dc4bd6f0a0215b7a470d6fae170223ea730d938028c1ea1569d4f`다. 직전 위 표의 앞면 배치 snapshot에서 CSS 1개 파일만 바뀌었다. 관련 증거는 같은 검증 폴더의 `color/`에 보관했다. Production·Git 작업은 수행하지 않았다.

### 같은 날 재보완: 고정 LC 색에서 카드 등급별 팔레트로

앞선 고정 연두색 검증은 실제 LC 참새 카드 범위였다. 사용자가 카드의 보전 등급마다 색이 다름을 지적해 고정 LC 색의 한계를 확인했다. 앞선 성공 결과를 전체 등급의 색상 적합성으로 확대하지 않는다.

`styles.css`에 카드별 `--recording-surface`·`--recording-focus`를 정의하고 오디오·내부 패널·키보드 초점이 해당 카드 값을 상속하게 했다. LC/NT/VU/EN/CR/EW/EX를 구분하며, EX는 어두운 badge 대신 밝은 카드 표면색 `#ecebf1`을 사용한다. DD·NE·미확인·알 수 없는 등급·등급 클래스 없음은 중립색이다. 중첩 카드도 자체 기본값을 가져 부모 등급색이 잘못 이어지지 않는다. JS·API·종 등급 데이터·DB는 수정하지 않았다.

- 같은 frontend 명령 재실행: **338 통과·0 실패·0 건너뜀**, 321.546791ms. 앞선 두 실행과 합산하지 않는다. network-none fixture·manager verify·graphify exit 0 통과.
- 최신 TEST CSS에 등급 class만 주입한 **13개 fixture**(LC/NT/VU/EN/CR/EW/EX/DD/NE/unconfirmed/unknown/no-class/nested-no-class)의 audio·panel·focus 기대색 및 카드별 독립성을 확인했다. `src` 없는 fixture이므로 전체 등급의 실제 음원 재생 검증이 아니다. Codex가 matrix 스크린샷을 시각 검토했다.
- 실제 프로필은 Passer montanus(LC, 녹음 1개), Aythya ferina(VU, 녹음 0개), Platalea minor(VU, 녹음 0개)의 카드 색 변수를 확인했다. VU에 없는 녹음을 만든 것으로 기록하지 않는다.
- 실제 LC 참새 자연 채팅 → native 재생·출처 초점 이동·정지·390/1280 재열기가 통과했다. 사람의 실제 청취·실기기·Safari·Firefox 미검증 한계와 vendor 내부 패널색 제한은 유지한다.

최신 TEST는 `robingraph-api:test-audio-tier-color-705c2dfd89d0`, release `audio-tier-color-705c2dfd89d0-7b0a43`이다. source SHA는 `705c2dfd89d049a208af81c358c857c18144c1802e2d82be218e4294bfdc3858`, image ID는 `sha256:d39690379dee4cc05bacc57b40039b110b227a6be25e31d537092961f0401777`이다. 앞선 고정색 release는 당시 이력으로 남기며, 이번 CSS 후속 증거는 `tier-color/`에 보관했다. Production·Git 작업은 수행하지 않았다.

## 6. 한계 및 후속 과제

- RG-409는 운영 승인 대기다. TEST 후속 완료를 Production 반영 완료로 표시하지 않는다.
- 실제 확인한 것은 CDN 데이터 디코딩·재생 시간·정지 이벤트다. 사람의 실제 청취, 물리 기기, Safari·Firefox는 검증하지 않았다.
- 이번 실제 브라우저 검사에는 물리 swipe가 없다. 기존 frontend 제스처 회귀 검사는 통과했다.
- 사진 부재·지연 경로, 오류 UI·URL 신뢰 경계는 단위검사 범위다. 실제 외부 공급자 장애를 유발하지 않았다.
- 녹음 3종의 범위를 확대하거나 해외 녹음을 국내 녹음이라고 표시하지 않았다. 기존 출처·라이선스와 제공된 메타데이터를 유지한다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-409|RG-409 출처 기반 도감 새소리 듣기]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/2026-10-30-RG409-출처기반-도감새소리|2026-10-30 최초 구현과 TEST 검증]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
