---
created: 2026-10-26
date: 2026-10-26
project: RobinGraph
type: worklog
status: completed
tags: [worklog, robingraph, production, refactor]
---

# 이름 해소 리팩토링 main 반영·운영 배포 — 2026-10-26

## 요약

사용자가 이름 해소 리팩토링의 운영 배포와 브랜치 병합을 명시적으로 승인했다. 리팩토링 commit `9df92886cac349e346b6197085d4dfc9031ff614`를 main에 fast-forward하고 origin/dev-codex·origin/main으로 push했다. 이전 리팩토링 문서의 “당시 배포·commit/push 미실행” 기록은 보존하고 이번 후속 작업을 별도로 기록한다.

실제 Jenkins job은 저장소 파일과 별개인 inline definition을 사용했다. 이전 lexical 정의를 현재 commit의 `ci/Jenkinsfile.production`과 동기화하고 job properties를 보존했다. 운영 교체 전 input 대기 중이던 이전 PROD #10은 ABORTED로 취소했고 stale queue 78도 취소했다. 새 PROD #11은 SUCCESS로 완료됐고 실제 운영에서 healthy·active/semantic·tracing true·실험 50을 확인했다. 공개 4 POST·3 GET은 모두 200이었고, 고유 trace 4개가 질문·마스킹된 응답·태그와 일치했다. TEST 컨테이너는 변경하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 현재 확인 상태 | 범위 |
| --- | --- | --- |
| 요구사항 | 운영 배포·브랜치 반영 명시 승인 | 기존 이름 해소 리팩토링 |
| Git | 9df92886 commit·main fast-forward·두 원격 push 완료 | 최신 검증 소스를 일반 배포 경로로 연결 |
| Jenkins | 실제 inline 정의를 committed production 파일과 동기화 | properties 보존 |
| 이전 실행 | #10 ABORTED·queue 78 취소 | 운영 교체 전 stale lexical 실행 중단 |
| 새 실행 | PROD #11 SUCCESS·운영 교체 완료 | runtime·공개 계약·trace 검증 완료 |
| 기능 상태 | RG-212 진행 중 유지 | 리팩토링 배포가 질의 정확도 개선을 뜻하지 않음 |

---

## 1. 작업 배경 및 문제 분석

이름 해소 리팩토링은 graph/profile 두 경로의 공통 resolver·identity 검증을 helper로 모으고 외부 응답을 유지하는 변경이었다. 사용자는 해당 변경의 운영 배포와 브랜치 반영을 승인했다.

앞선 Git 통합에서는 저장소 Jenkinsfile만 semantic·tracing 설정에 맞췄고 실제 inline job 정의는 변경하지 않았다. 이 차이를 그대로 두면 main에서 배포해도 lexical 설정으로 되돌아갈 수 있어, 이번 배포 전에 실제 job 정의를 committed 파일과 동기화했다.

---

## 2. 해결 방안 및 설계

- 이미 검증한 리팩토링 commit을 main에 fast-forward하고 원격 두 브랜치에 push했다.
- 실제 inline 정의를 현재 committed `ci/Jenkinsfile.production`으로 동기화했다. job properties를 보존하고 이전 문서의 당시 상태는 수정하지 않았다.
- 이전 정의로 실행돼 input 대기 중인 #10과 stale queue를 취소한 뒤 새 #11을 시작했다.
- 새 빌드의 검사·이미지·운영 runtime·실제 trace를 확인해 배포 완료를 확정했다. 앞선 로컬 리팩토링 검사와 이번 Jenkins 검사 시간을 분리해 기록했다.

```text
검증 리팩토링 commit → main fast-forward / push
→ 실제 inline 정의 동기화 → stale 실행 취소 → PROD #11
→ 운영 이미지·runtime·동일 요청 trace 검증
```

---

## 3. 변경 범위 및 증거

- `src/robingraph/api/services.py` — 앞서 검증한 `_resolve_taxon_name` 공통화. 이번 배포에서 추가 질의 로직을 개발하는 작업이 아니다.
- `tests/test_entity_resolution_api.py` — 앞선 invalid identity 회귀 검사.
- `ci/Jenkinsfile.production` — 실제 inline job 정의 동기화의 committed 원본.
- 증거 경로: `docs/verification/assets/2026-10-26-name-resolution-production/`.

