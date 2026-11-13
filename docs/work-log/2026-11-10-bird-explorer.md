---
created: 2026-11-10
date: 2026-11-10
project: RobinGraph
type: worklog
status: completed
task_id: RG-215
tags:
  - worklog
  - robingraph
  - bird-explorer
  - graph-query
---

# [RG-215 / 검색·그래프 질의] 조건으로 새 찾기(새 탐색기): 다중 조건 구조화 그래프 검색 및 탐색 인터페이스 (TEST 배포 및 실사 검증 완료 · 운영 미반영) — 2026-11-10

> **문서 상태: 완료 (TEST 배포 및 실사 검증 완료 · 운영 배포 미반영 / 사용자 명시 승인 대기)**  
> 자연어 입력 없이도 필터 선택(분포, 목·과·속 분류군, 서식지, 복수 먹이)을 통해 일치하는 조류를 탐색하고, 각 결과의 생태적 근거, 출처, 데이터 커버리지, 도감 링크를 투명하게 제공하는 ‘조건으로 새 찾기(새 탐색기 / Bird Explorer)’ 기능의 구현, TEST 배포 및 실사 검증 완료 문서이다.  
> 본 작업은 자연어 파서(LLM, Jev 의도 분석, 벡터 후보 검색)를 경유하지 않고 기존 고정 Cypher 구조화 그래프 검색 엔진(`graph_question_handler` → `_taxon_traits`)을 직접 재사용하여 다중 조건 AND 검색 및 선택 먹이 비율 합산 내림차순(DESC) 정렬을 결정론적으로 수행하도록 구현했다.  
> **검증 및 배포 이력 요약**:
> 1. 백엔드 API(`GET /v1/taxa/explore`) 및 프런트엔드 탐색 화면(`api/static/explore.*`)을 구현하고, root 통합 백엔드(167개) / 프런트엔드(361개) 테스트 및 실제 TEST DB 대상 in-process ASGI 실사(4질의), 로컬 실제 TEST HTTP API 23개 매트릭스(12개 정상 질의 + 11개 422 오류 처리) 검증을 전수 통과했다.
> 2. **1차 TEST 배포 (`74c37b75336f`)**: public 브라우저 실사 검증을 통과하였으며 이를 [`first-browser-public.json`](../verification/assets/2026-11-10-bird-explorer/first-browser-public.json)으로 별도 안전 보존했다. (이전 임시 초안에서 이 1차 통과본을 최종 배포본의 결과로 혼동 표기했던 부분을 명확히 분리 정정함).
> 3. **모바일 2열 CSS 1줄 보완 및 최종 TEST 배포 (`cdfed28ae4e3`)**:
>    - 최종 이미지(`robingraph-api:test-bird-explorer-cdfed28ae4e3`, release `bird-explorer-cdfed28ae4e3-b705a1`, verified) 배포 후, 컨테이너 내부/로컬 loopback(127.0.0.1:8000)은 200 정상이었으나 LAN .97 타임아웃 및 public 502 현상([`browser-failure.json`](../verification/assets/2026-11-10-bird-explorer/browser-failure.json))이 발생했다.
>    - 포트 연결 영역으로 추정되나 원인은 미확정이며, 코드 원인으로 단정하지 않았다.
>    - TEST 컨테이너 수동 1회 재시작([`test-port-recovery.json`](../verification/assets/2026-11-10-bird-explorer/test-port-recovery.json), `manual_test_restart_operations = 1`)을 통해 LAN/public 200이 완벽히 복구되었다. (Docker `RestartCount: 0`은 자동 재시작 카운트이며, 수동 1회는 `StartedAt` 로그로 명확히 구분; 운영 NAS 재시작 없음).
> 4. **복구 후 최종 브라우저 실사 전수 통과**:
>    - 공개 HTTPS origin 기준 [`actual-browser.json`](../verification/assets/2026-11-10-bird-explorer/actual-browser.json) 및 LAN HTTP origin 기준 [`final-lan-browser.json`](../verification/assets/2026-11-10-bird-explorer/final-lan-browser.json) 모두 최종 `source_sha256 = "cdfed28ae4e30c0c3e95164ead69b7e41ddc2535ddbfa0d9654f314f39b980a9"`로 전수 통과했다.
>    - 너비 1280px(4열), 390px(2열), 320px(2열) 전 뷰포트(각각 height 1100; CDP 검증)에서 가로 넘침 0건, 모바일 먹이 2열 배치, 공유 URL 재로드 복원, Enter 키보드 제출, 다중 먹이 비율 합산 정렬, 분류군 오류 안내, 도감 연결 시 선택 scope 유지를 확인했다.
> 5. **전체 필터 값 실API 추가 전수 검증 ([`filter-values-api.json`](../verification/assets/2026-11-10-bird-explorer/filter-values-api.json))**:
>    - 최종 배포본(`cdfed28ae4e3`)에서 먹이 10종류 전부, 서식환경 11종류 전부, 2개 분류군(`직박구리과`, `Turdus`) 총 23개 추가 질의를 전수 실행하여 23건 모두 200 OK, 종 rank, 형질 일치, 먹이 양수 비율, EltonTraits 확실성 A·B·C 경로를 확인했다.
>    - 초기 23건(12 정상 + 11 422)과 별개의 23건으로, 실제 TEST HTTP 질의는 총 46건 전수 통과했다 (중복 합산 주의).
> 6. **검증 한계선**: Headless Chromium CDP로 검증 완료하였으나, 실제 Safari, Firefox 브라우저 및 물리 스마트폰 모바일 기기 검사는 미실시(`physical_mobile_tested: false`) 상태이다.
> 7. **안전성 지표**: 운영 NAS 배포 없음 (`production_changed: false`), Git 커밋/푸시 미수행 (`git_commit_push: false`), 조류 DB 쓰기 0건 (`bird_db_writes: 0`), 외부 프로바이더 요청 0건 (`provider_requests_initiated_by_verifier: 0`). 모든 검증 아티팩트는 `docs/verification/assets/2026-11-10-bird-explorer/`에 영구 보존했다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **원인 규명 / 요구사항** | 자연어 파싱 없는 정밀 조건 기반 조류 탐색 요구 | 자연어 질의의 모호성이나 어휘 누락 없이 사용자가 분포, 분류군, 서식지, 먹이 복수 조건을 직접 조합하여 조건에 맞는 새를 탐색하고 출처/근거/도감을 확인하려는 기능 요구 대응 |
| **설계 및 해결 방안** | 구조화 그래프 검색 직접 재사용 및 다중 정렬 인터페이스 | 자연어 파서(LLM/Jev/벡터)를 배제하고 기존 Cypher 쿼리 엔진(`graph_question_handler`) 직접 재사용, 4대 스코프 지원, 목·과·속 분류군 한정 지원(결과 종 단위, 종·아종 입력 422 거부), 서식지 단일 선택, 다중 먹이 AND + 선택 먹이 비율 합산 DESC 정렬, 자료 부재와 빈 결과 구분 |
| **코드 / 설정 수정** | 백엔드 API 및 프런트엔드 UI 전체 구현 완료 (15개 파일 통합) | - 백엔드(dev-claude): `backend.patch` 9개 파일(+477 / −15), `graph_questions.py`(조건 0~11개 허용, 종/아종 rank_unsupported 차단), `services.py`(`explore_taxa`), `serializers.py`(`TaxonExploreRequestSerializer`), `views.py`/`urls.py`(`GET /v1/taxa/explore`), `openapi*.json`<br>- 프런트엔드(dev-agy + root 리뷰): `explore.html`, `explore.css`, `explore.js`, `index.html`(진입 링크), `styles.css`, `tests/frontend/explore_ui.test.js`. 기존 도감 곤충/고기 분류 일치, 영문 키 부제 제거, coverage 내부 키 제거, 접힌 먹이 분류 안내, 390/320 모바일 먹이 2열 배치<br>- 전체 통합: root 최종 15개 파일 통합 패치 (`integrated-code.patch`) |
| **실서비스 배포** | TEST 배포 완료 (운영 배포 없음) | - 1차 TEST 배포: `robingraph-api:test-bird-explorer-74c37b75336f` (public 브라우저 통과, `first-browser-public.json`)<br>- 최종 TEST 배포: `robingraph-api:test-bird-explorer-cdfed28ae4e3` (snapshot-cdfed28ae4e3, source sha256 `cdfed28ae4e30c0c3e95164ead69b7e41ddc2535ddbfa0d9654f314f39b980a9`, image id `sha256:fc5e015f7aa2c3b54614f837901d2971a152cfa13c00e96cad7282eb5ca876ad`, release `bird-explorer-cdfed28ae4e3-b705a1`, state `verified`, arm64)<br>- 수동 1회 재시작 복구: LAN timeout/public 502 발생 후 수동 1회 재시작으로 복구 완료 (`test-port-recovery.json`)<br>- NAS Production 배포 없음 (`production_changed: false`) |
| **검증 및 테스트** | **단위/통합, 실제 DB 실사, 실API(총 46건), 브라우저 E2E 전수 통과** | - **root 통합 백엔드 테스트**: 167/167 통과 (2.187s, failure=0, skip=0, `test_bird_explorer.py` 17건 포함)<br>- **root 통합 프런트엔드 테스트**: 361/361 통과 (337.37ms, failure=0, skip=0, `explore_ui.test.js` 포함)<br>- **실제 TEST DB ASGI 실사**: `real-asgi.json` 4질의 통과 (Neo4j .98:7687, PG .99:5433, db_writes=0, 단일 실행 0.226~0.551s 참고)<br>- **로컬 실제 TEST HTTP API 검증**: `actual-api.json` 23항목(12개 정상 200 + 11개 422 거부) 통과<br>- **전체 필터 값 실API 추가 전수 검증**: `filter-values-api.json` 23개 추가 질의(10개 먹이 전부 + 11개 서식지 전부 + 2개 분류군) 전수 200 OK 통과 (종 rank, EltonTraits A/B/C 경로, 양수 먹이 비율, 서식지 텍스트 일치 확인; 기존 23건과 별개 총 46건 실API 검증)<br>- **공개 URL 프로브 구분**: 초기 public urllib 프로브는 403(원인 미확정)이었으나, 동일 공개 URL 대상 curl 200 정상 및 실제 Chromium public UI 검증 정상 통과 확인<br>- **최종 cdfed 실브라우저 E2E 실사**: `actual-browser.json` (공개 HTTPS) 및 `final-lan-browser.json` (LAN HTTP) 전수 통과 (너비 1280/390/320px, 각각 height 1100 전 뷰포트 가로 넘침 0건, 모바일 먹이 2열, cards 20, 도감 scope 유지, keyboard_submit 통과, JS 예외 0건, 외부 프로바이더 요청 0건)<br>- **미검증 한계**: 실제 Safari, Firefox 브라우저 및 물리 모바일 기기 검사는 미실시 |
| **형상 관리** | 커밋·푸시 미수행 (워킹 트리 유지) | 운영 NAS 미배포 (`production_changed: false`), Git `commit`/`push` 미수행 (`git_commit_push: false`), DB 쓰기 0건 (`bird_db_writes: 0`), 외부 사진/음원 요청 0건 (`provider_requests_initiated_by_verifier: 0`), 검증 아티팩트 영구 보존 (`docs/verification/assets/2026-11-10-bird-explorer/`) |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항
* RobinGraph 사용자가 원하는 조류를 찾고자 할 때, 자연어 대화 방식(예: `"숲에 사는 열매 먹는 새"`)은 대화형 편의성을 제공하지만 다음과 같은 한계가 존재함:
  1. 복잡한 다중 조건(예: 참새목 중 숲에 살고 열매와 곤충을 모두 먹는 한국 서식 조류)을 질의할 때 자연어 어휘 해석이나 마커 감지에서 모호성이 발생할 수 있음.
  2. 전체 조건과 각 조건별 데이터 커버리지(자료 유무), 구체적인 출처와 근거를 한눈에 대조하고 탐색하기 어려움.
