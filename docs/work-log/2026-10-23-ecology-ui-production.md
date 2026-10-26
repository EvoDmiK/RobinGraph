---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: RG-212
tags: [worklog, robingraph, ui, production]
---

# [RG-212 UI 후속] 생태 관계 답변 레이아웃 운영 반영 — 2026-10-23

## 요약

사용자가 TEST에서 확인한 생태 관계 답변 화면을 “운영 배포해줘”라고 명시적으로 승인했다. Codex는 운영 `main`을 기준으로 별도 작업 공간에서 UI 변경만 이식하고, 기존 Jenkins PROD 경로로 배포를 진행했다. TEST 작업 트리의 의미 해석·확인 질문·API 실험 변경을 통째로 운영에 올리지 않았다.

반영 범위는 생태 결과의 중복 설명 제거, 범주 배지와 종별 비교 행, 접힌 출처, 보조 도감 버튼의 배치다. 운영의 기존 질문 해석·응답 계약은 유지한다. 운영 확인 질문은 기존 지원 표현인 `청둥오리랑 식성이 비슷한 새 알려줘`를 사용한다. TEST의 `식생` 의미 선택이나 오타 확인 흐름이 이번 배포로 운영에 추가됐다는 뜻이 아니다.

UI 커밋 `54b4cd9`를 `main`에 push했고 Jenkins PROD #7이 **SUCCESS**로 종료됐다. 실제 운영 자산과 API로 공개 Chromium 4개 흐름을 검증했으며, 배포된 JS·CSS 해시가 커밋과 일치했다. 이 문서의 `completed`는 승인된 UI 운영 배포에 한정한다. RG-212 전체는 진행 중으로 유지한다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 승인된 UI 개선의 운영 반영 | TEST에서 검증한 생태 답변 레이아웃을 운영에 적용 |
| 설계 및 해결 방안 | 운영 main에 UI만 이식 | 격리 작업 공간에서 3파일 변경, TEST의 미커밋 백엔드 실험 제외 |
| 코드 / 설정 수정 | JS·CSS·프런트엔드 검사 | 80줄 추가·11줄 삭제, API·데이터 모델 변경 없음 |
| 실서비스 배포 | Jenkins PROD #7 SUCCESS | NAS 앱 교체·검증 영수증 verified |
| 검증 및 테스트 | 프런트엔드 318·Python 992 통과 | Python 39 skip; 실제 공개 Chromium 4흐름·GET 3요청 통과 |
| 형상 관리 | main `54b4cd9` | 기존 main `7267df6` 기반, force push 없음 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

생태 관계 답변은 동일 종 목록과 설명이 일반 답변·탐색 영역에 반복되고, 큰 도감 버튼과 탐색 버튼·출처가 이어져 정보 위계가 약했다. 선행 TEST 작업에서 기존 탐색기를 답변 안에 재사용하고 출처를 접어 핵심 결과를 정리했다. 사용자의 이번 요청은 그 화면 변경의 운영 배포다.

### 원인 분석 / 설계 검토

TEST 작업 트리에는 UI 외에 시맨틱 해석·의미 확인·이름 후보 흐름과 관련 API 변경이 함께 존재한다. 해당 작업 트리를 그대로 운영 배포하면 UI 승인 범위를 벗어난 실험이 섞인다. Codex는 운영 기준 `main`에서 이번 UI 패치만 재구성하고 차이를 검토했다.

---

## 2. 해결 방안 및 설계

1. `/tmp/rg-prod-ecology-ui`의 격리 작업 공간에서 운영 main `7267df6`을 기준으로 UI 변경을 이식했다.
2. `chat.js`, `styles.css`, 관련 프런트엔드 검사만 수정했다. 기존 운영 API의 `ecological_related` 결과를 재사용한다.
3. 유효한 생태 그룹이 렌더링된 뒤 중복 설명·목록을 제거한다. 비어 있거나 오래된 구조화 근거에서는 원래 설명을 유지한다.
4. 기존 Jenkins의 main 검사·빌드·운영 반영 절차를 사용한다. TEST 실험 이미지를 승격하지 않는다.

