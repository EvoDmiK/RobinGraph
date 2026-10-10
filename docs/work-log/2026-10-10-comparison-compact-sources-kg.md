# 비교 화면 하단 정리·kg 단위 통일·출처 카드 — TEST 전용

## 요청 배경과 목표

사용자가 청둥오리·흰뺨검둥오리 비교 화면에서 1156 g 표기와 도감 버튼 아래 반복되는 탐색·추천 내용을 지적했다. 처음에는 도감 버튼까지 표시하도록 요청했고, 바로 이어 답변 출처까지 남기도록 수정했다. 추가로 51개 링크를 가진 출처 토글의 긴 평문·파란 링크·자료 코드가 읽기 어렵다고 지적했다. 이 세 요청을 하나의 비교 UI 수정으로 처리했다.

목표는 비교표 → 주의 문구 → 가로 도감 버튼 → 답변 출처의 흐름이다. 도감 카드와 같은 질량 표시 기준을 사용하고, 출처를 읽기 쉬운 카드로 만들되 자료와 검증 근거를 삭제하지 않는다. 운영 배포는 변경별 명시적 승인 전까지 금지한다는 사용자 지시에 따라 이번 작업은 TEST에만 배포했다.

## 확인한 원인과 근거

비교표는 cardTraitValue를 사용하지 않고 trait.display에 unit을 직접 붙였다. 그래서 같은 자료가 도감에서는 kg, 비교에서는 g으로 나타났다. buildSpeciesComparison은 도감 버튼 뒤에 related·ecological explorer를 추가했다. 후보 선택 이후에는 선택한 후보의 추천 카드, 관계 문장, 분류 버전까지 삽입되어 비교 답변을 길게 만들었다.

통합 출처 수집기는 원자료별 제목·링크·라이선스·릴리스·인용·분류 대응 검증 내용을 최상위 details 안으로 그대로 복사했다. 중복 링크 제거는 이미 있었지만, 세부 메타데이터를 처음부터 전부 보여줘 자료 수가 많은 비교는 길고 복잡했다. 실제 TEST 채팅과 profile API를 이용해 동일 흐름을 재현했다.

## 변경 파일과 구현 내용

`src/robingraph/api/static/chat.js`:

- 비교 체중에도 기존 cardTraitValue를 적용한다. 1000g 이상은 소수 둘째 자리 kg, 그 미만은 g이다. 실제 예시는 1156g → 1.16kg, 843.42g → 843.42g이다. 추정값·표본 평균·문헌 범위 평균 표기를 유지한다. 원자료의 수치와 단위를 DB에서 바꾸지 않는다.
- 비교 내부의 추가 탐색을 제거했다. 같은 속·과, 생태 탐색은 원래 종 답변에서 계속 사용할 수 있다. 가로 도감 버튼 배치는 유지했다.
- 선택한 추천 카드와 별도 관계·버전 표시를 비교 본문에서 제거했다. 선택 순위·점수·점수 해석, 관계와 분류 버전은 출처 자료에 보존한다. 일반 가중 점수와 분류·생태 대체 점수 문구도 보존한다.
- 기존 buildCombinedAnswerSources에 비교용 compact 모드를 추가했다. 원자료를 안전하게 복사하고 같은 URL·동일 문맥 행을 제거하는 기존 처리를 먼저 실행한 뒤, 제목별 section에 묶는다. 항목 제목과 자료 이름 링크를 먼저 표시한다. 릴리스 코드·라이선스·인용·분류 대응·검증 설명은 기본적으로 닫힌 `자료 상세 정보`에 넣는다. 직접 제목이 없는 추가 자료도 제목을 붙여 접는다.
- 기존 profile 등의 출처 수집 호출은 compact 모드를 선택하지 않아 이번 디자인 변경의 적용 범위는 비교 답변이다. innerHTML이나 새 의존성을 사용하지 않으며 링크 안전성·새 창 rel 정책·후속 카드 출처 갱신을 유지한다.

`src/robingraph/api/static/styles.css`: 비교 출처를 밝은 배경, 둥근 테두리, 작은 제목, 녹색 링크, 보조 상세 토글로 구성했다. 긴 URL·코드·이름은 줄바꿈하며 색상은 기존 테마 변수를 사용한다.

`tests/frontend/chat_ui.test.js`: 이전의 비교 내부 탐색 및 선택 카드 기대를 새 요구사항에 맞게 변경했다. 추가 회귀로 g/kg, 가로 도감 버튼 다음 마지막 자식이 출처인지, 출처 카드·링크 유지, 메타데이터 기본 접힘, 원자료 릴리스 보존과 URL 중복 제거를 확인한다. 앞선 비교값 중복 제거 회귀도 유지했다.

## 검증 방법과 실제 결과

