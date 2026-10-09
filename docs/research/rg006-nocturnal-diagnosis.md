# RG-502: 해오라기 야행성 표기 및 주야 활동성(Diel Activity) 진단 보고서

> **문서 ID**: RG-502-DIAGNOSIS  
> **기준일**: 2026-10-03  
> **상태**: Verified Research Diagnosis (근거 검증 완료)  
> **대상 종**: 해오라기 (*Nycticorax nycticorax*, Black-crowned Night Heron)  
> **식별자 구분**: AviList Taxon ID `avilist-taxon:v2025b:5341` (source_taxon_id `5341`), EltonTraits SpecID `5182`  
> **소유 파일**: `docs/research/rg006-nocturnal-diagnosis.md` (단독 소유, 소스 코드/UI/테스트/배포는 Root 전담)  

---

## 1. 진단 요약 및 재현 (Executive Summary & Live Reproduction)

### 1.1 현상 요약
RobinGraph 종 프로필 조회 시 해오라기(*Nycticorax nycticorax*)에 대해 `야행성: 아니요` (`value: false`, `display: "아니요"`)로 표출된다. 그러나 검증된 조류 생태 문헌(Cornell Lab of Ornithology)에 따르면 해오라기는 주로 저녁부터 이른 아침 사이에 먹이를 찾는 활동 양상을 보인다.

### 1.2 실시간 재현 (Live NAS TEST Environment Reproducer)
NAS TEST 환경(`robingraph-api-test`)의 프로필 엔드포인트를 호출하여 형질 응답을 실시간 검증하였다.

```bash
# 실시간 재현 커맨드 (robingraph-api-test 내부 호출)
curl -s 'http://127.0.0.1:8000/v1/taxa/profile?name=Nycticorax%20nycticorax' | jq '.traits[] | select(.name=="nocturnal")'
```

**실제 반환된 JSON 결과:**
```json
{
  "name": "nocturnal",
  "label": "야행성",
  "value": false,
  "display": "아니요",
  "unit": null,
  "inferred": false,
  "summary_statistic": null,
  "source_url": "https://ndownloader.figshare.com/files/5631081#SpecID=5182",
  "citation": "Wilman et al. (2014), EltonTraits 1.0",
  "dataset_id": "reference-bundle:avilist-v2025b:eltontraits-v1",
  "release": "figshare-article-3559887-v1:file-5631081",
  "license_name": "CC0 1.0",
  "source_name": "AviList and EltonTraits approved reference bundle"
}
```

### 1.3 근본 원인
1. **원천 데이터셋의 단순 이진 분류**: EltonTraits 1.0(`BirdFuncDat.txt`)은 주야 활동성에 대해 오직 단일 이진 변수 `Nocturnal` (0: no, 1: yes)만 제공하며, 해오라기 레코드(SpecID 5182)에 실제 `0` 값이 기재되어 있다. EltonTraits 저자들이 해오라기에 0을 부여한 구체적인 코딩 판단 기준이나 개별 사유는 원데이터셋에 주석이 제공되지 않아 불명(Unknown)이다.
2. **상세 종별 문헌과의 불일치**: Cornell Lab of Ornithology의 Life History 문헌에 따르면 해오라기는 주로 저녁부터 이른 아침에 취식하며 번식기에는 낮에도 활동하는 복합적 주기를 보인다.
3. **표현 계층에서의 수식 누락**: RobinGraph 백엔드가 원데이터셋의 이진 분류 `0`(주요 야간 취식: 아님)을 맥락 설명 없이 `display: '아니요'`로 직접 변환함으로써, 마치 밤에 전혀 활동하지 않는다는 단언적 부정으로 사용자에게 전달되었다.

---

## 2. 데이터 파이프라인 및 코드 경로 추적 (Code Trace & Data Lineage)

### 2.1 원천 데이터셋 (EltonTraits 1.0)
* **파일**: `BirdFuncDat.txt` (Figshare file ID `5631081`, Ecological Archives E095-178-D1, CC0).
* **레코드 식별자**: `SpecID = 5182`, 학명 `Nycticorax nycticorax`. (참고: `5182`는 EltonTraits의 내부 식별자이며 AviList의 Taxon ID `5341`과 구분된다.)
* **기재 값**: `Nocturnal = 0` (결측치 null이 아닌 실제 non-null 정수 값).

