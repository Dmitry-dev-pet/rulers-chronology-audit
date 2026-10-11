"""Minimal single-tool MCP server for the controlled macOS benchmark.

This is deliberately separate from the general-purpose atlas_mcp server:
there are *no other tools* for a model to discover in this benchmark.
Only official SHA-pinned Archigos 4.1 data may be read.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server import MCPServer

from scripts.archigos_returnees import calculate_returnees, read_archigos


def create_server(path: str | Path | None = None):
    source = path or os.environ.get("ATLAS_ARCHIGOS_PATH")
    if not source:
        raise ValueError("ATLAS_ARCHIGOS_PATH is required")
    records, _ = read_archigos(Path(source))
    server = MCPServer("historical-atlas")

    @server.tool()
    def archigos_returnees(
        start_year: int = 1875,
        end_year: int = 2015,
        country_code: str = "",
        min_gap_days: int = 1,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """Compute sourced return-to-power counts, gaps and identity conflicts.

        Reads only pinned original Archigos 4.1. No mutation, general SQL,
        repository access, web or other MCP tools are supported.
        """
        return calculate_returnees(
            records,
            start_year=start_year, end_year=end_year,
            country_code=country_code,
            min_gap_days=min_gap_days, limit=limit, offset=offset,
        )

    return server


if __name__ == "__main__":
    create_server().run()
