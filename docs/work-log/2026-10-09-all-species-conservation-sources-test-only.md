# 전체 종 보전 등급 출처 조사와 전문가 자료 연결 · TEST 전용

## 요청 배경과 목표

사용자는 박새의 IUCN 배지가 사라진 상태를 지적하고, 문구를 수정하거나 배지를 숨기는 대신 실제 등급 정보를 찾아 연결하라고 요청했다. 이어 박새 한 종만 수정하지 말고 전체 종을 대상으로 하라고 재확인했다. 이번 작업은 전체 활성 종의 기존 자료·표시를 검증하고, 미연결 종에 대해 공식 평가 기록과 전문가 종 자료를 조사하며, 확인된 출처를 공통 코드로 연결하는 작업이다. 전체 종의 독립된 최신 IUCN 평가를 확보했다는 뜻은 아니다.

사용자가 명시적으로 승인하기 전에는 Production 배포·재시작·DB 변경·롤백을 하지 않는다. AGENTS.md에 기록한 이 정책을 유지했다. 구현과 배포 대상은 TEST이다. DB 값에 임의 LC를 써 넣지 않는다.

## 협업과 조사 범위

- 부모: 출처 직접 조사, 프런트 공통 처리와 승인 manifest 생성, 전체 11,131종 런타임·표시 검증, TEST 배포, 실제 브라우저 검증, 문서 통합.
- resolve_traits503: 전문가 자료 공통 백엔드 reader·고정 레코드·분류 관계 검증·테스트, 프런트 검증기 독립 검토.
- resolve_ko408: 원래 평가 미연결 447종과 평가 후보 666개를 공식 AviList 및 GBIF에 공개된 IUCN 원본으로 독립 대조.
- quality_audit_report: HKBWS 전체 목록 584종 coverage 대조, 전문가 계정의 명시 등급 검토, 기존 표시와 다른 7종의 공식 IUCN 변경표 대조.

협업 검토 중 프런트가 해시의 64자리 형식만 검사하는 문제를 발견했다. LC와 원문 코드를 함께 EN으로 바꾸거나, 허위 날짜·범위 필드를 넣어도 승인되었다. 이를 승인 레코드의 모든 필드 exact 비교로 수정했다. 승인되지 않은 추가 필드도 label을 제외하면 거부한다. 이 문제의 재현 사례를 테스트에 포함했다.

## 원인과 근거

1. 기존 연결기는 현행 학명·명명자·평가 식별자가 맞는 GBIF/IUCN 자료와 BIRDBASE의 명시 등급을 우선 사용했다. 분류가 분할·병합·속 변경된 경우 전문가 자료에 명시 등급이 있어도 연결 경로가 없었다.
2. 박새는 현재 AviList의 Parus cinereus이다. HKBWS는 이전 학명 Parus minor 계정에 LC를 명시하고, 과거 Parus major에 포함된 평가라고 설명한다. Cornell 2024 변경 기록은 Parus minor를 Parus cinereus에 포함한 근거다. 두 자료를 대조해야 하며 단순 문자열 불일치를 이유로 등급 근거 자체를 버리는 것도, 새로운 독립 평가라고 꾸미는 것도 잘못이다.
3. 원래 미연결 305종 중 284종에는 등급을 가진 출처 종 후보가 있고, 277종은 출처 등급·Global 행·인용·평가 ID·연도 무결성 검사를 통과했다. 하지만 이는 출처 종의 평가가 존재한다는 뜻이다. 현재 종의 등급으로 확정된 277종이라는 뜻이 아니다.
4. 위 305종의 관계 분류는 명시적인 분할/병합 문서에 출처명이 등장하는 214종, 명시적 관계가 충분하지 않은 91종이다. 후보끼리 등급이 다른 대상도 16종 있다. 기존 genus_change 15건은 단어 탐지였으며 순수 속 변경 입증으로 사용할 수 없었다. 독립 감사에서 순수 속 변경만으로 확인된 대상은 0종이었다.
5. 홍콩 목록은 전 세계 목록이 아니다. HKBWS 2024 목록 584행 전체를 공식 페이지 검색 캐시 조각에서 확보해 대조했으며, 직접 HTML/PDF 전체 다운로드 성공으로 기록하지 않았다. 574개 학명이 현재 종과 정확히 일치했고 10개는 일치하지 않았다. 명시 등급은 72개이고 빈칸 512개를 LC로 해석하지 않았다. 원래 305종 중 정확한 학명 8종, 공식 분류 결정에 등장하는 이름 후보 29종, 해당 목록에서 미일치 268종이었다. 이 미일치는 전 세계에 출처가 없다는 뜻이 아니다.

## 확인된 전문가 자료

