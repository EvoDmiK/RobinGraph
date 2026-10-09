# GBIF 공개 IUCN 평가목록 연결과 NAS TEST 배포

## 요청 배경과 목표

IUCN API 신청 거절 이후 생성된 토큰으로 공식 API 정보 조회를 실행했지만 HTTP 401이 반환됐다. 사용자는 다른 출처를 찾자고 요청했고, 공식 GBIF 공개 배포본의 라이선스·실제 파일·연결 가능성을 조사한 뒤 “Obsidian mcp로도 올려주고, 일단은 진행하자 나중에 수정하더라도”라고 구현과 문서 저장을 승인했다.

목표는 보전 등급을 분류 체크리스트의 보조 값에만 의존하지 않고, 이용 근거와 종 연결을 확인한 공개 평가목록에서 공급하는 것이다. 이미 검증한 AviList fallback과 NE의 ‘평가 자료 연결 확인 필요’ 표시는 유지한다. 평가 대상이 불명확한 종에 다른 종의 등급을 상속하지 않는다.

## 출처와 원인 확인

출처는 [IUCN이 GBIF에 공개한 The IUCN Red List of Threatened Species](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3)다. 제공 기관은 International Union for Conservation of Nature, DOI는 `10.15468/0qnb58`, 자료 버전은 `2026-1`, 배포일은 `2026-07-28`, 라이선스는 **CC BY 4.0**이다. 등록 메타데이터와 ZIP 내부 EML의 라이선스가 일치함을 이전 조사와 독립 검토에서 확인했다. 원 API와 별도인 공개 배포본이며 다른 웹 본문이나 제한 API의 이용 권한을 확대하지 않는다.

- IUCN 공개 ZIP SHA-256: `2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d`.
- AviList v2025b JSON SHA-256: `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`.
- 생성 인덱스 SHA-256: `75d4aba60cc1da44f3ae5f4dd2d34be180c03da3e84fdb271176aa827ece75a6`.
- 상세 조사: [대체 출처 조사](2026-10-09-conservation-alternative-sources.md).

원본 ZIP의 accepted 조류 species 11,185개에 SIS별 Global 보전 등급이 한 개씩 있다. AviList와 비교할 때 명명자 이니셜 표기가 다른 경우가 많다. 예를 들어 `Linnaeus, C, 1758`과 `Linnaeus, 1758`은 동일한 단일 저자 표기의 이니셜 생략으로 처리하되, 연도·저자·괄호·다중 저자 차이를 임의로 제거하지 않는다. 명명자 완전 문자열 일치만 사용하면 12종만 연결됐으므로 이 좁은 구조 정규화만 추가했다.

## 변경 전후 동작

이전에는 허용된 활성 AviList 스냅샷의 등급을 `taxonomy_snapshot / snapshot_only`로 제공했다. NE는 실제 IUCN 미평가로 단정하지 않고 `needs_review`로 표시했다. 실제 평가 연도와 개별 평가 ID를 공급하지 않았다.

변경 후에는 검증된 AviList 행에 대해 고정 공개 인덱스를 조회한다. 종 ID·학명·명명자·기존 BirdLife SIS 링크·분류 개념집합·릴리스·스냅샷 SHA가 모두 맞고, 공개 자료의 accepted species·유일한 Global 행·평가 URL과 인용 ID가 연결되는 종에만 공개 평가목록을 우선 제공한다. 매칭은 이름 검색이나 fuzzy 추정이 아니다.

연결된 응답에는 다음을 제공한다.

- `evidence_kind=red_list_checklist`, `assessment_status=linked_checklist`, `independently_verified=false`.
- 세계 범위의 기본 등급, SIS·평가 ID, 공식 개별 IUCN 평가 URL, 개별 평가 인용.
- 공개 자료 버전·기관·인용·CC BY 4.0 링크·스냅샷 해시.
- 인용 연도와 DOI의 연도가 일치할 때만 개별 평가 연도. 자료 릴리스 연도로 채우지 않는다.
- AviList 원본 등급과 명명자 연결 방식. CR(PE/PEW) 표시는 공개 자료의 새 평가 flags로 만들지 않고 AviList 원본 보조 표시로 구분한다.