* 이에 따라 직관적인 필터 컨트롤(라디오, 자동완성, 체크박스)을 통해 조건을 조합하고, 구조화된 그래프 쿼리로 정밀 탐색할 수 있는 **'조건으로 새 찾기(새 탐색기 / Bird Explorer)'** 기능이 요구됨.

### 설계 원칙 및 경계 검토
* **자연어 파서 우회**: 본 탐색기는 자연어 파서(LLM 프롬프트, Jev 의도 라우터, 임베딩 기반 유형 분류)를 경유하지 않음. 사용자가 UI에서 선택한 조건 객체를 직접 구조화된 질의 계약으로 변환하여 안전하고 빠른 응답을 보장함.
* **기존 구조화 그래프 검색 재사용**: 새로운 비표준 Cypher를 임의 생성하지 않고, 기존에 검증된 `graph_question_handler` 및 Cypher 쿼리 패턴을 재사용함.
* **분류군 필터 한정 (v1 계약)**: v1 계약에 따라 분류군은 목(order)·과(family)·속(genus)만 지원하며, 결과는 항상 **종(species) 단위**로 반환함. 종(species)이나 아종(subspecies) 학명/국명 입력 시 부모 범위로 넓히지 않고 HTTP 422(`taxon_rank_unsupported`)로 엄격히 거부함. UI는 입력 안내로 `"목·과·속 학명 한 단어 또는 검토된 한국어 목·과·속 이름"`을 명시함.
* **서식지 및 다중 먹이 AND 조건 및 비율 합산 정렬 (RG-214 연계)**: 서식지는 종별 대표값 특성상 AVONET 11개 값 중 1개만 허용함(복수 전송 시 422). 먹이 복수 선택 시 모든 먹이를 먹는 종만 필터링(AND, >0%)하며, 선택된 먹이 성분들의 비율을 합산한 값의 내림차순(DESC)으로 정렬함 (동점 시 한국어 이름순).
* **분포 스코프 4종 완전 지원 (RG-406 연계)**: `all`(전체), `korea`(국내 기록종), `outside`(국외 분포종), `unknown`(미판정) 스코프를 정확히 반영함.
* **자료 부재와 불일치 구분**: 조건에 맞는 데이터가 없는 빈 결과(`empty`)와 그래프 내 형질 자료 자체가 부족한 상태(`insufficient_data`)를 명확히 구분하여 사용자에게 투명하게 고지함.

