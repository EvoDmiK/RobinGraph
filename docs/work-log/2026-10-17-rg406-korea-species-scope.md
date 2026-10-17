# RG-406 국내 기록·분포 범위와 이름 우선 정책 — 2026-10-17

## 요청 배경과 결과

전 세계 활성 조류를 대상으로 하던 검색에 국내/국외 범위와 언어 우선 정책을 추가하라는 요청이다. 사용자는 대한민국 기준을 선택했고, 추가로 원자료에 `Korea`라고 적힌 경우도 포함하도록 지시했다. Codex가 Claude·Antigravity·문서 담당과 협업하여 구현·통합·NAS TEST 배포와 실제 API/브라우저 검증까지 수행했다. Production은 변경하지 않았다. Git commit/push/병합은 수행하지 않았다.

이번 구현의 범위는 조류 종 탐색이다. 관찰·문헌 검색 전체에 대한 지리 필터가 아니다. 기본값은 기존과 같은 전체(`all`)다. 화면에 `전체`, `국내 기록·분포 확인`, `국외 분포 검토`, `미확인` 네 범위를 제공한다. “한국 비서식 전체”나 “현재 한국에 사는 모든 종”의 판정을 완료했다고 표현하지 않는다. RG-406의 범위 API·UI는 TEST 구현 완료이며, 전 세계 분포 전수 검토와 계절성 보강은 후속 사항이다.

## 확인한 원인과 출처 근거

기존 추천은 국명 유무와 점수를 사용했지만 지리 범위 계약이 없었다. 국명이 있다는 사실은 국내 분포의 증거가 아니며, 국명 없음·국내 기록 없음·원자료에 Korea가 없음도 비서식의 증거가 아니다. 기존 번역 이름이나 외부 사육 기록으로 분포를 생성하지 않았다.

- **대한민국 기준의 예외 수용**: 출처의 `Korea`, `Korean Peninsula`, `South Korea`를 수용한다. `North Korea`, `northern Korea` 등 북한만 명시한 근거는 국내로 승인하지 않는다. 사용자가 요청한 Korea 포함은 반도 전체를 대한민국과 동일시하는 일반 지리 판정이 아니라 이 서비스의 명시적 출처 수용 정책이다.
- **한국조류학회 2025 개정판 v2.1**: 공식목록 가-1은 야생에서 관찰되고 근거가 명확한 종이다. 가-2는 남한 기록은 없지만 북한에는 서식하거나 근거가 명확한 종이다. 가-2를 도입·탈출종으로 해석하지 않는다. 기존 국명 사전의 출처 범주를 국명 문자열과 독립적으로 사용한다. 이용자가 형식을 변경하는 등 자유롭게 가공 가능하다는 원문을 보존하고 정식 명명 라이선스는 확인되지 않아 `license_name:null`이다. 출처 분류는 IOC v15.1이며 정확한 AviList ID·학명 대응만 사용한다.
- **AviList v2025b Explorer**: CC BY 4.0, JSON range 열(13)의 종 원문을 사용한다. 종 원문이 없을 때만 직접 아종의 원문을 검토하고 source_rank·source_scientific_name을 유지한다. 부모 종/아종 근거를 동일한 대상으로 꾸미지 않는다.
- 원자료의 북한 한정·부정·과거·도입·미조 문구·물음표·모호한 인접 수역 등을 보수적으로 거절한다. 거절은 해당 문구를 국내 승인 근거로 쓰지 않는다는 뜻이며, 독립적인 KOS 가-1 근거가 있으면 국내 상태를 유지한다. 거절 합계는 44종/46행이며 전부 북한 문구라는 뜻은 아니다. Jeju 단독 표기는 생성기의 자동 승인 대상이 아니다.
- KOS 야생 기록에는 계절·미조 기록이 포함되지만 계절성 열은 없어 `seasonal_status:null`이다. AviList의 모호한 미조 문구는 자동 승인하지 않는다. 텃새·철새·현재 서식 여부를 생성하지 않는다.

출처와 고정 해시:

| 자료 | 출처 | SHA-256 |
|---|---|---|
| AviList Explorer v2025b | https://explore.avilist.org/data/avilist-2025b.json ; https://www.avilist.org/checklist/v2025b/ | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` |
| KOS 2025 v2.1 | https://sites.google.com/khu.ac.kr/korornsoc/알림마당/자료실 | `b660e125a35abc00df77aa61f3ba24997de7fe1d213ef1350ceacfe08466ba7a` |

