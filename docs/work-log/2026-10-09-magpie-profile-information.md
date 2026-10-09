# 까치 설명·생태·표본 체중 보완과 LC 표시 정리 — 2026-10-09

## 요청 배경과 목표

한국어 `까치`를 Pica serica로 연결한 뒤 실제 대화에서 설명과 생태 정보가 비어 있었다. 사용자는 TEST 화면의 `멸종위기 등급 미확인` 표시도 제보했고, 이후 `임시 보정` 문구를 지워 달라고 요청했다. 종 이름과 검색 구분을 유지하면서 첫 답변과 도감 카드에 출처가 있는 정보를 제공하고, 배지는 `관심대상 (LC)`로 표시하는 것이 목표다.

## 원인과 확인 근거

- 변경 전 실제 `POST /v1/chat`에 `까치에 대해 알고 싶어`, `intent=auto`, `defer_discovery=true`를 보냈다. Pica serica로 올바르게 연결됐지만 형질 목록이 비어 있었고, 외관·재미있는 사실의 외부 제공처 조회 경고가 있었다. 학명 외의 기본 설명도 대부분 비어 있었다. 이전 이름·등급 검증은 이 실제 대화의 정보 충실도까지 확인하지 못했다.
- 당시 서버의 실제 대화 응답에는 이미 LC가 포함돼 있었다. 새 브라우저에서 같은 질문을 보냈을 때 LC를 표시했다. 반면 구형 `fd8e959`의 JavaScript에 같은 새 응답을 넣으면 새 `manual_override` 계약을 인식하지 못해 `미확인` 표시를 재현할 수 있었다. 사용자 브라우저의 실제 탭·캐시를 직접 조사한 것은 아니므로 오래 열린 탭이나 이전 응답이 원인이라고 확정하지 않는다.
- 새 HTML은 버전 해시가 붙은 JavaScript URL을 사용하고 페이지 자체는 재검증한다. 기존 열린 탭과 과거 답변은 배포만으로 다시 렌더링되지 않으므로 새로고침 후 다시 질문하는 방식으로 확인해야 한다.
- 앞선 전체 자료 검토에서 AviList NE는 11,131종 중 808종(약 7.3%)이었다. 평가자료 연결 또는 분류 범위의 차이도 포함돼 실제 IUCN 미평가 종 수로 해석하지 않는다. 이번 변경은 이 전체 집합을 일괄 LC로 바꾸지 않는다.

## 사용한 자료와 범위

### 외관·생활·먹이

