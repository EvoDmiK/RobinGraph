# 전종 trait crosswalk 생성기 구현 보고 (Claude) — 2026-10-09

작업 경로: `/Volumes/Dove-Nest-SSD/app-data/orca/kimdove/home/workspaces/RobinGraph/dev-3` (HEAD `4c62562`). 지정 새 파일 4개만 작성했고, 기존 파일·DB·ingest·UI·커밋·배포·`ponytail-cleanup` 브랜치는 건드리지 않았다. `.env`는 읽지 않았다. (`scripts/audit_trait_coverage.py`, `tests/test_trait_coverage_audit.py`는 GPT-6.1-sol의 미추적 파일이라 손대지 않았다.)

## 0. 먼저 구분할 것 — "원본에 없음"과 "매핑이 막힘"

이 산출물은 **매핑 인덱스**라서 "차트가 빈 이유"를 단정하지 않는다. 종마다 아래 세 경우가 섞여 있다.

| 경우 | 의미 | 인덱스에서의 표현 |
|---|---|---|
| 원본 행이 있고 1:1로 입증됨 | 연결해도 되는 행 | `accepted` |
| 원본 행(또는 이름이 같은 행)이 있으나 개념 일치가 입증 안 됨 | 매핑이 보류된 것이지 원본 부재가 아님 | `needs_review` (후보 대상 포함) |
| 이 종에 연결되는 원본 행이 인덱스에 없음 | 원본에 없을 수도, 개념이 갈라져 연결 불가일 수도 있음(구분은 이 도구 범위 밖) | 엔트리 없음 / 소스 쪽 `unresolved` |

AviList 11,131종 기준(실행 결과):

| | 승인(accepted) | 후보만 있음(needs_review) | 인덱스에 원본 행 없음 | 참고: 대상 없는 원본 행(unresolved) |
|---|---|---|---|---|
| AVONET | 10,037 | 545 | 549 | 427행 |
| EltonTraits | 8,633 | 1,001 | 1,497 | 359행 |

"인덱스에 원본 행 없음"은 **원본이 없다는 증명이 아니다**: 대상 없는 원본 행(분할로 개념이 쪼개진 행 등)이 그 종과 관련 있을 수 있으나 자동으로 잇지 않았다.

## 1. 산출물과 실행

| 파일 | 내용 |
|---|---|
| `scripts/build_trait_crosswalk.py` | 생성기 (표준 라이브러리만, 새 의존성 없음). 해시·구조 검증 → 결정적 생성, `--check`, `--fetch` |
| `src/robingraph/retrieval/trait_crosswalk.json` | 매핑 인덱스 5,263,145 B, SHA-256 `ec7e5fcbf5c4f5b6eb872eb7d4c3ead4ad5e1d665cdecd2bf9001f0ed064d8b1`, 엔트리 21,002 (AVONET 11,009 + Elton 9,993) |
| `tests/test_trait_crosswalk.py` | 24개 테스트 (아래 §5) |
| `/tmp/rg-trait-crosswalk-verification.json` | 생성 결과의 소스·구조·요약 + 출력 해시 (소스 행 없음) |

주의: 인덱스는 `retrieval/*.json`이라 `pyproject.toml`의 package-data에 포함되어 wheel/Docker 이미지가 5.3 MB 커진다. 적용측이 필요 이상 로드하지 않도록(예: 시작 시 1회) 고려할 것. 크기를 줄이려면 같은 이름 승인 엔트리의 evidence 제거가 가능하다(스키마 변경 없이).

### 원본 파일 위치와 해시
원본은 저장소에 복사하지 않았다. 내가 내려받아 쓴 위치(세션 임시): `/private/tmp/claude-501/-Volumes-Dove-Nest-SSD-app-data-orca-kimdove-home-workspaces-RobinGraph-ponytail-cleanup/783b279d-cd48-42e1-b516-308e3c6cd1f2/scratchpad/raw2/` (3개 파일명은 `avilist-2025b.json`, `BirdFuncDat.txt`, `AVONET_Supplementary_dataset_1.xlsx`, 모두 `raw/` 원본을 가리키는 심볼릭 링크). 같은 위치는 `--fetch`로 언제든 재생성된다.

| 원본 | URL | 크기 | SHA-256 (고정값과 일치 확인) |
|---|---|---|---|
| AviList v2025b | `https://explore.avilist.org/data/avilist-2025b.json` | 19,933,159 | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` |
| EltonTraits 1.0 (BirdFuncDat.txt) | `https://ndownloader.figshare.com/files/5631081` | 2,199,507 | `97216eb1797da077169ebb1ebea275db293b09fc62f8bb8911f9beb98c50d321` |
| AVONET (figshare 16586228 v7) | `https://ndownloader.figshare.com/files/34480856` | 21,524,673 | `eb645e83dddb40f1654a3e8d721998dbca76eff540231b7b809267c1e96f8d3e` |

