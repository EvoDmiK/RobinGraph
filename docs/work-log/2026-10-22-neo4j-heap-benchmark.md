# TEST Neo4j Heap 감소 성능측정 (2GiB/4GiB) — 2026-10-22

> **문서 상태: 읽기 전용 벤치마크 완료 (설정·코드·DB 무변경)**
> TEST 환경(16GB Mac .97 앱 / 32GB Mac .98 Neo4j)에서 Neo4j 힙 메모리 축소(초기 2GiB / 최대 4GiB, pagecache 1GiB) 설정 하의 순수 읽기 성능을 실측했다. Chunk 검색(10/18 기준선 관측 비교), 분류군(Taxon) 노드 33,694개 도메인 그래프 복합 관계 질의, 855종 이름 벡터 검색의 지연 시간 및 JVM 힙/GC 상태를 순차 warm 조건에서 측정했다. 인프라 설정 변경, 컨테이너 재시작, DB 쓰기, 애플리케이션 코드 변경, 운영 반영 및 Git commit/push는 일체 수행하지 않았다.

---

## 1. 벤치마크 환경 및 핵심 실측 요약

- **대상 인프라 구성**:
  - TEST Neo4j 인스턴스: `bolt://192.168.219.98:7687` (32GB Mac mini .98, Neo4j 5.26.30)
  - TEST PostgreSQL: `robingraph_test` (NAS 192.168.219.99:5433, Read-Only 트랜잭션 검증)
  - 실행 환경: 16GB Mac mini .97 (`robingraph-api-test` 활성 컨테이너 환경)
- **연결 확인 및 보안 준수**:
  - 원격 비대화형 SSH BatchMode 읽기 실패 후, 현재 정상 기동 중인 TEST 앱 런타임 환경을 통해 Neo4j 드라이버 세션을 안전하게 연결함. 비밀번호 등 인증 정보는 문서에 일체 기록하지 않음.
- **Neo4j 메모리 설정 비교**:
  - 현재 (2026-10-22 실측): `server.memory.heap.initial_size=2.00GiB`, `server.memory.heap.max_size=4.00GiB`, `server.memory.pagecache.size=1.00GiB` (`SHOW SETTINGS` 검증 완료)
  - 과거 기준선 (2026-10-18): 초기 4.00GiB / 최대 6.00GiB, pagecache 1.00GiB (pagecache 동일)
- **도메인 데이터 규모 (현재 실측)**:
  - `Taxon`: 33,694개 (종뿐만 아니라 상위 분류 및 아종을 포함한 전체 분류군 노드 수)
  - `TraitClaim`: 174,843개, `TaxonNameVector`: 855개
  - `Chunk`: 개수(4개), 문자 수(171자), UTF-8 바이트(357B), vector 성분 수(1,024개) 집계 동일 확인 (`chunk_aggregate_matches_historical: true`)
  - 4개 핵심 레이블(`Taxon`, `TraitClaim`, `Chunk`, `TaxonNameVector`) 개수 집계 동일 확인 (`counts_mid_to_after_unchanged: true`)
- **실행 프로브 및 재현 명령어**:
  - Chunk 검색: `docker --context orbstack exec -i robingraph-api-test python - < scripts/measure_chunk_search.py` (오류 0, 경고 0, 금지결과 0건)
  - 그래프 질의: `docker --context orbstack exec -i robingraph-api-test python - < docs/verification/assets/2026-10-22-neo4j-heap-benchmark/graph-probe.py`
  - 이름 벡터: `docker --context orbstack exec -i robingraph-api-test python - < docs/verification/assets/2026-10-22-neo4j-heap-benchmark/names-probe.py`
  - 런타임 JMX: `docker --context orbstack exec -i robingraph-api-test python - < docs/verification/assets/2026-10-22-neo4j-heap-benchmark/runtime-probe.py`

### 핵심 실측 결과 비교표