화면 배지는 `공개 평가목록 기준`을 표시한다. 답변 출처 보기에는 릴리스·평가 연도·공식 평가 링크·라이선스·인용과 검증 범위를 넣는다. 실시간 조회나 평가 원문 전체를 독립 검증했다고 표현하지 않는다. 자료가 누락되거나 맞지 않으면 기존 AviList 표시로 안전하게 돌아간다.

런타임 네트워크 호출과 API 키가 추가되지 않았다. 고정 JSON을 패키지에서 읽어 캐시한다. Neo4j·PostgreSQL 자료를 수정하거나 ingest하지 않는다.

## 연결 범위와 제외 이유

| 구분 | 종 수 |
| --- | ---: |
| 활성 AviList species | 11,131 |
| 공개 평가목록 연결 | 7,507 (67.44%) |
| 명명자 불일치 | 2,286 |
| AviList NE: 종 범위 검토 필요 | 808 |
| 학명 불일치 | 474 |
| 평가 ID·인용 연결 불일치 | 56 |
| fallback 합계 | 3,624 |

연결 명명자는 완전 일치 12건, 단일 저자 이니셜 생략 7,495건이다. 연결된 기본 등급과 기존 AviList 기본 등급의 차이는 0건이었다. 출처 연결·평가 연도·이용 근거가 강화된 결과이며, 등급이 바뀐 작업은 아니다.

연결 등급 분포는 LC 5,937, NT 634, VU 434, EN 255, CR 138, EW 3, EX 83, DD 23이다. 개별 평가 연도는 2017~2025이며 24건은 검증 가능한 연도 형식이 없어 값을 넣지 않는다.

`Pica serica`는 공개 목록에 없어 연결하지 않는다. `Pica pica`도 이번 엄격한 명명자 연결 조건을 통과하지 않았다. 한국어 이름이 같다는 이유로 LC를 가져오지 않는다. 재두루미 `Antigone vipio`도 이번 조건에서는 fallback을 유지한다.

## 변경 파일과 구현

- `scripts/build_conservation_index.py`: 네트워크 없는 재현 가능한 빌더. 두 입력 해시, 공개 라이선스·기관·릴리스·DOI, Darwin Core 컬럼·ID 구조를 검증한다. 중복·동의어·불확실한 종은 제외 이유를 기록한다.
- `src/robingraph/retrieval/conservation_index.json`: 릴리스와 분류 개념집합이 고정된 7,507종 공개 자료 인덱스. 원본 ZIP이나 인증 정보를 포함하지 않는다.
- `src/robingraph/retrieval/conservation.py`: 출처·활성 분류·종·명명자·등급·평가 URL/인용 ID 검증과 캐시 읽기. 실패 시 fallback.
- `src/robingraph/retrieval/species_profile.py`: 기존 허용 AviList 검증 뒤 공개 자료를 우선 연결한다. 기본/전체 프로필 모두 같은 읽기 경로를 사용한다.
- `src/robingraph/api/static/chat.js`: 허용된 GBIF 공개 자료 계약만 표시하고 출처·평가 연도·라이선스를 설명한다. 카드 제스처와 배치 변경은 하지 않는다.
- `tests/test_conservation_index.py`, `tests/test_conservation.py`, `tests/frontend/chat_ui.test.js`: 입력·출처·연결 경계와 실제 인덱스·표시 회귀.
- `README.md`: 현재 출처·연결 범위·NE 의미·재생성 방법을 설명한다.
- `docs/verification/assets/2026-10-09-gbif-iucn-{deployment,browser,live-db}.json`: 실제 배포 응답·브라우저·읽기 전용 DB 검증 결과.

## 협업 검토와 수정

구현을 분담했다. `conservation_quality_review`는 빌더·원자료 연결·인덱스와 테스트를 담당했고, `quality_audit_report`는 화면·출처 표시와 frontend 테스트를 담당했다. `pc_card_drag_fix`는 코드를 수정하지 않고 별도로 연결 안전성을 검토했다.

