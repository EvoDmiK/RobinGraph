---
created: 2026-10-29
date: 2026-10-29
project: RobinGraph
type: worklog
status: completed
task_id: RG-408
backlog_status: completed
related_tasks: [RG-405]
legacy_task_id: RG-015
tags: [worklog, robingraph, card-popup]
---

# [RG-408] 도감 팝업 재열기 축소 수정 — 2026-10-29

## 요약

**현재 상태(2026-10-29 후속):** [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-29-승인3항목-운영배포-main병합|PROD #13 운영 배포·실제 검증 완료]]. revision `5056ccb`, dev-codex 커밋·main fast-forward 병합·양쪽 push 완료. 아래 구현·검증·배포 수치는 최초 TEST 단계의 이력이다.

2026-10-29 사용자 요청으로 기존 후속 기록을 독립 백로그 [[Work/RobinGraph/백로그 상세/RG-408|RG-408]]로 신규 등록했다. 최초에는 RG-405 후속으로 기록했으며, 이번 등록을 과거 착수 시점의 신규 번호로 소급하지 않는다. 등록 당시 백로그 상태는 진행 중(TEST 완료·운영 승인 대기)이었다. 이후 같은 날 사용자 승인으로 PROD #13 배포·실제 운영 검증을 마쳐 현재 백로그 상태는 **완료**다.

녹색비둘기 `Treron sieboldii` 도감 뒷면의 항목·비율을 펼친 채 팝업을 닫았다가 다시 열면 앞면 글씨가 작아지는 문제가 실제 TEST 모바일 환경에서 재현됐다. 팝업을 열 때 두 종류의 펼침 상태를 먼저 접어 초기 카드 크기를 측정하도록 최소 수정했다.

소스는 `chat.js` 3줄 추가, 관련 회귀 테스트는 1개 추가다. root 프런트엔드 334건 통과와 TEST 배포를 완료했다. 실제 Chromium 모바일·데스크톱 각각 3회 재열기와 닫힌 상태의 화면 크기 변경 후 재열기에서 초기 scale·앞면·토글 상태 복원을 확인했다.

## 작업 및 변경 결과 요약

| 구분 | 내용 | 상태 |
| --- | --- | --- |
| 재현 | 펼친 상태로 닫고 재열면 앞면 축소 | 실제 TEST 폭 390에서 확인 |
| 원인 | fit 기준 높이 초기화와 details 펼침 상태 잔존 | 재열기 때 확장된 높이를 기준으로 축소 |
| 해결 | 팝업 opener에서 두 종류 토글 접기 | 기존 앞면 전환·showModal·startFit 흐름 유지 |
| 로컬 검증 | frontend 334/334 | 실패 0·skip 0, 263.5015ms |
| 실제 배포 후 | TEST verified·Chromium | 반복 재열기 6/6 및 닫힌 resize 통과 |

## 1. 작업 배경 및 문제 분석

사용자는 녹색비둘기 카드 뒷면에서 항목·비율을 펼친 뒤 닫고 같은 팝업을 다시 열었을 때 앞면 글씨가 작아지는 현상을 제보했다.

배포 전 실제 TEST 재현에서 초기 scale은 `0.833333`, 카드 높이는 `955`였다. 토글 두 개를 열면 높이가 `1137`로 커져도 현재 scale은 유지됐다. 팝업을 닫고 다시 열면 토글의 open 상태가 남은 채 scale이 `0.700088`로 작아졌다.

`startFit`이 `collapsedFitHeight`를 0으로 초기화하는 동안 details 펼침 상태는 그대로 남아 있어, 재열기 때 확장된 높이를 초기 높이로 측정한 조합이 원인이었다.

## 2. 해결 방안 및 설계

새 높이 캐시나 상태 계층을 추가하지 않았다. 기존 opener에서 fit 대상 `.card-details-scroll`, `.species-distribution-values`를 접은 뒤 `showFront()` → `showModal()` → `startFit()`을 그대로 실행한다.

```text
다시 열기 → 세부 토글 접기 → 앞면 전환 → 팝업 열기 → 초기 크기 측정
```

열려 있는 팝업에서 토글을 펼칠 때의 scale 유지 동작은 보존한다. 다시 열기는 앞면과 접힌 토글이라는 초기 상태로 돌아가는 동작이다.

## 3. 주요 구현 내용

| 파일 | 변경 |
| --- | --- |
| `src/robingraph/api/static/chat.js` | opener에서 fit 대상 토글 2종을 `open = false`로 설정; 주석 포함 3줄 추가 |
| `tests/frontend/chat_ui.test.js` | 재열기 회귀 1개, fixture 높이 getter 재정의 허용 포함 23줄 추가 |

회귀는 모바일·데스크톱 각각 3회 반복해 토글을 펼쳤을 때 scale 유지, 닫고 재열었을 때 토글 접힘·최초 scale·앞면·내부 scroll 상태 복귀를 확인한다. 이는 fixture 검사이며 실제 기기 검사로 세지 않는다.

## 4. 검증 및 테스트 결과

- root 통합 frontend: 334 통과 / 0 실패 / 0 skip, 263.5015ms. `root-ui-tests.log`.
- UI 담당 chat 검사: 330 통과. root 통합 수치와 중복되므로 합산하지 않는다.
- 배포 전 실제 TEST 재현: 초기 `0.833333` → 재열기 `0.700088`. 수정 전 증거를 성공으로 표기하지 않는다.
- 회귀 검출 확인: scratch에서 수정 3줄을 제거하고 새 테스트를 실행하면 실패 1건이 발생했다. `regression-before.log`는 수정 전 결함 검출 증거이며 최종 실패로 합산하지 않는다.
- 최종 graphify 갱신 exit 0: `root-graphify.log`.

### 실제 배포 후 브라우저

실제 TEST API 응답을 사용한 Chromium headless CDP 검증이며 mock이 아니다. 녹색비둘기 같은 카드에서 두 토글을 펼친 뒤 닫고 재여는 동작을 각 화면에서 3회 반복했다.

| 화면 | 초기 scale / 높이 | 수정 후 재열기 3회 | 상태 |
| --- | --- | --- | --- |
| 390×844 모바일 에뮬레이션 | 0.833333 / 955 | 모두 0.833333 / 955 | 토글 0개 열림·앞면·Enter 뒤집기 통과 |
| 1280×800 데스크톱 | 0.832215 / 894 | 모두 0.832215 / 894 | 토글 0개 열림·앞면·Enter 뒤집기 통과 |

두 화면에서 팝업 범위가 viewport 안에 있고 문서 가로 넘침이 없었다. 닫힌 상태에서 viewport를 390→1280으로 바꾼 추가 검사도 새 화면의 baseline 0.832215와 재열기 0.832215가 같았고 앞면·접힌 토글로 복구됐다.

`popup-browser-results.json`과 `reopened-before.png`는 수정 전 실제 재현이다. `popup-browser-after-results.json`은 수정 후 6회 검사, `popup-browser-resize-results.json`은 닫힌 resize 검사다. `reopened-390.png`·`reopened-1280.png`는 반복 확인 후 Enter로 다시 뒤집은 **뒷면**이며 앞면 복원은 JSON에서 확인한다. `closed-resize-1280.png`는 닫힌 resize 후 **앞면**이다. root는 수정 후 모바일 스크린샷을 시각 검토했다.

검증 중 외부 사진 로드 실패가 있었지만 이 작업의 fit 복구와 분리해 기록한다. 사진 로드 성공까지 검증한 것은 아니다. 검증용 Chromium은 종료했다.

근거 원본은 `/tmp/robingraph-popup-reopen-20261029`, 선별 사본은 `docs/verification/assets/2026-10-29-card-popup-reopen-scale/`에 보관했다. 소스 전체·서명 토큰·인증 값은 복사하지 않았다. 배포 전 재현과 수정 후 검증을 별도 파일로 유지했다.

## 5. TEST 단계 배포 및 형상 관리 (이력)

| 항목 | 확정 값 |
| --- | --- |
| 대상 | TEST 16GB Mac 앱, ARM64 |
| 이미지 | `robingraph-api:test-popup-reopen-4b7da236983b` |
| 이미지 ID | `sha256:d9b89bc1a3966bbc81d014e7442f1b321cd187cf81b83175289df92a2672d326` |
| release | `popup-reopen-4b7da236983b-c5dbd5` |
| 소스 SHA256 | `4b7da236983bb31212794133a0f77d9c6e7f81fe8577864a1be647084f7a2980` |
| 배포 기준 revision | `318e7731fda8b85560b7e8d464b0f4f2c92439d1` — 이번 수정 commit 아님 |
| 검증 | verified·health·manage verify·네트워크 없는 fixture smoke 통과 |
| source 확인 | 235파일 전체 root/release SHA 일치; 직전 release와 source 변경은 chat.js 1파일 |
| 공개 자산 | 실제 static chat.js SHA `f9d19c4121292bebdd3428ed9055d168c02751e89d38fa9d3c6ba99520d0f0e7` 일치 |
| 환경 보존 | ENV는 IMAGE key만 변경, 서명 key 보존 |
| Production / Git | 운영 변경·commit·push 없음 |
| Writer | main-2/dev 문서·Obsidian 기록만 수행 |

직전 TEST `test-diet-ranking-0da3e28acdb1`에서 앱 이미지를 교체했다. 변경 테스트 파일은 서버 snapshot 235개에 포함되지 않으므로 source 한 파일 변경과 모순되지 않는다.

## 6. 한계 및 후속 과제

- 이번 범위는 details가 열린 채 팝업을 닫고 재열 때의 fit 기준 복구다. 전체 레이아웃 변경으로 확대하지 않는다.
- 실제 다른 종으로 전환하는 브라우저 검사, 물리 모바일·Safari·Firefox·스와이프·움직임 줄이기는 이번에 실행하지 않았다. 같은 카드 반복 재열기와 닫힌 viewport 변경이 실제 검증 범위다.
- RG-405(기존 RG-015) 후속 기록을 사용자 요청으로 RG-408에 신규 등록했다. 기존 카드 토글 기록과 연결하고 다른 작업 상태는 유지한다.

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/작업 백로그|카드 UI 작업 기록]]
- [[Work/RobinGraph/작업기록/4xx 채팅 UI·카드/2026-10-10-카드뒷면-토글배율유지-PC모바일|기존 카드 뒷면 토글 배율 유지 이력]]
