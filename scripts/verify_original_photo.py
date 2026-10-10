#!/usr/bin/env python3
"""Verify the source photograph has been uploaded unchanged."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
meta = json.loads((root / "assets/original/photo-metadata.json").read_text(encoding="utf-8"))
path = root / "assets/original" / meta["name"]

if not path.is_file():
    print(f"MISSING: {path.relative_to(root)}")
    sys.exit(2)
actual_size = path.stat().st_size
actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
expected_size = meta["size_bytes"]
expected_hash = meta["sha256"]
if actual_size != expected_size or actual_hash != expected_hash:
    print(f"MISMATCH: {path.relative_to(root)}")
    print(f"expected bytes={expected_size} SHA-256={expected_hash}")
    print(f"actual   bytes={actual_size} SHA-256={actual_hash}")
    sys.exit(1)
print(f"VERIFIED: {path.relative_to(root)} ({actual_size} bytes, sha256={actual_hash})")
