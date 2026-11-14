---
created: 2026-11-14
date: 2026-11-14
project: RobinGraph
type: worklog
status: completed
task_id: graphify-backlog-cleanup
tags: [worklog, robingraph, graphify, backlog]
---

# Graphify 갱신과 백로그 정리

## 요약

사용자가 Graphify 갱신과 백로그 정리를 요청했다. `dev-codex`의 현재 작업 지침·기존 기록을 확인하고 그래프의 AST 구조를 갱신했다. 노드는 10,229→10,492, 관계는 22,324→22,468이며 557개 community로 재생성됐다. 외부 LLM API 사용·비용은 0이다. 기존 문서 semantic 노드는 보존했으며 신규·변경 문서의 semantic 재추출은 실행하지 않았다.

백로그는 완료 근거와 미완료 경계를 분리했다. RG-507의 운영 수집 적용과 검토 화면 운영 대기를 구분했고, RG-202의 이름 해소 완료를 문헌 PPR 완료로 오기한 체크를 정정했다. RG-209~211의 누락된 요약·기존 기록 링크를 보완했다. RG-213·603·215 완료와 RG-204·205·212 미완료, 새소리 운영 승인 대기를 유지했다. 저장소 현황과 Obsidian을 동기화했으며 앱·DB·배포를 변경하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
|---|---|---|
| 원인 규명 / 요구사항 | 그래프 갱신·백로그 상태 정합성 | 요약의 오래된 운영 대기 문구, 요청 정정 누락, 링크 누락 대조 |
| 설계 및 해결 방안 | 기존 기록을 근거로 최소 정리 | 새 검증 없이 범위 완료와 잔여 작업 구분·기존 이력 보존 |
| 코드 / 설정 수정 | 앱 코드·설정 변경 없음 | 그래프 출력과 문서만 갱신 |
| 실서비스 배포 | 미실행 | TEST·Production 배포·재시작·DB 쓰기 없음 |
| 검증 및 테스트 | 그래프 JSON·CLI와 문서 readback | 아래 실제 수행·미수행 구분 |
| 형상 관리 | dev-codex, 기준 dca293cd | 이번 commit·push·merge·이력 변경 없음 |

## 1. 작업 배경 및 문제 분석

RG-507 요약에는 ‘운영 적용 대기’만 있어 이미 승인·적용된 수집 sidecar·최대 5종 예약까지 미적용으로 오해할 수 있었다. 11/05·07·09·10 기록은 운영 수집과 TEST 검토 화면·assessment 저장을 구분한다. 운영 최신 상태를 오늘 조회하지 않았으므로 과거 후보 수를 현재 수치로 갱신하지 않았다.

RG-202 전체 목록은 완료였으나 상세에 PPR 기반 결합 완료 체크가 있었다. 10/15 사용자 요청 정정 기록은 그래프 우선 이름 해소·벡터 후보·사용자 확인을 완료 범위로 명시하며 문헌 PPR은 미구현이다. 기존 카테고리의 정정 근거와 README의 제공 범위를 대조해 체크·설명을 바로잡았다. RG-209~211은 작업기록이 있으나 전체 현황에 빠져 있었고 독립 상세 파일은 없었다. 새 ID나 새 기능을 만들지 않고 기존 기록을 연결했다.

## 2. 해결 방안 및 설계

- Obsidian MCP의 `Templates/worklog.md`, `Templates/backlog-item.md`를 직접 조회했다. 이 기록은 worklog 양식을 적용하고 상세 백로그의 상태·목적·범위·완료 기준·검증·의존성·근거 필드를 유지했다. 현황 인덱스는 상세 항목 양식의 적용 대상이 아니다.
- root가 구현·검증 근거를 먼저 확인하고 Writer가 변경안을 전달했다. root 확인 후 문서를 작성·저장·재조회했으며 최종 diff·링크 검토는 root에 전달했다.
- 과거 작업기록을 현재 상태로 소급 수정하지 않았다. TEST와 운영 수치, 자동화 평가와 사람 Gold를 구분했다. 카테고리 문서는 확인된 충돌·누락만 최소 편집했다.

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `graphify-out/graph.json`, `graph.html`, `GRAPH_REPORT.md`, `manifest.json` 등 — `graphify update .`의 로컬 출력. gitignored 산출물이며 Git diff에 표시되지 않는다. `graphify-out/2026-11-14/`에 기존 그래프 4파일이 자동 백업됐다.
- `docs/backlog/README.md` — 완료 범위·미완료·보류·다음 작업 조건 현황.
- `docs/backlog/RG-507.md` — updated와 운영 수집/검토 대기의 요약·범위 정정.
- `docs/work-log/2026-11-14-graphify-backlog-cleanup.md` — 요청·근거·수행 결과·제한 기록.
- Obsidian `Work/RobinGraph/RobinGraph 작업 백로그.md` — updated 11/14, 착수 대기 placeholder 제거, 다음 행동 표, RG-209~211 링크, RG-202 범위·RG-507 상태, RG-213·603의 운영 수치 구분.
- Obsidian `Work/RobinGraph/백로그 상세/RG-202.md`, `RG-507.md` — 위 범위·체크 정정. PPR 과거 계획은 미구현으로 보존.
- Obsidian `Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그.md`, `5xx 데이터·분류·이름/작업 백로그.md` — 누락 요약·RG-507 상태 정합성, 당시 작업기록 보존.
- Obsidian `Work/RobinGraph/작업기록/8xx 문서·개발환경/2026-11-14-Graphify-갱신과-백로그-정리.md` — 이 작업 기록과 동일 본문.

