#!/usr/bin/env python3
"""Paired AGY / Gemini trial: no MCP vs canonical Historical Atlas over stdio.

Runs under a dedicated, already authenticated Mac runner account. No API key,
user OAuth export, public tunnel, Archigos source file or remote MCP is needed.
Only the reviewed CLI arguments may select a model, paths or question set;
never construct a command from an issue body or model response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "benchmarks" / "rulers_questions_v1.json"
TOOLS = (
    "dataset_info", "search_rulers", "get_timeline",
    "compare_rulers", "get_evidence",
)
DENIED = [
    "read_file(*)", "write_file(*)", "list_dir(*)", "find_by_name(*)",
    "grep_search(*)", "run_command(*)", "command(*)", "unsandboxed(*)",
    "read_url(*)", "execute_url(*)", "open_browser_url(*)",
    "browser_(*)", "send_message(*)", "manage_inbox(*)",
    "schedule(*)", "run_workflow(*)", "invoke_subagent(*)",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "uncertainty": {"type": "string"},
        "source_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "uncertainty", "source_refs"],
}
INSTRUCTION = (
    "Ответь на русском языке. Различай юридическую должность, регентство, "
    "коллективное управление и фактическое влияние. Не угадывай пропущенные "
    "данные, указывай неопределённость. Если доступен инструмент Historical "
    "Atlas, самостоятельно проверь по нему факты и источники; если он "
    "недоступен, не утверждай, что использовал его. Не используй интернет, "
    "файлы или какие-либо другие инструменты. Верни JSON с полями answer "
    "(развёрнутый ответ), uncertainty (оговорки), source_refs (только реально "
    "проверенные ссылки или идентификаторы; иначе пустой список).\n\n"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit(atlas: Path) -> str:
    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(atlas), *args],
            capture_output=True, text=True, check=False, timeout=15,
        )
    head = git("rev-parse", "HEAD")
    require(head.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", head.stdout.strip()) is not None,
            "Atlas directory must be a Git checkout at a concrete commit")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    require(dirty.returncode == 0 and not dirty.stdout.strip(),
            "Atlas has tracked local modifications; pin a clean Git checkout")
    return head.stdout.strip()


def load_questions(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions", [])
    require(data.get("id") == "russian_rulers_10_v1" and len(questions) == 10,
            "Unexpected/floating question set; expected 10 frozen v1 questions")
    ids = [q.get("id") for q in questions]
    require(len(set(ids)) == 10 and all(
        re.fullmatch(r"r\d\d", k or "") and isinstance(q.get("question"), str)
        and 30 <= len(q["question"]) <= 500 for k, q in zip(ids, questions)
    ), "Invalid question IDs/text")
    return data


def validate_auth(auth: Path) -> None:
    require(auth.is_file() and not auth.is_symlink(), "Missing dedicated runner OAuth file")
    info = auth.stat()
    require(info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) & 0o077 == 0 and info.st_size > 0,
            "OAuth file must belong to the dedicated runner and be mode 0600")


def list_models(agy: Path) -> set[str]:
    """Ask the *installed* CLI; never infer model slugs from documentation."""
    proc = subprocess.run([str(agy), "models"], capture_output=True,
                          text=True, errors="replace", timeout=25, check=False)
    require(proc.returncode == 0, "Could not list available models with installed AGY")
    slugs = set(re.findall(r"\bgemini-[A-Za-z0-9][A-Za-z0-9._-]*\b", proc.stdout))
    require(bool(slugs), "No Gemini model IDs parsed from `agy models`; inspect runner CLI manually")
    return slugs


def install_lane(root: Path, label: str, auth_file: Path, atlas: Path,
                 sqlite: Path, python: Path) -> tuple[Path, Path]:
    """Isolated empty workspace and HOME; allow exactly five local MCP tools."""
    require(label in ("baseline", "with_mcp"), "Unknown lane")
    workspace = root / label / "workspace"
    home = root / label / "home"
    workspace.mkdir(parents=True, exist_ok=False)
    (workspace / ".agents").mkdir()
    session = home / ".gemini" / "antigravity-cli"
    session.mkdir(parents=True)
    (home / ".gemini" / "config").mkdir()
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
            "allow": (
                [f"mcp(historical-atlas/{name})" for name in TOOLS]
                if label == "with_mcp" else []
            ),
        },
    }
    (session / "settings.json").write_text(
        json.dumps(policy, indent=2) + "\n", encoding="utf-8"
    )
    services = {}
    if label == "with_mcp":
        services["historical-atlas"] = {
            "command": str(python),
            "args": [str(atlas / "scripts" / "atlas_mcp_rulers.py")],
            "env": {"ATLAS_SQLITE_PATH": str(sqlite)},
        }
    (workspace / ".agents" / "mcp_config.json").write_text(
        json.dumps({"mcpServers": services}, indent=2) + "\n",
        encoding="utf-8",
    )
    return workspace, home


def cli_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "AGY_OAUTH_TOKEN_B64", "GITHUB_TOKEN", "GH_TOKEN", "GEMINI_API_KEY",
        "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT",
        "ATLAS_ARCHIGOS_PATH", "ATLAS_SQLITE_PATH",
    ):
        env.pop(key, None)
    env.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "GEMINI_FORCE_FILE_STORAGE": "true",
    })
    return env


def name_of_tool(obj: object) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return str(obj.get("name") or obj.get("tool_name") or "")
    return ""


def atlas_tool(name: str) -> str | None:
    value = name.lower().strip()
    if value in TOOLS:
        return value
    if "historical-atlas" not in value and "historical_atlas" not in value:
        return None
    for tool in TOOLS:
        if value.endswith(("/" + tool, "__" + tool, "." + tool)):
            return tool
    return None


def mcp_like(name: str) -> bool:
    name = name.lower()
    return "mcp" in name or "historical-atlas" in name or "historical_atlas" in name


def parse_events(raw: str) -> dict:
    events = []
    for line in raw.splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
        except json.JSONDecodeError:
            pass
    init = next((x.get("init", {}) for x in events if x.get("event") == "init"), {})
    final = next((x.get("result", {}) for x in reversed(events) if x.get("event") == "result"), {})
    steps = []
    for event in events:
        if event.get("event") != "step_update":
            continue
        s = event.get("step_update") or {}
        if not isinstance(s, dict) or s.get("step_type") != "tool":
            continue
        name = str(s.get("tool_name") or (s.get("tool_info") or {}).get("name") or "")
        state = str(s.get("state") or "").upper()
        if name and state:
            steps.append({"name": name, "state": state})
    answer = final.get("structured_output")
    if not isinstance(answer, dict):
        try:
            answer = json.loads(final.get("response") or "")
        except (ValueError, TypeError):
            answer = {}
    if not isinstance(answer, dict):
        answer = {}
    usage = final.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    return {
        "status": final.get("status") or "MISSING_RESULT",
        "model_reported": init.get("model"),
        "available_tools": [name_of_tool(x) for x in init.get("tools", [])],
        "tool_events": steps,
        "answer": {
            "answer": str(answer.get("answer") or "")[:10000],
            "uncertainty": str(answer.get("uncertainty") or "")[:3000],
            "source_refs": [
                str(x)[:300] for x in (answer.get("source_refs") or [])[:30]
            ] if isinstance(answer.get("source_refs"), list) else [],
        },
        "duration_seconds": final.get("duration_seconds"),
        "usage": {k: v for k, v in usage.items() if isinstance(v, (int, float))},
        "reported_error": bool(final.get("error")),
    }


def execute(agy: Path, model: str, question: str, schema: Path,
            workspace: Path, home: Path, timeout: int) -> dict:
    cmd = [
        str(agy), "-p", INSTRUCTION + question, "--model", model,
        "--output-format", "stream-json",
        "--json-schema", str(schema), "--print-timeout", f"{timeout}s",
    ]
    before = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=workspace, env=cli_env(home), capture_output=True,
            text=True, errors="replace", timeout=timeout + 30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT", "model_reported": None,
            "available_tools": [], "tool_events": [], "answer": {},
            "exit_code": None, "duration_seconds": None,
            "wall_seconds": round(time.monotonic() - before, 2),
            "diagnostic": "timeout",
        }
    result = parse_events(p.stdout)
    result["exit_code"] = p.returncode
    result["wall_seconds"] = round(time.monotonic() - before, 2)
    errors = (p.stderr + " " + p.stdout[-1000:]).lower()
    if ("unknown model" in errors or "model not found" in errors
            or "unsupported model" in errors or "invalid model" in errors):
        diagnosis = "model_unavailable"
    elif ("unauthorized" in errors or "authentication" in errors):
        diagnosis = "authentication_required"
    elif "permission denied" in errors or "soft-denied" in errors:
        diagnosis = "permission_denied"
    elif p.returncode or result["status"] != "SUCCESS":
        diagnosis = "cli_error"
    else:
        diagnosis = "ok"
    result["diagnostic"] = diagnosis
    return result


def evaluate(run: dict, model: str, powered: bool) -> dict:
    completed = [s["name"] for s in run["tool_events"] if s["state"] == "DONE"]
    attempted = [s["name"] for s in run["tool_events"]]
    other_calls = [name for name in attempted if atlas_tool(name) is None]
    mcp_calls = [atlas_tool(name) for name in completed if atlas_tool(name)]
    visible = run["available_tools"]
    problems = []
    if run.get("status") != "SUCCESS" or run.get("exit_code") != 0:
        problems.append("execution_failed")
    if run.get("diagnostic") != "ok":
        problems.append(run.get("diagnostic") or "unknown_error")
    if run.get("model_reported") != model:
        problems.append("reported_model_missing_or_mismatched")
    if not run.get("answer", {}).get("answer"):
        problems.append("missing_structured_answer")
    if other_calls:
        problems.append("other_tool_called")
    if powered:
        if not mcp_calls:
            problems.append("no_completed_atlas_mcp_call")
        if any(mcp_like(x) and atlas_tool(x) is None for x in visible):
            problems.append("unapproved_mcp_advertised")
    else:
        if attempted:
            problems.append("baseline_called_tool")
        if any(mcp_like(x) for x in visible):
            problems.append("baseline_mcp_advertised")
    return {
        "trial_valid": not problems,
        "issues": list(dict.fromkeys(problems)),
        "completed_atlas_tools": mcp_calls,
        "other_tool_calls": other_calls,
        "note": "No independent historical-accuracy score is asserted.",
    }


def write_report(path: Path, report: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    temp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--atlas", type=Path, default=ROOT)
    ap.add_argument("--sqlite", type=Path, default=ROOT / "dist" / "atlas.sqlite")
    ap.add_argument("--agy", type=Path, required=True)
    ap.add_argument("--python", type=Path, default=Path(sys.executable))
    ap.add_argument("--auth-file", type=Path, required=True)
    ap.add_argument("--model", required=True, help="Verified ID from installed AGY; no fallback")
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--max-questions", type=int, default=10, help="1 for smoke; 10 for full experiment")
    ap.add_argument("--expected-atlas-commit", help="Optional known HEAD SHA")
    ap.add_argument("--output", type=Path, default=ROOT / "dist" / "agy-rulers-ab" / "report.json")
    args = ap.parse_args()

    require(re.fullmatch(r"gemini-[A-Za-z0-9][A-Za-z0-9._-]{0,79}", args.model) is not None,
            "Pass a real Gemini model ID from the installed AGY (no hardcoded default)")
    require(60 <= args.timeout <= 900 and 1 <= args.max_questions <= 10,
            "timeout must be 60..900s and max-questions must be 1..10")
    atlas = args.atlas.resolve(strict=True)
    sqlite = args.sqlite.resolve(strict=True)
    agy = args.agy.resolve(strict=True)
    python = args.python.resolve(strict=True)
    auth = args.auth_file.absolute()
    require(agy.is_file() and os.access(agy, os.X_OK), "AGY executable is missing/not executable")
    require(python.is_file() and os.access(python, os.X_OK), "Python executable is missing/not executable")
    require(sqlite.is_file(), "Build a canonical local atlas.sqlite first")
    require((atlas / "scripts" / "atlas_mcp_rulers.py").is_file(),
            "Pinned Atlas checkout missing read-only stdio entrypoint")
    validate_auth(auth)
    models = list_models(agy)
    require(args.model in models,
            "Chosen --model is not in the installed `agy models` list; refusing fallback")
    commit = git_commit(atlas)
    if args.expected_atlas_commit:
        require(args.expected_atlas_commit == commit, "Atlas HEAD does not match expected pinned SHA")

    sys.path.insert(0, str(atlas))
    from scripts.atlas_mcp_query import AtlasQuery
    info = AtlasQuery(sqlite).dataset_info()
    require(info.get("dataset") == "canonical-rulers-atlas-v1",
            "Not the canonical Russian rulers dataset")
    questions = load_questions(QUESTIONS)
    db_digest = sha256(sqlite)
    spec_digest = sha256(QUESTIONS)
    output = args.output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output.parent, 0o700)
    require(not output.is_symlink(), "Output must not be a symlink")
    cli_version = subprocess.run(
        [str(agy), "--version"], capture_output=True, text=True,
        errors="replace", timeout=15, check=False,
    )
    report = {
        "benchmark_id": questions["id"],
        "model_requested": args.model,
        "model_verified_in_installed_agy_list": True,
        "available_model_count": len(models),
        "agy_version": (cli_version.stdout or cli_version.stderr).splitlines()[:1],
        "atlas_commit": commit,
        "atlas_sqlite_sha256": db_digest,
        "questions_sha256": spec_digest,
        "dataset_info": info,
        "same_prompt_and_model": True,
        "fresh_isolated_sessions_per_question": True,
        "archigos_required": False,
        "chatgpt_plugin_tunnel_modified": False,
        "historical_accuracy_scored": False,
        "requested_questions": args.max_questions,
        "results": [],
        "limitations": [
            "Local database SHA does not prove identity with the ChatGPT plugin dataset.",
            "Source citations and factual accuracy require independent historical review.",
        ],
    }
    schema_path = output.parent / "output-schema.json"
    schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    os.chmod(schema_path, 0o600)
    stop = False
    try:
        for case in questions["questions"][:args.max_questions]:
            pair = {"id": case["id"], "question": case["question"], "runs": {}}
            report["results"].append(pair)
            for label in ("baseline", "with_mcp"):
                # Fresh HOME+workspace for each trial, removed after completion.
                with tempfile.TemporaryDirectory(prefix="atlas-agy-", dir=output.parent) as temp:
                    workspace, home = install_lane(
                        Path(temp), label, auth, atlas, sqlite, python,
                    )
                    run = execute(
                        agy, args.model, case["question"], schema_path,
                        workspace, home, args.timeout,
                    )
                run["evaluation"] = evaluate(run, args.model, powered=label == "with_mcp")
                pair["runs"][label] = run
                if (run.get("diagnostic") in ("model_unavailable", "authentication_required")
                        or "reported_model_missing_or_mismatched" in run["evaluation"]["issues"]):
                    # Fail closed instead of silently selecting another model.
                    stop = True
                    break
            write_report(output, report)
            if stop:
                break
    finally:
        report["atlas_sqlite_hash_unchanged"] = sha256(sqlite) == db_digest
        report["completed_question_pairs"] = sum(
            len(pair["runs"]) == 2 for pair in report["results"]
        )
        report["all_trials_valid"] = (
            report["atlas_sqlite_hash_unchanged"]
            and report["completed_question_pairs"] == args.max_questions
            and all(run["evaluation"]["trial_valid"]
                    for pair in report["results"] for run in pair["runs"].values())
        )
        write_report(output, report)
    print(json.dumps({
        "report": str(output),
        "completed_question_pairs": report["completed_question_pairs"],
        "all_trials_valid": report["all_trials_valid"],
        "model": args.model,
        "diagnostics": {
            pair["id"]: {lane: run["diagnostic"] for lane, run in pair["runs"].items()}
            for pair in report["results"]
        },
    }, ensure_ascii=False))
    if not report["all_trials_valid"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
