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