형상 관리와 배포는 사용자의 운영 배포 승인에 필요한 범위에서 진행했다. 새 API 계약·질문 해석 일반화·조류 데이터 수정은 이 작업의 범위가 아니다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `src/robingraph/api/static/chat.js` — 생태 답변 inline 결과, 성공 후 중복 설명 제거, 범주 배지, 근거 묶음과 보조 도감 버튼.
- `src/robingraph/api/static/styles.css` — 답변 카드·종 행·출처·작은 화면의 간격과 시각 위계.
- `tests/frontend/chat_ui.test.js` — 직접 생태 답변 렌더링과 빈/오래된 근거 fallback 회귀.
- `docs/verification/assets/2026-10-23-ecology-ui-production/` — 이번 운영 배포·검증 영수증. 문서는 Codex 검토 후 저장소에 반영한다.

### 핵심 동작

```text
기존 운영 생태 질문 → 기존 ecological_related 응답
→ 범주 배지 + 종별 비교 행 + 접힌 출처
→ 유효한 그룹 렌더링 성공 후 중복 문장 목록 제거
```

동일 생태 범주는 실제 공존·포식 관계나 같은 먹이 종을 먹는다는 의미가 아니다. 기존 근거·제한 안내와 안전 링크를 유지한다. 서버 설정·API·DB 코드 변경은 해당하지 않는다.

---

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

| 수행자 / 검증 | 결과 | 범위 |
| --- | --- | --- |
| Codex chat·birds 프런트엔드 검사 | 318 통과 / 0 실패 / 0 건너뜀 | 모의 DOM·API, 실제 운영 데이터 검사 아님 |
| 독립 읽기 전용 UI 리뷰 | chat 314 통과 | 운영 브랜치 패치와 기존 계약 검토; 별도 담당자 실행 |
| Jenkins Python | 1,031 실행: 992 통과 / 39 건너뜀 / 0 실패, 22.832초 | skip 포함 전체 실행 수를 통과 수로 표시하지 않음 |
| Jenkins chat·birds 프런트엔드 | 318 통과 / 0 실패 / 0 건너뜀 | 로컬 결과와 별도 Jenkins 단계 실행 |
| Jenkins AMD64 fixture smoke | 통과 | 배포 대상 아키텍처 이미지 실행 검사; 실제 조류 데이터 검증 아님 |

Jenkins 실제 검사 명령은 다음과 같다. 프런트엔드 318개는 chat 314개와 birds 4개다.

```sh
uv run --locked --extra test --extra tracing python -m unittest discover -s tests
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
```

Jenkins의 `Tests`·`AMD64 fixture startup smoke`·`Production approval`·`Deploy and verify NAS Production` 단계가 실행됐고 최종 SUCCESS로 끝났다(`jenkins-validation.txt`, `jenkins.json`). Python 39건은 제외 상태로 기록하며 이번 UI 배포에서 제외 검사를 새로 실행하거나 완료로 전환하지 않았다. TEST에서 수행한 8+2개 브라우저 결과를 운영 결과로 재사용하지 않는다.

### 실서비스 / UI 검증 증거

실제 운영 `https://robingraph.dove-nest.com/chat`에서 배포 후 검증했다. 아래 수치는 Codex가 실행한 영수증을 Writer가 조회한 결과이며 Writer가 재실행한 결과는 아니다.

| 실제 운영 검증 | 결과 | 증거·구분 |
| --- | --- | --- |
| 390/1280px × 식성/서식 환경 | 4/4 통과 | 실제 배포 자산, 실제 운영 API, 응답·정적 자산 가로채기 없음 |
| 질문·결과 | 최종 answer, 각 3종, 요청한 관계 범주 일치 | `청둥오리랑 식성이 비슷한 새 알려줘`, `청둥오리랑 서식 환경이 비슷한 새 알려줘`; 중복 글머리 목록 없음 |
| 출처 키보드 조작 | 4/4 통과 | Enter로 출처 열기·닫기, 실제 출처 링크 존재 |
| 비교·도감 | 실제 비교 1회, 팝업 열기·Escape 1회 | 1280px 식성 결과에서 확인 |
| 오류·가로 넘침 | pageerror 0, 가로 넘침 0 | 작은 화면은 브라우저 viewport, 물리 모바일 아님 |
| 배포 자산 해시 | JS·CSS 모두 커밋과 일치 | 각 시나리오에서 no-store 조회·SHA256 비교 |
| 공개 GET | 3/3 HTTP 200·기본 계약 통과 | `/health`, `/openapi.json`, 청둥오리 lineage; `public-api.json` |

