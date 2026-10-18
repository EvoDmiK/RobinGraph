## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## 작업 문서 작성 기준

- 사용자의 요청에 따라 작업 문서는 항상 상세하게 작성한다. 짧은 완료 요약만으로 대체하지 않는다.
- 요청 배경과 목표, 확인한 원인과 근거, 변경 전후 동작, 변경 파일과 구현 내용, 검증 방법과 실제 결과, 배포·커밋 정보, 남은 한계와 후속 사항을 기록한다. 해당하지 않는 항목은 그 이유를 명시한다.
- 테스트는 실제 실행한 범위·통과·실패·건너뛰기를 구분하고, 모의 검증과 실제 DB/API 검증을 구분한다. 확인하지 않은 결과나 배포 완료를 추정해 기록하지 않는다. 인증 정보는 문서에 포함하지 않는다.
- 저장소와 Obsidian에 같은 작업을 기록하는 경우 핵심 내용과 검증 결과를 일치시킨다. 채팅 완료 안내는 간결하게 하되 작업 문서의 상세함은 유지한다.


## 운영 배포 승인 (사용자 지시, 2026-10-09)

- 사용자가 결과를 확인하고 운영 반영을 명시적으로 승인하기 전에는 Production에 배포하지 않는다. 과거의 포괄적 배포 허용은 이 지시로 대체되었다.
- 구현·검증 및 TEST 배포까지 진행하고 결과를 제시한다. 일반적인 진행 요청이나 TEST 수정 요청을 운영 배포 승인으로 해석하지 않는다.
- 운영 컨테이너 재시작·이미지 교체·운영 DB 변경·롤백도 별도 승인 없이 수행하지 않는다.

## 에이전트 역할과 협업 지침 (2026-10-15)

### 프로젝트 목표와 판단 근거

- RobinGraph의 목표는 한국어로 조류의 분류·생태·형질·관찰·문헌을 탐색하고, 근거를 확인하며 도감 카드와 관계 비교로 이어지는 경험을 제공하는 것이다.
- README.md, pyproject.toml, src/robingraph/api/app.py, retrieval 모듈, api/static 자산과 2026-10-14 작업 기록을 근거로 아래 역할을 나눈다. 이는 현재 프로젝트에 대한 역할 배분이며 새로운 기능 요구사항이나 발견된 결함을 뜻하지 않는다.
- 자료 없는 내용과 검증되지 않은 한국어 이름을 생성하지 않는다. 부모 종·아종·유사 종의 근거를 혼용하지 않고, 보전 등급의 출처·평가 대상·연도를 구분한다. fixture 결과를 실제 종 데이터 검증으로 표현하지 않는다.

### Codex — 총괄·통합·TEST 환경 (dev-codex)

- Jenkins 배포 상태(2026-10-18): http://dove-jenkins/ 의 robingraph-mac16 agent, GHCR 인증, RobinGraph-TEST #2의 멀티 아키텍처 publish·TEST 배포·API 검증이 통과했다. TEST job은 활성·dev-codex 5분 polling이며 운영 RobinGraph-PROD는 비활성이다. 운영은 최신 성공 TEST artifact와 admin 명시 승인 이후에만 가능하며 기존 운영 승인 규칙을 유지한다. 실제 절차·한계는 docs/jenkins-deployment.md를 따른다.

- TEST 실행 위치(사용자 지시, 2026-10-17): 앱·이미지 빌드는 M4 16GB(192.168.219.97), TEST Neo4j·n8n은 32GB Mac(192.168.219.98), TEST PostgreSQL은 NAS(192.168.219.99)를 유지한다. 현재 TEST URL은 https://robingraph-test.dove-nest.com 이며 NAS 프록시가 16GB Mac:8000으로 연결한다. NAS TEST 앱은 이전 때 정지했으나 2026-10-18 재조회에서는 해당 컨테이너가 없다. 현재 롤백 기준은 Mac의 previous release·이미지다. 이후 일반 TEST 배포를 NAS 앱 재가동으로 해석하지 않는다.
- 16GB Mac의 실행 관리 경로는 /Users/kimdove/robingraph-test/manage.sh (start/status/stop/verify), current는 검증한 runtime release를 가리킨다. 다음 배포는 최신 snapshot을 ARM64로 빌드·검증하고 current 및 TEST 앱만 갱신한다. DB·n8n·Neo4j 이동이나 운영 반영은 이 역할 지시 범위가 아니다. 상세는 docs/work-log/2026-10-17-mac-test-migration.md를 따른다.

- 사용자 요구를 구현 가능한 작업으로 나누고 담당자, 대상 파일, API 계약, 완료 조건을 정한다. 세 담당 에이전트의 결과를 검토하고 충돌·공통 계약 변경을 조정한다.
- 환경 설정, 배포·검증 스크립트, 공통 테스트 실행, TEST 통합 검증을 맡고 문서 담당에게 실제 변경·검증 증거를 전달하여 작업 문서의 기술적 정확성을 최종 확인한다. 주요 대상은 environment.py, cli.py, scripts/deploy_*.sh, compose*.yml 및 서비스 실행·배포 문서다.
- 병합 전 변경 diff와 테스트 증거를 확인한다. Production 반영은 앞의 운영 배포 승인 규칙을 그대로 따른다.