---

## 2. 해결 방안 및 수용 기준 달성 결과

### 수용 기준 매트릭스 (Acceptance Criteria) 검증 결과

| 번호 | 수용 기준 항목 | 상태 | 검증 근거 및 실제 결과 |
|---|---|---|---|
| 1 | **구조화 API 의도 보존**: 자연어 의도/LLM/벡터 검색 미호출 및 클라이언트 조건 보존 | 통과 (`[x]`) | `test_bird_explorer.py` 및 ASGI/HTTP 실사 확인: `graph_question_handler` 직접 실행, SemanticRouter/Jev 미호출 확인 |
| 2 | **분포 스코프 및 빈 조건**: 4개 스코프(`all`, `korea`, `outside`, `unknown`) 및 빈 조건 도감 반환 | 통과 (`[x]`) | `actual-api.json` 케이스 1, 2, 10, 11: `{}`(11,131건), `korea`(592건), `outside`(6건 중 0건 일치), `unknown`(10,533건) 정상 평가 |
| 3 | **분류군 목·과·속 한정 및 종 결과**: 목·과·속 학명/국명 허용, 종/아종 입력 시 422 거부 | 통과 (`[x]`) | 참새목/Anatidae/Anas 200 통과; `taxon=Anas+platyrhynchos`(종 학명), 직박구리(종 국명), `Corvus corone cornix`(아종) 즉시 422 반환 |
| 4 | **복합 조건 질의**: 숲+열매+Korea+참새목 AND 충족, 출처 URL, 대표 서식지 일치, 합산 정렬 | 통과 (`[x]`) | `actual-api.json` 케이스 9: 참새목 256종 중 평가 가능 164종, 조건 일치 41종 도출, 20종 표시, EltonTraits fruit >0% 합산 내림차순 정렬 확인 |
| 5 | **다중 먹이 정렬**: 열매+씨앗 동시 선택 시 모두 >0, 합산 비율 DESC 정렬 | 통과 (`[x]`) | `actual-api.json` 케이스 8: 11,131종 중 7,067종 평가, 924종 일치, 선택 먹이 합산 내림차순 정렬 검증 통과 |
| 6 | **독립 조건 검증**: 서식지 단독, 먹이 단독, 분류군 단독, 분포 단독 조회가 각각 독립적으로 정상 동작 | 통과 (`[x]`) | `actual-api.json` 케이스 2(`korea`), 3(`Passeriformes`), 6(`Forest`), 7(`fruit`) 각각 단독 질의 200 OK 확인 |
| 7 | **유효성 검증 및 422 에러**: 잘못된 스코프/서식지/먹이, 중복 파라미터, 빈 파라미터 422 거부 | 통과 (`[x]`) | `actual-api.json` 케이스 13~23: `diet=invalid`, `diet=fruit,fruit`, `limit=30`, `taxon=`, `diet=` 등 11건 422 리스트 에러 전수 확인 |
| 8 | **자료 커버리지 및 페이징**: 자료 부재(`insufficient_data`)와 비일치(`empty`) 구분, 20건 제한 및 `has_more` | 통과 (`[x]`) | `actual-api.json`: 케이스 10, 12에서 `empty` 정상 구분, 20건 상한 시 `has_more: true` 정확 노출 |
| 9 | **상태 공유 URL**: 공유 가능한 URL(Query string)을 통해 선택 필터 조합 완벽 복원 | 통과 (`[x]`) | `actual-browser.json` (source_sha `cdfed28a`): URL 리로드 시 필터 선택 상태 복원 검증 통과 (`url_reload_filter_restore: true`) |
| 10 | **반응형 및 접근성**: 데스크톱(1280px) 및 모바일(390px/320px) 가로 넘침 0건, 모바일 2열, 키보드 인터랙션 지원 | 통과 (`[x]`) | `actual-browser.json` & `final-lan-browser.json`: 1280px(4열), 390px(2열), 320px(2열) 전 뷰포트 가로 넘침 0건, Enter 키보드 제출 통과 (`keyboard_submit: true`) |
| 11 | **도감 연계**: 결과 카드 클릭 시 정규 학명 및 현재 선택 스코프 유지 팝업 연결 | 통과 (`[x]`) | `actual-browser.json`: `/birds?name=Oriolus+chinensis&species_scope=korea` 정상 연결 확인 (`profile_scope: "korea"`, `profile_scientific: "Oriolus chinensis"`) |
| 12 | **기존 기능 무회귀**: 기존 채팅, 도감, 새소리(RG-409/RG-507) 기능에 영향 없음 | 통과 (`[x]`) | 기존 1,400+ 파이썬 회귀 스위트 및 361건 프런트엔드 스위트 무회귀 통과 확인 |

