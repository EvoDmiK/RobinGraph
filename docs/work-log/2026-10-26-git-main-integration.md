---
created: 2026-10-26
date: 2026-10-26
project: RobinGraph
type: worklog
status: completed
tags: [worklog, robingraph, git, deployment]
---

# Git 변경 정리·main 병합·후속 운영 배포 설정 동기화 — 2026-10-26

## 요약

사용자 승인에 따라 검증한 코드·평가 자료·문서·증거를 commit하고 origin/main의 변경을 병합했다. 작업 commit은 `e74aaa4eb38cd4bcfa2b6ec206ca637b99981291`, 최종 merge commit은 `cf52e1dc0c9439ebb7b8b579f9fc5ed2dcc117f4`다. Desktop의 main을 fast-forward하고 `git push origin dev-codex main`을 완료해 두 원격 브랜치가 cf52e1d를 가리키게 했다.

저장소의 두 Jenkinsfile은 semantic·tracing 활성화·Production 실험 50으로 맞췄다. 실제 Jenkins job은 inline definition을 사용하며 이번 Git 작업에서 설정 API를 호출하지 않아 변경되지 않았다. 향후 inline 정의 동기화와 다음 운영 배포 승인이 별도로 필요하다. 병합 후 Python 1,326 실행·1,286 통과·40 skip·0 실패와 Node 322 통과를 확인했다. 현재 운영을 재배포하지 않았고, 이전 운영 배포 기록의 당시 main/lexical 상태는 보존했다.

Git 통합은 RG-212 전체 완료가 아니다. V2-07A·V2-10B 잔여 실패와 최초 평가·gold 작성 한계는 그대로 남는다.

## 작업 및 변경 결과 요약

| 구분 | 현재 확인 사항 | 범위 |
| --- | --- | --- |
| 요구사항 | 사용자 Git 정리·병합 승인 | 검증 소스·자료·기록 통합 |
| 변경 정리 | dirty 1,943파일·약 191MB | 코드·dataset·docs/evidence 포함 |
| 제외 | species_profile.py.orig 백업을 /tmp에 보존 이동 | 백업 제외, 원본 삭제로 기록하지 않음 |
| 비밀 점검 | 실제 runtime 비밀값 대조 scan 0건 | generic token scan은 fixture만 확인 |
| Jenkins 설정 | 저장소 두 Jenkinsfile을 semantic·tracing true·실험 50에 맞춤 | 실제 inline job 정의는 미변경; 별도 동기화 필요 |
| 검증 | helper mock 16 통과·코드 diff check 통과 | 기존 Markdown hardbreak·원본 patch 공백 보존 |
| Git | e74aaa4 작업 commit → cf52e1d merge | origin/dev-codex·origin/main push 완료 |

---

## 1. 작업 배경 및 문제 분석

직전 배포는 TEST 검증 소스 SHA를 불변 snapshot으로 고정해 운영에 반영했지만 Git에는 미커밋 상태가 남았다. origin/main은 이전 릴리스 revision `33c0b67`, dev 작업의 기준은 `834c535`였다. 일반 main 배포 정의가 lexical을 유지하면 향후 배포가 현재 승인된 semantic 설정을 덮어쓸 수 있었다.

사용자 승인에 따라 Git 통합과 후속 파이프라인 설정을 정리했다. 과거 배포 당시 상태와 이번 후속 변경을 시간 순서에 맞게 별도 기록하며, Git 통합을 새 운영 배포로 해석하지 않는다.

---

## 2. 해결 방안 및 설계

