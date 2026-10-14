"""Atlas structural and browser checks run without storing Actions artifacts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CIArtifactPolicyTests(unittest.TestCase):
    def test_audit_stays_executable_but_does_not_upload_cache(self):
        audit = (ROOT / ".github/workflows/soviet-audit.yml").read_text()
        self.assertNotIn("actions/upload-artifact@", audit)
        self.assertIn("Record result in job summary", audit)
        self.assertIn("Build compatible report and normalized database", audit)
        self.assertIn("Test actual Chromium navigation", audit)
        self.assertIn("Test experimental P4 graph", audit)
        self.assertIn("Screenshots and full build output are temporary CI files", audit)

    def test_pages_handoff_is_explicit_exception(self):
        pages = (ROOT / ".github/workflows/publish-pages.yml").read_text()
        self.assertIn("actions/upload-pages-artifact@", pages)
        self.assertIn("actions/deploy-pages@", pages)

if __name__ == "__main__":
    unittest.main()