---

## 3. 주요 구현 내용 (15개 파일 통합)

### 1) 백엔드 (`backend.patch`, 9개 파일)
* `src/robingraph/retrieval/graph_questions.py`:
  * `checked_conditions(conditions, sizes=range(1, 9))`: 기존 채팅 경로는 1~8개 제한 유지, 새 탐색기는 0~11개(서식지 1개 + 먹이 최대 10개) 허용.
  * `_taxon_traits(criterion='explore')`: 조건 0개 허용, 종/아종 입력 시 형질 쿼리 없이 즉시 `rank_unsupported` 차단, 조건 없을 때 타이틀 및 안내 문구 조정.
* `src/robingraph/api/services.py`:
  * `explore_taxa()`: `GET /v1/taxa/explore` 서비스 구현. 조건을 정규 순서(서식지, 그 다음 EltonTraits 키 순서)로 정규화, 분류군 해소 상태(`taxon_resolution`)에 따라 422 에러(`taxon_not_found`, `taxon_ambiguous`, `taxon_rank_conflict`, `taxon_rank_unsupported`) 매핑, 핸들러 부재/오류 시 503 처리, `korea` 스코프 시 `korea_record` limitation 추가, `query` 에코 반환.
* `src/robingraph/api/drf/serializers.py`:
  * `TaxonExploreRequestSerializer`: 스코프, 분류군, 서식지, 먹이 제약 조건 검증. 미지의 파라미터는 `extra_forbidden`, 중복 파라미터는 `duplicate_parameter`, 중복 먹이 키는 `duplicate_value`로 422 리스트 에러 생성.