독립 검토에서 runtime의 평가 명명자 검증 누락을 보완했고, `Pericrocotus albifrons`의 원본 `'LC '`와 ingest된 `'LC'` 비교 때문에 한 종이 빠지는 문제를 수정했다. 비교만 trim/대문자 정규화하고 원본 값은 보존한다. 실제 종의 회귀 테스트를 추가했으며 최신 코드에 검토 범위의 미해결 버그나 배포 차단 사항이 없음을 재확인했다.

## 검증 방법과 실제 결과

### 로컬 자동 검증

- Python 전체: **673개 실행, 통과 638, 실패 0, 건너뛰기 35**. 명령은 `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests`.
- 건너뛰기 35개 중 33개는 전용/disposable 실제 Neo4j·PostgreSQL 통합 환경 플래그가 없는 기존 검사다. 나머지 2개는 기존 아종 이름 자료의 외부 pinned 원본 파일이 없는 검사다. 이 작업의 공개 자료 빌더·runtime 검사는 건너뛰지 않았다.
- 보전 자료 focused 검사: **28개 통과, 실패·건너뛰기 0**. 실제 인덱스 테스트와 모의 변조·경계 테스트를 포함한다. 네트워크/API 모의 성공을 실제 원자료 검증으로 기록하지 않는다.
- Frontend 전체: **259개 통과, 실패·건너뛰기 0**. 개발 중 새 출처 테스트 fixture의 sourceMaterial이 null인 검사 실패 1건을 고쳤으며 최종 전체 재실행은 통과했다.
- 실제 pinned 원본 두 파일로 `build_conservation_index.py --check`: 재현성 일치. 독립 검토에서도 같은 입력을 확인했다.
- 독립 검토의 번들 전수 runtime 호출: **7,507건 모두 연결**.
- `git diff --check`: 통과.

### 실제 NAS TEST DB와 공개 API

NAS TEST 컨테이너의 실제 Neo4j에 READ 모드로 조회했다. 허용 AviList v2025b/개념집합의 species 11,131개, 고유 종 ID 11,131개를 확인했으며, 실제 저장된 명명자·BirdLife 링크·정규화된 등급·스냅샷 SHA를 runtime으로 검증했다. **공개 자료 7,507 / fallback 3,624 / NE 검토 필요 808**로 빌더 coverage와 일치했다. 쓰기 쿼리나 DB 변경은 하지 않았다.

공개 TEST API `/v1/taxa/profile` 샘플 **11종 모두 HTTP 200**이고 예상 등급·출처·연결 상태·해시가 일치했다.

- 공개 자료 연결: Anas platyrhynchos(LC, 평가 2025), Numenius arquata(NT, 2017), Tragopan caboti(VU), Ciconia boyciana(EN, 2018), Calidris pygmaea(CR, 2021), Cyanopsitta spixii(EW, 2019), Raphus cucullatus(EX, 2024), Bathmocercus cerviniventris(DD, 2018).
- AviList fallback: Antigone vipio(VU).
- 종 범위 확인 필요: Aegithalos concinnus(NE), Pica serica(NE).

공개 `chat.js`와 `styles.css`가 배포 소스의 바이트와 일치했다. favicon 3개 경로도 HTTP 성공으로 확인했다. `/health`는 정상·neo4j·test를 반환했다. 이 기존 health 응답의 `taxonomy_release` 문자열은 fixture 기본값이므로 실제 활성 릴리스 증거로 사용하지 않았다. 실제 릴리스는 DB·개별 프로필 lineage를 기준으로 확인했다.

### 실제 브라우저 확인

설치된 Google Chrome을 Playwright로 실행하고 공개 TEST `/chat`의 실제 JS/CSS를 로드했다. 실제 API에서 받은 청둥오리·까치 프로필을 앱 렌더러에 삽입해 PC 1280×900과 모바일 390×844에서 총 **4개 조합**을 검사했다.

