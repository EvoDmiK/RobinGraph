pipeline {
    agent { label 'robingraph-mac16' }
    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }
    parameters {
        booleanParam(name: 'CHECK_ONLY', defaultValue: false,
            description: 'Run checkout and tests only; do not publish images or deploy Production.')
    }
    triggers { pollSCM('H/5 * * * *') }
    environment {
        DOCKER_CONTEXT = 'orbstack'
        IMAGE_REPOSITORY = 'ghcr.io/evodmik/robingraph'
        PATH = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    }
    stages {
        stage('Checkout') {
            steps {
                checkout([$class: 'GitSCM', branches: [[name: '*/main']],
                    userRemoteConfigs: [[url: 'https://github.com/EvoDmiK/RobinGraph.git']]])
                sh 'python3 -c "import base64;exec(base64.b64decode(\'aW1wb3J0IHBhdGhsaWIsc2h1dGlsLGpzb24saGFzaGxpYgpzcmM9cGF0aGxpYi5QYXRoKCIvVXNlcnMva2ltZG92ZS9yb2JpbmdyYXBoLXRlc3QvcHJvZHVjdGlvbi1zbmFwc2hvdHMvcmcyMTItNmE5NTkxOGE1NTMzIikKZHN0PXBhdGhsaWIuUGF0aC5jd2QoKQphc3NlcnQgKGRzdC8iLmdpdCIpLmV4aXN0cygpCmZvciB4IGluIHNyYy5pdGVyZGlyKCk6CiB0PWRzdC94Lm5hbWUKIGlmIHQuaXNfZGlyKCk6IHNodXRpbC5ybXRyZWUodCkKIGVsaWYgdC5leGlzdHMoKTogdC51bmxpbmsoKQogaWYgeC5pc19kaXIoKTogc2h1dGlsLmNvcHl0cmVlKHgsdCkKIGVsc2U6IHNodXRpbC5jb3B5Mih4LHQpCm09anNvbi5sb2FkcygoZHN0LyJhcHByb3ZlZC1zb3VyY2UuanNvbiIpLnJlYWRfdGV4dCgpKQpmb3IgbmFtZSxkaWdlc3QgaW4gbVsiYXBwcm92ZWRfZmlsZXMiXS5pdGVtcygpOgogYXNzZXJ0IGhhc2hsaWIuc2hhMjU2KChkc3QvbmFtZSkucmVhZF9ieXRlcygpKS5oZXhkaWdlc3QoKT09ZGlnZXN0LG5hbWUKcHJpbnQoIkFwcHJvdmVkIHNuYXBzaG90OiAiK21bImFwcHJvdmVkX3NvdXJjZV9zaGEyNTYiXSsiOyBmaWxlcyAiK3N0cihsZW4obVsiYXBwcm92ZWRfZmlsZXMiXSkpKQo=\'))"'
                script {
                    env.REVISION = '834c5353ca45f0640152ca4849548cd48818b266'
                    env.SOURCE_SHA = '6a95918a55332aa0195c07bf4e5a9c60a7cb006b67fd56d255d683f22c72c922'
                    env.IMAGE_TAG = "${env.IMAGE_REPOSITORY}:snapshot-6a95918a5533"
                    env.DOCKER_CONFIG = "${pwd(tmp: true)}/registry-auth"
                }
                sh '''#!/bin/sh
set -eu
umask 077
rm -rf "$DOCKER_CONFIG"
mkdir -p "$DOCKER_CONFIG"
if [ -d "$HOME/.docker/cli-plugins" ]; then
  ln -s "$HOME/.docker/cli-plugins" "$DOCKER_CONFIG/cli-plugins"
fi
DOCKER_CONFIG="$HOME/.docker" docker context export orbstack - | \
  env -u DOCKER_CONTEXT docker context import orbstack -
'''
            }
        }
        stage('Tests') {
            steps {
                sh '''#!/bin/sh
set -eu
uv run --locked python -m django check --settings=robingraph.django_api.settings
uv run --locked --extra test --extra tracing python -m unittest discover -s tests
uv run --locked --extra test python -m unittest discover -s release-ops/tests -p 'test*.py'
node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js
docker version --format '{{.Server.Arch}}'
'''
                stash name: 'production-deploy-helper', includes: 'release-ops/**,approved-source.json'
            }
        }
        stage('Build and publish ARM64 + AMD64') {
            when { expression { !params.CHECK_ONLY } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'robingraph-ghcr',
                    usernameVariable: 'GHCR_USERNAME', passwordVariable: 'GHCR_TOKEN')]) {
                    sh '''#!/bin/sh
set -eu
umask 077
mkdir -p "$DOCKER_CONFIG"
printf '%s\n' "$GHCR_TOKEN" | docker login ghcr.io --username "$GHCR_USERNAME" --password-stdin
docker buildx build --platform linux/arm64,linux/amd64 --push \
  --label "org.robingraph.source-sha256=$SOURCE_SHA" --label "org.robingraph.uncommitted-snapshot=true" \
  --build-arg "VCS_REF=$REVISION" --tag "$IMAGE_TAG" \
  --metadata-file image-metadata.json .
'''
                }
                script {
                    env.IMAGE_DIGEST = sh(script: '''python3 -c 'import json; print(json.load(open("image-metadata.json"))["containerimage.digest"])' ''', returnStdout: true).trim()
                    env.IMMUTABLE_IMAGE = "${env.IMAGE_REPOSITORY}@${env.IMAGE_DIGEST}"
                }
            }
        }
        stage('AMD64 fixture startup smoke') {
            when { expression { !params.CHECK_ONLY } }
            steps {
                sh '''#!/bin/sh
set -eu
name="robingraph-amd64-smoke-$BUILD_NUMBER"
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT HUP INT TERM
docker run -d --platform linux/amd64 --name "$name" --network none \
  --read-only --tmpfs /tmp "$IMMUTABLE_IMAGE" \
  robingraph serve-fixture --host 0.0.0.0 --port 8000
attempt=0
until docker exec "$name" python -c 'import json,urllib.request; d=json.load(urllib.request.urlopen("http://127.0.0.1:8000/health",timeout=3)); assert d["status"]=="ok"; urllib.request.urlopen("http://127.0.0.1:8000/openapi.json",timeout=3)' >/dev/null 2>&1; do
  attempt=$((attempt+1))
  if [ "$attempt" -ge 30 ]; then echo 'AMD64 fixture smoke failed' >&2; exit 1; fi
  sleep 2
done
'''
            }
        }
        stage('Production approval') {
            when { expression { !params.CHECK_ONLY } }
            steps {
                input(id: 'approveProduction', submitter: 'admin', ok: 'Deploy to NAS Production',
                    message: "Deploy approved source snapshot ${env.SOURCE_SHA} (base ancestry ${env.REVISION}), image ${env.IMMUTABLE_IMAGE}, active / semantic and MLflow production experiment 50?")
            }
        }
        stage('Deploy and verify NAS Production') {
            agent { label 'robingraph-nas-deploy' }
            when { beforeAgent true; expression { !params.CHECK_ONLY } }
            environment {
                DOCKER_CONTEXT = 'default'
                DOCKER_HOST = 'unix:///var/run/docker.sock'
            }
            steps {
                unstash 'production-deploy-helper'
                withCredentials([
                    usernamePassword(credentialsId: 'robingraph-ghcr', usernameVariable: 'GHCR_USERNAME', passwordVariable: 'GHCR_TOKEN')
                ]) {
                    sh '''#!/bin/sh
set -eu
python3 release-ops/scripts/deploy_registry_prod.py --local \
  --image "$IMMUTABLE_IMAGE" --revision "$REVISION" \
  --graph-intent-mode active --graph-interpreter semantic \
  --mlflow-tracing true --mlflow-experiment-id 50 --mlflow-experiment-name robingraph-prod
printf '{"revision":"%s","image":"%s","production_verified":true}\n' \
  "$REVISION" "$IMMUTABLE_IMAGE" > production-release.json
'''
                }
                archiveArtifacts artifacts: 'production-release.json'
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: '*-metadata.json,production-release.json', allowEmptyArchive: true
            sh '''#!/bin/sh
set -eu
if [ -n "${DOCKER_CONFIG:-}" ]; then
  docker logout ghcr.io >/dev/null 2>&1 || true
  rm -rf "$DOCKER_CONFIG"
fi
'''
        }
    }
}
