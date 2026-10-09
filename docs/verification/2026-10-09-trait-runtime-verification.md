# 전체 종 형질: 승인된 저장 후보의 읽기 시점 복구 작업 기록

작성 2026-10-09 · 작업 경로 `/Volumes/Dove-Nest-SSD/app-data/orca/kimdove/home/workspaces/RobinGraph/dev-3` · 기준 HEAD `4c62562eca085122c0edd399149f5d179928303b`

## 배경·목표와 구현 결과

까치의 비율 차트 공백에서 시작된 전체 종 감사는 원기록 유실이 아니라 상당수 원본 학명의 현재 분류 연결 실패를 확인했다. 이전 감사는 Elton 2,241개·AVONET 1,130개 미해결 후보의 전체 형질값이 profile_json에 보존됨을 실제 TEST DB와 고정 원본으로 확인했다. 이번 작업은 Claude의 검증된 교차표가 승인한 **고유 1:1 변경학명**만 읽기 시점에 복구하며, DB의 노드·연결·후보 상태를 변경하지 않는다.

실 TEST의 고정 출처·활성 릴리스·대상 분류 snapshot/Avibase gate를 통과한 후보 2,571개와 같은 활성 PostgreSQL의 허용 원기록 2,571개를 수집했다. 새 단일 종 함수를 이 실 DB rows에 적용하여 Elton 1,868개 프로필 → **9,340개 형질**, AVONET 703개 프로필 → **9,131개 형질**을 복구했다. 후보값 대 반환값 불일치, 복구 실패, source/type 중복은 **0건**이다. 모든 숫자는 실제 DB 관측이며 생성기의 가능성 예상치만 인용한 것이 아니다.

## 변경 파일·전후 동작

- `src/robingraph/retrieval/trait_mapping.py` (새 파일): 패키지 내 교차표의 원본 provenance·고유성 검증과 1회 캐시, 현재 종에 필요한 후보만 조회하는 Cypher, 동일 활성 PostgreSQL source record 증거 확인, 저장된 정상화 profile의 재검증, source별 기존 형질 유지/중복 배제, taxonomy_alignment 표시를 구현했다. scripts를 import하거나 원본 재다운로드·n8n·ingest API를 호출하지 않는다.
- `src/robingraph/retrieval/species_profile.py`: 기존 active_release_context와 기존 TRAIT_QUERY는 유지한다. 이미 읽은 두 context와 정확연결 claim을 새 함수에 전달하고, 기존 reviewed_activity 처리는 복구 후 같은 위치에서 적용한다. 추가된 필드와 새 형질 외 기존 원값·출처·정책 gate를 변경하지 않는다. 원 source_note/certainty는 API에 보존하고 공식 메타데이터가 확정적으로 명시한 추정 코드를 inferred에 반영한다.
- `tests/test_trait_mapping.py`: 신규 25개 테스트로 승인 복구, false/0, 단일 종 한정 조회, metadata/출처/릴리스/식별자 거부, 분할·병합·IOC27 거부, inferred/단위/locator 유지, source/type 중복 배제, 정확연결의 accepted/needs_review, 원기록/교차표 오류와 다른 정상 소스 보존을 확인한다.
- `/tmp/rg-trait-runtime-report.md`: 구현·검증·실측 상세와 재현 명령을 기록한다. 별도 기존 감사 도구 파일은 이번 dispatch에서 수정하지 않았다.

이전 직박구리·대백로는 AVONET 13형질만 읽었지만 각각 Elton의 승인된 기존 행 5형질(체중·야행성 코드·먹이 유형·먹이 구성·먹이 활동 위치)을 추가하여 18형질이 된다. Tachyspiza badia는 0→18형질이 된다. Elton `pelagic_specialist`는 기존 LABELS에서 미지원이므로 복구에도 노출하지 않는다.

Pica serica는 교차표 엔트리가 없으므로 0→0 raw/read_traits가 유지되고 **가짜 먹이/활동 위치 비율은 추가되지 않는다**. 기존 API의 별도 검토 정성·체중 자료는 이번 함수에서 수정하지 않는다. Pica pica는 기존 18형질 원값을 유지하며 개념 정합성 needs_review를 표시한다. 사유는 소스별 실제 교차표 코드이며, 모든 불일치를 분할 전 자료라고 일괄 명명하지 않는다.

## 실제 gate와 증거의 의미

