---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: RG-204
tags: [worklog, robingraph, deployment, graph-query]
---

# [RG-204 연계] 검증된 그래프 질의·확인 흐름의 운영 배포 — 2026-10-23

## 요약

사용자가 “일단 지금까지 완성된 부분까지는 다 배포해줘”라고 요청해 운영 반영 범위를 생태 답변 UI에서 검증된 그래프 질의·확인 흐름까지 확대했다. 앞선 UI 전용 운영 배포와 달리, 이번에는 그래프 관계 질의, 질문 임베딩 기반 유형 후보·결정적 조건 처리, 5개 분류 계급·15개 형질 처리, 먹이 표현, 의미·이름 확인 후 원래 질문 재개를 함께 반영한다.

런타임은 `active + lexical`로 고정한다. RG-212의 실험적인 LLM 계획 생성·감사 코드는 이미지에 포함되지만 semantic 모드를 활성화하지 않으므로 실행 경로는 비활성이다. 코드 포함과 실제 활성화를 구분하며 모든 자연어 해석이나 RG-204·RG-205 사람 검토·RG-212 전체 완료로 기록하지 않는다.

운영 기준 main에 58파일 변경의 커밋 `33c0b67`을 push했다. 격리 TEST 후보와 NAS의 실제 운영 데이터 후보에서 각각 API 61문항이 통과한 뒤 승인 게이트를 제출했고 Jenkins PROD #8이 SUCCESS로 종료됐다. 배포 후 공개 UI 8흐름, 그래프 9문항, GET 3요청이 통과했고 실제 컨테이너의 healthy·prod·active·lexical을 확인했다. 이 기록의 완료 상태는 이번 검증된 기능 묶음의 운영 배포에 한정한다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 검증된 기능 전체의 운영 반영 | UI만 적용된 운영과 완료 기능이 있는 TEST 사이 차이를 해소 |
| 설계 및 해결 방안 | active·lexical 배포 | 검증된 고정 질의·조건 경로 활성화, 실험 semantic LLM 경로 비활성 |
| 코드 / 설정 수정 | 검색·API·UI·배포 도우미 | main 58파일, 이미지와 허용된 런타임 플래그를 같은 백업·복원 단위로 처리 |
| 실서비스 배포 | Jenkins PROD #8 SUCCESS | active+lexical 이미지 교체, 공개 화면·실제 런타임 확인 완료 |
| 검증 및 테스트 | 격리 TEST 실제 API 61/61 | 5계급·15형질을 각각 포함한 회귀이며 전체 75조합·미노출 정확도 검증 아님 |
| 형상 관리 | main `33c0b67` push 완료 | 최종 해시·이미지·운영 영수증은 아래에 기록 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

앞선 배포는 UI 변경만 운영에 올렸으므로 TEST의 의미 선택·이름 후보 확인 등은 운영에서 지원되지 않았다. 사용자는 완성된 범위를 모두 배포하기를 요청했다. 따라서 완료된 기능과 미완성 실험을 구분한 뒤 실제 운영 데이터로 검증하고 활성화할 필요가 있었다.

### 원인 분석 / 설계 검토

- TEST 코드에는 검증된 그래프 처리와 시맨틱 인터프리터 실험이 함께 있다. 최신 코드를 배포하는 것만으로 어느 경로가 켜졌는지 명확해지지 않으므로 런타임 모드를 배포 계약에 포함했다.
- 기존 배포 도우미는 이미지 교체와 런타임 설정 변경을 함께 검증·복원할 수 있어야 했다. 허용된 선택값만 전달하고 이미지와 같은 환경 백업·롤백 경로를 사용하도록 보완했다.
- TEST와 Production 데이터가 동일하다고 가정하지 않는다. 고정 회귀셋을 TEST 후보·운영 후보·최종 공개 운영에서 구분해 검증한다.

---

## 2. 해결 방안 및 설계

### 실제 활성 범위

