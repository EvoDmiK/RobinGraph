# 먹이 답변 타일과 profile 탐색 UI 통일 — Ponytail 협업 및 NAS 배포

## 요청 배경과 목표

사용자는 청둥오리의 먹이 질문 화면에서 각 항목에 같은 긴 출처 링크가 반복되어 읽기 어렵다고 지적했다. 또한 목적별 답변의 `더 알아보기`가 일반 `profile` 소개와 다르게 보이는 문제를 제시했다. 먹이 항목을 읽기 좋은 형태로 바꾸고, 근연종·생태·아종·이름 관계 탐색을 기존 profile UI와 같은 공용 경로로 연결하는 것이 목표다. 사용자가 지정한 Ponytail 방식으로 Claude와 Antigravity가 실제 Orca worker로 참여했다. 앞서 승인된 UI 배포 흐름에 따라 TEST 검증 후 동일 이미지를 운영에 반영했다.

특정 청둥오리 데이터에 대한 예외를 추가하지 않고 공용 프런트엔드 경로를 수정했다. 자료 수집·DB 마이그레이션·IUCN 등급 변경은 이번 작업에 해당하지 않는다.

## 협업 역할과 실제 결과

Orca Run은 `run_01954e83c80b`이다. 기존 dev-codex 작업트리를 공유하되 편집 권한을 분리했다. 새 브랜치를 만들지 않았다.

- Claude: `task_0268a6f66303`, `ctx_54e7fd0babcf`. chat.js·styles.css·프런트엔드 테스트 구현. 301개 모의 DOM 테스트 통과를 보고했다. 구현 보고서는 `/tmp/rg-food-ui-claude-report.md`에 있다.
- Antigravity: `task_abb0995e9370`, `ctx_6409fd0481ca`. 읽기 전용으로 데이터 계약, 공용 호출 경로, 출처 보존, UI와 예외 처리를 독립 검토했다. 보고서는 `/tmp/rg-food-ui-antigravity-review.md`에 있다.
- Codex: 검토 의견의 실제 근거 확인, 먹이 타일 최종 다듬기, 실제 TEST API 응답과 Chrome 화면 검증, TEST·운영 배포, 상세 문서와 Git 반영을 수행했다.

두 worker의 정확한 worker_done을 수신하고 결과를 검토한 뒤 terminal을 release했다. 마지막 reclaimable 조회는 0개였다. 작업 문서와 검증 결과를 에이전트의 완료 주장만으로 대체하지 않았다.

## 확인한 원인

`buildQuestionAnswer`가 모든 `question_answer.items`를 평문 불릿으로 출력하고 각 사실에 `source_name` 링크를 붙이고 있었다. 같은 자료 링크는 이미 메시지의 `species-answer-sources` 패널에서 합쳐지므로 본문에 출처가 반복됐다.

백엔드 `focused_answer`는 먹이 구성의 항목을 만들 때 원래 trait의 `name`, `value` 딕셔너리와 출처 메타데이터를 함께 전달한다. 따라서 화면의 한국어 문장을 다시 파싱하지 않아도 원자료의 비율을 읽을 수 있다. 구성 자료가 없으면 diet_category·trophic_niche를 전달한다.

일반 profile의 근연종 탐색은 `/v1/taxa/similar`를 사용한다. 목적별 답변에는 이 설정과 `result.similar_species` 초기 데이터가 전달되지 않아 공용 빌더의 기본 `/v1/taxa/related` 경로와 “같은 속·과” 문구가 표시됐다. 생태·아종·이름 관계는 이미 공용 빌더를 쓰고 있었다.

## 변경 전후와 구현 파일

### src/robingraph/api/static/chat.js

먹이 질문은 기존 `dietIconInfo`와 `buildDietIcons`를 재사용한다. 출처가 확인된 typed trait에서 먹이 종류·비율을 읽고, 아이콘·항목명·별도의 강조된 비율로 출력한다. 모든 항목의 반복 `먹이:` 접두어를 제거했다. 문장이나 이름에서 비율을 추정하거나 합계 100%로 재정규화하지 않는다. 다른 출처의 구성비도 합산하지 않는다.

비율이 없는 범주 자료는 항목명과 아이콘만 표시한다. 읽을 수 있는 아이콘 자료가 없으면 기존 불릿으로 폴백한다. 다른 목적별 답변도 본문 중복 출처 링크를 제거하고 기존 `답변 출처 보기`에 유지한다. 정량 값을 읽는 방식과 출처 수집 경로는 기존 계약을 따른다.

