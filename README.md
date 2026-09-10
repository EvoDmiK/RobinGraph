# RobinGraph

그래프 데이터베이스와 LLM을 이용해 근거가 확인되는 조류 정보를 제공하는 GraphRAG 프로젝트입니다.

합성 fixture로 정책 필터·출처 추적·답변 검증을 실행하고, 같은 데이터를 실제 Neo4j에 적재해 검색할 수 있다. 실제 Jina의 512차원 임베딩을 Neo4j에 저장하고 전문·벡터 결합 검색과 출처 반환까지 확인했다. NAS n8n이 GBIF 한국 조류 관찰 데이터를 직접 수집·검증해 Neo4j에 적재하는 경로도 실제 실행으로 검증했다. AviList 분류·EltonTraits 식성·체중과 AVONET 형태 측정치·서식 환경을 수집하는 두 n8n workflow를 제공한다. 메모리 제한을 피하는 검증 배치 로더로 실제 AVONET 11,009종과 128,331개 형질 claim까지 NAS Neo4j에 적재했다. HermesAgent 답변 생성은 후속 단계다.

- [시스템 설계](docs/system-design.md)
- [2026-09-04 작업 기록](docs/work-log/2026-09-04.md)
- [2026-09-07 작업 기록](docs/work-log/2026-09-07.md)
- [2026-09-08 작업 기록](docs/work-log/2026-09-08.md)
- [2026-09-09 작업 기록](docs/work-log/2026-09-09.md)
- [2026-09-10 작업 기록](docs/work-log/2026-09-10.md)
- [외부 데이터 소스 조사](docs/data-source-decision-input.md)
- [종 정보 수집 포인트와 평가](docs/collection-points.md)
- [n8n 종별 분류·생태·형태 정보 수집](docs/n8n/species-information-ingest.md)
- [데이터 계약](docs/data-contracts.md)
- [구현 준비 체크리스트](docs/implementation-readiness.md)
- [보유 인프라 적용안](docs/deployment-profile.md)
- [기술 의사결정 기록](docs/decisions/)
- [평가 fixture와 gold 질문](docs/evaluation.md)
- [현재 구현 상태](docs/current-implementation.md)
- [개발환경과 자동 테스트](docs/development.md)
- [다음 구현 배치와 담당 작업](docs/next-implementation-batch.md)
- [Jina 임베딩 어댑터](docs/embedding-adapter.md)
- [문헌 하이브리드 검색](docs/hybrid-retrieval.md)
- [n8n 운영 수집 워크플로우와 실행 런북](docs/n8n/README.md)
- [NAS Docker·Nginx Proxy Manager 배포 런북](docs/nas-deployment.md)
- [기여자와 AI 협업 기록](CONTRIBUTORS.md)

## 기여자