* `src/robingraph/api/drf/views.py`, `urls.py`:
  * `TaxonExploreView` 및 `v1/taxa/explore` 라우트 등록.
* `src/robingraph/api/drf/openapi.json`, `openapi_ingest.json`:
  * `/v1/taxa/explore` 엔드포인트 명세 추가.
* `tests/test_drf_parity.py`:
  * 마이그레이션 오라클 프로젝션 갱신 및 라우트 셋 포함.
* `tests/test_bird_explorer.py` (신규):
  * `ExplorerPlanTest`(9건) 및 `ExplorerApiTest`(8건) 총 17개 단위 테스트 추가.

### 2) 프런트엔드 UI (`api/static/`) 및 자체 리뷰 개선 (6개 파일)
* `src/robingraph/api/static/explore.html`:
  * 시맨틱 검색 폼: 분포 라디오(`all`, `korea`, `outside`, `unknown`), 목·과·속 자동완성/텍스트 필드, AVONET 대표 서식지 11종 라디오, EltonTraits 먹이 10종 체크박스(접을 수 있는 가이드 포함).
  * 결과 컨테이너: 상단 데이터 커버리지 배너, 20종 카드 목록, 페이지네이션/추가 결과 안내, 조류 프로필 연결.
* `src/robingraph/api/static/explore.css`:
  * 반응형 그리드: 데스크톱 1280px(4열) 및 모바일 390px/320px(2열) 최적화.
  * 모바일 먹이 체크박스 2열 그리드 배치(390px/320px 가로 넘침 방지).
* `src/robingraph/api/static/explore.js`:
  * 상태 관리: 폼 입력 변경 시 자동 제출 방지, 폼 제출 시 비동기 레이스 컨디션 방어(stale 요청 폐기).
  * URL 동기화: 필터 상태를 쿼리스트링으로 직렬화 및 페이지 로드 시 URL 파라미터 완전 복원, 초기화 시 URL 리셋.
* `src/robingraph/api/static/index.html`:
  * 기존 상단 네비게이션에 "새 탐색기" 진입 링크 최소 추가.
* `src/robingraph/api/static/styles.css`:
  * 상단 네비게이션 진입 링크 전용 최소 스타일 추가.
* `tests/frontend/explore_ui.test.js`:
  * 새 탐색기 전용 단위 테스트 7건 추가.
* **root UI 자체 리뷰 반영 사항**:
  1. 기존 도감 표시와의 곤충/고기 분류 통일.
  2. 영문 키 부제 제거로 가독성 향상.
  3. coverage 내부 시스템 키 제거 및 친화적 한글 안내.
  4. 먹이 분류 접이식 안내 문구 추가.
  5. 390px/320px 모바일 뷰포트에서 먹이 항목 2열 최적화.

---

## 4. 실제 검증 및 테스트 결과

### 1) 자동화 백엔드 / 프런트엔드 단위·통합 테스트
* **root 통합 백엔드 테스트 (`root-backend-tests.log`)**:
  * 실행 결과: **167 tests 통과 (2.187초, failure=0, skip=0, error=0)**.
  * `ExplorerPlanTest`(9건) 및 `ExplorerApiTest`(8건) 신규 17건 전수 통과.
* **root 통합 프런트엔드 테스트 (`root-frontend-tests.log`)**:
  * 실행 결과: **361 tests 통과 (337.370417ms, failure=0, skip=0)**.
  * `tests/frontend/explore_ui.test.js`(신규 7건) 포함 전체 UI 스위트 통과.