- 검증 코드와 재현 가능한 dataset·문서·실패/성공 증거를 함께 정리했다. 이전 평가 실패 기록은 통과 기록으로 덮어쓰지 않는다.
- 편집 백업 `species_profile.py.orig`는 /tmp에 보존하고 커밋 대상에서 제외했다.
- 실제 runtime 비밀값과 전체 대상 파일의 대조 scan, generic token scan으로 민감 정보 유입을 확인했다. fixture와 실제 인증 정보를 구분하며 문서에는 값 자체를 남기지 않는다.
- 두 Jenkinsfile을 기존 승인 운영 runtime과 맞추고 배포 helper의 기존 mock 검사를 재사용했다.
- 최신 검증 내용을 commit한 뒤 origin/main을 병합했다. 충돌은 원격 기능이 최신 승인본에 포함됐는지 독립 검토하고 해결했다. 병합 후 전체 검사와 원격 push 결과를 확인했다.

---

## 3. 주요 변경 내용

### 대상 파일 및 자료

- 검증한 앱 코드·관련 테스트·질문 평가 dataset.
- 저장소 작업기록과 검증 증거. 최초 독립 평가·노출 회귀·미해결 한계 구분을 보존한다.
- `Jenkinsfile`, `ci/Jenkinsfile.production` — semantic/tracing 설정을 기존 승인 운영 runtime과 맞췄다.
- `scripts/deploy_registry_prod.py`, `tests/test_registry_prod_tracing.py` — 앞선 운영 배포에서 검증한 tracing 옵션 묶음과 6개 신규 mock을 Git에 포함했다. 기존 10개와 합친 helper 검사는 16개다.
- 배포 helper 관련 검증은 16 mock 통과이며 운영 실제 재교체 검증과 다르다.

### 평가 CSV의 원본 바이트 보존

마지막 Git 정합성 검사에서 `data/eval/graph_questions/taxonomic-regression-v1/questions.csv`의 원래 CRLF가 Git에 의해 LF로 변환돼 published manifest SHA와 다른 문제가 확인됐다. 원본 파일과 manifest를 바꾸지 않고 `.gitattributes`에 해당 CSV 하나만 `-text` 예외를 추가한 뒤 `git add --renormalize`로 index를 정리했다.

검사한 published manifest 대상 Git index blob 3/3의 SHA가 일치했고, 다른 변경 파일에서는 CRLF 자동변환에 따른 불일치를 발견하지 않았다. 이는 앱 코드 변경이 아니므로 전체 Python·Node 검사를 다시 실행하지 않았으며, blob hash 검증을 별도 근거로 사용했다. 이 정리는 주요 merge cf52e1d 이후 후속 commit에 포함하는 변경이다.

### main에 반영한 설정

```text
graph interpreter = semantic
MLflow tracing = true
MLflow experiment ID = 50
MLflow experiment name = robingraph-prod
```

현재 운영은 직전 승인된 snapshot의 semantic·실험 50으로 유지한다. 위 값은 저장소 파일의 설정이며 실제 Jenkins inline job 정의가 이를 자동으로 읽는다는 의미가 아니다. 이번 작업은 Jenkins 설정 API를 호출하지 않았고 운영 재배포도 수행하지 않았다. 다음 배포 전 inline 정의 동기화와 별도 배포 승인이 필요하다.

---

## 4. 검증 및 테스트 결과

### 완료된 사전 검사

| 검사 | 결과 | 한계 |
| --- | --- | --- |
| 실제 runtime 비밀값 대조 | 대상 1,943파일에서 0건 | 검사한 값·파일 범위에 대한 결과 |
| generic token scan | fixture만 확인 | fixture와 실제 인증값 구분 |
| 코드 diff check | 통과 | 기존 Markdown hardbreak·원본 patch 공백은 보존 |
| 배포 helper mock | 16 통과 | 모의 검사, 실제 배포 아님 |

병합 후 전체 Python unittest 검사는 1,326 실행·1,286 통과·40 skip·0 실패(26.326초)였다. 앞선 1,320개에 신규 helper 검사 6개가 포함된 수치다. 40 skip은 pinned 자료 부재 또는 전용/일회용 DB opt-in 미설정 검사이며 통과로 합산하지 않는다. Node 검사는 322 통과·0 실패(288.676ms), graphify update도 통과했다. 이 검증은 실제 운영 API 재시험이나 운영 교체가 아니다.