| 기능 | 이번 운영 반영 범위 | 남는 경계 |
| --- | --- | --- |
| RG-203 그래프 관계 질의 | 분류 관계·같은 속·생태 범주 및 조합 조건의 고정 질의 | 자료에 없는 관계를 생성하지 않음 |
| RG-206~208 유형·조건 처리 | 질문 임베딩 기반 유형 후보, 원문 조건 추출·검증, 고정 질의 실행 | 자유 Cypher·질문 자동 학습 아님 |
| 분류·형질 조회 | 목·과·속·종·아종의 5계급과 15형질 처리 | 자료가 없는 아종 등은 근거 부족 유지 |
| 먹이 표현 | 곤충·고기 표현과 기존 자료 범주 연결, 특정 먹이 근거 부족 구분 | 구체적 식물·먹이 종을 일반 범주로 몰래 완화하지 않음 |
| 확인 후 질문 재개 | 식생 의미 선택, 필요한 이름 후보 선택 뒤 원래 관계 질문 계속 | 의미·종 자동 확정 없음, 미지원 복합 조건 보류 |
| 답변 UI | 생태 결과 카드·출처 접기·비교·도감 동작 | 기존 자료 한계 안내 유지 |
| RG-212 실험 코드 | 코드 배포, `lexical` 설정으로 semantic LLM 계획·감사 비활성 | 일반화 완료 아님, 별도 검증·승인 없이 semantic 활성화하지 않음 |

배포 도우미의 런타임 플래그는 선택적으로 받되 허용 목록을 검사한다. Jenkins에서 검토한 도우미를 stash하고 NAS에서 같은 파일을 unstash해 사용한다. 환경 파일의 이미지와 플래그는 같은 백업·복원 범위로 다룬다. 인증 정보는 문서·로그에 기록하지 않는다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

전체 58파일 목록은 `release-scope.json`에 보존했다. 주요 파일과 역할은 다음과 같다.

- `retrieval/graph_condition_extractor.py`, `graph_intent_schema.py`, `graph_questions.py`, `graph_semantic_router.py`, `species_questions.py` — 유형 후보 검색, 분류·형질 조건, 고정 그래프 질의와 안전 검증.
- `api/question_entities.py`, `schemas.py`, `services.py`, `drf/application.py`, `drf/urls.py`, OpenAPI 문서 — 의미 선택·이름 후보 확인 후 원문 관계 질의를 이어가는 경로와 응답 계약.
- `api/static/chat.js`, `styles.css`와 관련 프런트엔드 검사 — 확인 버튼·생태 관계 답변·비교·출처 표시.
- `retrieval/semantic_graph_intent.py`, `generation.py`, `cli.py` — 포함된 실험 계획·감사 코드와 모드 선택. 운영은 lexical 설정으로 실험 경로 비활성.
- `scripts/deploy_registry_prod.py`, `Jenkinsfile`, `ci/Jenkinsfile.production`, `.env.example` — 허용된 active/lexical 플래그와 이미지 교체를 한 배포 단위로 전달·검증·복원.
- `data/eval/graph_questions/`, 평가·감사·게시 스크립트와 관련 Python 검사 — 평가 자산과 회귀 검사. 파일 포함만으로 새 MLflow 게시를 수행했다는 뜻은 아니다.
- `docs/verification/assets/2026-10-23-completed-production/` — 고정 회귀 문항, 평가 스크립트, TEST·운영 후보·최종 운영 영수증.

### 핵심 설정

```text
ROBINGRAPH_GRAPH_INTENT_MODE=active
ROBINGRAPH_GRAPH_INTERPRETER=lexical
```

`active`는 검증된 그래프 처리 경로를 실제 응답에 사용한다는 뜻이고, `lexical`은 실험적인 semantic LLM 계획·감사 경로를 활성화하지 않는다는 뜻이다. 질문 임베딩 유형 후보 기능까지 꺼졌다는 의미로 해석하지 않는다.

---

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

| 실행 단계 | 결과 | 구분 |
| --- | --- | --- |
| 로컬 전체 Python (도우미 추가 5검사 전) | 1,205 실행: 1,166 통과 / 39 skip / 0 실패, 26.594초 | 최종 Jenkins 전체 실행 수와 혼용하지 않음 |
| 로컬 프런트엔드 | 322 통과 | 모의 DOM·API 검사 |
| 배포 도우미 | 10 단위 검사 통과 | 허용 플래그·배포 환경 처리 검사 |
| 격리 TEST 후보 | 실제 API 61/61 통과 | active+lexical, response_mocking false, 조류 DB 쓰기 0 |
| Jenkins 최종 Python | 1,210 실행: 1,171 통과 / 39 skip / 0 실패, 24.194초 | 배포 도우미 추가 검사까지 포함한 최종 릴리스 |
| Jenkins 프런트엔드 | 322 통과 / 0 실패 / 0 skip | 로컬 검사와 별도 실행 |
| Jenkins AMD64 smoke | 통과 | NAS 대상 아키텍처 이미지 fixture 실행 검사 |
| NAS 운영 데이터 후보 | 실제 API 61/61 통과 | 기존 운영 컨테이너 ID·시작 시각 유지, 공개 포트 없이 후보 검증 후 제거 |
| 그래프·변경 검사 | `graphify update .`, `git diff --check` 통과 | 코드 그래프 갱신·공백 검사이며 기능 검증과 구분 |