실제 운영 runtime은 active/semantic·MLflow tracing true·실험 ID 50/name robingraph-prod로 확인했다. `production-after.json`의 revision label과 실행 중 services.py SHA도 배포 소스와 일치했다. 서비스 파일 SHA256은 `3232e36ef4cb93f2fca9c01d7f1b7a9da8c949cd640d5e8e0d0bed0632d4b83c`다.

| 증거 파일 | 확인 내용 |
| --- | --- |
| `source.json`, `jenkins-result.json` | 실제 배포 revision·검사 수치·PROD #11 SUCCESS |
| `jenkins-config-sync.json` | 실제 inline 정의와 committed pipeline 일치·properties 보존 |
| `stale-build10-result.json` | 이전 #10 ABORTED |
| `production-release.json`, `image-metadata.json` | immutable image·revision·빌드 provenance |
| `production-before.json`, `production-after.json` | 교체 전후 runtime·실행 소스 확인 |
| `test-before.json`, `test-after.json` | TEST 컨테이너·이미지·시작 시각 동일 |
| `public-production.cjs`, `public-production.json`, `public-contract-verification.json` | 공개 실제 요청·응답 계약 |
| `production-traces.json`, `trace-response-verification.json` | 실험 50의 같은 질문·응답·태그 readback |

인증 정보는 기록하지 않았고 임시 인증 파일은 삭제했다.

---

## 4. 검증 및 테스트 결과

### 선행 리팩토링 검사 — 이번 빌드와 구분

선행 작업은 fixture API 60건의 상태·본문·resolver 인자/scope·후속 호출 횟수 동일, Python 1,327 실행·1,287 통과·40 skip·0 실패(24.973초), 독립 diff 리뷰 PASS였다. 실제 DB/provider 호출은 없었다. 이 수치를 진행 중인 PROD #11의 실행 결과로 표시하지 않는다.

### 실제 Jenkins 작업

| 실행 | 확인한 결과 | 의미 |
| --- | --- | --- |
| 이전 PROD #10 | 운영 교체 전 input 대기에서 ABORTED | 이전 lexical 정의 실행 취소 |
| stale queue 78 | 취소 | 오래된 실행 요청 제거 |
| 새 PROD #11 | SUCCESS | 검증한 commit으로 운영 교체 완료 |

취소된 #10은 운영 교체 전 중단됐으므로 앱 결함이나 운영 롤백으로 표현하지 않는다. stale queue 78도 취소했다. 최종 inline 정의는 committed pipeline과 다시 대조해 일치를 확인했고 job properties는 보존했다.

### 이번 Jenkins 검사

| 항목 | 결과 | 범위 |
| --- | --- | --- |
| Python 전체 | 1,327 실행·1,287 통과·40 skip·0 실패, 24.749초 | 이번 PROD #11 실행 |
| Node frontend | 322 통과·0 실패 | 자동 검사 |
| AMD64 fixture smoke | 통과 | 운영 아키텍처 기동 |
| 공개 POST | 4/4 HTTP 200·계약 확인 | 실제 API, mock 없음 |
| 공개 GET | 3/3 HTTP 200 | health·OpenAPI·국명 lineage |
| 페이지 JS 오류 | 0 | 관측한 공개 페이지 범위 |
| MLflow trace | 4/4 일치·추가 chat 0 | 실험 50·고유 trace 4개 |

40 skip은 기존 pinned 자료 부재 또는 전용/일회용 DB opt-in 미설정 검사이며 통과로 합산하지 않는다. 선행 로컬 24.973초와 이번 Jenkins 24.749초를 혼동하지 않는다.

### 독립 배포 후 검토

`independent-review.json`의 read-only 후검은 PASS였다. 리뷰어는 실제 commit·services SHA·inline 정의 SHA, 공개 4 POST·3 GET, trace 4개의 원문·마스킹 응답, TEST 불변을 직접 재대조했다. 추가 API 호출·테스트 재실행·Git 변경은 0이며 root 실행과 독립 재조회 결과를 중복 실행 횟수로 합산하지 않는다.

