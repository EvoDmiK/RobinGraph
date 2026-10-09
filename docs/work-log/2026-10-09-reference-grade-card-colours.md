# 참고 평가 등급의 카드 색상·적색목록 뱃지 통일

## 요청 배경과 목표

사용자가 유리딱새(Tarsiger cyanurus)와 꼬까직박구리(Monticola gularis)의 카드를 비교했다. 둘 다 공개 평가 자료에 LC가 있는데 유리딱새는 회색, 꼬까직박구리는 초록색이었다. 유리딱새 뱃지는 `관심대상 (LC) · 2025 평가 · 참고`였고 아래에 참고 평가 안내가 중복 노출됐다.

요청은 동일 등급에 동일 색상을 적용하고, 뱃지를 두 번째 카드 형식으로 통일하며, 카드의 별도 참고 평가 안내 줄을 제거하는 것이다. 이번 변경은 특정 종 예외가 아닌 검증된 참고 평가를 가진 모든 종에 적용한다.

## 확인한 원인

`chat.js`의 `conservationInfo`는 AviList NE 또는 원본 NE와 함께 반환된 미연결 평가를 `link-unresolved`로 분류했다. 참고 자료의 등급이 있어도 tier는 unconfirmed여서 회색 카드가 됐다. 기존 연결 평가와 참고 평가의 뱃지 문자열 생성 경로도 달랐다. `buildSpeciesCard`와 `buildSpeciesBrief`는 별도로 species-reference-assessment 요소를 추가했다.

평가 연도 차이 자체가 색상 차이의 직접 원인은 아니다. 공개 평가의 연결 상태에 따라 표시 정책이 달랐던 것이 원인이다. 이번 작업으로 데이터베이스의 연결 상태나 종 분류 일치를 새로 확정하지는 않는다.

## 변경 내용과 전후 동작

| 파일 | 구현 내용 |
|---|---|
| src/robingraph/api/static/chat.js | 유효한 참고 평가가 있으면 그 category의 tier를 사용. 뱃지를 기존 공개 평가목록 형식으로 통일. 카드와 답변 요약의 별도 참고 평가 줄 제거 |
| tests/frontend/chat_ui.test.js | LC 색상, 표준 뱃지, 안내 줄 부재, 출처 상세 보존, 등급별 색상과 잘못된 참고 자료 거부를 검증 |

유리딱새는 초록색 LC 카드와 `IUCN 적색목록 관심대상 (LC) · 2025 평가 · 공개 평가목록 기준` 뱃지로 표시한다. 꼬까직박구리는 같은 초록색과 2024년 뱃지를 유지한다. 평가 연도는 실제 자료의 값을 사용한다.

LC·NT·VU·EN·CR·EW·EX 참고 등급의 색상을 공통 경로에서 처리한다. 학명·출처·자료판·해시·URL·등급 등이 기존 검증 조건에 맞지 않는 자료는 색상을 부여하지 않는다. 자료가 없는 종을 임의로 LC로 만드는 작업이 아니다.

카드와 답변 요약의 별도 `참고 평가:` 안내 요소만 제거한다. `답변 출처 보기` 안의 평가 연도, 명명자, 원문 링크, 분류 범위 확인 필요 설명은 유지한다. API의 category와 raw category, independently_verified, taxonomy_alignment 및 내부 link-unresolved 상태는 변경하지 않는다. 뱃지 title의 기존 근거 설명도 유지한다.

## 자동 검증

- `node --test tests/frontend/chat_ui.test.js`: 277개 통과, 실패·취소·건너뜀 0.
- `node --test tests/frontend/*.test.js`: 전체 280개 통과, 실패·취소·건너뜀 0. 위 277개를 포함하므로 합산하지 않는다.
- DOM 모형 기반 UI 테스트이며 실제 서버 검증과 구분한다. 실제 큰부리까마귀 임시 payload 파일이 있을 때 실행하는 기존 조건부 검사도 포함한다.
- `git diff --check` 통과.
- `graphify update .` 실행: 4,578개 노드, 9,559개 연결로 갱신.
- 프런트엔드 변경이므로 전체 Python 테스트나 전 종 데이터 감사를 재실행하지 않았다. 이번 검증은 등급 표시 정책과 UI 회귀 범위다.