### 2.2 n8n 인제스트 파이프라인 (`scripts/generate_n8n_reference_ingest.py`)
`scripts/generate_n8n_reference_ingest.py`의 실제 구현 로직:

1. **파싱 단계 (라인 356~357)**:
   ```javascript
   const nocturnal = optionalNumber(raw.Nocturnal, 'nocturnal', reasons);
   if (nocturnal != null && nocturnal !== 0 && nocturnal !== 1) reasons.push('invalid_nocturnal');
   ```
   `raw.Nocturnal`의 문자열 `'0'`은 `optionalNumber` 함수에 의해 정수 `0`으로 파싱된다.

2. **클레임 생성 단계 (라인 440~457, 라인 481~483)**:
   ```javascript
   const addClaim = (profile, taxon, traitName, values) => claims.push({
     id: `trait-claim:eltontraits-v1:${profile.source_taxon_id}:${traitName}`,
     trait_name: traitName,
     taxon_id: taxon.id,
     source_taxon_id: profile.source_taxon_id,
     source_scientific_name: profile.scientific_name,
     source_record_id: `eltontraits-record:v1:${profile.source_taxon_id}`,
     evidence_id: `eltontraits-evidence:v1:${profile.source_taxon_id}`,
     source_uri: `${config.trait_url}#SpecID=${encodeURIComponent(profile.source_taxon_id)}`,
     ...
     ...values
   });

   if (profile.nocturnal != null) addClaim(profile, taxon, 'nocturnal', {
     value_boolean: profile.nocturnal === 1
   });
   ```
   * `profile.nocturnal`이 `0`이므로 `null`이 아니어서 `addClaim`이 호출된다.
   * `profile.nocturnal === 1` 평가 결과는 `false`가 된다.
   * 생성된 클레임의 식별자 및 속성:
     - `id`: `trait-claim:eltontraits-v1:5182:nocturnal`
     - `trait_name`: `'nocturnal'`
     - `value_boolean`: `false`
     - `taxon_id`: `'avilist-taxon:v2025b:5341'`
     - `source_record_id`: `'eltontraits-record:v1:5182'`

### 2.3 프로필 렌더링 파이프라인 (`src/robingraph/retrieval/species_profile.py`)
`src/robingraph/retrieval/species_profile.py`의 수정 전 `read_traits` 표시 로직:
```python
elif isinstance(value, bool):
    display = '예' if value else '아니요'
```
* 불리언 값에 대해 `True`는 `'예'`, `False`는 `'아니요'`로 단순 변환된다.

### 2.4 AVONET 데이터셋 확인
* AVONET(Tobias et al., 2022; Figshare file ID `34480856`, `scripts/generate_n8n_avonet_ingest.py`)은 형태 계측치(부리 4종, 부척, 날개, 꼬리, 체중)와 환경/영양 지위(Habitat, Trophic Level, Trophic Niche, Primary Lifestyle)만 포함한다.
* AVONET에는 주야 활동성 관련 필드가 존재하지 않으며, RobinGraph의 `nocturnal` 형질은 EltonTraits 1.0에서만 공급된다.

---

## 3. 원천 정의와 종별 생태 사실의 간극 (Source Definition vs Species Facts)

### 3.1 EltonTraits 1.0 코드북 정의 (독립 검증)
* **검증 URL**: `https://esapubs.org/archive/ecol/E095/178/metadata.php` (Ecological Archives E095-178-D1, Table 1)
* **정의 내용 요약**:
  - 변수명: `Nocturnal`
  - 설명: `"Main foraging activity at night. Source for all: Handbook of the Birds of the World"`
  - 형태: 이진 변수 (`Binary: 0: no; 1: yes`)
