#!/usr/bin/env bash
# Commit the original JPEG through authenticated git, then verify GitHub's blob SHA.
# Run on a Mac/Linux machine with the image present and gh already authenticated.
set -Eeuo pipefail

repo="Dmitry-dev-pet/rulers-chronology-audit"
name="1000428575.jpg"
sha256="6c487e9427658f711cb41b930db2fadd06bb4b921423ab0b1b5bab4416a1c6ee"
blobsha="512d21816181002450df9d9330b6dfa3a7b46d25"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
photo="$script_dir/../assets/original/$name"
if [[ $# -ge 1 ]]; then photo="$1"; fi

for c in gh git python3; do
  command -v "$c" >/dev/null || { echo "Missing $c" >&2; exit 2; }
done
[[ -f "$photo" ]] || { echo "Original JPEG not found: $photo" >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo "Run gh auth login first" >&2; exit 2; }

python3 - "$photo" "$sha256" <<'PY'
import hashlib
from pathlib import Path
import sys
p = Path(sys.argv[1])
data = p.read_bytes()
actual = hashlib.sha256(data).hexdigest()
assert len(data) == 464782 and actual == sys.argv[2], (
    f"Refusing a non-original image: {len(data)} bytes, SHA-256 {actual}"
)
print("Original SHA-256 confirmed:", actual)
PY
[[ "$(git hash-object "$photo")" == "$blobsha" ]] || {
  echo "Git blob SHA mismatch: refusing to upload" >&2; exit 2;
}

gh auth setup-git >/dev/null
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
gh repo clone "$repo" "$tmp/repo" -- --quiet
cd "$tmp/repo"
[[ "$(git branch --show-current)" == "main" ]] || {
  echo "Unexpected default branch" >&2; exit 2;
}

dest="assets/original/$name"
mkdir -p assets/original
if [[ -f "$dest" ]]; then
  [[ "$(git hash-object "$dest")" == "$blobsha" ]] || {
    echo "A different JPEG already exists at the destination" >&2; exit 2;
  }
else
  cp "$photo" "$dest"
  git add "$dest"
  git commit -m "Archive exact original rulers poster JPEG"
  git push origin HEAD:main
fi

remote_blob="$(gh api "repos/$repo/contents/$dest?ref=main" --jq '.sha')"
[[ "$remote_blob" == "$blobsha" ]] || {
  echo "GitHub verification failed: $remote_blob" >&2; exit 1;
}
echo "GitHub binary blob verified: $remote_blob"

python3 - "$blobsha" <<'PY'
from pathlib import Path
import json
import sys
p = Path("assets/original/photo-metadata.json")
metadata = json.loads(p.read_text(encoding="utf-8"))
metadata["github_binary_upload_verified"] = True
metadata["git_blob_sha1"] = sys.argv[1]
p.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

{
  echo "# Original photo: verified"
  echo
  echo "- Exact original: \`assets/original/$name\`"
  echo "- Size: 464782 bytes"
  echo "- SHA-256: \`$sha256\`"
  echo "- GitHub blob SHA-1: \`$remote_blob\`"
  echo "- Verified UTC: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} > assets/original/VERIFIED.md
rm -f assets/original/PHOTO_UPLOAD_PENDING.md
git add -A -- assets/original
if ! git diff --cached --quiet; then
  git commit -m "Mark source JPEG verified and resolve upload blocker"
  git push origin HEAD:main
fi

gh issue close 1 -R "$repo" --comment "Original JPEG uploaded and verified (SHA-256 $sha256; Git blob $blobsha)." ||
  echo "The image is verified but issue #1 could not be closed automatically." >&2

echo "SUCCESS: https://github.com/$repo/blob/main/$dest"
