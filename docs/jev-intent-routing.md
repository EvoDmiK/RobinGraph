# Jev 질문 의도 라우팅 (RG-013)

## 사용 목적과 설정

Jev는 답변 생성이나 종 이름의 존재 여부 판정을 하지 않고 조회 의도만 선택한다. 사용자가 `https://thejevai.com/settings`에서 발급한 키에 맞춰 [해당 제공자의 API 문서](https://thejevai.com/docs)를 사용한다. TypeSafe 직접 API와 별개인 제공자이므로 주소와 모델을 혼용하지 않는다.

서버의 저장소 루트 `.env` 또는 NAS TEST 릴리스의 `.env.nas.test`에 다음 설정을 둔다. 실제 키는 버전 관리·브라우저·작업 문서에 넣지 않는다.

```dotenv
JEV_API_KEY=
ROBINGRAPH_INTENT_ROUTER=auto
ROBINGRAPH_JEV_ENDPOINT=https://thejevai.com/v1/systemone
ROBINGRAPH_JEV_MODEL=typesafe/jev-1.13
ROBINGRAPH_JEV_TIMEOUT_SECONDS=8
ROBINGRAPH_JEV_MAX_RETRIES=1
ROBINGRAPH_JEV_CONFIDENCE_THRESHOLD=0.85
ROBINGRAPH_JEV_PROBABILITY_THRESHOLD=0.80
ROBINGRAPH_JEV_MARGIN_THRESHOLD=0.20
```

초기 테스트에서 안내했던 `TYPESAFE_API_KEY`도 같은 제공자용 호환 변수로 읽는다. 두 변수가 모두 있으면 `JEV_API_KEY`가 우선한다. 기존 키의 이름을 바꿀 필요는 없다. CLI는 시작할 때 현재 작업 디렉터리의 `.env`를 읽으며, 셸에 이미 설정된 값이 우선한다. 기존 환경 로더의 `KEY=VALUE` 형식에 맞춰 값에 따옴표를 붙이지 않는다. NAS Compose는 선택된 환경 파일을 컨테이너에 주입한다. 키가 없는 `auto`는 기존 임베딩 라우터를 사용한다. `jev`는 유효한 키 설정을 요구하고, `semantic`은 키가 있어도 기존 라우터로 되돌린다. 변경 후 서버를 재시작한다.

## 요청·검증·대체 동작

`POST /v1/systemone`에 Bearer 헤더와 `state/model/questions`를 전송한다. Choice의 13개 라벨은 일반 종 정보, 아종 목록, 분류 계통, 관찰, 근거, 먹이, 서식, 활동, 외관, 관련 종, 서식 환경 공유 종, 먹이 공유 종, 불확실이다. 공급자의 실제 HTTP 응답은 `code=0`, `data.result.answers.intent`, `data.result.usage`, `data.creditsUsed` 형식이었다. 문서에 보이는 간략 예시보다 실제 래퍼가 한 단계 깊다.

명시적 모드와 이미 인식되는 규칙 질문은 Jev를 호출하지 않는다. 나머지 자동 질문만 Jev를 호출한다. Choice의 타입·라벨·모든 라벨의 확률·합계·최대 확률 선택 일치·유한 수치를 검사한다. confidence, 선택 확률, 2위와의 차이 모두 임계값을 넘겨야 조회한다. 이 값들은 운영 안전 기준이며 실제 정답 확률이 보장된다는 뜻은 아니다. 64개 조정용 문항 평가 후 기본값을 유지한 채 별도 56개 최종 문항을 평가했다.

불확실·낮은 확신도는 확인 질문을 유지하며 임베딩 결과로 덮어쓰지 않는다. 인증·전송·HTTP·비정상 응답 오류는 기존 임베딩 라우터로 대체하고, 그것도 실패하면 확인 질문을 한다. 429/502/503/504만 0.25초 뒤 최대 한 번 재시도한다. 이미 처리됐을 수 있는 타임아웃 요청은 재전송하지 않는다. 기본 요청 타임아웃은 8초이며 재시도 HTTP 오류 시 최대 두 번의 요청이 가능하다. 리다이렉트는 Bearer 유출을 막기 위해 따르지 않는다. 응답 본문은 256KiB로 제한한다. 오류 응답 본문과 인증 헤더는 로그·추적에 기록하지 않는다.

## 이름·필터·조회 결과

모델이 자유형 종 이름·장소·날짜를 생성하게 하지 않는다. 이름은 질문 원문의 제한된 구간에서 추출하고, 기존 활성 분류판 및 검토된 통칭 관계 조회기가 존재·모호함을 판단한다. 이름을 추출하지 못하면 전체 문장을 종 이름으로 넘기지 않고 명확한 이름 또는 필터를 요청한다. 오타를 임의 교정하지 않는다. 일반 영어 통칭의 임의 해소는 추가하지 않았으며, 학명과 기존 검토 통칭을 우선한다. 질문 이름과 명시 필터가 충돌하면 조회하지 않는다.

아종 의도는 API의 상위 `selected_intent=profile`, `route_method=jev`와 세부 `question_answer.topic=subspecies`로 표현한다. 기존 `/v1/taxa/subspecies`와 같은 조회기를 사용하고 부모 식별자·분류판·개념집합을 부모 프로필과 대조한다. `result.subspecies`의 목록을 화면에 즉시 펼쳐 보여주고 중복 목록 요청을 만들지 않는다. 아종이 0개이면 활성 분류판에 연결된 아종이 없음을 알린다. 자료가 없다는 사실과 아종 조회 장애를 구분한다. 200개 표시 제한과 `has_more` 안내는 기존 조회기의 계약을 따른다. 종 자료와 아종 자료의 출처는 기존 컴포넌트에 보존한다.

먹이·서식·활동·외관·관련 종은 기존 출처 기반 답변기를 사용한다. 관찰 의도는 분류할 수 있지만 자연어 날짜·장소를 임의 필터로 변환하지 않으므로 검증된 명시 필터가 필요하다. 근거 의도는 기존 hybrid 검색·대체 경고를 유지한다. 답변 생성 모델·HippoRAG·MLflow 결과별 필터(RG-016)는 이 작업의 범위가 아니다.

## 추적과 검증

`jev_router.classify` MLflow 자식 span에 요청 모델, 공급자가 응답한 모델(있을 때만), 라벨·확신도·확률, 지연, 시도 수, 실패 유형, 사용 토큰·크레딧을 남긴다. 현재 제공자는 모델 버전을 응답에 보내지 않아 실제 실행 버전은 확인할 수 없으며 요청 모델을 실제 버전으로 가장하지 않는다. 공급자가 USD 비용을 보내지 않으므로 비용은 응답의 크레딧 사용량으로 기록한다.

- 단위·장애·회귀: `python -m unittest discover -s tests`
- 화면 회귀: `node --test tests/frontend/*.test.js`
- 실제 API 평가(유료 호출): `python scripts/evaluate_jev_intents.py --live --split calibration --output /tmp/jev-calibration.json`, 이후 설정을 고정하고 `--split heldout` 실행.

임베딩만 다시 비교하려면 `--reuse-jev 저장된평가.json --split heldout --output /tmp/baseline-recheck.json`을 사용한다. 문항과 정답의 일치를 검사하고 이전 Jev 결과를 재사용하므로 Jev 추가 과금은 없다.

평가표는 Claude가 작성한 120문항으로, 사람이 확정한 정답표가 아니다. Codex가 API 평가 전에 이름의 모호함·자료 존재와 의도 분류를 분리하도록 5개 정답을 정정했다. 질문 의도 점수는 실제 종 해소·DB 정답·전체 채팅 성공률을 뜻하지 않는다. 실제 실행 수치·배포·협업 결과는 [검증 기록](verification/2026-10-08-RG013-jev-intent-routing.md)에 별도로 기록한다.
## 채팅의 추가 자료 후속 로딩

채팅 화면은 `/v1/chat` 요청에 `defer_enrichment: true`를 보낸다. NAS 런타임은 같은 활성 분류판·종 식별·특성·보전 상태 검증을 사용하는 기본 프로필 흐름을 먼저 실행하며, 사진·외부 설명·일반 소개의 비슷한 새 추천은 기다리지 않는다. 빠른 프로필의 `enrichment_pending: true`를 확인한 화면은 **더 알아보기** 버튼을 표시한다. 버튼을 누르기 전에는 추가 조회를 시작하지 않는다. 클릭하면 기존 `/v1/taxa/profile?name=<학명>`과 일반 소개에 한해 `/v1/taxa/similar?name=<학명>`를 병렬 호출하며, 버튼을 비활성화해 중복 요청을 막는다. 아종 목록은 첫 답변에 포함되며, 집중 질문에서는 불필요한 추천 자동 조회를 하지 않는다.

후속 결과는 최초 프로필과 `taxon_id`, `concept_set_id`, `taxonomy_release`가 모두 일치할 때만 반영한다. 첫 답변을 유지하면서 사진 슬롯·추가 설명·추천을 갱신하고 제공처 경고와 개별 실패를 표시한다. 새 질문·비교 시작 시 이미 진행 중이던 추가 조회를 취소하고 늦은 결과를 반영하지 않는다. 아직 누르지 않은 이전 답변의 버튼은 해당 종 문맥으로 계속 사용할 수 있다. 대화 삭제는 미시작 버튼까지 무효화한다. 외관을 직접 묻는 질문은 외관 설명 자체가 필수 답변이므로 기존 전체 조회를 사용한다.

API의 `defer_enrichment` 기본값은 `false`다. 기존 직접 API 호출은 전체 프로필·추천 응답 동작을 유지하며, 기본 프로필 handler를 주입하지 않은 애플리케이션도 기존 경로를 사용한다. 사진·설명 생성은 버튼 클릭 후 HTTP 요청에서 실행된다. 누르지 않은 답변의 추가 조회 비용은 발생하지 않으며, 클릭한 조회의 외부 작업 시간·비용은 남는다. 실제 클릭 전후 검증과 NAS TEST 배포는 [버튼 조회 검증 기록](verification/2026-10-08-RG013-learn-more.md)을 따른다.
