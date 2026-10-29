---
created: 2026-10-29
date: 2026-10-29
project: RobinGraph
type: worklog
status: completed
task_id: RG-214
related_tasks: [RG-407, RG-408]
tags: [worklog, robingraph, production, release]
---

# [RG-214·RG-407·RG-408] 승인 범위 운영 배포 및 브랜치 병합 — 2026-10-29

## 요약

사용자가 “일단 운영 배포하고, 브랜치 merge 시켜줘”라고 명시 승인했다. 오늘 독립 등록한 먹이 비율 합산 정렬(RG-214), 도감 먹이 표시명(RG-407), 팝업 재열기 배율 복구(RG-408)를 운영 대상으로 분리했다.

root 작업트리에는 앞선 사용자 피드백(RG-603), 조건 유지 후속 질문(RG-213), 안내 UI의 미커밋 변경도 함께 있었다. 독립 후보와 부분 커밋으로 오늘 3개 작업의 source 5개·test 4개만 포함하고, 나머지 변경은 원래 작업트리에 보존한다. 승인 범위 57파일 commit `5056ccb`를 생성하고 dev-codex에 커밋하고 main으로 fast-forward 병합한 뒤 양쪽 push를 완료했다. 후보 전체 검사와 분리 환경 실제 API 검증을 통과했고 Jenkins PROD #13이 시작됐다. Jenkins PROD #13 SUCCESS로 운영 배포를 완료했다. 실제 운영 정렬·라벨·팝업 재열기 검증까지 통과해 RG-214·RG-407·RG-408의 운영 완료 기준을 충족했다.

## 작업 및 변경 결과 요약

| 구분 | 승인 / 설계 | 현재 상태 |
| --- | --- | --- |
| 대상 | RG-214·RG-407·RG-408 | 사용자 명시 운영·병합 승인 |
| 분리 | source 5개·test 4개 독립 후보 | 선행 미커밋 작업 보존·운영 제외 |
| 후보 검사 | Python 1,334 실행·1,294 통과·40 skip·0 실패 | UI 323 통과·Django check 정상 |
| Jenkins | 기존 inline·admin 승인 단계 유지 | PROD #13 SUCCESS, 실제 운영 revision·정적 자산 일치 |
| 백로그 | 세 항목의 운영 완료 기준 충족 | RG-214·RG-407·RG-408 completed |

## 1. 작업 배경 및 문제 분석

세 항목은 TEST 구현·배포·실제 검증이 완료됐지만 운영 승인 대기 상태였다. 이번 요청은 그 후속 운영 반영과 브랜치 병합 승인이다. TEST 단계 기록을 소급해 운영 완료로 바꾸지 않고 이번 배포 이력을 별도로 남긴다.

전체 dirty 작업트리를 그대로 배포하면 별도 미완료 과제가 포함될 수 있었다. root는 오늘 작업이 독립 가능한지 검토하고 승인된 변경만 후보로 분리했다. RG-603·RG-213·안내 UI의 구현 완료나 운영 승인을 이번 요청으로 확대하지 않는다.

## 2. 해결 방안 및 설계

- 기존 운영 계열 코드에 오늘 변경만 적용한 isolated candidate를 검사한다.
- 부분 커밋과 병합·push는 root가 수행한다. 미커밋 선행 작업을 버리거나 덮어쓰지 않는다.
- Jenkins PROD의 저장소와 일치하는 inline 정의 및 admin 승인 단계를 유지한다.
- 실제 운영에서 정렬·라벨·재열기 동작을 검증한 뒤 해당 백로그의 운영 완료 기준을 체크한다.

## 3. 주요 구현 내용

앱 신규 기능을 추가하는 작업이 아니라 기존 승인된 변경을 분리해 운영에 반영하는 작업이다.

| 구분 | 실제 경로 |
| --- | --- |
| source 5개 | `src/robingraph/api/static/chat.js`, `src/robingraph/retrieval/birdbase.py`, `graph_condition_extractor.py`, `graph_questions.py`, `species_profile.py` |
| test 4개 | `tests/frontend/chat_ui.test.js`, `tests/test_graph_questions.py`, `test_species_profile.py`, `test_taxon_traits.py` |
| 나머지 commit 내용 | 오늘 작업기록·백로그·TEST 증거를 포함해 총 57파일 |

