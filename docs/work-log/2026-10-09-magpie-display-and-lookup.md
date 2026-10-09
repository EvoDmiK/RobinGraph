# 까치 LC 임시 표시와 두 까치 종의 이름·검색 구분

## 요청 배경과 최종 목표

사용자는 까치를 우선 LC로 표시하도록 요청했다. 이름 표기 요청의 최종 기준은 **Pica pica → Eurasian magpie**, **Pica serica → 까치 / Oriental magpie**, **한국어 ‘까치’ 검색 → Pica serica**다. 두 종의 분류·종 ID를 합치지 않고 앱의 표시·검색 정책을 명시적으로 적용한다.

## 확인한 원인과 변경 전후

기존 Pica serica는 활성 AviList v2025b 원자료 NE로, 평가 자료 연결 확인 필요 상태였다. Pica pica 역시 실제 NAS TEST 프로필의 원자료는 NE이며 한국어 표시는 없었다. GBIF 목록의 Pica pica LC를 앱 종에 자동 연결한 상태가 아니었다.

최종 변경 후 Pica serica의 앱 표시 등급은 LC, 배지는 **‘관심대상 (LC) · 임시 보정’**이다. `manual_override`로 저장하며 `independently_verified=false`, 원자료 NE·출처·해시·연결 검토 상태는 `original_snapshot`에 그대로 보존한다. 평가 원문을 새로 확인한 결과나 GBIF 연결 결과로 표현하지 않는다. 답변 출처 보기에 사용자 요청에 따른 보정 사유와 기존 AviList 자료를 표시한다.

Pica pica는 한국어 이름을 붙이지 않고 영어 **Eurasian magpie**로 표시한다. Pica serica는 출처가 있는 한국어 **까치**와 영어 **Oriental magpie**를 함께 표시한다. 과거 중간 변경의 Pica pica 한국어 ‘까치’ 표시는 최종 코드에서 제거했다. 영어 이름의 대소문자 표시는 사용자 요청대로 적용하되 학명·종 ID·분류 근거는 유지한다.

한국어 ‘까치’는 허용된 활성 AviList v2025b 개념집합에서 Pica serica의 정확한 종 ID `avilist-taxon:v2025b:20193`로 조회한다. 기존 한국어 그래프 레이블의 중복이나 변경에 의존해 Pica pica를 고르지 않는다. 실제 종이 없거나 ID·학명·rank·릴리스·개념집합이 맞지 않으면 이 지정 연결을 적용하지 않는다. DB의 분류와 이름 원자료를 수정하지 않는다.

## 구현 파일

- `retrieval/conservation.py`, `species_profile.py`: 검증된 AviList NE의 Pica serica 한 종에만 사용자 지정 LC 표시를 적용한다. 공개 평가 연결을 먼저 시도하고 기존 원본을 별도 객체로 보존한다.
- `api/static/chat.js`: 정확한 임시 보정 계약·종 ID·학명·원본 해시가 맞을 때 LC 색을 적용한다. 평가 검증 플래그는 false로 유지하며 보정 배지와 출처 설명을 제공한다. 다른 NE와 카드 제스처·배치는 유지한다.
- `retrieval/taxonomy_lineage.py`: 두 종의 영어 표시 대소문자를 지정하고 source-checked 한국어 이름과 구분한다. 반복 변환에도 같은 결과를 반환한다. 공식 이름 JSON은 변경하지 않았다.
- `retrieval/taxonomy_lineage_neo4j.py`: 한국어 ‘까치’를 활성 Pica serica의 정확한 종으로 연결하며 분류 컨텍스트·반환 종을 검증한다.
- `tests/test_conservation.py`, `tests/test_korean_display_names.py`, `tests/test_taxonomy_lineage_neo4j.py`, `tests/frontend/chat_ui.test.js`: 다른 종·새 릴리스·잘못된 ID·원자료 변조·이름 반복 변환·검색 대상 경계 회귀.
- `README.md`: 현재 임시 보정과 최종 이름·검색 정책을 설명한다.

경로는 모두 `src/robingraph/` 기준인 구현 파일과 저장소 루트의 테스트·README다. 근연종·생태 후보 선택은 원래 source-checked 한국어 이름 목록을 유지한다. 두 종을 같은 한국어 후보로 만드는 중간 변경도 되돌렸다.

## 협업과 검증

