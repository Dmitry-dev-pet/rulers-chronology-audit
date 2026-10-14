# Secure MCP Tunnel for the private Historical Atlas

Status: **design / review only**. No external MCP connection has been activated
by this file. The existing VPS runtime remains `127.0.0.1:8020` and
`historical-atlas-mcp` continues to offer **only** `dataset_info`.
Do not report that the entire historical research API is available in ChatGPT.

## Decision and trust boundaries

Prefer OpenAI Secure MCP Tunnel over a publicly routable HTTPS proxy for
this *personal* ChatGPT integration. `tunnel-client` opens an outbound HTTPS
connection to OpenAI, then forwards received MCP requests to
`http://app:8765/mcp` **inside the same private Docker Compose network**
as the already-running Atlas service. The host mapping
`127.0.0.1:8020:8765` stays unchanged. No inbound firewall port,
public Cloudflare hostname, or unauthenticated MCP endpoint is created.

**This is a transport, not a new autonomous agent or Truthrail source
of truth.** The repository still owns immutable application data and
the `infra-access` project registry remains authoritative for the
VPS operation. The personal Truthrail plugin must not receive transport
credentials.

Upstream client: `openai/tunnel-client`, official release
[`v0.0.16`](https://github.com/openai/tunnel-client/releases/tag/v0.0.16)
(published 6 Oct 2026). Resolve and verify an **exact OCI digest** before
any VPS deployment; production must set `ATLAS_TUNNEL_IMAGE_REF` to
`ghcr.io/openai/tunnel-client@sha256:<verified-64-hex>`. Do not use
`latest` or silently substitute another publisher. The release
documentation recommends `gh attestation verify oci://... -R openai/tunnel-client`.

## Owner-provisioned Platform identifiers

From the same OpenAI account/workspace intended for ChatGPT:

1. Open [OpenAI Platform — Tunnels](https://platform.openai.com/settings/organization/tunnels),
   create a **single dedicated** Historical Atlas tunnel, and associate it
   with the intended personal ChatGPT workspace and Platform organization.
   Required manager rights: Tunnels Read + Manage.
2. Create a **separate runtime** Platform API key in
   [API keys](https://platform.openai.com/settings/organization/api-keys)
   whose principal has **Tunnels Read + Use** for the selected tunnel.
   Do not use an admin key or a broad personal provider key as a daemon
   credential. The runtime key is separate from the ChatGPT subscription.
3. Store the **runtime key value** only as a GitHub Environment secret in
   `Dmitry-dev-pet/infra-access`, environment `infrastructure`, with the
   proposed narrow name `ATLAS_TUNNEL_RUNTIME_API_KEY`. Do not paste
   the key into an Issue, commit, chat, workflow log, receipt or PR comment.
   Store the non-secret tunnel identifier as Environment variable
   `ATLAS_TUNNEL_ID`. The ID has the provider-issued
   `tunnel_<32 lower-case alphanumeric>` or namespaced form; preserve
   it exactly and never invent a replacement.
4. Confirm that `infra-access` owns a **separately reviewed, allowlisted,
   source-CI-tested operation** to install this one sidecar. There is
   **no such live operation as of this document**. The existing
   `[infra] onboard` and `[infra] deploy` commands do not authorize
   arbitrary new services or secret-file writes. Do not run an operator
   SSH workaround, general shell runner job, or direct Docker commands
   against production to bypass that requirement.

## Reviewed Compose overlay (not deployed)

`ops/mcp/tunnel.compose.review.yml` is a **reference overlay**, not an
independent stack. It defines a second container `tunnel-client` whose
service DNS target is `http://app:8765/mcp`. A Docker container cannot
reach the VPS host's `127.0.0.1:8020` from its own network namespace;
using the Compose service name avoids host networking and keeps the Atlas
MCP entirely private.

When a future reviewed `infra-access` operation activates the overlay,
it must:

- target **only** `historical-atlas-mcp`, never arbitrary project names
  or issue-provided paths/images;
- preserve the currently installed base Compose, immutable Atlas image
  and rollback records; stage the overlay atomically and validate
  `docker compose config` **before** activation;
- verify the official `tunnel-client` version/OCI digest independently;
- materialize the Platform runtime key only in a VPS private file
  (`ATLAS_TUNNEL_RUNTIME_KEY_FILE`) with owner-only host permissions;
  mount it via a Compose secret read-only in the client container,
  and use `--control-plane.api-key=file:/run/secrets/... ` so the
  key value does **not** appear in command line arguments or env;
- provide the non-secret tunnel ID through a reviewed, fixed configuration,
  not an attacker-controlled MCP URL or arbitrary issue payload;
- use the **same Compose project** as the existing `app`, keep
  `read_only`, `cap_drop: ALL`, non-admin container user, and
  no Docker socket, host network or privileged mounts;
- allow outbound TCP/443 to `api.openai.com`, but publish no public
  MCP or tunnel ports; the optional health endpoint binds only to
  VPS `127.0.0.1:8021`;
- require `/readyz` to report ready, verify the actual MCP protocol
  and log a sanitized structured receipt on the existing\n  \`infra-access\` **\`operations-history\`** branch without any secrets;
- roll back only the tunnel sidecar if connectivity fails, leaving the
  running Atlas app untouched.

Upstream image's ENTRYPOINT is already
`/usr/bin/tunnel-client run`. Compose `command` adds only the
`--control-plane.api-key=file:/run/secrets/...` flag.

## Acceptance: verify actual MCP tools, not just a running container

When the reviewed sidecar is started, validate in this order:

1. Local VPS `http://127.0.0.1:8020/mcp`:
   JSON-RPC `initialize`, `tools/list` (exactly
   `dataset_info`) and `tools/call dataset_info`.
   Existing `ops/mcp/smoke.sh` demonstrates the actual protocol and
   expected shape; the deployed runtime has not yet been independently
   tested through that sequence.
2. Tunnel client `/healthz`, `/readyz` and `/health/mcp`, with
   no public health port. A healthy process alone does not prove
   tool discovery.
3. In **ChatGPT on the web**, open Plugins → + → Add custom MCP server,
   choose **Tunnel**, select the owner-created tunnel ID, review the
   provider warning and create a *private development* MCP app.
   Product eligibility and Platform tunnel permissions may differ;
   the UI must actually show the tunnel before claiming readiness.
4. In a **fresh ChatGPT conversation**, select that installed app and
   verify `tools/list` and one **real** `dataset_info` call.
   There must be no historical record, arbitrary SQL, private Archigos,
   or mutation tools advertised by this image.
5. Only then change the personal Truthrail tool route from
   `defined_not_connected` to connected on an independently reviewed
   PR. Keep GitHub the source of truth for project/build/deploy status.

## Safe stop and recovery

Stop or remove only the tunnel sidecar if OpenAI account permissions,
secret handling or readiness fails. Preserve the base Atlas container
and its loopback port. Rotate/revoke the tunnel runtime key in Platform
if its exposure is suspected; refresh the owning GitHub Environment
secret and the VPS-mounted key through a reviewed operation. Do not
copy the key into `Dmitry-dev-pet/truthrail` or the Atlas application
repository.

References: OpenAI
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels),
[official Docker deployment](https://github.com/openai/tunnel-client/blob/master/docs/deployment/docker.md),
[onboarding](https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md).