### 2) 실제 TEST 데이터베이스 연동 in-process Django ASGI 실사 (`real-asgi.json`)
* **검증 환경**: TEST Neo4j (`192.168.219.98:7687`), PostgreSQL `robingraph_test` (`192.168.219.99:5433`).
* **실행 결과**:
  | 번호 | 질의 파라미터 (Query) | 상태 | 전체 대상 (scoped) | 평가 가능 (evaluable) | 조건 일치 (matched) | 반환 수 (shown) | 단일 실행 소요 시간 |
  |---|---|---|---|---|---|---|---|
  | 1 | `{}` (전체 목록) | `answer` | 11,131 | 11,131 | 11,131 | 20 | 0.498s |
  | 2 | `{"taxon": "Anas"}` (오리속) | `answer` | 31 | 31 | 31 | 20 | 0.288s |
  | 3 | `{"species_scope": "korea", "taxon": "Passeriformes", "habitat": "Forest", "diet": "fruit"}` (복합) | `answer` | 256 | 164 | 41 | 20 | 0.226s |
  | 4 | `{"diet": "fruit,seed"}` (다중 먹이 AND) | `answer` | 11,131 | 7,067 | 924 | 20 | 0.551s |
* *참고*: 위 소요 시간은 단일 실행 결과이며 벤치마크로 일반화하지 않음. `db_writes: 0`, `production_changed: false`.

### 3) 로컬 실제 TEST HTTP API 매트릭스 검증 (`actual-api.json`)
* **대상 Origin**: `http://127.0.0.1:8000` (TEST 컨테이너 포트)
* **검증 결과 요약**:
  * **정상 질의 12건**: 모두 200 OK 반환.
    * `{}` (11,131건 일치, 0.218s)
    * `species_scope=korea` (592건 일치, 0.129s)
    * `taxon=Passeriformes` (6,705건 일치, 0.210s)
    * `taxon=Anatidae` (172건 일치, 0.109s)
    * `taxon=Anas` (31건 일치, 0.097s)
    * `habitat=Forest` (5,595건 일치, 0.267s)
    * `diet=fruit` (2,551건 일치, 0.410s)
    * `diet=fruit,seed` (924건 일치, 0.411s, 먹이 합산 내림차순 정렬 확인)
    * `korea + 참새목 + 숲 + 열매` (41건 일치, 0.120s)
    * `outside + Wetland + fish` (0건 일치 `empty` 정상, 0.088s)
    * `species_scope=unknown` (10,533건 일치, 0.127s)
    * `Apterygiformes + fish` (0건 일치 `empty` 정상, 0.106s)
  * **부적절 질의 11건**: 모두 HTTP 422 반환.
    * `diet=invalid`, `habitat=invalid`, `species_scope=invalid`, `diet=fruit,fruit`, `diet=fruit&diet=seed`, `habitat=Forest&habitat=Wetland`, `limit=30`, `taxon=Imaginary`, `taxon=Anas+platyrhynchos`(종 학명 거절), `taxon=`, `diet=`

### 4) 전체 필터 값 실API 추가 전수 검증 (`filter-values-api.json`)
* **대상 Origin**: `http://127.0.0.1:8000` (최종 배포 이미지 `cdfed28ae4e3` 실제 TEST 컨테이너)
* **검증 내용**:
  * 지원되는 **먹이 10개 키 전수** (`invertebrate`, `endotherm_vertebrate`, `ectotherm_vertebrate`, `fish`, `unknown_vertebrate`, `carrion`, `fruit`, `nectar`, `seed`, `other_plant`)
  * 지원되는 **대표 서식환경 11개 값 전수** (`Forest`, `Shrubland`, `Woodland`, `Grassland`, `Rock`, `Wetland`, `Human Modified`, `Coastal`, `Marine`, `Riverine`, `Desert`)
  * 지원되는 **목·과·속 분류군 2개 질의** (`직박구리과` 161/161종, `Turdus` 105/105종)
* **검증 결과 (23건 전수 통과)**:
  * 23개 질의 모두 HTTP 200 OK 및 `status: "answer"` 반환.
  * 모든 결과 항목에서 `taxon.rank == 'species'` 일치 확인.
  * **먹이 질의**: 각 항목별 `EltonTraits 확실성 [ABC]$` 경로 정규식 검증 전수 통과 및 먹이 점유율(%) > 0 확인.
  * **서식지 질의**: 각 항목별 `(<habitat>)` 경로 텍스트 일치 전수 확인.
  * 질의별 소요 시간: 0.085s ~ 0.697s (단일 실행 참고).
