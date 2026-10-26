# [RG-203] 그래프 관계 기반 질의응답 기능 구현 및 TEST 배포 검증 완료 — 2026-10-22

> **문서 상태: TEST 검증 완료 (운영 배포 승인 대기)**
> 사용자 명시 승인(2026-10-22)에 따라 Neo4j 지식 그래프의 분류 계층 및 생태 형질 관계를 활용한 복합 관계 질의응답 기능 구현, 서비스 및 DRF 연동, 스키마 확장, Python 1,056건 자동화 회귀 테스트(1,017통과/39skip/0실패, 22.306초), Node 프런트엔드 319건 자동화 테스트(319통과/0skip/0실패, 251.356ms), TEST 환경(16GB Mac .97) 컨테이너 실제 배포(`robingraph-api:test-graph-qa-c298a12f15ef`), 실제 TEST DB 7개 질문 `live-api.json` 전수 통과, 공개 TEST 서버(`https://robingraph-test.dove-nest.com`) Playwright Chromium 10건 실측 검증(1280px 데스크톱 및 390px 모바일 뷰포트, 페이지 런타임 오류 0건, 가로스크롤 넘침 없음, mock 없음, 물리 모바일 기기 아님), 패키지 부재(FastAPI/Starlette) 및 DB 무변경(관측 범위 한정) 검증을 완료했다. 현재 운영 배포 승인 대기 상태이며, 운영 배포 및 Git commit/push는 수행하지 않는다.

---

## 요약

- **배경 및 목적**: 기존의 조류 검색(단일 종 사실 조회, 이름 해소, 유사종 추천 등)을 확장하여, Neo4j 지식 그래프의 분류학적 계층 구조(`PARENT_OF`)와 AVONET / EltonTraits 생태 형질 데이터를 결합하여 두 종 간 분류 관계, 동일 속 종, 특정 분류군과 식성/서식지 교집합 등 다중 조건을 자연어로 해결하는 질의응답 기능을 구현했다.
- **백엔드 구현 및 서비스 통합**:
  - 신규 모듈: `src/robingraph/retrieval/graph_questions.py` 구현 (관계 질의 해석, Neo4j LCA 경로 탐색, 복합 형질 필터링).
  - 서비스 통합: `src/robingraph/api/services.py`, `src/robingraph/api/schemas.py`, `api/drf/application.py`, `cli.py` 연동.
  - OpenAPI 스키마: `openapi.json` 및 `openapi_ingest.json`에 `graph_query` 분기 additive 추가, 과거 골든 스키마(`migrationgolden`) 대비 `graph_query` 제외 시 canonical JSON sha256 동등성 검증 통과 (byte 동일 검증 아님, `semantic_chat` 분기 수 7개로 갱신).
- **자동화 테스트 (Python / Node)**:
  - Python 회귀 테스트: 총 1,056개 실행, **1,017개 통과 / 39개 skip / 0개 실패** (22.306초, 단위 18건 + API 모의 7건 포함, 39건 skip은 opt-in 통합 테스트 및 외부 번들 재현 파일 `/tmp/rg406-avilist.json` 부재에 따른 제외 포함).
  - Node 프런트엔드 테스트: `node --test tests/frontend/*.test.js` 기준 **총 319건 전수 통과 / 0건 skip / 0건 실패** (251.356ms, Antigravity 작성 `chat.js`와 신규 DOM 단위 테스트 2건 통합, `chat_ui` 단독 315건 + 전체 프런트엔드 319건).
  - 신규 UI 단위 테스트: URL 안전성 검증, 계층 경로/출처 링크/종 버튼 클릭 콜백 동작, 자료 부족 안내 렌더링 검증 (초안 fakeDOM shim의 children/tagName 불일치 2건 수정 후 통과, 앱 실브라우저 버그 아님, 배포본과 바이트 동일 확인으로 추가 앱 배포 불필요).
