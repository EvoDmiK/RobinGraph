---
created: 2026-10-23
date: 2026-10-23
project: RobinGraph
type: worklog
status: in_progress
task_id: RG-212
tags: [worklog, robingraph, ui, ecology]
---

# [RG-212 후속] 생태 관계 답변 레이아웃 정리 — 2026-10-23

## 요약

사용자는 의미·이름 확인 뒤 나온 생태 관계 답변 화면의 디자인 개선을 요청했다. 종 목록이 문장 목록과 탐색 영역에 반복되고, 긴 설명·출처·도감 버튼·탐색 버튼이 한 말풍선에 이어져 핵심 결과를 읽기 어려웠다. 기존 생태 탐색 컴포넌트를 재사용해 답변 안에 결과를 한 번만 보여 주고, 비교 범주·종별 비교 버튼·접힌 출처 순서로 정리했다.

이번 변경은 프런트엔드 표시와 관련 검사에 한정한다. 생태 범주가 같다는 근거를 실제 공존·포식·동일 먹이 종의 증거로 확대하지 않으며, 검색·질문 해석·API·조류 DB를 바꾸지 않았다. RG-212의 전체 자연어 일반화는 여전히 진행 중이다.

TEST 이미지 `robingraph-api:test-ecology-layout-d1958a21194a`에 반영했다. 프런트엔드 모의 DOM 검사 318개가 통과했고, 공개 TEST Chromium에서 핵심 8흐름·20회 채팅 요청과 추가 320px 밝은/어두운 화면 2건을 확인했다. 최종 답변의 관계 범주와 3개 종 행, 중복 제거·출처 키보드 조작·실제 비교·도감 팝업을 검증했다. Production 변경과 Git commit·push는 수행하지 않았다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| 원인 규명 / 요구사항 | 생태 답변의 중복·밀도 개선 | 요약 목록과 생태 탐색 결과가 중복되고 여러 행동 버튼·출처가 한 화면에 쌓임 |
| 설계 및 해결 방안 | 기존 탐색기 inline 재사용 | 새 컴포넌트·API 없이 유효한 관계 결과를 한 카드 안에서 표시 |
| 코드 / 설정 수정 | JS·CSS·프런트엔드 검사 | `chat.js`, `styles.css`, `chat_ui.test.js` |
| 실서비스 배포 | Mac TEST 앱 | `test-ecology-layout-d1958a21194a`, Production 미반영 |
| 검증 및 테스트 | 모의 DOM 318개·실제 브라우저 8+2개 통과 | 390/1280px 확인 흐름, 320px 밝은/어두운 화면; 오류·넘침 0 |
| 형상 관리 | `dev-codex` 미커밋 snapshot | 기존 변경 보존, commit·push·merge 미실행 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

- 사용자가 제시한 화면에는 “청둥오리 · 생태가 비슷한 종” 제목 뒤 설명과 종별 글머리 목록, 큰 도감 버튼, 같은 내용을 다시 여는 탐색 버튼, 출처와 비교 결과가 이어졌다.
- 관계 결과가 이미 답변에 포함되어도 일반 프로필용 탐색 UI가 별도로 붙어, 같은 목록과 안내를 다시 읽어야 했다.
- 요구사항은 이 결과 화면의 디자인 정리다. 질문 해석 범위 확대, DB 갱신, 운영 배포는 이번 범위에 포함하지 않는다.

### 원인 분석 / 설계 검토

기존 `buildQuestionAnswer`의 문장·글머리 결과와 `buildEcologicalExplorer`의 상세 탐색 결과가 함께 렌더링됐다. 일반 도감에서 접어서 여는 탐색기는 유효하지만, 이미 생태 관계를 물은 답변에서는 열기 버튼과 중복 안내가 불필요하게 길이를 늘렸다.

단순히 기존 문장을 먼저 지우면 구조화 자료가 비었거나 버전이 달라졌을 때 설명까지 사라질 수 있다. 따라서 지원되는 관계 그룹의 렌더링이 성공한 뒤에만 중복 문장·목록을 제거한다.

---

## 2. 해결 방안 및 설계

1. 생태 관계 직접 답변에 기존 탐색기를 inline 모드로 넣는다. 일반 프로필의 탐색 버튼은 기존 동작을 유지한다.
2. “같은 먹이 생태” 또는 “같은 서식 환경” 제목 옆에 자료의 범주를 배지로 보여 준다. 종별 이름·학명과 기존 비교 버튼은 정돈된 행으로 표시한다.
3. “비교 기준과 출처”는 기본적으로 접고, 분류 기준과 각 종의 생태·이름 근거를 그 안에 보존한다.
4. 동일 범주가 실제 공존·먹이 관계를 뜻하지 않는다는 안내는 한 번 표시한다. 큰 도감 버튼은 보조 행동으로 축소한다.
5. 비어 있거나 오래된 구조화 근거에서는 원래 설명·항목을 보존한다. 대화 변경·분류 버전·종 일치 검사와 기존 비교 동작을 재사용한다.

