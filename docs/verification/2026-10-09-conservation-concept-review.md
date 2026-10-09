# 조류 전종 보전 등급 및 분류 개념(Taxon Concept) 연동 실측 조사 보고서 (개정판)

- **문서 위치**: `/tmp/rg-conservation-concepts-antigravity.md` (임시 경로 `/tmp`에 작성)
- **작성 일시**: 2026-10-09T18:36:00+09:00
- **조사자**: Antigravity (Orca Dispatched Worker, Terminal Handle: `term_49e80969-9a2d-4603-954f-70bb81544eae`)
- **작업 ID**: `task_25fa1fe266f2` / **디스패치 ID**: `ctx_4331e75dcaf2`
- **코디네이터**: Codex /root (`term_c30158ce-fff2-4b5b-9c7e-41093af6ea31`)
- **대상 저장소 기준**: `/Volumes/Dove-Nest-SSD/app-data/orca/kimdove/home/workspaces/RobinGraph/dev-3` (감사 기준선 `0689001`, 구현 `d4204bf`)
- **작업 성격 (Ownership)**: **조사·감사 보고서 수정 전용 (Research & Report Only)**. 소스 코드, 인덱스 파일, DB, 배포 환경 일체 미변경.

---

## 목차 (Table of Contents)
1. 이전 초안의 과잉 주장 정정 내역 (Corrected Overclaims)
2. 고정 원본 및 검증된 사실 (Knowns & Verified Ledger)
3. 큰부리까마귀(*Corvus macrorhynchos*) 실측 대조
4. 참고평가 360종 중 비-LC (CR/EN/VU/NT) 28개 출처 개념 실측
5. 미확인 사실 및 한계 (Unknowns & Scope Boundaries)
6. 런타임 계약 및 출처 URL (Runtime Contract & Reference URLs)

---

## 1. 이전 초안의 과잉 주장 정정 내역 (Corrected Overclaims)

본 보고서는 이전 초안에서 발생한 비근거 추정과 과도한 주장을 전면 배제하고 사실 중심으로 재작성되었다:
1. **학명 부재 330종 및 808개 NE 종 단정 삭제**: 330종 전체를 신규 분할종 또는 실제 미평가종으로 단정하거나, 808개 전수가 Avibase 불일치 때문이라고 일반화한 서술을 제거함 (AviList NE 808종 중 제안/결정문 보유는 770종, 미보유 38종).
2. **Corvus philippinus의 IUCN 포함 단정 및 sensu lato 용어 배제**: IUCN ZIP 내 philippinus 부재가 macrorhynchos 평가에 포함됨을 입증하지 못하므로, 독자적 범위 증거 없는 sensu lato/sensu stricto 규정 및 인과 단정을 배제하고 **개념 일치 미확인(taxonomy_alignment: unverified)**으로 정정함.
3. **까마귀 생물학적 LC 자체 판정 및 개체수/분포역 추정치 삭제**: 서식 면적 수치나 개체수 추정, IUCN 기준 자체 충족 주장 등 독자적 생물학적 평가를 전면 삭제함.
4. **국내 적색목록(NIBR 2019)·법정지위·공공누리 제4유형 및 비-LC 28종 국명 삭제**: 독립 검증되지 않은 국내 법적 보호/유해동물 지위 및 임의 국명을 삭제하고 **국내 지위 미검증(not verified)**으로 명시함.
5. **인덱스 references(360종)의 성격 정정**: 360개 참고평가는 이전 기준선이 아닌 이번 작업(runtime reference_checklist 계약)에서 신설된 것임.
6. **런타임 API 응답 규격 정정**: AviList NE 종의 런타임 API `category`는 `null`이며, 원본 `category_raw: "NE"`가 보존됨.

---

## 2. 고정 원본 및 검증된 사실 (Knowns & Verified Ledger)

### 2.1 고정 원본 및 무결성 검증
- **AviList v2025b JSON**: `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` (`/tmp/robingraph-global-avilist-2025b.json`, 19,933,159 B)
- **GBIF IUCN DwC-A ZIP (2026-1)**: `2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d` (`/tmp/robingraph-alternative-sources/iucn-2026-1.zip`, 21,140,648 B)
- **TEST 런타임 리플레이**: 입력 행 해시 `ee60f23871259d4cf2b8bb6d4be10475fa45b294f453018271180b1ad2abc982` (11,131 DB 종 행 실측 해시, `/tmp/rg-conservation-live-rows.json`, `/tmp`는 임시 보관 경로)

