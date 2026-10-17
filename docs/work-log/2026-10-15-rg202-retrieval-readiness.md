# RG-202 선행 문헌 감사·검색 기준선과 MRR 수정

후속 사용자 지시로 NAS TEST 배포·실제 검증을 완료했다. 아래 선행 작업 당시의 미배포 기록과 구별한다. [NAS TEST 배포 상세](2026-10-15-rg202-nas-test-deployment.md). RG-202 전체의 문헌 확보 대기는 유지한다.

## 요청 배경과 선정 근거

사용자가 Obsidian MCP에서 작업 백로그를 읽고 가장 먼저 필요한 작업을 실행하도록 요청했다. 전체 백로그와 2xx·1xx 상세, 구현·검증 가이드를 읽었다. 신규 권장 순서는 RG-202 → RG-406이며 RG-101은 실측 후 순서를 정한다. RG-102·503·504·505는 별도 재개 지시 전 최후순위 보류다. 따라서 RG-202의 첫 단계인 실제 TEST 문헌·청크·관계·인덱스·임베딩 감사를 선택했다. 전체 백로그의 과거 배포 상태를 현재 상태로 추정하지 않았다.

담당은 Codex이며 현재 세션 기록의 모델은 gpt-6.1-sol이다. 이번 작업에서 하위 에이전트를 새로 실행하거나 다른 에이전트의 코드 변경을 합치지 않았다. 기존 AGENTS.md와 이전 작업 문서는 사용자 변경으로 보존했다.

## 실제 TEST 감사와 판단

2026-10-15 로컬 robingraph-api-test에 연결해 /health의 status=ok, mode=neo4j, deployment_target=test를 확인했다. 컨테이너의 기존 접속 설정을 사용하고 ROBINGRAPH_DEPLOY_TARGET=test를 확인한 뒤 Neo4j 읽기 트랜잭션만 실행했다. 비밀값은 출력하지 않았다.

| 항목 | 실제 결과 |
|---|---:|
| Document | 2 |
| Chunk / HybridSearchChunk | 4 / 4 |
| 검색 청크 본문 길이 합 | 171문자 |
| HybridVectorChunk | 2 |
| PmcPilot 문서 | 0 |
| 정책 재검사·본문 SHA-256 일치 청크 | 4 |
| 이 감사에서 정책 제외된 검색 후보 | 0 |
| Taxon | 33,694 |
| EvidenceUnit 전체 | 136,213 |

문헌은 저장소 합성 fixture 문서 2개뿐이다. Fixture 라벨만으로 합성 여부를 판단하지 않았다. PMC 파일럿도 Fixture 라벨을 사용하므로 문서 식별자·합성 출처 URL과 PmcPilot 라벨을 구별했다. 문헌의 인접 관계는 HAS_CHUNK, FROM_RECORD, FROM_CHUNK였다. 전체 EvidenceUnit·Taxon 개수를 문헌 passage·다단계 근거 수로 세지 않았다.

전문 인덱스 robingraphFixtureChunkFulltext는 ONLINE, HybridSearchChunk.text 대상, standard-no-stop-words 분석기다. 벡터 인덱스 robingraphFixtureChunkVector는 ONLINE, HybridVectorChunk.hybrid_vector 대상, 512차원·COSINE이다. 저장 벡터는 jinaai/jina-embeddings-v3, normalized=true다. 재인덱싱하거나 기존 인덱스를 교체하지 않았다. 질문/문서 임베딩 작업 계약 전체나 모델 서버 revision은 이번에 다시 검증하지 않았다.

정책 재검사와 본문 해시를 통과한 청크 식별자·문서 식별자·본문 해시·원본 record 해시를 텍스트 없이 고정했다. manifest SHA-256은 a32d31c8972b6cb7d851bc1e196386fa0e411064367bcc105e108d2d400f6622다. 검색 노드에는 평가 corpus에 필요한 독립 release provenance가 충분히 저장돼 있지 않으므로 이 manifest를 실제 문헌 평가용 릴리스로 승격하지 않는다.

**판단: RG-202의 선행 감사와 합성 기준선은 완료했지만 전체 RG-202는 미완료다.** 현재 자료로 최소 50문항·다단계 20문항 및 여러 문서의 사실 연결을 독립 검증할 수 없다. 합성 문항을 늘려 실제 문헌 품질 검증으로 포장하지 않는다. 기존 검색을 유지하고 새 검색 활성화·자료 자동 수집은 하지 않았다.

