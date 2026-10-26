---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: completed
task_id: null
tags: [worklog, robingraph, refactor, ponytail]
---

# Ponytail — 질문 처리 중복 계산과 불필요한 보조 함수 정리 — 2026-10-23

## 요약

사용자가 “Ponytail로 리팩토링해줘”라고 요청했다. 직전 완성 기능의 동작을 유지하면서 재사용 가능한 결과와 상수를 활용하는 최소 정리로 범위를 잡았다. 같은 종 질문을 여러 번 파싱하고 그래프 질문으로 다시 변환하는 부분을 한 번의 계산 결과로 재사용하며, 단일 호출의 한 줄 보조 함수와 중복 안내 문자열을 제거했다.

앱 변경은 `api/services.py`, `retrieval/graph_questions.py` 두 파일이다. 새 기능·응답 계약·추출 규칙·오류 처리·DB 구조를 바꾸지 않는다. 사용자 체감 지연 개선을 측정하지 않았으므로 반복 호출 감소를 성능 향상 수치로 표현하지 않는다.

독립 백엔드 검토자의 scratch 검사 69개와 Codex의 전체 Python 검사 1,210개 중 1,171개가 통과하고 39개는 skip됐다. TEST 배포 후 healthy, 실제 API 회귀 61/61, 공개 TEST Chromium 8/8 흐름을 확인했다. 이번 작업에서 Production 배포나 commit·push는 수행하지 않았다. 새 백로그 번호를 만들지 않은 유지보수 요청이므로 `task_id`는 비워 두고 기존 작업 상태를 보존한다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 직전 기능의 최소 리팩토링 | 같은 질문 파싱·변환 반복, 단일 호출 wrapper, 중복 안내 문자열 |
| 설계 및 해결 방안 | 기존 결과·상수 재사용 | 새로운 추상화·의존성·설정 추가 없이 현재 흐름에서 중복 제거 |
| 코드 / 설정 수정 | 앱 Python 2파일 | `services.py`, `graph_questions.py` |
| 실서비스 배포 | TEST 이미지 healthy | `test-ponytail-023b4901e54b`, Production 미반영 |
| 검증 및 테스트 | Python 1,171 통과·39 skip | 독립 69·graph API 15 별도 통과, 실제 TEST API 61/61·브라우저 8/8 |
| 형상 관리 | dev-codex 작업 트리 | 기존 변경 보존, commit·push·merge 미실행 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

완료된 질문 처리 기능을 유지하면서 코드의 불필요한 반복을 줄이는 요청이다. 새 질의 유형이나 UI를 추가하는 것이 아니므로 이전 실패 문장을 더 인식하도록 규칙을 확장하지 않는다.

### 원인 분석 / 설계 검토

- `services.py`의 질문 처리에서 같은 종 질문 파싱이 최대 3회, 그래프 질문 변환이 최대 2회 수행되는 경로가 있었다. 같은 입력에서 얻은 결과를 재사용하면 중복 호출을 줄일 수 있다.
- `graph_questions.py`의 `_short_word`는 단일 호출에 쓰이는 한 줄 보조 함수였다. 불필요한 간접 호출을 지우고 사용 지점에서 바로 표현할 수 있다.
- `tree_fruit`의 자료 한계 안내가 두 응답 경로에 같은 문자열로 반복됐다. 기존 `LIMITATIONS` 맵에 `tree_fruit` 항목을 한 번 정의하고 두 경로가 참조하게 했다.

이 요청에서 관찰된 것은 코드 중복이다. 실제 서비스 장애나 성능 저하의 원인으로 단정하지 않는다.

---

## 2. 해결 방안 및 설계

1. 같은 요청 안의 종 질문 파싱 결과를 한 번 구해 기존 분기에서 재사용한다. 그래프 질문 변환도 한 번 계산한 결과를 사용한다.
2. 단일 호출 한 줄 `_short_word` 함수를 제거한다. 기존 값 처리 의미를 유지한다.
3. 나무 열매의 자료 한계 안내를 기존 `LIMITATIONS` 맵의 `tree_fruit` 항목으로 모으고 참조한다. 문구와 자료 의미는 유지한다.
4. 기존 검증·오류 처리·API 응답과 추출 규칙을 유지한다. 더 큰 모듈 분리·클래스 추가·의존성 도입은 하지 않는다.

Ponytail의 기존 구현 재사용·삭제 우선 원칙을 적용했다. 중복 제거를 위한 새 추상화는 만들지 않는다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `src/robingraph/api/services.py` — 동일 요청의 종 질문 파싱 최대 3회→1회, `to_graph_question` 최대 2회→1회로 결과 재사용.
- `src/robingraph/retrieval/graph_questions.py` — `_short_word` 제거, 중복 `tree_fruit` 안내를 기존 `LIMITATIONS` 맵으로 모아 두 응답 경로에서 재사용.
- `docs/verification/assets/2026-10-23-ponytail-refactor/` — 실제 검사와 TEST 배포 증거. `refactor.patch`에 이번 앱 2파일 차이를 보존했다. 검증 자산·작업 문서는 앱 변경 범위와 구분한다.

### 변경 전후

| 항목 | 변경 전 | 변경 후 |
| --- | --- | --- |
| 종 질문 해석 | 동일 입력을 분기별로 반복 파싱 | 같은 요청에서 파싱 결과 한 번 재사용 |
| 그래프 질문 변환 | 같은 해석 결과를 반복 변환 | 한 번 변환한 결과 재사용 |
| 단어 보조 함수 | 단일 호출을 위한 한 줄 wrapper | 사용 지점에서 기존 표현 사용 |
| 자료 한계 안내 | 같은 안내를 두 경로에서 문자열로 중복 관리 | `LIMITATIONS['tree_fruit']`로 한 번 정의 후 재사용 |