라이선스(저장소 `config/source-registry.json`): AviList CC BY 4.0, EltonTraits CC0 1.0, AVONET CC BY 4.0. 해시·URL·릴리스·라이선스는 모두 `config/`에서 읽어 출력의 `sources`에 기록한다(코드에 중복 하드코딩 없음).

### 실행 명령과 실제 결과
```
python3 scripts/build_trait_crosswalk.py --fetch RAW_DIR              # 고정 URL에서 내려받고 해시 확인
python3 scripts/build_trait_crosswalk.py --raw-dir RAW_DIR            # 인덱스 (재)생성
python3 scripts/build_trait_crosswalk.py --raw-dir RAW_DIR --check    # 재생성 결과가 커밋 파일과 byte 동일한지 확인
```
- 생성: `wrote …/trait_crosswalk.json (5263145 bytes, sha256 ec7e5fcb…d8b1)`, 소요 약 4.5초.
- `--check` 실제 결과: `OK … identical (5263145 bytes, sha256 ec7e5fcbf5c4f5b6eb872eb7d4c3ead4ad5e1d665cdecd2bf9001f0ed064d8b1)`, 종료 코드 0. 출력에 타임스탬프·절대경로가 없고 키 정렬·콤팩트 직렬화라 결정적이다.
- 해시 불일치·구조 불일치·시트 누락 시 종료 코드 2와 사유 출력.

## 2. Avibase ID가 식별하는 것 (공식 문서 확인)
- Lepage et al. (2014), *Avibase, a database management system for bird taxonomy*, ZooKeys 420:117–135, doi:10.3897/zookeys.420.7089 (PMC4109484 전문 확인): Avibase는 "각각의 구별되는 개념 클러스터에 고유 식별자(Avibase ID)를 부여"하며, 고유 ID는 "항상 구별되는 하나의 circumscription 클러스터"를 뜻한다. 동일 범위(congruent) 개념은 같은 ID를 공유한다. 속 변경·철자 변경은 새 ID가 필요 없고, **분할·병합·부분 겹침처럼 생물학적 범위가 바뀔 때만** 새 ID가 필요하다고 한다.
- Cornell Clements 'Taxon Concept Id' 안내(검색 결과 요약으로만 확인, 페이지 원문은 403으로 직접 열람 못 함): 분할 시에도 기존 하위 개념의 ID는 유지되고 이름·순위만 바뀌며, 속/철자 변경은 ID를 바꾸지 않는다.
- 판단: ID 동일 = "같은 개념으로 큐레이터가 매핑함"의 강한 증거이지만 독립 검증은 아니다. 부분 겹침 개념은 문서가 인정한 한계다. 그래서 (a) ID가 고유 1:1이어야만 승인하고, (b) 이름이 같은데 ID가 다르면 "분할 전 자료"라고 단정하지 않고 `alignment needs_review`로만 기록했다.
- AVONET Metadata 시트: `Avibase.ID1`은 "BirdLife 기준 종 개념의 고유 Avibase ID", `Species1`은 HBW-BirdLife v5.0(2020-12), `Species3`는 BirdTree(Jetz et al. 2012). 크로스워크 시트의 `Match.type`에는 별표(*, "불완전 매칭") 값이 없음을 확인(전부 아래 6종 값).

## 3. 매핑 규칙 (구현됨, 종 하드코딩 없음)
- **AVONET → AviList**: `Avibase.ID1`(대소문자 정규화; AVONET `AVIBASE-…`, AviList `avibase-…`)이 AviList 종 **정확히 하나**의 `AvibaseID`와 같고, 다른 AVONET 행이 같은 ID를 쓰지 않으며, 그 대상 이름을 쓰는 다른 AVONET 행이 없을 때 `accepted/avibase_id_unique`.
- **Elton → AviList**: `Scientific`(=BirdTree 이름) → AVONET `BirdLife–BirdTree crosswalk`에서 **정확히 한 행**이며 `Match.type == '1BL to 1BT'`, 그 BirdLife 종이 크로스워크에 한 행만 있고 AVONET1에 유일한 행·`Avibase.ID1`이 있으며, 이 ID가 AviList 종 하나와 일치할 때만 `accepted/birdtree_birdlife_avibase_chain`. Elton `Taxo`가 `BL3`가 아니면(IOC27 111행) 체인이 성립해도 `needs_review`.
- **금지(코드에 없음)**: 이름 유사/편집거리/종소명만 일치/다중 대응 자동 선택. 테스트가 확인.
- **충돌**: 한 대상에 승인 후보가 여러 소스 행이거나, 대상 이름을 쓰는 다른 소스 행이 있으면 모두 `needs_review/multiple_source_rows_same_target`.
- 원본 행이 이름 정확일치 후보를 갖지만 개념이 입증 안 되면 `needs_review`, 방법 `exact_name_legacy`(기존 규칙에서 나온 후보라는 표시).

