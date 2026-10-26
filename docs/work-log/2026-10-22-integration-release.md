# [RG-208] 의미 기반 그래프 질의 런타임 통합·관측·TEST 배포 검증 — 2026-10-22

> **문서 상태: 검증 범위 완료 (TEST shadow→active→off→active 전환, 실제 API 27건, 브라우저 8건 및 MLflow 관측 검증 완료; 운영 미배포, Git commit/push 없음)**  
> 상위 에픽 **RG-204 (의미 기반 그래프 질의 해석 및 안전한 실행 전환)**의 최종 4단계 과제인 **RG-208 (통합·관측·TEST 비교·단계적 전환)**의 구현, 빌드, TEST 환경 배포 및 엔드투엔드 검증을 완료했다.  
> 신규 컨테이너 이미지 `robingraph-api:test-semantic-graph-b77e26c7e897`를 TEST 환경에 배포하여 **`shadow` -> `active` -> `off` -> `active`** 단계적 전환 라이프사이클을 거치며 기존 7질문 베이스라인 지문(fingerprint) 일치 확인, 확장 27개 혼합 기능 시나리오 실제 API 전수 성공, 공개 Chromium 뷰포트(1280px 데스크톱 / 390px 모바일) 8건 전수 렌더링 정상(페이지 에러 0건)을 확인했다. 또한 외부 원격 MLflow 실험 33에 `route` 및 `candidates` 추적 span이 성공적으로 저장 및 조회됨을 확인했다.  
> **검증 범위 및 한계 명시**: RG-204 에픽 차원의 TEST 구현 및 런타임 통합 검증은 완료되었으나, **RG-205의 정답셋 사람 검토(Human Gold Review)는 미완료 후속 과제로 명확히 분리**되어 있으므로 상위 에픽 전체 완료로 혼동하지 않는다. 또한 MLflow 조회의 경우 50trace/5초 조회는 timeout이 발생하여 최근 5trace/20초 조회로 검증하였으므로 전체 서버의 부하 성능 검증으로 확대 해석하지 않으며, 물리 모바일 기기/Safari/Firefox 검증 및 부하 시험은 미실행 상태이다. 운영(Production) 배포, 조류 DB 쓰기, Git commit/push는 일체 수행하지 않았다.

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **요구사항 / 목적** | 런타임 파이프라인 통합 & TEST 단계적 전환 | 의미 기반 라우터(`RG-206`)와 조건 추출기(`RG-207`)를 Django + Django REST Framework(DRF) 서비스 레이어에 통합하고, shadow/active/off 런타임 제어 및 관측 가능성(MLflow) 확보 |
| **컨테이너 빌드 & 배포** | TEST 이미지 스냅샷 배포 | 이미지 `robingraph-api:test-semantic-graph-b77e26c7e897` 빌드 및 TEST 환경 배포, manifest 소스 일치(`source_manifest_matches: true`), 컨테이너 healthy 확인 |
| **모드 전환 라이프사이클** | `shadow` -> `active` -> `off` -> `active` | 1) `shadow`: 기존 7질문 fingerprint 일치 확인, 동일 요청 흐름 내 동기 방식으로 임베딩/추출 라우팅 실행 및 span 기록 (백그라운드/병렬 아님).<br>2) `active`: 27개 혼합 기능 시나리오 실제 API 전수 정상 응답 (`api-active.json`).<br>3) `off`: 런타임 비활성화 시 기존 정규식/레거시 경로로 안전 폴백 (7질문 fingerprint 동일).<br>4) `active`: 최종 정상 활성화 복귀 확인 |
| **API 검증** | Baseline(7), Shadow(7), Active(27), Off(7) | 기존 7대 질문 응답 지문 보존 확인 및 확장 27개 혼합 기능 시나리오 실제 API 전수 정상 응답 (표본 내 오실행 0건, 계약 준수) |
| **UI 및 브라우저 검증** | 공개 Chromium 1280px / 390px 8건 통과 | 데스크톱(1280px) 4질문, 모바일(390px) 4질문 전수 통과 (페이지 에러 0건, 스크린샷 8종 증거 확보, 모의 응답 아님) |
| **원격 측정 (Telemetry)** | MLflow 실험 33 저장 및 조회 | `graph_intent.route` 및 `graph_intent.candidates` span 실제 저장 확인.<br>구 내부 URI(`http://mlflow:80`) DNS 실패를 사용자 제공 HTTPS 엔드포인트로 TEST env 설정 수정하여 해결 |
| **런타임 벤치마크** | 순차 호출 지연 및 리소스 샘플링 | active 모드 동일 질문 순차 호출: cold 2,616.623ms, warm 5회 644~781ms (평균 694.7ms). 컨테이너 메모리 159.9MiB(2.0%) 안정화 관측 (`runtime-benchmark.json`) |
| **단위/통합 테스트** | 1,122실행 1,083통과 39skip 0fail | 전체 1,122건 실행 중 1,083 pass, 39 skip, 0 fail (23.857s) 및 graph 모듈 최종 89건 pass 통과 (0.197s) |
| **인프라 및 안전 경계** | 무영향 원칙 준수 | Production 배포 0건, 조류 DB 쓰기 0건, Git commit/push 0건, 격리 TEST 환경 한정 수행 |

