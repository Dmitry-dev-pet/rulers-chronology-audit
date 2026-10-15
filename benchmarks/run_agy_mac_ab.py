#!/usr/bin/env python3
"""Isolated two-lane Gemini / Historical Atlas MCP evaluation on the Mac runner.

Only an approved, already-authenticated dedicated runner account can supply
its own session; never read an unrelated user's login or a GitHub token.
No task, model, command or repository path comes from the issue text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

DENIED = [
    "read_file(*)", "write_file(*)", "list_dir(*)", "find_by_name(*)",
    "grep_search(*)", "run_command(*)", "command(*)", "unsandboxed(*)",
    "read_url(*)", "execute_url(*)", "open_browser_url(*)",
    "browser_(*)", "send_message(*)", "manage_inbox(*)",
    "schedule(*)", "run_workflow(*)", "invoke_subagent(*)",
]
SOURCE_SHA = "3e3b4092a7ac5a7e78cd86df6e6287c69027bf6fe60c9396adf136a39b1943ad"


def require(ok: bool, text: str) -> None:
    if not ok:
        raise ValueError(text)


def install_lane(root: Path, label: str, auth_file: Path, atlas: Path,
                 sqlite: Path, archigos: Path, python: Path) -> tuple[Path, Path]:
    """Isolate CLI state; only the powered lane receives one read-only tool."""
    workspace = root / label / "workspace"
    home = root / label / "home"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / ".agents").mkdir()
    (home / ".gemini" / "config").mkdir(parents=True)
    session = home / ".gemini" / "antigravity-cli"
    session.mkdir(parents=True)
    os.chmod(home, 0o700)
    os.chmod(session, 0o700)
    token = session / "antigravity-oauth-token"
    shutil.copyfile(auth_file, token)
    os.chmod(token, 0o600)
    (home / ".gemini" / "config" / "mcp_config.json").write_text(
        '{"mcpServers":{}}\n', encoding="utf-8"
    )
    policy = {
        "toolPermission": "strict",
        "allowNonWorkspaceAccess": False,
        "permissions": {
            "deny": DENIED + (["mcp(*)"] if label == "baseline" else []),
            "allow": ["mcp(historical-atlas/archigos_returnees)"]
            if label == "with_mcp" else [],
        },
    }
    (session / "settings.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
    if label == "baseline":
        mcp = {"mcpServers": {}}
    else:
        mcp = {
            "mcpServers": {
                "historical-atlas": {
                    "command": str(python),
                    "args": [str(atlas / "scripts" / "atlas_mcp_returnees.py")],
                    "env": {
                        "ATLAS_SQLITE_PATH": str(sqlite),
                        "ATLAS_ARCHIGOS_PATH": str(archigos),
                    },
                }
            }
        }
    (workspace / ".agents" / "mcp_config.json").write_text(
        json.dumps(mcp, indent=2), encoding="utf-8"
    )
    return workspace, home


def execution(cli: Path, model: str, question: str, schema: Path,
              workspace: Path, home: Path) -> dict:
    env = dict(os.environ)
    for secret in (
        "AGY_OAUTH_TOKEN_B64", "GITHUB_TOKEN", "GH_TOKEN", "GEMINI_API_KEY",
        "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT",
    ):
        env.pop(secret, None)
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["GEMINI_FORCE_FILE_STORAGE"] = "true"
    cmd = [
        str(cli), "-p", question, "--model", model, "--effort", "high",
        "--output-format", "stream-json", "--json-schema", str(schema),
        "--print-timeout", "7m",
    ]
    try:
        p = subprocess.run(
            cmd, cwd=workspace, env=env, capture_output=True,
            text=True, errors="replace", timeout=450, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "exit_code": None, "answer": None,
                "tool_calls": [], "available_tools": [], "duration_seconds": None,
                "usage": {}, "diagnostic": "timeout"}
    parsed = []
    for line in p.stdout.splitlines():
        try:
            e = json.loads(line)
            if isinstance(e, dict):
                parsed.append(e)
        except json.JSONDecodeError:
            pass
    init = next((e["init"] for e in parsed if e.get("event") == "init"), {})
    terminal = next(
        (e["result"] for e in reversed(parsed) if e.get("event") == "result"), {}
    )
    calls = [
        str(step.get("tool_name") or step.get("tool_info", {}).get("name") or "")
        for e in parsed
        if e.get("event") == "step_update"
        if isinstance(step := e.get("step_update"), dict)
        if step.get("step_type") == "tool" and step.get("state") == "DONE"
    ]
    answer = terminal.get("structured_output")
    if not isinstance(answer, dict):
        try:
            answer = json.loads(terminal.get("response") or "")
        except (json.JSONDecodeError, TypeError):
            answer = None
    stderr_lower = p.stderr.lower()
    error_text = str(terminal.get("error") or "").lower()
    diagnostic = "ok"
    if p.returncode or terminal.get("status") != "SUCCESS":
        if "authentication" in (stderr_lower + error_text) or "unauthorized" in (stderr_lower + error_text):
            diagnostic = "authentication_required"
        elif "permission" in (stderr_lower + error_text):
            diagnostic = "permission_blocked"
        else:
            diagnostic = "cli_error"
    elif "permission denied" in stderr_lower or "soft-denied" in stderr_lower:
        diagnostic = "permission_soft_denial"
    return {
        "status": terminal.get("status") or "MISSING_RESULT",
        "model_reported": init.get("model"),
        "exit_code": p.returncode,
        "answer": answer,
        "tool_calls": calls,
        "available_tools": [str(v) for v in init.get("tools", [])],
        "duration_seconds": terminal.get("duration_seconds"),
        "usage": terminal.get("usage", {}),
        "diagnostic": diagnostic,
    }


def evaluate(run: dict, expected: dict, powered: bool) -> dict:
    invoked = any("archigos_returnees" in name for name in run["tool_calls"])
    unauthorized = [
        name for name in run["tool_calls"]
        if "archigos_returnees" not in name
    ]
    a = run.get("answer")
    correct = isinstance(a, dict) and not a.get("insufficient_data", True)
    if correct:
        for field in ("return_events", "unique_country_person_keys",
                      "excluded_conflicting_identity_groups"):
            correct = correct and a.get(field) == expected[field]
        try:
            correct = correct and abs(
                float(a["mean_gap_days"]) - float(expected["mean_gap_days"])
            ) <= 0.001
        except (KeyError, TypeError, ValueError):
            correct = False
    return {
        "exact_aggregate_match": bool(correct),
        "honest_abstention": bool(isinstance(a, dict) and a.get("insufficient_data")),
        "invoked_archigos_mcp": invoked,
        "forbidden_tool_calls": unauthorized,
        "trial_valid": bool(
            run["status"] == "SUCCESS" and run["exit_code"] == 0
            and not unauthorized and (not powered or invoked)
            and run["diagnostic"] == "ok"
        ),
        "explanation": "Benchmark measures fixed source-derived numbers, not historical truth.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Explicit model ID verified on installed AGY; never falls back")
    ap.add_argument("--atlas", type=Path, required=True)
    ap.add_argument("--sqlite", type=Path, required=True)
    ap.add_argument("--archigos", type=Path, required=True)
    ap.add_argument("--auth-file", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--agy", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    import stat
    require(re.fullmatch(r"gemini-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", args.model) is not None,
            "Specify an actual installed Gemini model ID")
    require(args.auth_file.is_file() and not args.auth_file.is_symlink() and args.auth_file.stat().st_size > 0, "dedicated runner OAuth session not initialized")
    st = args.auth_file.stat()
    require(st.st_uid == os.getuid() and stat.S_IMODE(st.st_mode) & 0o077 == 0,
            "dedicated runner OAuth session must be owned by runner and private")
    require(args.atlas.is_dir() and args.sqlite.is_file(), "missing pinned atlas")
    require(args.agy.is_file() and args.python.is_file(), "missing executable")
    digest = hashlib.sha256(args.archigos.read_bytes()).hexdigest()
    require(digest == SOURCE_SHA, "Archigos checksum mismatch")
    args.work.mkdir(parents=True, exist_ok=True)
    os.chmod(args.work, 0o700)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(args.output.parent, 0o700)

    # Source-derived gold must match independently, before any model call.
    sys.path.insert(0, str(args.atlas))
    from scripts.archigos_returnees import read_archigos, calculate_returnees
    rows, _ = read_archigos(args.archigos)
    calculated = calculate_returnees(rows, limit=1)
    goldfile = json.loads(
        (args.atlas / "benchmarks" / "archigos_return_v1.json").read_text(encoding="utf-8")
    )
    expected = goldfile["expected"]
    for field in expected:
        require(
            (abs(calculated[field] - expected[field]) < 0.0005
             if isinstance(expected[field], float)
             else calculated[field] == expected[field]),
            "Pinned gold disagrees with source: " + field,
        )
    schema = {
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
    schemafile = args.work / "schema.json"
    schemafile.write_text(json.dumps(schema), encoding="utf-8")
    prompt = (
        goldfile["question"]
        + "\nReturn JSON fields from the schema. If exact source data are unavailable, "
        + "set insufficient_data=true and -1 for uncomputable numeric fields. "
        + "Do not guess. Do not read files, run commands or browse websites. "
        + "Use the designated read-only Archigos MCP tool if it is available."
    )
    results = {}
    for label in ("baseline", "with_mcp"):
        workspace, home = install_lane(
            args.work, label, args.auth_file, args.atlas,
            args.sqlite, args.archigos, args.python,
        )
        run = execution(args.agy, args.model, prompt, schemafile, workspace, home)
        if run.get("model_reported") != args.model:
            run["diagnostic"] = "model_missing_or_mismatched"
        run["evaluation"] = evaluate(run, expected, powered=(label == "with_mcp"))
        results[label] = run
    report = {
        "benchmark": goldfile["id"],
        "model": args.model,
        "source_ref": "immutable_project_action_package",
        "archigos_sha256": digest,
        "same_question": True,
        "independent_fresh_sessions": True,
        "gold": expected,
        "results": results,
        "historical_truth_verified_by_ci": False,
        "caveat": "A valid powered trial requires a real MCP invocation, not only a numerically correct guess.",
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(args.output, 0o600)
    print(json.dumps({
        "report_created": True,
        "baseline": results["baseline"]["evaluation"],
        "with_mcp": results["with_mcp"]["evaluation"],
        "diagnostics": {k: v["diagnostic"] for k, v in results.items()},
    }, ensure_ascii=False))
    if not all(r["evaluation"]["trial_valid"] for r in results.values()):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
