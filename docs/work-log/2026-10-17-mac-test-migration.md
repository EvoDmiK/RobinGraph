# TEST 앱을 M4 16GB로 이전 — 2026-10-17

## 요청 배경과 목표

사용자가 TEST 앱을 NAS 대신 M4 16GB Mac mini에 배치하도록 승인했다. TEST PostgreSQL은 NAS, TEST Neo4j·n8n은 32GB Mac에 있다는 사용자 설명을 기준으로 기존 연결을 유지하며 앱·빌드 위치와 TEST 도메인 upstream만 이전했다. DB 복제나 마이그레이션을 하지 않는다.

## 확인한 실제 상태와 변경 전후

현재 작업 호스트가 Mac16,10·RAM 17,179,869,184bytes(16GiB), 192.168.219.97임을 sysctl/hostname/ipconfig로 확인했다. Docker context는 OrbStack이다. 기존 로컬 TEST는 test-local 이미지로 2026-10-14부터 실행 중이었다. NAS에는 최신 RG-406 고급 옵션 이동 이미지 test-rg406-8ffeb7734750가 실행 중이었다.

| 항목 | 이전 | 이후 |
|---|---|---|
| 공식 TEST 앱 | NAS robingraph-api-test | M4 16GB robingraph-api-test |
| 로컬 이전 TEST | 과거 test-local 이미지 | 최신 snapshot ARM64 빌드로 교체 |
| TEST Neo4j | bolt://192.168.219.98:7687 | 동일 |
| TEST PostgreSQL | NAS192.168.219.99:5433 / robingraph_test | 동일 |
| TEST n8n | 32GB Mac이라는 사용자 확인 | 변경/재시작하지 않음, 이번 작업에서 별도 실측하지 않음 |
| TEST 프록시 host20 | robingraph-api-test:8000(NAS Docker) | 192.168.219.97:8000 |
| NAS TEST 앱 | 실행 | 정지, 컨테이너·이미지 롤백용 보존 |
| Production | NAS 기존 앱 | ID·시작·이미지 및 프록시 설정 동일 |

실제 등록된 도메인은 **https://robingraph-test.dove-nest.com**이다. 과거 대화의 robin-test.dove-nest.com은 이번 확인에서 HTTPS525를 반환했으며 해당 도메인을 새로 등록하거나 인증서를 변경하지 않았다.

## 배포 구현과 파일

NAS 최종 배포와 같은 runtime snapshot `8ffeb7734750752ac20356128be9f0c36dd68954b2528a78c081d6cb85447807`을 사용했다. 패키지141파일 SHA-256을 확인하고 macOS에서 linux/arm64로 빌드했다. 실행 이미지 src/scripts101파일 해시가 manifest와 모두 일치했다. NAS amd64와 Mac arm64는 빌드 이미지 ID가 달라도 동일 앱 소스다.

- release: `/Users/kimdove/robingraph-test/releases/robingraph-rg406-8ffeb7734750`
- current symlink: `/Users/kimdove/robingraph-test/current`
- 관리: `/Users/kimdove/robingraph-test/manage.sh {start|status|stop|verify}`. Docker context=orbstack 및 TEST 프로젝트/컨테이너를 명시한다.
- private env: release `.env.nas.test`, mode0600. NAS의 기존 TEST 설정을 비공개 복사하고 image 태그만 변경했다. DB URI·DB명·사용자·비밀번호 동일을 값 출력 없이 비교했다.
- runtime override `compose.mac-test.yml`: 127.0.0.1:8000 및 192.168.219.97:8000만 publish한다. 기존 read-only·cap_drop·no-new-privileges·unless-stopped 설정을 유지한다.
- image: `robingraph-api:test-mac-8ffeb7734750`
- image ID: `sha256:564d2428d0cde4860fad4443fe8a8ab02faa84441c97e679287d6baf7e2261b4`
- Mac container: `5bbabf4ee079f0f4d3c1ecf5fbb9a9aad0fe4ed0197af20f06a8e67da8c0fc67`
- 실제 재시작 후 시작: `2026-10-17T10:07:54.908021322Z`, healthy.