---

## 1. 작업 배경 및 아키텍처 통합

### 1) 통합 배경
- RG-206(유형 후보 검색)과 RG-207(원문 조건 추출 및 스팬 커버리지)에서 각각 독립 검증된 모듈을 실제 서비스 런타임인 Django + Django REST Framework(DRF) 애플리케이션에 통합하고, 실서버 환경에서 안전하게 단계적으로 활성화할 수 있는 체계가 필요함.
- 신규 의미 기반 라우팅이 기존 7대 기본 질문에 대한 응답을 훼손하지 않는지(회귀 방지) shadow 모드를 통해 우선 검증하고, 장애 시 즉시 레거시로 복귀할 수 있는 `off` 폴백 메커니즘을 함께 검증해야 함.

### 2) 런타임 모드 제어 아키텍처
- 환경 변수 `ROBINGRAPH_GRAPH_INTENT_MODE`를 통해 런타임 동작 모드를 제어:
  1. `off`: 신규 시맨틱 라우터를 완전히 우회하고 기존 정규식/레거시 라우터만 수행.
  2. `shadow`: 레거시 라우터가 최종 응답을 반환하되, 동일 요청 흐름 내에서 동기 방식으로 신규 시맨틱 파서 및 임베딩 라우터를 실행하여 검증 결과를 로깅 및 MLflow span에 기록 (기존 기획 단계에서는 비동기 백그라운드 병렬 실행을 구상했으나, 실제 구현에서는 동일 요청 스레드 내 동기 방식으로 신규 해석을 관측한 후 기존 응답을 유지하는 구조로 구현됨; 기획과 실제 동기 구현 차이 명시).
  3. `active`: 신규 시맨틱 파서와 임베딩 라우터의 결합 결과(`execution_gate`)를 기반으로 실제 Neo4j Cypher 쿼리를 실행하거나 적정 보류(`clarify`/`insufficient_data`) 응답을 즉시 반환.

---

## 2. 주요 배포 및 구현 내용

### 1) 빌드 및 배포 스펙
* **대상 환경**: TEST 서버 (`robingraph-test.dove-nest.com`, 16GB Mac .97)
* **이미지 태그**: `robingraph-api:test-semantic-graph-b77e26c7e897`
* **소스 해시**: `b77e26c7e8975d29a796e52973c49719f4547a057a36d8fcec74e1df6f0f2c47`
* **빌드 매니페스트**: `test-release.json`에 정의된 소스 파일 sha256 매니페스트 (196개 파일)와 현재 워크트리 소스가 일치함을 검증 (`source_manifest_matches: true`).

### 2) 원격 관측성 (MLflow) 구성 및 DNS 이슈 해결
- **발생 현상**: TEST 컨테이너 기동 시 구 내부 URI(`http://mlflow:80`)에 대한 DNS 해석 실패로 원격 트레이스 전송 오류 발생.
- **해결 방안**: 사용자 제공 외부 보안 HTTPS 주소(`https://mlflow.dove-nest.com`)로 TEST 컨테이너 환경 변수를 수정하여 정상 통신 수립.
- **실측 검증**: 실험 33(`experiment_id: 33`)에 `graph_intent.route` 및 `graph_intent.candidates` 속성이 shadow 및 active 모드에서 각각 정상 저장되고 OpenTelemetry span으로 조회됨을 확인함 (`shadow-mlflow.json`, `active-mlflow.json`).

---

## 3. 검증 및 테스트 결과

### 1) 단계적 모드 전환 (Lifecycle) 실측 검증
전환 절차: `shadow` -> `active` -> `off` -> `active`

