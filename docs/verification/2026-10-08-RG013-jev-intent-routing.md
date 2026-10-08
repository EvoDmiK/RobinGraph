# RG-013 — Jev 질문 의도 분석 구현·검증 기록

## 배경·목표와 확인한 원인

“청둥오리 아종 알려줘”, “흰뺨검둥오리 아종 알려줘”가 자동 분류에서 막히는 문제를 해결한다. 기존 규칙에는 아종 목록 요청이 없고, 임베딩 라우터의 capability는 분류·관찰·근거뿐이다. 분류를 profile로 바꾸는 것만으로는 전체 질문이 이름으로 넘어가므로 이름 구간 추출과 실제 아종 핸들러 연결이 함께 필요했다.

사용자는 `thejevai.com/settings`에서 키를 발급했다. 초기 smoke의 TypeSafe 직접 주소 401은 제공자 불일치였으며, 해당 제공자 주소와 `typesafe/jev-1.13`로 HTTP 200을 확인했다. 실제 응답은 `code=0 → data.result.answers.intent`이고, 기본 Python User-Agent에서는 403/error1010이 발생했다. 서버 클라이언트는 고유 User-Agent와 실제 응답 래퍼를 사용한다. 인증 값은 이 기록에 포함하지 않는다.

## 협업·변경 파일·구현

Orca run `run_8bdb7fd51302`에서 역할을 나눴다. Codex가 구현·API 실행·회귀·배포를 담당하고, Claude가 120문항 정답표를 작성했다(워커 자기 보고 모델 `claude-sonnet-5-5`; 런타임 모델 필드는 미제공). Antigravity가 제공자 문서·응답 계약·인증 리다이렉트·확률 검증·불확실/장애 분리와 구현을 읽기 전용으로 검토했다. Antigravity의 실제 모델명은 확인하지 못했다. Claude task `task_cdef8bdada28`, Antigravity task `task_8380e4f86d01`은 성공 정산 후 해제했다. 독립 검토는 유료 호출·DB·브라우저 테스트를 대신하지 않는다.

| 파일 | 최종 변경 내용 |
|---|---|
| `src/robingraph/api/jev_router.py` | 서버 HTTP 클라이언트, 설정·호환 키 변수·롤백 선택, Choice/확률 검증, 제한된 HTTP 재시도, 비밀 비노출, MLflow span |
| `src/robingraph/api/question_entities.py` | 원문 이름 구간 추출, 접속사·다중 학명 거절, 기존 검토 통칭 대조 |
| `src/robingraph/api/app.py` | 명시/규칙 우선, Jev 세부 의도 연결, 불확실 확인 질문·장애 대체, 필터 일치, 아종 부모/릴리스 대조와 응답 |
| `src/robingraph/cli.py` | Neo4j 서버 시작 시 설정된 Jev 주입 |
| `src/robingraph/api/static/chat.js` | 아종 응답을 즉시 펼쳐 표시, 기존 안전한 출처·카드 재사용, 중복 목록 HTTP 제거 |
| `.env.example`, `.env.nas.example` | 키·모델·timeout·threshold·router 선택 예시 |
| `tests/test_jev_router.py`, `tests/frontend/chat_ui.test.js` | 실제 응답 형식 모의 검증, 오류/불확실/필터/회귀, 즉시 표시·부모/분류판 불일치 거절 |
| `tests/fixtures/jev_intent_eval.json`, `scripts/evaluate_jev_intents.py` | 120문항, calibration/heldout 분리, opt-in 실제 API 비교 평가 |
| `docs/jev-intent-routing.md`, 이 기록·JSON 첨부 | 설정·계약·검증 범위·한계와 실제 결과 |

명시적 모드와 기존 확실한 규칙은 기존 결과를 유지하며 Jev를 호출하지 않는다. 추가 자동 경로만 13개 의도를 판단한다. 아종 목록은 `selected_intent=profile`, `route_method=jev`, `question_answer.topic=subspecies`, `result.subspecies`로 기존 profile 계약에 추가했다. 낮은 확신도·불확실·원문 이름 추출 실패는 조회를 강제하지 않는다. 관찰 날짜·장소는 자유형 모델 출력으로 생성하지 않고 기존 검증 필터를 요구한다. 답변 생성 모델과 RG-014/RG-016은 변경하지 않는다.

## 테스트와 실제 API 평가

모의·회귀와 실제 외부 검증을 분리한다.

