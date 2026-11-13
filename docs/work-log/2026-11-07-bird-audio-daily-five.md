---
created: 2026-11-07
date: 2026-11-07
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, n8n, bird-audio, production]
---

# [RG-507] 수집 후보 확인·운영 하루 최대 5종으로 확대

## 요약

사용자가 현재 수집 자료 확인과 하루 수집량 확대를 승인했다. 운영 PG의 음원 후보는 참새·개미잡이·청딱다구리 3개이며 모두 `awaiting_review`, review 필드 없음, 실제 파일 SHA256 일치 상태다. 저장 성공을 사람의 동정·청취 검토나 공개 완료로 해석하지 않는다.

운영 workflow의 이름과 예약 실행 입력만 하루 1종에서 **최대 5종 처리 대상**으로 변경했다. 매일 03:00 Asia/Seoul, 수동 기본 1·최대 5, 기존 cursor와 나머지 노드·연결은 유지했다. 실제 활성 발행 버전은 `d8f1c0c4-a745-4ed2-97f1-3388b7331f00`이다. 첫 5종 batch는 2026-11-08 03:00 KST 예정이며 아직 실행하지 않았다. 매일 성공 저장 5건을 보장하는 설정이 아니다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 수집 현황 확인·처리량 확대 | 기존 후보 3개 읽기 검증, 예약 최대 5종 |
| 설계 | 기존 최대 batch 범위 재사용 | 신규 수집 계층·fixture workflow 추가 없음 |
| 코드 / 설정 | Production 이름·예약 limit만 변경 | generator·Production artifact·회귀 기대값 갱신 |
| 실서비스 | 기존 활성 workflow PUT 1회 | current/active 발행 버전과 원래 설정값 보존 확인 |
| 검증 | fixture 13/13·운영 읽기 재조회 | 원격 기본값 추가로 발생한 최초 후검 실패와 해소 근거 보존 |
| 형상 관리 | 미커밋 변경 | 이번 요청으로 commit/push·컨테이너 배포·재시작 없음 |

## 1. 작업 배경 및 문제 분석

RG-507은 운영 수집 전용 sidecar와 매일 1종 예약을 적용했고 첫 정기 수집까지 검증했다. 사용자가 저장된 자료를 보고 하루 처리량을 늘리고자 해 기존 제한 내에서 예약 입력을 5로 조정했다. 과거 11월 5·6일의 1종 운영 기록은 당시 이력으로 보존한다.

초기 PG 조회는 존재하지 않는 `created_at` 열을 참조해 실패했다. `updated_at`으로 조회를 수정한 뒤 성공했으며 이 조회 수정으로 운영 자료를 쓰지 않았다. workflow 갱신 후 첫 후검에서는 settings 전체 exact equality가 실패했다. API가 공식 기본값 2개를 명시적으로 추가한 결과였고, 재PUT·수집 재실행 없이 설치된 schema/service 코드와 읽기 재조회로 확인했다.

## 2. 해결 방안 및 설계

Antigravity가 생성기·artifact·fixture를 수정하고 Codex가 최소 변경으로 리뷰·통합·실제 적용을 검증했다. Claude는 출처와 저장 metadata를 확인했고 Writer는 문서·백로그·Vault를 동기화했다.

- 예약 실행 `Scheduled collection inputs`의 `limit`만 1→5로 변경한다. 수동 기본 1·최대 5는 그대로다.
- cron `0 3 * * *`, timezone `Asia/Seoul`, cursor·검토/공개 분리·기존 실패 처리 규칙은 유지한다.
- 자료 없음·검증 skip·429/5xx 등에 따라 성공 수집 건수는 5보다 적을 수 있다. 예약 5는 처리 대상의 상한이다.
- 자동 검토·공개는 하지 않으며 실제 승인과 사람의 청취·동정은 별도 절차다.

## 3. 주요 구현 내용