| 구분 | 모드 / 질의 대상 | 표본 수 | 과거 실측 (10/18, 4G/6G) | 현재 실측 (10/22, 2G/4G) | 차이 (관측치) | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| **Chunk 검색** | Fulltext (전문) | 50회 | p50: 3.945ms / p95: 6.806ms | p50: **5.453ms** / p95: 9.535ms | +1.508ms (+38.2%) | 4개 Fixture 코퍼스 집계 동일 |
| | Vector (벡터) | 50회 | p50: 8.920ms / p95: 18.262ms | p50: **10.901ms** / p95: 13.303ms | +1.981ms (+22.2%) | 임베딩 생성 지연 제외 |
| | Hybrid (RRF) | 50회 | p50: 9.504ms / p95: 10.851ms | p50: **11.386ms** / p95: 13.413ms | +1.882ms (+19.8%) | 정책 재확인 포함 |
| **그래프 질의** | 복합 관계 6문항 | 120회 (문항당 20) | (과거 기준선 없음) | DB 왕복: **60.3 ~ 273.7ms**<br>전체: **132.8 ~ 490.0ms** | (신규 실측) | 380 Cypher 실행 (warm 120회 기준, warmup 별도), 해시 100% 일치 |
| **이름 벡터** | 저장 벡터 3종 검색 | 60회 (종당 20) | (과거 기준선 없음) | DB 왕복: **2.456 ~ 2.924ms** | (신규 실측) | self top-1 100% 일치 |
| **JVM 힙 관측** | Used Heap (스냅샷) | 3회 관측 | (과거 직접 비교 제외: 단위·부하 상이) | **303.9 MiB → 265.9 MiB → 123.0 MiB** | (순간 관측치) | 프로세스 RSS 아님, 최고치 아님 |
| **GC 동작** | G1 GC (mid→after) | 구간 측정 | - | Young GC: **4회 (47ms)**<br>Old GC: **0회 (0ms)** | 해당 구간만 측정 | 장기 부하 테스트 아님 |

---

## 2. 세부 검증 내용 및 관측 사실

### 1) Chunk 검색 관측 비교 (`chunk-current.json`, `summary.json`)
- 5개 표준 문항(SQ-001 ~ SQ-005)에 대해 warm 순차 실행(각 10회, 총 50표본)을 수행했다.
- 단계별 세부 지연: 전문 검색 단계 p50 2.297ms, 벡터 검색 단계 p50 4.796ms, 정책 권위 재확인 단계 p50 2.253ms로 측정되었다.
- 10/18 기준선 대비 약 +1.5 ~ 2.0ms의 지연 증가가 관측되었으나, **과거와 현재의 코드베이스, 데이터 구성 및 테스트 환경이 달라 이를 힙 감소에 따른 인과적 A/B 결과로 단정할 수 없다.**
- Chunk 코퍼스는 개수(4개), 문자 수(171자), vector 성분 수(1,024개) 집계가 과거와 동일하며(본문 자체의 동일성을 증명하는 것은 아님), 대규모 문헌 코퍼스 하의 힙 영향도를 검증한 것은 아니다.
- 외부 임베딩 API 호출 지연(Jina API: 첫 호출 580.6ms, 이후 192~215ms)은 DB 엔진 지연 측정에서 명확히 분리하여 제외했다.
- 실측 오류 및 경고는 0건(`errors: 0, warnings: 0, forbidden_results: 0`)이었다.

### 2) 도메인 그래프 관계 질의 실측 (`graph-current.json`, `graph-probe.py`)
- RG-203 복합 관계 질의 6문항을 순회하며 각 20회(총 120회) 실측했다 (첫 1회 웜업 제외):
  1. 청둥오리-흰뺨검둥오리 공통 분류 계통(LCA, 결과 2건): DB 왕복 p50 71.2ms, 전체 217.8ms
  2. 청둥오리 동일 속 종(결과 20건): DB 왕복 p50 60.3ms, 전체 137.8ms
  3. 한국 기록 동일 속 종(결과 4건): DB 왕복 p50 63.7ms, 전체 132.8ms
  4. 참새목 열매 섭식 종(결과 20건): DB 왕복 p50 195.5ms, 전체 242.0ms
  5. 서식지 일치 및 먹이 상이 종(결과 20건): DB 왕복 p50 195.0ms, 전체 377.9ms
  6. 숲 직박구리 먹이 공유 종(결과 20건): DB 왕복 p50 273.7ms, 전체 490.0ms
- warm 120회에 대해 총 380회의 Cypher 쿼리(문항당 3~4개)가 실행되었으며(웜업 1회는 별도 제외), 20회 반복 간 결과 해시가 100% 일치하여 응답 안정성을 검증했다.
- 지연시간은 Bolt 네트워크 및 드라이버 디코딩을 포함한 순수 Neo4j 왕복이 **60.3ms ~ 273.7ms**, PostgreSQL 메타데이터 조회 및 Python 계층 처리를 포함한 서비스 전체가 **132.8ms ~ 490.0ms**였다(HTTP 통신, 분류 모델, 임베딩 호출 제외).