| 현재 학명 | 전문가 자료의 학명 | 자료가 명시한 등급 | 자료 갱신일 | 출처 |
|---|---|---|---|---|
| Parus cinereus | Parus minor | LC | 2024-01-10 | [종 자료](https://avifauna.hkbws.org.hk/species/0270/034800) |
| Anser serrirostris | Anser serrirostris | LC | 2025-06-04 | [종 자료](https://avifauna.hkbws.org.hk/species/0010/000400) |
| Larus mongolicus | Larus mongolicus | LC | 2025-12-03 | [종 자료](https://avifauna.hkbws.org.hk/species/0110/017510) |
| Anthus japonicus | Anthus japonicus | LC | 2025-03-04 | [종 자료](https://avifauna.hkbws.org.hk/species/0440/054600) |
| Alcippe hueti | Alcippe hueti | LC | 2024-07-25 | [종 자료](https://avifauna.hkbws.org.hk/species/0360/043800) |
| Cinnyris ornatus | Cinnyris ornatus | LC | 2025-06-16 | [종 자료](https://avifauna.hkbws.org.hk/species/0420/052300) |
| Larus brachyrhynchus | Larus brachyrhynchus | LC | 2024-01-14 | [종 자료](https://avifauna.hkbws.org.hk/species/0110/017100) |
| Ardea coromanda | Bubulcus coromandus | LC | 2024-01-13 | [종 자료](https://avifauna.hkbws.org.hk/species/0170/023000) |
| Butorides atricapilla | Butorides striata | LC | 2024-01-13 | [종 자료](https://avifauna.hkbws.org.hk/species/0170/022800) |

자료 갱신일은 IUCN 개별 평가 연도가 아니다. 개별 평가 연도를 확인하지 못한 값은 null로 유지했다. 학명 일치도 생물학적 범위 일치나 독립 평가 원문 검증 완료를 의미하지 않는다. 원문에서 평가명이 명시되지 않은 Anthus japonicus, Cinnyris ornatus, Ardea coromanda, Butorides atricapilla는 평가 학명을 추정해 만들지 않는다. 구학명으로 된 인용과 현행 제목이 공존하는 경우 각각 다른 필드로 기록했다.

분류 변경 근거는 [Cornell 2024 변경 기록](https://www.birds.cornell.edu/clementschecklist/updates-and-corrections-october-2024/), [ITIS 황로 동의어 기록](https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value=1244987), 고정된 [AviList v2025b](https://explore.avilist.org/data/avilist-2025b.json) 결정문이다. ITIS-IOC-15.1-2025는 ITIS에 기재된 IOC 15.1 및 2025년 출처를 나타내는 로컬 식별자이며 ITIS 자체의 공식 릴리스명으로 주장하지 않는다.

## 변경 전후와 구현 파일

- `reviewed_conservation_references.json`: 전문가 자료의 학명·명시 등급·갱신일·짧은 발췌·출처 URL·과거 평가 범위·분류 관계 근거를 저장한다. 전체 HTML을 보관했다고 주장하지 않으며, snapshot_kind=reviewed_source_excerpt의 SHA는 검토 발췌 UTF-8에 대한 해시다.
- `reviewed_conservation.py`: 파일 전체 SHA, 레코드 SHA, 분류 릴리스·개념집합·taxon ID·학명·명명자·원본 NE를 검증한다. Cornell/ITIS/AviList 관계 자료는 허용된 공급자와 URL·릴리스·근거 해시 조건을 통과해야 한다. 다른 종이나 다른 릴리스로 자료를 전파하지 않는다.
- `conservation.py`: 기존 정확 연결 → GBIF 참고자료 → BIRDBASE 참고자료 우선순위를 유지하고, 그 다음에 검토한 전문가 참고자료를 사용한다.
- `chat.js`: 검증된 전문가 참고 등급으로 카드 색과 IUCN 배지를 표시한다. 예: `IUCN 적색목록 관심대상 (LC) · 홍콩조류관찰회 자료 기준`. 원래 NE와 현재 독립 등급 null은 보존하며, 앱 API의 reference_assessment에 실제 자료를 연결한다. 범위 및 출처 갱신일 설명은 답변 출처 보기에서 확인한다. 배지를 지우거나 평가 연도를 만들어 넣지 않는다.
- `sync_reviewed_conservation_frontend.py`: 검증된 백엔드 JSON에서 프런트 승인 manifest를 생성한다. 개별 종 이름에 따라 분기하는 표시 예외를 추가하는 방식이 아니다.
- `audit_conservation_runtime_all.py`: TEST DB를 읽기 전용 배치 조회하고 전체 종에 배포된 reader를 적용한다. 저장된 과거 DB 행 재생과 실제 새 DB 조회 모드를 구분한다.
- `audit_conservation_display_all.cjs`: 전체 reader 결과에 표시 함수를 적용해 알려진 등급 누락, 같은 등급의 잘못된 카드 색, 배지 삭제, 백엔드 참고자료를 프런트가 거부하는 오류를 검사한다. 실제 11,131개 HTTP 호출 또는 브라우저 테스트로 주장하지 않는다.

## 검증과 배포

최종 실행 결과와 배포 식별자는 아래 실행 기록에 기재한다. 코드 검증과 실제 DB/API/브라우저 검증을 구분한다.

## 한계와 후속 관리

미연결 대상 전체를 억지로 LC로 바꾸지 않았다. 출처 종의 평가 후보는 현재 종과 생물학적 범위가 같다는 증명이 아니므로 277개 후보를 자동 승격하지 않았다. 범위가 다르거나 상충하는 후보는 JSON 감사 목록에 모두 남겼다. 현재 연결된 전문가 자료도 현재 종의 독립 최신 평가를 확인한 것으로 표시하지 않는다.

HKBWS 목록과 현재 등급이 다른 7종은 공식 IUCN 변경표·자료 연도와 대조한다. 오래된 홍콩 목록의 값을 기준으로 최신 평가를 덮어쓰지 않는다. 국명·형질·사진·번역 엔진은 이번 등급 수정의 검증 대상에 포함하지 않는다. 브라우저에서 보이는 설명 제공처 경고는 별도 기록한다.

## 재현 자료

- `docs/verification/assets/2026-10-09-conservation-name-relationship-audit.json` 및 같은 날짜 `audit-conservation-name-relations.py`: 447종/666후보 원본 대조, 원래 305종 전체 관계 분류.
- HKBWS coverage 및 7종 변경표 대조 자료: 별도 검토 문서와 연결된 JSON에 기록한다.
- `docs/verification/assets/2026-10-09-expert-grade-browser.cjs`: 실제 TEST 화면 검증.
- 앞선 배지 복구만으로는 데이터 보완을 충족하지 못했던 경위: `2026-10-09-iucn-badge-restore-test-only.md`.


## 최종 실행 기록

- 프런트 전체: `node --test tests/frontend/*.test.js` 296개 통과, 실패 0, 건너뛰기 0.
- 백엔드 관련 범위: `tests.test_reviewed_conservation`, `tests.test_conservation_index`, `tests.test_species_profile`, `tests.test_conservation_birdbase` 59개 통과, 실패 0, 건너뛰기 0. 모의 repository와 고정 출처 레코드 검증이며 이 결과를 실제 DB 테스트로 계산하지 않았다. 협업자의 중복 실행 건수는 합산하지 않았다.
- 프런트 초기 전체 실행 1건은 신규 승인 출처 URL이 기존 URL 제한 테스트에 등록되지 않아 실패했다. 허용 출처는 고정 JSON에서만 읽도록 보완한 뒤 최종 296개가 통과했다. 초기 해시 검증의 논리적 허점도 독립 검토 후 보완했다.
- 실제 TEST DB 배치 조회: 전체 11,131종 처리, 예외 0. primary linked_checklist 7,507종, snapshot_only 2,816종, needs_review 807종, 기존 수동 까치 표시 1종. 참고자료 연결은 GBIF 385종 + BIRDBASE 117종 + HKBWS 9종. needs_review 중 참고자료도 없는 대상은 296종이다. 직접 11,131회 HTTP 호출한 테스트가 아니다.
- 실제 DB 반환값 전체의 프런트 표시 함수 검증: 11,131종 처리, 실패 0. 표시 기준 LC 8,502, NT 926, VU 653, EN 360, CR 206, EW 5, EX 148, DD 35. 중립색 331은 DD 35와 미연결 296을 포함한다. 참고자료를 독립된 신규 평가로 계산하지 않는다.
- 실제 TEST 브라우저: 14개 사례 통과. 새 전문가 자료 9종 전부를 검증하고, 박새 PC 1280px 및 모바일 390px, 기존 까치·유리딱새·꼬까직박구리·청둥오리의 회귀를 포함했다. 본문과 카드 배지 노출, LC 색, 실제 API 학명, 새 자료 9종의 source URL 및 승인 record SHA를 검사했다. 박새 화면에서 이전 내부 검토 문구가 본문에 남지 않음도 확인했다.
- 브라우저 14건 중 큰기러기와 한국재갈매기 2건에는 외관 특징·재미있는 사실 제공처 경고가 있었다. 등급·출처·카드 색 검사는 통과했다. 이 부가 설명 제공처 문제를 해결했다고 기록하지 않는다. 사진의 로드 완료와 외관 설명의 생물학적 정확성을 이번 배지 검증으로 보증하지 않는다.
- `.gitattributes`에서 고정 JSON을 LF로 지정해 Windows 체크아웃에 따른 byte hash 변경을 방지했다. 생성·재생 스크립트의 텍스트 인코딩도 UTF-8로 명시했다. 실제 Windows 실행은 이번 로컬 검증에 포함하지 않았다.
- `graphify update .`로 AST 지식 그래프를 갱신했다. 의미 추출 API는 실행하지 않았다.

### 배포·커밋 식별자

- 첫 코드 커밋: `168bdf2dc339cb6a273a2572c28f605177d6638a` (6종 및 공통 reader/표시).
- 최종 런타임 코드: `71501e397c968bbe8a2ea095d3d3065418b59e34` (9종 및 속 변경·분할 관계 근거).
- 최종 TEST 이미지: `robingraph-api:test-expert-71501e3`, health 확인 완료.
- 패키지 SHA-256: `80841e508b6cf1570295240b517ae8d1f1d5611936d88600dd88b99d1bec2a44`.
- NAS TEST 배포 경로: `/home/kimdove/RobinGraph-expert-71501e3`. TEST 환경 파일만 준비하고 ROBINGRAPH_DEPLOY_TARGET=test로 배포했다. 자격 증명은 문서·패키지에 포함하지 않았다.
- 확인 URL: https://robingraph-test.dove-nest.com/chat
- 운영 컨테이너 ID·이미지·시작시간은 작업 전후 완전히 같았다. 운영은 `robingraph-api:prod-readable-5fce6eb`를 유지한다. DB 쓰기, 운영 재시작·배포·롤백, main 병합을 하지 않았다. 사용자의 운영 승인도 아직 없다.

### 결과 파일

`docs/verification/assets/2026-10-09-expert-conservation-runtime.json`은 실제 DB 재생 방법, 전체 통계, 전체 출력 SHA, 새 9종의 실제 반환값, 운영 전후 상태를 담는다. `2026-10-09-expert-conservation-display.json`은 전체 표시 검사이며, `2026-10-09-expert-conservation-browser.json`은 14회 실제 화면 검증과 경고를 담는다. 스크린샷은 로컬 `/tmp/rg-expert-final-browser`에 있으며 저장소에 대량의 PNG를 추가하지 않았다.

현재 결과는 전체 종에 대한 감사와 검증된 9종 자료 연결까지다. 미연결 296종이 해결되었다거나 모든 종의 최신 독립 평가 원문을 확보했다고 완료 처리하지 않는다. 후보 원문·분류 관계를 검토한 감사 목록이 후속 작업의 기준이다.

현재 미연결 296종 전체와 각 종의 분류 결정·출처 종 평가 후보를 `docs/verification/assets/2026-10-09-conservation-remaining-296.json`에 별도로 저장했다. 이 목록은 실제 최종 TEST 런타임에서 참고자료가 없는 taxon ID 집합과 296/296 일치하며, 이번에 연결한 9종은 제외했다. 후보의 등급을 현재 종의 등급으로 오해하지 않도록 명시했다.

공식·전문가 교차 검토의 최종 결과는 `docs/verification/2026-10-09-conservation-source-crosscheck.md`에 기록했다. HKBWS 목록과 다른 7종 모두 IUCN 공식 2025-2 또는 2023-1 변경표 PDF로 과거 등급 변경이 확인되어 기존 앱 값을 유지했다. 해당 7개 개별 IUCN 평가 페이지는 403/접근 불가였으므로 원문 본문을 직접 읽었다고 주장하지 않는다. 공식 변경표 PDF는 직접 다운로드와 해당 페이지 이미지 검증까지 수행했다.

Obsidian에는 `Work/RobinGraph/작업기록/2026-10-09-전체종-보전출처-재조사-TEST전용.md`와 `Work/RobinGraph/검토자료/2026-10-09-보전등급-전수출처-교차검토.md`를 저장하고 읽기 재검증했다. 프로젝트·작업기록·검토자료 index에도 각각 링크를 추가했다. 저장소 문서 본문과 Obsidian 본문이 일치함을 확인했다.

추가 회귀 점검에서 기존 BIRDBASE 447종 전수 테스트는 옛 미연결 305종이 계속 None이어야 한다는 기대 때문에 5개 중 1개 실패했다. 이번에 검토한 승인 레코드에 속한 종만 정확한 전문가 레코드를 반환하고, 나머지는 여전히 None이며 기존 GBIF/BIRDBASE 우선순위가 유지되는지 검사하도록 수정했다. 해당 5개를 포함한 최종 백엔드 관련 59개가 모두 통과했다. 애플리케이션 코드를 재변경한 것은 아니므로 TEST 런타임 revision은 71501e3을 유지한다.