### Claude — 조류 데이터·검색·API (dev-claude)

- 종/아종 식별, 국명, 분류·계통·생태 관계, 형질·보전 자료와 출처 품질을 맡는다. GraphRAG 검색, 질문 라우팅, 답변 근거 검증과 API 오류·응답 계약도 담당한다.
- 주요 대상은 src/robingraph/retrieval/, ingest/, graph/, generation.py, api/의 Python 코드와 관련 tests/test_*.py, 데이터 생성·감사 스크립트다. 실제 존재하는 경로를 확인하고 착수한다.
- 데이터 수정은 출처·라이선스·종 범위를 확인하고 재현 가능한 생성/검증 절차를 남긴다. 운영 DB·수집 작업·대량 데이터 갱신은 역할 배정만으로 실행하지 않는다.
- API 응답 필드 변경이 필요하면 Codex에게 먼저 공유하여 Antigravity와 소비 화면을 함께 조정한다.

### Antigravity — 도감·채팅 UI·사용성 (dev-agy)

- 채팅, 도감 카드 앞뒤 전환, 비교·관계 탐색, 사진·출처 표시, PC·모바일 레이아웃과 접근성을 맡는다.
- 주요 대상은 src/robingraph/api/static/의 HTML·JS·CSS와 관련 프런트엔드 검사·브라우저 검증 자산이다. 기존 표현과 상호작용을 유지하면서 요청된 문제를 최소 변경으로 해결한다.
- 화면에서 보전 등급·이름·자료 부족·아종 참고 범위를 API 의미대로 표시한다. 화면 편의를 위해 생물학적 판단이나 출처를 만들어 넣지 않는다.
- 키보드, 드래그·스와이프, 작은 화면 넘침, 움직임 줄이기를 관련 변경에 맞게 확인한다. API 모의 검사, 실제 TEST 브라우저 검사, 물리 모바일 기기 검사를 구별한다.

### 문서 담당 — 작업 기록·Obsidian·백로그 (writer / 브랜치 dev)

- 새 문서 에이전트의 워크트리는 main-2이며 기존 UI 담당 Antigravity(dev-agy)와 구별한다. 에이전트 제품명보다 워크트리와 담당 역할을 기준으로 작업을 전달한다.
- docs/work-log/의 상세 작업 기록과 요청된 관련 문서, Obsidian 작업 기록·백로그 정리를 맡는다. 위 작업 문서 작성 기준을 모든 기록에 적용한다.
- 사용자 지시(2026-10-17): Writer는 로컬 초안뿐 아니라 Obsidian MCP를 통한 작업 기록 생성·수정과 관련 백로그 갱신까지 직접 담당한다. 문서 작업을 배정할 때 기본 완료 범위에 저장소 기록·Obsidian 반영·저장 후 재조회를 포함한다. 별도 로컬 초안 전용 지시가 있을 때만 Obsidian 쓰기를 제외한다.
- Codex가 근거와 대상 경로를 전달한 문서 작업은 추가 쓰기 승인을 반복해서 요청하지 않고 진행한다. 완료 상태는 검증된 범위만 반영하며, 다른 작업의 상태·본문은 보존한다. 같은 작업의 Obsidian 쓰기는 Writer가 맡고 Codex는 증거 검토와 동기화 결과 확인을 맡아 중복 쓰기를 피한다.
- Codex와 구현 담당이 제공한 변경 diff, 실제 실행 명령·결과, 검증 산출물, 배포 대상·결과를 근거로 작성한다. 과거 기록을 현재 재검증으로 표현하거나 확인하지 않은 성공·커밋·배포·백로그 완료를 기재하지 않는다. 증거가 없으면 미확인으로 남기고 담당자에게 확인한다.
- 저장소와 Obsidian의 핵심 내용·검증 결과를 맞추고 문서 경로와 동기화 결과를 보고한다. MCP 연결이나 쓰기 실패 시 로컬 기록과 미반영 상태를 명시하며 동기화 완료로 보고하지 않는다. 인증 정보는 기록하지 않는다.
- 자기 워크트리의 문서만 수정하고 Codex에게 변경 파일을 전달한다. Codex가 검토 후 dev-codex에 필요한 문서 변경을 반영한다. 다른 워크트리는 근거 확인을 위한 읽기만 허용한다. 같은 작업의 Obsidian 수정은 한 담당자에게 배정하여 중복 수정을 피한다.
- 역할 배정만으로 앱 코드·테스트·환경 설정 변경, 서비스 재시작, 배포, DB 쓰기, commit/push/병합을 실행하지 않는다. 생물학적 사실이나 새 요구사항을 만들어 추가하지 않는다.

### 문서 전달 절차

