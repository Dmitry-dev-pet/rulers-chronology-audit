#!/usr/bin/env bash
set -euo pipefail

# Smoke the exact image from the calling CI job; never pull another image.
image="${1:?Pass the built immutable image ref}"
container="atlas-probe-smoke-${GITHUB_RUN_ID:-local}-$$"
cleanup() {
  rc=$?
  if (( rc != 0 )); then
    echo "MCP probe container diagnostics (no credentials configured):" >&2
    docker logs "$container" >&2 || true
    docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$container" >&2 || true
  fi
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --detach --rm --name "$container" \
  --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,size=8m \
  --publish "127.0.0.1:18765:8765" "$image" >/dev/null

python3 - <<'PY'
import asyncio
import http.client
import json
import time

from mcp import Client

url = "http://127.0.0.1:18765/mcp"

# A Docker-published host TCP port can accept connections BEFORE the
# container's MCP/uvicorn process is ready; probe the actual JSON-RPC exchange.
initialize = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2026-07-28",
        "capabilities": {},
        "clientInfo": {"name": "atlas-ci-probe", "version": "1"},
    },
}).encode("utf-8")

for attempt in range(100):
    probe = http.client.HTTPConnection("127.0.0.1", 18765, timeout=2)
    try:
        probe.request("POST", "/mcp", body=initialize, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        })
        response = probe.getresponse()
        sample = response.read(300)
        if response.status != 200:
            raise AssertionError(
                f"MCP initialize returned {response.status}: {sample!r}"
            )
        print("Direct JSON-RPC initialize:", response.status, sample)
        break
    except (ConnectionError, TimeoutError, OSError):
        if attempt == 99:
            raise SystemExit("MCP process never accepted initialize within 25 seconds")
        time.sleep(0.25)
    finally:
        probe.close()

async def main():
    async with Client(url, raise_exceptions=True) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
        assert names == ["dataset_info"], names
        result = await client.call_tool("dataset_info", {})
        assert not result.is_error, result
        raw = str(result)
        assert "canonical_persons" in raw, raw
        assert "historical_truth_verified_by_ci" in raw, raw

asyncio.run(main())
print("MCP HTTPS-ingress candidate: local HTTP metadata-only tool roundtrip OK")
PY