1. 캐시 로딩 시 schema_version/분류판과 AviList·Elton·AVONET의 **고정 개별 SHA-256·릴리스·URL·라이선스**를 확인한다. 승인 규칙은 AVONET 고유 동일 Avibase, Elton BL3 및 정확한 `1BL to 1BT` 한 행 체인만 허용한다. 분할/병합, IOC27, Avibase 불일치, source record 중복, 한 소스의 복수 행→한 대상 승인 충돌은 복구에서 제외한다. 현재 Pica pica→serica의 출처 개념 ID가 일치하지 않으므로 승인 경로가 없다.
2. PostgreSQL의 실제 활성 context가 허용 dataset ID, 현재 concept set, taxonomy release, 해당 trait release와 고정 원본 해시를 제공해야 한다. Elton의 bundle SHA `fd3749be71afd154155b46c3e065e32485bd4106c1883b928a2064aa5c39822f`와 Elton 개별 SHA `97216eb1797da077169ebb1ebea275db293b09fc62f8bb8911f9beb98c50d321`는 서로 다른 것으로 검증한다. AVONET release/content hash와 sheet도 고정한다. 새 릴리스가 들어오면 명시적인 새 교차표·pin 검토 없이 임의로 복구하지 않는다.
3. Neo4j는 해당 **종 ID 한 개**와 후보 ID 최대 두 개만 조회한다. 대상 allowed Taxon의 현재 분류 release·동일 dataset의 allowed concept set·고정 snapshot SHA·대상 학명·Avibase ID가 모두 일치해야 한다. 후보 allowed policy/open 상태/출처 record/name/last_seen_run이 활성 성공 run과 같아야 한다. Python에서도 후보 identity/policy/run/release를 재검증한다.
4. 실제 후보에는 EvidenceUnit/SourceRecord graph 연결이 없다. 따라서 이를 있다고 주장하지 않는다. 동일 활성 PostgreSQL source_release의 allowed trait_profile record, 성공 run, 원본 SHA/URI/record ID/출처 학명, Elton SpecID·release 또는 AVONET row/sheet/Avibase/inference metadata를 **정식 증거**로 확인한다. PostgreSQL source record 조회는 `SET TRANSACTION READ ONLY` 후 필요한 ID만 수행한다.
5. profile_json을 100,000자 이하로 제한하고 소스 identity·shape·유효 숫자·단위·범주·distribution key/범위/합계(기존 99~101 허용)·원숫자/0/False·inferred source fields·통계 종류를 검증한다. 정상화된 값을 보존하며 임의 비율 추정·재계산·이름 근사는 없다. 아래 공식 메타데이터 코드가 명시하는 추정 표시만 값에 부가한다. 같은 dataset/name 형질이 이미 있으면 기존 값이 우선한다. 한 후보가 malformed/차단되거나 PG 확인이 실패해도 다른 정상 소스와 기존 정확연결 형질을 유지한다.
6. 출력 증거는 `evidence_kind=stored_source_record`, `mapping_provenance.read_time_recovery=true`와 원본/교차표/분류 snapshot SHA를 포함한다. 출처 URL·라이선스·citation은 검증된 고정 출처와 row/SpecID locator를 사용한다. 실제 DB에 TraitClaim/EvidenceUnit을 생성한 것처럼 표시하지 않는다.

정확학명 기존 자료는 삭제하거나 값을 바꾸지 않고 다음 object를 붙인다: `{status, method, source_scientific_name, target_scientific_name, reason}`. 같은 record의 교차표/활성 provenance 검증이 맞으면 accepted, 개념 불일치나 확인 불가면 needs_review다. fixture/알 수 없는 dataset/일반 종 ID 경로는 기존 동작을 유지하며 실제 source gate를 fallback으로 풀지 않는다. 교차표가 누락/깨진 경우 기존 실제 source 값은 보존하고 검증됨을 주장하지 않는다. 프런트엔드 수정은 Claude의 별도 소유 영역이다.

## 실 TEST 검증 범위와 성능

새 두 Python 파일과 교차표를 SSH stdin으로 보낸 **격리된 TEST 컨테이너 프로세스의 메모리**에서만 실행했다. 디스크에 배포하거나 실행 중 API 프로세스를 교체하지 않았다. 실제 Neo4j는 READ_ACCESS/execute_read의 고정 MATCH 쿼리, PostgreSQL은 연결 전체 default_transaction_read_only=on으로 수집했다. 활성 환경은 NAS 컨테이너 안에서만 읽고 자격증명·환경값을 출력·문서에 저장하지 않았다.

