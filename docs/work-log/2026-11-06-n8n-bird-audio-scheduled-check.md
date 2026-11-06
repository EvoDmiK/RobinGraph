---
created: 2026-11-06
date: 2026-11-06
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, n8n, bird-audio, production]
---

# [RG-507] 첫 운영 정기 새소리 수집 읽기 전용 점검

## 요약

2026-11-06 03:00 KST의 첫 정기 수집 execution `77742`가 trigger 모드로 성공했다. `Jynx torquilla` 음원 후보 1개를 저장했고, 실행 결과의 `next_cursor`와 n8n Data Table의 운영 cursor가 `avilist-taxon:v2025b:10211`로 일치했다. 실제 PG에는 기존 `Passer montanus`와 신규 후보를 합쳐 2개가 `awaiting_review`로 남아 있다.

이번 작업은 이미 실행된 결과와 저장 상태를 읽기 전용으로 점검했다. 점검 자체의 provider 요청·DB 쓰기·수집 재실행·사람의 검토·공개·배포·Git 작업은 없었다. 첫 정기 실행 1회의 성공이며 장기간 반복 실행의 안정성이나 사람의 청취·동정 검토를 완료한 결과는 아니다. RG-507은 `in_progress`를 유지하고 11월 5일 작업기록과 RG-409는 보존했다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 첫 실제 정기 수집 확인 | 전날 예약 활성화 이후 첫 trigger 실행 결과 점검 |
| 점검 방법 | 기존 기록·실제 저장 상태 재조회 | Jenkins NAS agent의 read-only docker exec·PG `BEGIN READ ONLY` |
| 코드 / 설정 | 변경 없음 | 앱·workflow·Jenkins job/설정 수정 없음 |
| 실서비스 | 기존 운영 실행 확인 | 03:00 수집 1회 성공, 신규 후보 1개·총 검토 대기 2개 |
| 검증 | 실행·cursor·PG·파일 상호 대조 | 두 영수증과 `check-verdict.json`의 invariants 확인 |
| 형상 관리 | 문서·선별 증거 추가 | commit/push/merge·배포 없음 |

## 1. 작업 배경 및 문제 분석

11월 5일에는 운영 전용 수집 sidecar와 매일 03:00·1종 workflow를 활성화했다. 당시 수동 수집과 Data Table fixture를 검증했지만 실제 정기 수집은 아직 미래였다. 이번에는 그 미검증 항목을 실제 실행과 저장 결과로 확인했다.

기존 점검 경로인 NAS `.99:99`와 대체 확인한 `.99:22` SSH 연결은 모두 거부됐고 Orca browser panes는 지원되지 않아 해당 경로를 사용하지 못했다. 기존 Jenkins NAS agent로 읽기 전용 점검을 수행했으며 새로운 Jenkins job이나 설정을 만들지 않았다. 접근 경로의 제약을 수집 실패로 분류하지 않는다.

## 2. 해결 방안 및 설계

Codex가 전달한 `scheduled-read.json`의 실행 결과·Data Table 값을 `storage-read.json`의 실제 PG·파일·health와 대조했다. 실행 summary만 성공인 경우와 실제 저장 성공을 구분하기 위해 후보 ID·종·검토 상태·파일 존재·hash·cursor를 확인했다. 별도 수집을 재실행하거나 상태를 고쳐 검증하지 않았다.

실행 시작·종료 시각은 원본 UTC에 9시간을 더해 KST로 표시했다. 현재 workflow version이 전날 기록과 다르다는 사실은 남기되 변경 원인이나 주체를 추정하지 않는다.

## 3. 주요 구현 내용

앱 구현은 없으며 다음 문서·증거만 변경했다.

- `docs/work-log/2026-11-06-n8n-bird-audio-scheduled-check.md` — 오늘의 읽기 전용 점검 결과.
- `docs/backlog/RG-507.md` — 첫 정기 수집 체크 완료·현재 검토 대기 2개와 상세 기록 연결.
- `docs/verification/assets/2026-11-06-n8n-bird-audio-scheduled-check/` — 인증값 없는 실행·저장·대조 영수증 3개와 문서 동기화 영수증.

11월 5일 TEST·운영 작업기록은 당시 사실로 보존했다. 사용자 후속 질문인 workflow 통합 논의는 설명만 했고 변경 지시가 없어 workflow 수정은 없었다. 현재 매일 실행과 수동 실행은 같은 운영 workflow에 있고 검토·공개는 분리돼 있다.

## 4. 검증 및 테스트 결과

### 실제 운영 실행·cursor

| 항목 | 결과 |
| --- | --- |
| Workflow | `rgAudioCollectionProd01`, 현재 active |
| Execution | `77742`, `mode=trigger`, `status=success`, error 없음 |
| 시작 | 2026-11-06 03:00:00.129 KST |
| 종료 | 2026-11-06 03:00:05.613 KST (5.484초) |
| 입력 | collect·limit 1·이전 cursor 빈 문자열·scheduled true |
| 신규 후보 | `Jynx torquilla`, `awaiting_review` |
| cursor | summary `next_cursor`와 Data Table `prod.after_taxon_id` 모두 `avilist-taxon:v2025b:10211` |
| cursor 저장 | `cursor_saved=true`, Data Table updated 03:00:05.589 KST |
| 자동 공개 | `publication_automatic=false` |

실행 경로에 scheduled cursor 읽기·수집·성공 checkpoint·cursor 저장·summary가 실제 포함됐다. 실행에 기록된 workflow version은 `4f6af6c2-d708-4ef6-a158-175fb95730b7`이며 Codex가 확인한 현재 active/current version도 같은 값이다. 11월 5일 기록의 `45fee2c2-a0ea-46e0-8a43-a8d5c65f4dec`와 다르지만 이번 점검에서 원인은 확인하지 않았다. 두 시점의 값을 혼합하거나 전날 문서를 덮어쓰지 않는다.