* **특징**:
  - 포유류 데이터(`MamFuncDat.txt`, Table 2)에는 `Activity-Nocturnal`, `Activity-Crepuscular`, `Activity-Diurnal` 3개 이진 변수가 분리되어 있으나, 조류 데이터(`BirdFuncDat.txt`)에는 오직 `Nocturnal` 1개의 이진 변수만 존재한다.
  - 이 변수는 "주된 취식 활동이 밤에 일어나는지(0: no, 1: yes)"를 평가한 것이며, 0이 부여되었다고 해서 이것이 야간 활동의 전면적 부재를 입증하는 것은 아니다.
  - EltonTraits 저자들이 *Nycticorax nycticorax*에 대해 `Nocturnal = 0`으로 코딩한 구체적 기준이나 사유는 원천 파일에 개별 설명이 없어 알 수 없다(Unknown).

### 3.2 검증된 1차 생태 문헌 (Cornell Lab of Ornithology)
* **검증 URL**: `https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory` (Life History · Food)
* **검증된 사실 내용 요약**:
  - 해오라기(Black-crowned Night-Heron)는 낮 시간대 다른 백로류와의 경쟁을 피하기 위해 통상적으로 **저녁부터 이른 아침 사이(normally feed between evening and early morning)**에 먹이를 찾는다.
  - 다만 번식기에는 둥지의 새끼를 기르기 위한 추가 에너지 확보를 위해 **낮 시간대에도 취식(feed during the day throughout the breeding season)** 활동을 병행한다.
* **불일치**: EltonTraits의 이진 척도에서 `0`(주요 야간 취식: 아님)으로 단순 코딩된 것과, 실제 문헌에서 확인되는 복합적 활동 주기(저녁~아침 주 취식 및 번식기 주간 활동) 사이에 표현의 불일치가 존재한다.

---

## 4. 라이브 그래프 매핑 통계 (Live Matched Graph Claims)

NAS TEST 환경의 live Neo4j 인스턴스에서 AviList v2025b와 매핑된 `TraitClaim {trait_name: "nocturnal"}`의 집계 결과:

* 전체 매핑 클레임 수: **7,752건**
* `value_boolean: true`: **267건** (3.44%)
  - Strigiformes (올빼미목): 175건
  - Caprimulgiformes (쏙독새목): 59건
  - Podargiformes (개구리입쏙독새목): 15건
  - Aegotheliformes (올빼미쏙독새목): 8건
  - Nyctibiiformes (포투목): 6건
  - Apterygiformes (키위목): 3건
  - Steatornithiformes (기름새목): 1건
* `value_boolean: false`: **7,485건** (96.56%)
  - 이 집계에는 해오라기가 포함된다. 종별 판정의 정확성을 일괄 검증한 결과는 아니다.

> **주의 사항**:
> 1. 상기 수치는 EltonTraits 원시 파일 전체의 통계가 아니며, RobinGraph 라이브 그래프에 AviList v2025b 학명 일치로 매핑된 클레임 집계이다.
> 2. 7,485건의 `false` 전체가 잘못된 정보(False Negative)라는 의미가 아니다. 원천 데이터셋의 `0`이 매핑되었다는 집계이며, 개별 종의 활동 시간을 확정하는 근거로 사용하지 않는다.

---

## 5. 정책적 해석 및 표시 시맨틱 (Policy Semantics for False Display)

### 5.1 원자료 0(False)의 시맨틱
* `Nocturnal = 0`은 원천 데이터셋에 명시적으로 기재된 실제 분류 값이며, 데이터 누락(Missing / Null)이나 '알려지지 않음(Unknown)'을 뜻하지 않는다.
* 따라서 지식 그래프의 원천 클레임(`TraitClaim`) 단계에서는 출처 보존(Provenance)을 위해 `value_boolean: false`를 원형 그대로 유지해야 한다.
* 단, 이 값은 "EltonTraits 데이터셋의 분류 기준상 주요 야간 취식 조류로 분류되지 않음"을 나타내는 출처의 분류일 뿐, **"해당 종이 밤에 전혀 활동하지 않는다"는 증거는 아니다**.

### 5.2 표출 시맨틱 (Presentation Semantics)
* UI 프로필에서 `False` 값을 무조건 `아니요`로 표출하는 것은 사용자에게 야간 활동의 완전한 부재로 오인될 소지가 크다.
* 따라서 상세 종별 1차 문헌이 확보된 종에 대해서는 원천 클레임을 훼손하지 않으면서, 사용자에게 올바른 활동 시간 정보를 제공할 수 있는 별도의 검토된 수식(Qualification) 레이어가 필요하다.