- **통합 리뷰 및 결함 개선**:
  - Claude 리뷰 반영: 명시적 profile 의도 시 빈 필터로 인해 조회가 막히는 현상 수정(`explicit_profile_empty_filter_fixed: true`), 미등록 종 이름 매칭 실패 시 명확한 clarify 응답으로 분리(`unknown_species_clarification_fixed: true`).
- **TEST 환경 실제 배포 (`test-release.json`)**:
  - 배포 상태: `verified`, 대상 환경: 16GB Mac `.97` 앱 (`robingraph-api-test` OrbStack) / 32GB Mac `.98` Neo4j (`bolt://192.168.219.98:7687`) / NAS `.99` PostgreSQL (`robingraph_test`).
  - 이미지: `robingraph-api:test-graph-qa-c298a12f15ef`, 소스 SHA: `c298a12f15ef7874a01f93dbc15108c2fb4bec95015ce9b1b8cf620ef8602caf`.
  - 배포 경로: `/Users/kimdove/robingraph-test/releases/graph-qa-c298a12f15ef-419c49`.
  - 베이스 리비전: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷 기반 TEST 빌드).
  - 이전 릴리스: `robingraph-api:test-rg701-django-only-0e15293544bb` (`/Users/kimdove/robingraph-test/releases/rg701-django-only-0e15293544bb-3d3455`).
  - 패키지 점검: `image-packages.json` (`fastapi: true, starlette: true` = 부재 확인), `manage.sh verify` 통과, fixture network none smoke 통과.
  - DB 무변경 점검: `db-comparison.json` (ingest 상태 해시, 파일럿 run 상태/카운트, 이름 벡터 카탈로그 855건 불변 확인; 관측 스코프 한정이며 전체 DB 체크섬 아님, DB 쓰기 0건).
- **실제 TEST 실서버 검증 (API 및 브라우저)**:
  - 실제 API 실측 (`live-api.json`): 7대 핵심 질문 전수 기대 상태 부합 (답변 6건, 특정 식물 열매 부족 1건 `insufficient_data`/`abstain`).
  - 실제 브라우저 실측 (`browser.json`, `browser.cjs`): 공개 TEST 서버(`https://robingraph-test.dove-nest.com/chat`) 대상 Playwright Chromium 데스크톱(1280px) 및 모바일(390px) 10건 검사 전수 통과 (응답 모킹 없음, 페이지 런타임 오류 0건, 콘솔 이벤트는 별도 미검증, 가로스크롤 넘침 없음, 종 버튼 클릭 시 profile 패널 열기 확인, 스크린샷 2건 보존).
- **데이터 원칙 및 한계선 명시**:
  - 특정 식물 열매 공유 질의는 원천 데이터 부재에 따라 임의 환각 없이 정직한 자료 부족(`insufficient_data`)으로 안내.
  - 서식지 일치 질의는 시공간적 실제 공존이 아닌 데이터상 서식 환경 범주 일치 한계 안내문 첨부.
  - EltonTraits `diet_distribution`의 열매 섭식 비율(`fruit > 0`)과 AVONET `trophic_niche`의 열매 섭식 범주(`Frugivore`)를 엄격히 분리 정의.
  - 진화적 계통 거리 추정이 아닌 분류학적 계층 경로(`PARENT_OF`)로 기술.
  - 관계 질의 오타 벡터 후보 연계는 미구현 (단일 종 질의에만 동작 유지).
  - 조건 이어가기(대화 상태 기억 및 문맥 유지)는 이번 구현 범위에서 제외하고 향후 후속 과제로 분리.

---

## 작업 및 검증 결과 요약