대표 종 6개는 기존 함수와 새 read_traits를 **실 DB에 직접 연결하여 각각 호출**했다. 이후 전체 승인 대상은 같은 단일 종 Cypher gate를 bulk 감사에 확장하여 실제 후보와 canonical PG records를 수집하고 새 함수를 그 실 rows에 replay했다. 전체 2,571개를 각각 네트워크 호출한 것은 아니며, 아래 전체 replay 1,103.21 ms는 네트워크 조회 전체 시간이나 사용자 API latency가 아니다.

| 종 | 이전→새 형질 | 복구 형질 | 새 read_traits 실측 ms | 총 PG 연결 / Neo4j query | 추가 왕복 |
|---|---:|---:|---:|---|---|
| Hypsipetes amaurotis | 13→18 | 5 | 180.49 | 3 / 2 | PG 1 + Neo4j 1 |
| Ardea alba | 13→18 | 5 | 84.21 | 3 / 2 | PG 1 + Neo4j 1 |
| Tachyspiza badia | 0→18 | 18 | 180.95 | 4 / 2 | PG 2 + Neo4j 1 |
| Pica serica | 0→0 | 0 | 35.83 | 2 / 1 | 0 |
| Pica pica | 18→18 | 0 | 67.04 | 2 / 1 | 0 |
| Anas platyrhynchos | 18→18 | 0 | 41.89 | 2 / 1 | 0 |

원래 reader의 활성 context 조회 2 PG + TraitClaim 조회 1 Neo4j를 포함한 수치다. single species 복구의 추가 조회는 Neo4j 1회와 소스별 필요한 record 한 개(최대 2개)의 PG 조회다. exact-only 종은 추가 DB 조회가 없다. 시간은 각각 1회 관측이며 p95나 부하 테스트가 아니다. 사진/설명 enrichment를 포함한 실제 HTTP 전체 응답 지연이 아니다.

교차표 index build는 NAS에서 **380.54 ms**로 1회 측정했고 `lru_cache(maxsize=1)`로 worker process마다 한 번 읽는다. 이 측정은 메모리에 decode된 artifact의 index build이며 실제 cold 파일 읽기/JSON 해독 비용을 포함한 총 startup latency로 단정하지 않는다. 파일은 약 5.3 MB다.

## 테스트 실제 결과와 배포 정보

- 신규 25개 + 기존 species_profile 20개: **45 실행·45 통과·0 실패·0 skip**, 최종 방어 코드에서 확인했다. 합성·mock 검증이며 실제 DB/API 결과와 다르다.
- 전체 Python suite: 최종 **744 실행·707 통과·37 skip·0 실패**, 17.965초. 기존 통합검증 35개와 원본 재생성에 외부 raw dir가 필요한 교차표 2개가 건너뛰어졌다. 테스트의 mocked n8n 상태 로그를 실제 n8n 활성화 실행으로 해석하지 않는다.
- 코디네이터가 별도로 raw dir를 제공하여 수행한 시점의 **740 실행·705 통과·35 skip·0 실패**, 프런트엔드 **273 통과**는 전달받은 독립 검증이다. 이후 교차표/식별자 방어 테스트 2개와 확정 추정 코드 테스트 2개가 추가되어 744가 됐다. 코디네이터의 최종 원본 포함 재실행은 744 실행·709 통과·35 skip·실패 0으로 전달받았다. 코디네이터의 당시 테스트를 본 worker가 실제 실행한 것으로 기록하지 않는다.
- 실 DB: 후보/활성 canonical records 각 2,571개, 승인 복구 1,868/703개, 원값 불일치 0; 상세 반환값과 측정은 아래 JSON.
- git diff --check exit 0. 신규 untracked 파일의 모든 내용을 이 검사만으로 검증했다는 뜻은 아니다.
- runtime 소유 파일 3개와 /tmp 보고서만 이번 dispatch에서 변경했다. DB mutation, commit, deploy, PROD 변경, n8n 실행/수집, 기존 ingest/generator/UI 수정은 수행하지 않았다. graphify query는 실행했고 graphify update는 코디네이터의 통합 단계로 남겼다. 저장소/Obsidian 작업 문서 통합도 코디네이터 영역이다.

코디네이터 후속 정보(전달받은 상태): 원본 제공 전체 744개 회귀 통과 후 통합 코드가 `663ef4f`로 커밋됐고 TEST 패키징/배포를 시작했다고 알렸다. 이 worker가 커밋/배포한 것은 아니며, 배포 완료·신규 실 HTTP/브라우저 결과는 이 보고서에서 직접 확인하지 않았다. 코디네이터는 Tinamus osgoodi / Megapodius decollatus D1의 실제 HTTP 추정 표시도 후속 확인할 예정이라고 밝혔다. 추가 코드 변경은 필요하지 않다.