---

## 6. Root 구현 반영 결과 (Implemented Solution in Root Track)

Root 트랙에서 소스 코드, UI, 테스트를 통합하여 다음 아키텍처로 구현했다. 배포 검증 결과는 RG-401~RG-404·RG-502 검증 기록에 별도로 남긴다:

### 6.1 구현 모듈: `src/robingraph/retrieval/reviewed_activity.py`
원천 데이터베이스의 원시 클레임 노드를 임의 삭제하거나 변경하지 않고, 종 프로필 조회 시 검증된 1차 출처의 설명을 결합하는 검토 레이어를 구축하였다.

```python
# reviewed_activity.py 주요 발췌
ACTIVITY_REVIEWS = {
    ('v2025b', 'Nycticorax nycticorax'): {
        'review_id': 'rg006-night-heron-2026-10-03',
        'reviewed_at': '2026-10-03',
        'value': 'evening_to_early_morning_with_breeding_daytime',
        'display': '주로 저녁부터 이른 아침에 먹이를 찾으며, 번식기에는 낮에도 활동합니다.',
        'source_name': 'Cornell Lab of Ornithology · Black-crowned Night Heron Life History',
        'source_url': 'https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory',
        'citation': 'Cornell Lab of Ornithology, Life History · Food',
        'license_name': '출처 기반 독자 요약 · 원문 미재배포',
    },
}

def reviewed_activity(lineage, traits):
    result = [dict(trait) for trait in traits]
    review = ACTIVITY_REVIEWS.get((lineage.taxonomy_release, lineage.items[-1].scientific_name))
    if review is None:
        return result
    raw = [trait for trait in result if trait.get('name') == 'nocturnal']
    result = [trait for trait in result if trait.get('name') != 'nocturnal']
    result.append({
        **review, 'name': 'activity_pattern', 'label': '활동 시간',
        'unit': None, 'inferred': False, 'source_claims': raw,
        'review_note': '활동 시간은 별도 출처를 검토해 설명했습니다. 원자료의 야행성 코드와 출처는 검토 기록에 보존합니다.',
    })
    return result
```

### 6.2 구현 평가
1. **출처 무결성 보존**: EltonTraits 1.0의 원본 클레임(`value_boolean: false`)을 삭제하거나 위변조하지 않고 `source_claims` 필드에 보존하여 데이터 계보(Lineage)를 유지하였다.
2. **생물학적 정밀도 확보**: Cornell Lab of Ornithology의 검증된 문헌에 근거하여 활동 시간(`activity_pattern`, `주로 저녁부터 이른 아침에 먹이를 찾으며, 번식기에는 낮에도 활동합니다.`)을 구체적으로 표출함으로써 활동 시간과 원자료 분류를 구분해 안내한다.
3. **버전 한정성(Bounded Review)**: 검토 기록을 특정 분류군 버전(`v2025b`)과 학명에 명시적으로 바인딩하여 향후 분류 개정 시에도 일관된 관리가 가능하도록 설계되었다.

---

## 7. 검증된 1차 출처 목록 (Verified Primary Sources)

1. **EltonTraits 1.0 메타데이터 및 코드북**:
   - **URL**: `https://esapubs.org/archive/ecol/E095/178/metadata.php`
   - **문헌**: Wilman, H., Belmaker, J., Simpson, J., de la Rosa, C., Rivadeneira, M. M., & Jetz, W. (2014). EltonTraits 1.0: Species-level foraging attributes of the world's birds and mammals. *Ecology*, 95(7), 2027-2027. (Ecological Archives E095-178-D1, Table 1).
   - **Figshare 파일**: `https://ndownloader.figshare.com/files/5631081` (`BirdFuncDat.txt`)

2. **Cornell Lab of Ornithology (All About Birds Life History)**:
   - **URL**: `https://www.allaboutbirds.org/guide/Black-crowned_Night_Heron/lifehistory`
   - **참조 섹션**: Life History · Food
   - **검증 내용**: 해오라기(Black-crowned Night Heron)는 통상 저녁부터 이른 아침 사이에 주로 먹이를 찾으며, 번식기에는 낮에도 취식함.
