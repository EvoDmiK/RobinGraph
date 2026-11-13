---
created: 2026-11-11
date: 2026-11-11
project: RobinGraph
type: worklog
status: completed
task_id: RG-215
tags: [worklog, robingraph, production, bird-explorer]
---

# [RG-215] 새소리를 제외한 신규 기능 운영 배포

## 요약

사용자가 “새소리 첨부 기능말고, 새로 추가한 기능 운영서버에도 배포해줘”라고 명시 승인했다. TEST 전체 이미지를 그대로 승격하지 않고, 실제 운영 기반 소스에 새소리 코드를 제외한 변경만 합친 별도 snapshot을 검증·배포했다. 조건 검색, 페이지네이션, 공유 도감 카드, 캐시와 라이트 테마가 운영에 반영됐다. 후속 조건·답변 피드백 코드도 포함했다.

Jenkins [RobinGraph-Explorer-Release #2](http://192.168.219.99:8080/job/RobinGraph-Explorer-Release/2/)는 SUCCESS다. NAS 운영 앱은 healthy이며 공개 Chromium 검증도 통과했다. 운영 도메인 DB 쓰기 명령·마이그레이션은 실행하지 않았다. TEST 앱의 ID·이미지·시작 시각과 기존 main polling 작업 정의는 전후 동일하다. Writer 도구의 quota 제한으로 문서 작업을 Codex가 인계받았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 새 기능 운영 반영, 새소리 제외 | TEST에는 새소리 재생·수집·검토 기능이 섞여 있어 전체 이미지 승격 불가 |
| 설계 및 해결 방안 | 승인 범위 snapshot | 실제 운영 revision 기반, 공통 파일의 새소리 코드까지 제거 |
| 코드 / 설정 수정 | 실행 파일 22개 변경 | 조건 검색·카드·후속 질문·피드백·메타데이터 캐시·라이트 테마 |
| 실서비스 배포 | NAS AMD64 앱 교체 | immutable digest, 별도 후보 검사, admin gate, 캐시 전용 volume |
| 검증 및 테스트 | 로컬·Jenkins·실제 운영·공개 UI | Python 218, Node 342, fixture 및 실제 운영 API·브라우저 통과 |
| 형상 관리 | 미커밋 snapshot 배포 | 새 commit/push/merge 없음; 기존 Git revision은 기반 식별자 |

## 1. 작업 배경 및 문제 분석

탐색기 결과의 긴 출처 표시, 도감 페이지 이동, 카드 정보 지연, 뒷면 체중 중복, OS에 따른 다크 테마와 20종 상한을 개선했다. API·공유 카드·CLI는 새소리 기능과 파일을 공유하고 있어 파일 전체 복사만으로 배포 범위를 분리할 수 없었다.

읽기 전용 NAS inventory에서 기존 image와 revision을 확인했다. Git과 비교한 실행 소스에는 차이가 없었다. 이미지에만 있던 `species_profile.py.orig`는 실행하지 않는 백업 파일로 구분했다. PostgreSQL·Neo4j·n8n의 배치와 운영 수집 sidecar는 변경하지 않았다.

## 2. 해결 방안 및 설계

- 운영 기반 `5056ccba9e75a891cc133a6f371b49deb5dbc598`에서 시작해 승인된 비음원 변경만 overlay했다. 새소리 UI·provider metadata·수집/검토 API·관련 migration은 후보에 없다. 사용자 제외 범위의 새소리 명칭 테스트 5개도 실행 대상에서 제외했다.
- 결과는 20종씩 표시하며 위·아래 이전/다음·페이지 선택, URL 복원, 조건 변경 시 첫 페이지 복귀를 제공한다. 먹이 비율은 전체 결과에서 정렬한 뒤 페이지로 나눈다. 자연 정렬의 깊은 페이지는 정렬된 prefix를 읽는 현재 구현이며 전송량 증가 시 count/SKIP 최적화가 후속이다.
- 기본 카드와 사진·추가 설명 조회를 분리하고, 공개 사진/설명 메타데이터를 24시간 캐시한다. 이미지 바이트 자체를 서버에 저장하는 기능이 아니다. 동일 측정값은 한 행에 표시하면서 출처의 통계 metadata를 유지한다.
- NAS에 `robingraph-prod-species-cache` 전용 volume과 cache root만 추가했다. 소유자 10001:10001, mode 700, 컨테이너 읽기/쓰기 검사를 통과했다. 기존 env·Compose는 0600 백업으로 보존했고 실패 복구 절차를 준비했으나 실제 롤백은 실행하지 않았다.

## 3. 주요 구현 내용

운영 기반 대비 실제 변경 파일:

- `src/robingraph/api/drf/application.py`
- `src/robingraph/api/drf/openapi.json`
- `src/robingraph/api/drf/openapi_ingest.json`
- `src/robingraph/api/drf/serializers.py`
- `src/robingraph/api/drf/urls.py`
- `src/robingraph/api/drf/views.py`
- `src/robingraph/api/feedback.py`
- `src/robingraph/api/followup.py`
- `src/robingraph/api/schemas.py`
- `src/robingraph/api/services.py`
- `src/robingraph/api/static/chat.js`
- `src/robingraph/api/static/explore.css`
- `src/robingraph/api/static/explore.html`
- `src/robingraph/api/static/explore.js`
- `src/robingraph/api/static/index.html`
- `src/robingraph/api/static/styles.css`
- `src/robingraph/cli.py`
- `src/robingraph/retrieval/external_cache.py`
- `src/robingraph/retrieval/graph_questions.py`
- `src/robingraph/retrieval/species_notes.py`
- `src/robingraph/retrieval/species_profile.py`
- `src/robingraph/tracing.py`

배포·검증 도구와 영수증은 `docs/verification/assets/2026-11-11-approved-non-audio-production/`에 보존했다. `non-audio-source.patch`를 운영 기반에 적용하면 manifest 239개 파일의 SHA가 배포 snapshot과 모두 일치한다. 검증은 `patch-reconstruction.json`에 기록했다.

캐시 설정:

```text
ROBINGRAPH_SPECIES_CACHE_ROOT=/var/lib/robingraph/species-cache
volume: robingraph-prod-species-cache
TTL: 86400 seconds
```

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

- 로컬 Python: 기능/API/캐시/설명/피드백 등 194개 + 프로필 24개 = 218 통과, 실패 0. `backend.log`, `profile-tests.log`.
- Jenkins Python: 같은 선택 범위 218 통과, 실패 0, 8.811초. Django check도 통과. 전체 저장소 suite 실행으로 해석하지 않는다.
- Jenkins Node: `node --test --test-skip-pattern=recording tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js tests/frontend/explore_ui.test.js`, 342 통과·실패 0. 새소리 이름 테스트 5개는 배포 범위에서 명시 제외했다.
- 최초 로컬 Node name-pattern 사용 시 제외가 적용되지 않아 새소리 테스트 5개가 실패했다. `test-skip-pattern`으로 명시 제외한 재검사와 Jenkins 검사는 통과했다. 기능 실패를 숨기기 위한 제외가 아니라 사용자가 배포에서 제외한 구현의 테스트다.
- AMD64 image의 network-none fixture health·OpenAPI 및 새소리 route 부재 검사 통과. fixture를 실제 운영 DB 검사와 구분한다.

### 실서비스 / UI 검증 증거

- 실제 운영 데이터를 읽는 별도 후보 컨테이너: 공개 포트 없이 GET health/OpenAPI/조건 검색/기본 프로필 검사, 원래 앱 ID 불변 확인 후 제거. `production-candidate.json`.
- 배포 후 운영 컨테이너: 같은 GET 검사 및 소스 파일 SHA, 새소리 route 404·profile 필드 부재, env·캐시 mount 검사 통과. `production-live.json`, `production-release.json`.
- 공개 HTTPS Headless Chromium CDP: 1280/390/320×1000 뷰포트, 가로 넘침 0, OS dark 요청에서도 light only. 41종을 20·20·1종으로 조회해 누락/중복 없음, 전체 먹이 비율 순서·키보드·드롭다운·reload·첫 페이지 초기화·큰 페이지 clamp·422 검증 통과.
- 운영 공유 카드 열기·뒷면 전환·새소리 UI 부재 통과. 이번 기본 카드 표시 시간은 738ms이며 사진/AI 설명 완료 시간이나 모든 종의 성능 보장이 아니다. JS 예외 0. `actual-browser.json`, `production-card-back.png`.
- TEST ID `4d800f4b2076637053e8daeb8af2ed6ae2b9ddb8c40e32427a805be90fdf3099`·이미지·시작 시각 불변 확인. `test-before.json`, `test-after.json`.
- 승인 조회의 잘못된 API 경로는 404였고 실제 입력 ID의 첫 글자가 대문자인 것을 확인한 뒤 정확한 gate를 한 번 제출했다. 승인 전 앱 교체는 없었다.

## 5. 배포 및 형상 관리

- 대상: NAS `robingraph-api`, [운영 탐색기](https://robingraph.dove-nest.com/explore).
- Jenkins: `RobinGraph-Explorer-Release #2 SUCCESS`. 검증된 후보의 digest·source SHA를 대조한 뒤 사용자 명시 승인에 근거해 admin gate 제출.
- 기반 Git revision: `5056ccba9e75a891cc133a6f371b49deb5dbc598`. 신규 기능 commit SHA가 아니다.
- source SHA256: `5bf5c154475d9332ae8c2e8b35959c287bbfa3aecf6146c341768059077d0890`.
- 배포 image: `ghcr.io/evodmik/robingraph@sha256:997ce4f410605011a17924b8ea1784849282f8931c22a27c4a11aa706c16e65f`.
- 신규 container: `f62ab640cd9548bc959470feb7cae1bee8fb66b3291c90b809076b00d1dfde92`, 시작 UTC `2026-11-11T08:36:14.785896403Z`, healthy.
- 이전 image: `ghcr.io/evodmik/robingraph@sha256:963b4836ccf77155a8ca94efa105e66c60f799d05e75f6ae6c5b6ce710b05edc`. env·Compose 백업 경로는 `production-release.json`의 backup에 기록했다. 인증값은 기록하거나 검증 자산으로 복사하지 않았다.
- 기존 active/semantic·MLflow 실험 50·DB endpoint·서명 설정을 보존했다. main polling job 정의 불변 확인. 일회성 release job은 성공 후 disabled 처리했다.
- 코드 작업 브랜치는 dev-codex이며 commit/push/merge/이력 변경은 하지 않았다. TEST 전체 snapshot과 운영 제외 범위 snapshot은 다른 소스다.

## 6. 한계 및 후속 과제

물리 모바일·Safari/Firefox·전체 DB checksum·실제 실패 롤백·호스트 재부팅은 검증하지 않았다. 운영 DB에 마이그레이션/자료 수정 명령을 실행하지 않았다는 근거를 전체 DB byte 불변 검증으로 확대하지 않는다. 기존 추적 동작은 유지한다. 추가 AI 설명의 모든 종 성공, 모든 프로바이더의 latency, 피드백의 실제 운영 저장·MLflow 재조회는 이번 공개 검사에 포함하지 않았다.

RG-409·RG-507 새소리 작업 상태는 보존했다. RG-213·RG-603의 코드는 배포에 포함됐지만 이번 배포만으로 사람 검토나 실제 운영 피드백 검증을 완료로 바꾸지 않았다. 영속 캐시는 배포 후 cold start에서 채워진다.

## 관련 문서

- [[Work/RobinGraph/백로그 상세/RG-215|조건으로 새 찾기 백로그]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [최초 TEST 구현·검증 기록](2026-11-10-bird-explorer.md)
