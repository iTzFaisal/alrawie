#!/usr/bin/env bash
# Build one zip per series folder and attach them to a GitHub release.
#
#   ./release.sh              build, upload, verify
#   ./release.sh --publish    ...and publish the release if it is still a draft
#
# Uploads are resumable: assets whose local SHA-256 matches the remote digest
# are skipped. Credentials come from the `gh` CLI (https://cli.github.com).
set -euo pipefail
cd "$(dirname "$0")"

REPO="${REPO:-iTzFaisal/alrawie}"
TAG="${TAG:-archive-2026-11-15}"
TITLE="${TITLE:-أرشيف فواز الغسلان الصوتي — 211 مقطعًا (11 سلسلة)}"
OUT="dist/release"
NOTES="RELEASE_NOTES.md"
PUBLISH=0
[[ "${1:-}" == "--publish" ]] && PUBLISH=1

for tool in gh python3; do
  command -v "$tool" >/dev/null || { echo "missing required tool: $tool" >&2; exit 1; }
done
[[ -f "$NOTES" ]] || { echo "missing release notes: $NOTES" >&2; exit 1; }

file_size() { wc -c <"$1" | tr -d '[:space:]'; }

local_sha() {
  if command -v shasum >/dev/null; then
    shasum -a 256 "$1" | awk '{print "sha256:" $1}'
  else
    sha256sum "$1" | awk '{print "sha256:" $1}'
  fi
}

# The GitHub API exposes each asset's SHA-256 digest. Comparing digests (not
# just sizes) is what catches a rebuilt zip that happens to keep its old size,
# and SHA256SUMS.txt, whose byte length never changes when a hash changes.
remote_field() {
  awk -F'\t' -v want="$2" -v col="$1" '$3 == want { print $col; exit }' \
    "$OUT/remote-assets-initial.tsv" 2>/dev/null
}
remote_digest() { remote_field 2 "$1"; }
remote_size() { remote_field 1 "$1"; }

python3 make_zips.py

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "release $TAG exists, reusing it"
  echo "syncing release notes from $NOTES"
  gh release edit "$TAG" --repo "$REPO" --title "$TITLE" --notes-file "$NOTES"
else
  echo "creating draft release $TAG"
  gh release create "$TAG" --repo "$REPO" --draft --title "$TITLE" --notes-file "$NOTES"
fi

# Smallest archive first, so a naming problem surfaces before the big uploads.
python3 - "$OUT" >"$OUT/upload-order.txt" <<'PY'
import sys
from pathlib import Path

out = Path(sys.argv[1])
for path in sorted(out.glob("*.zip"), key=lambda p: p.stat().st_size):
    print(path)
print(out / "SHA256SUMS.txt")
PY

gh release view "$TAG" --repo "$REPO" --json assets \
  --jq '.assets[] | "\(.size)\t\(.digest // "")\t\(.name)"' >"$OUT/remote-assets-initial.tsv"

while IFS= read -r file; do
  name="$(basename "$file")"
  size="$(file_size "$file")"
  digest="$(remote_digest "$name")"
  if [[ -n "$digest" ]]; then
    if [[ "$digest" == "$(local_sha "$file")" ]]; then
      echo "skip    $name (sha256 match)"
      continue
    fi
  elif [[ "$(remote_size "$name")" == "$size" ]]; then
    echo "skip    $name (size match, no digest)"
    continue
  fi
  echo "upload  $name ($((size / 1024 / 1024)) MB)"
  gh release upload "$TAG" "$file" --repo "$REPO" --clobber
done <"$OUT/upload-order.txt"

echo
echo "checking checksums"
(cd "$OUT" && { command -v shasum >/dev/null && shasum -a 256 -c SHA256SUMS.txt \
  || sha256sum -c SHA256SUMS.txt; })

echo "verifying release assets against local files"
gh release view "$TAG" --repo "$REPO" --json assets \
  --jq '.assets[] | "\(.size)\t\(.digest // "")\t\(.name)"' >"$OUT/remote-assets.tsv"

python3 - "$OUT" <<'PY'
import hashlib
import sys
from pathlib import Path

out = Path(sys.argv[1])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


remote = {}
for line in (out / "remote-assets.tsv").read_text(encoding="utf-8").splitlines():
    size, digest, name = line.split("\t", 2)
    remote[name] = (int(size), digest)

expected = {"SHA256SUMS.txt": (out / "SHA256SUMS.txt").stat().st_size}
for line in (out / "summary.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    _, asset, _, size = line.split("\t")
    expected[asset] = int(size)

problems = []
for name, size in expected.items():
    if name not in remote:
        problems.append(f"missing on release: {name}")
        continue
    remote_size, remote_digest = remote[name]
    if remote_size != size:
        problems.append(f"size differs on release: {name} ({remote_size} != {size})")
    if remote_digest and remote_digest != sha256(out / name):
        problems.append(f"sha256 differs on release: {name}")
for name in sorted(set(remote) - set(expected)):
    problems.append(f"unexpected asset on release: {name}")

if problems:
    print("\n".join(problems), file=sys.stderr)
    raise SystemExit(1)
print(f"verified: {len(expected)} assets, sizes and sha256 digests match local archives")
PY

if [[ "$PUBLISH" -eq 1 ]]; then
  gh release edit "$TAG" --repo "$REPO" --draft=false
  echo "published: https://github.com/$REPO/releases/tag/$TAG"
elif [[ "$(gh release view "$TAG" --repo "$REPO" --json isDraft --jq '.isDraft')" == "true" ]]; then
  echo "left as draft: https://github.com/$REPO/releases/tag/$TAG"
  echo "publish with: $0 --publish"
else
  echo "release is published: https://github.com/$REPO/releases/tag/$TAG"
fi
