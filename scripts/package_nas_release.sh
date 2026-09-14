#!/bin/sh
set -eu

# Builds a deterministic, secret-free transfer archive of a committed git
# ref for manual NAS transfer (scp/USB/etc.) when the NAS cannot `git pull`
# directly. Content always comes from the git object database for the given
# commit, never from the live working directory, so uncommitted local files
# (including a populated .env.nas or .env.nas.ingest) can never leak into
# the archive. This script never touches Docker, the network, or any NAS,
# and it never deploys or pushes anything -- it only writes files under the
# chosen output directory, which must be outside this worktree.
#
# The archive is scoped to a fixed runtime/deployment-only allowlist: enough
# to unpack offline, build and run the Docker image, and operate the NAS
# tools documented in docs/nas-deployment.md. Tests, .codex agent files, CI
# metadata, work logs, and other development-only material are never
# selected, regardless of what is tracked in the repository. A manifest
# (source commit + per-file SHA-256) is embedded inside the archive itself
# so a copy that traveled alone (no sibling manifest, no git access) can
# still be validated offline; the same manifest is also written next to the
# archive for pre-extraction verification.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

die() {
  echo "error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

usage() {
  cat <<EOF >&2
usage: $0 [--ref <commit-ish>] [--output-dir <dir>]

  --ref <commit-ish>    Git commit/tag/branch to package (default: HEAD).
  --output-dir <dir>    Destination directory, must be outside this
                         worktree (default: a fresh mktemp -d directory).
EOF
  exit "$1"
}

ref=HEAD
output_dir=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --ref)
      [ "$#" -ge 2 ] || usage 1
      ref=$2
      shift 2
      ;;
    --output-dir)
      [ "$#" -ge 2 ] || usage 1
      output_dir=$2
      shift 2
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      usage 1
      ;;
  esac
done

require_command git
require_command python3
require_command mktemp

commit=$(git -C "$ROOT_DIR" rev-parse --verify "${ref}^{commit}" 2>/dev/null) ||
  die "not a valid commit: $ref"

if [ -z "$output_dir" ]; then
  output_dir=$(mktemp -d "${TMPDIR:-/tmp}/robingraph-nas-release.XXXXXX")
else
  mkdir -p -- "$output_dir" || die "cannot create output directory: $output_dir"
fi

