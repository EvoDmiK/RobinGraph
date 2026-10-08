# 비교 후보 카드와 분류 계통 화면 정리

작성일: 2026-10-08. 대상: NAS TEST. 사용자의 비교 후보·분류 계통 표시 개선 요청을 함께 반영했다. 이번 작업은 표시와 조작 개선이며 서버의 후보 선택·점수 계산·계통 데이터는 변경하지 않았다.

## 요청 배경·확인한 원인

비교 후보는 긴 가중치 설명과 순위별 한 줄 문장으로 표시됐고, 그 아래 펼쳐진 비교 탐색기에 같은 후보가 다시 나왔다. `buildQuestionAnswer`의 fact 목록과 `buildRelatedExplorer`가 같은 결과를 각각 출력하는 것이 중복 원인이었다. 실제 NAS에서 청둥오리 질문으로 Indian Spot-billed Duck 100점, 흰뺨검둥오리 98.28점, Philippine Duck 96.55점을 확인했다.

분류 응답은 `answer-metadata`와 `resultSummaryLines`가 개념집합·분류명·출처를 긴 문장으로 연결했다. 목→과→속→종 구조를 한눈에 보기 어려웠고, 국명 출처를 모두 Wikidata로 표시하던 코드 때문에 한국조류학회 링크에도 잘못된 링크 이름이 붙었다. 실제 흰뺨검둥오리 계통은 목·과·속이 Wikidata 참고 국명이고, 종은 별도 원자료 국명 출처였다.

## 변경 전후 동작·구현

- 직접 비슷한 종을 묻는 지원 랭킹 응답은 **TOP3 카드 한 벌**을 즉시 표시한다. 순위 배지, 국명 또는 출처의 영어 이름, 학명, 큰 점수, 짧은 근거 태그 최대 3개, 점수 기준, ‘비교하기’, 접힌 상세 근거·출처를 분리했다. 전체 근거·관련 연구·상충 연구 안내·대상 생태 출처는 상세에 보존했다.
- 중복 제거는 `related` 주제이면서 기존 지원 ranking.method v1/v2/v3·limit=3인 경우에만 적용한다. 같은 속·과의 비랭킹 질문, 생태·아종 질문, 일반 소개의 ‘더 알아보기’ 지연 탐색은 유지했다. 순위 정렬·최대 3개·유한 점수 검증·종 ID/개념집합/분류판 대조도 유지했다.
- 점수는 원래 값을 그대로 `점`으로 표시하며 확률·실제 진화 거리로 표현하지 않는다. 계통 자료 부족 시 분류·생태 대체 점수임을 구분한다. 비교 버튼은 기존의 종별 중복 클릭 방지·실패 재시도·대화 초기화 후 무효화·새 비교 말풍선 흐름을 사용한다.
- 분류 답변은 API 배열 순서의 `ol` 세로 목록으로 목→과→속→종을 표시한다. 분류 단계 배지, 국명, 학명, 영어 rank를 구분하고 마지막 조회 분류군을 강조한다. 분류 출처·릴리스는 상단, 긴 개념집합 ID는 접힌 ‘분류 기준 상세’로 옮겼다. 원래 `answer_text`는 유지하므로 ‘무슨 과인가요’에 대한 실제 답변도 보인다.
- community-sourced/community-sourced-reference만 ‘참고 국명’으로 표시하며 source-reference는 ‘국명’으로 표시한다. machine-translated 이름은 주표시로 쓰지 않는다. 국명 출처 URL을 정제하고 정확한 Wikidata 호스트에만 Wikidata 라벨을 사용한다. 빈 목록·알 수 없는 rank·아종·국명 없음도 처리한다. `resultSummaryLines`의 기존 외부 함수 계약은 유지했다.
- 실화면 QA에서 전역 스타일이 영어 이름을 강제 대문자·흐린 색으로 만드는 것과 마지막 분류군 강조 배경이 부모와 겹치는 것을 확인했다. 원래 대소문자와 본문 색을 적용하고 마지막 분류군에 별도 표면색·테두리를 추가했다.

변경 파일은 `src/robingraph/api/static/chat.js`(구조화 렌더링·중복 제거), `src/robingraph/api/static/styles.css`(카드·계통·반응형·가독성), `tests/frontend/chat_ui.test.js`(기존 회귀 수정 및 새 계약 검증)다. `docs/jev-intent-routing.md`에 표시 형식과 이 기록 링크를 추가했다. Python·DB·환경 변수는 변경 대상이 아니었다.

## 협업·독립 검토

`progressive_chat_ui`가 JS/CSS/프런트엔드 테스트를 구현했다. 주 담당이 실제 NAS의 변경 전 응답·화면을 확보하고 통합 검증·시각 QA·가독성 후속 조정·NAS 배포·문서화를 담당했다. `progressive_review`는 두 UI의 읽기 전용 독립 검토와 전체 프런트엔드 실행을 수행했으며, 출처 상태와 분류 순서·비교 보호를 확인했다. 배포 차단 문제는 발견하지 않았다. 별도 증거가 없는 실행 모델 이름은 추정하지 않는다.

## 검증 범위·실제 결과

