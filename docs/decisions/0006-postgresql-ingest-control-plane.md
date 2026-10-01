# ADR-0006: PostgreSQL ingestion control plane

- 상태: Accepted
- 작성일: 2026-09-22
- 선행 결정: `0001-primary-database.md`, `0004-existing-infrastructure.md`

## 맥락

현재 n8n 워크플로는 `SourceRecord`, `SourceDataset`, `IngestionRun`, `IngestState`, quarantine과 도메인 그래프를 하나의 Neo4j 저장소에 직접 기록한다. 배치 중간 실패는 결정적 ID와 `MERGE`, 최종 count 검증, active-release 포인터 전환으로 격리하지만, 원본 레코드와 실행 이력을 그래프 projection과 독립적으로 복구하거나 재생할 수 없다.

production과 test는 같은 PostgreSQL 서버를 사용하되 각각 전용 데이터베이스와 로그인 역할로 분리되어 있다. 기존 인프라 결정도 관계형 control table이 필요해지면 PostgreSQL을 사용하도록 열어 두었다.

## 결정

PostgreSQL의 `ingest` 스키마를 수집 control plane의 system of record로 사용한다. 다음 데이터는 PostgreSQL이 소유한다.

- source dataset과 불변 release
- 원본 source record와 판본·supersession
- ingestion run 상태와 manifest/count
- quarantine 발생·해결 이력
- pipeline별 active release 포인터
- 향후 도메인 이벤트 전달을 위한 transactional outbox

Neo4j는 검색과 관계 탐색을 위한 도메인 projection으로 유지한다. `SourceRecord`, `SourceDataset`, `SourceRelease`, `IngestionRun`, quarantine 및 한국어 pipeline activation state는 Neo4j에 복제하지 않는다. 도메인 노드는 PostgreSQL 원본을 추적할 수 있도록 `dataset_id`, `source_record_ids`, `policy_status`만 보유한다. 한국어 이름 읽기 경로는 PostgreSQL에서 활성·허용된 dataset ID를 가져와 Neo4j 쿼리에 parameter로 전달한다.

n8n은 수집 예약·호출·알림을 담당한다. 긴 SQL이나 Cypher를 n8n 노드 안에 새로 추가하지 않고, 실제 transaction과 projection 규칙은 버전 관리되는 Python 코드가 소유한다.

## 격리와 마이그레이션

| 환경 | 데이터베이스 | 역할 | 스키마 |
|---|---|---|---|
| production | `robingraph` | `robingraph_app` | `ingest` |
| test | `robingraph_test` | `robingraph_test_app` | `ingest` |

마이그레이션은 forward-only이며 checksum과 transaction-scoped advisory lock으로 보호한다. 자동 테스트와 shadow projection은 test 데이터베이스만 사용한다. production에는 별도 적용 확인 전 마이그레이션하지 않는다.

## 단계적 전환

1. PostgreSQL 스키마와 설정·검증 명령을 추가하고 test DB에서 검증한다.
2. transaction repository와 generic outbox primitive를 구현한다.
3. Korean vernacular pipeline을 test에서 실행하고 SourceRecord가 PostgreSQL에만 저장됨을 검증한다.
4. AviList/EltonTraits, AVONET, GBIF operational 순으로 전환한다.
5. 모든 소스가 parity 검증을 통과한 뒤 n8n의 직접 Neo4j control-plane 쓰기를 제거한다.

## 결과와 제약

- PostgreSQL commit과 outbox insert는 하나의 transaction이어야 한다.
- SourceRecord outbox event와 Neo4j projector를 제공하지 않는다.
- drift 검출과 outbox replay 도구 없이 production source를 cutover하지 않는다.
- 기존 Neo4j 데이터는 즉시 삭제하지 않는다. shadow/parity 기간에는 읽기 호환성을 유지한다.
- n8n이 Python control plane을 호출할 네트워크/API 경계와 outbox 보존 기간은 다음 구현 단계에서 확정한다.