새로운 제한 자료 수집, NIBR/IUCN 활성화, 수집 워크플로 실행은 하지 않았다. 원자료 갱신은 자동 주기 작업으로 추가하지 않았다. 다음 갱신 때 입력 해시·분류판·대응 관계를 다시 확인하고 생성기를 실행해야 한다.

## 데이터 분류 결과

실제 로컬 TEST DB의 활성 허용 종 11,131개를 ID·학명·concept set·분류판과 대조했다. `local-taxa-audit.json`, `local-distribution-counts.json`에 증거를 저장했다. 이는 실제 DB 정체성과 정책 데이터 대조이며 모든 종의 문헌 전수 검토라는 뜻은 아니다.

| 상태 | 수 | 의미 |
|---|---:|---|
| korea | 592 | KOS 가-1 단독 490 + AviList 단독 1 + 양쪽 101 |
| outside | 6 | 에이전트가 정확한 뉴질랜드 섬 정상 분포 원문을 검토한 6종. 독립적인 사람 검토는 하지 않음 |
| unknown | 10,533 | 미검토·근거 부족·판정 보류. 가-2 5종 포함 |
| all | 11,131 | 전체 활성 종 |

`outside`는 검토한 출처의 정상 분포가 한국 밖이라는 뜻이며 우연한 도래·사육 기록의 부재를 입증하지 않는다. 대상은 Apteryx maxima, A. rowi, A. mantelli, Nestor notabilis, Xenicus gilviventris, Callaeas wilsoni 6종이다. 나머지를 자동으로 국외 집합에 넣지 않는다.

중요 사례:

- 청둥오리 Anas platyrhynchos: 국내, 국명 표시.
- Nestor notabilis: 국명 높은산앵무가 있어도 국외 범위에서는 **Kea** 표시.
- Saxicola maurus: 직접 아종 S. m. stejnegeri의 Korea 원문으로 국내 승인. 현재 검증 국명이 없어 **Siberian Stonechat** 표시. 미대응 KOS 분할종의 국명을 붙이지 않는다.
- 타조 Struthio camelus: 국명은 있지만 이 자료 묶음에서는 미확인. 국외 범위에서 자동 반환하지 않는다.

## 변경 전후 동작과 API 계약

`SpeciesScope = Literal["all","korea","outside","unknown"]`, 기본값 `all`이다. POST `/v1/chat` 최상위 필드와 GET `/v1/taxa/profile`, `/related`, `/similar`, `/ecological-related`, `/lineage`에 전달한다. 잘못된 값은 API 검증 오류다.

분포 판정은 종 ID+정확한 학명+활성 concept set+분류판이 일치할 때만 유효하다. 불일치·명시된 비종 rank·자료 부재는 미확인이다. 기존 종 후보가 rank를 생략하는 경우에는 정확한 ID·학명으로 묶음의 종 정체성을 확인한다. 응답에 `distribution`(status, KR, basis, source evidence, seasonal_status, note)과 `display_name`을 추가한다. 계통 DTO의 display_name은 선택 필드이며 전체 기본 응답에서는 null로 기존 이름 의미를 유지한다.

이름은 전체/국내/미확인에서 검증 국명→영어→학명, 국외에서 영어→검증 국명→학명 순이다. machine-translated 국명은 승격하지 않는다. 종 카드 제목·후보 말풍선·계통 답변·관계/비교에 같은 서버 표시 정책을 전달한다.

선택 범위 밖의 프로필 GET은 404, 채팅은 안내와 함께 abstain하고 프로필을 반환하지 않는다. 모호한 legacy 일반 이름 관계 조회는 선택 범위에서 정확한 종/학명을 요청하여 범위를 우회하지 않는다.

같은 속/과·생태 관계는 Cypher에서 scope predicate를 LIMIT 전에 적용한다. TOP3는 전체 활성 후보의 기존 점수와 계통 정규화를 먼저 계산한 뒤 범위 필터→언어 우선→상위 3종 순으로 고른다. 범위를 바꿨다는 이유로 같은 후보 점수를 재정규화하지 않는다. 3종 미만이어도 범위 밖 종으로 채우지 않는다.

