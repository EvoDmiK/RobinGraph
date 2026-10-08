# 근연종 탐색의 검증된 한국어 이름 우선 적용

작성일: 2026-10-08. 사용자 요청: 근연종 검색에도 생태 검색처럼 한국어 이름을 우선 적용한다. 대상은 같은 속·과 탐색 목록의 선택·정렬과 표시 일관성이다. 비교 후보 TOP 3의 가중 점수 순서는 유지한다.

## 배경·원인·근거

기존 화면의 `speciesLabel`과 서버의 `with_korean_display_name`은 이미 검증 국명→원자료 영어 이름→학명 순으로 표시했다. 그러나 `related_species.py`의 Neo4j 쿼리는 원본 그래프의 한국어 `VernacularName`으로 먼저 정렬하고 `LIMIT 13`을 적용했다. 이후 Python이 12개를 선택하고 검증되지 않은 국명을 제거해 영어로 바꿨다. 그 결과 영어 이름 사이에 한국어 이름이 섞이고, 제한 밖의 검증 국명 후보를 되살릴 수 없었다.

실제 수정 전 NAS TEST의 청둥오리 같은 속 목록은 `고방오리, Laysan Duck, Red-billed Teal, 쇠오리, 흰뺨검둥오리, African Black Duck, 미국오리, …`였다. 곤줄박이 같은 과 목록도 `노랑배박새, Crested Tit, 쇠박새, 진박새, Eurasian Blue Tit, …`처럼 섞였다. 공개 API를 실제 Chrome에서 호출해 응답을 확보했으며 HTTP 모의 결과가 아니다.

## 변경 전후 동작·구현 파일

- `src/robingraph/retrieval/related_species.py`: 생태 검색과 동일하게 기존 검증 국명표를 Cypher 매개변수로 전달한다. 종 ID로 참조표를 찾고 학명·원자료 영어 이름까지 정확히 일치할 때만 국명을 사용한다. 이 대조와 한국어 이름 우선 정렬을 `LIMIT 13` 전에 적용한다. 한국어 이름이 없는 후보는 영어 이름, 영어도 없으면 학명으로 정렬하며 종 ID로 동률을 해소한다.
- `_parse_lineage_items`의 기존 국명 재검증을 유지해 응답에 국명 출처 URL·`source-reference` 상태를 제공한다. 같은 속 12개·같은 과의 다른 속 12개, 추가 후보 유무, 대상 종 제외, 허용된 분류판·개념집합·관계 범위와 출처 검증은 유지한다.
- `tests/test_related_species.py`: 검증표 전달, 국명 없는 그래프의 검증 국명 표시, 학명 또는 영어 이름 불일치 시 영어 대체, 기존 오류·범위 계약을 검증한다.
- `tests/test_related_species_integration.py`: UUID로 격리한 실제 Neo4j 분류·후보를 생성해 `LIMIT 13` 이전 선택을 검증하고 `finally`에서 테스트 노드를 삭제한다. 검증 국명표는 합성 테스트 입력이며 Cypher 실행은 실제 DB다.
- `docs/korean-display-names.md`: 같은 속·과의 국명 우선 선택과 TOP 3 점수 순위 유지 정책을 명시했다.

한국어 이름이 없는 후보의 임의 번역이나 국명 사전 확장은 하지 않았다. 원본 DB 이름·검색 별칭·Jev 프롬프트·점수 계산·화면 구조·환경 변수는 변경 대상이 아니다.

## 협업

주 담당이 원인 확인·서버 수정·모의 테스트·실제 NAS 전후 비교·배포·문서화를 담당했다. `progressive_review`가 독립 검토로 제한 이후 재정렬만으로 누락을 복구할 수 없음을 확인하고, 실제 Neo4j의 13개 제한 경계·잘못된 이름 참조·개념집합/관계 범위·같은 속 제외 통합 테스트를 작성했다. 실제 DB 전체 실행은 주 담당이 수행했다. 최종 커밋 독립 검토에서 배포 차단 문제가 없었으며 협업 담당의 별도 관련 단위 테스트 5개도 모두 통과했다.

## 검증 방법·실제 결과

- 관련 서버 모의 테스트: `python -m unittest tests.test_related_species tests.test_ecological_relations tests.test_similar_species -v` **19개 통과, 실패 0, 건너뛰기 0**. 국명 참조·영어 대체·기존 점수 순서·오류 처리를 확인했다. DB/API를 실제 호출한 결과는 아니다.
- 전체 Python: `/tmp/rg010-venv/bin/python /tmp/rg013-integration-rerun.py` **610개 통과, 실패 0, 건너뛰기 0**, 37.678초. `.env`에서 DB 설정만 테스트 프로세스에 주입하고 실제 전용 PostgreSQL/Neo4j 통합 검증을 활성화했다. 외부 모델 API 키는 이 실행에 주입하지 않아 Jev 호출은 모의 검증이다. UUID 임시 PostgreSQL 스키마는 실행 후 삭제했다.
- 새 실제 Neo4j 테스트: 14개 미검증 raw 국명 후보와 뒤쪽의 검증 국명 후보를 생성해 **검증 국명 1개 + 영어 후보 12개**가 실제 `LIMIT 13` 결과에 포함되는 것을 확인했다. 학명/영어 이름 불일치 2개는 국명 없이 영어를 유지한다. 대상 종·다른 개념집합·다른 개념집합 관계는 제외되고, 같은 과 탐색은 같은 속을 제외한 다른 속 후보 1개만 반환했다. UUID 테스트 노드는 `finally`에서 정리했다.
- 전체 프런트엔드: `node --test tests/frontend/*.test.js` **164개 통과, 실패 0, 건너뛰기 0**. 기존 국명 표시·비교 카드·분류 화면 회귀를 검증했다. 브라우저/DB 모의 테스트다.
- `graphify update .` AST 갱신 성공. 기존 SQL 추출 의존성 누락·기호 없는 파일·커뮤니티 이름 갱신 안내가 있었으며 실행 실패는 없었다.

