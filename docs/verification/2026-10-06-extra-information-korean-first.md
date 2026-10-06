# 추가 정보 한국어 우선 표시

- 생태 후보는 검증된 국명 표의 taxon ID·학명·영어 이름을 대조한 뒤, 한국어 이름이 있는 종을 먼저 정렬하고 최대 3종을 선택한다. 기존에는 검증되지 않은 그래프 이름으로 LIMIT 4를 적용한 뒤 국명을 교정하여 영어 표시 후보가 먼저 나올 수 있었다.
- 통칭·가축형 관계 제목과 종 라벨에 확인된 한국어 이름을 우선하고 중복 영어 이름은 생략한다. 학명은 식별을 위해 유지한다.
- 아종 선택에는 한국어 소속 종 안내를 붙인다(예: 청둥오리의 아종 · Anas platyrhynchos conboschas). 소속 종의 국명을 아종 자체의 국명으로 부여하지 않는다.
- 한국어 이름이 확인되지 않은 종은 영어, 영어 이름도 없는 경우에는 학명을 유지한다. 근연 점수순 비교 후보의 순위는 변경하지 않는다.

## 검증

- 생태 관계 테스트 6개 통과. 한국어 후보 우선, stale 학명/영문명 제외, 선택 이전 Cypher 정렬, 근거와 분류판 조건 검증.
- 프런트엔드 전체 127개 통과. 한국어 관계 제목, 중복 영문명 생략, 아종 소속 종 안내 포함.
- NAS 실제 TEST Neo4j/PostgreSQL 읽기 검증: 청둥오리의 서식 환경 후보 가창오리·개개비·개구리매, 먹이 생태 후보 가창오리·고니·고방오리. 각 항목 모두 검증된 국명으로 표시됨을 확인. 테스트에서 서비스 데이터 변경 없음.

## 배포

Runtime commit `5906c10440af87f17e809b9dd66befb95678cbef`, origin/dev push 완료. NAS TEST image `robingraph-api:test-ko-extra-5906c10` healthy, OCI revision 일치. 전송 archive SHA-256 `65fc69d905306110c6025a2b1b4000d6a83aea9b897b79d0e2cdee1b96f628e6`와 manifest 검증 완료. PROD 유지.

공개 API에서 위 생태 후보 국명 우선 표시와 개개비(A. orientalis)·Great Reed Warbler(A. arundinaceus)의 구분을 확인했다. 공개 chat.js의 해시가 커밋 파일과 일치한다. 배포 계약 검증 passed=true.
