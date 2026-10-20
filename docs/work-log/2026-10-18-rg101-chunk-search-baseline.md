# RG-101 문헌 Chunk 검색 기준선 실측 — 2026-10-18

## 배경·목표·작업 범위

사용자가 백로그의 다음 작업으로 추천한 RG-101 첫 단계 진행을 승인했다. 문헌 청크 규모,
검색 p50/p95, 정책 필터 탈락과 확인 가능한 메모리 지표를 TEST에서 측정해 PostgreSQL
분리의 필요성을 판단한다. 분리 구현·스키마 쓰기·재색인·수집·운영 배포 승인은 아니다.
종 이름 벡터 검색은 Neo4j에 그대로 두며 이 작업의 대상과 구별한다.

## 확인한 현재 상태

실행 중 TEST 앱은 M4 16GB의 robingraph-api-test이며 Neo4j는 bolt://192.168.219.98:7687,
PostgreSQL은 NAS 192.168.219.99의 robingraph_test다. 배포 target와 Neo4j URI를
스크립트에서 강제 확인하고 PostgreSQL DB도 정확히 일치할 때만 조회했다.

- Document 2개 모두 RobinGraph/Fixture 라벨, Chunk/HybridSearchChunk 4개.
- 본문 171문자, UTF-8 합계 357바이트. 이는 본문 payload만이며 인덱스/DB 크기가 아니다.
- HybridVectorChunk 2개, 512차원, 총 벡터 성분 1,024개. 원소 수를 실제 인덱스 메모리로 환산하지 않는다.
- Chunk 전문·벡터 인덱스 ONLINE/100%. 별도 robingraphTaxonNameVector도 ONLINE이며 변경하지 않았다.
- SourceDataset 3개, Taxon 33,694개. 도메인 그래프 노드 수를 문헌 코퍼스 규모로 간주하지 않는다.
- 2026-10-15의 RG-202 문헌 감사와 같은 작은 fixture 규모다. 실제 다문헌 코퍼스에서의 측정이 아니다.

## 구현과 재현

새 scripts/measure_chunk_search.py는 읽기 전용 TEST 측정 스크립트다. bootstrap/index_chunks,
write transaction, DDL, 적재를 호출하지 않는다. 기존 검색 코드를 바꾸지 않고 동일 search와
전문·벡터·정책 재확인 쿼리를 사용한다. 집계·지연·오류 타입만 출력하며 본문·벡터·비밀번호를
산출물로 내보내지 않는다. PostgreSQL은 default_transaction_read_only=on과 statement timeout을
설정해 metadata만 조회한다. Neo4j 진단 쿼리는 READ_ACCESS와 20초 timeout을 사용한다.
기존 검색 모듈 내부 세션의 기본 access mode는 변경하지 않았으며 실행 쿼리는 읽기 전용이다.

실제 실행:

```sh
docker --context orbstack exec -i robingraph-api-test python - < scripts/measure_chunk_search.py
uv run --locked --extra test python -m unittest tests.test_chunk_search_measurement
graphify update .
```

inventory.py와 memory.py는 docs/verification/assets/2026-10-18-rg101/에 함께 보관했다.
같은 docker exec stdin 방식으로 실행했다. 계정 정보는 실행 컨테이너 환경에서만 읽었다.
문헌 내용·인증정보·전체 환경 파일은 기록하지 않았다.

## 측정 설계와 실제 결과

기존 data/eval/v1/search-questions.jsonl 5문항을 사용했다. 실제 설정 임베딩 서비스에
5번 요청해 각 질의의 벡터를 한 번 생성했다. 이후 생성 벡터를 재사용해 DB 검색 시간을
분리했다. 합성 벡터나 mock API를 사용한 검사가 아니다. 모드별 1회 전체 질의 warmup은 제외하고
10회 × 5질의 = 50표본을 측정했다. concurrency 1, warm sequential baseline이며 부하/scale 시험이 아니다.
p50은 median, p95는 nearest-rank 방식이다. 단계별 측정은 별도 50표본이며 모드별 측정과 합산하지 않는다.

| 검색 경로 | 표본 | p50 ms | p95 ms | 최대 ms |
|---|---:|---:|---:|---:|
| 전문 검색 전체 | 50 | 3.945 | 6.806 | 11.232 |
| 벡터 검색 전체 | 50 | 8.920 | 18.262 | 20.909 |
| 하이브리드 전체 | 50 | 9.504 | 10.851 | 25.447 |
| 전문 쿼리 단계 | 50 | 1.910 | 2.643 | 5.691 |
| 벡터 쿼리 단계 | 50 | 4.358 | 4.612 | 4.631 |
| 정책 재확인 단계 | 50 | 1.862 | 2.383 | 3.286 |

검색 전체 시간에는 클라이언트 로직·Bolt 왕복·정책 확인·RRF가 포함되고, 외부 임베딩 생성·HTTP·LLM 답변 생성은 포함하지 않는다.
벡터 p95가 하이브리드보다 큰 것은 실행 순서와 런타임 변동이 통제되지 않은 별도 표본이며 하이브리드가
더 빠르다는 일반 결론으로 읽지 않는다. 각 표본의 순위 지표 평가나 통계적 유의성 검정은 실행하지 않았다.

