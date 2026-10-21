## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Ponytail (Lazy Senior Dev Mode)

The best code is the code never written. Before writing code, stop at the first rung that holds:
1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse existing helpers/patterns.
3. Does the standard library already do this?
4. Does the native platform cover it?
5. Does an installed dependency solve it?
6. Can this be one line?
7. Only then: write the minimum code that works.

Rules:
- No unrequested abstractions, boilerplate, or unnecessary dependencies.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins once the problem and flow are understood.

# RobinGraph 작업 지침

## 공통

- 작업 전 현재 경로·브랜치와 자기 워크트리의 AGENTS.md를 확인한다.
- 자기 워크트리와 담당 범위에서만 수정하고 기존 변경사항을 보존한다. 공통 파일·API 계약·담당 범위 변경은 Codex와 조율한다.
- 자료 없는 내용과 검증되지 않은 국명을 생성하지 않는다. 종·아종·유사 종의 근거와 보전 등급의 출처·평가 대상·연도를 구분한다.
- 실제 DB 쓰기 검증은 격리 환경과 대상을 먼저 확인한다. 공유 TEST 벡터 인덱스를 테스트용으로 삭제·교체하지 않는다.
- 인증 정보를 출력하거나 문서에 기록하지 않는다.
- 코드 변경 후 기존 graphify 규칙에 따라 갱신한다.
- 별도 지시 없이 commit·push·병합·브랜치 삭제·이력 재작성을 수행하지 않는다.

## 운영 배포 승인

- 사용자 명시 승인 전에는 Production 배포·컨테이너 재시작·이미지 교체·운영 DB 변경·롤백을 수행하지 않는다.
- 과거의 포괄적 배포 허용보다 이 규칙을 우선한다.
- 요청 범위의 구현·검증·TEST 배포까지 진행하고 결과를 제시한다.
- 일반적인 진행 요청, TEST 수정 요청과 Jenkins 승인 절차를 운영 배포 승인으로 해석하지 않는다.

## 브랜치별 역할

- dev-codex / Codex: 작업 분담, 공통 계약 조정, 리뷰·통합·검증과 TEST 환경 관리.
- dev-claude / Claude Code: 조류 데이터·출처 품질, 검색·GraphRAG, 답변 근거와 Python API.
- dev-agy / Antigravity: 도감·채팅·비교 UI, 출처 표시, 반응형·접근성. 실제 워크트리는 main.
- dev / Writer: 저장소 작업 문서, Obsidian 기록·백로그. 실제 워크트리는 main-2.

### dev-codex

- 담당자·대상 파일·API 계약·완료 조건을 정하고 변경 diff와 실제 검증 증거를 검토한다.
- 환경 설정, 배포 스크립트, 공통 테스트와 TEST 통합 검증을 담당한다.
- Writer에게 변경·검증·배포·커밋 증거를 전달하고 문서 정확성과 동기화 결과를 확인한다.
- 공통 AGENTS.md를 네 워크트리에 전파하되 각 워크트리의 기존 지침을 보존한다.

### dev-claude

- retrieval/, ingest/, graph/, generation.py, api/ Python 코드와 관련 테스트·데이터 스크립트를 담당한다. 실제 경로를 확인하고 착수한다.
- 데이터 변경 시 출처·라이선스·종 범위와 재현 가능한 검증 절차를 남긴다.
- API 필드 변경은 Codex에게 먼저 공유하고 UI 담당과 조정한다.
- 역할 배정만으로 운영 DB 쓰기·수집·대량 갱신을 실행하지 않는다.

### dev-agy

- src/robingraph/api/static/과 관련 프런트엔드 검증 자산을 담당한다.
- 기존 동작을 유지하며 최소 변경으로 해결한다. 이름·보전 등급·자료 부족·아종 범위를 API 의미대로 표시한다.
- 관련 변경에 맞춰 키보드·스와이프·작은 화면·움직임 줄이기를 확인한다.
- 모의 API 검사, 실제 TEST 브라우저 검사와 물리 기기 검사를 구분한다.

### dev / Writer

- Codex가 전달한 근거와 경로에 따라 자기 워크트리의 문서만 수정한다.
- 기본 완료 범위는 저장소 기록·Obsidian 반영·관련 백로그 갱신·저장 후 재조회다. 로컬 초안 전용 지시가 있을 때만 Obsidian 쓰기를 제외한다.
- 배정된 문서 작업은 쓰기 승인을 반복 요청하지 않는다. 같은 작업의 Obsidian 수정은 Writer 한 명이 맡는다.
- 다른 작업의 본문·상태를 보존하고 저장소와 Obsidian의 핵심 내용·검증 결과를 일치시킨다.
- 동기화 실패는 미반영으로 보고한다. 문서 변경은 Codex 검토 후 dev-codex에 반영한다.
- 역할 배정만으로 앱·테스트·환경 변경, 재시작·배포·DB 쓰기·Git 작업을 수행하지 않는다.

## 문서 양식·기록·검증
- 작업 문서는 Obsidian MCP의 Templates/worklog.md, 백로그는 Templates/backlog-item.md를 조회하고 해당 양식에 맞춰 작성한다.
- 양식을 조회하지 못하면 임의 양식으로 대체하고 준수했다고 보고하지 않는다. 조회 실패와 미적용 상태를 명시한다.
- 작업 문서는 상세하게 작성한다. 배경·목표, 원인·근거, 변경 전후, 변경 파일·구현, 검증 방법·실제 결과, 배포·커밋 정보, 한계·후속 사항을 기록한다. 해당하지 않는 항목은 이유를 적는다.
- 실행·미실행, 통과·실패·건너뛰기와 mock·fixture·실제 DB/API 검증을 구분한다. 미확인 성공·배포·완료를 추정하지 않는다.
- 저장소와 Obsidian의 핵심 내용·검증 결과를 일치시키고 저장 후 재조회한다. 다른 작업의 본문·상태는 보존한다.
- 구현 담당 → Codex 통합 확인 → Writer 기록·동기화 → Codex 최종 확인 순서로 전달한다.
인증 정보는 기록하지 않는다. 채팅 완료 안내는 간결하게 하되 작업 문서의 상세함은 유지한다.

## 환경·기존 기록

- Production은 NAS이며 Jenkins PROD는 main polling·M4 검사/빌드·admin 승인·NAS 앱 교체 구조다. Jenkins TEST는 비활성이고 TEST artifact 승격 의존성은 없다.
- TEST 앱·빌드는 16GB Mac(.97), Neo4j·n8n은 32GB Mac(.98), PostgreSQL은 NAS(.99)를 유지한다.
- TEST URL: https://robingraph-test.dove-nest.com
- TEST 관리: /Users/kimdove/robingraph-test/manage.sh. 최신 snapshot을 ARM64로 검증한 뒤 current와 TEST 앱만 갱신한다.
- TEST 배포를 NAS 앱 재가동, DB·n8n·Neo4j 이동이나 운영 반영으로 확대하지 않는다.
- 환경·배포 상세는 docs/jenkins-deployment.md와 관련 docs/work-log/ 기록을 따른다.
- 과거 장애·복구·graphify 부재를 현재 상태로 단정하지 않는다. 미검증 항목은 현재 요청과 재현 근거에 따라 확인한다.
- 최초 역할 정립·현황 점검은 이력이며 새 구현·배포 승인이 아니다.