## 배포와 커밋

색상·뱃지 구현: `c5069bade4e135e263525616cb99ef72391f6cc9`.
안내 줄 제거 및 테스트 갱신: `8b7f2c4e5f5d8bb092b8ee360d23deb4e57edeb5`.
최종 배포 패키지 SHA-256: `25a360bcd456a2f2f4be823ee670369358cdfb84c7a2ec712c494eb95229a286`.
NAS 디렉터리: `/home/kimdove/RobinGraph-reference-colour-8b7f2c4`.

TEST 이미지: `robingraph-api:test-reference-colour-8b7f2c4`.
Production 이미지: `robingraph-api:prod-reference-colour-8b7f2c4`.

기존 환경별 설정 파일을 각각 복사하고 권한 600을 유지했다. 이미지 태그만 변경했다. TEST에서 먼저 빌드·배포하고 실제 화면 검증 후 동일 이미지를 Production 태그로 승격했다. 배포 도구의 rollback 하위 명령은 지정한 로컬 이미지의 compose 교체·health 대기 기능으로 사용했으며 과거 코드로 돌아간 것이 아니다.

두 컨테이너 모두 healthy, OCI revision `8b7f2c4e5f5d8bb092b8ee360d23deb4e57edeb5`를 확인했다. 데이터 마이그레이션이나 DB 쓰기는 수행하지 않았다. 이전 Production `prod-crow-direct-a87eb9b` 및 TEST `test-reference-colour-c5069ba` 이미지는 복구용으로 보존했다. 실제 롤백은 실행하지 않았다.

## 실제 화면 검증 방법과 제한

Playwright와 로컬 Chrome으로 공개 /chat에 접속하고 실제 /v1/chat 응답에서 학명을 확인한 뒤 도감 카드를 열었다. 응답이나 DB를 모의 처리하지 않았다. 두 종의 data-conservation-tier=lc, 뱃지 전체 문구, 실제 계산된 backgroundImage 동일, 카드 내 참고 안내 요소 0개, 출처 상세 보존, JavaScript 오류 부재를 검사한다.

비교 질문에는 학명을 사용했다. 앞선 중간 검증에서 `꼬까직박구리` 한국어 이름 조회가 실패해 정확한 학명으로 표시 경로를 검증했다. 따라서 이번 결과를 해당 한국어 이름 검색 정상화의 증거로 해석하면 안 된다. 이름 검색 개선은 이번 색상·뱃지 수정 범위에 포함하지 않았다.

현재 표시 색상은 유효한 공개 참고 평가 등급을 반영한다. 이는 참고 평가의 분류 범위 일치가 새로 검증됐다는 뜻이 아니다. 그 구분은 출처 상세와 응답 데이터에 보존한다.

## 최종 실제 검증 결과

- TEST: PC 1280×900에서 두 종, 2건 모두 통과.
- Production: PC 1280×900 및 모바일 에뮬레이션 390×844에서 두 종씩, 4건 모두 통과. 실제 모바일 기기 검사는 아니다.
- 두 환경 모두 LC 색상과 뱃지 형식이 일치하고 카드의 참고 안내 요소가 없었다. 출처의 분류 범위 설명은 유지됐고 브라우저 JavaScript 오류는 0건이다.
- TEST 유리딱새 PC와 Production 유리딱새 모바일 캡처를 직접 확인했다. 초록색 카드, 표준 뱃지, 별도 안내 줄 제거를 시각적으로 확인했다.
- 기존 큰부리까마귀 실제 payload 파일이 존재하여 조건부 회귀 검사도 실행됐다. 전체 자동 테스트 결과에서 건너뜀은 0이다.

[실제 브라우저 검사 결과](../verification/assets/2026-10-09-reference-grade-card-colours.json). 캡처는 로컬 /tmp/rg-reference-final-test 및 /tmp/rg-reference-final-prod에 보관하며 임시 경로이므로 영구 아티팩트로 간주하지 않는다.