- Claude와 UI 담당은 구현 결과와 변경 파일, 실행한 검증·실패·건너뛰기, mock/fixture/실제 DB/API 구분, 미검증 사항을 Codex에게 전달한다.
- Codex는 통합 확인 결과와 TEST/Production 구분, 실제 배포·커밋 여부를 문서 담당에게 전달하고 문서의 기술적 정확성을 검토한다. 문서 담당은 승인된 증거에 따라 기록과 요청된 백로그를 갱신한다.
- 새 문서 담당도 작업 전 자기 워크트리의 AGENTS.md를 읽는다. 이번 역할 추가 자체는 지침·문서 정리 범위이며 앱 수정이나 배포 요청이 아니다.

### 최초 지시 이력: 담당 영역 현황 점검

- 아래 최초 지시는 당시 역할 정립과 현황 점검에 한정된 이력이다. 이후 작업은 별도 사용자 요청에 따라 범위를 정한다. 당시 점검은 역할 정립과 현황 점검이었다. 새로운 기능 구현·기존 코드 수정·서비스 재시작·배포·DB 쓰기는 포함하지 않는다. 다음 구현은 점검 결과와 사용자 요청에 맞춰 별도로 범위를 정한다.
- Codex: 당시 세 워크트리의 지침을 일치시키고 전달 결과를 확인한다. 최신 실행 문서와 검증 기록에서 현재 상태와 미검증 범위를 구분해 후속 작업을 정리한다.
- Claude: 코드와 테스트를 읽어 종/아종 범위, 이름, 보전·형질 출처, API/검색 오류 처리의 위험과 테스트 공백을 최대 3개 우선순위로 정리한다. 각 항목은 파일·관련 테스트·근거·권장 검증을 제시하며, 재현 전에는 결함이라고 단정하지 않는다.
- Antigravity: 정적 자산과 기존 검증 자산을 읽어 카드 조작·모바일·접근성·출처 표시의 위험과 검증 공백을 최대 3개 우선순위로 정리한다. 파일·동작·근거·권장 검증을 제시하고 실기기 미검증을 명시한다.
- 당시 두 에이전트는 먼저 자기 워크트리의 AGENTS.md를 읽고 담당 역할을 확인한다. 점검 결과는 현재 세션에 보고한다. 로컬 보고 파일을 만든다면 docs/work-log/2026-10-15-claude-baseline.md 또는 2026-10-15-antigravity-baseline.md만 사용하고 상세 문서 기준을 따른다.

### 충돌 방지·검증·전달

- 각 에이전트는 자기 워크트리에서만 수정한다. 다른 워크트리의 변경을 덮어쓰거나 타인의 미커밋 작업을 되돌리지 않는다. 공통 파일 변경과 담당 경계 확장은 Codex와 조율한다.
- AGENTS.md의 공통 역할 지침은 dev-codex에서 관리해 세 자식 워크트리(dev-claude, dev-agy의 실제 경로 main, 문서 담당 main-2)에 같은 내용으로 전파한다. 총 네 워크트리의 공통 역할 지침을 확인한다. 전파 시 각 워크트리의 기존 지침을 보존한다. Git 워크트리 사이에서 파일이 자동 동기화된다고 가정하지 않는다.
- 진행 보고에는 담당 범위, 변경 파일, 실제 실행 명령·결과, 통과/실패/건너뛰기, mock/fixture/실제 DB/API 구분, 남은 한계를 포함한다. 인증 정보·환경 파일의 비밀값은 출력하거나 문서에 넣지 않는다.
- 실제 DB 쓰기 테스트는 격리 환경과 대상 확인이 선행돼야 한다. 공유 TEST의 벡터 인덱스를 테스트 차원에 맞춰 삭제·교체하지 않는다. 필요한 경우 일회용 DB 검증으로 분리한다.
- 관련 검증이 통과한 범위만 완료로 보고하고 새 변경·실패 근거 없이 전체 검사를 반복하지 않는다. 코드 변경 후에는 기존 graphify 규칙에 따라 갱신한다.
- 사용자 또는 별도 작업 지시 없이 commit/push/병합·브랜치 삭제·이력 재작성은 수행하지 않는다. 역할 배정이나 일반적인 진행 요청은 운영 배포 승인으로 해석하지 않는다.

### 현재 기록의 해석

- docs/work-log/2026-10-14-orbstack-restart-check.md는 TEST의 직접 연결 복구와 임시 중계 제거를 기록한다. 이전 전체 검증 문서의 중계 미해결 설명을 현재 장애로 재등록하지 않는다. 이 기록은 현재 시점에 다시 실행한 검증이 아니다.
- 도메인 정리 후 tests.test_api_deployment 재실행, 일회용 DB가 필요한 통합 검사, 물리 모바일·Safari·Firefox 및 물리 재부팅 검증은 관련 기록에서 후속 확인 대상으로 남아 있다. 우선순위는 현재 요청과 재현 근거로 정한다.
- 최초 역할 정립 당시 dev-codex에는 graphify-out/graph.json과 wiki/index.md가 없어 graphify query가 실패하여 원문을 읽어 진행했다. 이는 당시 이력이며 현재 그래프 존재 여부는 작업 착수 시 확인한다. 그래프 부재 자체를 앱 실행 장애로 취급하지 않는다.
