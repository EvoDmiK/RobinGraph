# n8n 종별 분류·생태·형태 정보 수집

**NAS 실검증 상태(2026-09-10):** reference 기준정보와 AVONET 적재를 모두
완료했다. AVONET은 11,009개 프로필 중 9,879종을 AviList에 매핑해 형질 claim
128,331개를 적재했고, 미매핑 1,130개는 후보로 보존했다. 원본 형질값 143,004개와
모든 기대 개수가 일치한 뒤에만 active release를 갱신했다. 정식 import artifact는
전체 workbook 파싱의 메모리 한계 때문에 계속 비활성으로 유지한다.

메모리가 제한된 현재 NAS에서는 `scripts/load_n8n_avonet.py`가 우회 경로를
제공한다. 로컬에서 고정 XLSX의 SHA-256과 선택 시트 전체 행·형질 개수를 먼저
검증하고, 성공한 경우에만 100종 단위로 임시 인증 webhook과 Neo4j Query API를
통해 적재한다. 임시 workflow와 credential은 성공·실패 모두 정리하며, 모든 배치의
정확한 매핑 개수를 확인하기 전에는 active release를 갱신하지 않는다.

관찰 위치·날짜와 별개로 종 도감에 필요한 정보를 수집한다. 충분한 메모리의
n8n에서는 두 JSON을 아래 순서대로 실행할 수 있고, 현재 NAS에서는 아래의
메모리 안전 로더를 사용한다.

| 순서 | import 파일 | 수집 내용 |
|---|---|---|
| 1 | `n8n/robingraph-reference-ingest.json` | AviList 목·과·속·종·아종, 학명·영명·분포 설명, EltonTraits 체중·먹이 구성·먹이활동 층위·야행성 |
| 2 | `n8n/robingraph-avonet-ingest.json` | AVONET 부리 길이·폭·깊이, 부척·접힌 날개·꼬리 길이, 체중, 서식지 유형·개방도, 영양 단계·먹이 틈새·생활 방식 |

## 실행 방법

1. n8n의 **Import from File**로 첫 JSON을 불러온다.
2. `n8n-nodes-neo4j` community node를 설치하고 모든 Neo4j 노드에 같은 DB
   credential을 연결한다. 첫 workflow는 ID 고유성 제약을 자동 준비하므로 해당
   계정에 제약 생성 권한이 필요하다. 기존 중복 ID가 있으면 적재 전에 중단한다.
3. 첫 workflow의 성공·실패 Discord 노드에 알림 credential을 연결한다.
4. **Execute Workflow**로 첫 수집을 실행한다. 최종 검증 노드에서 taxonomy
   33,684개, 계층 연결 33,638개, EltonTraits claim 46,512개와 미매핑 후보
   2,241개를 확인한다. 성공해야 `reference-taxonomy`가 `v2025b`를 가리킨다.
5. 두 번째 JSON을 import하고 Neo4j credential을 연결해 수동 실행한다.
   첫 workflow가 완료되지 않았거나 다른 분류판이면 적재하지 않는다. 입력은
   `AVONET1_BirdLife`의 11,009종이다. 고정 원본의 오프라인 비교 결과는
   9,879종 매핑, claim 128,331개, 미매핑 후보 1,130개이며, 실제 적재에서도
   이 수치를 확인한다. 성공한 실행만 `reference-avonet`의 active release를 갱신한다.

두 workflow는 비활성 상태로 제공한다. 기준정보는 고정 릴리스이므로 수동 실행만으로
수집 가능하다. 첫 workflow의 주간 스케줄을 사용할 때는 n8n 실행 동시성을 1로
설정한다. AVONET에는 정기 스케줄이 없으며 새 릴리스 반영 시 다시 실행한다.
실제 운영 활성화 전에 해당 n8n/Neo4j에서 수동 실행 결과를 확인한다.

## 데이터 해석

- 길이는 `mm`, 체중은 `g`다. AVONET 측정치는 종별 평균이며 개체별 범위나
  암수별 대표값으로 표시하지 않는다. 원본 필드·행·시트와 표본 수를 보존한다.
- `Wing.Length`는 **접힌 날개 길이**다. 양 날개를 펼친 **날개폭**이나 몸길이로
  바꾸어 표시하지 않는다.
- `Habitat.Density`는 dense / semi-open / open 범주이며 실제 수목 밀도 측정값이
  아니다. 선호 식물 종이나 식물 군락에 대한 근거도 아니다.