새 디자인 라이브러리나 네트워크 요청은 추가하지 않았다. 기존 색상 변수와 비교 행·안전 링크·키보드 버튼을 재사용해 범위를 줄였다.

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

- `src/robingraph/api/static/chat.js` — 생태 탐색기의 inline 옵션, 범주 배지, 출처 묶음, 성공 후 중복 설명 제거, 도감 버튼의 보조 표시.
- `src/robingraph/api/static/styles.css` — 직접 답변 카드와 종 행의 여백·위계·배경, 접힌 출처의 포커스 표시, 480px 이하 화면 조정.
- `tests/frontend/chat_ui.test.js` — 직접 답변의 중복 제거·근거 보존·기존 비교 동작 검사와 빈/오래된 구조화 자료에서 원래 설명 유지 검사.
- `docs/verification/assets/2026-10-23-ecology-answer-layout/` — 변경 전후 화면, 프런트엔드 검사, TEST snapshot·배포, 브라우저 검증 근거.
- `graphify-out/` — 코드 변경 후 그래프 갱신. 생성 자료의 기존 변경은 보존한다.

### 핵심 코드 / 설정 스니펫

```javascript
if (directEcological && targeted) {
  ecologicalOptions.inline = true;
  ecologicalOptions.onRendered = function () {
    Array.from(targeted.children).forEach(function (child) {
      if (child.tagName.toLowerCase() === "p" || child.className === "question-answer-facts") {
        targeted.removeChild(child);
      }
    });
  };
}
```

위 콜백은 유효한 생태 그룹이 렌더링된 뒤 호출된다. 자료가 없거나 버전이 어긋나면 설명을 지우지 않는다. API 응답·서버 설정 변경은 해당하지 않는다.

---

## 4. 검증 및 테스트 결과

### 자동화 테스트 (단위 / 회귀)

| 구분 | 실제 실행 / 결과 | 검증 범위 |
| --- | --- | --- |
| 프런트엔드 단위·회귀 | `node --test tests/frontend/chat_ui.test.js` — 318 통과 / 0 실패 / 0 건너뜀 | 모의 DOM·API 검사이며 실제 DB 결과 검증과 구분 |
| 코드 그래프 갱신 | `graphify update .` — 종료 코드 0 | AST 기반 그래프 갱신, 기능 테스트 아님 |
| TEST 이미지 smoke | 네트워크 없는 fixture smoke 통과 | 실제 DB 검증 아님; `test-release.json` 영수증 |
| 변경 공백 검사 | `git diff --check` — 통과 | whitespace 검사이며 기능 검증 아님 |

프런트엔드 검사는 중복 목록과 열기 버튼 제거, 범주·출처 링크 보존, 영어 이름 fallback, 추가 생태 API 호출 없이 initialData 재사용, 비교 동작을 확인한다. 추가 회귀는 `concept_set_id`가 오래되거나 `groups`가 빈 경우 원래 설명·항목을 보존하는지 확인한다.

### 실서비스 / UI 검증 증거

검증 대상은 `https://robingraph-test.dove-nest.com/chat`의 새 이미지다. Codex가 실제 실행하고 제출한 `summary.json`, `browser.json`, `compact.json`, `runtime-verification.json`을 Writer가 조회해 기록했다. Writer가 별도로 테스트를 재실행한 것은 아니다. 이전 작업의 브라우저 성공을 이번 결과로 재사용하지 않았다.

| 실제 공개 TEST 시나리오 | 결과 | 근거와 구분 |
| --- | --- | --- |
| 390/1280px × 청둥오리/천둥오리 × 식성·먹이/서식 환경 | 8/8 흐름 통과, 채팅 POST 20회 | 의미 확인 → 오타이면 종 확인 → 최종 answer; 요청한 관계 범주 일치, 종 행 각 3개 |
| 결과 중복·불필요한 버튼 제거 | 8/8 확인 | `.question-answer-facts` 없음, 중복 탐색 열기 버튼 숨김, 유효한 종 행 표시 |
| 출처 접기/펼치기 키보드 | 8/8 확인 | 기본 접힘, summary에 포커스 후 Enter로 열기·닫기, 출처 링크 존재 |
| 실제 종 비교 | 1/1 확인 | 1280px 청둥오리 먹이 결과에서 비교 버튼에 포커스·Enter, 실제 API 후 비교 메시지 표시 |
| 도감 팝업 | 1/1 확인 | 같은 시나리오에서 열기·Escape 닫기 |
| 320px 밝은/어두운 화면 | 2/2 확인 | 실제 API 응답 사용; 페이지·카드 가로 넘침 없음, 비교 버튼 약 66.66×44px |
| 런타임·가로 넘침 | 오류 0, 넘침 0 | 모든 위 시나리오의 pageerror와 viewport 검사; 콘솔 전체 이벤트 검사가 아님 |