## 한계와 후속 사항

읽기 복구는 graph ASSERTS_ABOUT 연결이나 후보 해결 상태를 영구 저장하지 않는다. read_traits를 쓰는 profile에는 나타나지만 Neo4j claim만 사용하는 다른 similarity/ecological retrieval의 전체 후보 pool이 자동 확대되지는 않는다. 그런 확장은 별도 ownership/설계 검토가 필요하다. 같은 분류개념이라는 것은 고정 교차표의 ID/1:1 근거이며 원문 연구의 지역·표본 적합성을 독립적으로 다시 확인한 것은 아니다. 원본값이 들어간 candidate profile_json의 byte별 암호학적 서명은 없으며, 이전 고정 원본 감사에서 전체 후보값 일치가 확인됐고 이번에는 active run/allowed evidence/identity와 정상화 값 구조를 검증했다.

이 작업의 새 코드로 실제 HTTP API/브라우저를 검증했다고 주장하지 않는다. 로컬 새 함수의 메모리 실 DB 검증이다. 최종 통합/TEST 배포/새 HTTP·브라우저 검증은 코디네이터의 후속 단계다. 잘못된 source/새 릴리스/불확실한 분할·병합 후보는 계속 미복구로 남는다. Pica serica 비율은 별도 적합한 원자료가 생기기 전에는 추가하면 안 된다.

## 재현 명령

저장소 root에서 오프라인 검증:

```sh
PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest tests.test_trait_mapping tests.test_species_profile -v
PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -q
git diff --check
```

아래 Python은 새 파일을 **메모리로만** 로드하여 대표종을 actual TEST DB에서 재검증한다. SSH BatchMode/ControlPath, 컨테이너 이름은 고정하며 환경값을 출력하지 않는다. 전체 후보 전수 gate/replay는 아래 실측 방식처럼 CANDIDATE_QUERY를 `id:request.target_taxon_id`로 바꾸고 runtime LIMIT만 제거한 bulk 감사 + source_records(context, accepted IDs) 두 번으로 확대하면 된다. 실제 사용자 single-profile 함수는 원래 고정된 단일 종 쿼리를 그대로 사용한다.

```python
import base64, json, subprocess, zlib
from pathlib import Path
payload = {
    'module': Path('src/robingraph/retrieval/trait_mapping.py').read_text(),
    'profile': Path('src/robingraph/retrieval/species_profile.py').read_text(),
    'index': json.loads(Path('src/robingraph/retrieval/trait_crosswalk.json').read_text()),
}
blob = base64.b64encode(zlib.compress(json.dumps(payload).encode())).decode()
runner = "blob=" + repr(blob) + "\n" + r'''
import base64, json, sys, types, zlib
from functools import lru_cache
import psycopg
from psycopg import sql
from neo4j import GraphDatabase, READ_ACCESS
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import IngestionStore
from robingraph.retrieval import species_profile as sp
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon
p = json.loads(zlib.decompress(base64.b64decode(blob)))
tm = types.ModuleType('robingraph.retrieval.trait_mapping')
tm.__file__ = '/memory/trait_mapping.py'
sys.modules[tm.__name__] = tm
exec(p['module'], tm.__dict__)
index = tm.build_index(p['index'])
assert index is not None
tm.crosswalk_index = lru_cache(maxsize=1)(lambda: index)
exec(p['profile'], sp.__dict__)
pg = PostgresSettings.from_environment()
assert 'test' in pg.database.lower()
class Store(IngestionStore):
    def _connect(self):
        c = psycopg.connect(**self._settings.connection_kwargs(),
                            options='-c default_transaction_read_only=on')
        c.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(self._settings.schema)))
        return c
store = Store(pg)
ns = Neo4jSettings.from_environment()
with GraphDatabase.driver(ns.uri, auth=(ns.username, ns.password)) as d:
    with d.session(database=ns.database, default_access_mode=READ_ACCESS) as session:
        class Repo:
            def _run(self, q, **params):
                return session.execute_read(lambda tx: tx.run(q, **params).data())
        repo = Repo()
        for name in ['Hypsipetes amaurotis', 'Ardea alba', 'Tachyspiza badia', 'Pica serica', 'Pica pica']:
            rows = repo._run("MATCH (t:Taxon:BirdTaxon {rank:'species',scientific_name:$name})-[:IN_CONCEPT_SET]->(:TaxonConceptSet {id:$concept}) RETURN t.id AS id", name=name, concept='rg:concept-set:avilist-v2025b')
            assert len(rows) == 1
            lineage = TaxonomyLineage(name, 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b',
                                      (LineageTaxon(rows[0]['id'], 'species', name, None),))
            traits = sp.read_traits(repo, store, lineage)
            print(json.dumps({'name': name, 'traits': traits}, ensure_ascii=False))
'''
result = subprocess.run(['ssh', '-p', '99', '-o', 'BatchMode=yes', '-o',
    'ControlPath=/tmp/rg-conservation-ssh.sock', 'kimdove@192.168.219.99',
    'docker exec -i robingraph-api-test python -'], input=runner,
    text=True, capture_output=True, timeout=600)
if result.returncode:
    raise SystemExit('Read-only TEST verification failed; stderr withheld')
print(result.stdout)
```