Jenkins 전체 검사는 `uv run --locked --extra test --extra tracing python -m unittest discover -s tests`와 `node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`로 실행했다. 로그는 `jenkins-validation.txt`에 보존했다. Python 39건은 skip으로 유지하며 이번 배포에서 실행·통과한 것으로 합산하지 않는다.

회귀셋 `cases.json`은 선행 독립 문항을 바탕으로 배포용으로 구성한 고정·피드백 노출 검사다. 5개 계급과 15개 형질을 각각 포함하지만 모든 5×15 조합을 검증한 것은 아니며 미노출 자연어 정확도로 해석하지 않는다. `test-candidate.json`은 로컬 격리 후보에서 실제 TEST API·DB 경로를 확인한 기록이며 공개 운영 검증과 구분한다.

### 실서비스 / UI 검증 증거

NAS 후보 검사는 실제 운영 데이터·신규 이미지로 61문항을 확인했다(`production-candidate.json`, `candidate-summary.json`). 기존 운영 컨테이너는 이 단계에서 교체하지 않았고 ID·시작 시각 유지가 확인됐다. 후보는 공개 포트를 게시하지 않고 검사 후 제거했다. 이 결과를 확인한 뒤 운영 승인 게이트를 제출했다.

후보 검증의 첫 job은 읽기 전용 rootfs에 `docker cp`를 시도해 평가기 실행 전 실패했다. 앱·데이터 결함이 아니며 live 앱 변경도 없었다. `docker exec` stdin을 통해 쓰기 가능한 `/tmp`에 평가기를 전달하도록 검사 도구를 수정했고 두 번째 job에서 61/61 통과했다. 첫 실패 기록을 보존한다.

배포 후 실제 운영 `https://robingraph.dove-nest.com/chat`에서 다음을 확인했다. Codex가 실행한 영수증을 Writer가 조회해 기록한 결과이며 Writer가 재실행한 것은 아니다.

| 공개 운영 검증 | 실제 결과 | 증거·범위 |
| --- | --- | --- |
| 의미·오타 확인 후 관계 조회 | 8/8 통과 | 390/1280px × 청둥오리/천둥오리 × 먹이/서식 환경; 의미 선택·필요 시 종 선택 후 최종 관계 답변 |
| 출처·도감·비교 | 출처 조작과 도감·비교 동작 확인 | 실제 운영 응답·배포 자산 사용, `browser.json` |
| 분류·형질·먹이 회귀 | 9/9 통과 | `public-graph.json`; 정상 실행과 근거 부족 결과를 각 기대값으로 판정 |
| 공개 GET | 3/3 HTTP 200 | health·OpenAPI·국명 청둥오리 lineage |
| 런타임 오류·가로 넘침 | pageerror 0 / overflow 0 | 브라우저 검사 범위이며 모든 콘솔·실기기 검사가 아님 |
| NAS 실제 런타임 | healthy, prod+active+lexical, digest 일치 | 읽기 전용 runtime job #4 SUCCESS, `runtime.json`, 조회 작업 mutations 0 |

`browser.cjs`와 `public-graph.cjs`를 `node`로 실행했고 응답을 모의하지 않았다. 문항과 viewport별 PNG를 증거 폴더에 보존했으며 Codex가 390px Chromium 스크린샷을 직접 열어 시각적으로 확인했다. 이 결과는 같은 릴리스의 실제 배포 후 검사이며 TEST 결과를 운영 성공으로 대체하지 않았다.

