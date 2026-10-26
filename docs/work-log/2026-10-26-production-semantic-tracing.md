---
created: 2026-10-26
date: 2026-10-26
project: RobinGraph
type: worklog
status: completed
task_id: RG-212
tags: [worklog, robingraph, production, tracing]
---

# [RG-212 연계] 시맨틱 질의·원인 trace 운영 배포 — 2026-10-26

## 요약

사용자 명시 승인에 따라 TEST 검증 소스를 NAS Production에 배포했다. Jenkins `RobinGraph-PROD #9`는 SUCCESS였고, 운영 컨테이너에서 healthy·active/semantic·tracing 활성화와 MLflow 실험 `50 / robingraph-prod`를 확인했다. 운영 공개 요청 3 POST와 3 GET은 모두 HTTP 200이었으며, 동일 질문·마스킹된 응답·태그가 실험 50의 고유 trace 3개와 일치했다.

이번 배포는 Git commit/push 없이 승인된 미커밋 snapshot을 일회성 Jenkins Replay로 빌드한 것이다. 소스 234파일은 SHA256 `6a95918a55332aa0195c07bf4e5a9c60a7cb006b67fd56d255d683f22c72c922`로 식별하고 immutable image digest와 연결했다. 기존 Jenkins 정의·매개변수·job properties와 TEST 컨테이너는 유지했다. 일반 main 자동 파이프라인은 여전히 lexical 설정이므로 이번 snapshot과 main의 동기화는 별도 승인 범위다.

이 작업의 배포·관측 검증은 완료했지만 RG-212 전체는 진행 중이다. 기존 TEST의 V2-07A 감사 거부와 V2-10B 수치 경계 보류는 해결하지 않았다. 공개 3건의 운영 관측 성공을 질의 일반화 완료나 모든 계획·감사 경로의 검증으로 해석하지 않는다.

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 검증 결과 |
| --- | --- | --- |
| 요구사항 | 검증 소스 운영 반영과 질문 처리 원인 관측 | 사용자 명시 운영 승인 |
| 설계 | 일회성 Replay·불변 snapshot·immutable image | 커밋 ancestry와 실제 배포 source를 구분 |
| 코드 / 설정 | 기존 검증 소스·active/semantic·tracing true·실험 50 | 새 질의 수정 없이 검증 snapshot 배포 |
| 실서비스 배포 | NAS Production 교체 | Jenkins #9 SUCCESS·healthy |
| 검증 | Python 1,280 pass/40 skip, ops mock 16, Node 322 | 후보 3/3·공개 POST 3/3·GET 3/3·trace 3/3 |
| 형상 관리 | 기준 revision 834c535의 미커밋 snapshot | commit/push 없음·Jenkins 기존 설정 보존 |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 / 요구사항

TEST에서 검증한 시맨틱 질의 해석·원문 근거 검증·조건 미적용 metadata·특정 식물 먹이 자료 한계와 원인 관측 기능을 운영에 반영하도록 사용자가 승인했다. 운영에서 정상 답변, 의미가 모호해 되묻는 경우, 자료 부족으로 답하지 못하는 경우를 구분하고 실제 요청의 trace로 확인하는 것이 이번 배포의 완료 조건이었다.

### 원인 분석 / 설계 검토

기존 운영은 active/lexical·tracing false였으며, main checkout 기반 Jenkins 경로만으로는 미커밋 TEST snapshot을 대표할 수 없었다. 검증한 파일과 배포한 파일을 연결하려면 소스 manifest와 immutable image digest가 필요했다. 기준 Git revision만으로 배포 내용 전체를 식별하지 않았다.

MLflow는 실험 이름만 설정해도 기존 ID 설정에 의해 TEST 실험으로 기록될 수 있다. 전용 실험 50을 만들고 실제 운영 요청이 해당 실험의 root trace로 남는지 확인했다. 설정값·패키지 설치 확인과 실제 trace readback을 별도 검증으로 취급했다.

```text
검증 TEST manifest → 불변 snapshot → Jenkins 검사·이미지 빌드
→ NAS 후보 실제 API → 운영 교체 → 공개 API → 실험 50 동일 요청 trace
```

---

## 2. 해결 방안 및 설계