| 구분 | 계획 및 설계 사항 | 최종 TEST 검증 결과 (2026-10-22) |
| --- | --- | --- |
| **신규 모듈 구현** | `graph_questions.py` 관계 질의 해석 및 그래프 쿼리 | 구현 완료 (`test_graph_questions.py` 18건 통과) |
| **서비스 및 API 통합** | `src/robingraph/api/services.py`, `src/robingraph/api/schemas.py`, DRF, CLI 연동 | 연동 완료 (`test_graph_questions_api.py` 7건 통과) |
| **OpenAPI 스키마** | additive `graph_query` 분기 추가 및 과거 호환성 검증 | `test_drf_parity` 통과, canonical JSON sha256 동등성 확인 (`semantic_chat` 7개 분기) |
| **Python 자동화 테스트** | 전체 회귀 테스트 통과 | **1,056개 실행: 1,017 통과 / 39 skip / 0 실패** (22.306초, opt-in 및 `/tmp/rg406-avilist.json` 부재 제외 포함) |
| **Node UI 자동화 테스트** | 프런트엔드 회귀 테스트 | **319건 실행: 319건 전수 통과 / 0 skip / 0 fail** (251.356ms, 신규 DOM 단위 테스트 2건 포함) |
| **TEST 환경 배포** | 16GB Mac .97 앱 컨테이너 실제 배포 | `robingraph-api:test-graph-qa-c298a12f15ef`, 상태: `verified` |
| **패키지 및 DB 무결성** | FastAPI/Starlette 부재 및 DB 무변경 확인 | 패키지 부재 확인(`image-packages.json`), 관측 DB 스코프 불변(`db-comparison.json`), DB 쓰기 0건 |
| **실제 API 7대 질문 실측** | 7대 핵심 자연어 질문 실서버 질의 | 7건 전수 기대 상태 부합 (6건 answer, 1건 abstain/자료부족, limit=20 적용) |
| **실제 브라우저 실측** | Playwright Chromium 데스크톱(1280) 및 모바일(390) | **10건 검사 전수 통과 (2개 뷰포트)** (mock 없음, 페이지 런타임 오류 0건, 콘솔 별도 미검증, 가로넘침 없음, 종버튼 profile 열기 성공) |
| **데이터 무결성 원칙** | 특정 열매 공유 자료부족 안내, 서식지 범주 한계 명시 | 원천 근거 없는 임의 환각 차단 및 정직한 안내 확인 |
| **운영 배포 및 형상 관리** | 운영 배포 배제 및 Git 커밋/푸시 배제 | 운영 변경 없음(`production_changed: false`), Git 커밋/푸시 없음(`git_commit_push: false`) |

---

## 1. 주요 구현 및 리뷰 개선 내용

### 1) 신규 모듈: `src/robingraph/retrieval/graph_questions.py`
- **질의 파서 (`parse_graph_question`)**:
  - 자연어 질의 유형 식별: 공통 분류(LCA), 동일 속, 국내 출현+동일 속, 분류군+식성, 서식지+먹이공유, 서식지일치+먹이상이, 특정 열매.
  - 초기 테스트 실패 이력: 최초 실행 시 파서 정규식 3건 실패 발생 -> 패턴 매칭 경계 및 토큰 처리 보완 후 정상 통과.
- **그래프 쿼리 및 오케스트레이션 (`graph_question_answer`)**:
  - Neo4j `PARENT_OF` 계층 관계를 추적하여 두 종의 공통 상위 분류군(LCA) 및 상위 분류 경로 구성 (진화적 계통 거리가 아닌 분류학적 계층 경로로 기술).
  - 식성 및 생태 범주: AVONET `trophic_niche`의 열매 섭식 범주(`Frugivore`)와 EltonTraits `diet_distribution`의 열매 섭식 비율(`fruit > 0`)을 분리하여 조회.
  - EltonTraits 데이터 품질 가드: 확실성 등급 A, B, C 자료만 포함하고, 근연 분류군에서 보간한 D1, D2 추정치는 제외.
  - 특정 식물 종 열매 공유 질의: 그래프에 개별 식물-조류 상호작용 데이터가 없으므로 `insufficient_data` 상태와 안내 문구 반환.
  - 서식지 범주 일치 질의: 서식 환경 범주 일치 종 목록과 함께 "실제 시공간 공존이 아닌 데이터상 범주 일치 한계" 안내문 첨부.
  - 결과 제한: API 및 뷰어 과부하 방지를 위해 최대 표시 수를 20개(`limit=20`)로 설정하고 초과 시 `has_more: true` 반환.