## 4. 결과 수치 (실행 결과)

| 데이터셋 | accepted | needs_review | unresolved |
|---|---|---|---|
| AVONET (11,009행) | 10,037 | 545 | 427 |
| EltonTraits (9,993 이름 있는 행; 이름 없는 2행은 인덱스 제외) | 8,633 | 1,001 | 359 |

accepted 세부: AVONET `same_name` 9,334 + `name_changed` **703**; Elton `same_name` 6,765 + `name_changed` **1,868**. 앞선 검토 보고서의 "복구 가능" Elton 1,882·체인 일치 6,821과 수치가 다른 이유(가능성 범위): (a) `Taxo`가 BL3가 아닌 68행은 체인이 성립해도 review로 이동, (b) 충돌 2행이 review로 이동, (c) 보고서의 1,882는 이미 정확일치가 있던 2건을 포함. 즉 **accepted T2 개수는 IOC27 제외·충돌 처리에 따라 달라지며**(이 규칙에서 Elton 1,868, AVONET 703) 규칙을 바꾸면 변한다.

unresolved/review 사유 카운터 (`summary.reasons`):
- AVONET: `exact_name_concept_id_mismatch` 545 (이름 일치·개념 ID 불일치, needs_review), `no_avibase_match_no_exact_name` 427 (unresolved)
- Elton: `birdtree_merges_birdlife_species` 826, `birdtree_splits_birdlife_species` 210, `avibase_id_not_in_avilist` 243, `taxo_not_bl3_crosswalk_basis_unverified` 68, `crosswalk_invalid_taxon` 4, `birdtree_name_not_in_crosswalk` 3, `birdlife_species_without_unique_avonet_avibase_id` 2, `exact_name_chain_target_mismatch` 2, `multiple_source_rows_same_target` 2
- Elton `Taxo=IOC27` 111행의 처리: 68 review(taxo 사유), 20 unresolved(분할 사유), 14 unresolved + 5 review(Avibase가 AviList에 없음), 4 review(분할 사유). **IOC27 승인 0건**(테스트로 확인).

충돌 2건(예): Elton `Colluricincla umbrina`→`Colluricincla tenebrosa`(ID 일치)인데, 같은 이름의 다른 Elton 행 `Colluricincla tenebrosa`는 체인상 `Pachycephala tenebrosa`로 감 → 둘 다 자동 승인 안 함, 사유 기록.

대표 종 (인덱스 실제 값):
- 직박구리: Elton `Ixos amaurotis`(SpecID 10338, 행 7105) → AviList `Hypsipetes amaurotis`(seq 23698), accepted/`name_changed`; AVONET도 accepted/`same_name`.
- 대백로: Elton `Casmerodius albus`(SpecID 5230) → `Ardea alba`(seq 5399), accepted/`name_changed`; AVONET accepted.
- 새매 `Accipiter nisus`(seq 8388): 이미 이름이 같아 AVONET·Elton 모두 accepted/`same_name`(복구가 아니라 유지 사례). 같은 속 이동 사례로 `Accipiter badius`→`Tachyspiza badia`(Elton accepted)를 테스트에 넣었다.
- Pica pica(seq 20198): AVONET(`AVIBASE-48CE29C5` ≠ AviList `avibase-FBBBA943`)와 Elton(BirdTree `Pica pica` = BirdLife 3종의 `Many BL to 1BT`) 모두 `needs_review` — 분할 전 자료라고 단정하지 않고 개념 정렬 검토 대상으로만 기록.
- **Pica serica: 인덱스에 엔트리 0건** (출처 `source_name`에도 `target_name`에도 없음). Elton·AVONET에 원본 행이 없다는 앞선 확인과 일치하며, 어떤 행도 Pica serica로 연결하지 않았다.

## 5. 회귀 검증 (실제 실행 결과)

| 실행 | 결과 |
|---|---|
| `ROBINGRAPH_TRAIT_RAW_DIR=<raw2> PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest tests.test_trait_crosswalk` | 24개 모두 OK |
| 같은 테스트, 원본 없이(기본 환경) | 24개 중 22 OK, 2 skipped (실제 원본 필요한 재생성·변조 테스트) |
| 전체 `python -m unittest discover -s tests` | **719개 실행: 통과 682, 실패 0, 건너뜀 37** (기존 35 + 이 파일의 2) |
| `--check` | 종료 코드 0, 바이트 동일 |

