# TEST 먹이 표시 실제 브라우저 확인

- 대상: https://robingraph-test.dove-nest.com/chat, 2026-10-29
- 실제 Chromium headless shell CDP, 실제 TEST `/v1/chat` 응답. 모의 데이터 사용 없음.
- 청둥오리 질문 → 실제 도감 팝업 열기 → Enter로 뒷면 → 항목·비율 펼침.
- 390×844 모바일 에뮬레이션 및 1280×800 데스크톱, 각 7개 검증 통과(14/14). 물리 기기·Safari·Firefox 미실행.
- 두 화면 공통: 곤충 40%, 기타 고기 0%, 온혈 척추동물 0%, 변온 척추동물 10% 표시. 원자료 괄호 suffix 없음, dialog viewport내, document 가로 overflow 없음.
- TEST health GET 200, deployment_target=test. 실제 static/chat.js 새 두 라벨 존재 및 옛 곤충 원자료 문자열 부재 확인.
- 초기 harness 시도는 페이지 초기화 전에 입력값을 설정하여 앱 초기화가 이를 지운 탓에 미전송 timeout. 초기화 대기를 추가하고 form requestSubmit을 사용한 최종 실행은 정상 통과. 앱 오류로 집계하지 않음.
- 첫 박새 popup 시도에서는 개별 항목 원자료 suffix 부재 및 layout 확인, 다만 diet_distribution 자료 자체가 없어 구성표 검증 대상으로 부적합. 최종 증거는 청둥오리로 기록.
- 최종 결과 browser-results.json, screenshots/diet-390.png 및 diet-1280.png. signed token·원본 API 전체 응답 저장 없음.
- 검증용 Chromium 종료 및 port19237 관련 프로세스 종료 확인.
- 이 작업에서 앱 코드 변경·배포·Git 작업은 수행하지 않음. 실제 TEST 데이터 출처/비율의 사실성 전체 감사는 범위 밖.
