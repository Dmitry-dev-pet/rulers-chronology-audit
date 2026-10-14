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

def result_dict(tool_result):
    """Decode SDK structured_content or the first JSON text payload."""
    candidate = getattr(tool_result, "structured_content", None)
    if candidate is None:
        candidate = getattr(tool_result, "structuredContent", None)
    if isinstance(candidate, dict):
        if isinstance(candidate.get("result"), dict):
            return candidate["result"]
        return candidate
    for item in getattr(tool_result, "content", []):
        raw = getattr(item, "text", None)
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                if isinstance(data.get("result"), dict):
                    return data["result"]
                return data
    raise AssertionError("MCP tool did not return structured dictionary content")


async def main():
    async with Client(url, raise_exceptions=True) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
        expected = [
            "dataset_info", "search_rulers", "get_timeline",
            "compare_rulers", "get_evidence",
        ]
        assert names == expected, (names, expected)
        assert "archigos_returnees" not in names
        assert not any("sql" in name or "exec" in name for name in names)

        info = await client.call_tool("dataset_info", {})
        assert not info.is_error
        dataset = result_dict(info)
        assert dataset["dataset"] == "canonical-rulers-atlas-v1"
        assert dataset["historical_truth_verified_by_ci"] is False
        assert dataset["archigos_file_configured"] is False
        assert dataset["archigos_data_loaded"] is False

        found = await client.call_tool(
            "search_rulers", {"text": "Владимир Ленин", "limit": 2}
        )
        assert not found.is_error
        people = result_dict(found)
        assert people["results"] and people["count"] >= 1
        person_id = people["results"][0]["person_id"]
        assert person_id.startswith("person-")

        timeline = await client.call_tool(
            "get_timeline", {"year": 1953, "limit": 60}
        )
        assert not timeline.is_error
        period = result_dict(timeline)
        assert period["entries"] and period["year"] == 1953
        assert period["historical_truth_verified_by_ci"] is False
        evidence_entry = next(
            item["entry_id"] for item in period["entries"] if item["source_ids"]
        )

        compared = await client.call_tool(
            "compare_rulers", {"person_ids": [person_id]}
        )
        assert not compared.is_error
        comparison = result_dict(compared)
        assert comparison["persons"][0]["person_id"] == person_id
        assert comparison["historical_truth_verified_by_ci"] is False

        sources = await client.call_tool(
            "get_evidence", {"record_id": evidence_entry}
        )
        assert not sources.is_error
        evidence = result_dict(sources)
        assert evidence["found"] is True
        assert evidence["sources"] and evidence["source_ids"]
        assert evidence["historical_truth_verified_by_ci"] is False
        assert all(
            str(source["url"]).startswith("https://")
            and "drive.google.com" not in source["url"].lower()
            for source in evidence["sources"]
        )

asyncio.run(main())
print("Private Historical Atlas HTTP MCP: five bounded read-only tool roundtrips OK")
PY
