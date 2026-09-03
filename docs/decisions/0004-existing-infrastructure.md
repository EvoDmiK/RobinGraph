# ADR-0004: 보유 인프라의 MVP 적용 범위

- 상태: Proposed
- 작성일: 2026-09-03

## 결정

MVP의 동기 요청 경로에는 Neo4j, Jina-embeddings-v3 API, HermesAgent의 gpt-5.6-sol만 사용한다. FastAPI가 세 서비스를 조정한다.

- n8n은 Python ingest CLI를 예약·호출하고 실패를 알린다.
- Prometheus/Grafana는 애플리케이션과 ingest 지표를 수집·표시한다.
- MLflow는 오프라인 검색·생성 평가에 사용한다.
- TimescaleDB, Redis, RobinGraph 전용 PostgreSQL은 초기 요청 경로에서 제외한다.

## 이유

이미 설치된 서비스라도 요청 경로에 추가하면 장애 지점, 데이터 동기화, 테스트 범위가 늘어난다. 현재 요구는 Neo4j 하나로 충족되며, 나머지 도구는 측정된 병목이나 명확한 운영 역할이 있을 때 연결할 수 있다.

## 확장

- 관찰 100만 건 또는 시간 집계 병목: TimescaleDB를 Observation 원장으로 검증
- 반복 요청과 모델 API 지연: Redis cache 검증
- 관계형 control table 요구: 기존 PostgreSQL 사용
- 실험 조합 증가: MLflow 기록을 필수 gate로 승격

세부 연결과 metric은 `docs/deployment-profile.md`를 따른다.

## 하드웨어 배치

FastAPI, Jina API, Neo4j live store는 Mac mini M4 32GB에 둔다. Ugreen NAS 2800 16GB에는 원본·staging·백업과 n8n, Prometheus, Grafana, MLflow를 둔다. TimescaleDB·Redis·RobinGraph 전용 PostgreSQL은 초기 애플리케이션 요청에서 사용하지 않는다.

Mac mini의 상시 운영이 불가능한 경우에는 실제 가용성 요구와 NAS 메모리 사용량을 측정한 뒤 Neo4j 위치를 재검토한다.
