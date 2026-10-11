#!/usr/bin/env python3
"""A/B harness: same Antigravity model and prompt, without vs with Atlas MCP.

Runs locally as the already authenticated agy user. Never asks for or
exports OAuth tokens. This does not use the Gemini API, a GitHub secret,
ChatGPT API, or a remote MCP endpoint. Logs remain in ignored dist/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "benchmarks" / "archigos_return_v1.json"
SCHEMA = {
    "type": "object",
    "properties": {
        "return_events": {"type": "integer"},
        "unique_country_person_keys": {"type": "integer"},
        "mean_gap_days": {"type": "number"},
        "excluded_conflicting_identity_groups": {"type": "integer"},
        "anomaly_example": {"type": "string"},
        "methodology_note": {"type": "string"},
        "insufficient_data": {"type": "boolean"},
    },
    "required": [
        "return_events", "unique_country_person_keys", "mean_gap_days",
        "excluded_conflicting_identity_groups", "anomaly_example",
        "methodology_note", "insufficient_data",
    ],
}


def parse_run(raw: str) -> dict:
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    first = next((e["init"] for e in events if e.get("event") == "init"), {})
    final = next((e["result"] for e in reversed(events) if e.get("event") == "result"), {})
    tools = []
    for event in events:
        item = event.get("step_update", {})
        if event.get("event") == "step_update" and item.get("step_type") == "tool" and item.get("state") == "DONE":
            tools.append(item.get("tool_name") or item.get("tool_info", {}).get("name", "unknown"))
    return {
        "status": final.get("status"), "error": final.get("error", ""),
        "answer": final.get("structured_output"),
        "response": final.get("response"),
        "usage": final.get("usage"),
        "duration_seconds": final.get("duration_seconds"),
        "model_requested": first.get("model"),
        "available_tool_names": first.get("tools", []),
        "used_tool_names": tools,
    }


def score(result: dict, gold: dict, with_mcp: bool) -> dict:
    answer = result.get("answer")
    expected = gold["expected"]
    toolnames = [str(t).lower() for t in result.get("used_tool_names", [])]
    touched_mcp = any("archigos_returnees" in t or "historical-atlas" in t for t in toolnames)
    assessed = isinstance(answer, dict) and result.get("status") == "SUCCESS"
    exact = assessed and not answer.get("insufficient_data")
    if exact:
        for key in ("return_events", "unique_country_person_keys", "excluded_conflicting_identity_groups"):
            exact = exact and answer.get(key) == expected[key]
        try:
            exact = exact and abs(float(answer.get("mean_gap_days")) - expected["mean_gap_days"]) <= 0.001
        except (TypeError, ValueError):
            exact = False
    return {
        "exact_aggregate_match": bool(exact),
        "honest_abstention": bool(assessed and answer.get("insufficient_data")),
        "used_archigos_mcp": touched_mcp,
        "protocol_failed_or_mcp_not_used": bool(result.get("status") != "SUCCESS" or (with_mcp and not touched_mcp)),
        "other_tool_calls": [t for t in toolnames if "archigos_returnees" not in t and "historical-atlas" not in t],
        "note": "Exact aggregate match is not an independent historical truth score. Non-MCP tool use is logged as a confounder.",
    }


def run_once(
    agy: str, model: str, prompt: str, schema_file: Path,
    cwd: Path, timeout: int,
) -> dict:
    command = [
        agy, "-p", prompt, "--output-format", "stream-json",
        "--json-schema", str(schema_file), "--model", model,
        "--print-timeout", str(timeout) + "s",
    ]
    try:
        completed = subprocess.run(
            command, cwd=str(cwd), capture_output=True,
            encoding="utf-8", errors="replace", timeout=timeout + 30,
            check=False,
        )
        if completed.returncode:
            return {
                "status": "ERROR", "exit_code": completed.returncode,
                "diagnostics": completed.stderr[-1800:],
                "raw_stream": completed.stdout,
            }
        parsed = parse_run(completed.stdout)
        parsed["raw_stream"] = completed.stdout
        parsed["diagnostics"] = completed.stderr[-1800:]
        parsed["exit_code"] = completed.returncode
        return parsed
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "raw_stream": "", "diagnostics": "", "exit_code": None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sqlite", type=Path, default=ROOT / "dist" / "atlas.sqlite")
    ap.add_argument("--archigos", type=Path, required=True, help="Private original Stata file, never uploaded to Git")
    ap.add_argument("--model", required=True, help="An actual installed agy model slug; same in both lanes")
    ap.add_argument("--agy", default="agy")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "benchmark-mcp")
    args = ap.parse_args()
    if not shutil.which(args.agy):
        ap.error("Antigravity CLI (agy) is not installed/in PATH")
    if not args.sqlite.is_file() or not args.archigos.is_file():
        ap.error("Build dist/atlas.sqlite and obtain private Archigos .dta first")
    if not 30 <= args.timeout <= 900:
        ap.error("timeout must be 30..900 seconds")
    from scripts.archigos_returnees import EXPECTED_SHA256
    import hashlib
    if hashlib.sha256(args.archigos.read_bytes()).hexdigest() != EXPECTED_SHA256:
        ap.error("Wrong source dataset checksum; refuses to run benchmark")
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    destination = args.out.resolve()
    if destination.is_relative_to(ROOT / "data" / "atlas") or destination == ROOT / "site":
        ap.error("Cannot write results into canonical/source directories")
    destination.mkdir(parents=True, exist_ok=True)
    os.chmod(destination, 0o700)
    with tempfile.TemporaryDirectory(prefix="atlas-agy-ab-") as dirname:
        scratch = Path(dirname)
        baseline = scratch / "baseline"
        powered = scratch / "with-mcp"
        baseline.mkdir()
        powered.mkdir()
        (baseline / ".agents").mkdir()
        (powered / ".agents").mkdir()
        (baseline / ".agents" / "mcp_config.json").write_text(
            '{"mcpServers":{}}', encoding="utf-8"
        )
        (powered / ".agents" / "mcp_config.json").write_text(json.dumps({
            "mcpServers": {
                "historical-atlas": {
                    "command": sys.executable,
                    "args": [str(ROOT / "scripts" / "atlas_mcp.py")],
                    "env": {
                        "ATLAS_SQLITE_PATH": str(args.sqlite.resolve()),
                        "ATLAS_ARCHIGOS_PATH": str(args.archigos.resolve()),
                    },
                }
            }
        }, indent=2), encoding="utf-8")
        schema_file = scratch / "output-schema.json"
        schema_file.write_text(json.dumps(SCHEMA), encoding="utf-8")
        prompt = data["question"] + "\nReturn only the requested structured fields. Use -1 for uncomputable numbers, and insufficient_data=true if exact source data are unavailable. Do not guess."
        runs = {}
        for label, folder in (("baseline", baseline), ("with_mcp", powered)):
            result = run_once(args.agy, args.model, prompt, schema_file, folder, args.timeout)
            raw = result.pop("raw_stream", "")
            # Raw step logs may expose local paths; remain private in ignored dist.
            (destination / (label + ".ndjson")).write_text(raw, encoding="utf-8")
            result["score"] = score(result, data, with_mcp=(label == "with_mcp"))
            runs[label] = result
    report = {
        "benchmark_id": data["id"],
        "model_requested": args.model,
        "same_prompt": True,
        "fresh_sessions": True,
        "archigos_sha256": EXPECTED_SHA256,
        "gold_aggregate": data["expected"],
        "runs": runs,
        "limitation": "Other tools, global MCP profiles or permission denials may contaminate the comparison. Check used_tool_names and available_tool_names before interpreting scores.",
    }
    (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(destination / "report.json"),
        "baseline": runs["baseline"]["score"],
        "with_mcp": runs["with_mcp"]["score"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
