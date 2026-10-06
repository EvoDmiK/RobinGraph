# 한국조류학회 국명 적용 검증

- 기준: 한국조류학회 2025 한국조류목록 개정판 v2.1 공개 XLSX, `공식목록` 시트의 Species 598행.
- 자료 출처와 원본 해시는 [표시명 정책](../korean-display-names.md) 및 `species_ko_names.json`에 보존했다.
- 활성 AviList v2025b 11,131종 전체를 읽기 전용으로 확인했다. 국명 적용 596종, 영어 표시 10,535종. 학명·영명·종 ID를 변경하지 않았다.
- 593종의 학명을 완전 일치로 연결하고, 근거가 확인된 속 이동 3종을 별도로 연결했다. 분류 기준 차이가 있는 Anas carolinensis와 Saxicola stejnegeri는 다른 종에 붙이지 않았다.
- 기존 그래프 이름 41종이 학회의 국명으로 교정됐다. 기존 자동 번역 자료는 삭제했다.
- Python 단위/계약 검사 533개 실행: 성공, 환경 의존 검사 40개 생략.
- 프런트엔드 검사 125개 성공. 과거 자동 번역명을 받은 경우에도 카드·설명·비교에서 영어를 표시하는 조건 포함.
- `graphify update .` 실행 완료.

## NAS TEST 검증

배포 코드: `988d4fe69b9a769620fe95b55dd21053fe897c66`, 이미지 `robingraph-api:test-korean-988d4fe`, 디렉터리 `/home/kimdove/RobinGraph-korean-988d4fe`.

아카이브 SHA-256: `8c27967bb1db31650eac0dbf8f9e9477dd0a25d993c9140039bca199ab3db129`. 전송 후 아카이브와 MANIFEST의 파일별 해시를 확인했다. TEST 서비스 health와 Docker 이미지 revision이 배포 코드에 일치했다.

공개 도메인 `https://robingraph-test.dove-nest.com`에서 배포 검증기의 계약·스키마·청둥오리 의미 검사가 성공했다. `/v1/taxa/lineage?scientific_name=...` 실제 조회에서 뿔바다오리·우는뻐꾸기·꼬마물떼새는 학회 국명과 source-reference/출처 URL을 반환했고, Abeillia abeillei는 한국어 이름 없이 Emerald-chinned Hummingbird를 반환했다. 공개 chat.js와 birds.js의 SHA-256이 로컬 코드와 일치했다.

프런트엔드 DOM 검사는 자동 검사이며 새 브라우저 스크린샷 검증을 수행한 것으로 주장하지 않는다. PROD 서비스는 기존 이미지를 유지했다. 오늘 Obsidian 기록에도 새 정책을 저장하고 이전 자동 번역명 정책을 대체한다고 연결했다.