테스트가 덮는 항목: 원본 해시 변경(임시 파일에서 1바이트 변조 시 실패 + 실제 원본 복사본 1바이트 변조 시 `eltontraits` 해시로 중단) · 구조 검증(AviList 행 수, Elton 컬럼, AVONET 시트 누락) · 고정 설정 누락(sha 비어 있음) 거부 · 분류판(Taxo IOC27 비승인) · 다중 대응(Many BL to 1BT, 1BL to many BT 비승인) · 중복 ID(AVONET 소스 중복, AviList ID 비고유) · 이름 같고 ID 다름(review, Milvus migrans 포함) · 이름 유사/종소명 일치만으로는 매칭 안 됨 · 충돌(소스 복수 행) 비승인 · 대표 복구(직박구리·대백로·새매·Accipiter badius) · Pica serica 미연결 · 커밋된 파일의 요약/불변식/정본성.

테스트의 한계: 합성 픽스처 테스트는 규칙 구현을, 실제 원본 테스트(환경변수 필요)는 현재 데이터의 결과를 검증한다. 기본 CI에는 원본이 없어 후자 2개가 skip되므로 CI에서 byte 동일 재생성을 보려면 원본 디렉터리를 제공해야 한다.

## 6. 스키마 (적용측용, `schema` 키에도 동일 문서화)
`entries`의 각 행은 열 순서 고정 배열: `dataset, source_row, source_id, source_name, source_taxonomy, target_sequence, target_name, target_avibase_id, status, method, name_relation, reason, evidence`.
- 적용은 `status == 'accepted'`만. `needs_review`의 target은 후보이며 승인 아님. `unresolved`는 target 없음.
- 소스 값·비율은 이 인덱스가 바꾸거나 복사하지 않는다. 적용측이 `dataset`+`source_row`/`source_id`로 기존 원본 행을 찾아 `target_sequence`(AviList Sequence)의 종에 붙인다.
- 최상위: `sources`(해시·URL·릴리스·라이선스·크기), `structure`(검증한 행 수), `policy`(규칙·Avibase 의미), `summary`(카운터, 사유 코드, 승인 대상 수, 승인 소스가 없는 AviList 종 수).

## 7. 알려진 한계·미확인
- Avibase ID가 같은 개념이라는 점은 AVONET·AviList 파일 안의 값만 비교했다. Avibase 서비스 자체 조회나 Cornell 페이지 원문 열람은 못 했다(HTTP 403).
- Elton `Taxo=BL3` 행이 BirdTree 이름과 일치함(9,993 전부 일치)을 근거로 AVONET의 BirdLife–BirdTree 교차표를 적용했다. Elton 저자가 BL3를 어떤 시점의 BirdLife 분류로 썼는지는 이 검증 범위 밖이다. IOC27 행은 요청대로 별도 review.
- 실제 NAS TEST Neo4j/PostgreSQL의 클레임·후보 노드와 이 인덱스를 대조하지 않았다(GPT-6.1-sol 영역). 기존 `TaxonMappingCandidate` 노드의 해결 상태 갱신, 클레임 재동기화, 조회 계층 적용은 하지 않았다.
- AVONET의 `Inference=YES` 행(다른 종 값 차용)은 매핑 대상이지만 값 자체가 추정이다. 인덱스는 각 AVONET 엔트리의 `evidence.inference`로 그 플래그만 전달한다. 적용측이 기존대로 추정 표시를 유지해야 한다.
- 5.3 MB 파일 크기(§1), IUCN·한국어 국명·UI는 범위 밖.


## 8. 통합 검토에서 보강한 1차 근거

Codex는 [EltonTraits 원저자 메타데이터](https://ndownloader.figshare.com/files/5631093)의 Taxonomy 절을 직접 확인했다. 해당 자료는 조류 분류가 Jetz et al. (2012)와 같으며 BirdLife v3 (June 2010)를 주로 따른다고 명시한다. 따라서 앞 절의 BL3 시점 미확인 한계는 이 추가 확인으로 해소했다. IOC27 행 자동 연결은 이번 정책에서 계속 보류하여 승인 범위를 넓히지 않았다.

메타데이터 파일 SHA-256은 `be3425118c2087a2795dff699d8264cbbc1b0c65fdbb93f0a7533b2d4ea54962`다. 이 파일은 원자료 비율이 문헌 설명을 표준화한 반정량적 추정임도 설명한다. 개별 행의 추가 추정 여부와 자료 확실성 코드는 그대로 보존해야 한다. 분류 개념 연결 승인이 모든 값의 현장 직접 측정을 뜻하지 않는다.