실제 NAS TEST 공개 주소에서 Chrome/Playwright로 `/v1/taxa/related`·`/v1/taxa/similar`를 청둥오리·곤줄박이에 대해 호출하고, 수정 전 응답과 비교했다. HTTP를 모의하지 않았다.

| 실제 확인 | 결과 |
|---|---|
| 청둥오리 같은 속 | 고방오리→미국오리→쇠오리→흰뺨검둥오리→African Black Duck 등 영어 후보. 검증 국명 4개가 영어보다 먼저 표시된다. |
| 청둥오리 같은 과의 다른 속 | 가창오리·개리·검둥오리 등 검증 국명 후보가 앞의 12개를 차지하며 `has_more=true`다. |
| 곤줄박이 같은 과 | 노랑배박새·노랑배진박새·박새·북방쇠박새·쇠박새·작은노랑배박새·진박새·흰머리유리박새 다음 영어 후보. |
| 곤줄박이 같은 속 | 검증 국명 후보가 없어 기존 영어 이름 4개와 `has_more=false`를 유지한다. |
| TOP 3 동일성 | 두 종 모두 후보 ID·순위·점수가 수정 전과 정확히 일치한다. 청둥오리 100/98.28/96.55점, 곤줄박이 100/98.57/97.14점. |
| 실제 채팅 화면 | ‘청둥오리와 같은 속의 새는?’에서 국명 우선 목록과 학명·영어 대체 표시를 확인했다. 390px/900px, 가로 넘침·JS 예외 0건. |

국명이 있는 모든 실제 API 후보의 `source-reference` 상태와 HTTPS 출처, 12개 이하 표시도 확인했다. 화면은 데스크톱 Chrome의 모바일/데스크톱 폭 검증이며 실제 모바일 기기 시험은 아니다. 긴 내부 목록의 스크린샷에는 일부만 보이므로 전체 목록은 API·DOM을 대조했다.

브라우저 검증 스크립트 초안은 접근 이름의 정확 일치와 영어 대소문자 가정 때문에 assertion이 실패했다. 실제 응답은 정상으로 확인했고, 렌더링 완료를 기다리는 DOM 선택과 대소문자에 무관한 이름 대조로 수정한 최종 실행이 통과했다. 제품 코드를 이 검증 스크립트에 맞춰 바꾸지는 않았다.

- [실제 API·화면 검증 JSON](assets/2026-10-08-RG013-korean-related-browser.json)
- [390px 화면](assets/2026-10-08-RG013-korean-related-390.png) / [900px 화면](assets/2026-10-08-RG013-korean-related-900.png)

## 커밋·배포

- 소스 커밋: `cb1cafb74f8d3790d6014edf1f5e26fbf0761f95` (`fix: prioritize verified Korean names before related species limits`), `origin/dev` push 완료. 상세 검증 문서·화면 자료는 후속 문서 커밋에 포함한다.
- NAS TEST 이미지: `robingraph-api:test-rg013-cb1cafb`, 컨테이너: `robingraph-api-test`, 릴리스: `/home/kimdove/RobinGraph-rg013-cb1cafb`.
- Git 런타임 허용 목록 아카이브 SHA256: `d2b0fde19d8768d72bb77c2da1d76bf208908407c3f394cf854393b3d76ddeba`. 원격 아카이브와 manifest의 파일별 해시를 검증했다. 기존 NAS 환경 파일을 NAS 내부에서 복사해 이미지·VCS revision만 변경했고 인증 정보는 문서나 Git에 포함하지 않았다.
- `deploy_nas.sh deploy`·`verify` 성공. Docker inspect에서 위 이미지·OCI revision 일치와 `healthy`, 공개 `/health`의 `status=ok`·`deployment_target=test`를 확인했다. health의 기존 fixture 분류판 문자열을 활성 분류판 검증으로 대신하지 않는다.
- [실제 NAS TEST](https://robingraph-test.dove-nest.com/chat). PROD 변경 없음. 직전 이미지 `robingraph-api:test-rg013-ddba07e`를 보존했다.

## 한계·후속 사항

검증표에 없는 종은 영어 이름을 유지한다. 특히 청둥오리 TOP 3의 Indian Spot-billed Duck·Philippine Duck은 검증 국명이 없으므로 영어를 유지하고, 국명이 있는 흰뺨검둥오리는 한국어로 표시한다. 한국어 이름이 있다는 이유로 비교 점수가 낮은 후보를 올리지 않는다. 외부 국명 원자료를 이번에 새로 수집·검증하지 않았으며 기존 검증표를 사용한다. 다른 백로그·보류 작업은 진행하지 않는다.