`node --test tests/frontend/*.test.js`: **164개 통과, 실패 0, 건너뛰기 0**. 주 담당·UI 담당·독립 검토에서 확인했다. DOM·HTTP 모의 회귀로 직접 랭킹 한 벌, 비교 말풍선, 잘못된 분류판 차단, 점수·영어 이름·안전한 출처, 분류 순서/상태/빈 데이터/중복 제거를 검증했다. 후속 CSS 조정은 실제 브라우저의 대소문자 스타일과 마지막 분류군 테두리를 추가 확인했다. Python 코드는 바뀌지 않아 전체 Python을 다시 실행하지 않았다. 이전 작업의 608개 통과와 이번 실행을 혼동하지 않는다.

실제 NAS TEST 공개 주소의 Chrome·Playwright에서 390px와 900px 각각 비교 후보·분류 질문을 실행했다. HTTP를 모의하지 않고 실제 API/DB를 사용했다.

| 흐름 | 실제 결과 |
|---|---|
| 청둥오리와 비슷한 새 알려줘, 390/900px | 카드 총 3개, 기존 문장 목록 중복 0, 순위·종 ID·100/98.28/96.55점이 변경 전 API와 일치 |
| 비교 후보 근거 펼치기 | 각 카드 상세는 처음 접힘, 펼치면 원출처 링크 확인; 서버 제공 랭킹 재조회 0건 |
| 첫 후보 비교하기, 390/900px | 실제 프로필 API 호출 후 새 비교 말풍선 생성, 원래 카드 3개 유지, Indian Spot-billed Duck·100점 근거 유지 |
| 흰뺨검둥오리 분류 알려줘, 390/900px | 변경 전 계통 API와 완전히 일치, 목/과/속/종 순서와 기러기목/오리과/오리속/흰뺨검둥오리 표시 |
| 국명·분류 상세 | Wikidata 3개/별도 국명 출처 1개를 올바른 링크로 표시, 개념집합은 처음 접히고 펼치면 보존된 값 표시 |
| 흰뺨검둥오리는 무슨 과인가요, 900px | “흰뺨검둥오리의 과 분류는 오리과(Anatidae)입니다.” 문장을 그대로 표시 |

모든 흐름에서 JS 예외 0건·가로 넘침 없음이 확인됐다. 390/900px 비교 후보와 분류 화면을 시각 확인했다. 채팅 내부 스크롤 때문에 한 스크린샷에는 목록 일부만 보일 수 있으며 전체 카드/항목 검증은 DOM과 API를 함께 대조했다. 모바일 폭의 데스크톱 Chrome 시험이며 실제 모바일 터치 기기 시험은 수행하지 않았다. 외부 출처 사이트 내용을 새로 검증한 것이 아니라 기존 URL·상태의 표시를 확인했다.

- [비교 후보 실제 검증 JSON](assets/2026-10-08-RG013-ranked-cards-browser.json)
- [분류 계통 실제 검증 JSON](assets/2026-10-08-RG013-taxonomy-browser.json)
- [변경 전 비교 답변](assets/2026-10-08-RG013-ranked-cards-before.png) / [390px 비교 카드](assets/2026-10-08-RG013-ranked-cards-390.png) / [900px 비교 카드](assets/2026-10-08-RG013-ranked-cards-900.png)
- [변경 전 분류 답변](assets/2026-10-08-RG013-taxonomy-before.png) / [390px 계통](assets/2026-10-08-RG013-taxonomy-390.png) / [900px 계통](assets/2026-10-08-RG013-taxonomy-900.png)

`graphify update .` AST 갱신을 실행했다. 추출기 경고와 커뮤니티 이름 갱신 안내가 있었고 실행은 성공했다.

## 커밋·배포

- 기본 구현 커밋: `ce5b9723c987041ad4274b931bb02fedefad804d` (`feat: present ranked bird candidates and taxonomy as structured cards`).
- 시각 QA 후 가독성 수정 및 최종 배포 커밋: `ddba07ee8f2bc52715c34ac13f7eb950e9a5a301` (`fix: improve candidate names and terminal taxon contrast`). 문서·검증 자료는 별도 후속 커밋으로 관리한다.
- NAS TEST 최종 이미지: `robingraph-api:test-rg013-ddba07e`, 컨테이너: `robingraph-api-test`, 릴리스: `/home/kimdove/RobinGraph-rg013-ddba07e`.
- Git 런타임 허용 목록 아카이브와 원격 manifest 해시를 검증했다. 최종 아카이브 SHA256: `b424d13fabbec6ddafa43d3c8900c8372a0b5d40af810a6f41dbe9f962d604c6`.
- 기존 NAS 환경 파일을 내부에서 복사해 이미지·리비전만 변경했다. 인증 정보는 문서·Git·브라우저에 포함하지 않았다. 배포 및 verify 성공, Docker inspect에서 최종 이미지·OCI revision 일치·`healthy`, `/health`의 `status=ok`/`deployment_target=test`를 확인했다. 기존 health의 taxonomy_release 문자열로 활성 데이터 검증을 대신하지 않는다.
- [실제 확인한 NAS TEST](https://robingraph-test.dove-nest.com/chat). PROD 변경 없음. 작업 전 이미지 `robingraph-api:test-rg013-a91ef5e` 및 중간 `ce5b972` 이미지 보존.

## 한계·후속 사항

랭킹 계산 방식과 자료의 정확성·누락은 기존 서버/원자료의 범위다. 한국어 이름이 없는 후보를 임의 번역하지 않으며 영어 이름을 유지한다. 근거 태그는 요약용 최대 3개이고 전체 근거는 상세에서 확인한다. 분류 목록은 기존처럼 최대 20개를 표시하며 알 수 없는 단계를 임의 분류로 바꾸지 않는다. 다른 백로그와 보류 작업은 진행하지 않았다.