* **중복 합산 주의**: 본 23건은 앞서 검증한 `actual-api.json`(12개 정상 + 11개 422 거부)과 별도로 수행된 추가 전수 질의이며, **실제 TEST HTTP 검증은 총 46건(12 + 11 + 23) 전수 통과**함. `db_writes: 0`, `production_changed: false`.

### 5) 배포 이력, 포트 연결 타임아웃 및 1회 수동 재시작 복구
* **1차 배포 (`74c37b75336f`)**:
  * public 브라우저 실사 통과 ([`first-browser-public.json`](../verification/assets/2026-11-10-bird-explorer/first-browser-public.json), 1280px 및 390px 가로 넘침 0건).
* **최종 배포 (`cdfed28ae4e3`) 타임아웃 및 복구 ([`test-port-recovery.json`](../verification/assets/2026-11-10-bird-explorer/test-port-recovery.json))**:
  * CSS 1줄 보완(모바일 2열) 후 최종 배포 시 컨테이너 내부 및 host loopback(127.0.0.1:8000)은 200 OK였으나, 외부 LAN(192.168.219.97:8000) HTTP 타임아웃 및 public 502가 발생함 ([`browser-failure.json`](../verification/assets/2026-11-10-bird-explorer/browser-failure.json)).
  * 포트 바인딩/연결 영역으로 추정되나 원인은 미확정이며, 코드 오류로 단정하지 않음.
  * TEST 컨테이너 명시적 1회 수동 재시작(`docker --context orbstack restart robingraph-api-test`, `manual_test_restart_operations = 1`)을 수행함.
  * 재시작 후 LAN 및 public 200 OK 복구, `container_health: "healthy"`, 컨테이너 재시작 시각 `2026-11-10T04:07:18Z` 정상 갱신 확인. (Docker `RestartCount: 0`은 자동 재시작 카운트이며, 수동 재시작은 StartedAt과 작업 로그로 구분; 운영 재시작 없음).

### 6) 최종 배포본(`cdfed28ae4e3`) 브라우저 E2E 실사 검증
* **도구**: Headless Chromium CDP (너비 1280px / 390px / 320px, 각각 높이 1100px; 물리 모바일 기기 검사는 미실행)
* **검증 아티팩트**:
  * 공개 HTTPS: [`actual-browser.json`](../verification/assets/2026-11-10-bird-explorer/actual-browser.json) (`source_sha256 = "cdfed28ae4e30c0c3e95164ead69b7e41ddc2535ddbfa0d9654f314f39b980a9"`, `origin = "https://robingraph-test.dove-nest.com"`)
  * LAN HTTP: [`final-lan-browser.json`](../verification/assets/2026-11-10-bird-explorer/final-lan-browser.json) (`source_sha256 = "cdfed28ae4e30c0c3e95164ead69b7e41ddc2535ddbfa0d9654f314f39b980a9"`, `origin = "http://192.168.219.97:8000"`)
* **검증 항목 및 결과**:
  * 1280px 데스크톱(1280×1100): `document_width=1280`, `diet_columns=4`, 가로 넘침 0건, 카드 20건 렌더링, 도감 링크 `/birds?name=Oriolus+chinensis&species_scope=korea` 정상 연결, 출처 목록 60건 확인.
  * 390px 모바일(390×1100): `document_width=390`, `diet_columns=2`, 가로 넘침 0건, 모바일 먹이 2열 배치 확인.
  * 320px 극소 모바일(320×1100): `document_width=320`, `diet_columns=2`, 가로 넘침 0건 확인.
  * 기능 인터랙션: 키보드 제출 통과 (`keyboard_submit: true`), 다중 먹이 비율 합산 정렬 통과 (`multiple_diet_share_sum: true`), URL 리로드 시 필터 복원 통과 (`url_reload_filter_restore: true`), 미해소 분류군 메시지 노출 (`invalid_taxon_visible_not_empty: true`), 이전 결과 즉시 제거 (`stale_results_removed: true`), 초기화 시 URL 리셋 (`reset_clears_url: true`), 페이지 런타임 예외 0건 (`page_exceptions: 0`), 채팅/외부 프로바이더 요청 0건 (`chat_or_provider_requests: 0`).
  * **미검증 한계**: 실제 Safari, Firefox 브라우저 및 물리 스마트폰 모바일 기기 검사는 미실시 (`physical_mobile_tested: false`).

---

## 5. 배포 및 형상 관리

* **1차 배포 이미지**: `robingraph-api:test-bird-explorer-74c37b75336f` (검증 완료, `first-test-release.json`)
* **최종 배포 이미지**: `robingraph-api:test-bird-explorer-cdfed28ae4e3`
  * Source Snapshot: `/tmp/robingraph-bird-explorer-20261110/snapshot-cdfed28ae4e3`
  * Source SHA256: `cdfed28ae4e30c0c3e95164ead69b7e41ddc2535ddbfa0d9654f314f39b980a9`
  * Image ID: `sha256:fc5e015f7aa2c3b54614f837901d2971a152cfa13c00e96cad7282eb5ca876ad`
  * Target & State: TEST (`robingraph-test`), `verified`, `arm64`
  * Release Path: `/Users/kimdove/robingraph-test/releases/bird-explorer-cdfed28ae4e3-b705a1`
