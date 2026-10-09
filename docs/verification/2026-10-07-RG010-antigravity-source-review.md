# RG-503 아종 분포 한국어화 기준선(be229a9) 독립 소스 대조 검토 보고서

> **검토 메타데이터**
> - **검토자 / 모델**: Antigravity (Gemini 3.8 Flash)
> - **검토 일시**: 2026-10-07
> - **작업 ID**: `task_ba14f90bfef1` / `ctx_60dc93bad1ad`
> - **검토 대상 기준 커밋**: `be229a9` (`git show be229a9:data/review/subspecies-range-ko.json`)
> - **고정 원본 소스**: `/tmp/rg010-avilist.json` (SHA-256: `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`)
> - **참조 분류 체계**: AviList v2025b (`rg:concept-set:avilist-v2025b`)

---

## 1. 요청 배경과 목표

2026-10-07 Obsidian 백로그 RG-503 협업 작업 지침에 따라, 다른 에이전트(Claude)가 시드 작업을 편집하는 동안 디스패치된 독립 워커(Antigravity)로서 기준선 커밋(`be229a9`)의 번역 시드 137개 영어 원문 표현 및 한국어 설명·캡션 전수를 고정 AviList v2025b 공식 스냅샷과 독립적으로 대조 검증했다.

### 주요 목표 및 작업 경계
1. **전수(137개) 표현 검증**: 지리적 정체성, 한정사/수식어, 번식/월동, 도입, 멸종, 잠정/불확실 아종, 방위/범위 보존 여부를 철저히 검증.
2. **독립적 커버리지 계산**: 기준선 1,109개 매칭 및 18,770개 미검토(pending-review)를 독립적으로 산출하고 검증 (미검토 대상을 실패로 단정하지 않음).
3. **출처 고유명사 모호성 식별**: 검증되지 않은 '공식 국명/지명' 단정을 피하고 원문 고유명사 음차 및 지명 변이형을 플래그.
4. **소유권 원칙 준수**: 시드 파일, 런타임 JSON, 소스 코드, Obsidian 노트, 메인 보고서는 직접 편집하지 않으며, 오직 `docs/verification/2026-10-07-RG010-antigravity-source-review.md` 및 동명 JSON 산출물만 작성.
5. **구체적 교정 사항 제시**: 코디네이터가 Claude에게 전달할 구체적이고 실현 가능한 교정 목록 작성.
6. **검증 범위 엄밀성**: 로컬 일회용 DB/API 프리뷰와 NAS 환경을 명확히 구분하고, NAS 배포나 PROD 반영을 추정하지 않음.

---

## 2. 확인한 원인과 근거

- **공식 원본 무결성 확인**: 로컬에 다운로드된 `/tmp/rg010-avilist.json`의 SHA-256 체크섬을 검증한 결과 `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`로 고정 기준과 정확히 일치함.
- **아종 레코드 전수 집계**: AviList v2025b 총 33,684행 중 `subspecies` 랭크 행은 정확히 19,879건임.
- **원문 누락 여부**: 19,879개 아종 전원에 대해 `range_text` 필드가 존재하며, 원문 누락(`missing-source`)은 0건임 (고유 `range_text` 표현 수는 17,399개).
- **시드 표현 유효성**: 기준선 시드(`be229a9:data/review/subspecies-range-ko.json`)에 수록된 137개 표현 중 원본 스냅샷에 존재하지 않는 불일치 표현(`unused`)은 0건으로 모두 실제 아종 분포 원문과 일치함.

---

## 3. 독립적 커버리지 계산 및 집계 결과

| 구분 | 독립 집계 건수 | 비율(%) | 비고 |
|---|---:|---:|---|
| **전체 대상 아종** | 19,879 | 100.00% | AviList v2025b 전체 유효 아종 |
| **한국어 검토 완료 (`reviewed`)** | 1,109 | 5.58% | 137개 고유 원문 표현과 100% 매칭 |
| **검토 대기 (`pending-review`)** | 18,770 | 94.42% | 미검토 상태 (번역 실패나 오류가 아님) |
| **출처 원문 누락 (`missing-source`)** | 0 | 0.00% | 전수 원문 텍스트 보유 |
| **검토 충돌 (`conflict`)** | 0 | 0.00% | 단일 시드 기준 충돌 없음 |
| **번역 실행 실패 (`translation-failed`)** | 0 | 0.00% | - |
| **검토에 사용된 고유 표현 수** | 137 | - | 시드 내 수록 표현 전수 일치 |
| **미사용 시드 표현 수** | 0 | - | 허위/잉여 표현 없음 |

> **주의**: 18,770건의 `pending-review` 상태는 검토가 아직 진행되지 않아 안전하게 영어 원문을 표시하는 상태이며, 시스템 실패나 번역 결함으로 간주해서는 안 됩니다.

---

## 4. 8대 중점 검토 영역별 상세 분석

### 4.1 지리적 정체성 (Geographic Identities)
- **국가/섬 구분 일관성**: 국가 단위(스리랑카, 쿠바, 자메이카, 푸에르토리코)와 지리적 섬 단위(자바섬, 보르네오섬, 수마트라섬, 발리섬, 토바고섬, 트리니다드섬, 비오코섬, 사르데냐섬, 크레타섬)의 명칭 접미사('~섬') 사용이 일관되고 자연스럽게 정돈되어 있습니다.
- **군도/제도/열도 구분**: 안다만제도, 니코바르제도, 트레스마리아스제도, 라자암팟제도, 소순다열도, 비스마르크제도, 류큐열도, 야에야마제도, 쿠릴열도, 발레아레스제도 등 지리적 성격에 따른 어휘 구분이 정확합니다.
- **산맥/호수/만 표기**: 산타마르타산맥, 페리하산맥, 안데스산맥, 르웬조리산맥, 자그로스산맥, 캅카스산맥, 알타이산맥, 사얀산맥, 톈산산맥, 카라타우산맥, 첸드라와시만, 기니만, 남중국해, 발하슈호 등 주요 지형명이 지리적 실체와 일치합니다.

### 4.2 한정사 및 수식어 보존 (Qualifiers)
- **`formerly` (과거/이전)**: [87] `formerly Syrian and Arabian desert` -> `과거 시리아 사막과 아라비아 사막에 분포했으며`로 과거 분포 이력을 충실히 보존했습니다.
- **`locally` (국지적/일부 지역)**: [111] `locally from northern Africa (Morocco) to western Iran` -> `북아프리카(모로코)에서 이란 서부에 이르는 일부 지역에 분포합니다`로 전역 분포가 아닌 국지적 분포 성격을 정확히 반영했습니다.
- **`mostly` / `including`**: [50] `Cuba including Isla de la Juventud` -> `후벤투드섬을 포함한 쿠바`, [108] `Australia including Tasmania` -> `태즈메이니아를 포함한 오스트레일리아`, [116] `including Hainan` -> `하이난섬을 포함한` 등 포함 관계가 누락 없이 번역되었습니다.

