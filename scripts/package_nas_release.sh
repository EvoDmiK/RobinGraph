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

sha256_of_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "no sha256 tool found (need sha256sum or shasum)"
  fi
}

sha256_of_stdin() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  else
    die "no sha256 tool found (need sha256sum or shasum)"
  fi
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
require_command tar
require_command gzip
require_command awk
require_command sort
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

filelist_file=$(mktemp "${TMPDIR:-/tmp}/robingraph-nas-filelist.XXXXXX")
trap 'rm -f "$filelist_file"' EXIT

git -C "$ROOT_DIR" ls-tree -r --name-only "$commit" | sort >"$filelist_file"
[ -s "$filelist_file" ] || die "commit $commit has no tracked files to package"

# Defense in depth: the archive can only ever contain files tracked at this
# commit (secrets are gitignored and thus never tracked), but refuse to
# package anyway if a secret-shaped path somehow got committed.
while IFS= read -r path; do
  case "$path" in
    *.example) continue ;;
    .env | .env.* | */.env | */.env.*)
      die "refusing to package tracked secret-like file: $path"
      ;;
    *credential* | *secret* | *.pem | *.key)
      die "refusing to package tracked secret-like file: $path"
      ;;
  esac
done <"$filelist_file"

prefix="robingraph-nas-release-${commit}"
archive_path="$resolved_output_dir/${prefix}.tar.gz"
manifest_path="$resolved_output_dir/${prefix}.manifest.txt"

# `-n` drops the original filename/mtime from the gzip header so identical
# tar bytes always produce identical gzip bytes; `git archive` itself is
# deterministic for a fixed commit and git version (no working-directory
# mtimes or ordering are involved).
git -C "$ROOT_DIR" archive --format=tar --prefix="${prefix}/" "$commit" |
  gzip -n -9 >"$archive_path"

archive_sha256=$(sha256_of_file "$archive_path")
file_count=$(grep -c '' "$filelist_file")

{
  echo "release=robingraph-nas"
  echo "source_commit=$commit"
  echo "archive=$(basename "$archive_path")"
  echo "archive_sha256=$archive_sha256"
  echo "file_count=$file_count"
  echo "---"
  while IFS= read -r path; do
    blob_sha=$(git -C "$ROOT_DIR" rev-parse "${commit}:${path}")
    file_sha256=$(git -C "$ROOT_DIR" cat-file blob "$blob_sha" | sha256_of_stdin)
    printf '%s  %s\n' "$file_sha256" "$path"
  done <"$filelist_file"
} >"$manifest_path"

echo "source_commit=$commit"
echo "archive=$archive_path"
echo "archive_sha256=$archive_sha256"
echo "manifest=$manifest_path"