직접 관계를 묻는 답변은 전달받은 relations의 의미를 보존한다. 그 외 목적별 답변은 profile처럼 `/v1/taxa/similar`와 준비된 similar_species 데이터를 사용한다. 공용 생태·아종·이름 관계 빌더를 그대로 쓰며, 버튼을 누르기 전에 탐색 API를 호출하지 않는다.

### src/robingraph/api/static/styles.css

`question-answer-diet`를 자동 열 수를 정하는 grid로 바꿨다. 넓은 화면에서는 두 개 이상을 나란히, 좁은 화면에서는 한 열로 표시한다. 각 타일에 기존 먹이 색상과 아이콘을 적용하고 둥근 모서리·간격·안쪽 여백을 조정했다. 항목명은 유연한 폭을 사용하고 비율은 오른쪽에서 줄어들지 않도록 했다.

### tests/frontend/chat_ui.test.js

기존 본문 출처 링크 기대를 통합 패널 기준으로 수정했다. 신규 회귀 테스트는 실제 backend 형태의 중복 distribution items에서 한 자료를 한 번 읽어 항목을 만드는지, 35.5% 같은 값을 보존하는지, 미지원 항목을 표시하지 않는지, 출처 링크가 패널에 한 번 남는지 확인한다. 목적별 답변의 공용 탐색 구성·버튼 문구·클릭 전 무요청도 확인한다. 최종 타일의 항목명과 비율을 각각 검증한다.

## 독립 검토 의견의 판정

Antigravity의 반복 접두어·세로 pill 배치에 대한 의견은 수용해 최종 타일 UI에 반영했다. 반면 “Claude가 relatedSlot을 !targeted로 변경해 목적별 탐색을 깨뜨렸다”는 의견은 현재 커밋 전후 비교와 일치하지 않았다. `git show bfcd2e8^:.../chat.js`에서도 같은 !targeted 조건이 존재했고 이번 diff에는 그 조건 변경이 없다. 목적별 화면에는 실제 탐색 버튼이 있으며 클릭 시 /v1/taxa/similar를 요청한다. TEST와 운영에서 실제 API 응답뿐 아니라 “비교할 새를 선택하세요” 상태와 similarity-evidence 후보 렌더링까지 확인했다. 이 의견을 확인된 회귀로 기록하거나 기존 지연 로딩을 변경하지 않았다.

목적별 답변에도 사진 미리보기를 추가하자는 의견은 별도의 개선 제안으로 분류했다. 이번 사용자의 통일 요청은 `더 알아보기` 인터페이스에 대한 것이므로 모든 목적별 답변을 전체 profile 소개로 바꾸지 않았다. 원래 일반 소개의 사진 미리보기와 목적별 답변의 카드 진입 동작을 유지했다.

## 실행한 검증과 실제 결과

- `node --test tests/frontend/*.test.js`: 최종 코드에서 301개 통과, 실패 0, 취소 0, 건너뛰기 0. fake DOM 검증이며 실제 DB 테스트로 표현하지 않는다.
- 실제 TEST `/v1/chat`에서 청둥오리 먹이, 까치 먹이, 원앙 서식, 청둥오리 profile 응답을 받았다. 청둥오리는 구성비, 까치는 정량 비율 없는 범주 자료라 서로 다른 경로를 확인했다.
- 위 실제 응답을 재생하고 로컬 JS/CSS를 적용한 Chrome에서 320·390·768·1280px × 4응답 = 16사례 통과. 탐색 구성·먹이 UI·본문 중복 링크 없음·가로 넘침 없음·탐색 버튼 클릭 전 /v1/taxa 요청 없음·페이지 오류 0을 확인했다.
- TEST와 운영 각각 배포된 자산으로 같은 16사례를 통과했다. 이 32사례는 채팅 응답을 재생한 UI 검증이며, DB와 LLM을 새로 호출한 사례로 세지 않는다.
- 별도로 응답을 가로채지 않은 실제 UI에서 TEST·운영 각각 390·1280px × 3질문 = 6흐름씩, 총 12흐름 통과. 질문 전송 → 목적별 답변 → 더 알아보기 → 키보드 Enter로 근연종 버튼 → 실제 /v1/taxa/similar HTTP 200 → 후보와 상태 렌더링까지 확인했다. 페이지 오류 0.
- TEST·운영의 공개 chat.js·styles.css 바이트가 로컬 최종 코드와 일치한다. 실제 /health와 profile 질문의 종·영문명도 확인했다.
- `graphify update .`를 변경 뒤 실행했다. 최종 그래프 5,084 nodes, 10,566 edges, 321 communities. SQL 파서가 설치되지 않은 일부 SQL은 AST 추출 경고가 있었으며 이번 수정은 JS/CSS다.