Git staging의 source/test 9파일이 검사 후보와 byte 단위로 같음을 확인했다. RG-603 피드백·RG-213 후속 질문·안내 UI 선행 미커밋 변경은 포함하지 않았다.

증거 준비 위치: `/tmp/robingraph-prod-release-20261029/release.patch`, `candidate/`. 전체 dirty 내용은 배포 대상으로 간주하지 않는다.

## 4. 검증 및 테스트 결과

| 검사 | 실제 결과 | 범위 |
| --- | --- | --- |
| 후보 전체 Python | 1,334 실행·1,294 통과·40 skip·0 실패, 25.637초 | `python-tests-final.log` |
| 후보 UI | 323 통과, 284.195ms | `ui-tests.log`; TEST 최신 작업트리 334건과 포함 범위가 달라 합산하지 않음 |
| Django check | 문제 없음 | 후보 설정 검사 |
| 분리 ARM 후보 실제 API | 7/7 통과 | 실제 TEST DB 읽기, `isolated-candidate-live-api.json` |
| Git source/test 일치 | 9파일 byte 일치 | 검사 후보와 staging 동일 |

최초 Git 이력 없는 archive 후보의 전체 Python 실행은 packaging 검사 7개가 Git HEAD 부재로 실패했다. 임시 후보 저장소 초기화 후 같은 전체 검사를 재실행해 최종 통과했다. 앱 결함으로 단정하지 않는다. 40 skip은 미실행 검사로 별도 기록하며 실제 API 7건과 합산하지 않는다.

원래 TEST `test-popup-reopen-4b7da236983b`는 유지했다. 분리 후보에 피드백·후속 질문 기능이 포함되지 않았음을 확인했다. 인증값은 staging에 없음을 검사했고 인증 파일의 내용은 출력하거나 기록하지 않았다.

source diff 검사는 통과했다. `*.patch` 증거 원문의 유효한 공백 context 행 1개가 전체 diff 검사에서 trailing whitespace로 표시되어 패치 artifact를 제외한 source 검사와 구분했다. 증거 패치 원문을 임의로 정리하지 않았다.

### Jenkins 운영 빌드와 배포 검증

PROD #13은 SUCCESS다. Jenkins에서도 Python 1,334 실행·1,294 통과·40 skip·0 실패(24.974초), UI 323 통과와 AMD64 fixture smoke를 확인했다. 공개 health는 HTTP 200, status ok·mode Neo4j·target prod였고 공개 chat.js SHA가 commit의 파일과 일치했다.

승인 처리의 첫 소문자 endpoint ID는 404였으며 HTML의 실제 `ApproveProduction` ID를 확인한 뒤 `proceedEmpty` 200과 admin 승인을 확인했다. 앱 장애로 분류하지 않는다.

### 실제 운영 HTTP·브라우저

공개 운영 `https://robingraph.dove-nest.com/chat`과 실제 Production API를 검사했다. mock 응답을 사용하지 않았다.

| 항목 | 실제 결과 | 완료 기준 |
| --- | --- | --- |
| RG-214 전체 열매 | 20종 점수 DESC, HTTP 4.649초 | 단일 먹이 비율 정렬 |
| RG-214 까마귀과 열매 | 20종, 100·100·70·60·50×13·40×3 순, HTTP 0.841초 | API·DOM 학명 순서 동일 |
| RG-214 열매+곤충 | 20종 합산 점수 DESC, HTTP 3.282초 | 복수 먹이 합산 정렬 |
| RG-407 청둥오리 팝업 | 실제 라벨·팝업·배치 7/7 통과 | 곤충 40%·고기 온혈 0%·고기 변온 10%·기타 고기 0%, 원자료 suffix 제거 |
| RG-408 녹색비둘기 팝업 | 3회 재열기 모두 scale 0.833333 유지 | 토글 접힘·앞면 복원·Enter 뒤집기·가로 넘침 없음 |

HTTP 시간은 각 한 번의 전체 요청 측정이며 성능 보장이 아니다. 넓은 범위의 원자료 전송·합산 비용은 앞선 TEST 계측 한계를 유지한다.