실제 빌드는 release의 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh build`를 로컬에서 실행했고, 시작은 관리 스크립트의 명시적 mac override compose up으로 수행했다. 앱 변경이나 새 기능 추가는 없다.

저장소 문서는 `docs/deployment-profile.md`에 현재 배치를 우선 표시했고, AGENTS.md Codex 절에 이후 TEST 배포 위치·관리 경로·NAS TEST 정지 상태를 명시했다. 공통 지침을 네 워크트리에 같은 문구로 반영했다. 환경 비밀값과 NPM DB 백업은 저장소에 넣지 않았다.

## TEST 도메인 전환과 보존

NAS Nginx Proxy Manager의 로컬 관리 모델로 host20을 확인했다. 먼저 NPM SQLite 일관 백업과 TEST 설정 파일, 전체 proxy_host 행 해시 및 운영 host18 설정 해시를 NAS 사용자 홈 `robingraph-test-migration-20261017`에 비공개 보존했다. DB 백업과 TEST 원문 설정은 mode0600이며 인증 메타데이터가 포함될 수 있어 출력/배포하지 않는다.

NAS 호스트와 NPM 컨테이너 양쪽에서 새 Mac:8000 health200·target=test를 확인한 뒤, NPM의 기존 내부 관리 경로를 사용해 host20의 forward_host만 192.168.219.97로 바꾸고 원래 http/8000을 유지했다. NPM이 설정 생성·nginx reload를 수행했으며 컨테이너 재시작은 하지 않았다. 다른21개 프록시 행은 바이트 정규화 해시가 같고 운영 host18 nginx 파일도 동일했다. 기존 인증서·access list·보안 옵션을 변경하지 않았다.

공개 HTTPS Chromium 검증을 모두 마친 뒤 `docker stop robingraph-api-test`를 **NAS에서** 실행했다. NAS TEST 정지 후 공개 health200을 다시 확인해 요청이 Mac으로 전달됨을 입증했다. 이어 Mac TEST 컨테이너 docker restart 후 healthy·공개 health·계약 검증 통과를 확인했다.

## 실제 실행 검증

증거 디렉터리: `docs/verification/assets/2026-10-17-mac-test-migration/`.

| 검사 | 실제 결과 | 산출물 |
|---|---|---|
| runtime/package/source | package141 및 실행 src/scripts101파일 일치, arm64 | mac-release.json, build.log |
| API 계약 | manage.sh verify, health/openapi/실제 lineage, 배포 전후 및 재시작 후 passed | api-contract.json, api-contract-after-restart.json |
| 실제 TEST API/DB/provider | 기존 verify_http.py를 localhost8000에 실행,12사례 통과(8POST·4GET) | local-http.json |
| NAS→Mac | NAS 호스트 및 NPM컨테이너에서 health200·target=test | 실행 출력 및 이 기록 |
| 공개 HTTPS 실제 브라우저 | Chromium1280/390/320,각3POST=9회와 단독 /birds 통과, pageerror0. 고급 옵션을 펼치고 국내/국외/미확인·Kea표시·초안유지·이전대화정리 확인 | browser_live.js, browser-live.json, 화면3개 |
| TEST 위치 전환 | NAS TEST exited 후 공개HTTPS200, Mac 컨테이너 실제 restart 후 healthy·계약 통과 | final-state.json, public-health.json |
| 설정/운영 보존 | TEST DB연결 동일, 다른프록시21행·운영프록시파일·운영컨테이너동일 | before.json, final-state.json 및 실제 해시 assert |
| 자원/시작 설정 | 검사 시 앱287.8MiB·CPU0.25%(한 시점), OrbStack VM8192MiB·로그인자동시작true, macOS sleep0·정전복구autorestart1, restart policy unless-stopped | 실행 출력; 부하 시험 아님 |

API12사례는 청둥오리 국내answer/국외abstain, Kea국외answer/국내abstain, 타조미확인answer/국외abstain, Saxicola maurus국내answer, 관련16·유사3·생태6 모두 국내, Kea프로필, Jev요청오타 정상 프로필이다. 실제 외부 DB/provider를 사용했으며 fixture/mock가 아니다. 현재 데이터/후보 범위가 확장된 것은 아니다.

이번 작업은 앱 소스 변경이 없어 Python/Node 전체 단위 검사를 반복하지 않았다. 별도 DB쓰기·인덱스생성·수집/n8n 실행은 없다. 공개 브라우저는 실제 Chromium viewport 에뮬레이션이며 물리 모바일·Safari/Firefox는 미검증이다. graphify는 문서/검증 자산 갱신 후 AST update만 수행했다.

## 실패·한계·보안 후속

- NPM origin의 14443에 LAN 직접 HTTPS 연결은 로컬 신뢰 체인 오류로 curl60/Chromium ERR_CERT_AUTHORITY_INVALID였다. 인증 검사를 끄거나 인증서를 바꾸지 않고, 정상 공개 도메인의 신뢰 가능한 HTTPS로 검증하여 통과했다.
- Python urllib 기본 요청은 공개 health403을 받아 초기 재시작 검사 루프가 실패했다. 같은 시점 로컬/LAN/curl 공개 요청은200이며 Chromium도 통과했다. curl 기반 재시작 확인 및 실제 컨테이너 내부 계약 검증으로 구분했다. WAF/클라이언트 정책을 변경하지 않았다.
- 프록시 갱신의 반환 meta에 Cloudflare 인증 값이 포함되어 도구 출력에 노출되는 실수가 있었다. 값은 이 문서·검증 자산에 복사하지 않았다. 사용자에게 알렸고 토큰 교체가 후속으로 필요하다. 운영 인증 영향 가능성 때문에 임의 토큰 폐기/교체나 운영 설정 변경은 하지 않았다.
- 맥의 물리 재부팅·로그인 전 서버 복구는 실제 수행하지 않았다. OrbStack 로그인 자동시작과 Docker restart policy는 확인했지만 로그인 이전 자동 서비스 실행을 입증하지 않는다. DHCP주소 고정 여부도 확인하지 않았다. Mac의 LAN IP가 바뀌면 bind와 TEST upstream을 함께 조정해야 한다.
- 앱 메모리 수치는 단일 관측이며 동시부하/장기 soak 시험은 아니다. 빌드/브라우저/에이전트를 함께 사용할 때 VM메모리 여유를 확인해야 한다.
- Production container `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`, 시작 `2026-10-10T06:07:33.413088244Z`, image `robingraph-api:prod-approved-ui-0681747`는 유지했다. 운영 DB/앱 재시작/이미지교체 없음. Git commit/push/병합 없음.

## 관리와 롤백

일반 상태/검증은 16GB Mac에서 `/Users/kimdove/robingraph-test/manage.sh status` 및 `verify`를 사용한다. 다음 앱 배포는 새 검증 snapshot을 release로 빌드하고 current를 전환해 같은 TEST 앱을 갱신한다. 이전 NAS 배포 스크립트를 일반 TEST 반영 경로로 사용하지 않는다.

Mac 장애 시 보존된 NAS TEST 컨테이너를 NAS에서 시작하고 health를 확인한 뒤, NPM host20 upstream을 원래 http://robingraph-api-test:8000으로 복구하면 된다. 이는 TEST 롤백 절차이며 실제 롤백은 수행하지 않았다. 인증서/나머지프록시/운영 앱을 바꾸지 않는다.

Writer에게 확정된 이 기술 기록과 산출물을 전달해 자기 워크트리 기록·Obsidian 상세/관련 백로그의 최신 TEST위치를 갱신하고 재조회하도록 맡긴다. 전달 완료와 Writer의 저장 완료는 구분해 보고한다. 이번 작업용 SSH control master를 검증 종료 후 종료했다. 비밀값 할당·Cloudflare 토큰 접두어가 검증 자산에 없는지 확인했고 네 워크트리 AGENTS.md 해시 일치와 git diff --check 통과를 확인했다.
