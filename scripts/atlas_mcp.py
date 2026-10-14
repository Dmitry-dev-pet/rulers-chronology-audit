#!/usr/bin/env python3
"""Historical Atlas MCP (stdio), read-only, no public service or arbitrary SQL.

Run from the root with:
  ATLAS_SQLITE_PATH=dist/atlas.sqlite python3 -m scripts.atlas_mcp
Optional private Archigos file:
  ATLAS_ARCHIGOS_PATH=/absolute/private/Archigos_4.1_stata14.dta

Requires the official MCP Python SDK v2: pip install 'mcp>=2,<3'.
Raw data never goes to GitHub Pages and credentials are not used here.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.archigos_returnees import calculate_returnees, read_archigos
from scripts.atlas_mcp_query import AtlasQuery


def create_server(
    sqlite_path: str | Path | None = None,
    archigos_path: str | Path | None = None,
    *,
    probe_only: bool = False,
    http_read_only: bool = False,
):
    from mcp.server import MCPServer

    path = sqlite_path or os.environ.get("ATLAS_SQLITE_PATH")
    if not path:
        raise ValueError("ATLAS_SQLITE_PATH must point to a derived atlas.sqlite")
    if probe_only and http_read_only:
        raise ValueError("probe_only and http_read_only are mutually exclusive")
    atlas = AtlasQuery(path)
    external = archigos_path if archigos_path is not None else os.environ.get("ATLAS_ARCHIGOS_PATH")
    external = Path(external) if external else None
    cache = {"rows": None, "sha": None}
    lock = threading.Lock()
    server = MCPServer("Historical Atlas Read-Only")

    @server.tool()
    def dataset_info() -> dict:
        """Show the datasets actually available, scope, and coverage limitations."""
        result = atlas.dataset_info()
        result["archigos_file_configured"] = bool(external)
        result["archigos_data_loaded"] = cache["rows"] is not None
        return result

    # First-stage metadata probe remains unchanged for compatibility.
    # The separately reviewed, authenticated private HTTP transport can
    # additionally enable the four bounded canonical query/evidence tools.
    # Never grant the optional private Archigos tool to the HTTP service.
    if probe_only:
        return server

    @server.tool()
    def search_rulers(text: str = "", year: int | None = None, limit: int = 20) -> dict:
        """Search canonically identified rulers by names/aliases and optional year."""
        return atlas.search_rulers(text=text, year=year, limit=limit)

    @server.tool()
    def get_timeline(year: int, state_id: str = "", limit: int = 40, offset: int = 0) -> dict:
        """Fetch legal terms and separately sourced assessments of influence."""
        return atlas.get_timeline(year=year, state_id=state_id, limit=limit, offset=offset)

    @server.tool()
    def compare_rulers(person_ids: list[str]) -> dict:
        """Compare up to five canonical persons and their distinct sourced roles."""
        return atlas.compare_rulers(person_ids)

    @server.tool()
    def get_evidence(record_id: str) -> dict:
        """Get historical assertion, methodological caveats and its source links."""
        return atlas.get_evidence(record_id)

    # Strict network allowlist boundary: do not register private Archigos,
    # raw-file access, arbitrary SQL, or any state-changing tool over HTTP.
    if http_read_only:
        return server

    @server.tool()
    def archigos_returnees(
        start_year: int = 1875,
        end_year: int = 2015,
        country_code: str = "",
        min_gap_days: int = 1,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """Count repeated effective-leader spells with exact date gaps.

        Uses a private, checksum-verified Archigos 4.1 file if configured.
        Quarantines leader UUID groups with conflicting reported birth years.
        Does not infer legal offices or merge anybody into the atlas canon.
        """
        if external is None:
            return {
                "available": False,
                "reason": "ATLAS_ARCHIGOS_PATH not configured; raw Archigos stays private.",
                "historical_truth_verified_by_ci": False,
            }
        with lock:
            if cache["rows"] is None:
                cache["rows"], cache["sha"] = read_archigos(external)
        return calculate_returnees(
            cache["rows"], start_year=start_year, end_year=end_year,
            country_code=country_code, min_gap_days=min_gap_days,
            limit=limit, offset=offset,
        )

    return server


if __name__ == "__main__":
    create_server().run()
