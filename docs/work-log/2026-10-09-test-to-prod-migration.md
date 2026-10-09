# TEST → PROD 데이터 이관 — 2026-10-09

## 요청 배경과 목표

TEST 서버에만 올라가 있던 데이터를 PROD DB로 옮긴다. 사용자는 PROD의 기존 데이터를
모두 지우고 TEST 데이터 전부를 옮기도록 승인했고, PROD 직접 접속도 허용했다.
작업 중 TEST 서버 Neo4j를 잠시 중지하는 것과 PROD Neo4j의 짧은 중단도 승인받았다.

## 사전 확인한 사실

저장소에는 TEST/PROD 간 데이터 이관 스크립트나 절차 문서가 없었다
(`docs/nas-deployment.md`의 TEST/PROD 전환은 API 컨테이너 배포만 다룬다).
적재 스크립트(`load_*.py`)는 원본에서 DB로 넣는 용도이며 DB 간 복사는 하지 않는다.
이관은 DB 덤프와 복원으로 수행했다.

| 항목 | PROD | TEST |
|---|---|---|
| Neo4j 위치 | NAS `neo4j` 컨테이너, `neo4j:latest` (2026.08.1), 데이터 `/volume3/Birds-Nest/docker-data/homelab/neo4j/data` | Mac mini 로컬 `neo4j-test` 컨테이너, `neo4j:5.26.30-community` |
| PostgreSQL | NAS `postgres-n8n` 컨테이너(호스트 포트 5433), DB `robingraph`, 스키마 `ingest` | 같은 컨테이너, DB `robingraph_test` |

- 5433 포트의 PostgreSQL은 n8n이 함께 쓰는 인스턴스다. 이관은 `robingraph` DB의
  `ingest` 스키마 안에서만 수행했고 다른 DB는 건드리지 않았다.
- TEST와 PROD는 각각 `.env.nas.test`, `.env.nas.prod`(NAS `~/RobinGraph-rg001-20261002/`)로 구분된다.

## 이관 전 상태 (읽기 전용 확인)

| 항목 | PROD | TEST |
|---|---|---|
| Neo4j 노드 | 약 162,000 (ExternalIdentifier 60,796 / Taxon 33,684 / ScientificName 33,684 / SourceRecord 33,684 외 소수) | 474,998 |
| Neo4j 관계 | 262,856 | 543,637 |
| TEST 주요 레이블 | — | TraitClaim 174,843 / EvidenceUnit 136,213 / ExternalIdentifier 60,796 / ScientificName 33,723 / Taxon 33,694 / TaxonMappingClaim 17,648 / VernacularName 13,690 / TaxonMappingCandidate 3,371 / BirdNameUsage 396 / VernacularNameCandidate 306 / SourceRecord 116 / Observation 116 / MediaAsset 36 / BirdTaxon 29 / Place 8 / Chunk 4 / TaxonConceptSet 3 / SourceDataset 3 / Document 2 / License 1 |
| Neo4j 인덱스 | — | LOOKUP 2, FULLTEXT 1, VECTOR 1, RANGE 18 |
| PG `ingest` 테이블 | 8개 모두 0행 | `source_record` 57,625 / `ingestion_run` 33 / `source_release` 10 / `source_dataset` 13 / `outbox_event` 0 |

`pg_stat_user_tables.n_live_tup`은 오래된 통계여서 TEST `source_record`가 47로 보였지만
실제 행 수는 57,625였다. 작업 중 TEST 노드 수를 "약 38.2만"이라고 잘못 말한 적이 있으며,
레이블별 합계는 474,998이다.

## 수행 내용

1. **TEST Neo4j 덤프**: `neo4j-test`를 중지하고 같은 이미지와 데이터 볼륨의 임시 컨테이너에서
   `neo4j-admin database dump neo4j`를 실행한 뒤 컨테이너를 다시 시작했다. 덤프 크기
   104,719,306 바이트, SHA-256 `1a7833d5…e285`.
2. **PROD Neo4j 백업**: NAS `neo4j`를 중지하고 임시 컨테이너로 덤프했다.
   NAS `/volume3/Birds-Nest/backups/robingraph-deploy/neo4j-migration-20261009/prod-pre-migration-20261009.dump`(92,939,227 바이트)로 보관한다. 처음에는 `…/neo4j/backups/`에 두었다가 같은 날 이 위치로 옮겼다.
   첫 시도는 백업 폴더 쓰기 권한 때문에 덤프가 생성되지 않았고(PROD는 즉시 재시작),
   폴더를 `chmod 777`로 열어 재시도해 성공했다.
3. **덤프 전송**: `scp`가 실패(`Connection closed`)해 `ssh … "cat > file" < dump`로 전송했다.
   NAS 쪽 SHA-256이 로컬과 일치했다.