검사 도구에서 발생한 오류도 `postcheck-harness-notes.json`에 보존했다. 공개 9문항은 첫 시도에도 통과했으나 lineage의 국명용 `name`에 학명을 넣어 GET만 404가 발생했다. `name=청둥오리`로 수정하고 9문항+GET 3요청 전체를 재실행해 통과했다. 읽기 전용 runtime job #3은 한 줄 Jenkins 선언문의 문법 오류로 명령 실행 전 실패했으며 줄 구분·lint 확인 후 #4가 통과했다. Python urllib의 직접 HTTP는 Cloudflare에서 403으로 차단되어 실제 Chromium same-origin 검사로 확인했다. 앱 코드 수정이나 운영 롤백을 필요로 한 실패는 아니다.

---

## 5. 배포 및 형상 관리

- **사용자 승인**: “일단 지금까지 완성된 부분까지는 다 배포해줘”. 검증된 기능 묶음의 운영 반영 승인이다.
- **대상**: NAS Production 앱, Jenkins PROD #8.
- **Git**: main `33c0b67ef6a0ab23e3f3d20f6112ee38d43ba83b`, 58파일. 이전 커밋은 UI 전용 `54b4cd94cd032b3d2c25a55b796b383ff94e0a20`이다.
- **운영 이미지**: `ghcr.io/evodmik/robingraph@sha256:f000a7219d365cb69a33acde3bea11b57a5a8054af79db75a3832684c849b280`.
- **Jenkins**: [RobinGraph-PROD #8](http://dove-jenkins/job/RobinGraph-PROD/8/) SUCCESS. 실제 운영 데이터 후보 61문항 통과 뒤 사용자 승인에 근거해 admin 게이트를 제출했다.
- **영수증**: `production-release.json`의 `production_verified: true`, `deployment-receipt.json`의 `state: verified`, 일치하는 revision·digest를 확인했다.
- **실제 런타임**: `runtime.json`에 같은 이미지 digest, healthy, `ROBINGRAPH_DEPLOY_TARGET=prod`, active·lexical을 기록했다. 코드가 포함됐다는 추정이 아니라 실행 중 컨테이너를 조회한 결과다.
- **배포 설정**: active+lexical. 검토된 도우미로 이미지·런타임 플래그를 함께 처리한다.
- **실험 비활성**: semantic LLM 계획·감사 코드는 포함되나 실행 모드로 활성화하지 않는다.
- **데이터 범위**: DB 마이그레이션·벡터 인덱스 교체·자료 백필·수집 명령 없음. 전체 DB 불변 감사는 미실행이다.
- **롤백·정리**: 이미지·환경 파일의 복원 경로를 갖추었으나 실제 운영 롤백은 실행하지 않았다. 후보 컨테이너를 제거하고 임시 preflight job을 비활성화했다.
- **TEST·인증 정리**: TEST는 기존 `robingraph-api:test-ecology-layout-d1958a21194a` 이미지를 유지하며 healthy다. 사용한 임시 Jenkins 인증 파일은 삭제했고 비밀값은 기록하지 않았다.

---

## 6. 한계 및 후속 과제

- RG-204 상위 과제·RG-205 사람 검토·RG-212 시맨틱 일반화는 전체 완료 처리하지 않는다.
- 고정 문항의 성공은 모든 자연어 표현 지원을 뜻하지 않는다. 부정·수치·여러 종 등 복합 조건의 보류와 자료 부족은 허용된 결과로 구분한다.
- 실험 코드가 이미지에 있다는 사실과 운영에서 실행된다는 사실을 구분한다. 이번 검증은 active+lexical 동작에 한정한다.
- DB 전체 체크섬 감사·물리 모바일·Safari·Firefox는 미검증이다. 작은 브라우저 viewport 결과를 실기기 검증으로 표현하지 않는다.
- Writer는 실제 영수증을 바탕으로 문서를 작성했다. 저장소 반영용 scratch와 같은 본문을 Obsidian에 저장하고 재조회로 일치를 확인했다. 관련 인덱스에는 링크만 추가했고 기존 본문을 보존했다. 다른 작업의 완료 상태와 전체 백로그는 변경하지 않았다. 저장소 반영은 Codex 최종 검토 후 수행한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-생태-관계-답변-UI-운영-배포|선행 UI 전용 운영 배포]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-오타와-의미-확인-후-관계-조회|선행 의미·이름 확인 흐름 TEST 검증]]
