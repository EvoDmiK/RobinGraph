---
created: 2026-11-06
date: 2026-11-06
project: RobinGraph
type: worklog
status: completed
task_id: git-push-cleanup
tags: [worklog, robingraph, git]
---

# 미반영 변경사항 검토·작업 단위 커밋·브랜치 push

## 요약

사용자가 아직 push하지 않은 변경사항 정리를 요청했다. 각 담당자는 자기 워크트리에서 기존 변경을 검토하고 작업 단위로 커밋한 뒤 담당 브랜치에만 일반 push했다. 새로운 기능 개발이나 main 병합·force push·운영 배포·DB 변경으로 범위를 확대하지 않았다.

Writer의 `dev`에는 문서·증거·평가 자료와 공통 지침 변경을 보존했다. 오래된 테스트 복사본 2개와 scratch 1개는 영구 백업과 SHA 확인 뒤 Git 대상에서 제외했다. 각 담당자의 최종 원격 확인 결과를 아래 표에 기록했다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 요구사항 | 미커밋·미push 정리 | 승인된 기존 작업을 작업 단위로 기록 |
| 분담 | 각자 자기 브랜치만 처리 | Codex·Claude·Antigravity·Writer 병행 |
| 자료 보존 | 문서·증거·dataset 원문 보존 | manifest bytes와 기존 사용자 AGENTS 변경 포함 |
| 검증 | 비밀값 패턴·회귀·원격 대조 | 실제 실행 범위와 담당별 결과 구분 |
| 배포 | 없음 | main 병합·force push·배포·DB 작업 없음 |
| 형상 관리 | 일반 commit/push | 최종 원격 SHA·clean 상태를 표에 기록 |

## 1. 작업 배경 및 문제 분석

여러 작업에 걸쳐 각 워크트리에 구현·문서·검증 자산이 누적돼 있었다. Writer 워크트리 `main-2`의 브랜치는 `dev`, 초기 HEAD는 `67fea34`였고 origin/dev와 같았다. 변경 546파일·134,004,134 bytes 가운데 docs 증거 494개·작업기록 31개·백로그 5개·README 1개, eval 데이터 11개, AGENTS 1개, 테스트 2개와 scratch 1개가 있었다.

기존 테스트 복사본은 현재 root의 검증본보다 오래됐고 Writer 브랜치 앱과의 호환 검증 대상도 아니었다. 새 기능으로 추가하거나 삭제해 잃지 않도록 영구 백업으로 분리했다. 평가 CSV는 CRLF 원문 자체가 공개 manifest hash의 대상이어서 일반 Git 줄바꿈 변환을 그대로 적용하면 증거가 달라지는 문제가 있었다.

## 2. 해결 방안 및 설계

각 담당자의 AGENTS 역할과 기존 변경을 보존하고 자기 브랜치만 commit/push했다. Writer는 문서 범위에서 초기 지침, 그래프 평가 자료, 후속 질문·식이/카드 기록, 새소리 수집 기록을 분리했다. root는 backend/UI/n8n/문서 등 담당 결과를 분리해 정리했다.

비밀값이나 실제 환경 파일은 Git에 넣지 않는다. 패턴 검사는 인증값 자체를 출력하지 않고 파일·종류·건수만 확인했다. 휴리스틱 검사의 통과가 모든 가능한 비밀의 부재를 보증하지는 않는다. 과거 검증 결과는 이번에 다시 실행한 검사와 구분한다.

## 3. 주요 구현 내용

새 앱 구현은 없다. 기존 사용자 AGENTS의 Ponytail 통합 리뷰 지침 1줄을 보존했다. `.gitattributes`에는 root와 동일한 실제 CSV 1개 경로의 `-text` 예외만 추가해 공개 데이터 원문을 보존했다.

```gitattributes
data/eval/graph_questions/taxonomic-regression-v1/questions.csv -text
```

`tests/test_taxon_traits.py`, `tests/test_taxon_traits_api.py`, `scratch/readback_generalization_check.py`는 `/Users/kimdove/orca/git-cleanup-backups/RobinGraph-20261106-writer/` 아래 기존 상대경로로 복사했고 SHA256 일치를 확인한 뒤 워크트리 중복본만 정리했다. 백업은 `/tmp`가 아닌 영구 경로이며, 자세한 hash는 `writer-initial-push.json`에 남겼다.

## 4. 검증 및 테스트 결과

### Writer 검증

텍스트 457개에서 PEM private key·JWT·URL 내 인증·대표 token prefix·quoted secret assignment 패턴 후보는 0개였다. 바이너리 증거를 텍스트 검사로 검증했다고 주장하지 않는다. 데이터 11개는 root와 byte 동일이었고 공개 데이터셋의 indexed Git blob 3개는 manifest SHA256과 일치했다.