새 설정이나 데이터 마이그레이션은 해당하지 않는다. 반복 계산 제거는 구현 사실이며 실행 시간 개선을 별도로 입증한 것은 아니다.

---

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

| 실행 | 결과 | 구분 |
| --- | --- | --- |
| 백엔드 담당자의 독립 scratch 검사 | 69개 통과 | 구현 리뷰와 관련 단위·회귀 검사, 실제 DB 검증 아님 |
| graph API 관련 검사 | 15개 통과 | 기존 API 계약·오류 회귀 검사 |
| Codex 전체 Python | 1,210 실행: 1,171 통과 / 39 skip / 0 실패, 27.840초 | 기존 검사의 실제 실행 수치 |
| 코드 그래프·공백 검사 | `graphify update .`, `git diff --check` 통과 | 기능 검증과 별도 |
| TEST 이미지 smoke | 네트워크 없는 fixture smoke 통과 | 실제 DB 검사 아님 |

단위·계약 검사는 기존 검사로 검증했으며 새 테스트는 추가하지 않았다. 전체 검사는 `uv run --locked --extra test --extra tracing python -m unittest discover -s tests`로 실행하고 stdout·stderr를 `python-tests.log`에 보존했다. UI 변경이 없어 Node 전체 검사는 재실행하지 않았다. 선행 운영 배포의 검사 수치를 이번 수정 결과로 대신 사용하지 않는다. 39개 skip은 실행·통과한 것으로 합산하지 않는다.

### 실서비스 / UI 검증 증거

Codex가 실행한 새 TEST 이미지의 실제 결과를 Writer가 조회해 기록했다. Writer가 검사를 재실행한 것은 아니다.

| 실제 검증 | 결과 | 구분·근거 |
| --- | --- | --- |
| TEST API 고정 회귀 | 61/61 통과, 실패 목록 없음 | `test-api.json`·`test-api.log`; 실제 TEST active+semantic, 응답 모의 없음, 조류 DB 쓰기 0 |
| 공개 TEST Chromium | 8/8 통과, 채팅 POST 20회, pageerror 0 | 390/1280px × 정상/오타 × 먹이/서식 환경, `browser.json`·`browser.log` |
| 확인·출처·후속 행동 | 실제 의미 선택·종 후보 확인 후 관계 답변, 출처 조작·도감·비교 흐름 확인 | 기존 계약과 동작 회귀; 신규 UI 디자인 수정 아님 |

브라우저는 `https://robingraph-test.dove-nest.com/chat`의 실제 응답을 사용했다(`response_mocking: false`). API 61문항은 기존 배포 회귀셋을 재사용한 것으로 미노출 정확도·모든 자연어 표현 검증이 아니다. 이번 동작 보존 확인 범위를 일반적인 의미 해석 완료로 확대하지 않는다.

---

## 5. 배포 및 형상 관리

- **대상**: TEST 앱, 이미지 `robingraph-api:test-ponytail-023b4901e54b`, healthy.
- **소스 SHA256**: `023b4901e54b279636037e269be991d48365286b0a96d7c5e661c52148d4b61c`.
- **릴리스**: `/Users/kimdove/robingraph-test/releases/ponytail-023b4901e54b-ac350a`, `state: verified`, source manifest 일치 확인.
- **기준 HEAD**: `834c5353ca45f0640152ca4849548cd48818b266`. 이번 변경 커밋이 아니라 미커밋 source snapshot의 기준이다.
- **TEST 런타임**: 기존 `active + semantic` 유지. 새 실험 활성화가 아니며 Production의 `active + lexical`은 변경하지 않았다.
- **배포 스크립트 재사용**: 선행 `deploy-test-snapshot.py`의 경로·접두어만 바꾼 `/tmp/rg-ponytail-deploy.py`를 사용했다. `deployment-reuse.json`에 재사용 범위를 기록했다. 새 배포 체계를 추가하지 않았다.
- **브랜치**: `dev-codex`.
- **Git**: 기존 미커밋 변경을 보존하며 이번 요청으로 commit·push·merge를 수행하지 않았다.
- **Production**: 배포·재시작·이미지 교체·롤백 없음. 앞선 운영 승인을 이번 리팩토링 승인으로 확대하지 않는다.
- **DB·API**: 자료 변경·인덱스 교체·마이그레이션·API 계약 변경 없음.

---

## 6. 한계 및 후속 과제

- 반복 호출 감소는 확인 대상이지만 서비스 지연·처리량 벤치마크는 이번 범위가 아니다. 속도가 얼마나 빨라졌는지 수치를 주장하지 않는다.
- RG-204·RG-205 사람 검토·RG-212 등 기존 기능 과제의 상태를 변경하지 않는다. 리팩토링으로 자연어 지원 범위가 늘어난 것은 아니다.
- 물리 모바일·Safari·Firefox와 DB 전체 불변 감사는 미실행이다. 390px 브라우저 검사를 실기기 검증으로 표현하지 않는다.
- Writer는 실제 증거에 따라 저장소 반영용 scratch와 동일한 Obsidian 기록을 저장하고 재조회로 일치를 확인했다. 인덱스에는 링크만 추가하고 기존 본문·전체 백로그 상태를 보존했다. 앱·테스트·환경 파일은 직접 수정하지 않았으며 저장소 반영은 Codex 최종 검토 후 수행한다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-검증된-그래프-질의-확인흐름-운영-배포|선행 검증된 기능의 운영 배포]]
