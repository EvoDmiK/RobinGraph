# 2026-10-06 전체 종 근연 관계 우선 비교

## 변경

오리 두 종의 특별 동점 규칙을 제거하고 활성 전체 종에 `taxonomy-phylogeny-ecology-v2`를 적용했다. 같은 속·같은 과를 우선하며, 같은 분류 범위에서 검증된 계통 합성 공통 조상 관계를 생태 점수보다 먼저 반영한다. 자료가 없는 종은 분류 자료로 표시하며 멀다고 단정하지 않는다. 표시 점수는 분류·생태 일치 점수로 명시했다.

Aves 1.6 / Clements2025 phylogeny-only 원본과 연구별 지원 주석을 고정 파일·해시로 검증했다. 실제 활성 AviList 11,131종의 taxon ID·학명·영어 이름을 공식 Extended XLSX와 대조한 뒤 Avibase 종 개념을 crosswalk에 연결했다. 9,518종에 근거가 적용되며 나머지 1,613종은 분류 자료로 표시한다. 분류 제약 연구 ot_2019/ot_2770, 추정 추가 종, 연구 tip 근거가 없는 종은 계통 근거로 쓰지 않는다. 원 연구 출처와 충돌 정보도 전달한다.

## 검증

- Python 최초 실행: 548개 중 508 통과, 외부 통합 환경 조건에 따른 40 skipped. 아래 NAS 재접속 검증에서 548개 전체 통과·0 skipped를 확인했다.
- 프런트엔드 전체: 125 tests, pass 125, fail 0.
- 분류판·개념집합·taxon ID·학명 변경 시 기존 계통 근거 미적용.
- 파서 중복·미완성·다중 root·미지원 branch length 거부, polytomy 유지.
- 공식 XLSX와 활성 종 과학명/영문명/sequence 불일치 및 중복 거부.
- 고유 Avibase를 통한 공식 속 이동 허용; 식별자가 다른 분할·통합·중복 거부.
- 비분류 연구 근거 없는 조상 분기가 순위를 높이지 않음.
- synthetic topology에서 오리·해오라기·박새 등 동일 규칙으로 생태 점수보다 계통 근거 우선.
- 실제 고정 계통수에서 흰뺨검둥오리–청둥오리 관계가 고방오리보다 안쪽 공통 조상; 해오라기–Nankeen Night Heron 관계가 왜가리보다 안쪽 공통 조상.
- 실제 전체 후보 조사: 오리, 해오라기, 박새, 매류, 비둘기에서 서로 다른 계통 관계 순위 확인.
- graphify AST update 완료; git diff --check 통과.

## 협업

Orca run `run_ed90d2e734cb`: Claude 원본/지원 주석/분류 제약 연구 감사, GPT 고정 데이터 파서·종 개념 연결·runtime·검증 구현, Antigravity 독립 순위 정책 검토. 원본·적용 범위·재생성 명령은 `docs/phylogenetic-relations.md`에 기록했다. n8n 새 스케줄은 등록하지 않고 고정 공개 파일의 재현 가능한 수집 경로를 사용했다.

## NAS TEST 배포 및 공개 응답

- Code commit `595954e246e7ddd75550da3832d725b7b11d288a`, origin/dev push 완료.
- NAS release `/home/kimdove/RobinGraph-phylogeny-595954e`, image `robingraph-api:test-phylogeny-595954e`; OCI revision과 실제 TEST 컨테이너 이미지 일치 확인.
- Archive SHA-256 `980ecd5d87b2b6bb10068b513293ac870f026b2db29a37587b05113ed903ea81`; NAS archive/manifest 검증 완료.
- TEST preflight/update/verify 완료, health status ok/neo4j/test. PROD 변경 없음.
- 공개 https://robingraph-test.dove-nest.com : 배포 검증기 passed=true, OpenAPI/응답 계약 일치.
- `/v1/taxa/similar` 실제 5종 요청 모두 method v2, 전체 후보 11,130, coverage 9,518 확인.
- 흰뺨검둥오리: 청둥오리 → Indian Spot-billed Duck → Philippine Duck. 첫 두 종은 같은 계통 공통 조상 단계이며 서로의 표시 우열은 생태/학명 규칙으로 결정.
- 해오라기: Nankeen Night Heron 먼저 표시, 공통 조상 연구 2개. 같은 속의 계통 자료 없는 멸종 종은 분류 근거만 표시.
- Parus major: Parus cinereus(박새,80점) → Parus monticolus(작은노랑배박새,90점) → Pseudopodoces humilis. 생태 가점보다 계통 근거가 앞섬을 실제 응답에서 확인.
- Accipiter nisus: Accipiter rufiventris → A. striatus → A. madagascariensis.
- Columba livia: Columba rupestris(낭비둘기) → C. leuconota → C. oenas(분홍가슴비둘기).
- `/v1/chat` 흰뺨검둥오리 관련 종 질문: v2와 청둥오리 첫 후보, 규칙 설명·일치점수·근거 반환 확인.
- 공개 `/static/chat.js` SHA-256 `5c5a2bf4a6ac5f36dc7b951acbfc1b52697eeb8474e3a737149a3ba5d65ce6c1`가 현재 커밋 파일과 일치.
- Obsidian MCP 문서: `Work/RobinGraph/2026-10-06-전체종-근연관계우선-계통근거-NAS배포.md` 생성 및 Work/index 링크 추가.

