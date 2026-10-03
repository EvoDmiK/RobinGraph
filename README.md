# RobinGraph

그래프 데이터베이스와 LLM을 이용해 근거가 확인되는 조류 정보를 제공하는 GraphRAG 프로젝트입니다.

종의 분류·생태·형태 정보, 사진과 문헌 근거를 한국어 대화 화면에서 확인할 수 있습니다. 현재는 NAS에서 운영하는 개인 프로젝트이며, 실제 종 데이터가 준비된 TEST 환경에서 기능을 검증하고 있습니다.

## 현재 제공 기능

- **구조화된 종 설명**: 기본 정보, 외관적 특징, 생태와 재미있는 사실을 확인된 자료와 출처를 바탕으로 표시합니다. 자료가 없는 내용은 추측하지 않습니다.
- **조류 도감 카드**: 간단한 설명과 함께 카드 열기 버튼을 제공합니다. 앞면에는 사진과 핵심 특성, 뒷면에는 전체 특성과 출처·라이선스를 담습니다. 사진은 버튼으로 이동하고 출처는 펼치거나 접을 수 있습니다.
- **수집형 카드 표현**: 서식 환경별 문양과 자료에 기록된 IUCN 등급별 색상·광택을 적용합니다. 앞뒤 전환에는 입체 회전, 빛 반사와 작은 반동 효과가 있으며 움직임 줄이기 설정을 존중합니다.
- **그래프 관계 탐색과 비교**: 설명창에서 같은 속·과의 다른 새를 찾아 특성과 출처를 비교합니다. 관련 목록은 한국어 이름이 있는 종만 이름순으로 최대 12종씩 표시합니다. 같은 분류에 속한다는 관계이며 진화적 거리나 가장 가까운 종을 의미하지 않습니다.
- **독립된 새 비교 답변**: 같은 속·과의 새를 비교하면 원래 설명을 유지하고 별도 말풍선에 두 종의 특성·출처·카드 버튼을 표시합니다.
- **먹이 생태와 사진 상태**: 출처로 확인한 먹이 항목을 다중 아이콘으로 표시하고, 사진이 없거나 조회·로딩이 실패해도 설명과 카드를 제공합니다. [후속 작업·표시 정책](docs/graph-exploration-expansion.md)
- **아종 카드**: 설명창에서 소속 종의 아종 목록을 그래프로 조회하고, 선택한 아종의 카드·분류·검토된 분포 설명을 제공합니다. 부모 종 자료는 별도 ‘종 수준 참고 정보’로 표시합니다. [조회·자료 정책](docs/subspecies-cards.md)
- **통칭·가축형 관계 탐색**: 검토된 관계 자료를 적재하면 `닭`, `거위`, `칠면조`, `뱁새`, `앵무새` 등 통칭·별칭·가축형 질문에 관계·후보·출처를 안내합니다. 한 종으로 확인되는 통칭은 연결된 종의 설명·카드를 바로 준비하고, 여러 종이면 후보를 선택합니다. 가축형은 관련 야생종 자료와 구분합니다. 설명창에서 이름 관계를 역방향으로도 탐색합니다. [조사 목록](docs/name-relations-coverage.md) · [적재·검증 방법](docs/name-relations.md)
- **이름 표시**: 한국어 이름을 우선하고, 없으면 AviList의 영어 이름을 표시합니다. 학명도 별도로 유지하며 이름을 임의 번역하지 않습니다. 검토한 원본 이름 충돌은 근거를 남겨 보정합니다.
- **분류·관찰·문헌 조회**: AviList 분류 계보, GBIF 관찰 기록, 문헌 전문·벡터 결합 검색을 제공합니다. Gemini가 설정된 문헌 경로에서는 검색 근거로 답변을 생성하고 근거 ID를 검증합니다.