### 실제 PG·파일·자료 범위

| 대상 | 실제 결과 |
| --- | --- |
| PG | database `robingraph`, schema `ingest` |
| 후보 총수 | `awaiting_review` 2개, 두 후보 모두 review 필드 없음 |
| 기존 `Passer montanus` | 파일 존재·289,857 bytes·저장 SHA256 일치 |
| 신규 `Jynx torquilla` | 파일 존재·1,766,350 bytes·저장 SHA256 일치 |
| collector health | ok·target prod·publication_enabled false |

신규 candidate ID는 `9e84efdf7b2f9a9a951553a460c073f4913d56a12065b67d96134713b17f93ba`, 파일 SHA256은 `05da5ee5079346626281498a34b0cf38e12daab90beb0547329cf9f4fb777ab1`이다. Commons page `91877997`, revision `962980390`, 정확한 학명 일치 근거·제작자 Kim Erlend Vidal·CC BY-SA 4.0·기록 시각 `2020-05-23 21:30`을 기록한다. location·recording_type은 원 metadata의 null을 유지하며 지역·소리 유형이나 검증되지 않은 국명을 생성하지 않는다.

metadata 조회 시각은 `2026-11-05T18:00:03.889489+00:00`다. 자료 저장과 license metadata 보존은 사람의 청취·동정 검토 완료를 의미하지 않는다. 이번 점검은 파일 hash를 대조했으며 새 브라우저 디코딩·실제 청취·공개 음원 제공 검사는 하지 않았다.

### 대조 결과와 미실행 항목

`check-verdict.json`은 Codex가 두 실제 영수증의 실행·후보·cursor·파일·검토 상태 invariants를 확인한 결과다. 모의 API나 fixture의 결과가 아니다. 이번 점검 자체의 provider 요청 0·DB 쓰기 0·review 0·publication 0과, 새벽 정기 수집이 후보를 저장한 사실은 서로 다른 범위다.

앱 코드 변경이 없는 읽기 전용 점검이므로 단위·프런트엔드 회귀 테스트와 graphify 갱신은 새로 실행하지 않았다. 이전 작업의 통과 수치를 오늘 재실행한 결과로 합산하지 않는다. `check.py`·`check-storage.py`는 문서 자산에 포함하지 않았고, 재현에 필요한 확인 항목과 실제 결과는 선별 JSON 영수증에 보존했다.

## 5. 배포 및 형상 관리

[운영 workflow](https://workflow.dove-nest.com/workflow/rgAudioCollectionProd01)의 이미 완료된 실행을 점검했다. 이번 점검에서 컨테이너 재시작·이미지 교체·workflow 수정·Jenkins 설정 변경·DB migration·롤백·Git 작업은 수행하지 않았다. 전체 DB checksum이나 다른 서비스의 불변성을 새로 감사했다고 주장하지 않는다.

## 6. 한계 및 후속 과제

- 실제 daily 성공은 1회다. 다음 날의 cursor 이어받기·장기 반복 안정성·외부 제한 발생 시 운영 동작은 아직 추가 관측이 필요하다.
- 후보 2개는 사람의 청취·동정·자료 검토와 별도 공개가 남아 있다. 수집 성공을 공개 종 증가로 세지 않는다.
- RG-507은 진행 중을 유지하며, RG-409의 도감 기능·TEST 12종·운영 승인 상태는 이번 점검에서 변경하지 않는다.
- workflow version 차이는 관측 사실만 남겼고 원인은 미확정이다.

## 7. 사용자 요청 후속: 불필요한 fixture workflow 정리

앞선 읽기 전용 점검을 마친 뒤 사용자가 화면에 남은 fixture workflow 2개의 제거를 명시적으로 요청했다. 이 별도 후속 범위에서 2026-11-06 13:15:58 KST에 비활성 `rgAudioCursorFixture20261105`와 `rgAudioTableFixture20261105`를 삭제했다. 삭제 전 정의를 `fixture-backup.json`에 보존했고 삭제 후 각각 GET 404로 부재를 확인했다. 실제 삭제 처리는 한 번만 수행했다.

workflow 수는 43→41이며 나머지 workflow ID는 보존됐다. 운영 `rgAudioCollectionProd01`의 전체 GET 응답 hash는 전후 동일하고 `active=true`, 현재 version `4f6af6c2-d708-4ef6-a158-175fb95730b7`도 유지됐다. 다른 모든 workflow 본문 hash까지 검증한 것은 아니다. 증거는 `fixture-deletion-receipt.json`이다.

초기 snapshot 읽기 명령은 Node의 예약 명령 `inspect`와 충돌해 2회 읽기 전에 실패했고, 명칭을 `snapshot`으로 바꾼 뒤 성공했다. 이 준비 단계의 실패를 삭제 실패나 중복 삭제로 세지 않는다.

Data Table의 prod/fixture 행·후보는 삭제하지 않았다. 수집 재실행·credential 쓰기·배포·재시작·Git 작업은 없고 앱 코드 변경이 없어 graphify 갱신도 하지 않았다. `check.py`·`cleanup-run.py`는 문서 자산에 복사하지 않았다. 앞선 절의 변경 0은 최초 읽기 전용 점검 범위의 사실이며 이 후속 삭제와 구분한다. 기존 11월 5일 기록·RG-409 상태는 변경하지 않았다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 현황·완료 기준]]
- [[Work/RobinGraph/작업기록/5xx 데이터·분류·이름/2026-11-05-RG507-운영새소리일일수집|전날 운영 적용·예약 활성화 기록]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
