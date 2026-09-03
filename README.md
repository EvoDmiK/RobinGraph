# RobinGraph

그래프 데이터베이스와 LLM을 이용해 근거가 확인되는 조류 정보를 제공하는 GraphRAG 프로젝트입니다.

합성 fixture를 이용한 첫 수직 슬라이스를 구현했다. 실제 외부 데이터 적재와 운영 서비스 연결은 데이터 소스·라이선스·민감좌표·모델 endpoint 결정 후 진행한다.

- [시스템 설계](docs/system-design.md)
- [외부 데이터 소스 조사](docs/data-source-decision-input.md)
- [데이터 계약](docs/data-contracts.md)
- [구현 준비 체크리스트](docs/implementation-readiness.md)
- [보유 인프라 적용안](docs/deployment-profile.md)
- [기술 의사결정 기록](docs/decisions/)
- [평가 fixture와 gold 질문](docs/evaluation.md)
- [현재 구현 상태](docs/current-implementation.md)

## Fixture 검증

프로젝트는 Python 3.12 이상을 기준으로 한다. 최초 한 번 가상환경을 만들고 editable 설치를 수행한다. 아래 명령은 합성 fixture 생성, 라이선스 정책 필터, 이름 해소, 인용 검증과 15개 gold 질문 평가를 실행한다.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/generate_eval_fixture.py
.venv/bin/robingraph validate-fixture
.venv/bin/robingraph evaluate-fixture
.venv/bin/python -m unittest discover -s tests -v
```

Neo4j 연결 정보는 Git에 넣지 않고 환경 변수로만 제공한다. `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`를 설정한 뒤 아래 명령으로 합성 fixture를 graph에 적재하고 안전 조건을 검증한다.

```sh
.venv/bin/robingraph verify-neo4j
.venv/bin/robingraph load-neo4j-fixture
.venv/bin/robingraph verify-neo4j-fixture
```

합성 fixture API는 다음 명령으로 실행한다. 이 API는 실제 외부 데이터나 LLM을 사용하지 않으며, `GET /health`가 `mode: fixture`를 반환한다.

```sh
.venv/bin/robingraph serve-fixture
```