- 최초 전체 Python: 599개 발견, 557개 통과, 42개 건너뜀, 실패 0. DB integration opt-in 및 optional MLflow 테스트를 포함한 건너뜀은 실제 DB/API 검증 완료로 세지 않는다.
- 최종 전체 Python: 600개 발견, 558개 통과, 42개 건너뜀, 실패 0. 프런트엔드 전체 134개 통과, 실패·건너뜀 0.
- Jev 모의/계약 최초 13개 및 통칭 호환성 보완 후 14개 통과. HTTP 401/403/429/503/redirect, timeout/transport, 깨진 JSON·oversize·확률·알 수 없는 라벨·필터 충돌·확신도·키 없음·롤백을 확인했다. 모의 응답의 두 신고 질문 결과는 실제 종 데이터 검증이 아니다.
- 실제 Jev 의도 평가: calibration 64문항(규칙 우회 21, 유료 API 43) 이후 threshold 0.85/0.80/0.20을 유지하고 heldout 56문항(규칙 우회 18, 유료 API 38)을 실행했다. 총 120문항 중 실제 API 요청 81회, 응답 크레딧 합 81, input 67,041/output 10,321 tokens. API 재시도 0회. 낮은 확신도·uncertain은 오류가 아니라 확인 질문 판단이다.

| 세트·경로 | 의도 정확도 | macro-F1 | 자동 분류율 | 확신한 오분류율 | 확인 질문율 |
|---|---:|---:|---:|---:|---:|
| calibration 기존 | 37.50% | 0.4044 | 32.81% | 3.13% | 67.19% |
| calibration Jev 결합 | 95.31% | 0.9613 | 90.63% | 3.13% | 9.38% |
| heldout 기존 | 41.07% | 0.4741 | 32.14% | 1.79% | 67.86% |
| heldout Jev 결합 | 92.86% | 0.9471 | 87.50% | 3.57% | 12.50% |

**임베딩 복구 후 재검증**: 최초 비교에서는 임베딩 단독 요청이 로컬 EmbeddingTransportError, NAS 기존 컨테이너 ConnectionRefusedError로 실패했다. 이후 사용자 확인 요청 시 로컬 300ms/NAS 395ms로 실제 512차원 벡터 반환을 확인했다. 저장된 Jev 판단을 그대로 재사용하고 정상 임베딩으로 calibration/heldout 기존 경로만 다시 실행했다(추가 Jev 호출 0). 결과는 위 표와 동일했다. 실제 capability 코사인 진단 4문항의 최고 점수는 약 0.028/0.206/0.336/0.183으로 기존 confidence 임계값 0.70을 넘지 못했다. 현재 기본 설정의 규칙+정상 임베딩 라우터와의 비교이며, 임계값을 별도로 조정한 최적 임베딩 기준선이나 모든 모델의 일반적 우열을 뜻하지 않는다. 최초 장애 당시 결과도 JSON의 previous_baseline과 previous_baseline_embedding_probe에 보존했다. 서버 복구 작업 자체는 수행하지 않았다.

Jev 호출 지연은 calibration p50 1,806/p95 2,309ms, heldout p50 1,803/p95 1,982ms다. 4개 동시 요청의 클라이언트 관측치이며 전체 채팅·DB·카드 지연과 다르다. 제공자는 실제 모델 버전과 USD 비용을 응답에 보내지 않아 요청 모델과 크레딧만 확인했다. 두 신고 문항의 의도는 각각 subspecies로 맞았다.

정답표는 Claude 단일 모델 주석이며 사람이 확정한 정답표가 아니다. API 실행 전에 Codex가 모호한 통칭 4개와 도도새 1개의 정답을 의도/종 해소 분리에 맞춰 정정했다. 최종 평가 후 prompt·threshold는 조정하지 않았다. heldout 오차 4개: 아존 오타와 같은 속 표현 2개는 낮은 확신도 확인 질문, T. rex 아종 요청은 Jev subspecies 오분류, Canis lupus 분류는 기존 결정 규칙 taxonomy였다. calibration 고양이·용도 기존 규칙이 생태 의도로 인식한다. 의도 분류가 종 존재나 답변 가능성을 보장하지 않으며 실제 분류판 해소 실패는 미응답으로 처리한다.

세부 의도별 정확도·F1·문항별 판단·확신도·사용량은 다음에 보존한다.

- [조정용 평가](assets/2026-10-08-RG013-calibration.json)
- [최종 평가](assets/2026-10-08-RG013-heldout.json)

## 배포·커밋과 후속 실제 검증