- 승인된 234파일 snapshot을 일회성 Jenkins Replay에서 사용했다. TEST/local source와 release manifest 일치를 확인한 뒤 immutable image를 만들었다.
- 운영 interpreter를 lexical에서 semantic으로 바꾸고 tracing을 활성화했다. 실제 교체 후 환경을 다시 읽어 active/semantic·실험 ID 50을 확인했다.
- NAS에서 공개 포트 없는 후보 컨테이너로 운영 설정과 실제 데이터를 사용하는 API 3건을 먼저 검증했다. 이 단계의 운영 원본 컨테이너는 유지했고 후보는 정리했다.
- 운영 교체 후 공개 요청을 보내고 같은 질문·응답과 MLflow trace를 재조회했다. trace readback을 위해 새로운 chat 요청을 만들지 않았다.
- 조류 DB 복사·마이그레이션·백필·벡터 갱신과 Neo4j/n8n 이동으로 확대하지 않았다. MLflow 실험·trace 저장은 이번 관측 기능의 의도된 쓰기다.
- 일반 Jenkins main 파이프라인 정의는 바꾸지 않았다. 이번 Replay와 기존 자동 배포 정의를 혼동하지 않도록 보존 여부를 확인했다.

---

## 3. 주요 구현 및 배포 자산

### 변경 범위와 파일

이번 작업은 앞선 TEST snapshot의 운영 배포이며 추가 질의 알고리즘 수정을 수행하지 않았다. 배포 helper는 별도 release-ops sidecar로 사용해 앱 234파일 snapshot 원본을 유지했다.

- `scripts/deploy_registry_prod.py` — tracing 옵션 3개의 atomic bundle 검증, 기존 tracking URI·인증 보존, 실패 시 env+image rollback을 지원하도록 변경했다.
- `tests/test_registry_prod_tracing.py` — 신규 mock 6개와 기존 10개를 합친 16개 검사로 helper 동작을 검증했다. 실제 운영 롤백을 실행했다는 의미는 아니다. 배포 대상은 234 release files이며 application files 112개·data files 46개를 포함한다. 후보에서 application source 112개 해시가 승인 소스와 일치했다.

증거는 `docs/verification/assets/2026-10-26-production-semantic-tracing/`에 저장했다.

| 파일 | 역할 |
| --- | --- |
| `approved-source.json`, `preflight-source-review.json` | 소스 SHA·파일별 manifest·미커밋 여부·독립 사전 점검 |
| `jenkins-pipeline-before.groovy`, `jenkins-replay.groovy` | 기존 정의와 일회성 snapshot 배포 경로 |
| `image-metadata.json`, `release-identity.json`, `production-release.json` | 빌드 provenance·digest·source·배포 검증 연결 |
| `nas-candidate.py`, `production-candidate.json` | 실제 후보 API·해시 확인·정리·운영 원본 유지 |
| `production-before.json`, `production-after.json` | 교체 전후 이미지·healthy·runtime |
| `test-before.json`, `test-after.json` | TEST 이미지·컨테이너 ID·시작 시각 동일 |
| `prod-experiment.json`, `prod-mlflow-probe.json` | 실험 50 생성 및 패키지·접속 사전 확인 |
| `public-production.cjs`, `public-production.json` | 실제 공개 API·page error 확인 |
| `production-traces.json`, `trace-response-verification.json` | 같은 요청의 root·태그·하위 span과 응답 readback |
| `jenkins-config-preservation.json` | 기존 정의·매개변수·job properties 보존 |
| `production-models.json` | 실제 모델·router 식별 설정 확인 |

### 최종 runtime

```text
ROBINGRAPH_DEPLOY_TARGET=prod
ROBINGRAPH_GRAPH_INTENT_MODE=active
ROBINGRAPH_GRAPH_INTERPRETER=semantic
ROBINGRAPH_MLFLOW_TRACING=true
MLFLOW_EXPERIMENT_ID=50
MLFLOW_EXPERIMENT_NAME=robingraph-prod
```

실행 모델 설정은 Gemini `gemini-3.5-flash-lite`, 시스템에서 배포 중인 Jina 호환 임베딩 모델 식별자 `jinaai/jina-embeddings-v3`, Jev `typesafe/jev-1.13`, intent router `jev`로 확인했다. 모델 식별값 확인을 모델 정확도 검증으로 보지 않는다. 인증 정보는 문서·영수증에 기록하지 않는다.