### 핵심 코드 / 설정 스니펫

앱 코드·설정 수정은 없어 코드 스니펫은 해당하지 않는다. 실행한 갱신 명령은 `graphify update .`이며 exit 0이었다. 선행·후속 `graphify query`도 성공했다.

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

앱 코드가 바뀌지 않아 단위·회귀 suite와 DB/API·브라우저 검증은 실행하지 않았다. 예전 TEST·운영 수치는 기록 대조 근거이며 이번 실행 결과로 합산하지 않는다.

| 실제 실행 검사 | 결과 / 제한 |
|---|---|
| Graphify AST 갱신 | exit 0, 3,159개 corpus files, 10,492 nodes·22,468 edges·557 communities; 증가 +263 nodes·+144 edges |
| 출력 생성·query | graph.json·GRAPH_REPORT.md·graph.html 생성, query CLI 성공 |
| 빌드 후 JSON 정합성 | 노드 ID 중복 0, missing/dangling endpoint 0, exact duplicate edge 0 |
| 자기참조 | 16건(기존 14) 경고. SQL 자체 FK 포함, 함수 1건은 추출 오인 가능. 손상·전부 재귀로 단정하거나 그래프를 삭제·수정하지 않음 |
| 대형 HTML | 원 그래프 5,000 초과를 CLI가 알리고 557 community nodes·2,046 cross-community edges로 자동 집계 |
| 분류·추출 경고 | 미분류 120파일(.patch 52·.jsonl 20·.log 17 등), 심볼 없음 36 code files. 전 파일의 의미 추출 완료가 아님 |
| 레이블 제한 | 저장 레이블 155→community 557 차이, hub 기준 27개 이름 조정 경고. LLM semantic 레이블 재생성 미실행 |
| 문서 동시변경·저장 | Obsidian 수정 전 원문 대조로 동시변경 없음 확인; 변경 5개 문서 저장 후 요청 본문과 정확히 일치 재조회 |
| 최종 문서 검토 | root의 로컬 내용·diff 검토 및 `git diff --check` 통과; 변경 3파일의 로컬 Markdown 링크 23개 확인·누락 0 |

신규 작업로그도 Obsidian 저장 후 로컬 전체 본문과 정확히 일치 재조회했다. RG-507 상세는 저장소·Obsidian 전체 본문 일치를 확인했다. 전체백로그·상세 2개·카테고리 2개·작업로그 1개, 총 6개 Obsidian 문서만 쓰고 재조회했다.

빌드 후 JSON 진단은 추출 단계의 관계 손실을 전수 검증하지 않는다. 문서 변경 후 AST 재실행은 코드가 동일하므로 반복하지 않았고 신규 문서 semantic 노드가 반영됐다고 주장하지 않는다.

### 실서비스 / UI 검증 증거

현재 TEST·NAS 운영 API/UI·DB·n8n을 호출하지 않았다. Obsidian만 실제 MCP 읽기·쓰기·재조회했다. 이는 mock 검증이 아니며 조류 서비스의 새 운영 인수검증과 구분한다. RG-209의 당시 정책은 RG-210으로 대체됐고 RG-211은 표적 어순 범위 완료일 뿐 일반화 완료가 아니다.

## 5. 배포 및 형상 관리

- 대상 환경: 로컬 저장소 그래프·문서 및 기존 Obsidian vault.
- Git 브랜치: `dev-codex`, 작업 시작 기준 `dca293cd`.
- 이번 새 커밋 없음. push·merge·브랜치 삭제·이력 변경 없음.
- TEST·Production 배포·이미지 교체·컨테이너 재시작·DB 쓰기·수집·공개 없음.
- 인증값·서명 토큰을 문서나 도구 출력에 기록하지 않았다.

## 6. 한계 및 후속 과제

RG-205 사람 검토와 RG-212 잔여 회귀·Gold·미노출 일반화, RG-409의 2종 가용성·운영 승인, RG-507의 사람 검토·검토 화면 운영 반영이 남는다. RG-506은 배치·출처 고정 후 착수하며 RG-101·과거 PPR 계획은 실제 문헌·평가 자료 확보가 필요하다. 이 의존성 설명은 신규 실행 지시·운영 승인이 아니다.

Obsidian 5xx 카테고리에는 이번 작업 전부터 도구의 `# File`·Tip 형식 문구가 본문에 포함돼 있었다. 무관한 기존 본문 보존을 위해 전체 재서식·삭제하지 않았다. 신규 문서는 raw 응답의 실제 content만 사용했다.

## 관련 문서

- [현재 백로그 현황](../backlog/README.md)
- [이름 해소 요청 정정](2026-10-15-graph-first-name-resolution.md)
- [문헌 감사·PPR 미구현](2026-10-15-rg202-retrieval-readiness.md)
- [검토 기록 저장 TEST](2026-11-10-bird-audio-assessment.md)
- [후속 조건·피드백 운영 검증](2026-11-12-followup-feedback-production.md)
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