이름 해소는 그래프 일치와 벡터 후보를 범위로 제한하고 기존 실제 그래프 재검증을 유지한다. 벡터 검색은 기존 전역 최대 10개 히트 안에서 범위를 거르므로 범위 내 종이 전체 벡터 인덱스에 있어도 후보가 적거나 없을 수 있다. 검색 예산·벡터 인덱스·DB 스키마를 바꾸지 않았다.

범위 변경 시 진행 중 POST/조회에 AbortController를 연결하고 generation으로 늦은 응답을 무효화한다. 이전 카드·비교·대화를 정리하고 입력 초안은 유지한다. 자동 재질문하지 않는다. 이전 후보 버튼이 새 범위에서 질문을 보내거나 이전 요청이 새 요청의 busy 상태를 끝내지 못하도록 회귀 검사를 추가했다. 단독 /birds 화면도 GET 범위를 전달한다.

## 담당·변경 파일

- Claude: `retrieval/species_scope.py`, `species_distribution.json`, `scripts/build_species_distribution.py`, `tests/test_species_scope.py` 생성. 출처·북한 제외·아종·분류판·정확한 정체성·Cypher 매핑 검증.
- Antigravity: `api/static/index.html`, `chat.js`, `styles.css`, `birds.html`, `birds.js`, `tests/frontend/chat_ui.test.js`, `birds_ui.test.js`. 토글·설명·표시 이름·분포 근거·GET/POST 전파·상태 전환과 UI 단위 검사.
- Codex: `api/app.py`, `cli.py`, `retrieval/related_species.py`, `ecological_relations.py`, `similar_species.py`, `species_profile.py`, `species_questions.py`, `taxon_name_resolution.py`, `tests/test_species_scope_api.py`, 기존 API/deployment/CLI 계약 fixture. root 소유 init에 실제 요청 취소를 통합하고 회귀 3개 추가. TEST 실제 DB/API/브라우저·NAS 배포·상세 문서·Obsidian 정합성 담당.
- 문서 담당: 상세 초안을 자기 워크트리에 작성. 총괄이 가-2 의미, 국명 미확인 사례, 점수 검증의 mock/live 구분을 대조·보정하고 이 최종 기록으로 통합했다.
- `taxonomy_lineage_neo4j.py`의 기존 dirty 변경은 이번 scope 구현 파일로 잘못 계산하지 않는다. 이전 Jev/이름 해소/벡터/UI/MRR 변경을 보존하고 무관한 미커밋 변경을 되돌리지 않았다.

Orca run `run_42902bb0ed10`: Claude 조사→구현, Antigravity UI, 문서 담당을 감독했다. 최초 UI dispatch는 준비 timeout으로 실패했고 Task를 새 소유 터미널로 재시도하여 성공했다. 성공 메시지를 확인·ack하고 새 소유 UI 터미널만 release했다. 기존 사용자/외부 터미널은 retained로 보존했다. reclaimable worker는 0개다. 런타임의 실제 모델명을 별도로 입증하지 않았으므로 추정해 쓰지 않는다.

## 검증 명령과 실제 결과

