# 일반 종 소개에도 그래프 유사종 TOP-3 — NAS TEST 검증

사용자 요청에 따라 Claude와 GPT(Codex)가 Ponytail full로 기존 흐름을 재사용했다. Claude는 `ChatSpeciesResult.similar_species`와 일반 프로필 응답 연결을, GPT는 기존 `buildRelatedExplorer`의 미리 받은 데이터·자동 펼침 연결을 맡았다. 새 유사도 알고리즘·컴포넌트·의존성을 추가하지 않았다.

## 구현과 검증

- 종 소개 요약·전체 설명·카드 표시 버튼을 유지하면서 설명창에서 TOP-3 점수·근거·출처를 함께 표시한다.
- 일반 프로필에서 허용된 유사종 handler를 호출하고 taxon ID·개념집합·분류판을 대조한다. 실패·버전 불일치는 유사종만 생략한다. 아종에는 이 종 유사도 조회를 적용하지 않는다.
- 미리 받은 TOP-3 데이터를 기존 화면에 전달하므로 중복 관련 종 요청이 없다. 기존 질문별 응답과 새 말풍선 비교는 유지한다.
- Python 530개 성공(32개 skip), 프런트엔드 124개 통과.
- 실제 NAS `멧비둘기에 대해 알고싶어.`: 일반 소개와 Sunda Collared Dove 90점, 염주비둘기 90점, Philippine Collared Dove 90점 동시 제공, 7.647초.
- 실제 NAS `청둥오리에 대해 알고 싶어.`: 일반 소개와 고방오리·Andean Teal·White-cheeked Pintail 각 100점 동시 제공, 7.327초.
- 기존 `왜가리는 무엇을 먹고 사니?`의 출처 있는 먹이 구성비 정상, 4.839초.
- Chromium 390px·1280px: 전체 소개, 카드 버튼, 자동 펼쳐진 TOP-3 3개, 근거 링크, 별도 비교 말풍선·두 카드 확인. 가로 넘침 및 pageerror 없음.
- graphify AST update 완료.

## 배포

코드 `214ad6605201d73cf6424b01a8241a065d5a8cfa`를 dev에 push하고 커밋 기반 패키지를 NAS에 전송했다. 아카이브·파일별 체크섬을 검증하고 기존 TEST 설정으로 빌드·배포했다.

- 이미지 `robingraph-api:test-intro-214ad66`
- 경로 `/home/kimdove/RobinGraph-intro-214ad66`
- 패키지 SHA-256 `a2526c5ea5b3b0b3ba7669e3beeecf260c6f290e6b10dafc4a1f85045707a79e`
- `deploy`, `verify` 성공, TEST healthy·Neo4j 모드.
- https://robingraph-test.dove-nest.com/chat

협업 Run `run_413e1acddaa7`: Claude·GPT 두 Task 모두 succeeded. Claude 작업자는 released, GPT 작업자는 release 호출에서 Orca가 user_takeover를 감지해 retained로 사용자에게 넘겼다. 추가 회수 대기 작업자는 없다.