resolved_output_dir=$(CDPATH= cd -- "$output_dir" && pwd)
case "$resolved_output_dir" in
  "$ROOT_DIR" | "$ROOT_DIR"/*)
    die "output directory must be outside the worktree: $resolved_output_dir"
    ;;
esac

prefix="robingraph-nas-release-${commit}"
archive_path="$resolved_output_dir/${prefix}.tar.gz"
manifest_path="$resolved_output_dir/${prefix}.manifest.txt"

# The allowlist, hashing, tar/gzip construction, and manifest writing all
# happen in this embedded helper so the archive can be built as a single
# deterministic pass over git blob content, with an in-memory tar that a
# generated (non-tracked) MANIFEST.txt member can be added to before the
# one-shot gzip. Only committed objects for $commit are ever read.
archive_sha256=$(python3 - "$commit" "$ROOT_DIR" "$archive_path" "$manifest_path" "$prefix" <<'PYEOF'
import gzip
import hashlib
import io
import os
import subprocess
import sys
import tarfile

commit, root_dir, archive_path, manifest_path, prefix = sys.argv[1:6]

# Runtime/deployment-only allowlist: sufficient to unpack offline, build
# and run the Docker image (matches the Dockerfile COPY list), and operate
# the NAS tools documented in docs/nas-deployment.md. Everything else --
# tests, .codex agent files, .github CI metadata, work logs, decision/
# design docs, n8n draft candidates, dev-only generator scripts -- is
# deliberately excluded.
ALLOW_FILES = frozenset(
    [
        ".dockerignore",
        ".env.nas.example",
        ".env.nas.ingest.example",
        ".python-version",
        "compose.nas.yml",
        "Dockerfile",
        "pyproject.toml",
        "README.md",
        "uv.lock",
        "docs/nas-deployment.md",
        "docs/n8n/korean-vernacular-ingest.md",
        "n8n/robingraph-operational-ingest.json",
        "n8n/robingraph-reference-ingest.json",
        "n8n/robingraph-avonet-ingest.json",
        "n8n/robingraph-korean-vernacular-ingest.json",
        "scripts/deploy_nas.sh",
        "scripts/package_nas_release.sh",
        "scripts/verify_api_deployment.py",
        "scripts/deploy_n8n_operational_ingest.py",
        "scripts/deploy_n8n_reference_ingest.py",
        "scripts/manage_n8n_korean_vernacular.py",
        "scripts/load_n8n_avonet.py",
    ]
)
ALLOW_PREFIXES = ("src/", "data/eval/v1/", "config/")


def die(message):
    sys.stderr.write("error: " + message + "\n")
    sys.exit(1)


def run_git(args):
    result = subprocess.run(
        ["git", "-C", root_dir] + args, capture_output=True, check=True
    )
    return result.stdout


all_paths = run_git(["ls-tree", "-r", "--name-only", commit]).decode("utf-8").splitlines()
all_paths_set = set(all_paths)

missing = sorted(p for p in ALLOW_FILES if p not in all_paths_set)
if missing:
    die(
        "required deployment file(s) missing from commit %s: %s"
        % (commit, ", ".join(missing))
    )

selected = sorted(
    p for p in all_paths if p in ALLOW_FILES or p.startswith(ALLOW_PREFIXES)
)
if not selected:
    die("commit %s has no allowlisted files to package" % commit)

# Defense in depth: the allowlist above never names a secret-like file, but
# refuse anyway if one somehow appears under an allowed directory prefix.
for path in selected:
    if path.endswith(".example"):
        continue
    name = path.rsplit("/", 1)[-1]
    lowered = path.lower()
    if name == ".env" or name.startswith(".env."):
        die("refusing to package tracked secret-like file: %s" % path)
    if lowered.endswith(".pem") or lowered.endswith(".key"):
        die("refusing to package tracked secret-like file: %s" % path)
    if "credential" in lowered or "secret" in lowered:
        die("refusing to package tracked secret-like file: %s" % path)

mode_by_path = {}
for line in run_git(["ls-tree", "-r", commit]).decode("utf-8").splitlines():
    header, _, path = line.partition("\t")
    mode_by_path[path] = int(header.split()[0], 8)

commit_ts = int(run_git(["show", "-s", "--format=%ct", commit]).decode("utf-8").strip())

batch = subprocess.Popen(
    ["git", "-C", root_dir, "cat-file", "--batch"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)
query = "".join("%s:%s\n" % (commit, path) for path in selected).encode("utf-8")
batch_out, _ = batch.communicate(query)
if batch.returncode != 0:
    die("git cat-file --batch failed")

contents = {}
offset = 0
for path in selected:
    newline = batch_out.index(b"\n", offset)
    header = batch_out[offset:newline].decode("utf-8")
    _sha, _type, size_str = header.rsplit(" ", 2)
    size = int(size_str)
    start = newline + 1
    contents[path] = batch_out[start : start + size]
    offset = start + size + 1

file_hashes = [(path, hashlib.sha256(contents[path]).hexdigest()) for path in selected]
file_count = len(file_hashes)

manifest_lines = [
    "release=robingraph-nas",
    "source_commit=" + commit,
    "file_count=" + str(file_count),
    "---",
]
for path, digest in file_hashes:
    manifest_lines.append(digest + "  " + path)
embedded_manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")


def make_tarinfo(name, size, mode, kind):
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = commit_ts
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = kind
    return info


tar_buf = io.BytesIO()
with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
    added_dirs = set()

    def add_dir(dir_path):
        if not dir_path or dir_path in added_dirs:
            return
        parent = dir_path.rsplit("/", 1)[0] if "/" in dir_path else ""
        if parent:
            add_dir(parent)
        added_dirs.add(dir_path)
        tar.addfile(make_tarinfo(dir_path + "/", 0, 0o755, tarfile.DIRTYPE))

    add_dir(prefix)
    for path in selected:
        parent = prefix + "/" + path.rsplit("/", 1)[0] if "/" in path else prefix
        add_dir(parent)
        data = contents[path]
        info = make_tarinfo(
            prefix + "/" + path, len(data), mode_by_path[path] & 0o777, tarfile.REGTYPE
        )
        tar.addfile(info, io.BytesIO(data))

    manifest_info = make_tarinfo(
        prefix + "/MANIFEST.txt", len(embedded_manifest), 0o644, tarfile.REGTYPE
    )
    tar.addfile(manifest_info, io.BytesIO(embedded_manifest))

tar_bytes = tar_buf.getvalue()

gz_buf = io.BytesIO()
with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, compresslevel=9, mtime=0) as gz:
    gz.write(tar_bytes)
gz_bytes = gz_buf.getvalue()

with open(archive_path, "wb") as handle:
    handle.write(gz_bytes)

archive_sha256 = hashlib.sha256(gz_bytes).hexdigest()

external_lines = [
    "release=robingraph-nas",
    "source_commit=" + commit,
    "archive=" + os.path.basename(archive_path),
    "archive_sha256=" + archive_sha256,
    "file_count=" + str(file_count),
    "---",
]
for path, digest in file_hashes:
    external_lines.append(digest + "  " + path)

with open(manifest_path, "w", encoding="utf-8") as handle:
    handle.write("\n".join(external_lines) + "\n")

sys.stdout.write(archive_sha256 + "\n")
PYEOF
) || die "packaging failed"

echo "source_commit=$commit"
echo "archive=$archive_path"
echo "archive_sha256=$archive_sha256"
echo "manifest=$manifest_path"