---

## 4. 검증 및 테스트 결과

### 자동화·빌드 검사

| 검사 | 실제 결과 | 검증 성격 |
| --- | --- | --- |
| Jenkins Python 전체 | 1,320 실행·1,280 통과·40 skip·0 실패, 24.948초 | 단위/fixture/회귀; 이번 Jenkins 실행 |
| 배포 helper | 16 mock 통과 | 운영 실제 교체 검사와 구분 |
| Node frontend | 322 통과·0 실패 | 프런트엔드 자동 검사 |
| AMD64 fixture smoke | 통과 | 운영 아키텍처 이미지 기동 검사 |
| NAS 후보 실제 API | 3/3 통과 | 실제 운영 설정·자료, response mocking false |
| 공개 운영 POST | 3/3 HTTP 200 | 실제 답변·되묻기·자료 부족 |
| 공개 운영 GET | 3/3 HTTP 200 | health·OpenAPI·국명 lineage |
| 공개 페이지 오류 | 0 | 물리 기기·접근성 종합 검증과 구분 |
| Production trace 대응 | 3/3 일치 | 실험 50·고유 trace 3개·추가 chat 요청 0 |

Python은 기존 unittest discover 검사로 실행했다. 40 skip은 pinned 원본 자료 부재 또는 전용/일회용 DB opt-in 미설정으로 실행하지 않은 검사이며 통과로 합산하지 않는다. 선행 TEST 작업의 25.338초와 이번 Jenkins의 24.948초를 서로 바꾸지 않는다.

### NAS 후보 검증 및 실패 이력

최종 `NAS-Agent-Check #8` 후보 검증은 기록형 형질 조회, 생물학적 부정 보류, 특정 식물 종 먹이 자료 부족을 확인했다. 세 요청 모두 HTTP 200·기대 계약 통과였고, 공개 포트 없이 실행했다. application hash 112개 일치, 후보 정리, 원래 운영 컨테이너 유지가 영수증에 남았다.

검증 과정의 초기 inventory 하네스 #3 실패 1건(embedded Python newline syntax error)과 구버전 후보 하네스 호환 결함으로 실패한 `NAS-Agent-Check #7` 이력을 보존한다. `candidate7-first-failure.json`의 실제 원인은 후보 생성 전 TypeError이며 운영 컨테이너는 유지됐다. stop을 호출했지만 최종 Jenkins 결과는 script exit 1의 FAILURE였고 ABORTED가 아니다. 최종 #8에서 하네스를 바로잡아 해결했으며 앱 소스를 바꾸거나 이전 실패를 성공으로 덮어쓰지 않았다. 이는 운영 앱 질의 결함이나 운영 롤백 성공을 뜻하지 않는다.

### 공개 운영 요청과 실제 trace

| 공개 요청 | HTTP / API 결과 | trace reason / stage |
| --- | --- | --- |
| 참새목 새 중 나무 열매를 먹는 새 | 200 / answer | none / none |
| 청둥오리와 비슷한 식생 | 200 / clarify; 먹이·식성과 서식 환경 중 선택 요청 | ambiguous_conditions / routing |
| 숲에 사는 새 중 직박구리와 같은 열매 | 200 / abstain; 특정 식물 종 자료 부족 | insufficient_data / retrieval |

첫 답변은 나무와 풀의 열매를 구분한 자료가 없다는 한계를 밝히고 열매 먹이 범주를 조회했다. “식생”은 임의로 식성으로 바꾸지 않고 의미를 되물었다. 특정 식물 종의 열매 공유는 근거가 없어 답변을 유보했다. 모든 HTTP 200을 종 목록 답변 성공으로 세지 않는다.

GET `/health`, `/openapi.json`, `/v1/taxa/lineage?name=청둥오리`는 모두 200이었다. 국명 lineage에서 학명 `Anas platyrhynchos` 해소를 확인했으며 이를 별도의 학명 직접 입력 검색 시험으로 과장하지 않는다.