| 파일 | 변경 |
| --- | --- |
| `scripts/generate_n8n_audio_collection.py` | Production 이름과 예약 5종 입력 생성 |
| `n8n/robingraph-audio-collection-prod.json` | 생성된 Production artifact 갱신 |
| `tests/test_n8n_audio_collection.py` | 예약 5·수동 1·기존 최대 5 경계 회귀 |
| `docs/n8n/README.md` | 현재 운영 절에 최대 5종·첫 실행 예정·후보 3개 반영 |
| `docs/backlog/RG-507.md` | 진행 중 유지, 처리량·검토 대기 현황과 오늘 기록 연결 |

사용자가 요청한 실행 설정 변경은 workflow name과 `Scheduled collection inputs`의 limit뿐이다. API가 기본 settings 2개를 추가한 사실은 아래 검증 절에 구분했다. version ID는 새 발행에 따라 바뀌었다. TEST artifact는 byte 동일이며 앱·DB 스키마·컨테이너 이미지·credential을 변경하지 않았다.

## 4. 검증 및 테스트 결과

### 현재 저장 후보와 출처

실제 대상은 Production PostgreSQL `robingraph.ingest`다. 아래 국명은 `species_ko_names`의 학명 exact row로 확인한 값이며 새 국명을 생성하지 않았다.

| 국명 / 학명 | 파일 크기 | 녹음자·라이선스 | 상태 |
| --- | --- | --- | --- |
| 참새 / `Passer montanus` | 289,857 bytes | Vladimir Yu. Arkhipov, Arkhivov · CC BY-SA 3.0 | 검토 대기·SHA256 일치 |
| 개미잡이 / `Jynx torquilla` | 1,766,350 bytes | Kim Erlend Vidal · CC BY-SA 4.0 | 검토 대기·SHA256 일치 |
| 청딱다구리 / `Picus canus` | 734,114 bytes | Alexander Kürthy · CC BY-SA 4.0 | 검토 대기·SHA256 일치 |

