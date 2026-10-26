---
created: 2026-10-26
date: 2026-10-26
project: RobinGraph
type: worklog
status: completed
tags: [worklog, robingraph, ponytail, refactor]
---

# Ponytail 이름 해소 중복 정리·응답 보존 검증 — 2026-10-26

## 요약

사용자의 Ponytail 리팩토링 요청에 따라 `services.py`의 두 이름 해소 경로에 반복된 resolver 호출·검증을 `_resolve_taxon_name` 하나로 모았다. 앱 변경은 한 파일이며 16줄 helper와 두 호출로 정리해 순 4줄을 줄였다. graph/profile별 응답 렌더링·질문 재작성·예외 처리·trace 경계는 유지했다.

fixture API 60건의 전후 HTTP 상태·응답 본문·resolver 인자와 scope·후속 호출 횟수가 동일했다. 이 비교는 실제 DB·provider 호출 0인 모의 환경 검사다. 전체 Python 검사는 1,327 실행·1,287 통과·40 skip·0 실패(24.973초), graphify 갱신과 git diff check도 통과했다. TEST/운영 배포나 commit/push는 수행하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 근거 |
| --- | --- | --- |
| 요구사항 | Ponytail 방식의 최소 리팩토링 | 중복 이름 해소 두 곳만 정리 |
| 설계 | 기존 검증·resolver 동작을 단일 helper로 재사용 | 새로운 parser·추상화·의존성 없음 |
| 앱 수정 | services.py 한 파일, 순 4줄 감소 | 16줄 helper와 두 호출 |
| 회귀 검사 | invalid identity 외부 API 검사 1 method·16 subcases 추가 | 응답 계약 보호 |
| 전후 비교 | fixture API 60건 동일 | 15 variants × 2 routes × 2 scopes |
| 배포 / Git | 미실행 | 리팩토링 요청 범위 유지 |

---

## 1. 작업 배경 및 문제 분석

graph와 profile의 이름 해소 경로에 같은 resolver 호출 및 identity 검증이 반복됐다. 같은 검증을 두 곳에서 유지하면 향후 한 경로만 고치는 불일치 위험이 있어, 이미 쓰는 동작을 작은 공통 helper로 정리했다. 이는 새로운 질의 지원이나 기존 오거절을 수정하는 작업이 아니다.

Ponytail의 기존 코드 재사용·최소 변경 원칙에 따라 앱 한 파일의 중복만 제거했다. 경로마다 다른 렌더링과 질문 재작성, 예외 처리, trace는 그대로 둬 외부 동작 변화가 없도록 범위를 제한했다.

---

## 2. 해결 방안 및 설계

- 두 호출부의 공통 이름 해소·identity 확인을 `_resolve_taxon_name`으로 모았다.
- graph/profile별 후속 로직은 각 호출부에 유지했다. 공통화 범위를 응답 생성이나 추적 전체로 넓히지 않았다.
- 기존 오류 처리와 검증을 삭제하지 않고 이동·재사용했다.
- fixture 전후 응답뿐 아니라 resolver 호출 인자·scope와 후속 호출 횟수도 비교해 숨은 동작 변화 여부를 확인했다.

```text
graph 경로 ─┐
            ├─ _resolve_taxon_name → 각 경로의 기존 응답·예외·trace 처리
profile 경로┘
```

---

## 3. 주요 구현 내용

- `src/robingraph/api/services.py` — 중복 이름 resolver 부분을 16줄 helper와 두 호출로 정리했다. 앱 순 변경량은 -4줄이며 parser·DB·UI는 변경하지 않았다.
- `tests/test_entity_resolution_api.py` — invalid identity가 외부 API로 잘못 이어지지 않는 회귀 검사 1 method, 16 subcases를 추가했다.

증거는 `docs/verification/assets/2026-10-26-name-resolution-refactor/`에 보존했다.

| 파일 | 내용 |
| --- | --- |
| `compare_responses.py` | 같은 fixture 조건으로 전후 API 실행·관측 |
| `before.json` | 변경 전 상태·응답·호출 기록 |
| `after.json` | 변경 후 같은 관측 기록 |
| `comparison.json` | 60건 상태·본문·resolver/scope·후속 호출 동일성 |

---

## 4. 검증 및 테스트 결과

### 전후 fixture API 비교

15 variants × graph/profile 2 routes × 2 scopes, 총 60건을 비교했다. `comparison.json`은 다음 결과를 기록했다.

| 관측 항목 | 결과 |
| --- | --- |
| HTTP 상태·응답 본문 | 60건 동일 |
| resolver 호출·scope | 동일 |
| 후속 호출 횟수 | 동일 |
| 실제 DB/API/provider 호출 | 0 |

### 독립 코드 리뷰

`independent-review.json`에서 최종 diff 리뷰 PASS를 확인했다. 리뷰어는 before/after 60건 JSON 전체의 동일성을 직접 대조하고, graph/profile의 except·trace·질문 재작성 scope 차이가 유지됨을 확인했다. 리뷰어가 테스트를 다시 실행한 것은 아니므로 root 실행 결과와 독립 리뷰를 합산하지 않는다.

### 전체 회귀 검사와 graphify

`verification.json`·`unit.log`에 전체 Python unittest 1,327 실행·1,287 통과·40 skip·0 실패(24.973초)가 기록됐다. 신규 invalid identity 검사 1 method의 16 subcases가 포함되며 subcase 수를 전체 test method 수에 더하지 않는다. 40 skip은 기존 pinned 자료/전용 DB opt-in 조건으로 미실행한 검사이며 통과로 계산하지 않는다.

`graphify.log`의 갱신 결과는 9,152 nodes·19,969 edges·487 communities였다. `git diff --check`도 통과했다. 로그는 증거 경로에 보관했지만 현재 ignored log를 별도 Git staging하지 않았으며 사용자 리팩토링 범위에서 commit/push도 하지 않았다.

위 모의 비교와 단위 검사를 실서버 질의·독립 일반화 성능 평가로 해석하지 않는다. 이전 작업의 평가 점수나 미해결 한계를 이번 리팩토링의 성능으로 포장하지 않는다.

---

## 5. 배포 및 형상 관리

- **작업 환경**: dev-codex 로컬 리팩토링.
- **TEST / Production 배포**: 수행하지 않음.
- **Git commit / push / merge**: 수행하지 않음.
- **DB / provider / UI 변경**: 수행하지 않음.
- **범위**: 앱 한 파일의 동작 보존 중복 제거와 관련 회귀 검증.

---

## 6. 한계 및 후속 과제

- 전체 질의 정확도나 응답 속도가 개선됐다는 주장은 하지 않는다. 성능 benchmark를 실행하지 않았다.
- 실제 DB/provider/운영 브라우저 검증을 새로 실행하지 않았다. 같은 fixture의 계약 보존이 검증 범위다.
- RG-212 진행 중 상태와 기존 미해결 V2-07A·V2-10B를 변경하지 않는다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