[Production MLflow 실험 50](https://mlflow.dove-nest.com/#/experiments/50)의 고유 trace 3개에서 root 원문·기존 마스킹/길이 제한을 적용한 응답·최종 disposition/reason/stage 태그가 실제 HTTP와 일치했다. readback의 새 chat 요청은 0이다. 전체 원본 응답이 마스킹 없이 그대로 저장됐다는 뜻은 아니다.

관측된 span은 정상 답변의 `graph_intent.route`·`graph_intent.candidates`·`jina.embed`, 자료 부족의 `graph_intent.route`·`graph_intent.interpret`·`graph_intent.selection`이었다. 모호한 의미의 되묻기는 root만 관측됐다. 이번 세 요청에서 계획·감사 span 전체를 실행·검증했다고 주장하지 않는다.

### TEST 및 Jenkins 설정 보존

`test-before.json`과 `test-after.json`의 이미지·컨테이너 ID·시작 시각이 동일했다. TEST 재시작이나 DB 이동은 하지 않았다. `jenkins-config-preservation.json`에서 기존 pipeline definition·parameters·job properties가 모두 유지됨을 확인했다.

---

## 5. 배포 및 형상 관리

- **대상**: NAS Production, `RobinGraph-PROD #9 SUCCESS`; Jenkins duration 202,427ms.
- **최종 이미지**: `ghcr.io/evodmik/robingraph@sha256:851bc96d358374f0dce37fa95638e905d79845c5c036a44590b20c57ef22d659`.
- **소스 SHA256**: `6a95918a55332aa0195c07bf4e5a9c60a7cb006b67fd56d255d683f22c72c922`.
- **기준 Git revision**: `834c5353ca45f0640152ca4849548cd48818b266`; 미커밋 snapshot의 ancestry로만 사용.
- **이전 운영 이미지**: `ghcr.io/evodmik/robingraph@sha256:f000a7219d365cb69a33acde3bea11b57a5a8054af79db75a3832684c849b280`.
- **변경 전후**: healthy active/lexical·tracing false → healthy active/semantic·tracing true·실험 50.
- **Git**: commit·push·merge 없음. 배포 성공을 main 동기화 완료로 표시하지 않는다.
- **후속 배포 경로**: 일반 main 자동 파이프라인은 기존 lexical 설정을 유지한다. main 동기화 없이 향후 main 배포가 실행되면 이번 snapshot을 덮어쓸 수 있다. 현재 운영은 승인된 immutable snapshot으로 정상 유지 중이며, main 반영 및 영구 배포 설정 변경은 별도 승인 작업이다.

---

graphify 최종 갱신은 9,112 nodes·19,909 edges로 성공했고 배포 helper diff check도 통과했다. 임시 Jenkins 인증 파일은 삭제했다. 추가 앱 코드 수정은 없었고 위 배포 helper 변경은 앱 snapshot과 분리했다.

## 6. 한계 및 후속 과제

- 이 배포 작업은 완료했지만 RG-212는 진행 중이다. V2-07A 감사 오거절과 V2-10B 수치 경계 보류는 이번 작업에서 수정·재평가하지 않았다.
- 선행 TEST 노출 회귀 82/84·26/28군과 신규 8 최초 5/8→노출 8/8, 원 gold12의 작성 문제 2건을 보존한다. 공개 운영 3건은 새 독립 일반화 성능 점수가 아니다.
- 모델 계획의 조건 전체 누락을 감사 모델에 의존하는 한계와 모델 gold의 사람 검토 부재는 남는다.
- 운영 데이터가 TEST와 다를 수 있으므로 결과 행 수 동일성을 배포 조건으로 사용하지 않았다. 조류 DB 쓰기 명령은 수행하지 않았지만 전체 DB checksum 불변 감사는 하지 않았다.
- 공개 페이지 오류 0은 물리 모바일·Safari/Firefox·전체 키보드/반응형 검증을 대신하지 않는다.
- 일반 main 배포와 이번 미커밋 snapshot의 차이를 정리하는 후속 작업이 필요하다. 이번 운영 승인만으로 Git 작업 승인까지 확대하지 않는다.

---

## 관련 문서

- [[Home|🏠 홈으로]]
- [[Work/RobinGraph/index|RobinGraph 프로젝트 인덱스]]
- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 작업 백로그]]
- [[Work/RobinGraph/작업기록/2xx 검색·RAG·그래프 질의/2026-10-26-RG212-기록질의-공통보완-독립평가|선행 TEST 검증·최초 평가·잔여 한계]]