검증 도중 브라우저 도구의 출처 selector를 `.answer-sources`로 잘못 지정한 assertion이 한 번 실패했다. 실제 클래스 `.species-answer-sources`로 도구를 수정하고 최종 16사례 전체를 다시 통과했다. 배포 환경 준비 도구도 처음 POSTGRES_DB라는 잘못된 키를 가정해 실제 API 교체 전에 중단됐고, 저장소의 ROBINGRAPH_PG_DATABASE를 확인한 뒤 TEST/운영 격리를 검사해 해결했다. 두 오류 모두 제품 코드나 DB 데이터 변경 실패가 아니다.

검증 JSON은 `docs/verification/assets/2026-10-10-food-ui-{local,test,prod}.json`, `2026-10-10-food-ui-live-{test,prod}.json`, `2026-10-10-food-ui-{test,prod}-assets.json`이다. 화면 증거는 `/tmp/rg-answer-names-browser/food-{local,test,prod}-{variant}-{width}.png`이며 브라우저 실행 도구도 같은 임시 디렉터리에 있다.

## 패키징·NAS 배포·Git

최초 구현 bfcd2e8, 디자인 검토 반영 최종 앱은 `2ee9318948ab29383014add34efceb09ae101ebc`다. 두 커밋 모두 origin/dev-codex에 push했다. main/dev 병합은 별도 지시를 따른다.

표준 `package_nas_release.sh`로 최종 커밋의 런타임 허용 목록만 패키징했다. 아카이브 SHA-256은 `546e9b9e4dffca3dbad09a09e696c9fc5877f6ef492d1aa778dfa4f83884ad0b`다. SSH 바이트 전송 후 NAS에서 아카이브와 MANIFEST 파일별 해시를 검증했다. 기존 환경 파일은 NAS 안에서 복사하고 이미지·revision만 바꿨다. TEST PG robingraph_test, 운영 robingraph 격리를 확인했다. 인증 정보는 출력하거나 문서에 포함하지 않았다.

릴리스 경로는 `/home/kimdove/RobinGraph-food-ui-2ee9318`이다. TEST에서 표준 preflight → deploy → verify를 통과했다. buildx 미설치 경고는 있었으나 classic builder로 정상 빌드됐다. 공개 자산·UI·실제 API 검증 후 동일 이미지에 운영 태그를 붙여 `up -d --no-build api`로 운영 API만 교체했다.

- TEST: `robingraph-api:test-food-ui-2ee9318`, 시작 2026-10-10T05:10:42.209545816Z.
- 운영: `robingraph-api:prod-food-ui-2ee9318`, 시작 2026-10-10T05:12:57.867612805Z.
- 동일 이미지: `sha256:c32be224b61c44b2cd2425f69fcf765e3d065182a9b892f2b0540bccf70b8226`.
- 마지막 확인에서 두 컨테이너 healthy, restart count 0. 운영 preflight·verify 통과.

이전 운영 prod-answer-preview-0df2b1b 이미지를 보존하고 실패 시 rollback을 준비했다. 정상 완료되어 rollback은 실행하지 않았다. DB 수집·이관·스키마 변경은 없다. 상세 문서와 JSON은 별도 기록 커밋으로 dev-codex에 반영하며 앱 이미지는 문서 커밋으로 재빌드하지 않는다. Obsidian 작업기록에도 같은 본문을 저장하고 읽어 원문과 비교한다.

## 확인하지 않은 범위와 남은 한계

전체 종의 실제 HTTP 요청, 물리 모바일 기기·iOS Safari, 전체 백엔드 테스트·새 CI는 실행하지 않았다. 목적별 related/ecological_related의 직접 답변과 기존 보안·접근성·카드 동작은 프런트엔드 회귀 범위에서 검증했고, 이번 실제 UI 질문은 먹이와 서식에 집중했다.

기존 먹이 아이콘 정책에 따라 일부 척추동물 하위 범주는 척추동물로 합쳐지고, 여러 자료가 있으면 첫 유효 구성 자료를 표시한다. 원래 범주·자료 의미는 출처와 카드에서 확인할 수 있다. 이번 화면 개선을 새 생태 데이터 수집이나 모든 자료 공백 해소로 안내하지 않는다. 정량 자료가 없는 종에는 임의 비율을 만들지 않는다.