config/source-registry.json과 docs/pmc-literature-pilot.md에서 현재 허용된 실제 문헌은 PMC9946348 한 편뿐임을 확인했다. 이 파일럿은 임베딩 없이 전문 검색하는 경로이며, 허용 판정을 다른 논문에 복사하지 않도록 명시한다. 한 편을 다시 적재해도 다문헌 검증 조건은 충족되지 않는다. 다음 corpus 준비에서는 문서별 출처·라이선스·임베딩 권한 검토가 필요하다.

## 확인한 평가 오류와 변경 전후

기존 evaluate_search는 정답 근거가 있는 질문에서 검색에 성공한 경우만 reciprocal_ranks에 추가했다. 성공 1개·누락 1개의 경우 MRR=1.0을 보고하고, 모두 누락하면 None이었다. 기준선 비교를 신뢰하려면 누락을 포함해야 하므로 모든 답변 가능한 질문을 평균 분모에 포함하고 누락의 RR은 0.0으로 수정했다. 근거가 원래 없는 질문은 기존처럼 MRR 분모에서 제외한다. 개별 case의 reciprocal_rank=None 표기는 유지한다.

성공 1개·누락 1개는 이제 MRR=0.5, 모두 누락은 0.0, 답변 가능한 질문 자체가 없으면 None이다. API 검색 알고리즘·응답 계약·실제 반환 순서는 바꾸지 않았다. 이 수정은 CLI 평가와 벤치마크가 사용하는 공통 계산 함수에 적용된다.

## 변경 파일과 구현

- scripts/audit_retrieval_readiness.py: TEST 전용 읽기 감사. 기존 검색의 권위 있는 양방향 출처 정책 재검사 쿼리를 재사용한다. 실제 인덱스·프로필·라벨별 수·청크 인접 관계와 해시 일치 manifest를 출력한다. 인증 정보와 본문은 직렬화하지 않는다. 읽기 트랜잭션 제한 30초, manifest 최대 1,000개 및 잘림 표시를 둔다. 미분류 문서를 검토 문헌으로 자동 승격하지 않는다.
- src/robingraph/retrieval/evaluation.py: MRR에 누락 질문의 0점을 포함하는 한 곳의 수정.
- tests/test_search_evaluation.py: 성공/누락 혼합, 전체 누락, 답변 가능한 문항 없음의 회귀 3개.
- tests/test_retrieval_readiness.py: 본문 비노출·정렬 독립 manifest, 본문 변경, PMC/합성 구분, 미분류 자료, PROD에서 연결 전 거부의 오프라인 계약 5개.
- docs/verification/assets/2026-10-15-rg202/: 실제 감사 readiness.json, 실제 API 기준선 baseline.json과 재실행용 benchmark.py. 벤치마크는 기존 evaluate_search를 사용하며 응답 본문을 결과 파일에 저장하지 않는다.
- 본 기록 및 Obsidian 전체·2xx 백로그와 같은 카테고리의 작업기록에 상태와 한계를 일치시킨다.

## 실제 API 기준선

고정된 data/eval/v1/search-questions.jsonl의 5문항을 사용했다. 정답 근거가 있는 4문항과 금지 청크 제외를 확인하는 1문항이며 다단계 문항은 0개다. limit=5, 모드별 warmup 1회 제외 후 3회 반복(5×3=15회씩)했다. 총 HTTP 검색 호출은 warmup 포함 32회다. 실제 localhost TEST API·현재 DB·설정된 임베딩 서비스를 사용했고 API route 모의는 없다.

| 모드 | Recall@5 (각 3회 동일) | MRR (각 3회 동일) | p50 | p95 | 지정 금지 청크 제외 |
|---|---:|---:|---:|---:|---|
| fulltext | 0.75 | 0.75 | 909.15ms | 1321.67ms | 3회 모두 통과 |
| hybrid | 1.0 | 0.833333 | 412.53ms | 487.68ms | 3회 모두 통과 |

두 모드 모두 요청 모드 그대로 응답했다. fulltext는 한국어 질문에 영어 검색어를 추가했다는 경고를 반환했고 hybrid의 경고는 없었다. 따라서 fulltext HTTP 지연에는 검색어 변환 단계가 포함되며 순수 Neo4j 질의 시간과 동일하지 않다. 15표본의 nearest-rank p95와 중앙값 p50이며 장시간 부하·고유 문항 15개·통계적 우월성 검증이 아니다. 정책 안전 통과는 해당 gold 파일의 지정 금지 ID 검사 범위이며 전체 라이선스 검증 증명이 아니다. No-evidence 문항의 무응답 품질, 생성 답변·인용 정확성은 별도 평가가 필요하다.