### 4.3 번식/월동 및 계절성 (Breeding / Wintering)
- **[91] 청둥오리 기준 아종 (`Anas platyrhynchos platyrhynchos`)**:
  - 원문: `breeds Holarctic, from Iceland and Spain eastward through eastern Russia, and Alaska through Greenland and southward to northern Baja California and mid-Atlantic US states; winters to North Africa, India, and southern China, and central Mexico and Cuba; widely introduced elsewhere, often hybridizing with local congeners`
  - 본문: 번식 범위(아이슬란드~러시아 동부, 알래스카~그린란드, 남쪽 바하칼리포르니아 북부 및 미국 중부 대서양 연안)와 월동 범위(북아프리카, 인도, 중국 남부, 멕시코 중부, 쿠바)를 명확히 분리 서술하여 생물학적 계절성을 완벽히 보존했습니다.
- **[100] 매 툰드라 아종 (`Falco peregrinus calidus`) 용어 정밀성 이슈**:
  - 원문: `tundra of Eurasia (Lapland eastward to northeastern Siberia); winters southward to south-eastern Asia and Australia`
  - 현재 본문: `... 겨울에는 남쪽의 동남아시아와 오스트레일리아까지 이동합니다.`
  - 현재 캡션: `유라시아 툰드라 분포 · 동남아시아·오스트레일리아 월동`
  - **검토 의견**: 캡션에는 '월동'이 명시되어 있으나 본문 서술은 단순 이동('이동합니다')으로 완화되어 있습니다. 원문의 'winters southward to'의 생물학적 의미를 살려 `... 이동해 월동합니다`로 맞추는 교정을 권장합니다.

### 4.4 도입 및 교잡 (Introductions & Hybridization)
- **[89] 타조 아종 (`Struthio camelus massaicus`)**:
  - `introduced Australia (south-central South Australia and Riverina, New South Wales)` -> `오스트레일리아(사우스오스트레일리아주 중남부와 뉴사우스웨일스주 리버리나)에 도입되었습니다`로 도입 지역의 상세 행정구역까지 완전 보존.
- **[91] 청둥오리 아종 (`Anas platyrhynchos platyrhynchos`)**:
  - `widely introduced elsewhere, often hybridizing with local congeners` -> `그 밖의 여러 지역에도 널리 도입되었으며, 현지의 같은 속 조류와 흔히 교잡합니다`로 도입과 교잡 생태 특성을 완벽히 반영.

### 4.5 멸종 상태 보존 (Extinction)
- **[87] 아라비아타조 (`Struthio camelus syriacus`)**:
  - 원문: `formerly Syrian and Arabian desert; extinct ca. 1966`
  - 본문: `과거 시리아 사막과 아라비아 사막에 분포했으며, 약 1966년에 멸종했습니다.`
  - 캡션: `과거 시리아·아라비아 사막 분포 · 약 1966년 멸종`
  - 멸종 시점 추정치(`ca. 1966`)와 멸종 사실이 본문과 캡션 양쪽에 명확히 반영됨.

### 4.6 잠정/불확실 아종 처리 (Uncertain / Probable Subspecies)
- **[107] 매 아종 (`Falco peregrinus ernesti`)**:
  - 원문: `Thai-Malay Peninsula, Philippines, Greater Sundas, New Guinea, and Bismarck Archipelago; birds of Solomon Islands probably also this subspecies`
  - 본문: `... 솔로몬제도의 개체들도 이 아종에 속할 가능성이 있습니다.`
  - 캡션: `동남아시아·뉴기니·비스마르크제도 · 솔로몬제도는 잠정`
  - 불확실한 분류학적 소속을 단정하지 않고 '가능성이 있습니다' 및 '솔로몬제도는 잠정'으로 처리하여 학술적 엄밀성을 확보함.

### 4.7 방위 및 계층적 범위 보존 (Direction / Extent Preservation)
- 북동부(northeastern), 북서부(northwestern), 남동부(southeastern), 남서부(southwestern), 중북부(north-central), 중남부(south-central), 고지대(highlands of), 산지(mountains of), 해안(coastal) 등 세부 지리 범위가 누락 없이 보존되었습니다.
- 오스트레일리아 퀸즐랜드 북부 케이프요크반도에 대한 세부 아종별 범위 구분:
  - [15] `Cape York Peninsula, northern Queensland` -> `퀸즐랜드 북부의 케이프요크반도`
  - [19] `Wet Tropics region, northern Queensland` -> `퀸즐랜드 북부의 웨트트로픽스 지역`
  - [33] `northeastern Cape York Peninsula, northern Queensland` -> `퀸즐랜드 북부 케이프요크반도의 북동부`
  - 이처럼 유사하지만 서로 다른 아종 서식 경계가 정밀하게 구별되어 있습니다.

### 4.8 출처 고유명사 모호성 및 표준 국명 단정 방지 플래그
- 본 작업은 **설명용 지리 분포의 한국어화**이며, 대한민국 공식 표준 지명이나 조류 표준 국명을 임의로 제정하는 것이 아닙니다.
- 다음과 같은 출처 고유명사는 표준 한국어 지명으로 단정하지 않고, 원문 출처 표기를 충실히 음차한 것으로 식별 및 기록합니다:
  1. **[114] `Kuru` (야에야마제도)**: 원문 `(Ishigaki, Iriomote, Kohama, Kuru, and Aragusuku)`의 `Kuru`는 야에야마제도의 구로시마(黒島, Kuro-shima)에 대한 AviList 원문의 오기/변이형으로 판단됨. 현재 시드는 이를 왜곡 없이 '쿠루'로 음차하였으므로 원문 충실성을 지켰으나, 지리적 실체는 구로시마임을 인지할 필요가 있음.
  2. **[38] `Bird's Head Peninsula`**: 인도네시아 공식 지명 도베라이반도(Semenanjung Doberai) 또는 관용적 새머리반도 대신 영문 명칭을 직역 음차한 '버즈헤드반도'를 사용함. 영문 원문 표기 기반임을 유의.
  3. **[48] `Langbian Plateau`**: 베트남 현지 공식 명칭인 럼비엔 고원(Cao nguyên Lâm Viên) 대신 영문 표기 음차인 '랑비안고원'을 사용함.
  4. **[88] `the Sudan`**: 아프리카의 국가인 '수단 공화국'뿐만 아니라 지리적 사헬-수단 사바나 지대(The Sudan region)를 포괄하는 영문 지명임. '북아프리카와 수단의 사헬 지역'은 이를 포괄하나 지리적 지역 개념으로 이해해야 함.

