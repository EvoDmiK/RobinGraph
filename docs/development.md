# 개발환경과 fixture 재현성

Windows PowerShell, macOS, Linux는 같은 명령과 같은 의존성 잠금 파일을 사용한다.

## 최초 설치와 검증

[uv 공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)에 따라 uv를 설치한다. CI는 uv `0.11.26`을 사용하며 Python은 `.python-version`의 `3.12.13`으로 고정한다. `uv sync`가 필요한 Python과 `.venv`를 자동 준비한다.

```sh
uv sync --locked --extra test
uv run --locked robingraph validate-fixture
uv run --locked robingraph evaluate-fixture
uv run --locked --extra test python -m unittest discover -s tests -v
```

`--locked`는 pyproject와 lock이 어긋났을 때 자동 갱신하지 않고 실패한다. 테스트용 `httpx2`도 lock에 포함된다. 의도적으로 의존성을 바꿀 때만 `uv lock`을 실행하고 `pyproject.toml`과 `uv.lock` 변경을 함께 검토한다.

## 줄바꿈과 manifest

`data/eval/**`는 `.gitattributes`로 LF를 강제한다. 생성기도 UTF-8, LF를 명시하므로 Windows의 `core.autocrlf=true`에서도 새 체크아웃과 재생성 결과가 동일하다. manifest의 SHA-256은 원시 바이트를 검사하며 줄바꿈 차이를 무시하지 않는다.

이 수정 이전부터 사용하던 Windows 작업공간에는 CRLF 파일이 남아 있을 수 있다. **fixture를 직접 수정하지 않은 작업공간**에서는 고정 생성기로 v1 파일을 다시 만든 뒤 검증한다.

```sh
uv run --locked python scripts/generate_eval_fixture.py
uv run --locked robingraph validate-fixture
git diff --exit-code -- data/eval/v1
```

fixture를 수정 중이라면 먼저 변경 내용을 보존하고 검토한다. 생성기는 대상 파일을 덮어쓴다. 별도 위치에서 결과만 확인할 때는 `--output`을 사용한다.

```sh
uv run --locked python scripts/generate_eval_fixture.py --output .venv/fixture-preview
```

fixture 내용의 의도적인 변경은 생성기 수정 → 재생성 → manifest·gold 기대값 검토 → 전체 테스트 순으로 진행한다. 검증 실패를 숨기기 위해 manifest 해시만 갱신하지 않는다.

## 자동 테스트

`.github/workflows/ci.yml`은 push와 pull request에서 Windows, Ubuntu, macOS를 검사한다. Windows job은 체크아웃 전에 `core.autocrlf=true`를 설정한다. 커밋된 fixture 검증과 15개 gold 평가를 먼저 실행하고 전체 테스트를 수행한다.

재현성 테스트는 임시 디렉터리에서 생성기를 실행해 커밋된 파일·manifest와 바이트 단위로 비교한다. 별도의 손상 시험은 내용 추가와 CRLF 변환 모두 무결성 검사에서 거부되는지 확인한다. 실제 체크아웃을 먼저 검증하므로 테스트가 파일을 재생성해 오류를 감추지 않는다.

CI 설정은 [uv의 GitHub Actions 안내](https://docs.astral.sh/uv/guides/integration/github/)를 따른다. 로컬 테스트 통과와 원격 GitHub Actions 실행 결과는 구분해 기록한다.

## Neo4j 통합 테스트

일반 테스트는 DB 없이 실행한다. CI의 별도 `neo4j` job은 Neo4j Community `2026.07.1` 컨테이너를 매번 새로 만들고, 인증을 켠 상태에서 `ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1`로 실제 DB 테스트를 활성화한다. 이 job의 비밀번호는 일회용 테스트용 값이며 운영 자격 증명을 사용하지 않는다.

로컬에서는 테스트용 Neo4j에 연결한 뒤 같은 전체 테스트 명령을 실행한다. 테스트는 fixture를 적재하므로 별도 테스트 인스턴스를 사용한다.

PowerShell 예시:

```powershell
$env:ROBINGRAPH_NEO4J_INTEGRATION_TESTS = "1"
$env:NEO4J_URI = "bolt://127.0.0.1:17687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "fixture-test-only"
$env:NEO4J_DATABASE = "neo4j"
uv run --locked --extra test python -m unittest discover -s tests -v
```

macOS/Linux 예시:

```sh
ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1 \
NEO4J_URI=bolt://127.0.0.1:17687 \
NEO4J_USERNAME=neo4j NEO4J_PASSWORD=fixture-test-only NEO4J_DATABASE=neo4j \
uv run --locked --extra test python -m unittest discover -s tests -v
```