### 2.2 전체 11,131종 및 808개 NE 종의 실측 집계
- **공식 체크리스트 연동 (`linked_checklist`)**: **7,507종** (학명·명명자·SIS ID·서지 인용 전수 일치 목록 연결; 평가 원문 전체의 독립 검증 아님).
- **미연결군 (Unlinked)**: **3,624종**
  - 명명자 불일치 (`authority_mismatch`): **2,286종** (학명·SIS ID 일치하나 명명자 불일치; 933건 패턴은 성씨 동일성 미검증).
  - 학명 불일치 (`scientific_name_mismatch`): **474종** (SIS ID 일치하나 학명 불일치).
  - 평가 ID / 서지 인용 불일치: **56종** (서지 정규식 매칭 실패 등; 56건 전체가 단순 절단 오류는 아님).
  - AviList 원자료 NE (`needs_review`): **808종** (분류 개념 검토 필요).

**808개 AviList NE 종의 정밀 원장 분해**:
1. **동일 학명 조회 (`exact_name_hits`)**: **478종** (IUCN 2026-1 수락 종 중 속명+종소명 일치).
2. **정합성 유효 후보 (`integrity_valid`)**: **471종** (478종 중 단일 대응 및 전 지구 평가·서지 정합성을 만족한 후보).
3. **엄격 참고평가 수록 (`strict_refs`)**: **360종** (471종 중 보수적 명명자 검증을 통과하여 `references`에 수록된 종; 332 LC, 15 NT, 9 VU, 3 EN, 1 CR).
4. **118개 제외 격차 분석**: 478 - 360 = 118종의 제외 사유는 명명자 불일치 111종 + 정합성 탈락 7종임 (전부 명명자 차이가 아님).
5. **동일 학명 미존재 (`no_exact_name`)**: **330종** (IUCN 2026-1 수락 종에 학명이 없음; 이 수치가 실제 미평가나 종 분할을 증명하지는 않음).

---

## 3. 큰부리까마귀(*Corvus macrorhynchos*) 실측 대조

1. **AviList v2025b 스냅샷**:
   - Taxon ID: `avilist-taxon:v2025b:20296`, 학명: `Corvus macrorhynchos`, 명명자: `Wagler, JG, 1827`
   - 제안: `2025-1070`, 원자료 등급: `NE`, `BirdLife_DataZone_URL`: `None`, Avibase: `avibase-A9146F3B`
   - 결정문: *philippinus*는 미토콘드리아 DNA 분화로 분리, *levaillantii* 및 *culminatus*는 증거 부족으로 분리 보류.
2. **GBIF IUCN 2026-1 스냅샷**:
   - Taxon ID (SIS): `103727590`, 학명: `Corvus macrorhynchos Wagler, 1827`, 명명자: `Wagler, 1827`
   - 등급: `Least Concern (LC)`, 평가 ID: `264280673`, 평가 연도: `2024`
   - 인용: `BirdLife International 2024. Corvus macrorhynchos Wagler, 1827. The IUCN Red List of Threatened Species 2024: https://doi.org/10.2305/IUCN.UK.2024-2.RLTS.T103727590A264280673.en`
   - URL: `https://www.iucnredlist.org/species/103727590/264280673`
3. **대조 결론**:
   - 학명 및 명명자는 `single_author_initials_omitted` 규칙으로 일치함.
   - 그러나 공식 평가의 지리적·분류학적 범위와 AviList v2025b 개념의 일치 여부는 독립 검증되지 않음 (`taxonomy_alignment: "unverified"`).

---

## 4. 참고평가 360종 중 비-LC (CR/EN/VU/NT) 28개 출처 개념 실측

360개 참고평가의 등급은 **IUCN 출처 개념의 평가**이며, AviList 개념의 확인된 위험도가 아니다:
- **CR (위급, 1종)**: *Pyrrhura subandina* (SIS 45422401)
- **EN (위기, 3종)**: *Premnoplex tatei* (SIS 103672434), *Ramphocinclus brachyurus* (SIS 22711137), *Laterallus jamaicensis* (SIS 22692353)
- **VU (취약, 9종)**: *Pionites leucogaster* (SIS 62181308), *Neomorphus geoffroyi* (SIS 62144610), *Calamonastides gracilirostris* (SIS 103779235), *Nesoenas mayeri* (SIS 22690392), *Psophia viridis* (SIS 45470705), *Eudyptes chrysocome* (SIS 22735250), *Puffinus yelkouan* (SIS 22698230), *Crax fasciolata* (SIS 45092100), *Buceros hydrocorax* (SIS 22727019)
- **NT (준위협, 15종)**: *Pteroglossus bitorquatus* (SIS 22728132), *Falco chicquera* (SIS 22727778), *Pyrrhura amazonum* (SIS 45422118), *Eupsittula nana* (SIS 45418540), *Cinclodes antarcticus* (SIS 103670928), *Symposiachrus browni* (SIS 22707326), *Neomixis striatigula* (SIS 103771036), *Iole charlottae* (SIS 22713170), *Dessonornis anomalus* (SIS 103762448), *Treron formosae* (SIS 22727539), *Sturnella magna* (SIS 22735434), *Thalassarche cauta* (SIS 22729604), *Nisaetus nipalensis* (SIS 22696153), *Actenoides monachus* (SIS 22726844), *Todiramphus veneratus* (SIS 22726919)

