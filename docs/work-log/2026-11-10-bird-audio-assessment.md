---
created: 2026-11-10
date: 2026-11-10
project: RobinGraph
type: worklog
status: completed
task_id: RG-507
related_tasks: [RG-409]
tags: [worklog, robingraph, bird-audio, assessment, test]
---

# [RG-507] 음원 후보별 검토 기록 저장


## 요약

사용자가 재생·출처·동정 근거·판정·메모를 후보별로 저장하는 기능을 승인했다. 기존 읽기 전용 검토 화면에서 검토 의견을 남길 수 있도록 확장하되, 이 기록은 공개 승인과 분리했다. 최신 기록은 기존 candidate.data.assessment JSON에 저장하고 기존 status·legacy review·taxon_verified·publication gate·원출처·음원은 유지한다. [TEST 화면](https://robingraph-test.dove-nest.com/audio-review)에서 실제 저장·재조회·권한·충돌을 확인하고 자동화 검토 기록을 조건부 복원했다.

Claude가 backend 저장·인증·충돌 검사를, Antigravity가 화면 입력·저장 동작을 구현했다. Codex는 통합·검증·TEST 배포, Writer는 근거 기반 문서와 Vault 동기화를 담당한다. 운영 쓰기·배포와 Git 작업은 이번 승인 범위에 없다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 현재 상태 |
| --- | --- | --- |
| 요구사항 | 후보별 검토 의견 저장 | 사용자 구현 승인 |
| 설계 | assessment 최신 기록·공개 gate 분리 | 구현·단위 검사 완료 |
| 코드 / 설정 | 별도 작성 키·저장 API·UI 입력 | 최종 구현·회귀 확인 |
| 실서비스 | TEST 배포 완료 | 공개 TEST 저장·재조회·복원 확인 |
| 검증 | 격리 schema 저장·재조회·충돌 완료 | 실제 TEST UI 저장·충돌·복원 확인 |
| 형상 관리 | 기존 11/7·9 미커밋 변경 보존 | commit/push 없음 |

## 1. 작업 배경 및 문제 분석

11/9 화면은 음원·출처·검토 상태를 읽을 수 있었지만 검토자가 확인한 결과를 후보에 남기는 기능은 없었다. 사용자 요청에 따라 항목별 기록을 추가한다. 재생 성공만으로 동정이 확인되거나 자료가 공개되는 흐름을 만들지 않는다.

동시 검토에서는 오래된 화면의 저장이 다른 사람의 기록을 덮을 수 있다. expected_updated_at을 필수로 받아 일치하지 않으면 409로 거부하는 계약을 사용한다. 인증 토큰이 메모에 잘못 포함돼 저장·반사되지 않도록 전용 토큰을 포함한 입력은 422로 차단한다.

## 2. 해결 방안 및 설계

별도 작성 전용 키는 조회·private preview·assessment 저장만 허용한다. 기존 읽기 키의 조회는 유지하지만 저장은 401, 수집 ingest 키의 assessment 저장도 거부한다. 자동 공개·승인 권한으로 확대하지 않는다.

채택 후보는 공개 승인과 다르고, 제외 판정은 파일 삭제가 아니다. 재생이 성공해도 체크 상태를 자동 갱신하지 않는다. 실제 검토자가 항목을 선택하고 저장해야 한다. 최신 기록만 보관하며 변경 이력 누적 저장 기능으로 설명하지 않는다.

## 3. 주요 구현 내용

| 필드 | 계약 |
| --- | --- |
| reviewer | 검토자 |
| playback | unchecked / normal / silent / file_error |
| source | unchecked / checked |
| identification | unchecked / uploader_only / additional_evidence / uncertain |
| decision | pending / hold / candidate / exclude |
| note | 최대 2,000자 |
| identification_note | 최대 1,000자, additional_evidence 선택 시 필수 |
| assessed_at | 서버 기록 시각 |
| expected_updated_at | 필수, 충돌 보호용 기존 갱신 시각 |

저장 대상은 candidate.data.assessment다. 최신 평가 JSON만 저장하며 기존 후보 status와 원자료·legacy review를 변경하지 않는다.

| 파일 / 범위 | 변경 내용 |
| --- | --- |
| `src/robingraph/ingest/audio.py`, `audio_store.py`, `audio_collector.py` | assessment 검증·저장·읽기, 갱신 시각 충돌 보호와 기존 수집 계약 유지 |
| `src/robingraph/api/drf/audio_views.py`, `urls.py`, `openapi_audio.json` | assessment 경로·전용 키 권한·응답/오류 계약 |
| `src/robingraph/api/drf/application.py`, `src/robingraph/cli.py`, `.env.example` | 별도 assessment 키 환경 연결 |
| `src/robingraph/api/static/audio-review.js`, `.html`, `.css` | 항목별 입력·저장·재조회·충돌 안내·읽기 권한에서 폼 비노출 |
| `tests/test_audio_assessment.py`, `tests/frontend/audio_review_ui.test.js` | 입력·키·충돌·원자료 보존·폼/메모/재생 회귀 |

파일 내용은 `backend.patch`, `ui.patch`로 보관했다. 두 패치는 기존 11/9 상태 대비 이번 변경이며 root의 전체 미커밋 diff에는 11/7·9 변경도 있어 구분한다. `can_assess=true`일 때만 작성 폼을 표시하고 읽기 전용 키로는 기존 저장 기록을 조회할 수 있다. 비밀 키 값·raw env·인증 helper는 문서에 복사하지 않는다.

## 4. 검증 및 테스트 결과

### 단위·fixture 검사

```sh
PYTHONPATH=src:tests uv run --locked --extra test python -m unittest tests.test_audio_assessment tests.test_audio_review tests.test_audio_collection tests.test_audio_collector tests.test_django_runtime tests.test_drf_parity -q
node --test tests/frontend/audio_review_ui.test.js tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
```


최종 Python 62/62 통과·실패 0·skip 0·2.104초, 프런트엔드 354/354 통과·실패 0·skip 0·307.493792ms다. 각각 `backend-final-tests.log`, `frontend-tests.log`에 결과를 보존했다. 합성 API와 무음 WAV를 이용한 별도 Chromium fixture는 1280/390에서 초기 unchecked, 수동 저장, 메모 텍스트 처리, 충돌 시 입력 유지, 확대 폼/플레이어 넘침 없음, 연결 해제를 확인했다. 이것은 실제 TEST 저장이나 청취가 아니다.

### 실제 격리 PostgreSQL·Django ASGI

대상 DB는 `robingraph_test`, 일회용 schema는 `test_audio_assessment_43b0fa7be504`다. 실제 PostgreSQL과 in-process 실제 Django ASGI를 사용했다. 첫 저장 200·재조회 일치, 오래된 버전 저장 409, 읽기 키 저장 401, 두 번째 저장 200을 확인했다. 원출처 자료·legacy review·candidate status는 유지됐고 공개는 하지 않았다. provider 요청 0, 일회용 schema 제거·공유 ingest 후보 불변을 확인했다(`isolated-db.json`).

### 실제 공개 TEST 브라우저

실제 공개 HTTPS TEST에서 실존 후보 1개의 폼으로 자동화용 검토 기록을 저장한 뒤 새로 조회해 일치를 확인했다. 읽기 전용 키에는 폼이 없고 저장 POST는 401이었다. assessment 키의 stage/review/publish 요청도 각각 401로 차단됐다. 오래된 expected_updated_at 저장은 409로 거부됐다.

1280/390px Chromium에서 Enter로 연결, 키 입력 비움·storage 없음, 가로 넘침 0을 확인했다. 실제 native audio 디코딩 후에도 재생 확인 항목은 자동 체크되지 않았다. 저장 메모에 넣은 XSS 검사 문자열은 텍스트로만 표시됐고 실행 0·JS 예외 0·provider 요청 0이었다. 자동화 메모는 기능 검사 자료이며 사람이 실제 동정·청취를 완료했다는 기록이 아니다.

이 단계는 격리 schema 시험과 달리 **공유 TEST DB의 실제 후보 annotation 쓰기와 복원**이다. `shared-db-restore.json`에 따라 원 data·legacy review·status를 복원/보존하고 updated_at은 과거로 되돌리지 않았다. 조건부 복원으로 동시 변경을 덮어쓰지 않았고 실제 공개 0이었다. `actual-assessment-browser.json`과 1280/390 실제 캡처를 보관했고 Codex가 화면을 시각 검토했다.

물리 모바일·Safari·Firefox·사람의 청취·전문 동정은 미실행이다. 초기 실행 도구에서 plain `python` 명령이 없어 한 번 검증을 시작하지 못했지만 `python3`로 바로잡은 뒤 최종 실제 검증을 마쳤다. 앱 기능 실패로 분류하지 않는다.

최종 root 로그 `graphify-final.log`의 `graphify update .`는 exit 0, 9,991 nodes·21,739 edges·499 communities로 갱신됐고 `git diff --check`도 통과했다.

자동화용 모의 검토 기록을 실제 사람의 청취·동정 완료로 표현하지 않는다. 실제 DB 저장 검사와 물리 청취·실기기·타 브라우저 검증 범위를 분리한다.

## 5. 배포 및 형상 관리

ARM64 TEST 이미지 `robingraph-api:test-audio-assessment-9afd12fe5956`를 배포했고 source SHA는 `9afd12fe595659b6f610c844216fcb6edfce3f5df7e35eed9fd57149898b4f0f`다. base revision `9ddea521847093b071c9d3436fb908313c4b1f2c`의 미커밋 snapshot이다. release는 `audio-assessment-9afd12fe5956-5912e5`, 영수증 state는 verified다. network-none fixture와 배포 source manifest·compose model을 확인했고 signing key는 보존했다. 직전 `audio-review-f94bade119bd-1e903c`는 영수증에 보존했다. TEST 전용 작성 키는 `/Users/kimdove/robingraph-test/private/audio-assessment.key`(0600), 기존 조회 전용 키는 같은 폴더의 `audio-review.key`다. 값은 기록하거나 증거로 복사하지 않았다. Production에는 작성 키를 설정하지 않았다. Production 쓰기·배포·재시작, Git commit/push/merge는 수행하지 않았다. 기존 11/7·9 작업 문서·미커밋 변경은 보존한다.

## 6. 한계 및 후속 과제

- 검토 기록 저장은 공개 승인·원자료 수정·파일 삭제가 아니다.
- 최신 assessment만 저장하므로 전체 검토 변경 이력 기능과 구분한다.
- RG-507은 진행 중을 유지하고 RG-409 및 과거 작업기록을 변경하지 않는다.
- 실제 사람의 판단 입력과 Production 반영은 후속 범위다. RG507은 기능 저장 검증과 사람의 검토·공개 단계를 구분한다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-507|RG-507 수집·검토·저장]]
- [[Work/RobinGraph/작업기록/5xx 데이터·분류·이름/2026-11-09-RG507-새소리수집점검과검토화면|읽기 전용 검토 화면 이력]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