부모가 backend·검색·배포를 담당했고 `quality_audit_report`가 임시 LC 화면·frontend 검사와 최종 두 이름의 렌더러를 검토했다. 모의 DOM에서 Pica pica는 영어 주제목과 별도 학명, Pica serica는 한국어 제목과 작은 영어 이름으로 구분됨을 확인했다.

- Python 최종 전체: **677개 중 통과 642, 실패 0, 건너뛰기 35**. 33개는 기존 disposable Neo4j/PostgreSQL 환경 플래그가 없는 통합 검사, 2개는 기존 아종 자료의 외부 pinned 입력이 없는 검사다.
- Frontend 최종 전체: **261개 통과, 실패·건너뛰기 0**.
- `git diff --check` 통과.
- `graphify update .` 실제 실행: API/LLM 호출 없이 AST 그래프 **4,135 nodes / 8,623 edges / 239 communities** 갱신. 기존 SQL 추출기 미설치 한계는 유지된다.
- 중간 API 검증에서 Pica pica를 LC로 가정한 테스트 조건이 실패했다. 실제 원자료가 NE임을 확인하고 최종 요청에 맞게 기대값을 수정했다. 이 종에 새 LC 보정을 추가하지 않았다.

### 실제 서비스 검증 결과

공개 TEST API에서 Pica serica, Pica pica, Aegithalos concinnus, Anas platyrhynchos 네 종 모두 HTTP 200으로 확인했다. 각각 까치/Oriental magpie/LC 임시 보정, 영어 Eurasian magpie/기존 NE, 다른 NE 유지, 공개 IUCN LC 연결 유지가 예상과 일치했다. 배포된 chat.js 바이트도 커밋과 일치했다.

한국어 `name=까치` 프로필 조회가 Pica serica/LC를 반환했다. 실제 `/v1/chat`에 `question=까치`, `intent=profile`, `defer_enrichment=true`로 요청해 Pica serica/까치/Oriental magpie/LC 반환을 확인했다. 명시적 profile 의도의 채팅 조회 검증이며 Jev 자동 의도 분류까지 검증했다고 확대하지 않는다.

실제 공개 `/chat`을 Chrome+Playwright로 열고 실제 API 프로필 세 종(Pica serica/Pica pica/청둥오리)을 앱 렌더러에 삽입해 PC 1280×900과 모바일 390×844의 총 6개 조합을 검사했다. 이름·배지·화면 안 카드 크기·키보드 앞뒤 전환·보정 출처 설명을 확인했고 페이지 오류는 0건이었다. 프로필 삽입 렌더러 검증을 전체 자연어 채팅 E2E로 기록하지 않는다.

검증 산출물은 `docs/verification/assets/2026-10-09-magpie-{deployment,browser}.json`에 저장했다.

## 배포·커밋과 한계

LC 표시 구현 커밋 `71a8ff6`, 최종 이름·검색 수정 커밋 **`22ff90b05636a6259fcebabeaa9f46de91a39d6e`**다. 최종 NAS TEST 이미지는 `robingraph-api:test-magpie-22ff90b`, 경로는 `/home/kimdove/RobinGraph-magpie-22ff90b`다. Git 커밋 객체에서 생성한 인증 정보 없는 아카이브 SHA-256은 `8b1101e40d1bdf3dc4059130512bfdcc7df7987273bc16a0e3db73361bd4558e`이며 NAS에서 아카이브·내부 MANIFEST 검증을 통과했고 최종 TEST 컨테이너는 healthy다. 배포 전후 운영 컨테이너 ID가 동일함을 확인했으며 운영 이미지는 prod-e90ff85를 유지했다. main/dev 병합·문서 커밋·푸시는 Git 이력에서 확인한다.

LC 임시 보정은 검증된 IUCN 평가 자료를 새로 얻었다는 뜻이 아니다. Pica pica의 기존 NE 연결 검토 상태는 유지한다. 미래 분류 릴리스에는 이번 종 ID와 이름 정책을 자동 확대하지 않는다. DB 쓰기·원자료 재적재·제한 API 호출은 이 작업에 포함하지 않는다.

상세 기록은 Obsidian `Work/RobinGraph/작업기록/2026-10-09-까치-임시LC-이름-검색구분.md`에도 동일 내용으로 보존하고 프로젝트·작업기록 인덱스를 연결한다. 인증 정보는 문서·Git·배포 아카이브에 포함하지 않는다.
