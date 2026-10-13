"""Prune only stale, successful browser evidence. Never touch other artifacts."""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY = "Dmitry-dev-pet/rulers-chronology-audit"
ARTIFACT_NAME = "smuta-browser-evidence"
KEEP_MAIN_RUNS = 3
MIN_AGE_HOURS = 3
MAX_DELETES = 250


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def select_deletions(artifacts, runs_by_id, open_pr_heads, now):
    """Select deletions conservatively; missing metadata raises rather than guesses."""
    successful_main = [
        a for a in artifacts
        if a.get("name") == ARTIFACT_NAME
        and runs_by_id[int(a["workflow_run"]["id"])].get("conclusion") == "success"
        and runs_by_id[int(a["workflow_run"]["id"])].get("event") == "push"
        and runs_by_id[int(a["workflow_run"]["id"])].get("head_branch") == "main"
    ]
    main_runs = list(dict.fromkeys(
        int(a["workflow_run"]["id"])
        for a in sorted(successful_main, key=lambda a: a["created_at"], reverse=True)
    ))
    protected_main = set(main_runs[:KEEP_MAIN_RUNS])
    cutoff = now - timedelta(hours=MIN_AGE_HOURS)
    candidates, reasons = [], Counter()
    for a in artifacts:
        if a.get("name") != ARTIFACT_NAME:
            reasons["other_name"] += 1
            continue
        if a.get("expired") or not a.get("workflow_run"):
            reasons["expired_or_missing_run"] += 1
            continue
        run_id = int(a["workflow_run"]["id"])
        run = runs_by_id[run_id]
        if parse_time(a["created_at"]) > cutoff:
            reasons["newer_than_3_hours"] += 1
        elif run.get("status") != "completed" or run.get("conclusion") != "success":
            reasons["non_success_or_unfinished"] += 1
        elif run.get("event") == "push" and run.get("head_branch") == "main":
            if run_id in protected_main:
                reasons["last_three_main_successes"] += 1
            else:
                candidates.append(a)
        elif run.get("event") == "pull_request":
            if not run.get("head_branch") or run["head_branch"] in open_pr_heads:
                reasons["open_or_unknown_pr"] += 1
            else:
                candidates.append(a)
        else:
            reasons["unknown_event_or_branch"] += 1
    if len(candidates) > MAX_DELETES:
        raise RuntimeError(f"Fail closed: {len(candidates)} candidates exceed cap {MAX_DELETES}")
    return sorted(candidates, key=lambda a: a["created_at"]), reasons


class GitHubAPI:
    def __init__(self, token):
        if not token:
            raise RuntimeError("Missing GITHUB_TOKEN")
        self.token = token
        self.root = f"https://api.github.com/repos/{REPOSITORY}"

    def request(self, path, method="GET"):
        req = Request(self.root + path, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "atlas-artifact-pruner",
        })
        with urlopen(req, timeout=30) as response:
            data = response.read()
        return json.loads(data) if data else None

    def pages(self, path, key):
        result = []
        for page in range(1, 51):
            sep = "&" if "?" in path else "?"
            obj = self.request(f"{path}{sep}{urlencode({'per_page': 100, 'page': page})}")
            chunk = obj if key is None else obj[key]
            result.extend(chunk)
            if len(chunk) < 100:
                return result
        raise RuntimeError("Fail closed: over 50 pages")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if os.getenv("GITHUB_REPOSITORY") != REPOSITORY:
        raise RuntimeError("Repo restriction violated")
    if args.apply and (
        os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}
    ):
        raise RuntimeError("Deletion requires main and trusted push/dispatch event")
    api = GitHubAPI(os.environ.get("GITHUB_TOKEN"))
    artifacts = api.pages(f"/actions/artifacts?{urlencode({'name': ARTIFACT_NAME})}", "artifacts")
    prs = api.pages("/pulls?state=open", None)
    open_pr_heads = {
        pr.get("head", {}).get("ref") for pr in prs
        if (pr.get("head", {}).get("repo") or {}).get("full_name") == REPOSITORY
    }
    runs = {
        int(a["workflow_run"]["id"]): None for a in artifacts
        if a.get("name") == ARTIFACT_NAME and a.get("workflow_run")
    }
    for run_id in runs:
        runs[run_id] = api.request(f"/actions/runs/{run_id}")
    selected, reasons = select_deletions(artifacts, runs, open_pr_heads, datetime.now(timezone.utc))
    processed, errors = [], []
    for a in selected:
        if args.apply:
            try:
                api.request(f"/actions/artifacts/{a['id']}", method="DELETE")
            except HTTPError as exc:
                errors.append({"artifact_id": a["id"], "http_status": exc.code})
                break
            print(f"DELETED artifact={a['id']} run={a['workflow_run']['id']} bytes={a['size_in_bytes']}", flush=True)
        processed.append(a)
    total = sum(int(a.get("size_in_bytes") or 0) for a in processed)
    report = {
        "repository": REPOSITORY, "artifact_name": ARTIFACT_NAME,
        "applied": args.apply, "deleted_or_planned": len(processed),
        "bytes_deleted_or_planned": total, "mib_deleted_or_planned": round(total / 1048576, 2),
        "protected": dict(reasons), "artifact_ids": [a["id"] for a in processed],
        "errors": errors, "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    Path("artifact-cleanup-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## Evidence cleanup: {'APPLY' if args.apply else 'DRY RUN'}\n\n")
            f.write(f"Deleted/planned: **{len(processed)}**; storage: **{report['mib_deleted_or_planned']} MiB**.\n\n")
            f.write(f"Protected groups: {json.dumps(dict(reasons))}\n\n")
            f.write(f"Errors: {len(errors)}. Only successful duplicate browser evidence is eligible.\n")
    if errors:
        raise RuntimeError("Stopped after an artifact deletion error")


if __name__ == "__main__":
    main()
