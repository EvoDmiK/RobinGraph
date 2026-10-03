# RG-003 · RG-004 관계 자료 확대 검증

구현 커밋: `f2fd88e85d043f035d4e92ec4352f62eb91f8850`.

- 33개 이름 엔티티, 70개 고유 검색어, 47개 관계, 37개 고유 대상 종. 모든 관계에 출처와 구분 설명을 기록.
- 고정 AviList 2025b 원본의 species 행을 정확한 학명으로 대조: 37/37, 각 1개. 원본 SHA-256은 [조사 목록](../name-relations-coverage.md)에 기록.
- Python 전체: 502개, 32개 skip, 실패 0. 관계 단위 테스트 17개 포함.
- 프런트엔드: 81개, 실패 0.
- 격리된 실제 PostgreSQL 16 / Neo4j 5.26.30 통합 테스트: 1개 통과. 모든 등록 검색어의 관계 조회, 모든 이름 엔티티의 자연어 질문, dry-run·적재·재실행·분류판 변경·후보 누락 거부 검증. 테스트 그래프는 실제 운영 데이터가 아니다.
- Chromium 320·390·1280px: 거위 후보 선택 후 관련 종 설명, 연속 앵무새 질문과 3개 후보, 가축형 경고, 가로 넘침·JS 오류 없음.
- graphify AST 업데이트 완료.
- NAS 릴리스 패키지 생성 완료. 새 조사 문서도 배포 허용 목록에 포함.

## 고정 분류판의 대상 목록

| 학명 | 원본 영어 이름 |
|---|---|
| Agapornis fischeri | Fischer's Lovebird |
| Alauda arvensis | Eurasian Skylark |
| Anas platyrhynchos | Mallard |
| Anser anser | Greylag Goose |
| Anser cygnoides | Swan Goose |
| Ardea alba | Great Egret |
| Ardea intermedia | Medium Egret |
| Asio flammeus | Short-eared Owl |
| Bubo bubo | Eurasian Eagle-Owl |
| Cairina moschata | Muscovy Duck |
| Columba livia | Rock Dove |
| Corvus corone | Carrion Crow |
| Corvus macrorhynchos | Large-billed Crow |
| Coturnix japonica | Japanese Quail |
| Cygnus columbianus | Tundra Swan |
| Cygnus cygnus | Whooper Swan |
| Cygnus olor | Mute Swan |
| Dendrocopos major | Great Spotted Woodpecker |
| Egretta eulophotes | Chinese Egret |
| Egretta garzetta | Little Egret |
| Gallus gallus | Red Junglefowl |
| Grus japonensis | Red-crowned Crane |
| Lonchura striata | White-rumped Munia |
| Meleagris gallopavo | Wild Turkey |
| Melopsittacus undulatus | Budgerigar |
| Motacilla alba | White Wagtail |
| Motacilla cinerea | Grey Wagtail |
| Motacilla grandis | Japanese Wagtail |
| Numida meleagris | Helmeted Guineafowl |
| Nymphicus hollandicus | Cockatiel |
| Pavo cristatus | Indian Peafowl |
| Phasianus colchicus | Common Pheasant |
| Picus canus | Grey-headed Woodpecker |
| Serinus canaria | Atlantic Canary |
| Streptopelia orientalis | Oriental Turtle Dove |
| Streptopelia roseogrisea | African Collared Dove |
| Suthora webbiana | Vinous-throated Parrotbill |

## NAS TEST 적용·실환경 검증

- 배포 디렉터리: `/home/kimdove/RobinGraph-rg004-f2fd88e`.
- TEST 이미지: `robingraph-api:test-rg004-f2fd88e`; 구현 커밋은 위와 동일.
- SSH 접속 복구 후 별도 릴리스 디렉터리를 사용. 기존 checkout·기존 환경 파일·PROD 스택을 수정하지 않았다.
- 전송 아카이브 SHA-256: `5029f6e6329633af617fa3b039125c4c3198d9168bbd8b31204997a298eed6f7`, 로컬/NAS 일치.
- 활성 개념집합: `rg:concept-set:avilist-v2025b`. dry-run으로 37종·47관계 검증 후 적용. 재실행은 `Already active; no writes` 확인.
- 활성 manifest SHA-256: `1d398d0a8bc415c81ca50055b507b110e453aee5e56502ca8045b5ba276f627d`.
- 실행 중 TEST API에서 70개 검색어의 모든 후보 집합과 출처, 33개 이름의 자연어 질문(`clarify`, `name_relations`), 5개 학명의 역방향 조회를 확인했다.
- TEST 컨테이너의 HTTP `/health`가 정상이고 `deployment_target=test` 확인. health의 `taxonomy_release=fixture-avlist-2025`는 정적 설정 표기이며, 실제 관계 dry-run·조회에 사용한 활성 분류판은 위의 AviList 개념집합이다.
- NAS TEST로 SSH 터널을 연결한 실제 Chromium 320·390·1280px 화면: 거위 후보 선택→관련 종 설명, 이어서 앵무새 질문→3개 후보, 가축형 안내, 가로 넘침·JS 오류 없음.
- PROD 활성 데이터 준비는 RG-002 별도 범위다.