`node --test tests/frontend/chat_ui.test.js`: 300개 통과, 실패·취소·건너뛰기 0. 이어 `node --test tests/frontend/*.test.js`: 303개 통과, 실패·취소·건너뛰기 0. 이 결과는 fake DOM·단위 회귀이며 실제 DB/API 검증으로 계산하지 않는다. 최초 실행에서는 기존 비교 내부 탐색을 기대하던 세 테스트가 실패했다. 요청에 맞게 해당 기대를 변경했다. 신규 테스트의 release 객체 구성에서 공통 fixture가 값을 덮어써 한 번 실패했고 객체 순서를 수정한 뒤 전체 통과했다.

Chrome 390·1280px에서 실제 TEST에 청둥오리 먹이 질문 → 더 알아보기 → 근연종 조회 → 첫 후보 비교를 실행했다. 로컬 최종 JS/CSS를 라우팅한 2흐름에서 실제 API는 그대로 호출했다. 비교표 중복값 없음, 셀별 출처 토글 없음, 1.16kg, 하단 두 요소가 도감 버튼·답변 출처임, 반복 탐색과 선택 카드 없음, 자료 상세 기본 접힘·클릭 열림, 가로 넘침 없음, 페이지 오류 0을 확인했다. 모바일 스크린샷을 직접 열어 카드 구획·색·줄바꿈도 확인했다.

배포된 TEST의 최종 JS/CSS에서도 동일한 실제 채팅·후보 선택·비교 390·1280px 2흐름이 모두 통과했다. 페이지 오류 0, 가로 넘침 없음, 1.16kg, 하단 버튼·출처 순서와 상세 토글 동작을 다시 확인했다. 별도 공개 자산 검증에서 chat.js·styles.css가 로컬 최종 파일과 바이트 단위로 일치했다. health와 실제 청둥오리 profile 질문도 정상이며 학명 Anas platyrhynchos와 영문명 Mallard가 반환됐다.

검증 파일은 `docs/verification/assets/2026-10-10-comparison-compact-local.json`, `2026-10-10-comparison-compact-test.json`, `2026-10-10-comparison-compact-test-assets.json`이다. 브라우저 실행 도구와 스크린샷은 `/tmp/rg-answer-names-browser/comparison-compact.cjs`, `comparison-compact-{local,test}-{390,1280}.png`에 있다. 이전 검증 파일은 덮어쓰지 않았다.

`git diff --check` 통과. `graphify update .` 완료: 5111 nodes, 10596 edges, 308 communities. SQL 파서 미설치로 4개 SQL 추출이 생략된 기존 경고가 있다. 이번 작업은 JS/CSS이며 SQL은 수정하지 않았다.

## 배포·Git 정보와 운영 보존

앱 커밋은 `d5ff022d8f1064b0ff000112fe6d296b564f419e`, origin/dev-codex에 push했다. 표준 NAS release package SHA-256은 `227212f9c63c355ba36e79b6a81fed54d6417ecdcf290187e459f3ca5211b221`이며 NAS에서 아카이브 해시를 검증한 뒤 추출했다. TEST 환경만 이전 TEST 릴리스에서 복사하고 DB가 robingraph_test인지 확인했다. 인증 정보는 문서에 포함하지 않는다.

TEST 릴리스 `/home/kimdove/RobinGraph-comparison-compact-d5ff022`에서 ROBINGRAPH_DEPLOY_TARGET=test로 표준 preflight → deploy → verify를 통과했다. buildx 미설치 경고 후 classic builder가 정상 완료했다.

- 이미지: `robingraph-api:test-comparison-compact-d5ff022`.
- 이미지 ID: `sha256:906f7a0df18cdf521052a42e40b9d3fbc20a169a44c276b3d453c3a3f94a194b`.
- TEST 시작: 2026-10-10T05:51:44.172698534Z, healthy.
- 확인 URL: https://robingraph-test.dove-nest.com/chat.

배포 전후 운영 컨테이너 ID·이미지·시작 시각이 모두 동일함을 실제 docker inspect 결과로 확인했다. 운영은 prod-food-ui-2ee9318을 유지한다. 운영 환경·Compose·DB에는 변경 작업을 실행하지 않았다. main/dev 병합도 하지 않았다. 검증 결과와 상세 문서는 별도 후속 기록 커밋으로 dev-codex에 올리고 Obsidian 작업기록에 같은 본문을 저장한다.

## 남은 한계와 후속 사항

물리 모바일 기기·iOS Safari·전체 종 HTTP·전체 backend 테스트·CI는 이번 수정에서 실행하지 않았다. 브라우저 실제 API 흐름은 가중 점수 후보를 확인했으며 대체 점수 문구 보존은 기존 frontend 회귀로 검증했다. 출처 51 표기는 중복 제거한 고유 URL 수이며 모든 링크가 즉시 보이는 카드 수는 아니다. 같은 URL은 한 번만 링크로 남고 다른 주장 문맥에서는 이름과 설명이 유지된다. 여러 출처의 서로 다른 자료는 접혀 있을 뿐 삭제하거나 하나의 평균으로 합치지 않는다. kg 표시는 기존 카드와 동일하게 둘째 자리 반올림이며 원래 g 수치는 상세 출처에서 확인할 수 있다. 운영 배포는 이 변경에 대한 명시적 승인 이후 별도로 수행한다.