> [!WARNING]
> 위 28개 종의 존재는 "AviList NE 종은 흔한 종이므로 일괄 LC 처리해도 무방하다"는 가정이 심각한 오류임을 실측으로 증명한다.

---

## 5. 미확인 사실 및 한계 (Unknowns & Scope Boundaries)

1. **개념 일치 미확인 (Concept Alignment Unverified)**:
   - 360개 참고평가는 동일 학명·명명자에 대한 IUCN 출처의 평가일 뿐, AviList v2025b의 분류 개념과 범위가 일치함을 증명하지 않는다.
2. **국내 보전 및 법적 지위 미검증 (National Status Not Verified)**:
   - 국립생물자원관(NIBR) 적색자료집, 환경부 멸종위기 야생생물 등 국내 지위와 라이선스는 이번 고정 검증 파이프라인에서 독립 검증하지 않았으며 미검증(`not verified`)으로 유지한다.
3. **체크리스트 연동 한계 (Not Assessment Full-Text)**:
   - 7,507개 확정 연결은 공개 체크리스트의 키 대조 결과(`linked_checklist`)이며, 평가 원문 전체에 대한 독립 검증이 아니다 (`independently_verified: false`).
4. **임의 상속 및 일괄 LC 적용 불가**:
   - 분할 전 모종 등급의 무단 상속이나 NE 종에 대한 일괄 LC 적용은 28개 멸종위기·준위협 개념을 왜곡하므로 금지된다.

---

## 6. 런타임 계약 및 출처 URL (Runtime Contract & Reference URLs)

### 6.1 런타임 계약 상태
- **API 응답**: 기존 Pica serica 사용자 지정 보정을 제외한 미연결 AviList NE 종은 `category: null`, `category_raw: "NE"`, `assessment_status: "needs_review"`, 라벨 `"평가 연결 확인 필요"`를 반환함.
- **참고 평가 필드**: `reference_checklist`를 통해 `reference_assessment` 객체(등급, 평가연도, URL, 인용, 명명자, `taxonomy_alignment: "unverified"`)가 격리 제공됨.
- **UI 표시**: 주 배지는 미확인 상태를 유지하고, 참고 평가는 "참고 평가: 관심대상 (LC) · 2024 · 현재 분류 범위와 일치 여부 확인 필요"로 별도 명시됨.
- **배포 계획**: TEST 환경에서 기능 검증을 완료하였으며, 이번 작업에서 PROD는 변경하지 않음.

### 6.2 신뢰할 수 있는 직접 출처 URL
- **GBIF 호스팅 IUCN Red List Checklist**: `https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3` (DOI: `10.15468/0qnb58`, 릴리스 `2026-1`)
- **큰부리까마귀 공식 IUCN 개별 평가**: `https://www.iucnredlist.org/species/103727590/264280673` (평가 ID `264280673`, SIS `103727590`)
- **AviList v2025b 글로벌 체크리스트**: `https://explore.avilist.org/data/avilist-2025b.json` (안내 페이지: `https://www.avilist.org/checklist/v2025b/`)

## 영구 보관 및 코디네이터 검토

원본은 Antigravity가 조사하고 코디네이터가 실제 코드·원장과 대조했다. 개정본에 남아 있던 런타임 라벨, 입력 행 파일 경로, 기준선 표현을 위와 같이 바로잡았다. 출처에 없는 분류 범위·국내 지위 단정은 채택하지 않았다.

전 종 원장과 입력 행은 이 저장소의 `docs/verification/assets/2026-10-09-conservation-*.json.gz` 및 재현 노트북에 보존한다. 작업·검증·배포 내역은 [작업기록](../work-log/2026-10-09-all-species-conservation-reconciliation.md)을 따른다.