브라우저 스크립트는 `node docs/verification/assets/2026-10-23-ecology-answer-layout/browser.cjs`이며 실제 HTTP 응답을 사용한다(`response_mocking: false`). `reducedMotion: reduce`로 검증했다. 320px 추가 검사의 수치 영수증은 `compact.json`에 보존했다. 공개 API가 실제 결과를 반환한 검증이며 독립 DB 재질의·자료 재감사는 수행하지 않았다.

변경 전 `before-1280.png`, `before-390.png`와 변경 후 각 이름·관계·폭의 PNG를 같은 증거 폴더에 저장했다. Codex는 최종 1280px·390px·320px 어두운 화면을 직접 열어 시각적으로 확인했다. 자동 수치 검사와 Codex의 스크린샷 시각 검토 범위를 구분하며, 사용자의 디자인 검토는 아직 받지 않았다.

이번 UI 변경에서 백엔드 전체 검사와 전체 의미 평가셋은 재실행하지 않았다. 검색·API 구현을 바꾸지 않았기 때문이며, 자연어 전체 품질이 확인됐다고 해석하지 않는다.

---

## 5. 배포 및 형상 관리

- **대상 환경**: 16GB Mac TEST 앱·빌드, 공개 URL `https://robingraph-test.dove-nest.com/chat`. Neo4j·n8n은 32GB Mac, PostgreSQL은 NAS의 기존 배치를 유지한다.
- **이미지**: `robingraph-api:test-ecology-layout-d1958a21194a`.
- **소스 SHA256**: `d1958a21194a6da8f91db884cc9b5418fdbd31c55eed18609fe6169a9d5cf0b8`.
- **릴리스 경로**: `/Users/kimdove/robingraph-test/releases/taxonomic-traits-d1958a21194a-fc233d`.
- **이전 이미지**: `robingraph-api:test-taxonomic-traits-8a18de290625`.
- **Git 브랜치**: `dev-codex`.
- **기준 커밋**: `834c5353ca45f0640152ca4849548cd48818b266`. 이번 변경을 커밋한 해시가 아니라 미커밋 snapshot의 기준이다.
- **원격 반영**: commit·push·merge 미실행. 별도 요청이 없으므로 기존 미커밋 변경을 보존했다.
- **배포 증거**: `test-release.json`은 `target: test`, `state: verified`, `fixture_network_none_smoke: true`, `release_source_manifest_verified: true`, `production_changed: false`를 기록한다.
- **최종 런타임 확인**: `runtime-verification.json`에서 컨테이너 healthy, 현재 워크스페이스·릴리스의 208개 소스 파일 일치, `GRAPH_INTENT_MODE=active`, `DEPLOY_TARGET=test`, `GRAPH_INTERPRETER=semantic`을 확인했다.
- **배포 차이 확인**: `changed-image-files.json`에서 이전 208개 파일 manifest와 대조한 차이는 `chat.js`, `styles.css` 두 파일뿐이다. 백엔드·데이터·설정의 이미지 차이는 없다. `ui.patch`에는 프런트엔드 검사까지 포함한 이번 작업 diff를 보존했다.
- **운영 및 데이터**: Production 배포·재시작·이미지 교체·운영 DB 변경 없음. 이번 작업에서 조류 데이터 변경이나 DB 쓰기 검증을 수행하지 않았다.

---

## 6. 한계 및 후속 과제

- 생태 범주 일치는 같은 실제 먹이 종을 먹는다는 증거나 같은 장소에서 공존한다는 증거가 아니다. 기존 자료 한계와 출처를 화면에 보존했다.
- RG-212는 진행 중이다. 앞선 의미 해석의 false hold·복합 조건 확인 메시지 한계는 이번 UI 정리로 완료 처리하지 않는다.
- 물리 모바일·Safari·Firefox는 미검증이다. 브라우저 자동화의 작은 viewport를 실기기 검사로 표현하지 않는다.
- 이 기록은 UI 후속 범위의 TEST 검증 완료를 뜻한다. 상위 RG-212의 상태는 `in_progress`로 유지하며 새로운 NLP 완료 판정을 만들지 않는다.
- 저장소 반영용 scratch와 동일한 본문을 Obsidian에 저장한 뒤 재조회로 일치를 확인했다. 2xx 작업기록 목록에는 이 문서 링크만 추가하고 기존 본문을 보존했다. 전체 백로그의 RG-212 상태는 변경하지 않았다. 저장소 반영은 Codex 최종 검토 후 수행하며, Writer는 앱·테스트·환경 파일을 직접 수정하지 않았다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/작업 백로그|2xx 작업기록 목록]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-23-오타와-의미-확인-후-관계-조회|선행 오타·의미 확인 후 관계 조회]]
