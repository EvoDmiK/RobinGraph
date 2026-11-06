---
created: 2026-10-29
date: 2026-10-29
project: RobinGraph
type: worklog
status: completed
task_id: RG-407
backlog_status: completed
related_tasks: [RG-210]
tags: [worklog, robingraph, diet-labels, ui]
---

# [RG-407] 도감 팝업 먹이 표시명 정리 — 2026-10-29

## 요약

**현재 상태(2026-10-29 후속):** [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-29-승인3항목-운영배포-main병합|PROD #13 운영 배포·실제 검증 완료]]. revision `5056ccb`, dev-codex 커밋·main fast-forward 병합·양쪽 push 완료. 아래 구현·검증·배포 수치는 최초 TEST 단계의 이력이다.

2026-10-29 사용자 요청으로 기존 후속 기록을 독립 백로그 [[Work/RobinGraph/백로그 상세/RG-407|RG-407]]로 신규 등록했다. 최초에는 RG-210 후속으로 기록했으며, 이번 등록을 과거 착수 시점의 신규 번호로 소급하지 않는다. 등록 당시 백로그 상태는 진행 중(TEST 완료·운영 승인 대기)이었다. 이후 같은 날 사용자 승인으로 PROD #13 배포·실제 운영 검증을 마쳐 현재 백로그 상태는 **완료**다.

도감 팝업의 먹이 유형·먹이 생태·먹이 구성에서 원자료 설명 괄호를 제거하고 기타 척추동물 표시를 “기타 고기”로 정리했다. 로컬 변경이 TEST에 배포되지 않아 사용자가 본 화면에 이전 문구가 남아 있었다. 새 ARM64 이미지를 TEST에 반영했고, 실제 정적 파일과 API 네 종에서 새 표시값을 확인했다.

내부 key·원자료 범주·비율과 API 구조는 유지했다. TEST 배포·health·fixture 검증과 실제 Chromium 두 화면 크기의 팝업 검사 14/14가 완료됐다. 10월 28일 로컬 Python 78건·frontend 333건 통과 이력은 오늘 재실행한 검사로 합산하지 않는다. 아래 TEST 단계에서는 Production 배포와 Git commit·push를 수행하지 않았으며, 이후 운영 결과는 상단 후속 기록을 따른다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 / 요구사항 | 미배포된 표시명 수정 반영 | TEST 공개 static에 이전 문구가 남아 있었음 |
| 설계 | 기존 표시 문자열만 정리 | 원본 key·SOURCE_CATEGORY·비율 보존 |
| 코드 | 표시 관련 3파일·주석 1파일 | 235파일 snapshot 중 예상 4파일만 이전 release와 다름 |
| 배포 | TEST ARM64 이미지 verified | health·관리 verify·격리 fixture 통과 |
| 실제 검증 | 공개 static·API 네 종·Chromium 두 화면 | 표시값과 원본 value 확인, 팝업 검사 14/14 통과 |
| 형상 관리 | 미커밋 snapshot TEST 배포 | Production·commit·push 미실행 |

---

## 1. 작업 배경 및 문제 분석

기존 RG-210은 원자료의 무척추동물/척추동물 범주에 친숙한 곤충/고기 표시명을 제공하면서 설명 괄호를 함께 붙였다. 이번 요청은 도감 팝업의 요약 값을 간결하게 보이도록 원자료 괄호를 제거하고 “기타 고기”로 표시하는 후속 작업이다.

로컬 수정 후 TEST 미배포 상태여서 사용자가 본 팝업과 root가 확인한 공개 정적 파일에 이전 문자열이 남아 있었다. 새 배포 후 실제 asset SHA와 로컬 SHA가 일치했으므로 반영 여부를 코드 존재만으로 판단하지 않았다. 브라우저 캐시를 원인으로 확정한 것은 아니다.

## 2. 해결 방안 및 설계

프로필·BirdBase·프런트엔드의 기존 표시 라벨만 함께 정리했다. 별도의 변환 계층이나 새 데이터 분류를 추가하지 않았다. 표시에서 “원자료:” 설명을 없애되 SOURCE_CATEGORY 등 근거 식별값과 비율 계산은 유지했다.

모든 괄호를 제거한 것은 아니다. 온혈·변온 척추동물을 구분하는 `고기 (온혈 척추동물)`과 `고기 (변온 척추동물)`은 그대로 표시한다. “곤충”은 기존 무척추동물 범주의 사용자용 라벨이며 원자료 범위가 곤충만으로 좁아졌다는 뜻이 아니다.

## 3. 주요 구현 내용

| 파일 | 변경 내용 |
| --- | --- |
| `src/robingraph/retrieval/species_profile.py` | VALUES 대문자 key 4개·소문자 key 2개 표시 문자열 정리 |
| `src/robingraph/retrieval/birdbase.py` | 먹이 표시 문자열 2개 정리 |
| `src/robingraph/api/static/chat.js` | 먹이 구성 라벨 2개 정리 |
| `src/robingraph/retrieval/graph_condition_extractor.py` | 표시명 관련 주석 정리; 추출 규칙 변경 없음 |
| `tests/test_species_profile.py`, `tests/test_taxon_traits.py` | 새 표시명에 맞춰 기대값 갱신; 서버 snapshot 235파일에는 tests 미포함 |

주요 표시 전후:

| 원본 key / 영역 | 이전 표시 | 변경 표시 |
| --- | --- | --- |
| `Invertebrate`, `invertebrate` | 곤충 (원자료: 무척추동물) | 곤충 |
| `VertFishScav` | 고기·물고기·사체 (원자료: 척추동물·물고기·사체) | 고기·물고기·사체 |
| `Invertivore` | 곤충 섭식 (원자료: 무척추동물 섭식) | 곤충 섭식 |
| `Vertivore` | 고기 섭식 (원자료: 척추동물 섭식) | 고기 섭식 |
| `unknown_vertebrate` | 고기 (기타 척추동물) | 기타 고기 |
| BirdBase `Vertebrate` | 고기 (원자료: 척추동물) | 고기 |

표시 값의 예시는 다음과 같다. 원본 key와 수치가 화면 라벨 변경과 분리된다.

```json
{"name":"diet_category","value":"Invertebrate","display":"곤충"}
```

## 4. 검증 및 테스트 결과

### 로컬 검사와 배포 검사

| 시점 / 종류 | 결과 | 해석 |
| --- | --- | --- |
| 10월 28일 Python 관련 검사 | 78 실행, OK, 1.485초 | 실패 없음, skip 출력 없음; 오늘 재실행하지 않음 |
| 10월 28일 frontend 검사 | 333 통과 / 0 실패 / 0 skip, 306.571667ms | 모의/로컬 검증 이력이며 오늘 재실행하지 않음 |
| 10월 29일 ARM64 빌드 | 성공 | TEST 이미지 생성 |
| 네트워크 없는 읽기 전용 fixture smoke | 통과 | 실제 DB 조회와 별도 |
| TEST health·manage verify | 통과 | 배포 상태 verified |
| source/release manifest 비교 | 235파일 전부 SHA 일치 | root 독립 확인; 이전 release 대비 변경 4파일 |
| 공개 `/static/chat.js` | 로컬 SHA 일치 | 새 곤충·기타 고기 라벨 확인 |

당시 실제 명령은 아래와 같다. 관련 검사이며 전체 Python 스위트 실행으로 확대하지 않는다.

```sh
PYTHONPATH=src:tests uv run --locked --extra test python -m unittest tests.test_species_profile tests.test_taxon_traits tests.test_birdbase_traits -q
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
```

frontend 원본 로그는 `/tmp/robingraph-diet-distribution-frontend.log`에 남아 있다. Python 출력은 `Ran 78 tests in 1.485s`, `OK`였고 별도 skip 줄은 없었다.

### 실제 TEST API

검증은 공개 TEST의 실제 프로필 GET 응답을 사용했다. mock 결과로 대체하지 않았다.

| 조회 대상 | 실제 확인한 표시와 값 |
| --- | --- |
| `Anas platyrhynchos` / 청둥오리 | 잡식, 수생 초식; 구성 `invertebrate: 40` → 곤충 40%, 변온 척추동물 10%, 물고기 10%, 씨앗 20%, 기타 식물 20% |
| `Corvus corone` / 까마귀 | `VertFishScav` → 고기·물고기·사체; 곤충 30%, 온혈·변온 척추동물 각 20%, 사체 20%, 씨앗 10% |
| `Parus cinereus` / 박새 | `Invertebrate` → 곤충; 분포 자료가 없어 구성 차트가 없는 것은 정상 |
| `Lanius excubitor` | `Vertivore` → 고기 섭식, `VertFishScav` → 고기·물고기·사체; 구성 원본 key·수치 유지 |

네 종 중 분포 자료가 있는 응답의 `unknown_vertebrate`는 0이다. 따라서 이번 API 표본으로 “기타 고기” 양성 비율 문장까지 검증했다고 주장하지 않는다. 표시 문자열·0 행과 양성 자료 표본 검증을 구분한다.

### 브라우저

실제 Chromium headless shell CDP에서 청둥오리 질문 → 도감 팝업 → Enter로 뒷면 → 항목·비율 펼침을 확인했다. API 응답 mock은 사용하지 않았다. 390×844 모바일 에뮬레이션과 1280×800 데스크톱에서 각각 7개, 총 14/14 검사가 통과했다.

두 화면에서 팝업 열림·뒷면, 곤충 40%, 기타 고기 0%, 온혈·변온 척추동물 구분, 원자료 설명 괄호 부재, viewport 안 배치와 문서 가로 넘침 없음을 확인했다. 최종 스크린샷은 청둥오리 두 장이며 root가 모바일 이미지를 독립 시각 검토했다. 중간 박새 팝업에서는 먹이 유형 “곤충”을 확인했으나 분포 자료가 없어 차트 검증은 청둥오리로 진행했다. 박새 스크린샷은 덮어써져 최종 증거에 포함하지 않았다.

질문 제출은 하네스의 `requestSubmit()`을 사용했고 팝업 뒤집기는 Enter로 검사했다. 스와이프·움직임 줄이기·물리 모바일·Safari·Firefox는 이번에 확인하지 않았다. 검증용 Chromium/CDP 프로세스는 종료했다.

### 검증 도구 정정 이력

초기 urllib 공개 요청은 HTTP 403이었고 curl 요청으로 실제 응답을 확인했다. compose 보존 검사에서 존재하지 않는 `compose.nas.test.yml`을 지정했던 하네스를 실제 파일 `compose.mac-test.yml`, `compose.nas.yml`로 고쳐 두 파일이 보존됐음을 확인했다. 이를 앱 결함이나 데이터 손실로 기록하지 않는다. 브라우저 초기 시도는 앱 초기화 전에 설정한 입력값이 초기화되어 미전송 timeout이 났다. 초기화 대기와 form `requestSubmit()`으로 하네스를 고친 최종 실행은 통과했다.

증거는 `docs/verification/assets/2026-10-29-diet-display-labels/`에 수록했다. 프로필 전체 본문과 인증 값은 복사하지 않았고, 일부 JSON 사본은 필요한 배포 메타데이터·표시 결과만 남겼음을 파일에 명시했다.

## 5. TEST 단계 배포 및 형상 관리 (이력)

| 항목 | 확정 값 |
| --- | --- |
| 대상 | TEST 16GB Mac 앱, ARM64 |
| 공개 주소 | https://robingraph-test.dove-nest.com |
| 이미지 | `robingraph-api:test-diet-labels-90f9602f3f61` |
| 이미지 ID | `sha256:f3d418c5c3f31aef07604bd1a3614ce26c4fe0c379a75d13185904b7fa696053` |
| release | `diet-labels-90f9602f3f61-3af927` |
| 소스 SHA256 | `90f9602f3f610b5ef21dd802685588c4bd7aaa8a17085ffa1391817696f50146` |
| static chat.js SHA256 | `26a2be811fd1717eed2cb5144177e7b651725a0dc5d465a40297744adbab4466` |
| snapshot 기준 revision | `318e7731fda8b85560b7e8d464b0f4f2c92439d1` — 이번 변경 commit을 뜻하지 않음 |
| 상태 | verified / healthy |
| 환경 보존 | ENV 변경 key는 `ROBINGRAPH_IMAGE` 하나; signing key와 compose 두 파일 보존 |
| 형상 관리 | 이번 commit·push 미실행; Writer는 main-2/dev 문서만 수정 |
| Production | 배포·재시작·DB 쓰기 없음 |

직전 TEST는 `test-notice-ui-dc72ada65dbf`였고 이번 release로 교체됐다. 기존 영수증의 `current_image`는 배포 전 캡처 값이므로 최종 이미지와 혼동하지 않는다.

## 6. 한계 및 후속 과제

- 양성 비율의 기타 고기 표시, 물리 모바일 기기·Safari·Firefox는 이번 실제 검증 완료 범위로 세지 않는다.
- 이번 턴에 앱 소스를 다시 수정하지 않았고 graphify는 앞선 10월 28일 코드 변경 후 성공한 갱신 이력을 사용했다.
- MLflow trace 재조회와 전체 조류 DB checksum 감사는 수행하지 않았다. 표시 변경을 DB 전체 불변 검증으로 확대하지 않는다.
- 간결한 표시명은 새 생물학적 자료나 더 세밀한 먹이 분류가 추가됐다는 뜻이 아니다.
- RG-210 기존 완료 기록은 당시 이력으로 보존한다. 사용자 후속 요청에 따라 RG-407로 신규 등록하고 4xx 인덱스와 기존 2xx 기록을 연결했다. 다른 항목의 상태는 유지한다.

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-먹이-표시명-개선|RG-210 기존 먹이 표시명 개선 이력]]