4. **PROD Neo4j 복원**: PROD를 중지하고 `neo4j-admin database load neo4j --overwrite-destination=true`로
   덮어쓴 뒤, 5.26(커널 V5_25) 스토어를 2026.08(V2026_08)로 `neo4j-admin database migrate`했다.
   두 명령 모두 종료 코드 0이었고 이후 컨테이너를 시작했다.
5. **PostgreSQL**: TEST의 `ingest` 스키마를 `pg_dump --schema=ingest --no-owner --no-privileges --clean --if-exists`로 떠서
   PROD `robingraph` DB에 `psql --single-transaction -v ON_ERROR_STOP=1`로 복원했다.
6. **API 재시작과 검증**: `robingraph-api`(PROD)를 재시작하고 검증 스크립트를 실행했다.

## 검증 결과 (실제 DB/API)

| 항목 | 결과 |
|---|---|
| PROD Neo4j 노드 / 관계 | 474,998 / 543,637 (TEST와 일치) |
| PROD Neo4j 인덱스 | LOOKUP 2, FULLTEXT 1, VECTOR 1, RANGE 18 모두 ONLINE; 제약조건 17개 |
| PROD PG | `source_record` 57,625 / `ingestion_run` 33 / `source_release` 10 / `source_dataset` 13 / `outbox_event` 0 (TEST와 일치) |
| `scripts/verify_api_deployment.py` (PROD 컨테이너 내부, `--lineage-name 대륙검은지빠귀 --expected-scientific-name 'Turdus mandarinus'`) | `passed: true`, health·openapi·lineage 모두 200, 구조·스키마·응답 드리프트 없음 |

모의(mock) 검증은 없었다. 위 결과는 모두 실제 DB와 API에 대한 것이다.
단위 테스트 스위트는 실행하지 않았다(코드 변경이 없다).

## 변경 전후 동작

- 변경 전: PROD Neo4j에는 AviList 분류(약 16.2만 노드)만 있었고 PG `ingest`는 비어 있었다.
- 변경 후: PROD가 TEST와 같은 내용(형질 근거, 근거 단위, 한국어 이름, 관찰, 문헌 Chunk, 벡터 인덱스 포함)을 갖는다.
- 저장소 코드, 설정, 배포 파일은 바꾸지 않았다. 이 문서만 추가했다.

## 중단 시간

- PROD Neo4j: 백업 2회(첫 시도 실패 포함)와 복원 1회로 총 3회 중지.
- TEST Neo4j: 덤프 시 1회 중지.
- 모두 작업 후 재시작했다. 각 중단은 수 초에서 수십 초 규모이며 정확한 시간은 측정하지 않았다.

## 설계 논의

관찰과 문헌을 Neo4j가 아닌 RDB에 두자는 의견이 있었다. `deployment-profile.md`에도
TimescaleDB로 확장하는 방향이 있다. 그러나 현재 API는 관찰(`operational_neo4j.py`)과
문헌 Chunk의 벡터·전문 검색을 Neo4j에서 읽고, TEST 기준 Observation 116, Document 2,
Chunk 4로 양이 적어 이전 이득이 작다. 이번 이관에서는 구조를 바꾸지 않고 그대로 옮겼다.
RDB 이전은 규모가 커졌을 때 검색 경로 포함 별도 작업으로 다룬다.

## 남은 한계와 후속 사항

- 배포·커밋 정보: 코드 배포나 git 커밋은 없다. 이 문서는 아직 커밋하지 않았다.
- 브라우저에서의 실제 채팅·관찰 조회 스모크 테스트는 하지 않았다(`verify`는 health와 분류 계통까지만 확인).
- 롤백 수단: `prod-pre-migration-20261009.dump`로 Neo4j만 복구할 수 있다. 이관 전 PG `ingest`는 빈 상태라 따로 백업하지 않았다.
- 정리 완료(후속 작업): 임시 `chmod 777` 폴더와 TEST 덤프는 `/volume3/Birds-Nest/backups/robingraph-deploy/neo4j-migration-20261009/`(`test-dump-20261009.dump`)로 옮기고 빈 `neo4j/backups/`는 제거했다. 상세는 NAS 임시 파일 이동 기록 참조.
- 보안: 작업 중 `.env` 마스킹 패턴이 `NEO4J_PASSWORD`를 놓쳐 TEST Neo4j 비밀번호가 대화 기록에 노출됐다.
  이 값은 NAS 로그인 비밀번호와 같으므로 교체를 권고했다. 이 문서에는 인증 정보를 적지 않았다.
- 같은 이관을 반복할 수 있는 스크립트는 만들지 않았다.