- 원본의 `Inference`, `Traits.inferred`, `Reference.species`를 보존해 추정 형질과
  참조 종을 확인할 수 있다.
- EltonTraits의 먹이·먹이활동 분포는 원본 퍼센트를 유지한다. 각 값은 0~100이고,
  합계는 100±1 percentage point를 허용한다. 고정 원본의 381행은 먹이활동 합계가
  99이므로 경고를 남기며 100으로 재정규화하지 않는다.
- 다른 출처의 체중은 별도 claim이다. 평균내거나 한 출처로 덮어쓰지 않는다.
- 학명이 AviList 종에 정확히 하나만 대응할 때 연결한다. 미대응·모호한 이름은
  원본 프로필을 가진 매핑 후보로 남긴다. 이름 일치는 분류 개념의 완전한 동일성을
  보장하지 않으므로 종 분할·통합과 동의어 보완은 별도 검토 대상이다.

깃털 색·무늬와 암수·계절별 식별 설명, 몸길이·날개폭, 특정 식물과의 연관성은
이번 원본에 포함되지 않아 채우지 않는다. NIBR·EcoBank 등 추가 설명 자료는
선택한 자료의 접근 계약을 확정한 후 연결해야 한다.

## 출처와 재현성

- [AviList v2025b](https://www.avilist.org/checklist/v2025b/): Extended XLSX,
  CC BY 4.0. 상세 해시와 수용 기준은 [기준정보 런북](reference-ingest.md).
- [EltonTraits](https://doi.org/10.6084/m9.figshare.c.3306933.v1): 조류 파일
  `5631081`, CC0. 원본 먹이 분류·출처·확실성 필드를 함께 저장한다.
- [AVONET 데이터 v7](https://doi.org/10.6084/m9.figshare.16586228.v7):
  `AVONET Supplementary dataset 1.xlsx`, file `34480856`, **CC BY 4.0**.
  논문이 아닌 [데이터 객체 메타데이터](https://api.figshare.com/v2/articles/16586228/versions/7)의
  라이선스를 확인했다. 인용: Tobias et al. (2022), AVONET,
  [Ecology Letters](https://doi.org/10.1111/ele.13898).

모든 파일의 URL·버전·SHA-256은 `config/collection-points.json`에 고정한다.
해시나 행 수가 바뀌면 자동으로 최신판을 받아들이지 않고 중단한다. 중간 batch의
실패로 일부 노드가 남을 수 있으나 완료 릴리스는 갱신하지 않는다. 조회할 때는
성공한 `IngestState.last_successful_run_id`의 `IngestionRun`에 연결된 자료만 사용한다.

## 로컬 생성·검증·API 배포

```sh
uv run --locked python scripts/generate_n8n_reference_ingest.py
uv run --locked python scripts/generate_n8n_avonet_ingest.py
uv run --locked python scripts/deploy_n8n_reference_ingest.py
uv run --locked python scripts/deploy_n8n_reference_ingest.py --workflow avonet
uv run --locked python scripts/load_n8n_avonet.py
uv run --locked --extra test python -m unittest discover -s tests -q
```

배포 스크립트는 기본적으로 로컬 파일만 확인한다. `.env.example`을 참고해
Git 제외 `.env`에 n8n API URL/key와 credential 이름을 설정하면 `--remote`로
읽기 전용 점검, `--apply`로 비활성 workflow 생성·갱신을 할 수 있다.

```sh
uv run --locked python scripts/deploy_n8n_reference_ingest.py --apply
uv run --locked python scripts/deploy_n8n_reference_ingest.py --workflow avonet --apply
```

각각 `ROBINGRAPH_N8N_REFERENCE_WORKFLOW_ID`, `ROBINGRAPH_N8N_AVONET_WORKFLOW_ID`를
사용한다. 활성 workflow를 덮어쓰지 않으며 기존 비활성 workflow 갱신 전에는
백업한다. 배포 명령 자체는 수집·스케줄 활성화·Discord 전송을 실행하지 않는다.

AVONET 로더도 기본 실행은 다운로드·로컬 검증만 수행한다. 검증 요약이
11,009종·원본 형질값 143,004개인지 확인한 뒤에만 원격 적재를 명시한다.

```sh
uv run --locked python scripts/load_n8n_avonet.py --apply
```