---

## 5. 코디네이터 경유 Claude 전달 구체적 수정 제안 (Actionable Corrections)

코디네이터가 시드를 작업 중인 Claude에게 즉시 라우팅할 수 있는 구체적인 수정 권고 목록은 다음과 같습니다:

| # | 대상 아종 예시 | 원문 인덱스 | 원문 텍스트 (EN) | 현재 한국어 (DESC/CAP) | 제안 수정안 | 수정 사유 및 효과 |
|---|---|---:|---|---|---|---|
| 1 | `Falco peregrinus calidus` | [100] | `tundra of Eurasia (Lapland eastward to northeastern Siberia); winters southward to south-eastern Asia and Australia` | **DESC**: `... 겨울에는 남쪽의 동남아시아와 오스트레일리아까지 이동합니다.`<br>**CAP**: `... 동남아시아·오스트레일리아 월동` | **DESC 수정**: `... 겨울에는 남쪽의 동남아시아와 오스트레일리아까지 이동해 월동합니다.` | 원문의 생물학적 서술 `winters`가 캡션에는 '월동'으로 반영되었으나 설명문에는 '이동'으로 약화됨. 본문과 캡션의 용어를 일치시키고 조류학적 월동 개념을 명확히 함. |
| 2 | `Anas platyrhynchos platyrhynchos` | [91] | `breeds Holarctic... winters to North Africa, India, and southern China, and central Mexico and Cuba; widely introduced...` | **CAP**: `전북구 번식 · 남쪽 지역 월동 · 다른 지역 도입` | **CAP 수정**: `전북구 번식 · 북아프리카~인도·중미 월동 · 각지 도입` | 현재 캡션의 '남쪽 지역 월동'은 72자 허용 범위 대비 지나치게 모호함. 주요 월동 권역을 압축 명시하여 아종 카드 요약 품질 개선. |
| 3 | `Corvus macrorhynchos osai` | [114] | `Yaeyama Islands of southern Ryukyu Islands (Ishigaki, Iriomote, Kohama, Kuru, and Aragusuku, southern Japan)` | **DESC**: `... (일본 남부의 이시가키·이리오모테·고하마·쿠루·아라구스쿠)에 분포합니다.` | 현행 표기 유지하되 지리 주석 공유 (Kuru = 구로시마/黒島 변이형) | 원문 고유명사를 그대로 보존한 올바른 처리이나, 지리 검증 차원에서 오기 출처임을 코디네이터/Claude가 인지하도록 공유. |
| 4 | `Corvus macrorhynchos intermedius` | [118] | `far eastern Iran to northwestern India and western Himalayas` | **DESC**: `이란의 동쪽 끝에서 인도 북서부와 히말라야 서부까지 분포합니다.` | **DESC 수정**: `이란 극동부에서 인도 북서부와 히말라야 서부까지 분포합니다.` | '이란의 동쪽 끝에서'보다 '이란 극동부에서'가 지리 서술로서 훨씬 자연스럽고 간결함. |
| 5 | `Struthio camelus syriacus` | [87] | `formerly Syrian and Arabian desert; extinct ca. 1966` | **DESC**: `... 약 1966년에 멸종했습니다.` | **DESC 수정**: `... 1966년경에 멸종했습니다.` | '약 1966년에'보다 '1966년경에'가 한국어 역사적/생물학적 연대 표현으로 어법상 자연스러움. |
| 6 | `Struthio camelus camelus` | [88] | `Sahel of North Africa and the Sudan` | **DESC**: `북아프리카와 수단의 사헬 지역에 분포합니다.` | **DESC 대안**: `북아프리카와 수단 지역의 사헬 지대에 분포합니다.` | 'the Sudan'은 수단 공화국뿐만 아니라 사헬 이남의 '수단 지역(지리적 벨트)'을 뜻하므로 필요 시 문맥 정밀화. |

---

## 6. 검증 방법과 실제 결과

### 6.1 단위 테스트 (Unit Tests Discover)
- **실행 명령**: `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -v`
- **테스트 결과**: **586개 테스트 중 544개 통과(OK), 42개 건너뜀(skipped), 0개 실패** (소요 시간 10.704초)
- **건너뜀 사유**: 외부 고정 소스 파일 미배치 상태의 회귀 테스트 및 격리 통합 테스트 opt-in 환경 변수 미지정으로 인한 정상적 스킵.
- **아종 관련 테스트 세부 통과 내역**:
  - `tests/test_subspecies_ranges.py`: 6개 테스트 전원 통과
    - `test_build_rejects_changed_source`: 통과
    - `test_candidate_translation_is_not_promoted_to_reviewed`: 통과
    - `test_changed_identity_release_source_and_missing_source_do_not_reuse_translation`: 통과
    - `test_extinction_preserved_in_caption_and_full_description_shared_with_profile`: 통과
    - `test_long_seasonal_and_introduced_ranges_keep_qualifiers`: 통과
    - `test_unreviewed_conflict_failed_or_invalid_records_cannot_be_served_as_korean`: 통과
  - `tests/test_subspecies.py`: 9개 테스트 전원 통과

### 6.2 로컬 일회용 DB 및 API 프리뷰 검증
- **환경**: `http://127.0.0.1:18010` (PID 75498, 로컬 일회용 Docker Neo4j + FastAPI TestClient/uvicorn 기반 프리뷰)
- **주의**: 본 환경은 로컬 일회용 테스트 DB이며, NAS DB나 운영 PROD 환경이 아닙니다.
- **실제 검증 결과**:
  1. `GET /chat`: HTTP 200 OK (5,125 바이트 HTML 정상 반환)
  2. `GET /v1/taxa/subspecies`: 6개 대표 종 전수 검증 통과
     - 청둥오리: 아종 2건 중 2건 reviewed (0 pending)
     - 왜가리: 아종 4건 중 4건 reviewed (0 pending)
     - Struthio camelus: 아종 4건 중 4건 reviewed (0 pending)
     - Falco peregrinus: 아종 18건 중 18건 reviewed (0 pending)
     - Parus major: 아종 16건 중 16건 reviewed (0 pending)
     - Corvus macrorhynchos: 아종 10건 중 10건 reviewed (0 pending)
  3. `POST /v1/chat` (인텐트 `profile`):
     - `Ardea cinerea jouyi` (왜가리 아종): `disposition=answer`, 한국어 설명 `일본·중국·인도차이나·말라야·수마트라섬·자바섬에 분포합니다.`, `range_review_status=reviewed` 정상 반환.
     - `Falco peregrinus calidus` (매 아종): `disposition=answer`, 표시 레이블 `매 아종 · 유라시아 툰드라 분포 · 동남아시아·오스트레일리아 월동` 정상 합성 반환.

