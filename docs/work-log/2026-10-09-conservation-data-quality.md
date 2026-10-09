# IUCN 등급 출처와 평가 연결 상태 개선

## 요청 배경과 목표

사용자는 등급별 도감 카드 미리보기를 확인한 뒤, 앱에서 까치가 NE로 표시되는 이유를 질문했다. 외부 자료의 LC와 앱의 NE가 다른 점을 계기로 자료 신뢰성을 높이고 AviList 외의 출처도 검토해 달라고 요청했다.

이번 작업은 현재 자료가 무엇을 증명하는지 분명하게 표시하고, 자료의 출처와 릴리스 연결을 검사하며, 테스트 DB의 보전 등급 데이터를 공식 원자료와 전수 대조하는 데 목적이 있다. 실제 IUCN 평가 원문을 새로 수집하거나 까치의 등급을 LC로 수동 변경하는 작업은 포함하지 않았다.

## 원인과 확인 근거

AviList는 조류 분류 목록이며, 이 프로젝트의 보전 등급도 현재 AviList 스냅샷에 기록된 값을 읽는다. 그 값을 IUCN 평가 원문을 직접 조회한 결과로 해석하면 안 된다. 특히 AviList NE에는 BirdLife 평가 대상과 종 범위가 정확히 연결되지 않은 경우가 포함된다.

공식 v2025b 확장 엑셀의 `How to use` 시트에서 `IUCN_Red_List_Category` 설명을 확인했다. 일치하는 평가 대상이 없을 때 NE를 사용한다는 설명이 있다. 설명 안의 BirdLife 버전 표기는 일부 과거 표현이 함께 남아 있으므로 그 문구만으로 평가 릴리스를 추정하지 않았다.

같은 엑셀에서 다음 값을 확인했다.

| 종 | AviList sequence | 원자료 등급 | 평가 참고 링크 |
| --- | ---: | --- | --- |
| Pica serica | 20193 | NE | 없음 |
| Pica pica | 20198 | NE | 없음 |

기존 화면은 NE를 일반적인 IUCN 미평가 표시로 설명했고, 출처 이름이 있으면 등급 색을 적용할 수 있었다. 출처 ID, 릴리스, URL의 실제 호스트, 동일 데이터셋 연결을 추가로 확인할 필요가 있었다.

공식 자료:

