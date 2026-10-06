# 비교 후보의 일반 계통 근거

활성 AviList v2025b 종 전체에 `taxonomy-phylogeny-ecology-v2`를 적용한다. 기존 오리 두 종의 특별 규칙은 삭제했다. 같은 속, 같은 과를 먼저 확인하고, 같은 분류 범위에서는 출처가 있는 공통 조상 관계를 생태 일치 점수보다 먼저 반영한다. 계통 자료가 없는 종은 먼 종으로 단정하지 않고 속·과·생태 자료로 표시한다. 따라서 가장 가까운 유전적 종을 모든 종에 대해 확정하는 서비스는 아니다.

계통 근거는 [McTavish et al. 2025, PNAS](https://doi.org/10.1073/pnas.2409658122)의 공개 [AvesData](https://github.com/McTavishLab/AvesData)에서 가져왔다. Aves 1.6 / Clements2025를 commit `c85b4b8e54c7031787c0506ea59fa02fc4f5ca6c`로 고정하고 CC BY 4.0으로 출처를 표시한다. `phylo_only_clements_labels.tre`, `OTT_crosswalk_2025.csv`, `annotations.json`, `rank_collection.json`의 SHA-256을 검증한다. 이 판은 논문이 소개한 Aves 1.3보다 새 자료이며, 정확한 파일 버전과 해시는 응답 `ranking.phylogeny`에 포함한다.

종 연결은 공식 AviList XLSX의 Avibase 종 개념 ID와 crosswalk의 고유 ID를 일치시키고, 현재 학명·Clements 영어 이름·활성 taxon ID·개념집합·분류판도 확인한다. 공식 식별자가 일치하는 속 이동·이명은 crosswalk를 통해 연결하며 유사 문자열이나 국명 번역으로 추정하지 않는다. 종 분할·통합이나 중복 식별자는 제외한다.

분류 제약 입력인 `ot_2019`와 `ot_2770`은 실제 계통 근거에서 제외한다. 대상과 후보 모두 비분류 연구의 tip 근거가 있어야 하며, 두 종이 공유하는 조상 중 비분류 연구 `supported_by`가 있는 가장 안쪽 조상을 사용한다. 근거 없는 하위 분기는 순위를 높이지 못한다. 연구가 충돌하는 경우 원 연구 식별자와 충돌 정보도 제공한다. 연구 수는 독립 실험 수나 통계적 신뢰도라는 뜻이 아니다.

날짜가 있는 summary tree와 무작위 taxon-addition 결과는 사용하지 않는다. 계통수에서 공통 조상을 공유하는 후보는 계통상 같은 단계로 취급하고, 생태 일치 점수·학명·taxon ID는 그 안의 표시 순서만 결정한다. 숫자 depth는 한 대상의 조상 경로를 비교하기 위한 내부 값이며, 유전적 거리나 종 사이의 진화 시간을 뜻하지 않는다. 화면 점수는 같은 속 50 + 같은 과 30 + 같은 서식 환경 10 + 같은 먹이 생태 10의 일치 점수다. 근연 관계가 앞서므로 점수가 낮은 후보가 먼저 표시될 수 있다.

## 수집과 재생성

공개 정적 파일을 검증해 앱과 함께 배포하는 최소 경로를 사용한다. n8n에 새 주기 작업을 등록하지 않았다. 실시간 API 의존성과 대형 계통수의 n8n 메모리 부담 없이 같은 원본으로 재현할 수 있다.

`build_phylogenetic_index.py`는 활성 종의 JSON export (`taxonomy_release`, `concept_set_id`, `species`: `taxon_id`, `scientific_name`, `english_name`)와 공식 AviList Extended XLSX를 입력받는다. 파일 경로를 준비한 뒤:

```sh
uv run --locked --extra test python scripts/build_phylogenetic_index.py \
  --tree /path/phylo_only_clements_labels.tre \
  --crosswalk /path/OTT_crosswalk_2025.csv \
  --annotations /path/annotations.json \
  --rank-collection /path/rank_collection.json \
  --active-species /path/active-species.json \
  --avilist-workbook /path/AviList-v2025b-Extended.xlsx \
  --avilist-url https://www.avilist.org/checklist/v2025b/
```

산출물은 `src/robingraph/retrieval/species_phylogeny.json`이다. 원문 전체나 모든 종 쌍의 행렬 대신 종별 조상 경로·근거·식별 정보를 저장한다. 분류판/개념집합이 바뀌면 기존 계통 근거를 자동 적용하지 않으며 새 입력으로 재검증해야 한다. API는 요청마다 활성 후보를 대조하므로 삭제되거나 다른 종으로 바뀐 ID는 근거를 받지 못한다.

## 적용 범위

- 활성 종 11,131; phylogeny-only 원본 tip 9,603.
- 고유 종 개념과 비분류 연구 근거가 확인된 연결 9,518종.
- 1,613종은 계통 근거 없이 분류 자료로 표시: 원본 계통수에 없음 1,534, 고유 crosswalk 개념 없음 40, 학명 변경/중복 15, 비분류 tip 근거 없음 24.
- 비분류 연구로 뒷받침된 내부 조상 9,428개.

Claude는 원본·분류 제약 입력을 감사했고, GPT는 파서·식별 검증·공통 조상 조회·검증을 구현했다. Antigravity는 독립적으로 순위 정책과 누락 자료 처리의 의미를 검토했다. 검증 결과와 배포 기록은 별도 verification 문서에 남긴다.