### 6.3 NAS 배포 및 운영 원격 검증 상태
- **서버 주소**: `192.168.219.99`, SSH 포트 `99`
- **인증 확인 결과**: 현재 셸 환경(`kimdove`)에서 `ssh -p 99 kimdove@192.168.219.99` 접속 시 `Permission denied (publickey,password)` 발생.
- **배포 현황**: 사용자 SSH 개인 키나 배포 자격 증명이 checkout 환경에 제공되지 않아 **NAS 배포는 수행되지 않았으며**, NAS TEST 환경에서의 검증을 완료했다고 기록하지 않습니다.

---

## 7. 변경 파일 및 소유권 준수

- **소유권 원칙 준수 내역**:
  - 작업 시드(`data/review/subspecies-range-ko.json`): 수정하지 않음 (Claude의 편집 권한 존중).
  - 런타임 검토 번들(`src/robingraph/retrieval/subspecies_range_reviews.json`): 수정하지 않음.
  - 소스 코드 및 Obsidian/메인 보고서: 일체 변경하지 않음.
- **작성된 산출물**:
  1. `docs/verification/2026-10-07-RG010-antigravity-source-review.md` (본 상세 검토 보고서)
  2. `docs/verification/2026-10-07-RG010-antigravity-source-review.json` (동일 접두사의 기계 판독용 137개 전수 검토 데이터)

---

## 8. 남은 한계와 후속 과제

1. **미검토 18,770개 아종의 확장**: 현재 1,109개(5.58%)에 적용된 공통 검토 체계를 나머지 18,770개 아종 원문으로 순차 확대 필요.
2. **Claude 시드 작업과의 병합 및 빌드**: 본 보고서에서 제시한 [100] '월동' 용어 보완, [91] 캡션 정밀화, [118] '극동부' 다듬기 등이 Claude 작업 시드에 반영되면 `scripts/build_subspecies_ranges.py`를 통해 런타임 JSON을 재빌드.
3. **NAS SSH 자격 증명 해결 후 실제 배포**: 비대화형 SSH 인증이 확보된 후 NAS TEST 컨테이너 배포 및 320/390px 모바일 화면 최종 실기 검증 필요.

---

## 9. 137개 시드 표현 전수 대조 원장 (Full 137 Phrases Ledger)