브라우저는 Chromium headless CDP 390×844 모바일 에뮬레이션이었다. 세 검증 스크립트가 모두 exit 0이고 가로 넘침이 없었다. root가 재열기 스크린샷을 시각 검토했다. `reopened-390.png`는 마지막 Enter 이후 뒷면이며, 앞면 복구 수치는 JSON에서 확인한다. 정렬 스크린샷은 자동 스크롤로 경고 목록 위치가 찍혀 정렬 성공의 근거는 API·DOM 비교 JSON을 사용한다.

외부 사진 로드 실패와 기존 외부 경고 목록은 세 기능의 동작 검사와 구분한다. 안내 UI 정리는 배포 범위에서 제외했으므로 기존 경고 목록이 남아 있는 것은 이번 회귀가 아니다. 검증용 Chromium은 종료했다.

### NAS 영수증·환경 보존

`nas-deployment-receipt.json`은 실제 revision과 일치하는 verified 영수증 1개만 보존했다. console에 함께 있던 단위 fixture 영수증 2개는 제외했다. 이전 이미지 `sha256:d1077581143bbb59bb47ea2723c140af66b20a59e4df8cd3a1bae5f6985670f5`에서 승인 이미지로 교체됐다.

런타임 graph intent active·interpreter semantic·MLflow tracing true·운영 실험 50(`robingraph-prod`)를 유지했다. 이번 작업에서 DB migration이나 TEST 앱 변경은 없었다. 인증 파일·config XML·원본 HTML·전체 Jenkins console은 증거 사본에 넣지 않았다.

## 5. 배포 및 형상 관리

- Production: [Jenkins PROD #13](http://192.168.219.99:8080/job/RobinGraph-PROD/13/) SUCCESS.
- 실제 revision: `5056ccba9e75a891cc133a6f371b49deb5dbc598`.
- immutable image digest: `sha256:963b4836ccf77155a8ca94efa105e66c60f799d05e75f6ae6c5b6ce710b05edc`.
- 실제 공개 chat.js SHA256: `48e0e008bac6e6124441d69f54c94227487e5f6da185f00fb301b455f8cdfeb2` — Git 파일과 root 독립 비교 일치.
- commit·merge·push: `5056ccba9e75a891cc133a6f371b49deb5dbc598` 생성, dev-codex에 커밋하고 main으로 fast-forward 병합, 양쪽 원격 push 완료.
- Jenkins: PROD #13, queue 88에서 실행해 SUCCESS. 준비 시점 이전 #12 ABORTED와 구분한다.
- Writer: main-2/dev 문서와 Obsidian·백로그 동기화만 수행. Git·앱·배포·DB 작업 없음.
- 최종 문서 commit·push·병합은 root의 후속 작업이며 이 기록 작성 시 해시는 미정이다. 운영 이미지 revision은 위 5056ccb로 고정한다.
- 선별 증거: `docs/verification/assets/2026-10-29-approved-production-release/`.

## 6. 한계 및 후속 과제

- RG-214의 넓은 범위 전체 행 조회 비용과 기존 자료 범위 한계는 배포만으로 해소되지 않는다.
- 세 항목은 명시된 운영 기능 검증 범위에서 완료했다. RG-603·RG-213 등 별도 미완료 과제는 변경하지 않는다.
- 운영에서는 데스크톱·다른 종으로 전환·닫힌 viewport 변경·물리 모바일·Safari·Firefox를 실행하지 않았다. 데스크톱·닫힌 resize는 앞선 TEST 검증이다.
- 기타 고기의 양성 비율 표본·전체 원자료 사실성·전체 DB checksum·운영 동시 부하는 검사하지 않았다.
- 원래 3개 TEST 작업기록은 당시 이력을 유지하고 현재 상태에 이번 운영 완료 기록을 연결했다. 운영 이미지 revision은 5056ccb이며 후속 문서 commit과 구분한다.

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-214|RG-214 먹이 비율 정렬]]
- [[Work/RobinGraph/백로그 상세/RG-407|RG-407 도감 먹이 표시명]]
- [[Work/RobinGraph/백로그 상세/RG-408|RG-408 팝업 재열기 배율 복구]]
