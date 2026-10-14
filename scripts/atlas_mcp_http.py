"""Read-only HTTP front door for the private Historical Atlas MCP.

Exactly five source-bounded canonical tools are eligible over the owner's
already authenticated OpenAI Secure MCP Tunnel: dataset_info, search_rulers,
get_timeline, compare_rulers, get_evidence. The separate stdio MCP retains its
optional private Archigos tool, which is NEVER exposed by this entrypoint.

The container port is published to VPS loopback only; there is no public
network listener, write tool, arbitrary SQL, or private source-file access.
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

    # Explicit allowlist: absent Archigos even if a host env var is set.
    create_server(archigos_path="", http_read_only=True).run(
        transport="streamable-http",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        max_request_body_size=16384,
    )


if __name__ == "__main__":
    main()