1차 구현 커밋 `162e5408ef403ba06a8f7577d48622191bc0087d`를 NAS TEST에 배포했다. 1차 릴리스 `/home/kimdove/RobinGraph-rg013-162e540`, 이미지 `robingraph-api:test-rg013-162e540`, 공개 주소 `https://robingraph-test.dove-nest.com`이다. 비밀을 제외한 커밋 아카이브의 SHA-256·MANIFEST를 확인하고 기존 TEST 환경 파일을 NAS 내부에서 복사한 뒤 Jev 키만 암호화 SSH로 주입했다. 환경 파일은 0600이다. 기존 TEST 이미지 `robingraph-api:test-rg010-cd46b33`는 되돌리기 기준으로 보존한다. 일반 통칭 응답의 기존 동작을 유지하는 보완과 복구 후 평가 재사용 러너를 `42f49275e783dd3eda1dde92d01fc0e109de077e`에 반영했다. 최종 릴리스는 `/home/kimdove/RobinGraph-rg013-42f4927`, 이미지 `robingraph-api:test-rg013-42f4927`이다. 실제 컨테이너의 이미지·OCI revision·healthy 상태가 해당 커밋과 일치함을 확인했다. PROD의 컨테이너·환경 파일·DB는 변경하지 않았다.

실제 공개 HTTP 9개 요청이 통과했다: 신고 질문 2개, 기존 규칙/명시 profile 2개, 필터 충돌, 지시대명사, 복합 의도, 필터 없는 관찰, 자료 없는 이름. 청둥오리는 정확한 부모 Anas platyrhynchos의 아종 2개, 흰뺨검둥오리는 정확한 부모 Anas zonorhyncha와 연결된 아종 0개로 확인됐다. 이는 활성 AviList v2025b 결과이며 다른 분류판에도 같다고 단정하지 않는다. 부모 식별자·분류판·개념집합을 실제 프로필과 대조했다. 실제 DB를 읽는 배포 API 검증이며 DB 적재나 분류판 변경은 하지 않았다.

실제 Chrome 390/900px에서 두 질문을 textarea에 입력하고 보내기를 눌러 전체 채팅 흐름 4개를 통과했다. 아종 목록은 추가 클릭 없이 열리고 청둥오리 2개/흰뺨검둥오리 0개가 표시됐다. JS 오류·가로 넘침 0. 응답 가로채기·컴포넌트 주입 없이 실제 공개 JS/CSS/API/DB/Jev를 사용했다.

- [공개 채팅 HTTP 검증](assets/2026-10-08-RG013-public-chat.json)
- [브라우저 검증](assets/2026-10-08-RG013-browser.json)
- [복구된 임베딩 진단](assets/2026-10-08-RG013-embedding-recovery.json)

실제 MLflow `robingraph-test`에서 연결된 root/child 관계의 Jev LLM span 3개를 확인했다. 요청 모델, 1회 시도, 성공 판정, 1크레딧, 토큰 usage가 저장됐고 Jev 인증 값은 span inputs/outputs/attributes에 없었다. 제공자가 실행 모델을 에코하지 않아 reported_model은 null이다. [MLflow 확인](assets/2026-10-08-RG013-mlflow.json). 최초 검증기의 `get_experiment_by_name`은 설치된 mlflow-tracing 전용 패키지에 없어 실패했고, 지원되는 `set_experiment`를 사용해 재확인했다. 검증 도구의 오류를 API 장애로 기록하지 않았다.

최종 이미지 `42f4927`에서 공개 채팅 HTTP 9개와 브라우저 실제 입력·전송 4개를 다시 실행해 모두 통과했다. 최종 이미지에서도 MLflow Jev span 3개를 다시 확인했다. 해당 JSON에 tested_revision을 명시했다. 구현 커밋 `162e540`, 호환성 보완·평가 재확인 커밋 `42f4927`은 origin/dev에 push 완료(`04389fc..42f4927`). 이번 후속 기록·최종 증거 갱신은 별도 문서 커밋으로 보존한다.

**RG-013 구현·NAS TEST 적용 완료**로 기록한다. 평가 정답표의 한계와 일반 영어 통칭·자동 관찰 필터·임베딩 임계값 최적화 미포함은 아래에 남긴다. Obsidian 상세 기록과 백로그·프로젝트 index에도 같은 핵심 결과를 기록한다. PROD 배포는 수행하지 않았다.

## 남은 한계·후속 사항

- 복구된 임베딩 서비스로 기존 기본 설정 비교를 재실행했다. 임베딩 임계값 최적화·다른 프로토타입의 기준선은 평가하지 않았다.
- 의도 점수는 원문 이름 구간 해소·실제 DB 응답·화면 성공률이 아니다. 이름을 안전하게 뽑지 못하는 표현은 확인 질문으로 남긴다. 일반 영어 통칭·자연어 관찰 필터의 자동 해소는 추가하지 않았다.
- 공급자는 모델 실제 버전과 USD 비용을 반환하지 않는다. 크레딧 외 금액을 추정해 확정하지 않는다.
- 출처 없는 자료나 다른 활성 분류판 자료로 답변하지 않는다. 아종 번역 확대와 보류 작업 재개는 별도 지시 대상이다.
- `graphify update .` AST 갱신을 실행했다. SQL 추출기는 미설치 경고가 있으며 해당 그래프가 SQL 관계 검증을 대신하지 않는다.