## 독립 검토 종료

Antigravity 검토 보고 수신 및 작업 정상 종료. 같은 속·과의 분류 범위를 먼저 지키고 범위 안에서 계통 근거를 생태 점수보다 앞세우는 정책, 계통 자료가 없는 같은 속 종을 먼 분류군보다 아래로 보내지 않는 처리 방향을 독립 검토에서도 확인했다. 보고의 추가 제안인 연구 수에 따른 동점 우열과 미지원 합성 분기에 의한 순위는 적용하지 않았다. 연구 수는 통계적 신뢰도/진화 거리와 같지 않으며 지원 근거 없는 분기는 순위를 높이지 않아야 한다. 검증된 투영 계통 근거의 정확한 적용 수는 위의 9,518종/9,428 내부 조상이다.

Claude·GPT·Antigravity 모든 dispatch가 succeeded로 종료됐고 회수 가능한 작업 세션을 정리했다. 사용자가 인계받거나 기존 세션을 재사용한 작업 창은 Orca의 보존 상태를 따른다.

## NAS 재접속 후 전체 통합 테스트

- NAS 접속 복구 후 기존 TEST PostgreSQL과 Neo4j 설정을 확인했다. 테스트 의존성과 tracing 추가 의존성을 모두 설치했다.
- 모든 실행 스위치(`ROBINGRAPH_NEO4J_INTEGRATION_TESTS`, `ROBINGRAPH_POSTGRES_INTEGRATION_TESTS`, `ROBINGRAPH_NAME_RELATIONS_INTEGRATION_TESTS`)를 `1`로 설정하고 `uv run --locked --extra test --extra tracing python -m unittest discover -s tests -v`와 같은 전체 테스트 검색을 실행했다.
- 최종 결과: **548 실행, 548 통과, 실패 0, 오류 0, 건너뛰기 0**. 실행 시간 28.249초. 기존에 건너뛴 Neo4j 20개, n8n Cypher 2개, PostgreSQL 9개, 이름 관계 1개, MLflow/Google GenAI 8개를 모두 포함한다. tracing 테스트는 SDK를 설치한 로컬 모의 실행이며 외부 LLM 호출 검증은 아니다.
- 기존 TEST Neo4j에는 삭제·재적재 대상인 Fixture 영역에 논문 자료도 있어 일회용 Neo4j 컨테이너를 별도로 사용했다. PostgreSQL은 기존 TEST DB의 별도 스키마 `ingest_test_20261006_check40`를 사용했다.
- 실제 실행에서 이름 관계 통합 테스트의 누락된 `source_release`·`policy_status`를 보완했다. 단일 종 통칭의 직접 답변과 다종 통칭·가축형의 선택 요청을 구분해 검증하고, 다음 분류판 활성화 후 실제 관계 조회도 확인했다. 서비스의 조회 보호 조건은 유지했다.
- 검증 후 기존 Fixture 노드 555개·그중 논문 노드 168개가 유지됨을 확인했다. 일회용 컨테이너·볼륨과 별도 PostgreSQL 스키마를 삭제했다. 수정 범위는 테스트와 검증 문서이며 서비스 재배포는 필요하지 않다.