- [AviList v2025b 릴리스](https://www.avilist.org/checklist/v2025b/)
- [AviList v2025b 확장 엑셀](https://www.avilist.org/wp-content/uploads/2026/06/AviList-v2025b-10Jun2026-extended.xlsx)
- [AviList v2025b JSON](https://explore.avilist.org/data/avilist-2025b.json)
- [BirdLife 분류와 IUCN 평가의 관계](https://datazone.birdlife.org/about-our-science/taxonomy)
- [BirdLife의 IUCN 평가 역할](https://datazone.birdlife.org/about-our-science/the-iucn-red-list)

## 변경 전후 동작

| 상황 | 이전 | 변경 후 |
| --- | --- | --- |
| AviList NE | 미평가로 해석되는 배지 | `평가 자료 연결 확인 필요 (AviList NE)`와 중립 색상 |
| AviList LC 등 | 원문 직접 평가처럼 보일 수 있는 배지 | 등급 뒤에 `자료 기준` 표시 |
| 출처 이름만 있고 릴리스 또는 URL이 불완전 | 등급 색이 적용될 수 있음 | 등급 미확인 표시와 중립 색상 |
| 출처 ID·분류 릴리스 불일치 | 연결을 충분히 검증하지 않음 | 확인되지 않은 자료로 반환 |
| 원자료 등급과 정규화된 등급이 충돌 | 화면 신뢰 여부가 불명확 | 화면에서 확인된 등급으로 승격하지 않음 |
| 답변 출처 | 출처 이름·링크 중심 | 릴리스, 검증 범위, 원자료 해시, 안전한 평가 참고 링크 추가 |

NE 원자료를 삭제하거나 임의로 LC로 바꾸지 않았다. 기존 API의 category, category_raw, label 필드는 호환성을 위해 보존하고, 의미를 설명하는 필드를 추가했다. 따라서 클라이언트는 원자료 값만 보고 판단하지 않고 평가 연결 상태를 함께 확인해야 한다.

## 구현 파일

- `src/robingraph/retrieval/species_profile.py`: 동일 활성 개념집합·자료 릴리스·데이터셋과 허용 정책의 출처만 조회한다. AviList 출처 ID와 릴리스, HTTPS 공식 출처 URL, 선택적인 SHA-256 형식을 검사한다. `evidence_kind`, `assessment_status`, `independently_verified`, `quality_note`를 추가했다. BirdLife 참고 링크는 안전한 URL이고 NE가 아닐 때만 제공한다.
- `src/robingraph/api/static/chat.js`: 출처 정보 확인과 등급 색 적용 조건을 구분한다. HTTPS 호스트, 포트, 사용자 정보, 릴리스, 원자료 코드 일관성을 검사한다. AviList 스냅샷임을 명시하고 NE 연결 상태를 표시한다. CR(PE)·CR(PEW) 부가 표시를 보존한다.
- `tests/test_species_profile.py`: 정상 스냅샷, NE 연결 확인 필요, 출처·릴리스 불일치, 잘못된 URL과 해시를 검증한다.
- `tests/frontend/chat_ui.test.js`: NE 배지, 자료 기준 표시, 출처 보존, 원자료 코드 충돌, URL·출처 위장, CR 부가 표시를 검증한다.
- `scripts/audit_conservation_quality.py`: 읽기 전용 감사 스크립트. 개념집합 ID와 분류 릴리스를 필수 인자로 받아 해당 범위만 비교한다. 인증 정보는 결과에 기록하지 않는다.
- `docs/verification/assets/2026-10-09-conservation-quality.json`: 실제 DB 감사 결과.
- 같은 디렉터리의 `conservation-quality-report.html`, `.artifact.json`, `conservation-quality.ipynb`: 감사 결과를 검토하는 보고서와 재현용 노트북.

## 실제 테스트 DB 감사

대상은 `rg:concept-set:avilist-v2025b`, 분류 릴리스 `v2025b`이다. Neo4j READ_ACCESS 및 읽기 트랜잭션으로 조회했다. DB 데이터를 수정하지 않았다.

| 검사 | 실제 결과 |
| --- | ---: |
| 원자료 종 수 / DB 종 수 | 11,131 / 11,131 |
| 중복 taxon ID | 0 |
| 원자료 또는 DB에만 있는 종 | 0 |
| 학명·정규화한 등급 불일치 | 0 |
| 출처 ID 또는 등급 코드 오류 | 0 |
| 문자열 공백 차이 | 1 |
| NE 종 수 | 808 |
| NE 중 BirdLife 참고 링크가 있는 종 | 0 |
| NE 외 등급 중 참고 링크가 없는 종 | 0 |
| 저장된 스냅샷 해시와 다운로드 해시 일치 | 일치 |
| 독립적인 IUCN 평가 원문 대조 | 미실행 |

공백 차이는 `Pericrocotus albifrons`의 원자료 `LC `와 DB의 `LC`이다. 문자열 끝 공백 정리 차이이며 등급이 바뀐 것은 아니다.

JSON SHA-256은 `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`이다. 해시 일치는 원자료 바이트와 저장 기록의 일치를 확인하는 근거이며, 생물학적 사실이나 최신 평가의 정확성을 보장하지 않는다.

등급 분포는 LC 8,027, NE 808, NT 909, VU 642, EN 356, CR 183, CR(PE) 17, CR(PEW) 2, EW 5, EX 147, DD 35이다. 이는 해당 AviList 자료 버전의 분포다.

감사 실행 형식:

```sh
PYTHONPATH=src python scripts/audit_conservation_quality.py \
  --env-file /path/to/private.env \
  --snapshot /path/to/avilist-2025b.json \
  --concept-set-id rg:concept-set:avilist-v2025b \
  --taxonomy-release v2025b \
  --output /path/to/conservation-quality.json
```

## 회귀 테스트와 검증 범위

- Python: `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests`. 최신 main의 favicon 변경을 포함한 소스에서 642개 중 607개 실행 통과, 35개 건너뛰기, 실패 0. 이후 병합한 카드 토글 스크롤 변경은 프런트엔드와 해당 테스트만 변경했다.
- 프런트엔드: `node --test tests/frontend/*.test.js`. 최종 카드 토글 변경 병합 후 253개 통과, 건너뛰기 0, 실패 0.
- Python의 건너뛰기는 전용 DB를 요구하는 opt-in 통합 테스트, 선택적 의존성 또는 별도 원자료가 필요한 테스트다. 건너뛴 테스트를 통과로 계산하지 않았다.
- 위 회귀 테스트에는 Mock·fixture 검증이 포함된다. 실제 DB 11,131종 감사와 9등급의 실제 `read_conservation` 조회는 별도로 실행했다.
- 로컬 카드 미리보기: 기존 실제 NAS 프로필에 실제 DB 보전 메타데이터를 결합해 현 렌더러로 9등급을 표시했다. Chrome에서 사진 로드, 카드 영역 수용, 색상, EW 키보드 뒤집기와 페이지 오류 0을 확인했다. 이 검증은 새 서버 API 전체 경로를 통과한 결과와 구분한다.
- 보고서: canonical artifact 검증과 HTML 패키징 통과. 4개 노트북 코드 셀을 표준 Python으로 순서대로 실행하고 assertion을 확인했다. Jupyter 커널 실행은 하지 않았다. 보고서 패키징 도구의 브라우저 검증은 Chrome 환경 불일치로 실패했고 `structural_only`로 전달했다. 보고서의 light/dark, desktop/narrow, sourceDialog 브라우저 QA는 미실행이다.
- `git diff --check` 통과.

실제 NAS 배포 후 검증:

- 공개 `/health`가 HTTP 200, status ok, mode neo4j, deployment_target test를 반환했다. health의 `taxonomy_release`는 기존 기본값 `fixture-avlist-2025`이므로 실제 자료 릴리스 검증에 사용하지 않았다. 이 health 메타데이터 개선은 후속 사항이다. 실제 10종 프로필의 출처 릴리스는 v2025b로 확인했다.
- 공개 `/v1/taxa/profile`로 LC·NT·VU·EN·CR·EW·EX·DD·NE 9등급과 Pica serica를 포함한 10종을 조회했다. 모두 HTTP 200이며 taxonomy_snapshot, independently_verified false, 릴리스와 해시가 기대값과 일치했다. NE 2종은 needs_review와 평가 참고 링크 없음, 나머지는 snapshot_only였다.
- 공개 JS와 CSS를 다운로드해 배포 소스의 파일 바이트와 일치함을 확인했다. 최신 main의 카드 토글 변경도 포함했다. favicon.ico와 32·192px PNG 모두 조회했다.
- 공개 `/chat` 페이지의 실제 JS/CSS에 실제 API Pica serica 프로필을 삽입하여 현 렌더러와 팝업을 실행했다. 데스크톱 1280×900과 모바일 390×844에서 NE 중립 색상, 연결 확인 필요 배지, 카드 화면 수용, Enter 뒤집기, 출처 설명을 확인했다. 페이지 오류 0. 프로필 삽입을 통한 렌더러 검증이며 자연어 질문 분류 전체 흐름의 새 검증은 아니다.
- 근거 파일: `docs/verification/assets/2026-10-09-conservation-deployment.json`, `docs/verification/assets/2026-10-09-conservation-browser.json`.

검증 스크립트의 첫 실행은 새 카드 토글의 클래스 이름을 잘못 예상한 assertion 때문에 실패했다. 실제 배포 JS/CSS의 바이트 일치는 그 전에 통과했다. 실제 속성인 data-fit-scroll로 검증 조건을 수정한 후 API 및 브라우저 검증을 다시 실행해 통과했다. 앱 코드 수정은 필요하지 않았다.

## 배포와 커밋

코드 커밋은 `b61adf8`이다. 이후 최신 main의 favicon과 카드 토글 스크롤 변경을 병합했다. 최종 배포 소스는 `6cb98546f676f0280a362a39e01824a01a618e7f`이다.

- 대상: NAS TEST, `robingraph-api-test`.
- 최종 이미지: `robingraph-api:test-conservation-6cb9854`.
- NAS 릴리스 디렉터리: `/home/kimdove/RobinGraph-conservation-6cb9854`.
- 실행: `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy`.
- 배포 패키지 해시: `038ec680ebb92a6a2b1bdbdef91da6fe144c0663b973cef2c4b8aa8606a52d69`.
- 압축 파일과 포함 파일의 SHA-256 확인 후 배포했다. 실제 환경변수는 NAS 내부에서 기존 파일을 복사했고 권한은 600으로 설정했다. 인증 정보는 패키지나 문서에 포함하지 않았다.
- 배포 스크립트가 API healthy 상태를 확인했다. 배포 전후 PROD 컨테이너 ID를 비교했고 동일했다. PROD 이미지는 `robingraph-api:prod-5fb401e`로 유지했다.
- 첫 TEST 배포 소스는 `95a9253`이었다. 작업 도중 main에 추가된 카드 토글 개선을 확인하고 최종 소스 `6cb9854`로 다시 배포했다. 최종 결과는 후자를 기준으로 판단한다.

## 남은 한계와 후속 방향

1. **IUCN 또는 BirdLife 원문 평가 연동**: 평가 ID, 평가 연도, 세계/지역 평가 범위, 평가 당시 종의 범위를 보존해야 한다. 출처가 다른 LC 값을 기존 종 ID에 학명만으로 덮어쓰지 않는다.
2. **종 범위 매핑**: 동일 종, 분할된 종, 통합된 종을 구분한다. 기존 넓은 범위 종의 등급을 새로 분리된 종에 자동 상속하지 않는다. BirdLife와 AviList의 분류 일치 작업은 진행 중이다.
3. **한국어 이름 확인**: 이번 조사에서 한국어 `까치` 요청은 Pica pica로, 직접 학명 Pica serica 요청은 별도 종으로 해석되는 현상을 관찰했다. 원인과 이름 매핑 수정은 이번 범위에 포함하지 않았다. 국립생물자원관 자료로 국명과 인정 학명을 확인하는 후속 작업이 필요하다.
4. **출처별 역할**: 분류 기준은 AviList, 보전 평가는 IUCN/BirdLife, 국내 이름·종 정보는 국립생물자원관, 관찰 기록·계절 분포는 eBird로 보완하는 구성을 추천한다. 새 연결은 이번에 구현하지 않았다. BirdLife는 조류 IUCN 평가 기관이므로 IUCN과 서로 독립적인 두 평가로 세지 않는다.
5. **평가 최신성**: 현재 값은 v2025b 스냅샷이다. 참고 링크 존재만으로 현재 최신 등급과 일치한다고 판단하지 않는다.
6. **다른 자료 영역**: 체중·먹이·서식·사진·한국어 이름의 전체 신뢰성을 이번 감사로 확인한 것은 아니다. 이번 전수 대조는 학명과 보전 등급 및 출처 연결에 한정한다.

국내 자료와 관찰 자료 후보:

- [국립생물자원관 한반도의 생물다양성](https://species.nibr.go.kr/)
- [국립생물자원관 국가생물종목록 구축 역할](https://nibr.go.kr/cmn/sym/mnu/mpm/115020100/htmlMenuView.do)
- [eBird Status and Trends](https://science.ebird.org/en/status-and-trends)
- [IUCN Red List API](https://api.iucnredlist.org/)

작업 기록은 저장소에 작성했다. 같은 작업을 Obsidian에 중복 기록하지 않았으므로 두 문서의 내용 대조는 해당하지 않는다.