### 2) 서비스 계층 및 스키마 통합
- **`src/robingraph/api/services.py`**: 그래프 질문 처리 파이프라인 연계.
- **`src/robingraph/api/schemas.py`**: `ChatGraphResult` 등 응답 스키마 정의.
- **`src/robingraph/api/drf/application.py`**: DRF API 엔드포인트 연동.
- **`src/robingraph/cli.py`**: CLI 인터페이스 지원.
- **OpenAPI 스키마**:
  - `openapi.json` 및 `openapi_ingest.json`에 `graph_query` 분기 additive 확장.
  - `test_drf_parity`에서 신규 `graph_query` 분기 제외 시 과거 `migrationgolden` 스키마와 canonical JSON sha256 동등성을 입증 (바이트 동일 검증 아님).
  - `semantic_chat` 스키마 분기 기대 수를 기존 6개에서 7개로 갱신 (초기 테스트 1건 실패 후 수정 통과).

### 3) Claude 통합 리뷰 및 결함 개선 사항
- **빈 profile 필터 막힘 수정 (`explicit_profile_empty_filter_fixed: true`)**:
  - 사용자가 고급 설정 등에서 의도를 `profile`로 명시했을 때 빈 필터 조건이 주어지면 조회가 차단되던 결함을 수정하여, 질의 텍스트로부터 그래프 질의 파이프라인이 정상 동작하도록 보완.
- **미등록 종 이름 실패 안내 분리 (`unknown_species_clarification_fixed: true`)**:
  - 수정 전에는 미등록 종 이름 입력 시 200 abstain/조회불가로 응답했으나, 이를 사용자가 종 이름을 다시 확인할 수 있는 이름 미확인 clarify 안내로 개선하고 실제 조회 장애 시의 abstain 안내와 명확히 분리 서술.
- **미구현 및 범위 한계선 확인**:
  - 관계 질의 오타 벡터 후보 연계는 이번 범위에 연결되지 않음 (`vector_fallback_for_graph_questions: false`, 기존 단일 종 질의에만 동작 유지).
  - 조건 이어가기(대화 상태 기억 및 문맥 유지)는 이번 단일 턴 구현 범위에서 제외되고 향후 후속 과제로 분리.

---

## 2. 검증 및 테스트 결과

### 1) 단위 및 회귀 자동화 테스트
- **Python 자동화 테스트 (`automated-tests.json`)**:
  - 총 테스트 수: **1,056개**
  - **통과: 1,017개** / **건너뜀(skip): 39개** / **실패: 0개**
  - 실행 시간: **22.306초**
  - 검사 성격: 오프라인/모의/픽스처 기반
  - skip 사유: opt-in 통합 테스트 및 외부 번들 재현 파일(`/tmp/rg406-avilist.json`) 부재에 따른 제외 포함
  - 신규 단위 테스트: `test_graph_questions.py` 18건 전수 통과 (Claude 작성)
  - 신규 API 테스트: `test_graph_questions_api.py` 7건 전수 통과 (Codex 작성, 리뷰 후 2건 추가)
  - 스키마 parity 테스트: `test_drf_parity.py` canonical JSON sha256 동등성 통과
- **Node UI 자동화 테스트**:
  - 실행 명령어: `node --test tests/frontend/*.test.js`
  - 결과: **총 319건 실행: 319건 전수 통과 / 0건 skip / 0건 fail (251.356ms)**
  - 내역: `chat_ui` 단독 315건 + 전체 프런트엔드 319건 기준 충족
  - 신규 DOM 단위 테스트 2건: URL 안전성 검증, 계층 경로/출처 링크/종 버튼 클릭 콜백 연동, 자료 부족 안내 표출 검증
  - 초안 fakeDOM 실패(2건)는 shim `children`과 `tagName`을 맞춰 수정 후 정상 통과 (앱 실브라우저 버그 아님)
  - 배포된 `chat.js`와 통합본 바이트 동일 확인 완료 (추가 앱 배포 불필요)