### 실제 공개 질의와 trace

| 질문 | API 결과 | reason / stage |
| --- | --- | --- |
| 청둥오리에 대해 알려줘 | answer·프로필 종 identity 일치 | none / none |
| 청둥오리와 서식지가 겹치면서 먹이가 다른 새는? | graph answer | none / none |
| 천둥오리에 대해 알려줘 | clarify·벡터 후보 확인 필요 | ambiguous_name / name_resolution |
| 청둥오리랑 비슷한 식생을 가진 새들을 알려줘 | clarify·식성/서식 환경 두 의미 선택 | ambiguous_conditions / routing |

오타를 자동 확정하거나 “식생”을 임의로 식성으로 바꾼 결과가 아니다. 두 clarify는 후보·의미 확인 계약의 정상 동작이며, HTTP 200 네 건을 모두 종 답변 네 건으로 세지 않는다.

GET `/health`, `/openapi.json`, `/v1/taxa/lineage?name=청둥오리`는 모두 200이었다. `public-contract-verification.json`은 프로필 identity·관계 답변·벡터 후보 확인·의미 선택 네 계약을 통과로 확인했다.

[Production MLflow 실험 50](https://mlflow.dove-nest.com/#/experiments/50)의 root 원문, 기존 마스킹·길이 제한을 적용한 HTTP 응답, disposition/reason/stage 태그가 고유 trace 4개와 일치했다. 재조회 과정의 새 chat 요청은 0이다. 원본 전체 응답을 마스킹 없이 저장했다는 뜻은 아니다.

프로필의 name lookup·profile 단계, 관계 질의의 graph route·candidates·embedding, 오타 후보의 name lookup·embedding span을 관측했다. 의미 선택은 root만 남았다. 계획·감사 등 모든 경로를 이번 네 요청에서 실행했다고 주장하지 않는다.

`test-before.json`과 `test-after.json`은 컨테이너 ID·이미지·시작 시각이 동일했다. DB 직접 명령·마이그레이션은 실행하지 않았고, MLflow trace 쓰기는 요청 관측을 위한 의도된 기록이다. 전체 DB checksum 불변 감사는 수행하지 않았다.

---

## 5. 배포 및 형상 관리

- **작업 commit**: `9df92886cac349e346b6197085d4dfc9031ff614`.
- **main 반영**: fast-forward 완료.
- **원격**: origin/dev-codex·origin/main push 완료.
- **Jenkins 실제 설정**: committed production 파일로 inline 정의 동기화, properties 보존.
- **배포**: PROD #11 SUCCESS.
- **Immutable image**: `ghcr.io/evodmik/robingraph@sha256:d1077581143bbb59bb47ea2723c140af66b20a59e4df8cd3a1bae5f6985670f5`.
- **실제 소스**: revision `9df92886cac349e346b6197085d4dfc9031ff614` 및 services.py SHA 일치, healthy.
- **문서 후속 Git 작업**: Codex가 별도 commit/push로 마무리하며 이 기록에 문서 자신의 commit hash를 요구하지 않는다.
- **문서 이력**: 기존 리팩토링 기록의 당시 미배포 상태는 유지한다.

---

## 6. 한계 및 후속 과제

- RG-212 진행 중과 V2-07A·V2-10B 잔여 실패를 유지한다.
- 이름 해소 중복 제거가 정확도·속도 향상을 입증한 것은 아니다.
- 공개 계약 4건과 trace 검증이 전체 질의 일반화나 성능 benchmark를 대신하지 않는다. 실제 물리 기기·Safari/Firefox·전체 반응형/접근성 검사는 이번에 수행하지 않았다.
- 이전 “inline 정의 미동기화” 기록은 당시 이력으로 유지한다. 이번 작업에서 실제 정의 동기화를 완료한 사실은 이 문서로 연결한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-26-Ponytail-이름해소-중복정리|리팩토링 구현과 당시 로컬 검증]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-26-Git정리-main병합-원격동기화|이전 Git 정리와 inline 정의 미동기화 이력]]
