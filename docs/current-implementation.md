# RobinGraph 현재 구현 상태

- 상태: In progress
- 기준일: 2026-09-03
- 범위: 합성 fixture 기반의 첫 실행 가능한 수직 슬라이스

## 1. 완료된 범위

현재 구현은 실제 외부 조류 데이터가 아닌 결정적 synthetic fixture를 사용한다. fixture는 10개 Taxon, 허용 Observation 100건, 허용 Document 2개, 허용 Chunk 4개, 정책 차단 입력과 15개 gold 질문으로 구성된다.

| 영역 | 구현 내용 | 검증 결과 |
|---|---|---|
| Fixture 생성 | 고정 timestamp, ID, manifest SHA-256을 생성 | 재생성 가능 |
| Staging 검증 | provenance, 날짜, 좌표, 수량, 민감도, 문서/Chunk 필드 검사 | 형식 오류와 정책 필터 분리 |
| Source registry | JSON Schema 및 Python validator | 잘못된 source 설정 차단 |
| Policy filter | `allowed`만 retrieval corpus에 포함 | `denied`, `review_required` 제외 |
| 이름 해소와 답변 | 한국어·영어·학명 exact match, 모호 이름 clarify, 근거 없는 질문 abstain | gold 질문 15/15 통과 |
| Citation validation | 존재하는 허용 evidence ID만 인용 | 민감 좌표와 금지 evidence 차단 |
| Neo4j fixture | idempotent constraint 및 graph projection | 실제 Neo4j Community에서 검증 |
| HTTP API | health, 근거 답변 endpoint | FastAPI contract 테스트 통과 |

## 2. 데이터와 보안 경계

- fixture의 `fixture-*` URL, 위치, 관찰값은 실제 관찰·출처가 아니다.
- `latitude_private`, `longitude_private`는 graph projection과 HTTP 응답에 포함하지 않는다.
- `denied`와 `review_required` 입력은 감사를 위해 fixture 입력에 존재하지만 graph, 검색, 생성 근거에는 포함하지 않는다.
- Neo4j URI, 사용자명, 비밀번호는 환경 변수로만 제공한다. `.env`는 Git에서 제외하고, `.env.example`에는 placeholder만 둔다.
- 실제 source adapter는 승인된 source registry, 라이선스 snapshot, 고정 release, 원본 manifest가 준비될 때까지 작성하지 않는다.

## 3. Neo4j 검증 결과

개발 database는 Neo4j Community `2026.07.1`에서 인증과 Bolt 연결을 확인했다. `load-neo4j-fixture`를 두 번 실행해도 fixture 수량은 변하지 않았다.

| 확인 항목 | 결과 |
|---|---:|
| Fixture Taxon | 10 |
| Fixture Observation | 100 |
| Fixture Document | 2 |
| Fixture Chunk | 4 |
| `latitude_private` 또는 `longitude_private` graph property | 0 |
| 정책 차단 observation | 0 |

적재되는 모든 fixture 노드는 `:RobinGraph:Fixture` 라벨을 가진다. schema constraint 이름도 `robingraph_` 접두사를 사용한다.

## 4. 실행 방법

Python 3.12 이상이 필요하다.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/generate_eval_fixture.py
.venv/bin/robingraph validate-fixture
.venv/bin/robingraph evaluate-fixture
.venv/bin/python -m unittest discover -s tests -v
```

Neo4j 연결 정보가 환경 변수에 있을 때 fixture 적재와 검증을 실행한다.

```sh
.venv/bin/robingraph verify-neo4j
.venv/bin/robingraph load-neo4j-fixture
.venv/bin/robingraph verify-neo4j-fixture
```

fixture API는 다음으로 실행한다.

```sh
.venv/bin/robingraph serve-fixture
```

`GET /health`는 `mode: fixture`를 반환한다. `POST /v1/answers`는 아래 형식의 질문을 받으며, `answer_text`, `evidence_ids`, `citations`, `disposition`, `warnings`을 반환한다.

```json
{"question": "2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"}
```

## 5. 검증 명령과 현재 결과

| 명령 | 현재 결과 |
|---|---|
| `robingraph validate-fixture` | 10 taxa, 100 allowed observations, 2 allowed documents, 4 allowed chunks |
| `robingraph evaluate-fixture` | 15/15 gold questions passed |
| `python -m unittest discover -s tests -v` | 12 tests passed |
| `robingraph verify-neo4j-fixture` | fixture count와 민감·정책 안전 조건 통과 |

## 6. 다음 운영 단계의 입력

실제 서비스 구현으로 전환하기 전에는 다음을 확정해야 한다.

- MVP 지역과 대상 사용자, 서비스의 상업성
- AviList v2025b와 NIBR 이용 조건에 대한 최종 분류·국명 정책
- GBIF의 선택 dataset, DOI, 고정 release, 최소 필드와 라이선스
- 민감종 원좌표 보관본과 공개 일반화 규칙
- 문헌별 full text, Chunk, embedding 허용 상태
- HermesAgent와 Jina API의 endpoint, 인증, 구조화 출력, token usage, embedding dimension/task/normalization 계약

운영 소스가 확정되면 fixture 전용 repository를 source adapter, Neo4j retrieval, Jina embedding, HermesAgent structured generation으로 교체한다. API의 provenance와 citation validation 계약은 유지한다.
