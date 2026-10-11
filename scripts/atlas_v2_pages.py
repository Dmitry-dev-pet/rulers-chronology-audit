"""Publish Atlas v2 as /v2.html alongside an UNCHANGED GitHub Pages index.

No additional Pages repository, hosting service, API or database server.
The existing checked-in source remains read-only. The v2 page reuses the
existing flat / site assets, so only four extra flat static files are needed:
v2.html, atlas-v2-graph.js, atlas-v2-graph.css, atlas-v2-graph.json.

Called AFTER the normal, tested v1 static build and before Pages allowlist
verification. The original index.html and every v1 artifact are unchanged;
only SHA256SUMS is updated to include the four new assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from scripts import atlas_v2_graph_preview as preview

ROOT = preview.ROOT
PUBLIC_FILES = (
    "v2.html",
    "atlas-v2-graph.js",
    "atlas-v2-graph.css",
    "atlas-v2-graph.json",
)


def require(condition: bool, reason: str) -> None:
    preview.require(condition, "Pages v2: " + reason)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root: Path = ROOT, dist: Path | None = None) -> dict:
    """Safely add v2.html to existing Pages dist, leaving index.html untouched."""
    dist = dist or root / "dist"
    require(dist.is_dir(), "expected existing verified dist")
    require((dist / "index.html").is_file() and
            (dist / "atlas.json").is_file() and
            (dist / "SHA256SUMS").is_file(),
            "dist is missing canonical SPA assets")
    require(not any((dist / name).exists() for name in PUBLIC_FILES),
            "public v2 files already exist; refuse to overwrite")
    require(all(p.is_file() for p in dist.iterdir()),
            "nested public assets are not permitted")

    before = {p.name: digest(p) for p in dist.iterdir() if p.is_file()}
    with tempfile.TemporaryDirectory(prefix="atlas-v2-pages-") as temp:
        stage = Path(temp) / "preview"
        # Existing exporter validates the entire graph and privacy, then
        # modifies only the throwaway preview/ index, never original dist.
        receipt = preview.preview_build(root, dist, stage)
        require(receipt["counts"]["relations"] == 27,
                "unexpected historical graph relation count")
        page = (stage / "index.html").read_text(encoding="utf-8")
        require("id='atlas-v2-launch'" in page and
                "src='./atlas-v2-graph.js'" in page and
                "href='./atlas-v2-graph.css'" in page,
                "preview SPA is missing feature-flag launcher")
        require("atlasV2=graph" in page,
                "v2 graph is not enabled by deep link")
        mapping = {
            "v2.html": "index.html",
            "atlas-v2-graph.js": "atlas-v2-graph.js",
            "atlas-v2-graph.css": "atlas-v2-graph.css",
            "atlas-v2-graph.json": "atlas-v2-graph.json",
        }
        for destination, source in mapping.items():
            shutil.copyfile(stage / source, dist / destination)

    # Preserve exactly the same SHA256SUMS contract already used by v1.
    (dist / "SHA256SUMS").write_text("".join(
        digest(p) + "  " + p.name + "\n"
        for p in sorted(dist.iterdir()) if p.is_file() and p.name != "SHA256SUMS"
    ), encoding="utf-8")
    for name, old_hash in before.items():
        if name != "SHA256SUMS":
            require(digest(dist / name) == old_hash,
                    "original Pages artifact changed: " + name)

    public = {p.name for p in dist.iterdir()}
    require(public == set(before) | set(PUBLIC_FILES),
            "unexpected public assets")
    require((dist / "v2.html").read_bytes() !=
            (dist / "index.html").read_bytes(),
            "v2.html must be opt-in; index.html must stay unchanged")
    for p in dist.iterdir():
        raw = p.read_bytes()
        require(b"drive.google.com" not in raw and
                b"1000428575.jpg" not in raw,
                "private source reference in public output: " + p.name)
    return {
        "status": "ready_for_existing_pages_deploy",
        "historical_truth_verified_by_ci": False,
        "site_entry": "v2.html?atlasV2=graph&v2Year=1788#/timeline/1762",
        "new_files": list(PUBLIC_FILES),
        "original_index_unchanged": True,
        "original_file_count": len(before),
        "counts": receipt["counts"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.dist),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
