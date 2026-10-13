# Historical Atlas MCP: first ChatGPT connection milestone

Tracking: [Issue #67](../../issues/67) · [Original MCP #43](../../pull/43).
This **is not yet a remotely installed ChatGPT plugin**.

## First, reuse the existing research code

- Canonical Git-tracked `data/atlas/` remains authoritative.
- `scripts/atlas_mcp.py` stays the **single** domain MCP implementation. The original `stdio` mode keeps all five read-only Atlas query/evidence tools and optional private Archigos tooling.
- `scripts/atlas_mcp_http.py` creates the same MCP with the explicit `probe_only=True` allowlist. Its only advertised tool is `dataset_info`; the optional Archigos file is unconfigured. It exposes no arbitrary SQL, filesystem, historical-row read, PR mutation, or command execution.
- The image's SQLite is produced during the **build** from source, not synchronized or edited at runtime. It is bundled read-only and includes the canonical Russian atlas v1 only; the European HPM v2 projection remains separate. A passing CI does not certify historical truth.

## Reproducible container smoke

```sh
python3 -m pip install 'mcp==2.0.0'
docker build -f ops/mcp/Dockerfile -t historical-atlas-mcp:smoke .
bash ops/mcp/smoke.sh historical-atlas-mcp:smoke
```

The smoke starts a non-root, read-only container, publishes only loopback on the CI host, polls the actual MCP initialize response (not merely the published TCP port), asserts exactly one advertised tool, invokes `dataset_info`, then removes the container. No private dataset or credentials are required.

The image CI workflow verifies the PR and publishes an image tagged with the **full immutable source SHA only on a verified `main` push**. Before GHCR authentication it rebuilds and smokes the exact main commit. Do not deploy from a PR tag or from `latest`.

## VPS deployment is separately gated

The companion [infra-access PR #267](https://github.com/Dmitry-dev-pet/infra-access/pull/267) only registers the exact application and a hardened Compose template. It binds the service to **`127.0.0.1:8020` on the VPS**, without public ports, volumes, host filesystem mounts or secret inputs.

Required acceptance before production:

1. Merge the app code only after the two relevant MCP checks and full historical atlas audit are green; verify successful GHCR publication for the exact merged SHA.
2. Merge infra inventory **only after its own two validation workflows are green**. Onboard and deploy only via existing, allowlisted `infra-access` operations; independently verify health and an MCP initialize + `dataset_info` roundtrip on the VPS loopback endpoint.
3. Make an explicit second security/transport decision **before** providing a remote HTTPS route to ChatGPT: OpenAI Secure MCP Tunnel (requires owner-created `tunnel_id` and Platform runtime key), or authenticated Cloudflare HTTPS. Do not expose an unauthenticated public historical MCP, even if the first tool contains only public metadata.
4. Only after a verified private connection, update the existing personal Truthrail plugin's MCP configuration and verify actual tool discovery and one call from **the user's native tablet ChatGPT session**. Do not confuse existing GitHub tools in Truthrail with a direct historical MCP connection.
5. Maintain narrow scope and immutable historical data. A subsequent PR can add reviewed HPM source-tracing read tools, not a generic SQL executor.

The underlying transport choice does not affect the site's existing Pages build; it is a visualization consumer rather than the research product.