| 모드 | 검증 대상 | 질문 수 | 검증 결과 | 세부 판정 |
|---|---|:---:|---|---|
| **Shadow** | 기존 베이스라인 7문항 | 7 | 기존 응답 fingerprint와 일치 확인 | 레거시 응답 보존 및 동기 span 기록 성공 |
| **Active** | 확장 실제 질의 세트 (혼합 기능 시나리오) | 27 | 27건 전수 정상 HTTP 200 및 정형 스키마 응답 | 자연어/대조/부정/미지원 질의 정상 분기 |
| **Off** | 폴백 안전성 검증 | 7 | 기존 응답 fingerprint와 일치 확인 | 레거시 라우터로 무손실 즉각 폴백 확인 |
| **Active** | 최종 서빙 상태 확정 | - | 컨테이너 Health Check 200 OK | 최종 active 서빙 모드로 안착 확인 |

#### API 지연시간 원자료 실측 비교 (`api-{baseline,shadow,active,off}.json`)

| 모드 / 데이터셋 | 질문 수 | 지연시간 (Median) | 지연시간 (Max) | 지연시간 (Min) | 세부 설명 |
|---|:---:|:---:|:---:|:---:|---|
| **api-baseline** | 7 | **300.6ms** | 754.4ms | 4.9ms | 레거시 정규식 라우팅 기준선 |
| **api-shadow** | 7 | **621.2ms** | 2,547.3ms | 387.2ms | 레거시 응답 + 동기 시맨틱 라우팅·span 기록 (동일 7질문) |
| **api-active** | 27 | **659.2ms** | 2,592.1ms | 127.3ms | 27개 혼합 기능 시나리오 (서로 다른 종류 혼합) |
| **api-off** | 7 | **265.1ms** | 703.4ms | 4.4ms | 플래그 off 시 레거시 즉각 폴백 경로 |

- **API 지연 분석 및 해석 주의사항**:
  - 임베딩 라우팅 및 조건 추출 로직이 추가되면서 baseline 대비 shadow/active 모드의 지연시간이 증가함 (median 약 300ms -> 620~660ms, max 2,500ms대). 여기에는 최초 질의 시의 초기 프로토타입 콜드 로드 비용이 포함되어 있음.
  - 본 측정은 소표본 순차 호출(비동시 호출)이며 각 모드별/질문별 조건이 상이하므로, **부하 시험(load testing)이나 성능 향상 주장으로 해석해서는 안 됨**.
  - **지연 시간 구분**: 라우터 단위의 순수 추론 지연(warm p95 = 0.379초)과 전체 웹 API 종단 간(HTTP 요청-Django-DRF-DB-직렬화) 지연시간(active median 659.2ms, max 2,592.1ms)을 명확히 구분하여 기록함.
  - **27개 active API의 성격**: 27개 질문은 자연어 질의뿐만 아니라 명시적 intent, filter, species_scope 등을 포함한 혼합 기능 시나리오 검증 세트이며, 40건 고정 홀드아웃셋(정답셋 평가)과 명확히 구분됨.

### 2) 실제 UI 브라우저 렌더링 검증 (Chromium)
모의 응답(mocking) 없이 실제 TEST API와 통신하는 Chromium 브라우저 환경에서 데스크톱과 모바일 뷰포트 각각 4개 대표 질문(총 8건)을 전수 검증함 (`browser.json` 및 8개 스크린샷 캡처 증거).

| 뷰포트 | 질문 유형 | 질의 내용 | 기대 상태 | 렌더링 결과 | 에러 | 스크린샷 증거 |
|---|---|---|:---:|:---:|:---:|---|
| **1280px** | 자연어 검색 | "열매 먹는 참새목 새를 찾아 줘" | `answer` | 20개 아이템 정상 카드 렌더링 | 0건 | `natural-1280.png` |
| **1280px** | 복합 조건 | "숲에서 살면서 직박구리와 식성이 같은 새가 궁금해" | `answer` | 20개 아이템 정상 카드 렌더링 | 0건 | `shared-1280.png` |
| **1280px** | 부정 조건 | "참새목 중 열매를 안 먹는 새는?" | `clarify` | 안내 및 보류 카드 정상 출력 | 0건 | `negation-1280.png` |
| **1280px** | 미지원 식물 | "참새목 중 감나무 열매를 먹는 새는?" | `abstain` | 자료 부족 안내 정상 출력 | 0건 | `plant-1280.png` |
| **390px** | 자연어 검색 | "열매 먹는 참새목 새를 찾아 줘" | `answer` | 모바일 카드 뷰 20개 렌더링 | 0건 | `natural-390.png` |
| **390px** | 복합 조건 | "숲에서 살면서 직박구리와 식성이 같은 새가 궁금해" | `answer` | 모바일 카드 뷰 20개 렌더링 | 0건 | `shared-390.png` |
| **390px** | 부정 조건 | "참새목 중 열매를 안 먹는 새는?" | `clarify` | 모바일 보류 카드 정상 출력 | 0건 | `negation-390.png` |
| **390px** | 미지원 식물 | "참새목 중 감나무 열매를 먹는 새는?" | `abstain` | 모바일 안내 카드 정상 출력 | 0건 | `plant-390.png` |