[Hong Kong Bird Watching Society의 Oriental Magpie 종 계정](https://avifauna.hkbws.org.hk/species/0260/033600)은 학명을 Pica serica로 명시한다. Pang, Leven & Carey (2023), *The Avifauna of Hong Kong*, version 1.0이며 페이지 최종 갱신일은 2024-01-10이다.

검은색·흰색 깃털, 긴 꼬리와 광택, 몸길이 약 46~50cm, 마을·농경지·개방된 습지, 지상 먹이 탐색, 잡식 등 사실을 한국어로 독자 요약했다. 공동 잠자리와 인공 구조물 둥지 관찰은 홍콩 기록이라는 범위를 본문에도 명시한다. 출처의 문장이나 사진을 복제하지 않으며, 이를 공개 재배포 라이선스가 있는 원문으로 취급하지 않는다.

이 종 계정은 Pica serica의 보전 상태를 IUCN LC로 소개한다. 답변 출처에 참고 링크를 추가했으나 개별 IUCN 평가 ID·평가 원문·평가 종 범위의 독립 검증을 완료한 것으로 기록하지 않는다.

### 체중

[Chae et al. (2025), Scientific Reports](https://www.nature.com/articles/s41598-025-13894-4), DOI `10.1038/s41598-025-13894-4`의 Supplementary Information 2에서 Pica serica의 `sheet1`·`weight` 열을 집계했다. 논문과 보충 자료는 CC BY 4.0이다.

- 범위: 한국 5개 지역, 2008년 3월, 2년차 이상 115개체.
- 합계 25,373.2g / 115 = 220.636521739…g, 소수 둘째 자리 반올림 **220.64g**.
- 표본 최소 167.9g, 최대 257.2g; 수컷 62, 암컷 53개체.
- 이 값은 해당 조사 **표본 평균**이며 종 전체의 고정 평균이나 일반적인 체중 범위로 단정하지 않는다.
- [원본 보충 파일](../verification/assets/2026-10-09-pica-serica-mass-source.xlsx), 80,195바이트, SHA-256 `32b8d981cf09216ff9b5ae2a009ecb559e7c30ca8a722b2b831068c2be34bf3d`.
- [집계 결과](../verification/assets/2026-10-09-pica-serica-mass-analysis.json)와 `scripts/verify_reviewed_magpie_mass.py`로 파일 체크섬·대상 115개체·계산을 재현할 수 있다. 소스 변경 시 자동으로 다른 값을 적용하지 않고 검토를 요구한다.

## 변경 전후와 구현 파일

- `src/robingraph/retrieval/reviewed_magpie.py`: 활성 AviList v2025b·개념집합·Pica serica 종 ID·학명·rank가 모두 일치할 때만 누락된 4개 형질과 외관·재미있는 사실을 제공한다. 기존 DB 형질은 우선 사용한다. Pica pica나 다른 릴리스에 상속하지 않는다.
- `src/robingraph/retrieval/species_profile.py`: 첫 기본 응답과 전체 프로필 모두 검토한 사실을 병합한다. 이 종의 설명은 외부 제공처의 성공에 의존하지 않는다. 체중 설명은 `연구 표본 평균`으로 표시하고 출처 범위를 전달한다.
- `src/robingraph/retrieval/conservation.py`: 표시 설명과 출처 이름에서 요청한 문구를 제거했다. LC 표시와 원자료 NE, `manual_override`, `independently_verified=false`는 보존한다.
- `src/robingraph/api/static/chat.js`: 새 출처 계약을 인식하고 배지는 `관심대상 (LC)`로 표시한다. 답변 출처에는 원자료 상태와 HKBWS 참고 링크를 남긴다. 앞·뒷면 체중 라벨은 `체중 · 표본 평균`, 출처에는 조사 범위·115개체·라이선스를 표시한다. 다른 체중의 g/kg 변환은 유지한다.
- `tests/test_reviewed_magpie.py`, `tests/frontend/chat_ui.test.js`: 종·릴리스 경계, DB 우선, 제공처 실패, 표본 집계 재현, 양면 라벨과 문구 제거를 검증한다.
- `README.md`: 현재 LC 표시와 새 자료·표본 평균·재현 방법을 설명한다.

변경 후 `까치`는 계속 **까치 / Oriental magpie / Pica serica**로 검색된다. Pica pica는 **Eurasian magpie**로 구분한다. 실제 첫 답변의 기본 정보 2개, 외관 2개, 생활과 먹이 3개, 재미있는 사실 2개가 채워진다.

## 협업 검토

- `conservation_quality_review`: 출처의 Pica serica 범위·라이선스와 코드 적용 경계를 독립 검토했다. 보충 파일 체크섬과 115개체 계산도 독립 재현했고, 종 전체 평균으로 읽히지 않도록 카드 라벨에 표본 평균을 명시할 것을 권고했다. 차단 결함은 발견하지 않았다.
- `quality_audit_report`: 구형 JavaScript의 LC 미확인 재현과 새 브라우저 실제 대화를 확인했다. 화면 문구·양면 표본 평균·출처 범위와 회귀 테스트를 구현했다.
- 주 작업자: 사실 보완·표본 재현 스크립트·백엔드 통합·최종 검증·NAS 배포·문서 동기화를 수행했다.

## 실제 검증 결과

| 구분 | 실행 범위와 결과 |
|---|---|
| Python 전체 | `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -v`: 683개 중 **648 통과, 35 건너뜀, 실패 0**. fixture·모의 제공처 계약 검증이 포함되며 전체를 실 DB 검증으로 부르지 않는다. |
| 건너뜀 | 전용·폐기 가능한 Neo4j/PostgreSQL opt-in 설정이 없는 33개, 이전 아종 자료의 외부 고정 원본이 없는 2개. 이번 API 검증으로 이 테스트들이 통과한 것은 아니다. |
| 화면 전체 | `node --test tests/frontend/*.test.js`: **262 통과, 실패·취소·건너뜀 0**. DOM 모의 환경 회귀 검증이다. |
| 공개 원본 집계 | 새 테스트가 저장된 실제 XLSX를 재현 스크립트로 실행해 표본 수·체중·체크섬과 실행 코드 값을 대조했다. 외부 API를 모의로 만든 데이터가 아니다. |
| 실제 NAS API | 네 종 프로필, 한국어 `까치` 조회, 실제 자연어 `POST /v1/chat` 모두 HTTP 200. 까치 형질 4개·모든 설명 섹션의 항목·LC·경고 없음 확인. Pica pica 및 다른 NE 종의 등급, 청둥오리의 공개 평가목록 LC는 유지. |
| 실제 브라우저 | Chrome/Playwright, PC 1280×900와 모바일 크기 390×844에서 실제 질문 전송·실제 API 응답을 사용했다. 응답 모의나 프로필 삽입 없음. LC 배지, 설명, 양면 표본 평균, 출처, 요청 문구 제거, 화면 맞춤, 키보드 양면 전환 통과. JavaScript 예외 0. 물리 모바일 기기·터치 동작을 별도로 시험한 것은 아니다. |
| 배포 코드 | 공개 `chat.js`가 커밋 코드와 바이트 단위로 일치. SHA-256 `ece7704ffaff56592a969ecbb0917c40ff65923410687f4dafa24386a81afa2c`. |
| 그래프·정적 검사 | `git diff --check` 통과. `graphify update .` 완료: 4,164노드·8,685엣지·247커뮤니티. SQL 파서 의존성 부재로 SQL 4파일 추출 경고가 있었으며 의미 확장 API는 사용하지 않았다. |

[실제 API 검증 기록](../verification/assets/2026-10-09-magpie-profile-verification.json), [실제 브라우저 검증 기록](../verification/assets/2026-10-09-magpie-profile-actual-browser-verification.json), [모바일 앞면](../verification/assets/2026-10-09-magpie-profile-actual-chat-card-390.png), [PC 뒷면](../verification/assets/2026-10-09-magpie-profile-actual-chat-back-1280.png)을 보존한다.

## 배포·커밋

- 구현 커밋: `60ce6afd639c8c9c04fea3cd3caaadc9e3e8c9d6`.
- 다른 작업자의 문서 변경을 합친 커밋: `e312351` (`origin/main` 병합). 런타임 변경은 추가되지 않았다. 코드·병합 커밋은 main/dev에 반영하고 atomic push를 완료했다. 이 작업 기록과 검증 산출물은 후속 문서 커밋으로 관리한다.
- TEST 이미지: `robingraph-api:test-magpie-facts-60ce6af`, healthy. 이미지 revision 라벨도 구현 커밋과 일치한다. 최초 빌드에서 이전 환경파일의 revision이 남은 것을 발견해 `ROBINGRAPH_VCS_REF`를 수정하고 같은 코드를 재빌드·배포했다.
- 릴리스 묶음 SHA-256: `270de116c27852cd52015de1cafcfada8fcf1bf7c5590734a57e09d14cf737d0`. 전송 후 묶음과 내부 파일 manifest 검증을 수행했다.
- NAS 디렉터리: `/home/kimdove/RobinGraph-magpie-facts-60ce6af`. 비밀 환경파일은 NAS 안에서 복사했고 저장소·릴리스 묶음·이 문서에 포함하지 않았다.
- PROD는 `robingraph-api:prod-e90ff85`, healthy. 컨테이너 ID `71d938bb700e8b75ccc8f470357b38c4f96f03d67da30736d70fe769ec4423cf`가 배포 전후 동일하다. DB 적재·수정은 수행하지 않았다.
- 복구가 필요하면 이전 TEST 이미지 `robingraph-api:test-magpie-22ff90b`를 같은 TEST 전용 배포 스크립트의 rollback 대상으로 사용할 수 있다.

## 남은 한계와 후속 사항

까치의 먹이 구성 비율·먹이 활동 위치 비율은 출처가 없어 채우지 않았다. 도넛 영역은 같은 카드 형식을 유지하며 자료 없음으로 표시한다. 형질 보완은 프로필 응답 계층의 고정 사실이므로 그래프에 형질을 적재한 것은 아니며, 관계 후보 선정용 그래프의 생태 정보가 함께 보완된 것으로 주장하지 않는다.

HKBWS의 IUCN LC 소개와 앱 LC 표시는 확인했지만, 최신 개별 IUCN 평가 원문의 범위·연도·ID를 검증한 상태는 아니다. 이후 정식 평가 연결 시 원자료와 표시 이력을 유지하면서 별도 검토한다. Pica pica의 등급을 이 변경에서 자동으로 LC로 바꾸지 않았다.

`/health`의 `taxonomy_release`에는 기존 fixture 기본값이 남아 있다. 활성 분류는 실제 프로필의 `lineage`에서 AviList v2025b로 확인했으며 health 필드를 근거로 분류 릴리스를 판단하지 않았다. 이번 요청 범위에서 health 필드를 수정하지 않았다.