실제 임베딩 생성은 첫 8,729.422ms, 이후 215.594/216.448/215.484/205.979ms였다.
첫 호출과 이후 호출의 차이는 관측됐지만 cold-start/네트워크 등 원인을 분리 검증하지 않았다.
벡터·하이브리드가 모두 warning 0으로 실행됐고 벡터 비활성 fallback을 성공으로 오인하지 않았다.

후보 합집합 130회분 중 정책 재확인 제외 0, eligible embedding 불허 0. 모든 모드에서 fixture
금지 ID 반환 0. 현재 후보에 실제 불허 항목이 없으므로 정책 취소·오래된 사본·fail-closed 경계의
실제 부정 사례 검증 완료를 뜻하지 않는다. 그런 검증을 위해 정책을 변경하지 않았다.

## 메모리·PG 인프라 확인

- Neo4j 설정: heap initial 4GiB/max 6GiB, page cache 1GiB.
- JMX heap used: 전 1,068,029,448B, 후 1,411,962,376B. non-heap used: 전 266,723,936B, 후 276,668,304B.
- 공유 인스턴스이며 GC/동시 요청/서버 상태를 통제하지 않았다. 차이를 청크·벡터의 메모리 사용량으로 귀속하지 않는다.
- org.neo4j JMX 조회에 page-cache 지표가 노출되지 않았다. page-cache hit ratio, 프로세스 RSS,
  인덱스별 디스크 크기·메모리 영향은 미측정이다. Mac32에 BatchMode SSH로 docker stats를 시도했으나
  publickey/password 인증이 거부됐다. 추가 인증 흐름이나 서비스 변경을 하지 않고 미검증으로 남겼다.
- NAS PostgreSQL metadata: read-only transaction 확인. pg_trgm 1.6은 available이나 installed_version null.
  vector/pg_bigm/pgroonga는 pg_available_extensions 결과에 없다. 해당 인스턴스의 현재 사용 가능 확장 기준이다.
  다른 서버나 향후 이미지의 지원 가능성까지 부정하지 않는다. 확장 설치나 DB 이미지 교체는 수행하지 않았다.

## 판단과 후속

**현재는 Neo4j 유지, PG 분리 구현은 보류한다.** 문헌이 4개 청크여서 규모로 인한 병목을
재현하지 못했고 PG 후보를 실제 비교하지 않았다. 임베딩 지연이 DB 지연보다 크게 관측됐지만
전체 서비스 병목이라고 단정하지 않는다. 검색 backend 변경으로 첫 임베딩 지연을 해결한다고 보장할 수 없다.

RG-101은 전체 완료가 아니다. 상태는 **착수·소규모 기준선 측정 완료, 실제 문헌 규모 판단 후속**이 적절하다.
대표 문헌/한국어 질의와 품질·지연 목표를 먼저 정하고, 수집·정책 허용이 확인된 자료를 격리된 환경에서
규모별 측정해야 한다. 이후 메모리 지표 수집과 pgvector 지원 인프라 후보, 한국어 전문 검색 비교를 진행한다.
임의의 이전 시점·청크 수를 확정하지 않는다. ADR-0007은 Proposed를 유지하고 실측 후속만 추가했다.

## 검증·형상·배포·한계

- tests/test_chunk_search_measurement.py 3개 통과, 실패/skip 0. p95 계산과 TEST/운영 호스트·target guard의
  단위 검증이며 실제 DB/API 검증과 구별한다.
- 실제 TEST Neo4j/JMX, 실제 임베딩 서비스 5질의, 실제 PostgreSQL metadata 조회가 성공했다.
- 측정 전후 Chunk 수·문자 수·벡터 성분 수 집계 일치. 모든 속성의 완전 해시 비교는 수행하지 않았다.
- 앱/API/UI 코드, DB 스키마/데이터/인덱스, 배포·컨테이너·운영 환경을 변경하지 않았다.
  따라서 이 작업의 TEST 배포나 운영 배포 완료 주장은 해당하지 않는다.
- 신규 commit/push/merge 없음. 앞선 Jenkins/CSS의 미커밋 파일은 보존했다.
- graphify AST 갱신 성공. SQL parser 미설치와 community labeling 안내는 별도 도구 한계다.
- 전체 회귀 테스트·물리 모바일·HTTP/LLM 응답 품질·실제 문헌 scale·PG 비교·rollback은 미실행이며,
  계측 스크립트만 추가했으므로 관계없는 전체 검사를 반복하지 않았다.

실측 원문: docs/verification/assets/2026-10-18-rg101/ 의 inventory.json, benchmark.json,
memory-before.json, memory-after.json, unit-tests.txt, graphify.txt.

## 사용자 후속 지시: 보류

2026-10-18 사용자가 RG-101을 일단 보류하고 RG-406 진행을 지시했다. 이 문서의 기준선 측정 결과는 보존하고, 실제 문헌 축적·대표 규모 비교 전까지 추가 구현/DB 이전은 진행하지 않는다. 전체 완료로 표시하지 않는다.