일반 `git diff --cached --check`는 CSV의 기존 CRLF 497행과 과거 문서·패치·Markdown 증거 공백 69행을 보고했다. 원자료·증거 bytes를 보존해 이를 일괄 수정하지 않았다. Writer는 앱 코드를 변경하지 않았고 과거 테스트 복사본을 새 테스트로 도입하지 않아 앱 회귀 검사를 재실행하지 않았다.

### 담당별 검사

- Codex: focused Python 142/142 통과·4.569초·skip 0, Node chat+birds 339/339 통과. mock/fixture 기반 focused 회귀이며 실제 DB/API 검사를 다시 실행한 것은 아니다. 새 기능 변경이 아닌 기존 구현 정리 후 검사다.
- Codex 비밀값 휴리스틱: 텍스트 209개, 실제 비밀 0건·가짜 테스트 패턴 3건으로 보고했다.
- Codex 코드 diff check는 통과했다. 일반 문서 diff check는 과거 patch context·Markdown 2-space 줄바꿈·기존 JSON 끝 빈 줄을 보고했고 bytes를 보존했다. 문서 commit 전 `core.whitespace=-blank-at-eof,-blank-at-eol`로 해당 항목을 제외한 검사는 통과했다. 일반 검사 전체 통과로 바꿔 기록하지 않는다.
- Claude: 오프라인 unittest 1,403개 실행·1,363 통과·40 skip·실패/오류 0, 26.568초. 실제 DB/API 실행 검증이 아니다. 164파일 검토·AST·비밀 패턴 검사에서 실제 비밀 0건과 보안 fixture 후보 4건을 확인했고 diff check가 통과했다. 공개 CSV는 Writer와 같은 단일 경로 `-text` 예외로 원 CRLF 497행을 보존했고, HEAD blob SHA256 `39ea0b080fe4fcaeff064218128fd0e51338765ea49850da5794593df6600e24`가 원 manifest와 일치했다. manifest·MLflow 결과는 바꾸지 않았다. CR-at-EOL을 허용한 diff check도 통과했다.

## 5. 배포 및 형상 관리

| 담당 / 브랜치 | 커밋 | 원격 확인 |
| --- | --- | --- |
| Writer / dev | `8daa0de` AGENTS, `39c56fc` 그래프 평가·데이터, `77046e5` 후속 질의·카드, `0c05d27` 새소리 기록 | 초기 정리 push 완료, origin/dev=`0c05d27786d60ca16b0afbff37f396c916d840a1`, 당시 clean |
| Codex / dev-codex | `4b1d86c`, `9fedeb9`, `c95d9af`, `1168f10`, `975190d` | push 완료, HEAD=origin/dev-codex=`975190d`, ahead/behind 0/0·clean |
| Antigravity / dev-agy | `ff88756`, `dadad25`, `e8369b8` | origin/dev-agy와 `e8369b8` 동일·clean 확인 |
| Claude / dev-claude | `27e6b58`, `f38ef04`, `af867d4`, `a4bbfde`, `b37b5dd` | push 완료, HEAD=origin/dev-claude=`b37b5ddea5a94ef7b42858847b1d3f64119f8abf`, ahead/behind 0/0·clean |

기존 로컬 `EvoDmiK/main-2`는 origin/main의 ancestor이며 21 behind·0 ahead로 독립 미push 커밋이 없어 그대로 보존했다. origin/main은 변경하지 않았고 main 병합·force push·배포는 수행하지 않았다. 이 정리 기록과 Vault 동기화 영수증은 Writer가 별도 문서 commit/push로 남긴다. 아래 최초 정리 SHA는 그 문서 후속 커밋의 부모 이력이며, 문서 후속 커밋 ID·최종 원격 일치는 작업 완료 응답에서 전달한다. 자기 문서 커밋의 self hash를 본문에 다시 추가하는 반복 커밋은 만들지 않는다.

## 6. 한계 및 후속 과제

과거 증거는 기록 당시의 검사·환경 결과이며 이번 Git 정리로 현재 전체 기능·운영 상태를 재검증한 것은 아니다. stale 테스트/scratch는 명시된 영구 백업에 보존했다. main 통합·배포는 이번 요청 범위가 아니며 별도 지시가 필요하다. 기존 기능 백로그 상태는 이 Git 작업으로 변경하지 않는다.

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/5xx 데이터·분류·이름/2026-11-06-RG507-첫정기새소리수집점검|직전 정기 수집 점검·fixture 정리 기록]]