### 2) TEST 환경 컨테이너 배포 영수증 (`test-release.json`)
- **대상 환경**: 16GB Mac `.97` (`robingraph-api-test`, OrbStack 컨테이너)
- **배포 상태 (`state`)**: `verified`
- **배포 이미지 (`image`)**: `robingraph-api:test-graph-qa-c298a12f15ef`
- **소스 SHA256 (`source_sha256`)**: `c298a12f15ef7874a01f93dbc15108c2fb4bec95015ce9b1b8cf620ef8602caf`
- **베이스 리비전 (`base_revision`)**: `834c5353ca45f0640152ca4849548cd48818b266` (미커밋 작업트리 스냅샷, `uncommitted_source_snapshot: true`)
- **릴리스 디렉터리 (`release`)**: `/Users/kimdove/robingraph-test/releases/graph-qa-c298a12f15ef-419c49`
- **이전 이미지 및 릴리스**:
  - `previous_image`: `robingraph-api:test-rg701-django-only-0e15293544bb`
  - `previous_release`: `/Users/kimdove/robingraph-test/releases/rg701-django-only-0e15293544bb-3d3455`
- **보조 검증**:
  - `fixture_network_none_smoke`: `true` (네트워크 단절 픽스처 스모크 통과)
  - `physical_reboot_tested`: `false` (물리 장비 재부팅은 미실시)
  - `production_changed`: `false` (운영 환경 무변경)

### 3) 새 TEST 이미지 패키지 검사 (`image-packages.json`)
- **검사 내용**: `FastAPI` 및 `Starlette` 부재 확인
- **결과**: `{"fastapi": true, "starlette": true}`
  - *주*: 값 `true`는 `importlib.util.find_spec(...) is None`이 성립하여 레거시 패키지가 완전히 제거되었음을 의미함.
- `manage.sh verify` 검증 통과.

### 4) TEST DB 변경 여부 검사 (`db-comparison.json`)
- **대상**: TEST DB (`db-before.json` vs `db-after.json`)
- **관측 스코프**:
  1. `non-pilot ingest pipeline states hash`
  2. `pilot run status/counts`
  3. `name vector catalog fingerprints/count` (855건 유지)
- **결과**: `unchanged_in_observed_scope: true`
- **주의**: 전체 데이터베이스 체크섬이 아니며(`whole_database_checksum: false`), 배포 및 검증 과정에서 쓰기 요청은 전혀 없었음 (`writes_requested: false`, DB 쓰기 0건).

### 5) 실제 TEST API 실서버 읽기 검증 (`live-api.json`)
- **호출 대상**: `https://robingraph-test.dove-nest.com` (읽기 전용 질의)
- **7대 질문 실측 결과 전수 대조 표**:

| 번호 | 질문 내용 | 응답 상태 (`disposition`) | 응답 종류 (`kind`) | 반환 수 (`items`) | `has_more` | 출처 수 (`sources`) | 주요 응답 및 검증 포인트 |
|---|---|---|---|---|---|---|---|
| 1 | 청둥오리와 흰뺨검둥오리는 어떤 관계야? | `answer` | `graph_query` | 2 | `false` | 1 | 같은 속(`Anas` 오리속) 공통 분류학적 계층 경로 출력 |
| 2 | 청둥오리와 같은 속에 속하는 새를 보여줘 | `answer` | `graph_query` | 20 | `true` | 1 | 동일 속 종 목록 반환 (최대 표시 한도 `limit=20` 도달) |
| 3 | 한국에 기록된 오리 중 청둥오리와 같은 속인 종은? | `answer` | `graph_query` | 4 | `false` | 3 | 고방오리, 미국오리, 쇠오리, 흰뺨검둥오리 (국내 야생 기록 종 한정) |
| 4 | 참새목 중 열매를 먹고 사는 새는? | `answer` | `graph_query` | 20 | `true` | 21 | `Passeriformes` + EltonTraits `Fruit > 0` (확실성 A·B·C만 포함, D1·D2 제외) |
| 5 | 숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는? | `abstain` | `graph_query` | 0 | `false` | 0 | **`status: insufficient_data`, "특정 식물 열매를 함께 먹는다는 근거 자료가 없어 답할 수 없습니다" 정직한 자료 부족 안내** |
| 6 | 청둥오리와 서식지가 겹치면서 먹이가 다른 새는? | `answer` | `graph_query` | 20 | `true` | 42 | 서식지 범주(습지) 일치 + 먹이 범주 상이 ("실제 공존이 아닌 데이터상 서식 범주 일치 한계" 안내 포함) |
| 7 | 숲에 사는 새중 직박구리랑 같은 먹이 범주를 공유하는 새는? | `answer` | `graph_query` | 20 | `true` | 42 | 숲 서식지 + 열매 섭식(`Frugivore`) 생태 범주 공유 종 목록 반환 |

*주의*: 위 20종은 UI/API 최대 표시 수(`limit=20`)이며 전체 데이터베이스의 종 수가 아님 (`has_more: true`).

### 6) 실제 공개 TEST 브라우저 검증 (`browser.json`, `browser.cjs`)
- **실행 환경**: Playwright Headless Chromium (`reducedMotion: 'reduce'`)
- **기본 URL**: `https://robingraph-test.dove-nest.com/chat`
- **응답 모킹**: 없음 (`response_mocking: false`, 실제 배포된 TEST 컨테이너 호출)
- **물리 기기 여부**: `physical_mobile: false` (Chromium 뷰포트 에뮬레이션)
- **10건 브라우저 검사 결과 (2개 뷰포트)**:

| 뷰포트 너비 | 질문 / 동작 | 응답 상태 (`disposition`) | 렌더링 확인 | 출처 링크 수 | 페이지 런타임 오류 | 가로스크롤 넘침 | 검사 결과 |
|---|---|---|---|---|---|---|---|
| **1280px** (Desktop) | 청둥오리와 흰뺨검둥오리는 어떤 관계야? | `answer` | 정상 | 6 | 0건 | 없음 | **통과** |
| 1280px | 참새목 중 열매를 먹고 사는 새는? | `answer` | 정상 | 61 | 0건 | 없음 | **통과** (스크린샷 `graph-query-1280.png`) |
| 1280px | 숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는? | `abstain` | 정상 | 0 | 0건 | 없음 | **통과** (자료 부족 문구 렌더링) |
| 1280px | 한국에 기록된 오리 중 청둥오리와 같은 속인 종은? (profile 의도 명시) | `answer` | 정상 | 16 | 0건 | 없음 | **통과** (국내 기록 문구 렌더링) |
| 1280px | 종 버튼 클릭 동작 (`profile` 패널 전환) | `answer` | 정상 (`kind: profile`) | - | 0건 | 없음 | **통과** |
| **390px** (Mobile) | 청둥오리와 흰뺨검둥오리는 어떤 관계야? | `answer` | 정상 | 6 | 0건 | 없음 | **통과** |
| 390px | 참새목 중 열매를 먹고 사는 새는? | `answer` | 정상 | 61 | 0건 | 없음 | **통과** (스크린샷 `graph-query-390.png`) |
| 390px | 숲에 사는 새중에 직박구리랑 같은 열매를 먹는 새는? | `abstain` | 정상 | 0 | 0건 | 없음 | **통과** (자료 부족 문구 렌더링) |
| 390px | 한국에 기록된 오리 중 청둥오리와 같은 속인 종은? (profile 의도 명시) | `answer` | 정상 | 16 | 0건 | 없음 | **통과** (국내 기록 문구 렌더링) |
| 390px | 종 버튼 클릭 동작 (`profile` 패널 전환) | `answer` | 정상 (`kind: profile`) | - | 0건 | 없음 | **통과** |