| 검증 | 실제 실행 범위와 결과 | 증거 |
|---|---|---|
| Python 전체 | `/tmp/robingraph-qa-python/bin/python -m unittest discover -s tests` (PYTHONPATH=src), 922개 중 **884 통과·38 건너뜀·최종 실패 0**, 21.956초 | `python-final.log` |
| UI 단위 | `node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`, **317 통과·0 실패·0 건너뜀** | `frontend-final.log` |
| 생성 재현 | `PYTHONPATH=src /tmp/robingraph-qa-python/bin/python scripts/build_species_distribution.py --avilist /tmp/rg406-avilist.json --check`, 고정 데이터 재현 통과 | 생성기·정책 14개 검사 및 전체 로그 |
| API 범위 단위 | `tests/test_species_scope_api.py` 10개 포함. fake handler/fixture로 제외·계통 영어·점수 불변·이름 후보 범위 검증 | Python 전체 결과 |
| 실제 로컬 DB | 활성 11,131종 정체성/분류 집계 읽기 대조 | `local-taxa-audit.json`, `local-distribution-counts.json` |
| 실제 로컬 ASGI | 실 DB/provider 연결 후보 앱 인프로세스 11사례 통과, 데몬 배포 증거와 구분 | `verify_local_app.py`, `local-live.json` |
| 실제 로컬 HTTP/browser | 별도 소유 QA 앱8001, Chromium 1280/390/320, 9 POST와 /birds 프로필 검증 통과 | `local-browser/browser-live.json` 및 화면 |
| 실제 NAS HTTP | 실행 중 최종 TEST 서버에 HTTP 12사례 전부 통과. 8 POST(범위 7+Jev 오타 1), 4 GET(관계3+프로필1) | `verify_http.py`, `nas-http.json` |
| 실제 NAS 계약 | `docker exec robingraph-api-test python scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json` 통과, schema/response drift 없음 | `nas-api-contract.json` |
| 실제 NAS browser | SSH 포워딩을 통해 실행 중 NAS 자산/API/DB 사용. Chromium 1280/390/320, 각3POST=9와 /birds 1건 통과, 페이지 오류/가로 넘침 없음 | `nas-browser/browser-live.json`, 화면 3개 |
| NAS DB 전후 | Taxon33694, Document2, Chunk4, TaxonNameVectorEntry850, TaxonNameVector850, HybridVectorChunk2가 동일 | `nas-db-before.json`, `nas-db-after.json` |
| 소스·운영 | 패키지141파일 해시 확인, 실행 이미지의 src/scripts101파일 해시 일치, TEST healthy, PROD ID/시작/이미지 동일 | `nas-release.json`, `release-package.json` |
| graphify | `graphify update .`, 5764노드·11957엣지·347커뮤니티. SQL parser 미설치 4파일 건너뜀 | `graphify-final.log` |

Python 전체 결과는 주로 fixture/mock 단위 검사이며 38개 조건부/외부 통합 검사를 건너뛰었다. 따라서 전수 실제 DB 통합 검사 완료라고 표현하지 않는다. 실제 DB/API/provider 범위는 위 별도 행만 해당한다. 점수 불변은 모의 회귀에서 확인했으며 실제 API의 점수 전수 비교를 수행하지 않았다. NAS DB 노드 수 동일은 모든 DB 값의 불변을 입증하는 전수 checksum 검사가 아니다. 작업 자체에 DB 쓰기·마이그레이션·벡터 재생성 명령은 없었다.

실제 HTTP 결과: 청둥오리 korea answer/outside abstain, Kea outside answer/korea abstain, 타조 unknown answer/outside abstain, Saxicola maurus korea answer, 관련16/유사3/생태6개 항목 모두 국내 범위 일치. “청둥오리에 대해 일고 깊어”도 korea에서 실제 Jev를 거쳐 올바른 종 프로필을 반환했다. 브라우저에서는 키보드 Space로 토글, 초안 유지·자동 제출 없음, 이전 대화 제거, Kea 제목, unknown 타조와 요청 scope 전파를 확인했다. 느린 응답·이전 후보 버튼 격리는 단위 검사이며 실제 네트워크 지연 주입 검증과 구분한다.

### 검증 중 실패와 수정

처음 Python 실행에서 잘못 지정한 존재하지 않는 테스트 모듈은 loader 오류였다. 계통의 새 선택 필드/범위 파라미터로 기존 API·CLI·배포 canary fixture가 불일치하여 갱신했고, 영명 위치 인자를 잘못 넣은 신규 fixture도 키워드 인자로 수정했다. 일시적으로 rank 누락을 모두 거절하는 변경은 기존 정확한 ID·학명 종 후보 계약과 충돌하여 되돌렸다. 최종 전체922개 결과가 위 통과 수다.

UI 통합 중 중복 controller 상태와 POST signal 연결을 정리했으며, fake window에 AbortController가 없던 검증 환경은 명시적으로 주입했다. 최종317개가 통과했다. `git diff --check`의 테스트 파일 말미 빈 줄 1건을 제거했다.

로컬 임시 코드 검증은 read-only 컨테이너에 docker cp가 거절되어 tmpfs stdin tar 방식으로 바꿨고, 기존 fixture 앱 초기화가 요구하는 data 경로를 읽기 링크로 연결한 뒤 통과했다. 최초 브라우저 접속은 QA 앱 준비 전 ERR_EMPTY_RESPONSE였으며 health 확인 뒤 재실행해 통과했다. 모의 fixture를 실제 종 검증으로 집계하지 않았다. 최종 NAS deploy/HTTP/browser 검사에는 실패가 없었다.

## TEST 배포와 Git 상태