공개 평가목록 배지와 NE 배지, 화면에 카드가 들어오는 크기, 키보드 앞뒤 전환, 평가 연도 2025와 릴리스 2026-1의 구분, CC BY 출처 설명을 확인했다. 페이지 오류 0건이었다. 프로필 삽입 방식의 UI 검증이며 Jev 자연어 분류까지 실행한 전체 채팅 E2E로 확대해 기록하지 않는다.

## 커밋·패키지·배포

구현 커밋: **`fd8e959a6266c38f2a8172f185870bb382c63502`** — `feat: link conservation grades to the public GBIF IUCN checklist`.

`EvoDmiK/primary-conservation`에 origin/main 최신 `ab977b8`을 병합해 최신 카드·도넛·TEST favicon 변경을 함께 포함했다. Git의 커밋 객체에서 인증 정보 없는 배포 아카이브를 생성했다.

- 아카이브 SHA-256: `442fab133531746103461fc239a66e169508d1031e0055bcbcd8fc3876cabc8f`.
- NAS 경로: `/home/kimdove/RobinGraph-gbif-fd8e959`.
- 이미지: `robingraph-api:test-gbif-fd8e959`.
- 서비스: `robingraph-api-test`, 배포 대상 `test`, health **healthy**.
- 공개 주소: <https://robingraph-test.dove-nest.com/chat>.
- 아카이브 전체 해시와 압축 안 파일별 MANIFEST를 NAS에서 검증했다.
- NAS에 이미 존재하는 TEST/PROD 환경 파일을 NAS 내부에서 복사해 TEST 이미지 태그만 갱신했다. 자격 증명은 저장소·아카이브·문서에 포함하지 않았다.
- 배포 전후 PROD 컨테이너 ID가 같음을 확인했다. 운영 이미지 `robingraph-api:prod-e90ff85`를 이 작업으로 교체하지 않았다.
- 이전 TEST 이미지 `robingraph-api:test-chartlook-e90ff85`는 되돌리기 후보로 유지했다.

문서 커밋과 main/dev 병합·푸시는 Git 이력에서 확인한다. dev에 구현 커밋을 fast-forward 반영한 뒤 `graphify update .`를 실제 실행해 API/LLM 호출 없이 AST 그래프를 4,111 nodes·8,581 edges·236 communities로 갱신했다. 기존 SQL 4개 파일은 tree_sitter_sql 미설치로 추출되지 않았으며 문서·이미지 의미 추출은 이번 AST 갱신 범위에 포함하지 않았다. 구현 코드를 다시 빌드하지 않아도 되는 검증 기록만 후속 문서 커밋에 추가한다.

## Obsidian 저장과 남은 한계

조사 문서는 `Work/RobinGraph/검토자료/2026-10-09-보전등급-대체출처-GBIF-IUCN-공개목록.md`, 이 구현 기록은 `Work/RobinGraph/작업기록/2026-10-09-GBIF-IUCN-보전등급-연동-NAS-TEST배포.md`에 같은 핵심 내용과 검증 결과로 저장한다. 프로젝트·각 폴더 인덱스에도 연결한다. MCP로 쓰고 다시 읽어 저장 내용을 대조한다.

이 자료도 평가 기관은 IUCN이므로 별도 기관의 독립 평가가 아니다. 공개 목록은 고정 스냅샷이며 최신 실시간 위험 상태·평가 본문 전체·정확한 평가 날짜·CR PE/PEW flags를 제공하지 않는다. 전체 종의 32.56%는 이번 조건을 통과하지 않았고, 명명자 다중 저자 표기 정규화·분류 변경 개념 연결은 추후 별도 검토 대상이다. 24건의 평가 연도 결측은 남겨둔다.

현재는 NAS TEST에만 반영했다. 국내 법정 보호 등급과 국가·지역 적색목록을 IUCN 세계 등급의 대체값으로 섞지 않았다. 까치의 실제 종 범위 연결과 현행 국내 보호 상태 보완은 후속 작업으로 남는다. 기존 health 릴리스 기본값 표기의 개선도 별도 범위다.