## 공식 원자료의 추정·불확실성 코드 보완

코디네이터의 추가 원자료 검토를 반영했고 `/tmp/elton-metadata.htm` 바이트 SHA-256을 직접 확인했다. 공식 출처는 `https://ndownloader.figshare.com/files/5631093`, SHA-256 `be3425118c2087a2795dff699d8264cbbc1b0c65fdbb93f0a7533b2d4ea54962`다. 원문은 BL3가 BirdLife V3(2010)이며 bird taxonomy가 Jetz 2012와 같음을 명시한다. 본 보완은 현재 저장 데이터의 의미를 드러내며 새 원자료 수집/n8n 실행은 아니다.

- 체중 `BodyMass-SpecLevel=0`: genus/family typical value로 추정. 기존 exact claim의 certainty와 복구 profile의 body_mass_spec_level을 그대로 보존하고 body_mass.inferred=True를 적용한다.
- 활동 위치 `ForStrat-SpecLevel=0`: species-level 자료 없음. 기존 certainty/복구 foraging_spec_level을 보존하고 foraging_strata_distribution.inferred=True를 적용한다.
- 식이 `Diet-Certainty=D1/D2`: 종별 정보가 없고 genus/family typical value. diet_category 및 diet_distribution 모두 inferred=True를 적용한다.
- `C`: 불확실성과 특정 근연종 추정 양쪽 의미가 있으므로 C만으로 추정이라고 단정하지 않는다. certainty 원값만 보존한다. 이미 원 claim에 inferred=True가 있었으면 그 플래그는 그대로 유지한다.

최종 새 코드로 actual TEST 후보 2,571개+canonical source records 2,571개를 다시 조회/검증했다. **Elton 1,868 / AVONET 703 전체의 값과 플래그가 source 원값/확정 규칙에 동일했고 issues 0**이다. 기존 대표종 반환 형질에도 최신 source_note/certainty 필드가 들어 있으며 아래 JSON representative traits는 이 최종 재검증 결과로 갱신했다. 앞의 실행 시간은 추정 코드 보완 이전의 실제 1회 관측으로 유지했으며, 보완 후 시간을 다시 측정했다고 주장하지 않는다.

| 대상 | 체중 추정 | 활동 위치 추정 | 식이 유형 추정 | 먹이 구성 추정 | C 보존(추정 미단정) |
|---|---:|---:|---:|---:|---|
| 복구된 Elton 1,868 프로필 | 191 | 45 | 139 | 139 | 원 certainty 보존 |
| 기존 exact Elton 7,752 프로필 | 631 | 266 | 685 | 685 | 각 식이 형질 265건 |

기존 exact 수치는 실제 allowed evidence/현재 source release claim의 certainty 코드를 source_note와 함께 group-query한 뒤 새 helper의 확정 규칙으로 집계했다. 기존 7,752종 모두를 추가 HTTP 호출했다는 뜻은 아니다. 새 read_traits 대표종 실 호출과 코드 보존/추정 rule unit test를 별도로 수행했다. AVONET 기존 per-trait inferred는 그대로 보존했으며 복구된 703프로필 중 추정형질은 체중31, 부리 콧구멍18/너비14/전체12/높이13, 부척12, 날개11, 꼬리12로 총123건이다.


## 상세 반환값

[실 TEST 함수 검증 JSON](2026-10-09-trait-runtime-verification.json)에 전체 반환값과 집계를 보존했다. 배포 후 HTTP/브라우저 검증은 [통합 작업 기록](../work-log/2026-10-09-all-species-trait-recovery.md)을 참조한다.