## 검증 명령과 결과

```sh
docker exec -i robingraph-api-test python - < scripts/audit_retrieval_readiness.py
PYTHONPATH=src /tmp/robingraph-qa-python/bin/python docs/verification/assets/2026-10-15-rg202/benchmark.py
PYTHONPATH=src /tmp/robingraph-qa-python/bin/python -m unittest tests.test_search_cli tests.test_search_evaluation tests.test_retrieval_readiness tests.test_hybrid_retrieval
graphify update .
git diff --check
```

초기 회귀 11개 중 2개 실패로 MRR의 누락 질문 문제를 재현했다. 수정 후 관련 최종 스위트는 33개 통과·실패 0·건너뛰기 0이다. 이 33개는 오프라인 fixture/mock 단위·계약 검사이며 위 실제 DB 감사·API 호출과 구분한다. 새 감사 도구의 첫 DB 실행은 managed transaction에 Query 객체를 전달해 TypeError로 실패했다. Neo4j 드라이버 계약에 맞춰 unit_of_work(timeout=30)와 문자열 쿼리로 고친 후 실제 읽기 감사가 통과했다. 앞선 수동 점검의 잘못된 환경 변수 이름 검사도 연결 전에 거부됐고 실제 배포 변수 ROBINGRAPH_DEPLOY_TARGET으로 정정했다.

Graphify AST 갱신은 5,292노드·10,888엣지·327커뮤니티로 완료했다. 5,000노드 초과로 HTML은 커뮤니티 집계 보기로 생성됐다. tree_sitter_sql 부재로 SQL 4개는 추출되지 않았고 문서 의미 추출은 수행하지 않았다. 최초에는 그래프가 없어 원문으로 조사했으며 이번 코드 변경 후 그래프가 생성됐다. git diff --check는 통과했다. 전체 앱 테스트·실제 DB 쓰기 통합·브라우저 검사는 변경 범위가 평가 계산과 감사 도구라 반복하지 않았다.

## 기술 방향과 다음 단계

[HippoRAG 원 논문](https://arxiv.org/abs/2405.14831)은 개체 그래프와 Personalized PageRank를 사용한다. [HippoRAG 2 논문](https://arxiv.org/abs/2502.14802)은 passage 통합과 온라인 LLM 활용을 강화한다. [공식 저장소](https://github.com/OSU-NLP-Group/HippoRAG)도 확인했다. 이번에는 어느 방식의 구현·색인도 추가하지 않았고 두 버전을 혼용한 재현을 주장하지 않는다. 원리의 적용 여부는 허용 문헌과 고정 평가 자료를 갖춘 뒤 결정한다.

재개 순서는 (1) 승인된 여러 문헌의 원문·출처·라이선스·릴리스 고정, (2) passage에 추적 가능한 추출 사실을 기존 분류·형질과 분리해 검토, (3) 단일/다단계/근거 부족 50문항 이상 및 다단계 20문항 이상을 조정/최종 평가로 분리, (4) 같은 corpus·top-k·생성 조건의 기준선과 모든 근거 회수율·인용·무근거 응답·지연/메모리 측정, (5) 개선폭·상한 고정 후 PPR 시험 경로 구현이다. 현재 합성 기준선으로 문헌 실험의 합격 임계값을 정하지 않는다. RG-101의 저장소 전환도 이 작은 자료만으로 정당화하지 않는다.

## 배포·커밋·운영 영향

TEST·Production 이미지 배포, 컨테이너 재시작, DB 쓰기·재적재·스키마·인덱스 변경, commit/push/병합은 수행하지 않았다. TEST에서는 새 감사 스크립트를 표준 입력으로 실행하고 현재 HTTP API를 읽었다. 평가 함수는 실행 서비스의 검색 경로가 아니라 로컬/CLI 보고 계산이므로 이미지 재배포 없이 실제 API 결과에 새 계산을 적용했다. 변경 파일은 미커밋이며 RG-202는 완료 체크하지 않는다. Production 반영은 사용자 별도 승인 전 금지다.
