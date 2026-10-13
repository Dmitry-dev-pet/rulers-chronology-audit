"""Metadata-only HTTP front door for the existing Historical Atlas MCP.

The private stdio server remains unchanged by default. This entrypoint is
deliberately restricted to *dataset_info*: it contains no historical record,
arbitrary SQL, raw file, state-changing, or optional private Archigos tool.

Docker publishes its port to the VPS LOOPBACK interface only. A public HTTPS
route and authentication, if any, are a separate reviewed deployment gate.
"""
from __future__ import annotations

import os

from scripts.atlas_mcp import create_server


def main() -> None:
    host = os.environ.get("ATLAS_MCP_BIND", "127.0.0.1")
    if host not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("ATLAS_MCP_BIND must be loopback or container-all")
    port = int(os.environ.get("ATLAS_MCP_PORT", "8765"))
    if not 1024 <= port <= 65535:
        raise ValueError("ATLAS_MCP_PORT out of range")

    create_server(archigos_path="", probe_only=True).run(
        transport="streamable-http",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        max_request_body_size=16384,
    )


if __name__ == "__main__":
    main()