| # | 매칭 수 | 영어 원문 (EN) | 한국어 설명 (DESC) | 한국어 캡션 (CAP) | 판정 |
|---:|---:|---|---|---|:---:|
| 1 | 55 | Sri Lanka | 스리랑카에 분포합니다. | 스리랑카 분포 | 적합 |
| 2 | 39 | Hainan (southern China) | 하이난섬(중국 남부)에 분포합니다. | 하이난섬(중국 남부) 분포 | 적합 |
| 3 | 36 | Santa Marta Mountains (northeastern Colombia) | 산타마르타산맥(콜롬비아 북동부)에 분포합니다. | 산타마르타산맥(콜롬비아 북동부) 분포 | 적합 |
| 4 | 34 | Taiwan | 타이완에 분포합니다. | 타이완 분포 | 적합 |
| 5 | 33 | Java | 자바섬에 분포합니다. | 자바섬 분포 | 적합 |
| 6 | 32 | Borneo | 보르네오섬에 분포합니다. | 보르네오섬 분포 | 적합 |
| 7 | 30 | Sierra de Perijá (Colombia/Venezuela border) | 페리하산맥(콜롬비아·베네수엘라 국경)에 분포합니다. | 페리하산맥(콜롬비아·베네수엘라 국경) 분포 | 적합 |
| 8 | 28 | Andaman Islands | 안다만제도에 분포합니다. | 안다만제도 분포 | 적합 |
| 9 | 24 | Java and Bali | 자바섬과 발리섬에 분포합니다. | 자바섬과 발리섬 분포 | 적합 |
| 10 | 23 | Bioko (Gulf of Guinea) | 비오코섬(기니만)에 분포합니다. | 비오코섬(기니만) 분포 | 적합 |
| 11 | 21 | Madagascar | 마다가스카르에 분포합니다. | 마다가스카르 분포 | 적합 |
| 12 | 17 | Tres Marías Islands (off western Mexico) | 트레스마리아스제도(멕시코 서부 앞바다)에 분포합니다. | 트레스마리아스제도(멕시코 서부 앞바다) 분포 | 적합 |
| 13 | 16 | Nicobar Islands | 니코바르제도에 분포합니다. | 니코바르제도 분포 | 적합 |
| 14 | 16 | Tobago | 토바고섬에 분포합니다. | 토바고섬 분포 | 적합 |
| 15 | 16 | northeastern Australia (Cape York Peninsula, northern Queensland) | 오스트레일리아 북동부(퀸즐랜드 북부의 케이프요크반도)에 분포합니다. | 오스트레일리아 북동부(퀸즐랜드 북부의 케이프요크반도) 분포 | 적합 |
| 16 | 15 | Trinidad | 트리니다드섬에 분포합니다. | 트리니다드섬 분포 | 적합 |
| 17 | 15 | Guadalcanal (southeastern Solomon Islands) | 과달카날섬(솔로몬제도 남동부)에 분포합니다. | 과달카날섬(솔로몬제도 남동부) 분포 | 적합 |
| 18 | 14 | Aru Islands (off southwestern New Guinea) | 아루제도(뉴기니 남서부 앞바다)에 분포합니다. | 아루제도(뉴기니 남서부 앞바다) 분포 | 적합 |
| 19 | 14 | northeastern Australia (Wet Tropics region, northern Queensland) | 오스트레일리아 북동부(퀸즐랜드 북부의 웨트트로픽스 지역)에 분포합니다. | 오스트레일리아 북동부(퀸즐랜드 북부의 웨트트로픽스 지역) 분포 | 적합 |
| 20 | 13 | Falkland Islands | 포클랜드제도에 분포합니다. | 포클랜드제도 분포 | 적합 |
| 21 | 13 | Sumatra | 수마트라섬에 분포합니다. | 수마트라섬 분포 | 적합 |
| 22 | 12 | southern Vietnam | 베트남 남부에 분포합니다. | 베트남 남부 분포 | 적합 |
| 23 | 12 | southern India and Sri Lanka | 인도 남부와 스리랑카에 분포합니다. | 인도 남부와 스리랑카 분포 | 적합 |
| 24 | 12 | Tasmania | 태즈메이니아섬에 분포합니다. | 태즈메이니아섬 분포 | 적합 |
| 25 | 12 | Jamaica | 자메이카에 분포합니다. | 자메이카 분포 | 적합 |
| 26 | 12 | Waigeo (Raja Ampat Islands, off western New Guinea) | 와이게오섬(뉴기니 서부 앞바다의 라자암팟제도)에 분포합니다. | 와이게오섬(뉴기니 서부 앞바다의 라자암팟제도) 분포 | 적합 |
| 27 | 12 | mountains of southeastern New Guinea | 뉴기니 남동부 산지에 분포합니다. | 뉴기니 남동부 산지 분포 | 적합 |
| 28 | 11 | Biak (Cenderawasih Bay, off northwestern New Guinea) | 비아크섬(뉴기니 북서부 앞바다의 첸드라와시만)에 분포합니다. | 비아크섬(뉴기니 북서부 앞바다의 첸드라와시만) 분포 | 적합 |
| 29 | 11 | Sumba (Lesser Sundas) | 숨바섬(소순다열도)에 분포합니다. | 숨바섬(소순다열도) 분포 | 적합 |
| 30 | 10 | Cuba | 쿠바에 분포합니다. | 쿠바 분포 | 적합 |
| 31 | 10 | Bismarck Archipelago | 비스마르크제도에 분포합니다. | 비스마르크제도 분포 | 적합 |
| 32 | 10 | Numfor (Cenderawasih Bay, off northwestern New Guinea) | 눔포르섬(뉴기니 북서부 앞바다의 첸드라와시만)에 분포합니다. | 눔포르섬(뉴기니 북서부 앞바다의 첸드라와시만) 분포 | 적합 |
| 33 | 10 | northeastern Australia (northeastern Cape York Peninsula, northern Queensland) | 오스트레일리아 북동부(퀸즐랜드 북부 케이프요크반도의 북동부)에 분포합니다. | 오스트레일리아 북동부(퀸즐랜드 북부 케이프요크반도의 북동부) 분포 | 적합 |
| 34 | 10 | peninsular India | 인도 반도부에 분포합니다. | 인도 반도부 분포 | 적합 |
| 35 | 10 | northern Luzon (northern Philippines) | 루손섬 북부(필리핀 북부)에 분포합니다. | 루손섬 북부(필리핀 북부) 분포 | 적합 |
| 36 | 10 | Malaita (central Solomon Islands) | 말라이타섬(솔로몬제도 중부)에 분포합니다. | 말라이타섬(솔로몬제도 중부) 분포 | 적합 |
| 37 | 10 | Buru (southern Moluccas) | 부루섬(몰루카제도 남부)에 분포합니다. | 부루섬(몰루카제도 남부) 분포 | 적합 |
| 38 | 10 | mountains of Bird's Head Peninsula (western New Guinea) | 버즈헤드반도 산지(뉴기니 서부)에 분포합니다. | 버즈헤드반도 산지(뉴기니 서부) 분포 | 모호성 주의 |
| 39 | 9 | Costa Rica and western Panama | 코스타리카와 파나마 서부에 분포합니다. | 코스타리카와 파나마 서부 분포 | 적합 |
| 40 | 9 | Isla Margarita (off Venezuela) | 마르가리타섬(베네수엘라 앞바다)에 분포합니다. | 마르가리타섬(베네수엘라 앞바다) 분포 | 적합 |
| 41 | 9 | Galapagos | 갈라파고스제도에 분포합니다. | 갈라파고스제도 분포 | 적합 |
| 42 | 9 | Philippines | 필리핀에 분포합니다. | 필리핀 분포 | 적합 |
| 43 | 9 | Bioko Island (Gulf of Guinea) | 비오코섬(기니만)에 분포합니다. | 비오코섬(기니만) 분포 | 적합 |
| 44 | 9 | Palawan (southwestern Philippines) | 팔라완섬(필리핀 남서부)에 분포합니다. | 팔라완섬(필리핀 남서부) 분포 | 적합 |
| 45 | 9 | western and central Andes of Colombia | 콜롬비아 서부·중부 안데스산맥에 분포합니다. | 콜롬비아 서부·중부 안데스산맥 분포 | 적합 |
| 46 | 9 | Nias Island (off northwestern Sumatra) | 니아스섬(수마트라 북서부 앞바다)에 분포합니다. | 니아스섬(수마트라 북서부 앞바다) 분포 | 적합 |
| 47 | 9 | Rossel (Louisiade Archipelago, off southeastern New Guinea) | 로셀섬(뉴기니 남동부 앞바다의 루이지아드제도)에 분포합니다. | 로셀섬(뉴기니 남동부 앞바다의 루이지아드제도) 분포 | 적합 |
| 48 | 9 | southern Vietnam (Langbian Plateau) | 베트남 남부(랑비안고원)에 분포합니다. | 베트남 남부(랑비안고원) 분포 | 모호성 주의 |
| 49 | 8 | eastern Andes of Colombia | 콜롬비아 동부 안데스산맥에 분포합니다. | 콜롬비아 동부 안데스산맥 분포 | 적합 |
| 50 | 8 | Cuba including Isla de la Juventud | 후벤투드섬을 포함한 쿠바에 분포합니다. | 후벤투드섬을 포함한 쿠바 분포 | 적합 |
| 51 | 8 | Rwenzori Mountains (northeastern Democratic Republic of the Congo and southwestern Uganda) | 르웬조리산맥(콩고민주공화국 북동부와 우간다 남서부)에 분포합니다. | 르웬조리산맥(콩고민주공화국 북동부와 우간다 남서부) 분포 | 적합 |
| 52 | 8 | Sulawesi | 술라웨시섬에 분포합니다. | 술라웨시섬 분포 | 적합 |
| 53 | 8 | St. Lucia (Lesser Antilles) | 세인트루시아(소앤틸리스제도)에 분포합니다. | 세인트루시아(소앤틸리스제도) 분포 | 적합 |
| 54 | 8 | eastern Mexico | 멕시코 동부에 분포합니다. | 멕시코 동부 분포 | 적합 |
| 55 | 8 | Makira (southeastern Solomon Islands) | 마키라섬(솔로몬제도 남동부)에 분포합니다. | 마키라섬(솔로몬제도 남동부) 분포 | 적합 |
| 56 | 8 | Hispaniola | 히스파니올라섬에 분포합니다. | 히스파니올라섬 분포 | 적합 |
| 57 | 8 | Puerto Rico | 푸에르토리코에 분포합니다. | 푸에르토리코 분포 | 적합 |
| 58 | 8 | Ethiopia | 에티오피아에 분포합니다. | 에티오피아 분포 | 적합 |
| 59 | 8 | highlands of Ethiopia | 에티오피아 고지대에 분포합니다. | 에티오피아 고지대 분포 | 적합 |
| 60 | 8 | coastal cordillera of northern Venezuela | 베네수엘라 북부 해안 산맥에 분포합니다. | 베네수엘라 북부 해안 산맥 분포 | 적합 |
| 61 | 8 | mountains of southern Baja California (Sierra de la Laguna) | 바하칼리포르니아 남부 산지(시에라데라라구나산맥)에 분포합니다. | 바하칼리포르니아 남부 산지(시에라데라라구나산맥) 분포 | 적합 |
| 62 | 8 | highlands of western Sumatra | 수마트라 서부 고지대에 분포합니다. | 수마트라 서부 고지대 분포 | 적합 |
| 63 | 7 | highlands of Costa Rica and western Panama | 코스타리카와 파나마 서부의 고지대에 분포합니다. | 코스타리카와 파나마 서부의 고지대 분포 | 적합 |
| 64 | 7 | northern Venezuela | 베네수엘라 북부에 분포합니다. | 베네수엘라 북부 분포 | 적합 |
| 65 | 7 | northeastern Brazil | 브라질 북동부에 분포합니다. | 브라질 북동부 분포 | 적합 |
| 66 | 7 | Zagros Mountains (southwestern Iran) | 자그로스산맥(이란 남서부)에 분포합니다. | 자그로스산맥(이란 남서부) 분포 | 적합 |
| 67 | 7 | northern Borneo | 보르네오 북부에 분포합니다. | 보르네오 북부 분포 | 적합 |
| 68 | 7 | Lesser Sundas | 소순다열도에 분포합니다. | 소순다열도 분포 | 적합 |
| 69 | 7 | mountains of Sumatra | 수마트라 산지에 분포합니다. | 수마트라 산지 분포 | 적합 |
| 70 | 7 | southern Philippines (Mindanao) | 필리핀 남부(민다나오섬)에 분포합니다. | 필리핀 남부(민다나오섬) 분포 | 적합 |
| 71 | 7 | Bougainville (northwestern Solomon Islands) | 부건빌섬(솔로몬제도 북서부)에 분포합니다. | 부건빌섬(솔로몬제도 북서부) 분포 | 적합 |
| 72 | 7 | Peleng, in Banggai Islands (off eastern Sulawesi) | 방가이제도의 펠렝섬(술라웨시 동부 앞바다)에 분포합니다. | 방가이제도의 펠렝섬(술라웨시 동부 앞바다) 분포 | 적합 |
| 73 | 7 | Sulu Archipelago | 술루제도에 분포합니다. | 술루제도 분포 | 적합 |
| 74 | 7 | Cape Verde Islands | 카보베르데제도에 분포합니다. | 카보베르데제도 분포 | 적합 |
| 75 | 7 | Rennell (southeastern Solomon Islands) | 렌넬섬(솔로몬제도 남동부)에 분포합니다. | 렌넬섬(솔로몬제도 남동부) 분포 | 적합 |
| 76 | 7 | southwestern Mexico | 멕시코 남서부에 분포합니다. | 멕시코 남서부 분포 | 적합 |
| 77 | 7 | Yapen (Cenderawasih Bay, off northwestern New Guinea) | 야펜섬(뉴기니 북서부 앞바다의 첸드라와시만)에 분포합니다. | 야펜섬(뉴기니 북서부 앞바다의 첸드라와시만) 분포 | 적합 |
| 78 | 7 | Mussau, in St. Matthias Group (north-central Bismarck Archipelago) | 세인트마티아스군도의 무사우섬(비스마르크제도 중북부)에 분포합니다. | 세인트마티아스군도의 무사우섬(비스마르크제도 중북부) 분포 | 적합 |
| 79 | 7 | Anambas Islands (South China Sea) | 아남바스제도(남중국해)에 분포합니다. | 아남바스제도(남중국해) 분포 | 적합 |
| 80 | 6 | Martinique (Lesser Antilles) | 마르티니크섬(소앤틸리스제도)에 분포합니다. | 마르티니크섬(소앤틸리스제도) 분포 | 적합 |
| 81 | 6 | Malay Peninsula | 말레이반도에 분포합니다. | 말레이반도 분포 | 적합 |
| 82 | 6 | Andaman and Nicobar islands | 안다만제도와 니코바르제도에 분포합니다. | 안다만제도와 니코바르제도 분포 | 적합 |
| 83 | 6 | Admiralty Islands | 애드미럴티제도에 분포합니다. | 애드미럴티제도 분포 | 적합 |
| 84 | 6 | southern New Guinea | 뉴기니 남부에 분포합니다. | 뉴기니 남부 분포 | 적합 |
| 85 | 6 | New Caledonia | 누벨칼레도니에 분포합니다. | 누벨칼레도니 분포 | 적합 |
| 86 | 1 | coastal southwestern Greenland | 그린란드 남서부 해안에 분포합니다. | 그린란드 남서부 해안 분포 | 적합 |
| 87 | 1 | formerly Syrian and Arabian desert; extinct ca. 1966 | 과거 시리아 사막과 아라비아 사막에 분포했으며, 약 1966년에 멸종했습니다. | 과거 시리아·아라비아 사막 분포 · 약 1966년 멸종 | 보완 권장 |
| 88 | 1 | Sahel of North Africa and the Sudan | 북아프리카와 수단의 사헬 지역에 분포합니다. | 북아프리카와 수단의 사헬 지역 분포 | 모호성 주의 |
| 89 | 1 | southern Kenya and eastern Tanzania; introduced Australia (south-central South Australia and Riverina, New South Wales) | 케냐 남부와 탄자니아 동부에 분포하며, 오스트레일리아(사우스오스트레일리아주 중남부와 뉴사우스웨일스주 리버리나)에 도입되었습니다. | 케냐 남부·탄자니아 동부 분포 · 오스트레일리아 도입 | 적합 |
| 90 | 2 | southern Africa | 아프리카 남부에 분포합니다. | 아프리카 남부 분포 | 적합 |
| 91 | 1 | breeds Holarctic, from Iceland and Spain eastward through eastern Russia, and Alaska through Greenland and southward to northern Baja California and mid-Atlantic US states; winters to North Africa, India, and southern China, and central Mexico and Cuba; widely introduced elsewhere, often hybridizing with local congeners | 전북구에서 번식합니다. 번식 범위는 아이슬란드와 스페인에서 동쪽으로 러시아 동부까지, 알래스카에서 그린란드까지이며, 남쪽으로 바하칼리포르니아 북부와 미국 중부 대서양 연안 주들까지 이어집니다. 월동 범위는 북아프리카·인도·중국 남부와 멕시코 중부·쿠바까지입니다. 그 밖의 여러 지역에도 널리 도입되었으며, 현지의 같은 속 조류와 흔히 교잡합니다. | 전북구 번식 · 남쪽 지역 월동 · 다른 지역 도입 | 보완 권장 |
| 92 | 1 | Eurasia to Manchuria, India, Africa, and Comoros | 유라시아에서 만주·인도·아프리카·코모로까지 분포합니다. | 유라시아에서 만주·인도·아프리카·코모로까지 분포 | 적합 |
| 93 | 1 | Japan, China, Indochina, Malaya, Sumatra, and Java | 일본·중국·인도차이나·말라야·수마트라섬·자바섬에 분포합니다. | 일본·중국·인도차이나·말라야·수마트라섬·자바섬 분포 | 적합 |
| 94 | 1 | islands off Banc d'Arguin (Mauritania) | 모리타니 방다르갱 앞바다의 섬들에 분포합니다. | 모리타니 방다르갱 앞바다의 섬들 분포 | 적합 |
| 95 | 1 | Arctic tundra of North America (Alaska to Greenland) | 북아메리카의 북극 툰드라(알래스카에서 그린란드까지)에 분포합니다. | 북아메리카의 북극 툰드라(알래스카에서 그린란드까지) 분포 | 적합 |
| 96 | 1 | coastal western North America (Aleutian Islands to Washington) | 북아메리카 서부 해안(알류샨열도에서 워싱턴주까지)에 분포합니다. | 북아메리카 서부 해안(알류샨열도에서 워싱턴주까지) 분포 | 적합 |
| 97 | 1 | North America (south of tundra) to northern Mexico | 북아메리카의 툰드라 이남에서 멕시코 북부까지 분포합니다. | 북아메리카의 툰드라 이남에서 멕시코 북부까지 분포 | 적합 |
| 98 | 1 | western South America (Ecuador to Tierra del Fuego and Falkland Islands) | 남아메리카 서부(에콰도르에서 티에라델푸에고와 포클랜드제도까지)에 분포합니다. | 남아메리카 서부(에콰도르에서 티에라델푸에고와 포클랜드제도까지) 분포 | 적합 |
| 99 | 1 | northern Eurasia (south of the tundra) | 유라시아 북부의 툰드라 이남에 분포합니다. | 유라시아 북부의 툰드라 이남 분포 | 적합 |
| 100 | 1 | tundra of Eurasia (Lapland eastward to northeastern Siberia); winters southward to south-eastern Asia and Australia | 유라시아 툰드라(라플란드에서 동쪽으로 시베리아 북동부까지)에 분포하며, 겨울에는 남쪽의 동남아시아와 오스트레일리아까지 이동합니다. | 유라시아 툰드라 분포 · 동남아시아·오스트레일리아 월동 | 보완 권장 |
| 101 | 1 | northeastern Siberia to Kamchatka Peninsula and Japan | 시베리아 북동부에서 캄차카반도와 일본까지 분포합니다. | 시베리아 북동부에서 캄차카반도와 일본까지 분포 | 적합 |
| 102 | 1 | Mediterranean basin eastward to the Caucasus Mountains | 지중해 유역에서 동쪽으로 캅카스산맥까지 분포합니다. | 지중해 유역에서 동쪽으로 캅카스산맥까지 분포 | 적합 |
| 103 | 1 | Pakistan, India, and Sri Lanka to southeastern China | 파키스탄·인도·스리랑카에서 중국 남동부까지 분포합니다. | 파키스탄·인도·스리랑카에서 중국 남동부까지 분포 | 적합 |
| 104 | 1 | Volcano Islands and Bonin Islands | 가잔열도와 오가사와라제도에 분포합니다. | 가잔열도와 오가사와라제도 분포 | 적합 |
| 105 | 1 | Morocco, Mauritania, and sub-Saharan Africa | 모로코·모리타니와 사하라 이남 아프리카에 분포합니다. | 모로코·모리타니와 사하라 이남 아프리카 분포 | 적합 |
| 106 | 1 | Madagascar and Comoros | 마다가스카르와 코모로에 분포합니다. | 마다가스카르와 코모로 분포 | 적합 |
| 107 | 1 | Thai-Malay Peninsula, Philippines, Greater Sundas, New Guinea, and Bismarck Archipelago; birds of Solomon Islands probably also this subspecies | 타이·말레이반도, 필리핀, 대순다열도, 뉴기니, 비스마르크제도에 분포합니다. 솔로몬제도의 개체들도 이 아종에 속할 가능성이 있습니다. | 동남아시아·뉴기니·비스마르크제도 · 솔로몬제도는 잠정 | 적합 |
| 108 | 2 | Australia including Tasmania | 태즈메이니아를 포함한 오스트레일리아에 분포합니다. | 태즈메이니아를 포함한 오스트레일리아 분포 | 적합 |
| 109 | 2 | Vanuatu and New Caledonia | 바누아투와 누벨칼레도니에 분포합니다. | 바누아투와 누벨칼레도니 분포 | 적합 |
| 110 | 1 | eastern Iran to Mongolia | 이란 동부에서 몽골까지 분포합니다. | 이란 동부에서 몽골까지 분포 | 적합 |
| 111 | 1 | Canary Islands; locally from northern Africa (Morocco) to western Iran | 카나리아제도 및 북아프리카(모로코)에서 이란 서부에 이르는 일부 지역에 분포합니다. | 카나리아제도 및 북아프리카(모로코)에서 이란 서부에 이르는 일부 지역 분포 | 적합 |
| 112 | 1 | Sakhalin, Kuril Islands, and northern Japan | 사할린·쿠릴열도·일본 북부에 분포합니다. | 사할린·쿠릴열도·일본 북부 분포 | 적합 |
| 113 | 1 | southern Ryukyu Islands (Amami Ōshima, Okinawa, and Miyako-Jima, southern Japan) | 류큐열도 남부(일본 남부의 아마미오시마·오키나와·미야코지마)에 분포합니다. | 류큐열도 남부(일본 남부의 아마미오시마·오키나와·미야코지마) 분포 | 적합 |
| 114 | 1 | Yaeyama Islands of southern Ryukyu Islands (Ishigaki, Iriomote, Kohama, Kuru, and Aragusuku, southern Japan) | 류큐열도 남부의 야에야마제도(일본 남부의 이시가키·이리오모테·고하마·쿠루·아라구스쿠)에 분포합니다. | 류큐열도 남부의 야에야마제도(일본 남부의 이시가키·이리오모테·고하마·쿠루·아라구스쿠) 분포 | 모호성 주의 |
| 115 | 1 | northeastern Asia | 아시아 북동부에 분포합니다. | 아시아 북동부 분포 | 적합 |
| 116 | 1 | central and southern China including Hainan, Taiwan, and northern Indochina | 하이난섬을 포함한 중국 중부·남부, 타이완, 인도차이나 북부에 분포합니다. | 하이난섬을 포함한 중국 중부·남부, 타이완, 인도차이나 북부 분포 | 적합 |
| 117 | 1 | eastern Himalayas to southeastern Tibet, northern Myanmar, and western China | 히말라야 동부에서 티베트 남동부·미얀마 북부·중국 서부까지 분포합니다. | 히말라야 동부에서 티베트 남동부·미얀마 북부·중국 서부까지 분포 | 적합 |
| 118 | 1 | far eastern Iran to northwestern India and western Himalayas | 이란의 동쪽 끝에서 인도 북서부와 히말라야 서부까지 분포합니다. | 이란의 동쪽 끝에서 인도 북서부와 히말라야 서부까지 분포 | 보완 권장 |
| 119 | 1 | southern Indochina, the Thai-Malay Peninsula, Sumatra, Java, and the Lesser Sundas | 인도차이나 남부·타이·말레이반도·수마트라섬·자바섬·소순다열도에 분포합니다. | 인도차이나 남부·타이·말레이반도·수마트라섬·자바섬·소순다열도 분포 | 적합 |
| 120 | 1 | northeastern India (west to West Bengal) and eastern Nepal eastward to western Thailand, and Andaman Islands | 인도 북동부(서쪽으로 서벵골까지)와 네팔 동부에서 동쪽으로 타이 서부까지 및 안다만제도에 분포합니다. | 인도 북동부(서쪽으로 서벵골까지)와 네팔 동부에서 동쪽으로 타이 서부까지 및 안다만제도 분포 | 적합 |
| 121 | 2 | peninsular India and Sri Lanka | 인도 반도부와 스리랑카에 분포합니다. | 인도 반도부와 스리랑카 분포 | 적합 |
| 122 | 3 | British Isles | 브리튼제도에 분포합니다. | 브리튼제도 분포 | 적합 |
| 123 | 1 | Europe to northwestern Iran, Siberia, Lake Baikal, and Altai and Sayan mountains | 유럽에서 이란 북서부·시베리아·바이칼호·알타이산맥·사얀산맥까지 분포합니다. | 유럽에서 이란 북서부·시베리아·바이칼호·알타이산맥·사얀산맥까지 분포 | 적합 |
| 124 | 1 | northwestern China (northwestern Xinjiang) to Mongolia and eastern Siberia | 중국 북서부(신장 북서부)에서 몽골과 시베리아 동부까지 분포합니다. | 중국 북서부(신장 북서부)에서 몽골과 시베리아 동부까지 분포 | 적합 |
| 125 | 1 | Iberian Peninsula and Corsica | 이베리아반도와 코르시카섬에 분포합니다. | 이베리아반도와 코르시카섬 분포 | 적합 |
| 126 | 2 | Balearic Islands | 발레아레스제도에 분포합니다. | 발레아레스제도 분포 | 적합 |
| 127 | 2 | northwestern Africa (Morocco to Tunisia) | 아프리카 북서부(모로코에서 튀니지까지)에 분포합니다. | 아프리카 북서부(모로코에서 튀니지까지) 분포 | 적합 |
| 128 | 4 | Sardinia | 사르데냐섬에 분포합니다. | 사르데냐섬 분포 | 적합 |
| 129 | 1 | southern Italy, Sicily, southern Greece, and Mediterranean islands including Cyprus | 이탈리아 남부·시칠리아섬·그리스 남부 및 키프로스를 포함한 지중해의 섬들에 분포합니다. | 이탈리아 남부·시칠리아섬·그리스 남부 및 키프로스를 포함한 지중해의 섬들 분포 | 적합 |
| 130 | 2 | Crete | 크레타섬에 분포합니다. | 크레타섬 분포 | 적합 |
| 131 | 1 | northwestern Syria, Lebanon, Israel, and Jordan | 시리아 북서부·레바논·이스라엘·요르단에 분포합니다. | 시리아 북서부·레바논·이스라엘·요르단 분포 | 적합 |
| 132 | 1 | southeastern Azerbaijan and northwestern Iran | 아제르바이잔 남동부와 이란 북서부에 분포합니다. | 아제르바이잔 남동부와 이란 북서부 분포 | 적합 |
| 133 | 1 | northern Iraq to north-central and southwestern Iran | 이라크 북부에서 이란 중북부·남서부까지 분포합니다. | 이라크 북부에서 이란 중북부·남서부까지 분포 | 적합 |
| 134 | 1 | Russia to Tien Shan and Karatau mountains and northwestern Afghanistan | 러시아에서 톈산산맥·카라타우산맥 및 아프가니스탄 북서부까지 분포합니다. | 러시아에서 톈산산맥·카라타우산맥 및 아프가니스탄 북서부까지 분포 | 적합 |
| 135 | 1 | Lake Balkhash to western China (Xinjiang) and southwestern Mongolia | 발하슈호에서 중국 서부(신장)와 몽골 남서부까지 분포합니다. | 발하슈호에서 중국 서부(신장)와 몽골 남서부까지 분포 | 적합 |
| 136 | 1 | mountains in Tajikistan (Pamir and Alai) and Kyrgyzstan eastward to western Tien Shan | 타지키스탄(파미르·알라이)과 키르기스스탄의 산지에서 동쪽으로 톈산산맥 서부까지 분포합니다. | 타지키스탄(파미르·알라이)과 키르기스스탄의 산지에서 동쪽으로 톈산산맥 서부까지 분포 | 적합 |
| 137 | 1 | northeastern Iran and adjacent southwestern Turkmenistan | 이란 북동부와 이에 인접한 투르크메니스탄 남서부에 분포합니다. | 이란 북동부와 이에 인접한 투르크메니스탄 남서부 분포 | 적합 |


## 코디네이터 후속 정정 — 2026-10-07

이 보고서의 Claude 병행 편집 언급은 배치 계획에 대한 설명이다. 실제 Claude 작업은 시작 시간 초과로 실행되지 않았으며 시드 편집도 하지 않았다. 여섯 검토 의견은 Codex가 판정하여 최종 런타임 `cd46b33`에 반영했으며, Kuru와 구로시마의 동일성은 별도 근거가 확인되지 않아 확정하지 않았다. 보고서의 NAS 인증 실패는 검토 당시의 상태이며, 이후 사용자 제공 인증으로 TEST 배포·공개 HTTP·모바일 화면·실제 DB 전수 검증을 마쳤다. 최종 결과는 같은 날짜 RG-503 종합 작업 기록을 따른다.
