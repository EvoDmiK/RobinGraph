# 비교 후보의 일반 계통 근거

활성 AviList v2025b 종 전체에 `taxonomy-phylogeny-ecology-v3`를 적용한다. 계통 관계 50%, 분류 관계 30%(같은 속 20%·같은 과 10%), 같은 서식 환경 10%, 같은 먹이 생태 10%의 가중합 점수순으로 후보를 표시한다. 오리 두 종의 특별 규칙 없이 전체 종에 같은 계산을 적용한다. 가중치는 서비스의 초기 비교 정책이며 통계적으로 학습한 계수나 가장 가까운 유전적 종을 확정하는 값은 아니다.

계통 근거는 [McTavish et al. 2025, PNAS](https://doi.org/10.1073/pnas.2409658122)의 공개 [AvesData](https://github.com/McTavishLab/AvesData)에서 가져왔다. Aves 1.6 / Clements2025를 commit `c85b4b8e54c7031787c0506ea59fa02fc4f5ca6c`로 고정하고 CC BY 4.0으로 출처를 표시한다. `phylo_only_clements_labels.tre`, `OTT_crosswalk_2025.csv`, `annotations.json`, `rank_collection.json`의 SHA-256을 검증한다. 이 판은 논문이 소개한 Aves 1.3보다 새 자료이며, 정확한 파일 버전과 해시는 응답 `ranking.phylogeny`에 포함한다.

종 연결은 공식 AviList XLSX의 Avibase 종 개념 ID와 crosswalk의 고유 ID를 일치시키고, 현재 학명·Clements 영어 이름·활성 taxon ID·개념집합·분류판도 확인한다. 공식 식별자가 일치하는 속 이동·이명은 crosswalk를 통해 연결하며 유사 문자열이나 국명 번역으로 추정하지 않는다. 종 분할·통합이나 중복 식별자는 제외한다.

분류 제약 입력인 `ot_2019`와 `ot_2770`은 실제 계통 근거에서 제외한다. 대상과 후보 모두 비분류 연구의 tip 근거가 있어야 하며, 두 종이 공유하는 조상 중 비분류 연구 `supported_by`가 있는 가장 안쪽 조상을 사용한다. 근거 없는 하위 분기는 순위를 높이지 못한다. 연구가 충돌하는 경우 원 연구 식별자와 충돌 정보도 제공한다. 연구 수는 독립 실험 수나 통계적 신뢰도라는 뜻이 아니다.

날짜가 있는 summary tree와 무작위 taxon-addition 결과는 사용하지 않는다. 계통수에서 공통 조상을 공유하는 후보는 같은 계통 점수를 받는다. 숫자 depth는 한 대상의 조상 경로를 비교하기 위한 내부 값이며 유전 거리나 진화 시간을 뜻하지 않는다. 전체 활성 후보에서 확인된 서로 다른 공통 조상 단계들을 바깥쪽부터 순서대로 정렬한다. N개 단계 중 k번째 단계의 상대 점수는 k/N(1 ≤ k ≤ N), 계통 기여는 50 × k/N점이다. 깊이의 숫자 간격이나 후보 종 수로 가중하지 않는다. 단계가 하나면 모두 같은 상대 점수 1을 받으며 이는 조회 내 상대 순서일 뿐 절대적 가까움이나 신뢰도가 아니다.

계통 자료가 없는 후보는 계통 항목을 제외하고 나머지 50%를 100점으로 환산한다. `score_basis=taxonomy_ecology_fallback`, `phylogeny_available=false`, `available_weight=50`와 화면의 ‘분류·생태 대체 점수(계통 자료 부족)’로 구분한다. 이 대체 점수는 계통이 먼 것으로 측정한 0점이 아니며, 계통 자료가 있는 후보와 자료 범위·불확실성이 다르다. 생태 미확인 항목은 일치 가점을 받지 않는다.

`similarity_reasons[].weighted_points`는 원래 가중치 기준 기여이고 `points`는 환산 후 표시 기여다. 표시 기여의 합을 두 자리로 반올림해 `similarity_score`로 제공한다. 이 점수 내림차순으로 순위를 정하며 동점은 학명·taxon ID순으로 정한다. 계통 우선의 별도 정렬은 제거했다.

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