RobinGraph는 프로젝트 소유자 김둘기와 AI 개발 도구인 [OpenAI Codex](https://github.com/apps/chatgpt-codex-connector), [Anthropic Claude](https://github.com/apps/claude)의 협업으로 개발하고 있습니다. 역할과 Git 커밋 표기 기준은 [CONTRIBUTORS.md](CONTRIBUTORS.md)에 기록합니다.

## Fixture 검증

개발환경은 `.python-version`의 Python 3.12.13과 `uv.lock`으로 통일한다. [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치한 뒤 아래 명령을 Windows PowerShell, macOS, Linux에서 동일하게 실행한다. uv가 Python과 `.venv`를 준비하므로 가상환경 활성화는 필요 없다.

```sh
uv sync --locked --extra test
uv run --locked robingraph validate-fixture
uv run --locked robingraph evaluate-fixture
uv run --locked --extra test python -m unittest discover -s tests -v
```

커밋된 fixture를 먼저 검증한다. 재생성 비교는 테스트가 임시 폴더에서 수행하므로 원본 손상이나 줄바꿈 문제를 덮어쓰지 않는다. 기존 Windows 작업공간의 CRLF 복구와 의도적인 fixture 변경 방법은 [개발 가이드](docs/development.md)를 참고한다.

Neo4j 연결 정보는 Git에 넣지 않고 로컬 `.env` 또는 환경 변수로만 제공한다. CLI는 실행 디렉터리의 `.env`를 읽으며, 명시적으로 설정한 환경 변수가 같은 키를 우선한다. `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`를 설정한 뒤 아래 명령으로 합성 fixture를 graph에 적재하고 안전 조건을 검증한다.

```sh
uv run --locked robingraph verify-neo4j
uv run --locked robingraph load-neo4j-fixture
uv run --locked robingraph verify-neo4j-fixture
```

합성 fixture API는 다음 명령으로 실행한다. 이 API는 실제 외부 데이터나 LLM을 사용하지 않으며, `GET /health`가 `mode: fixture`를 반환한다.

```sh
uv run --locked robingraph serve-fixture
```

Neo4j에 fixture를 적재한 뒤 실제 그래프 조회를 사용하는 API 또는 단일 질문 CLI를 실행할 수 있다. `/health`의 `mode`는 `neo4j`다.

```sh
uv run --locked robingraph serve-neo4j
# 또는 API 서버 없이 질문 한 건 실행
uv run --locked robingraph ask-neo4j --question "Anas zonorhyncha의 한국어 이름은?"
```

두 모드 모두 현재는 작은 합성 데이터에 대해 이름·장소·날짜를 해소하고 근거로 답변을 구성한다. Neo4j 모드는 매개변수가 바인딩된 Cypher로 조회하며 벡터 검색이나 LLM 생성은 아직 사용하지 않는다. DB 통합 테스트 실행법은 [개발 가이드](docs/development.md#neo4j-통합-테스트)를 참고한다.

## 문헌 청크 검색

위 질문 API와 별도로, 문헌 검색 결과의 본문·순위·출처·라이선스를 CLI와
`POST /v1/search`에서 JSON으로 확인할 수 있다. 먼저 현재 버전의 loader로
fixture를 적재한 뒤 전문 검색 인덱스를 준비한다.

```sh
uv run --locked robingraph load-neo4j-fixture
uv run --locked robingraph index-neo4j-fixture
uv run --locked robingraph search-neo4j --question "fixture 호수" --limit 5
```

이 기본 경로는 Jina를 호출하지 않는다. 키워드 검색은 한국어 형태소를 해석하지 않으므로 일부 표현을 놓칠 수 있다.

`.env.example`의 `ROBINGRAPH_JINA_*` 변수를 로컬 `.env` 또는 환경 변수로 설정하면 다음 명령으로 허용된 fixture 청크를 임베딩하고 벡터 검색을 함께 사용할 수 있다. 제공된 API 문서에 맞춰 BirdsNest 프로필과 512차원을 반영했다. `.env`는 CLI가 자동으로 읽고 Git에서는 제외된다. API 키는 `.env` 또는 secret store에서만 제공한다. [연결 검증 기록](docs/embedding-adapter.md)을 참고한다.

```sh
uv run --locked robingraph index-neo4j-fixture --embeddings
uv run --locked robingraph search-neo4j --question "물가에 사는 새에 대한 기록" --hybrid --limit 5
```

`--embeddings`는 HTTP 요청과 Neo4j 벡터 쓰기를 수행한다. 동일 프로필의 전체 허용 청크 집합으로 벡터를 갱신하므로 부분 배치 갱신용 명령이 아니다. `--hybrid`는 읽기 전용 검색과 질문 임베딩 요청을 수행하며, 벡터를 사용할 수 없으면 `warnings`에 이유를 표시한다. 현재 이 경로는 근거 검색까지 제공하며 LLM 답변 생성은 포함하지 않는다.

`serve-neo4j`의 Swagger(`/docs`)에서는 `mode`를 `fulltext` 또는 `hybrid`로
선택한다. 기본값은 `fulltext`이며 이때 Jina를 호출하지 않는다.

```sh
curl -X POST http://127.0.0.1:8000/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"question":"호수와 하천에서 관찰된 물새","mode":"hybrid","limit":5}'
```

응답의 `requested_mode`는 요청값, `mode`는 실제 결과에 사용된 모드다. 임베딩
호출이 일시적으로 실패하면 전문 검색으로 폴백하고 `warnings`에 이유를 남긴다.
`serve-fixture`에서도 OpenAPI 계약은 보이지만 검색 호출은 HTTP 503을 반환한다.

## 운영 GBIF 관찰 조회

n8n 운영 workflow가 적재한 실제 GBIF `BirdTaxon`·`Observation`은
`serve-neo4j`의 `GET /v1/observations`에서 조회한다. GBIF taxon key, 학명,
장소명, 관찰일 범위와 pagination을 조합할 수 있다.

```sh
curl "http://127.0.0.1:8000/v1/observations?scientific_name=Anas%20zonorhyncha&observed_from=2026-09-01&limit=25"
```

응답은 `mode: operational`, `data_source: gbif`, `fixture_only: false`를 명시하고,
각 관찰에 taxon·place·허용된 media·EvidenceUnit·원본 GBIF URL·dataset URL·
허용 라이선스를 포함한다. `SourceRecord → SourceDataset → License`의 허용 provenance 체인이
완전한 레코드만 반환한다. `sensitivity: generalized`인 관찰은 저장된 공개 좌표도
API에서 숨기며 `coordinate_disclosure: withheld`와 경고를 반환한다.

이 endpoint는 구조화된 관찰 검색이다. 문헌 전문·벡터 검색인 `/v1/search`와
Hermes 기반 자연어 답변 생성은 별도 경로다. `serve-fixture`에서는 계약만
노출하고 호출은 HTTP 503을 반환한다.

한국어 문헌 검색 품질은 fixture의 별도 5개 gold 질문으로 비교한다. `all`은 전문, 벡터, RRF 결합 검색의 recall@k, MRR, 평균/p95 지연시간과 정책 제외 결과를 JSON으로 출력한다.

```sh
uv run --locked robingraph evaluate-search-neo4j --mode all --limit 3
```