이전 Jev TEST 패키지를 기준으로 승인된 runtime16경로만 overlay하여 이전 이름 해소·벡터·후보 UI 변경을 보존했다. 새 runtime 파일은 scope 모듈·분포 JSON·생성기3개이며 총141개 파일 패키지다. 문서·테스트·AGENTS·MCP 설정·환경 비밀값은 배포 패키지에서 제외했다. 원격 기존 TEST 설정을 비공개 복사해 이미지/revision만 변경하고 TEST DB 연결이 이전과 같으며 운영과 다른 것을 메모리에서 확인했다.

최종 실행 명령:

```sh
cd /home/kimdove/robingraph-rg406-7c1eb99c3762
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy
```

- TEST image: `robingraph-api:test-rg406-7c1eb99c3762`
- image ID: `sha256:a89f82b18e940bfa9624c41ae0bd302115307f9c8e4addecd3d76b0d0c82a1ad`
- TEST container: `6545b1ab44e17aa0491419abf218a4fec29330043f548b1a9b6ae5da1ca77541`
- 시작: `2026-10-17T05:54:46.331763713Z` (UTC), healthy.
- snapshot SHA-256: `7c1eb99c3762dc37ce1f9eba45dfd25306ce44cf9b4b7976a3815af9aa414387`
- archive SHA-256: `27375aad52b9ae55cb66878d688cfc8192ee82043eabd552fb99c2031e0b1bf1`
- OCI revision: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-rg406-7c1eb99c3762`. 미커밋 차분을 포함한 snapshot 표기이며 새 Git commit이 아니다.
- 이전 TEST image `robingraph-api:test-jev-typo-0629aa1e9f4a`를 보존했다. 임시 후보160383933eeb는 빌드만 했고 실행 배포하지 않았다.
- Production `robingraph-api:prod-approved-ui-0681747`, container `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`, 시작 `2026-10-10T06:07:33.413088244Z`가 그대로다. 운영 재시작·DB 변경·배포는 수행하지 않았다.
- Git commit/push/병합 없음. 인증 정보는 이 문서와 검증 자산에 포함하지 않는다.

## 한계와 후속 확인

1. 국외 검토6종과 미확인10,533종: 전 세계 분포의 전수 분류는 후속이다. 신뢰할 수 있고 이용 가능한 원자료를 추가 확보하고 충돌·분류판·라이선스를 재검토해야 한다. AI 에이전트 검토를 사람 전문가 검토로 표현하지 않는다.
2. 계절성·현재 서식·미조/사육 부재는 미검증이다. 모드 이름과 출처 범위를 유지한다. Saxicola maurus의 국명은 검증되지 않았으므로 생성하지 않는다.
3. 기존 전역 벡터 히트 최대10개 이후 범위 필터의 재현율 한계가 있다. 인덱스 전체 범위별 검색은 이번 변경에 포함하지 않았다.
4. 물리 휴대폰·Safari/WebKit·Firefox·물리 재부팅은 미검증이다. 실제 Chromium은 viewport 에뮬레이션이며 물리 모바일 검사가 아니다. 외부 사진 전송·전체 종 답변 정확성을 전수 검증하지 않았다.
5. 원격 검증은 NAS TEST에 직접 연결한 SSH 포워딩 기준이다. 공개 도메인 프록시/외부 접근 경로를 검증했다고 주장하지 않는다. Production 승격은 사용자 결과 확인과 별도 승인 이후다.
6. 후속 자료 확장 상태를 백로그에 남기고 저장소·Obsidian의 수치·검증·배포 상태를 일치시킨다. 소유한 로컬 QA 컨테이너 robingraph-rg406-qa를 제거했고 SSH 포워딩·control master를 종료했다. 기존 로컬 TEST 컨테이너는 유지했다.

## 문서 정합성과 최종 정리

Obsidian 상세 작업 기록에 이 문서와 같은 본문을 저장하고, 전체 및 4xx 백로그의 RG-406 상태를 `TEST 구현 완료 · 자료 확장 후속`으로 갱신했다. 초기 등록 계획은 당시 기록으로 구분해 보존했고 전 세계 비서식 전수 분류 완료 체크를 하지 않았다. 저장한 세 문서를 재조회해 내용 일치를 확인했다. 최종 `git diff --check` 통과, 검증 JSON의 통과 상태와 NAS DB 전후 수치 일치도 재확인했다. 인증 정보 할당 문자열이 검증 자산에 없는지 확인했다.
