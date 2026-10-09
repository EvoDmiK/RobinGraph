# IUCN 직접 평가 연동 조사와 토큰 접근 확인

## 배경과 목표

사용자는 AviList 분류를 유지하면서 보전 등급은 IUCN/BirdLife, 국내 이름은 국립생물자원관, 관찰 자료는 eBird 등으로 보완하는 방향에 동의했다. 이후 IUCN API 신청 거절 화면을 제공했지만 토큰은 생성되어 있다고 알렸다. 사용자가 기존 로컬 .env에 키를 저장한 뒤 실제 동작 확인을 요청했다.

이번 기록은 공식 API 계약과 출처 이용 조건 조사, 실제 인증 요청 결과를 구분한다. 새 보전 등급 연결 코드의 구현 완료 기록은 아니다.

## 공식 자료 조사

협업 검토 에이전트가 공식 IUCN Python/R SDK를 독립 확인했다.

- API v4 인증은 `Authorization: <token>` 형태다. 공식 SDK는 Bearer 접두사를 붙이지 않는다.
- SIS 조회 경로는 `taxa/sis/{id}`, 학명 조회는 `taxa/scientific_name`이다. 평가 목록에서 단일 최신 세계 평가를 선택한 뒤 `assessment/{id}` 상세 레코드를 확인해야 한다.
- 평가 ID, SIS ID, 종 학명·rank·분류강, 세계 평가 범위와 최신 여부, 공식 URL의 ID를 교차 검증해야 한다. 평가일과 발표 연도는 서로 다르다.
- 기존 AviList의 BirdLife 연결 등 종 범위 일치 근거가 없는 NE 종에는 동일 학명만으로 등급을 상속하지 않는다. Pica serica 및 Pica pica의 새로운 LC 연결 근거는 확인되지 않았다.
- BirdLife는 직접 웹 자동 수집을 제한한다. 데이터셋 다운로드나 웹 스크래핑으로 API 신청 거절을 우회하지 않았다.

공식 출처:

- [IUCN API](https://api.iucnredlist.org/)
- [공식 R SDK 인증](https://github.com/IUCN-UK/iucnredlist/blob/main/R/init_api.R)
- [공식 Python SDK 인증](https://github.com/IUCN-UK/iucnredlistpy/blob/main/src/iucnredlistpy/client.py)
- [공식 R SDK 사용 안내](https://iucn-uk.github.io/iucnredlist/)
- [BirdLife 분류 설명](https://datazone.birdlife.org/about-our-science/taxonomy)
- [BirdLife 이용 조건](https://datazone.birdlife.org/terms-and-conditions)

## 신청 화면과 실제 인증 검증

사용자가 제공한 화면에는 API 사용 신청이 거절되었다는 안내, 상업적 이용을 위한 IBAT 안내, 거절이 잘못되었다고 생각하면 IUCN에 연락하라는 안내가 있었다. 구체적인 거절 사유는 표시되지 않았으므로 상업적 이용으로 분류되었다고 단정하지 않는다.

실제 로컬 파일에는 안내했던 IUCN_API_TOKEN 대신 IUCN_API_KEY가 있었다. 진단 스크립트가 두 이름을 확인하도록 하여 사용자가 저장한 IUCN_API_KEY로 요청했다. 로컬 파일이나 키 값은 변경하지 않았다.

| 검증 | 실제 결과 |
| --- | --- |
| 로컬 키 변수 존재 및 값 있음 | 확인 |
| 실제 사용한 변수 이름 | IUCN_API_KEY |
| 요청 | GET https://api.iucnredlist.org/api/v4/information/api_version |
| 인증 방식 | 공식 SDK와 같은 Authorization 헤더 |
| HTTP 결과 | 401 |
| 응답 형식 | JSON 오류 응답 |
| 종별 평가 조회 | 인증 실패 후 미실행 |
| 직접 IUCN 평가 연결 성공 | 확인되지 않음 |

토큰 값을 출력하거나 저장하지 않았다. 인증 정보를 URL에 넣지 않았다. 리다이렉트는 따라가지 않도록 했다. 401 이후 다른 인증 방식으로 반복 시도하거나 권한을 우회하지 않았다.

401은 서버가 이 요청의 인증을 받아들이지 않았다는 결과다. 키 오입력, 비활성 상태, 신청 거절과의 연관 등 구체적인 원인은 이 진단만으로 확정할 수 없다. 토큰이 생성되었다는 사실도 실제 조회 권한을 증명하지 않는다.

## 다른 출처 후보

두 번째 협업 에이전트는 NIBR 및 eBird의 공식 연결 경로와 개별 자료 이용 조건을 조사했다. 현재 정책을 만족하는 후보로 Cornell이 GBIF에 제공하는 EOD를 확인했다. 부모 에이전트도 아래 공식 데이터셋 메타데이터를 실제 조회해 title, license, DOI를 재확인했다.

- datasetKey: `4fa7b334-ce0d-4e88-aaae-2e0c138d049e`
- title: EOD – eBird Observation Dataset
- license: CC BY 4.0
- DOI: 10.15468/aomfnb
- [공식 GBIF 메타데이터](https://api.gbif.org/v1/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e)

EOD는 관찰 자료 후보이며 보전 등급을 대체하는 평가 자료가 아니다. 실제 관찰 레코드 적재, AviList와의 종 범위 매핑, API 연결은 이번에 실행하지 않았다. NIBR은 개별 목록 파일의 이용 조건을 확인해야 하며, 기관 홈페이지의 표시를 모든 파일의 이용 허락으로 간주하지 않는다.

## 변경·검증·배포 상태와 후속 사항

이번 변경 파일은 이 작업 문서뿐이다. 새 IUCN 어댑터, 국명 연동, 관찰 자료 연결은 아직 구현하지 않았다. 테스트 서버에는 앞서 배포한 출처 검증 및 NE 연결 확인 필요 표시가 유지되며, 이번 인증 진단으로 서버나 DB를 변경하지 않았다.

실행한 검증은 로컬 환경변수 존재 확인과 실제 공식 API 인증 요청, 공식 EOD 메타데이터 조회다. 새 단위 테스트 또는 전체 회귀 테스트는 실행하지 않았다. 코드 변경이 없으므로 이번 문서 작업에서 graphify AST 갱신은 해당하지 않는다. API 승인 또는 유효한 접근권한이 확인된 뒤 직접 평가 조회와 연결 구현을 재개해야 한다.

인증 정보와 사용자 신청 화면 원본은 저장소에 포함하지 않았다. Obsidian에는 중복 기록하지 않았으므로 문서 간 대조는 해당하지 않는다. 문서 커밋은 Git 이력에서 확인할 수 있다.