실행 자산은 `browser.cjs`, `public-api.cjs`이며 각각 `node`로 실행했다. `browser.json`의 `api_mocked: false`, `static_override: false`는 실제 배포 후 검증을 구분한다. Chromium은 `reducedMotion: reduce`로 실행했다. `production-*.png` 화면을 보존했고 Codex가 최종 1280px 스크린샷을 직접 열어 시각적으로 확인했다. 물리 모바일·Safari·Firefox와 DB 전체 체크섬 감사는 수행하지 않았다.

배포 전에는 실제 운영 API를 사용하되 브라우저의 JS·CSS 두 파일만 로컬 변경본으로 가로챈 preflight 4흐름이 통과했다(`preflight.json`, `static_override: true`). 운영 API 응답 모의는 아니지만 아직 운영에 올라간 자산의 검증도 아니다. 첫 실행은 검사 도구가 `?v=`가 붙은 자산 URL을 놓쳐 이전 JS를 읽었고, 자산 가로채기 패턴을 고친 뒤 통과했다. 이를 앱·데이터 결함으로 기록하지 않으며 최초 실패 로그도 보존한다.

---

## 5. 배포 및 형상 관리

- **사용자 승인**: “운영 배포해줘”. 이번 생태 UI 반영에 대한 명시 승인이다.
- **운영 대상**: NAS 앱, Jenkins PROD main 배포 경로.
- **Git 기준**: `main`의 `7267df6`에서 시작.
- **변경 커밋**: `54b4cd94cd032b3d2c25a55b796b383ff94e0a20` — UI 3파일, 80줄 추가·11줄 삭제.
- **원격 반영**: main push 완료, force push 없음.
- **Jenkins**: [RobinGraph-PROD #7](http://dove-jenkins/job/RobinGraph-PROD/7/) — `building: false`, `result: SUCCESS`.
- **운영 이미지**: `ghcr.io/evodmik/robingraph@sha256:dc4974f9d82e4625d8f61361caf82f4bb1b7a841ad8f433d76bc3fdb89f0f91b`.
- **교체 검증**: `production-release.json`의 `production_verified: true`, `deployment-receipt.json`의 `state: verified`, 동일 revision·digest를 확인했다.
- **승인 게이트**: 사용자 명시 배포 승인에 근거해 Jenkins admin 게이트를 제출했고 `Approved by admin` 이후 실제 배포·검증 단계가 실행됐다.
- **격리**: TEST dirty 백엔드·시맨틱 실험·의미 선택 API는 이번 커밋에 포함하지 않는다.
- **데이터 변경**: DB 마이그레이션·백필·자료 변경 명령 없음. 전체 DB 불변 감사는 미실행이므로 모든 DB 바이트가 동일하다고 주장하지 않는다.
- **환경·다른 브랜치**: TEST 이미지는 `robingraph-api:test-ecology-layout-d1958a21194a`로 그대로이며 healthy다. 다른 브랜치 변경과 force push 없음. 운영 롤백은 실행하지 않았다.

---

## 6. 한계 및 후속 과제

- 운영의 질문 해석 지원 범위는 기존과 같다. `청둥오리랑 식성이 비슷한 새 알려줘`로 결과를 확인하며, TEST의 의미 선택·오타 확인 흐름 전체를 배포했다고 안내하지 않는다.
- RG-212 전체 자연어 일반화는 진행 중이다. 이 문서의 운영 UI 완료 여부와 상위 과제 완료를 구분한다.
- 이번 변경은 동일 범주 결과의 표시 개선이며 새 생태 근거를 추가하지 않는다.
- 물리 모바일·Safari·Firefox는 미검증이다. 운영 데이터 전체 체크섬 감사도 수행하지 않았으므로 데이터 전체 불변을 실측한 것으로 표현하지 않는다.
- Writer는 전달받은 실제 증거만 기록했으며 앱·테스트·환경 파일을 수정하지 않았다. 저장소 반영용 scratch와 같은 본문을 Obsidian에 저장하고 재조회로 일치를 확인했다. 2xx 인덱스에는 이 기록 링크만 추가했으며 기존 본문과 전체 백로그의 RG-212 진행 중 상태를 보존했다. 저장소 파일 반영은 Codex가 최종 검토 후 수행한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-생태-관계-답변-레이아웃-정리|선행 TEST 레이아웃 검증]]