- **가로 넘침 검증**: `document.documentElement.scrollWidth > innerWidth === false` (두 해상도 모두 가로 스크롤 넘침 없음).
- **페이지 오류**: 페이지 런타임 오류 0건 (`page_errors: 0`), 콘솔 이벤트는 별도 미검증 (`browser.cjs`에서 pageerror 이벤트만 수집).

---

## 3. 한계 및 향후 확인 과제

1. **원천 데이터 매핑 한계**:
   - 그래프에 종 노드와 **직접 연결된 형질 주장만 검색**하며, 프로필이나 외부 보충 자료(BirdBase 등)에서 분류 대응으로 복원되는 형질은 제외됨.
   - 직박구리의 경우 EltonTraits 데이터가 복원형이어서 fruit 직접 연결 목록에서 제외될 수 있음.
2. **특정 식물 열매 공유 데이터 부재**:
   - 조류-특정 식물 종 간의 상호작용 데이터는 현재 원천 그래프에 없으므로, 향후 관련 생태 데이터셋이 확보되기 전까지는 `insufficient_data` 안내를 유지함.
3. **관계 질의 오타 벡터 후보 연계 미구현**:
   - 이번 RG-203에서는 관계 질의 입력에 대한 오타 벡터 후보 자동 연계를 적용하지 않았으며(`vector_fallback_for_graph_questions: false`), 단일 종 질의에만 기존 방식대로 동작함. 향후 필요 시 관계 질의 파서에도 오타 벡터 보정을 확장할 수 있음.
4. **대화 상태 기억(조건 이어가기) 후속 과제**:
   - 현재 구현은 각 질문을 독립적으로 해석하는 **단일 턴 처리**이며, "그 중에서 국내에 사는 새는?"과 같은 대화 상태 기억 및 문맥 조건 이어가기는 이번 완료 범위에서 제외되고 향후 후속 과제로 분리됨.
5. **물리 모바일 기기 검증 미실시**:
   - Playwright Chromium 390px 모바일 뷰포트 에뮬레이션 검증은 통과했으나, 실제 물리 스마트폰 기기에서의 터치 및 스크롤 감각 검증은 후속 과제로 남음.
6. **운영 배포 승인 대기**:
   - TEST 검증은 전수 완료되었으며, 사용자 명시 승인 전까지 운영 환경 배포 및 Git commit/push는 일체 수행하지 않음.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-203|RG-203 — 그래프 관계 기반 질의응답 (상세 백로그)]]
- 배포 영수증: [test-release.json](../verification/assets/2026-10-22-graph-relationship-qa/test-release.json)
- 실서버 API 검증: [live-api.json](../verification/assets/2026-10-22-graph-relationship-qa/live-api.json)
- 브라우저 실측 결과: [browser.json](../verification/assets/2026-10-22-graph-relationship-qa/browser.json)
- 브라우저 검증 스크립트: [browser.cjs](../verification/assets/2026-10-22-graph-relationship-qa/browser.cjs)
- 데스크톱 스크린샷: [graph-query-1280.png](../verification/assets/2026-10-22-graph-relationship-qa/graph-query-1280.png)
- 모바일 스크린샷: [graph-query-390.png](../verification/assets/2026-10-22-graph-relationship-qa/graph-query-390.png)
- 패키지 부재 점검: [image-packages.json](../verification/assets/2026-10-22-graph-relationship-qa/image-packages.json)
- DB 비교 점검: [db-comparison.json](../verification/assets/2026-10-22-graph-relationship-qa/db-comparison.json)
- 자동화 테스트 요약: [automated-tests.json](../verification/assets/2026-10-22-graph-relationship-qa/automated-tests.json)
- 사전 검증 증거 자산: [predeploy-retrieval.json](../verification/assets/2026-10-22-graph-relationship-qa/predeploy-retrieval.json)