### 실제 병합과 source 동일성 검증

1,943파일을 포함한 commit `e74aaa4eb38cd4bcfa2b6ec206ca637b99981291`이 생성됐다. origin/main `33c0b67`을 `merge --no-commit`으로 합치는 과정에서 두 Jenkinsfile 추가 충돌과 기존 10개를 합친 12충돌이 발생했다. 독립 검토에서 원격 기능이 현재 승인본에 모두 포함됨을 확인한 뒤 최신 승인본을 선택했고, 해결 후 tree는 e74aaa4와 동일했다.

`integration-verification.json`은 승인 manifest 234개 중 232개 동일·배포 helper 1개 변경·백업 `.orig` 1개 제외를 확인했다. 실제 runtime src 111파일과 data 46파일이 일치했다. 앞선 운영 후보의 application 112개 집계에는 `.orig`도 포함돼 있었으므로 이번 111개와의 차이를 앱 기능 누락으로 해석하지 않는다. 병합 후 전체 Python·Node 검사는 위 결과로 완료했다. `independent-git-review.json`의 사전 simulation은 당시 cached 원격을 대상으로 한 검토였고, 최종 12충돌과 tree 동일성은 root의 실제 merge 결과 및 `integration-verification.json`으로 구분해 확정했다.

증거 위치는 `docs/verification/assets/2026-10-26-git-main-integration/`이다. 원격 기능 검토와 실제 병합 기록을 함께 보존했다.

---

## 5. 배포 및 형상 관리

- **현재 작업**: 사용자 승인에 따른 Git 정리·main 통합.
- **시작 기준**: origin/main `33c0b67`, dev 기준 `834c535`.
- **검증 변경 commit**: `e74aaa4eb38cd4bcfa2b6ec206ca637b99981291` (1,943파일).
- **최종 병합**: `cf52e1dc0c9439ebb7b8b579f9fc5ed2dcc117f4`; origin/main `33c0b67` 이력을 포함하며 12충돌 해결 후 tree는 e74aaa4와 동일.
- **main 반영**: `/Users/kimdove/Desktop/RobinGraph`의 main을 `ff-only`로 갱신.
- **원격 반영**: `git push origin dev-codex main` 성공. 이번 주요 병합 시점의 두 원격 브랜치는 cf52e1d. 문서 후속 commit의 자기 해시는 이 기록에 요구하지 않는다.
- **운영**: 재배포 없음. 직전 승인 immutable snapshot 유지.
- **이력 보존**: 기존 운영 배포 문서의 당시 lexical/main 미동기화 사실은 그대로 두고 이번 문서에 후속 변경을 기록한다.

---

## 6. 한계 및 후속 과제

- Git 통합이 RG-212 일반화 완료를 뜻하지 않는다. 기존 V2-07A·V2-10B 잔여 실패와 평가 gold 한계를 유지한다.
- 약 191MB 자료를 포함한 변경량은 사전 정리 시점 값이다. 백업 제외·추가 문서 반영 뒤 최종 commit 파일 수와 혼동하지 않는다.
- 이번 문서·동기화 영수증은 주요 병합 이후 작성한 후속 기록이다. 전체 working tree가 계속 깨끗하다고 주장하지 않으며, 문서 후속 commit/push는 Codex가 별도로 마무리한다.
- 기존 운영 앱은 승인 snapshot 그대로다. 저장소 Jenkins 설정 정렬을 실제 job 정의 변경·운영 재배포 또는 새 API 검증으로 표시하지 않는다. 실제 inline 정의는 미변경이므로 동기화 전 배포에 의한 lexical 회귀 위험이 남는다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-26-시맨틱-질의-원인trace-운영배포|직전 운영 배포와 당시 Git 상태]]
