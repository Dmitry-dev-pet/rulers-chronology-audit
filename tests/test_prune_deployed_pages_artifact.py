"""Prove Pages cleanup cannot occur before a verified published deployment."""
from copy import deepcopy
from pathlib import Path
import unittest
from urllib.error import HTTPError

from scripts.prune_deployed_pages_artifact import (
    REPOSITORY,
    cleanup_after_deploy,
    require_published_context,
    verify_exact_pages_artifact,
)

COMMIT = "a" * 40
RUN_ID = 1234567
ARTIFACT_ID = 9876543


def env(**changes):
    result = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "push",
        "PUBLISH_RESULT": "success",
        "GITHUB_RUN_ID": str(RUN_ID),
        "PAGES_ARTIFACT_ID": str(ARTIFACT_ID),
        "GITHUB_SHA": COMMIT,
        "DEPLOYED_PAGE_URL": "https://example.github.io/rulers-chronology-audit/",
    }
    result.update(changes)
    return result


def meta(**changes):
    artifact = {
        "id": ARTIFACT_ID,
        "name": "github-pages",
        "expired": False,
        "size_in_bytes": 123456,
        "workflow_run": {
            "id": RUN_ID,
            "head_branch": "main",
            "head_sha": COMMIT,
        },
    }
    artifact.update(changes)
    return artifact


class PagesArtifactCleanupTests(unittest.TestCase):
    def test_requires_actual_deployment_and_owned_main(self):
        claim = require_published_context(env())
        self.assertEqual(claim["artifact_id"], ARTIFACT_ID)
        self.assertEqual(claim["run_id"], RUN_ID)
        for diff in (
            {"GITHUB_REPOSITORY": "different/repo"},
            {"GITHUB_REF": "refs/heads/feature"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"PUBLISH_RESULT": "failure"},
            {"PUBLISH_RESULT": "skipped"},
            {"PAGES_ARTIFACT_ID": ""},
            {"PAGES_ARTIFACT_ID": "123;bad"},
            {"GITHUB_RUN_ID": "0"},
            {"GITHUB_SHA": "short"},
            {"DEPLOYED_PAGE_URL": ""},
            {"DEPLOYED_PAGE_URL": "http://example.github.io/site"},
            {"DEPLOYED_PAGE_URL": "https://user:pass@example.github.io/site"},
        ):
            with self.subTest(diff=diff), self.assertRaises(ValueError):
                require_published_context(env(**diff))

    def test_artifact_must_be_exact_current_run_with_pinned_main_sha(self):
        claim = require_published_context(env())
        verify_exact_pages_artifact(meta(), claim)
        for altered in (
            {"id": ARTIFACT_ID + 1},
            {"name": "soviet-chronology-report"},
            {"expired": True},
            {"size_in_bytes": 0},
            {"size_in_bytes": 2_000_000_000},
            {"size_in_bytes": "4096"},
            {"workflow_run": {"id": 999, "head_branch": "main", "head_sha": COMMIT}},
            {"workflow_run": {"id": RUN_ID, "head_branch": "feature", "head_sha": COMMIT}},
            {"workflow_run": {"id": RUN_ID, "head_branch": "main", "head_sha": "b" * 40}},
            {"workflow_run": None},
        ):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                verify_exact_pages_artifact(meta(**altered), claim)

    def test_success_deletes_exact_artifact_and_verifies_404(self):
        claim = require_published_context(env())
        calls = []
        removed = False

        def api(method, artifact_id, token):
            nonlocal removed
            self.assertEqual(artifact_id, ARTIFACT_ID)
            self.assertEqual(token, "repo-scoped-token")
            calls.append(method)
            if method == "GET":
                if removed:
                    raise HTTPError("https://api.github.com", 404, "gone", {}, None)
                return meta()
            if method == "DELETE":
                removed = True
                return 204
            raise AssertionError("Unsupported method")

        result = cleanup_after_deploy(claim, "repo-scoped-token", api)
        self.assertEqual(result["result"], "deleted")
        self.assertEqual(result["delete_http_status"], 204)
        self.assertEqual(calls, ["GET", "DELETE", "GET"])

    def test_missing_artifact_id_is_noop_but_not_false_204(self):
        claim = require_published_context(env())
        calls = []

        def api(method, artifact_id, token):
            calls.append(method)
            raise HTTPError("https://api.github.com", 404, "gone", {}, None)

        result = cleanup_after_deploy(claim, "repo-token", api)
        self.assertEqual(result["result"], "already-absent")
        self.assertIsNone(result["delete_http_status"])
        self.assertEqual(calls, ["GET"])

    def test_wrong_metadata_or_delete_error_never_claims_success(self):
        claim = require_published_context(env())
        calls = []

        def mismatched(method, artifact_id, token):
            calls.append(method)
            if method == "GET":
                return meta(name="other-name")
            raise AssertionError("Must never call DELETE")

        with self.assertRaises(ValueError):
            cleanup_after_deploy(claim, "repo", mismatched)
        self.assertEqual(calls, ["GET"])

        def bad_delete(method, artifact_id, token):
            if method == "GET":
                return meta()
            return 403

        with self.assertRaises(RuntimeError):
            cleanup_after_deploy(claim, "repo", bad_delete)

    def test_workflow_keeps_publisher_unprivileged_and_cleanup_separate(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/publish-pages.yml").read_text()
        self.assertIn("id: pages-artifact", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertIn("pages_artifact_id: ${{ steps.pages-artifact.outputs.artifact_id }}", workflow)
        self.assertIn("deploy_url: ${{ steps.publish.outputs.page_url }}", workflow)
        self.assertIn("needs: publish", workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("scripts/prune_deployed_pages_artifact.py", workflow)
        self.assertIn("needs.publish.result == 'success'", workflow)
        self.assertLess(workflow.index("actions/deploy-pages@"), workflow.index("  cleanup-deployed-artifact:"))
        self.assertNotIn("artifacts/delete-all", workflow)


if __name__ == "__main__":
    unittest.main()