* **릴리스 동등성 확인 (`release-equivalence.json`)**:
  * 1차와 최종 배포 간의 변경은 `src/robingraph/api/static/explore.css` 1개 파일(모바일 2열)뿐이며 백엔드 소스는 100% 동일함 (`all_backend_sources_identical: true`).
* **보안 및 환경 변수**: 임시 인증 헬퍼 부재, 비밀값/인증 토큰 복사 일체 금지 원칙 준수, 배포 헬퍼는 `.env.nas.test` 환경 파일 직접 참조.
* **운영 배포 여부**: Production(NAS) 배포 없음 (`production_changed: false`, 운영 승인 대기 유지)
* **데이터베이스**: 조류 DB 쓰기 0건 (`bird_db_writes: 0`)
* **Git 형상**: `commit`, `push` 미수행 (`git_commit_push: false`, 워킹 트리 변경 보존)
* **검증 아티팩트 영구 보존**: `docs/verification/assets/2026-11-10-bird-explorer/`
  * `actual-api.json`, `filter-values-api.json`, `actual-browser.json`, `final-lan-browser.json`, `real-asgi.json`, `test-port-recovery.json`, `release-equivalence.json`, `root-final-evidence.json`
  * `first-browser-public.json`, `browser-failure.json`, `test-release.json`, `first-test-release.json`, `deploy-final.log`
  * `root-backend-tests.log`, `root-frontend-tests.log`, `ui-focused-review.log`, `graphify-final.log`, `integrated-code.patch`
  * `actual-explorer-1280.png`, `actual-explorer-390.png`, `actual-explorer-320.png`, `screenshots/` 폴더

---

## 6. 한계 및 후속 과제

1. **운영(NAS) 배포 승인 게이트**: 본 기능은 TEST 환경 격리 배포 및 실사 검증을 완벽히 마쳤으며, 사용자 명시 승인이 있을 때만 운영 NAS 배포를 진행함.
2. **미검증 브라우저 및 물리 기기**: 데스크톱 Headless Chromium CDP로 1280/390/320 뷰포트 검증을 완료하였으나, 실제 Safari, Firefox 브라우저 및 물리 스마트폰 모바일 기기에서의 터치 제스처 검증은 후속 과제로 남김.
3. **공개 urllib 프로브 403 원인 분석**: curl 및 실제 Chromium 브라우저를 통한 공개 UI 접근은 200 정상 작동하였으나, 표준 Python urllib 단독 요청 시 403이 발생한 원인(Cloudflare WAF User-Agent 필터 등)에 대한 추가 관측을 진행할 수 있음.
4. **포트 연결 타임아웃 재발 방지 모니터링**: 최종 배포 시 발생했던 일시적 LAN 타임아웃/502 현상(수동 재시작으로 복구 완료)에 대해 향후 컨테이너 재배포 시 포트 바인딩 안정성을 지속 모니터링함.

---

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- [[Work/RobinGraph/백로그 상세/RG-214|선행 작업: RG-214 먹이 조건 비율 합산 내림차순 정렬]]
- [[Work/RobinGraph/백로그 상세/RG-406|선행 작업: RG-406 한국 서식 여부 토글과 범위별 이름 우선 정책]]
- [실제 TEST API 매트릭스 검증 아티팩트 (23항목)](../verification/assets/2026-11-10-bird-explorer/actual-api.json)
- [전체 필터 값 실API 추가 전수 검증 아티팩트 (23항목)](../verification/assets/2026-11-10-bird-explorer/filter-values-api.json)
- [최종 브라우저 실사 아티팩트 (공개 HTTPS)](../verification/assets/2026-11-10-bird-explorer/actual-browser.json)
- [최종 브라우저 실사 아티팩트 (LAN HTTP)](../verification/assets/2026-11-10-bird-explorer/final-lan-browser.json)
- [포트 타임아웃 및 수동 1회 재시작 복구 매니페스트](../verification/assets/2026-11-10-bird-explorer/test-port-recovery.json)
- [최종 TEST 릴리스 매니페스트](../verification/assets/2026-11-10-bird-explorer/test-release.json)
- [루트 최종 종합 검증 근거 매니페스트](../verification/assets/2026-11-10-bird-explorer/root-final-evidence.json)


## 2026-11-11 후속 운영 반영

위 내용은 최초 TEST 완료 당시 이력이다. 사용자 명시 승인 후 새소리를 제외한 후속 개선·페이지네이션의 운영 배포와 실제 검증을 완료했다. [후속 배포 기록](2026-11-11-approved-non-audio-production.md)을 따른다.