### 3) Python 전체 회귀 및 그래프 모듈 테스트
- **전체 통합 테스트**: Python 1,122건 실행 중 **1,083 pass, 39 skip, 0 fail** (23.857s 소요, `integrated-full-python.log`). (39 skip은 DB opt-in 및 외부 환경 번들 부재로 정상 건너뜀)
- **그래프 핵심 스위트**: OpenTelemetry trace 속성 확장 반영 후 **89 pass, 0 skip, 0 fail** (0.197s 소요, `final-graph-tests.log`).

### 4) 실제 TEST 런타임 벤치마크 및 리소스 측정 (`runtime-benchmark.json`)
- **실측 환경**: TEST 컨테이너(`robingraph-api-test`) 재시작 후 `active` 모드에서 동일 읽기 질문("열매 먹는 참새목 새를 찾아 줘")을 콜드 1회 + 웜 5회 순차 호출. (모의 응답 아님, 조류 DB 쓰기 0건, 답변 캐시 없음, 프로세스 메모리 내 프로토타입 캐시만 유지)
- **지연 시간 실측**:
  - Cold 1회: **2,616.623ms** (20개 아이템 반환)
  - Warm 5회: **713.723ms, 647.937ms, 781.396ms, 644.603ms, 686.060ms** (전수 20개 아이템 정상 반환, 평균 약 694.7ms)
- **컨테이너 리소스 샘플링 (CPU / Memory)**:
  - 1회차 (t=0.0s, 기동 직후): CPU 1.08%, Mem 146.8MiB / 7.816GiB (1.83%), PIDs 10
  - 2회차 (t=1.078s, 처리 중): CPU 21.97%, Mem 165.3MiB / 7.816GiB (2.06%), PIDs 13
  - 3회차 (t=3.087s, 처리 중): CPU 16.81%, Mem 159.9MiB / 7.816GiB (2.00%), PIDs 17
  - 4회차 (t=5.096s, 안정화): CPU 0.18%, Mem 159.9MiB / 7.816GiB (2.00%), PIDs 16
  - 최종 스냅샷: CPU 0.14%, Mem 159.9MiB / 7.816GiB (2.00%), PIDs 16
- **중요 한계**: 본 측정은 순차 쿼리 처리 시의 컨테이너 리소스 스냅샷이며, **부하 시험(load testing)이나 최대 처리 용량(peak capacity) 한계 시험이 아님**을 명확히 명시함.

---

## 4. 중요한 한계 및 방법론적 시사점

1. **RG-204 상위 에픽 완료 범위와 RG-205 사람 검토의 분리**:
   - RG-204의 하위 구현 과제인 RG-206, RG-207, RG-208이 모두 검증 완료되어 TEST 환경 런타임 배포가 완수됨.
   - 그러나 **RG-205의 정답 평가셋(Gold Questions)에 대한 '인간/전문가 검토(Human Gold Review)'는 아직 미완료 상태**이므로, 상위 에픽 RG-204는 '진행 중'으로 유지하며 전체 완료로 혼동하지 않아야 함. 사람 검토는 향후 운영 배포 승인 전 독립적인 후속 과제로 명확히 분리 관리됨.
2. **원격 관측(MLflow) 조회 성능 한계**:
   - 50개 트레이스를 5초 타임아웃으로 일괄 조회하는 질의는 타임아웃이 발생함.
   - 최근 5개 트레이스를 20초 타임아웃으로 조회하여 span 기록이 정상 저장됨을 확인함.
   - 따라서 본 검증 결과는 원격 서버에 라우팅 span이 유실 없이 기록된다는 **관측 가능성(Observability) 입증**에 한정되며, MLflow 서버의 대량 부하 처리 성능을 보증하는 것이 아님.
3. **브라우저 및 클라이언트 검증 범위의 한계**:
   - 자동화된 공개 Chromium(1280px, 390px 에뮬레이션)으로 UI 레이아웃 및 렌더링을 검증함.
   - 실제 물리 모바일 기기 터치/제스처 반응, Safari(WebKit) 엔진, Firefox(Gecko) 엔진 검증은 미실행 상태임.
