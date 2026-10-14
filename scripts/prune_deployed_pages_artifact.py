#!/usr/bin/env python3
"""Delete this run's GitHub Pages artifact only after a successful deployment.

The publish job has no Actions:write authority. Its dependent cleanup job
receives a repository-scoped token and rechecks exact immutable artifact ID.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPOSITORY = "Dmitry-dev-pet/rulers-chronology-audit"
ARTIFACT_NAME = "github-pages"
MAX_PAGES_ARTIFACT_SIZE = 1_073_741_824


def require_published_context(env: dict) -> dict:
    if env.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("Cleanup must target this one repository")
    if env.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Cleanup must run only on reviewed main")
    if env.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}:
        raise ValueError("Cannot cleanup a PR/fork artifact")
    if env.get("PUBLISH_RESULT") != "success":
        raise ValueError("Pages deployment must have succeeded")
    run_id = env.get("GITHUB_RUN_ID", "")
    artifact_id = env.get("PAGES_ARTIFACT_ID", "")
    commit = env.get("GITHUB_SHA", "")
    if not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("Invalid publisher run ID")
    if not artifact_id.isdecimal() or int(artifact_id) <= 0:
        raise ValueError("Missing exact artifact ID from upload-pages-artifact")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid published main commit")
    url = urlsplit(env.get("DEPLOYED_PAGE_URL", ""))
    if (url.scheme != "https" or not url.hostname
            or url.username or url.password or len(env.get("DEPLOYED_PAGE_URL", "")) > 2048):
        raise ValueError("Missing successful HTTPS Pages deployment URL")
    return {
        "repo": REPOSITORY,
        "run_id": int(run_id),
        "artifact_id": int(artifact_id),
        "head_sha": commit,
        "site_url": env["DEPLOYED_PAGE_URL"],
    }


def verify_exact_pages_artifact(artifact: dict, receipt: dict) -> None:
    meta_run = artifact.get("workflow_run") or {}
    if (
        artifact.get("id") != receipt["artifact_id"]
        or artifact.get("name") != ARTIFACT_NAME
        or artifact.get("expired") is not False
        or meta_run.get("id") != receipt["run_id"]
        or meta_run.get("head_branch") != "main"
        or meta_run.get("head_sha") != receipt["head_sha"]
    ):
        raise ValueError("Artifact does not match the deployed run and commit")
    length = artifact.get("size_in_bytes")
    if type(length) is not int or not 0 < length <= MAX_PAGES_ARTIFACT_SIZE:
        raise ValueError("Unexpected Pages artifact byte count")


def request(method: str, artifact_id: int, token: str):
    if not token:
        raise ValueError("Repository-scoped GITHUB_TOKEN is required")
    uri = f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}"
    req = Request(
        uri, method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "rulers-pages-verified-consumption-cleanup",
        },
    )
    with urlopen(req, timeout=30) as result:
        raw = result.read()
        if method == "DELETE":
            if result.status != 204:
                raise RuntimeError("GitHub artifact delete response was not 204")
            return 204
        return json.loads(raw)


def cleanup_after_deploy(receipt: dict, token: str, api=request) -> dict:
    target = receipt["artifact_id"]
    try:
        existing = api("GET", target, token)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        return {
            **receipt,
            "artifact_name": ARTIFACT_NAME,
            "result": "already-absent",
            "delete_http_status": None,
            "verified_after_delete": True,
        }
    verify_exact_pages_artifact(existing, receipt)
    status = api("DELETE", target, token)
    if status != 204:
        raise RuntimeError("GitHub refused to delete the verified Pages artifact")
    try:
        api("GET", target, token)
    except HTTPError as exc:
        if exc.code != 404:
            raise
    else:
        raise RuntimeError("Pages artifact still exists after deletion")
    return {
        **receipt,
        "artifact_name": ARTIFACT_NAME,
        "result": "deleted",
        "delete_http_status": 204,
        "verified_after_delete": True,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    receipt = require_published_context(os.environ)
    result = cleanup_after_deploy(receipt, os.environ.get("GH_TOKEN", ""))
    print("PAGES_ARTIFACT_CONSUMED " + json.dumps(result, sort_keys=True), flush=True)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write("## Published Pages artifact cleanup\n\n")
        f.write(f"- Successfully deployed: {receipt['site_url']}\n")
        f.write(f"- Producer run: {receipt['run_id']}\n")
        f.write(f"- Artifact ID: {receipt['artifact_id']}\n")
        f.write(f"- Outcome: {result['result']}\n")
        f.write("- No source code, Releases or cached build files were deleted.\n")


if __name__ == "__main__":
    main()