[TEST 대화 화면](https://robingraph-test.dove-nest.com/chat)에서 `청둥오리에 대해 알려줘` 또는 `흰뺨검둥오리에 대해 알려줘`를 입력하고, 카드의 `출처 보기 ↻` 버튼으로 뒤집기 효과를 확인할 수 있습니다. 대화 기록은 현재 창에서만 유지됩니다.

TEST에는 활성 종 데이터가 있습니다. PROD에도 같은 코드를 배포했지만 활성 종 데이터가 아직 없어, 실제 종 질문 검증과 PROD의 서비스 상태·정적 파일 검증을 구분합니다.

AviList 분류, EltonTraits 식성·체중, AVONET 형태·서식 환경과 GBIF 관찰 기록은 수집 workflow와 검증 로더를 통해 적재합니다. Wikidata는 승인된 한국어 이름의 보충 자료로 사용합니다. Neo4j는 종과 자료의 관계를, PostgreSQL은 수집·활성 스냅샷 상태를 관리합니다. 문헌 검색에는 Jina의 512차원 임베딩과 Neo4j 전문·벡터 검색을 사용합니다.

## 문서

- [통합 대화 화면과 카드](docs/chat-ui.md)
- [분류 계보 API](docs/taxonomy-lineage-api.md)
- [시스템 설계](docs/system-design.md)
- [그래프 DB 스키마](docs/graph-database-schema.md)
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
- [NAS 배포 런북](docs/nas-deployment.md)
- [기술 의사결정 기록](docs/decisions/)
- [평가 fixture와 gold 질문](docs/evaluation.md)
- [PMC 실제 문헌 1편 TEST 적재 파일럿](docs/pmc-literature-pilot.md)
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

fixture 검증 경로는 작은 합성 데이터에 대해 이름·장소·날짜를 해소하고 규칙으로 답변을 구성한다. 실제 Neo4j 모드에서는 별도로 적재한 분류·형질·관찰·문헌 자료를 조회하며, Jina·Gemini 설정에 따라 문헌 검색과 근거 답변 생성을 사용한다. 활성 분류·한국어 이름 스냅샷은 PostgreSQL 수집 상태로 결정되므로 실제 종 조회에는 그래프 데이터와 수집 상태가 함께 필요하다. DB 통합 테스트 실행법은 [개발 가이드](docs/development.md#neo4j-통합-테스트)를 참고한다.

## 브라우저 채팅 UI와 API 경계

패키지에 포함된 한국어 채팅 UI는 `serve-fixture`와 `serve-neo4j` 모두에서
`/` 및 `/chat`으로 제공되고, JS·CSS 같은 정적 파일은 같은 origin의 `/static/`에
제공된다. 따라서 브라우저는 별도 API URL, 프록시, 토큰 또는 임베딩/Neo4j 자격 증명을
가질 필요 없이 상대 경로 `POST /v1/chat`를 호출한다. 관련 종 탐색과 비교는
같은 origin의 `GET /v1/taxa/related`와 `GET /v1/taxa/profile`을 사용한다. 배포 산출물에
`src/robingraph/api/static/index.html`과 관련 자산이 누락된 경우에도 API는 시작되며,
UI 경로만 세부 경로를 노출하지 않는 일반적인 HTTP 503을 반환한다.

프런트엔드는 `/v1/chat` 응답을 다음처럼 표시한다.

- `answer_text`는 서버가 근거 확인을 마친 본문이며, 클라이언트가 검색 결과나 모델 출력으로 보완·재작성하지 않는다.
- `disposition`이 `answer`이면 답변으로, `abstain`이면 답변 불가 안내로, `clarify`이면 추가 선택 질문으로 표시한다. 알 수 없는 값은 성공 답변으로 취급하지 않는다.
- `result.kind`에 따라 종 프로필·분류 계보·관찰·문헌 검색·추가 확인 화면을 구성한다. 각 결과에 포함된 출처 URL, 근거 ID와 라이선스를 표시하며 `warnings`도 함께 보여준다.
- 분류 결과에는 AviList 릴리스와 개념집합을 표시한다. 별도 `POST /v1/answers`는 기존 규칙 기반 답변 계약이며, `citations`, `taxonomy_release`, `data_cutoff`을 반환한다.

`POST /v1/search`는 문헌 청크 검색 계약이며 채팅 답변 생성 API가 아니다. 결과의
본문·점수·citation만으로 `answer_text` 또는 `disposition`을 만들어 내거나, `/v1/answers`
실패 시 그 결과를 채팅 답변처럼 표시해서는 안 된다. `GET /health`의 `mode`는 현재
`fixture` 또는 `neo4j` 백엔드를 운영 상태로 표시하는 용도이며, UI가 답변 내용을
추론하는 입력이 아니다.

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
설정된 검색 백엔드 자체를 사용할 수 없어 HTTP 503이 되는 경우에도
`{"detail":"Document search is temporarily unavailable."}`라는 고정 상세만
반환한다. 이 보안 처리로 상태 코드와 성공 응답 `DocumentSearchResponse` 스키마,
요청의 `mode`·`limit` 범위는 바뀌지 않으며, 공급자 오류·설정·토큰 같은 내부
상세는 응답에 포함하지 않는다.

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

이 endpoint는 구조화된 관찰 검색이다. 문헌 전문·벡터 검색은 `/v1/search`에서,
검색 근거를 사용한 자연어 답변은 `/v1/chat`에서 제공한다. `serve-neo4j`에
`GEMINI_API_KEY`를 설정하면 Gemini API가 근거 답변을 생성한다. 모델은
`ROBINGRAPH_GEMINI_MODEL`로 지정할 수 있다. `serve-fixture`에서는 계약만
노출하고 호출은 HTTP 503을 반환한다.

한국어 문헌 검색 품질은 fixture의 별도 5개 gold 질문으로 비교한다. `all`은 전문, 벡터, RRF 결합 검색의 recall@k, MRR, 평균/p95 지연시간과 정책 제외 결과를 JSON으로 출력한다.

```sh
uv run --locked robingraph evaluate-search-neo4j --mode all --limit 3
```
