#!/usr/bin/env python3
"""Five-tool canonical Historical Atlas MCP over local stdio.

Unlike the separate Archigos benchmark, this exposes only the publicly sourced
rulers tools. There are no mutation tools, arbitrary SQL, or private Archigos.
The underlying AtlasQuery opens the canonical SQLite database read-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.atlas_mcp import create_server


if __name__ == "__main__":
    create_server(http_read_only=True).run()