4. **운영 환경 및 데이터 무변경 원칙**:
   - 모든 배포 및 검증은 격리된 TEST 환경(16GB Mac .97)에서만 수행됨.
   - Production 배포, 운영 DB 및 조류 DB 쓰기, Git commit/push는 수행하지 않음.

---

## 5. 작업 현황 및 순차 진행 로드맵

1. **RG-203**: `완료 (2026-10-22, 구현·TEST 검증 완료; 운영 미배포 · 향후 명시 승인 필수)` (보존).
2. **RG-204 (상위 에픽)**: **`진행 중 (2026-10-22, TEST 구현·통합·검증 완료; 단, RG-205 사람 검토 미완료로 진행 중 유지, 운영은 향후 별도 승인)`**.
3. **RG-205 (Phase 1)**: `진행 중 (계약·기준선·에이전트 평가셋 구축 검증 완료; 사람 미검토 분리)`.
4. **RG-206 (Phase 2)**: `완료 (2026-10-22, 검증 범위 한정: 유형 후보 검색 완료; 전체 semantic quality 미검증)`.
5. **RG-207 (Phase 3)**: `완료 (2026-10-22, 검증 범위 완료: 원문 조건 추출·스팬 커버리지·안전 검증 완료; 런타임 엔드투엔드는 RG-208로 연계)`.
6. **RG-208 (Phase 4)**: **`완료 (2026-10-22, 검증 범위 완료: TEST shadow→active→off→active 전환 및 실제 API/브라우저/MLflow 검증 완료; 운영 미배포)`**.

---

## 관련 문서 및 검증 증거 링크

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 검색·RAG·그래프 질의 작업 백로그]]
- 선행 작업 문서:
  - [`2026-10-22-semantic-graph-routing.md`](2026-10-22-semantic-graph-routing.md) (선행 설계 및 평가 게이트 검증)
  - [`2026-10-22-candidate-router.md`](2026-10-22-candidate-router.md) (RG-206 질의 유형 후보 검색 검증)
  - [`2026-10-22-condition-extractor.md`](2026-10-22-condition-extractor.md) (RG-207 원문 조건 추출기 검증)
- 검증 자산 (상대 경로 링크):
  - [`integration-summary.json`](../verification/assets/2026-10-22-semantic-graph-routing/integration-summary.json) (통합 및 라이프사이클 요약 메트릭)
  - [`runtime-benchmark.json`](../verification/assets/2026-10-22-semantic-graph-routing/runtime-benchmark.json) (TEST 런타임 콜드/웜 지연 및 리소스 샘플링)
  - [`test-release.json`](../verification/assets/2026-10-22-semantic-graph-routing/test-release.json) (TEST 배포 이미지 및 소스 해시 매니페스트)
  - [`api-active.json`](../verification/assets/2026-10-22-semantic-graph-routing/api-active.json) (Active 모드 27개 실제 질의 API 응답)
  - [`browser.json`](../verification/assets/2026-10-22-semantic-graph-routing/browser.json) (Chromium 1280/390 8건 브라우저 렌더링 결과)
  - [`shadow-mlflow.json`](../verification/assets/2026-10-22-semantic-graph-routing/shadow-mlflow.json) (Shadow 모드 MLflow 추적 span)
  - [`active-mlflow.json`](../verification/assets/2026-10-22-semantic-graph-routing/active-mlflow.json) (Active 모드 MLflow 추적 span)
  - [`final-graph-tests.log`](../verification/assets/2026-10-22-semantic-graph-routing/final-graph-tests.log) (최종 그래프 모듈 단위 테스트 89건 로그)
  - [`integrated-full-python.log`](../verification/assets/2026-10-22-semantic-graph-routing/integrated-full-python.log) (전체 회귀 테스트 1,122건 실행 로그)
- 관련 상세 백로그:
  - [[Work/RobinGraph/백로그 상세/RG-204|RG-204 — 의미 기반 그래프 질의 해석 및 안전한 실행 전환 (상위/에픽)]]
  - [[Work/RobinGraph/백로그 상세/RG-205|RG-205 — 구조화 질의 계약·정답 평가셋·현재 기준선]]
  - [[Work/RobinGraph/백로그 상세/RG-206|RG-206 — 질문 임베딩 기반 질의 유형 후보 검색]]
  - [[Work/RobinGraph/백로그 상세/RG-207|RG-207 — 원문 조건 추출·엔티티 연결·안전 검증]]
  - [[Work/RobinGraph/백로그 상세/RG-208|RG-208 — 통합·관측·TEST 비교·단계적 전환]]
