"""Fail-closed review-only checks for the outbound Historical Atlas tunnel."""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "ops/mcp/tunnel.compose.review.yml"
RUNBOOK = ROOT / "ops/mcp/SECURE_TUNNEL.md"


class SecureTunnelReferenceTests(unittest.TestCase):
    def setUp(self):
        self.overlay = OVERLAY.read_text(encoding="utf-8")
        self.runbook = RUNBOOK.read_text(encoding="utf-8")

    def test_outbound_only_and_no_public_mcp(self):
        o = self.overlay
        self.assertIn("MCP_SERVER_URL: http://app:8765/mcp", o)
        self.assertIn('127.0.0.1:8021:8080', o)
        self.assertIn('HEALTH_LISTEN_ADDR: ":8080"', o)
        self.assertNotIn("0.0.0.0:8021", o)
        self.assertNotIn("0.0.0.0:8765", o)
        self.assertNotIn("network_mode: host", o)
        self.assertNotIn("privileged: true", o)
        self.assertNotIn("/var/run/docker.sock", o)
        self.assertIn("condition: service_started", o)

    def test_never_store_runtime_key_in_source_or_environment(self):
        o = self.overlay
        self.assertIn("ATLAS_TUNNEL_RUNTIME_KEY_FILE", o)
        self.assertIn("atlas_openai_tunnel_runtime_key:", o)
        self.assertIn(
            "--control-plane.api-key=file:/run/secrets/atlas_openai_tunnel_runtime_key",
            o,
        )
        self.assertNotIn("CONTROL_PLANE_API_KEY:", o)
        self.assertNotIn("OPENAI_API_KEY:", o)
        self.assertNotIn("sk-proj-", o)
        self.assertIn("ATLAS_TUNNEL_ID:", o)
        self.assertIn("ATLAS_TUNNEL_IMAGE_REF:", o)
        self.assertIn("ghcr.io/openai/tunnel-client", self.runbook)

    def test_nonroot_readonly_and_capability_drop(self):
        o = self.overlay
        self.assertIn("read_only: true", o)
        self.assertIn("cap_drop:\n      - ALL", o)
        self.assertIn("no-new-privileges:true", o)
        self.assertIn('user: "65532:65532"', o)
        self.assertIn("/tmp:rw,nosuid,nodev", o)
        self.assertNotIn("latest", o)

    def test_scope_stays_metadata_only_and_transport_not_live(self):
        d = self.runbook
        self.assertIn("design / review only", d)
        self.assertIn("dataset_info", d)
        self.assertIn("defined_not_connected", d)
        self.assertIn("No external MCP connection has been activated", d)
        self.assertIn("No inbound firewall port", d)
        self.assertIn("create a **single dedicated** Historical Atlas tunnel", d)
        self.assertIn("Tunnels Read + Use", d)
        self.assertIn("infra-access", d)
        self.assertIn("operations-history", d)
        self.assertIn("actual MCP protocol", d)
        self.assertNotIn("ATLAS_TUNNEL_RUNTIME_API_KEY=", d)

    def test_tunnel_id_is_a_platform_provisioned_value(self):
        self.assertIn("CONTROL_PLANE_TUNNEL_ID", self.overlay)
        self.assertNotRegex(
            self.overlay,
            r"tunnel_[a-z0-9]{32}",
        )
        self.assertRegex(
            self.runbook, r"tunnel_<32 lower-case alphanumeric>",
        )


if __name__ == "__main__":
    unittest.main()