출처는 각각 [참새 Commons](https://commons.wikimedia.org/wiki/File:Passer_montanus.ogg), [개미잡이 Commons](https://commons.wikimedia.org/wiki/File:Jynx_torquilla_-_Eurasian_Wryneck_XC561861.mp3), [청딱다구리 Commons](https://commons.wikimedia.org/wiki/File:Picus_canus_-_Grey-headed_Woodpecker_XC310918.mp3)다. 원 page/revision·metadata hash·license URL은 `candidates-before.json`에 보존했다.

Claude의 이번 출처 점검에서 참새 Commons 페이지는 실제 조회됐지만 나머지 Commons·XC 웹 접근은 실패해 저장된 raw description만 확인했다. 개미잡이·청딱다구리 description에는 `bird-seen:no`, song/call과 지역 설명이 있지만 `recording.location`·`recording_type` 구조 필드는 null이므로 그대로 보존했다. 원문 설명과 구조화된 값의 차이를 사람의 검토 없이 보충하지 않는다. 독립 동정·품질 rating·전문가 보증이나 실제 청취를 완료했다고 주장하지 않는다.

### 자동화 검사

Codex의 fixture 검사는 13/13 통과·실패 0·skip 0·3.282초다. Antigravity도 같은 범위 13/13·2.970초로 확인했으며 이를 26개의 독립 검사로 합산하지 않는다. 실제 5종 외부 수집을 실행한 시험이 아니다. `agy-checks.json`의 `actual_remote_changes=false`는 구현 담당 로컬 검사 시점의 값이며 이후 실제 원격 PUT이 없었다는 뜻이 아니다.

재현 명령은 `uv run python scripts/generate_n8n_audio_collection.py --target test --check`와 `uv run python scripts/generate_n8n_audio_collection.py --target prod --check`다.

TEST·Production 생성 artifact의 `--check`와 `git diff --check`는 모두 통과했다. `graphify update .`는 exit 0, 9,871 nodes·21,457 edges·514 communities로 갱신됐다. SQL parser 부재로 SQL 5개가 분석되지 않았으며 단위 테스트 skip과는 다르다. 새 웹 UI 개발은 없고 수집 현황은 채팅 표와 공개 음원·출처 링크로 안내했다.

### 실제 활성 workflow 대조

| 항목 | 확인 결과 |
| --- | --- |
| Workflow | `rgAudioCollectionProd01`, name `RobinGraph Audio Collection PROD (daily 5 species)` |
| 활성 / 발행 | active true, current·active version `d8f1c0c4-a745-4ed2-97f1-3388b7331f00` 일치 |
| 예약 | 매일 03:00 Asia/Seoul, 최대 5종 처리 |
| 원격 쓰기 | PUT 1회, 기존 active workflow가 새 버전을 자동 발행 |
| 나머지 graph | 다른 노드·connections와 전체 workflow ID 목록 동일 |
| 기존 settings | 기존 key의 값 모두 유지 |
| API 추가 기본값 | `callerPolicy=workflowsFromSameOwner`, `availableInMCP=false` |
| cursor | `prod=avilist-taxon:v2025b:10399`, fixture row 포함 전후 동일 |
| 수동 입력 | 기본 1·최대 5 유지 |
| 첫 5종 실행 | 2026-11-08 03:00 KST 예정, 아직 관측하지 않음 |

첫 settings equality 실패는 사실대로 보존했다. 설치된 API schema/service와 읽기 재조회에서 공식 기본값 2개 추가를 확인했고 기존 설정값은 유지됐다. 따라서 “settings 전체가 byte 동일”이라고 기록하지 않는다. 이 확인을 위해 재PUT하거나 수집을 실행하지 않았다. 근거는 `daily-five-receipt.json`, 변경 전 `snapshot-live.json`, 변경 후 `snapshot-after.json`이다.

최신 실제 정기 실행 `79835`는 변경 전 1종 설정으로 2026-11-07 03:00:00.152~03:00:07.427 KST에 성공했다. 오늘 청딱다구리 저장은 이 실행의 결과이며 5종 batch 성공 근거가 아니다. `execution-read.json`에서 현재 DB의 active/current 버전 일치와 설정 수정 후 추가 실행 없음을 재확인했다. 실행 조회와 JSON 저장은 성공했으나 로컬 wrapper가 workflow 배열을 dict처럼 표시하다 TypeError를 냈고, 저장 본문 재조회·형식 검사 수정으로 확인했다. 운영 수집 실패나 추가 쓰기가 발생한 것은 아니다.

## 5. 배포 및 형상 관리

[운영 workflow](https://workflow.dove-nest.com/workflow/rgAudioCollectionProd01)의 예약 설정을 기존 활성 상태에서 갱신했다. 컨테이너 배포·재시작·후보 DB 쓰기·수집 재실행·검토·공개·credential 쓰기·새 fixture 생성·Git commit/push/merge는 수행하지 않았다. 운영 자료 읽기와 설정 변경 과정의 자동 수집 provider 호출은 0이며 Claude의 별도 출처 웹 확인과 구분한다.

선별 증거는 `docs/verification/assets/2026-11-07-bird-audio-daily-five/`에 보관했다. 인증 실행 helper인 `run-node.py`, `read-live.py`, `apply-live.py`, `check.py`류는 복사하지 않았다. 이번 문서에서 다른 기능 백로그나 RG-409 상태를 변경하지 않았다.

## 6. 한계 및 후속 과제

- 첫 최대 5종 정기 실행과 다음 cursor 진행은 11월 8일 실제 결과 확인이 필요하다. 장기 반복 안정성·매일 성공 5건은 검증하지 않았다.
- 현재 후보 3개는 사람의 검토·동정·공개가 남아 있으며 RG-507 상태는 `in_progress`다.
- 구조 metadata의 null과 raw description은 구분해서 보존한다. 원문에 `bird-seen:no`가 있어 시각 확인된 녹음으로 표시하지 않는다.
- RG-409의 TEST 음원·도감 운영 승인 상태 및 과거 작업기록은 그대로 유지한다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 현황·완료 기준]]
- [[Work/RobinGraph/작업기록/5xx 데이터·분류·이름/2026-11-06-RG507-첫정기새소리수집점검|첫 정기 실행 점검·fixture 정리 이력]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