### 3) 종 이름 벡터 검색 실측 및 프로브 가드 보정 (`names-current.json`, `names-probe.py`)
- 저장된 855건 카탈로그 중 3종(`Nestor notabilis`, `Anas zonorhyncha`, `Anas platyrhynchos`)의 사전 적재 벡터를 재사용하여 각 20회(총 60회) 검색을 수행했다.
- top-1 자가 매칭 정확도는 **60회 전수 100%** 일치했으며, Neo4j 왕복 지연 p50은 **2.456ms ~ 2.924ms** (Nestor 2.924ms, zonorhyncha 2.787ms, platyrhynchos 2.456ms)로 매우 신속했다.
- 본 측정은 이미 저장된 벡터 속성을 조회하는 단일 Cypher 쿼리 벤치마크이며, 외부 임베딩 호출 및 전체 repository preflight 초기화 시간은 포함하지 않는다.
- **프로브 진단 가드 보정 이력**: 최초 프로브 작성 시 cosine 유사도 조건을 `> 0.9999`로 과도하게 엄격히 설정하여 올바른 1위 결과(`score: 0.9998698...`)를 비정상 탈락시키는 현상이 발생했다. 이는 애플리케이션이나 인덱스 버그가 아니며, 진단 가드를 올바른 `taxon_id` 일치 및 유효 유사도 범위(`0 <= score <= 1`)로 정정하여 60회 전수 통과했다.

### 4) JVM 힙 및 GC 동작 관측 (`runtime-mid.json`, `runtime-after.json`, `memory-before.json`)
- JMX MBean(`java.lang:type=Memory`, `java.lang:type=GarbageCollector`, `java.lang:type=Runtime`)을 통해 측정했다.
- 힙 사용량(used): 시작 시점 303.9 MiB(318,627,960B) → 그래프 질의 중간 265.9 MiB(278,852,064B) → 측정 종료 후 123.0 MiB(129,002,256B). 이는 순간 스냅샷 관측치일 뿐 프로세스 RSS나 최고 메모리 점유가 아니다.
- GC 델타(mid→after): G1 Young Generation GC 4회(누적 47ms) 발생, Old Generation GC는 0회(0ms)였다 (해당 구간만 측정).

---

## 3. 한계 및 해석 유의사항

1. **인과적 A/B 비교 불가**: 10/18과 10/22 간 힙 크기 외에도 코드베이스 및 데이터 구성 차이가 존재하므로 관측된 지연 차이를 힙 축소의 직접적 영향으로 단정하지 않는다.
2. **청크 코퍼스 규모의 한계**: 4개 synthetic fixture(171자) 집계 동일 확인에 불과하여, 수만~수십만 청크가 적재된 대규모 문헌 환경에서의 힙 점유를 대변하지 않는다.
3. **힙 추가 축소 안전 확언 금지**: 본 벤치마크는 단일 스레드(동시성 1) 순차 warm 읽기 부하에 국한된다. "현재의 순차 읽기 부하 하에서 요청 오류가 없고 해당 측정 범위 내 큰 지연이 관측되지 않았다"는 선까지만 유효하며, 단기 스냅샷으로 메모리 누수 여부를 판정할 수 없고 힙을 더 줄여도 안전하다거나 대규모 운영 부하를 견딜 수 있다는 결론으로 확대 해석하지 않는다.
4. **미검증 영역**: Cold cache(인스턴스 재시작 직후), 다중 동시 요청(고동시성), 장기 GC soak, OS 레벨 물리 메모리(RSS, Swap, 페이지 캐시 히트율)는 검증 대상에 포함되지 않았다.

---

## 관련 문서 및 증거 자산

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/1xx DB·저장소/작업 백로그|1xx DB·저장소 작업 백로그]] (기존 백로그 항목 상태 변경 없음, 기록 링크만 보존)
- 선행 기준선 기록: [[Work/RobinGraph/작업기록/1xx DB·저장소/2026-10-18-RG101-문헌청크-검색기준선-실측|RG-101 문헌 Chunk 검색 기준선 실측 (2026-10-18)]]
- 검증 요약: [summary.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/summary.json)
- Chunk 검색 실측: [chunk-current.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/chunk-current.json)
- 도메인 그래프 실측: [graph-current.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/graph-current.json)
- 이름 벡터 실측: [names-current.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/names-current.json)
- 런타임 중간 스냅샷: [runtime-mid.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/runtime-mid.json)
- 런타임 종료 스냅샷: [runtime-after.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/runtime-after.json)
- 시작 전 메모리 스냅샷: [memory-before.json](../verification/assets/2026-10-22-neo4j-heap-benchmark/memory-before.json)
- 재현 프로브 스크립트:
  - 그래프 벤치마크: [graph-probe.py](../verification/assets/2026-10-22-neo4j-heap-benchmark/graph-probe.py)
  - 이름 벡터 벤치마크: [names-probe.py](../verification/assets/2026-10-22-neo4j-heap-benchmark/names-probe.py)
  - JMX 런타임 수집기: [runtime-probe.py](../verification/assets/2026-10-22-neo4j-heap-benchmark/runtime-probe.py)
- 과거 기준선 자산: [2026-10-18 benchmark.json](../verification/assets/2026-10-18-rg101/benchmark.json)
- **실제 검증 자산 보존 위치** (`dev-codex`):
  `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-22-neo4j-heap-benchmark/`
