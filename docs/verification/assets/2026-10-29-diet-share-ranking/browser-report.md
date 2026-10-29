# TEST 브라우저 검증

2026-10-29 실제 TEST /chat, Chromium headless CDP 모바일 390×844. API 모의 응답 사용 없음.

- 청둥오리 실제 질문 → 도감 팝업 → Enter 뒷면 → 항목·비율 펼침: 7개 확인 모두 통과. `고기 · 온혈동물`, `고기 · 변온동물`, `기타 고기`, `곤충` 표시 및 원자료 suffix 부재, 가로 넘침 없음.
- `까마귀과 중 열매를 먹는 새는?` 실제 질문: graph_query 응답 20종, API 학명 순서와 DOM 학명 순서 동일. 기존 paths text에서 추출한 열매 비율이 모두 내림차순. 문서 가로 넘침 없음.
- 결과 popup-browser-results.json, ranking-browser-results.json, screenshots/diet-390.png, screenshots/fruit-ranking-390.png. 토큰과 전체 응답은 저장하지 않음.
- 물리 모바일·Safari·Firefox는 미검증. 비율 데이터의 원자료 사실성 전체 감사는 범위 밖. 이 검증에서 배포·Git 작업 없음.
