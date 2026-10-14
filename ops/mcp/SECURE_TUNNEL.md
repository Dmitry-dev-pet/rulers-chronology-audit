# Secure MCP Tunnel for the private Historical Atlas

Status (14 October 2026): **VPS transport active; ChatGPT MCP app not yet
connected or verified**. The existing historical Atlas application remains
healthy at `127.0.0.1:8020` and exposes **only** `dataset_info`.
The official tunnel-client sidecar passed `/readyz` following the approved
[infra-access activation #286](https://github.com/Dmitry-dev-pet/infra-access/issues/286)
and sanitized [operations-history receipt](https://github.com/Dmitry-dev-pet/infra-access/actions/runs/38647815948).
The separate read-only [inspection #287](https://github.com/Dmitry-dev-pet/infra-access/issues/287)
verified that the pinned Atlas image stayed healthy, and its private key-file
path and Compose overlay are present. A *native ChatGPT* `dataset_info` call
and independent local MCP protocol roundtrip are **still unverified**.
Truthrail must remain `defined_not_connected`; do not report the entire
historical research API as available in ChatGPT.

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
(published 6 Oct 2026). The reviewed production gateway pins exactly
`ghcr.io/openai/tunnel-client@sha256:4605ea909701668d3bdcbe6152558e068e24006aa96ca5518ca67f786a1bce13`.
GitHub Actions passed the official `gh attestation verify oci://... -R
openai/tunnel-client` preflight before transferring credentials.
Never use `latest` or substitute a different publisher or image.

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
4. The **operator-only** operation is now implemented by
   [infra-access PR #277](https://github.com/Dmitry-dev-pet/infra-access/pull/277)
   (reviewed, source-CI-tested), and its non-root file access was corrected
   in [PR #284](https://github.com/Dmitry-dev-pet/infra-access/pull/284).
   The owner activated the sidecar via the *exact* `[infra]
   atlas-tunnel-activate historical-atlas-mcp` issue; the older
   `onboard/deploy` operations do not authorize arbitrary new services or
   secret writes. The owner-only status is **not** transferable to an AI
   agent, generic SSH bridge, or other project.

## Reference overlay vs deployed runtime

`ops/mcp/tunnel.compose.review.yml` is a **historical reference overlay**
from the pre-activation review, **not the live Compose stack**. The reviewed
`infra-access/scripts/infra-gateway.sh` owns the active overlay and fixed
non-root runtime identity. Do not independently deploy this reference file
or assume its placeholder UID/GID reflects production.
It is not an independent stack. It defines a second container `tunnel-client` whose
service DNS target is `http://app:8765/mcp`. A Docker container cannot
reach the VPS host's `127.0.0.1:8020` from its own network namespace;
using the Compose service name avoids host networking and keeps the Atlas
MCP entirely private.

The approved `infra-access` gateway enforces the following invariants:

- target **only** `historical-atlas-mcp`, never arbitrary project names
  or issue-provided paths/images;
- preserve the currently installed base Compose, immutable Atlas image
  and rollback records; stage the overlay atomically and validate
  `docker compose config` **before** activation;
- verify the official `tunnel-client` version/OCI digest independently;
- write the Platform runtime key only into a private `deploy`-owned
  file (parent directory `0700`, file `0600`) on VPS; run the official
  sidecar under that **same** deploy numeric UID/GID (not UID 0), using
  values discovered locally by the forced gateway with `id -u/id -g`.
  Bind-mount the file as a Compose read-only secret. The key is provided
  only to `--control-plane.api-key=file:/run/secrets/...`, never embedded
  in command-line secret values, environment variables or logs;
- provide the non-secret tunnel ID through a reviewed, fixed configuration,
  not an attacker-controlled MCP URL or arbitrary issue payload;
- use the **same Compose project** as the existing `app`, keep
  `read_only`, `cap_drop: ALL`, non-admin container user, and
  no Docker socket, host network or privileged mounts;
- allow outbound TCP/443 to `api.openai.com`, but publish no public
  MCP or tunnel ports; the optional health endpoint binds only to
  VPS `127.0.0.1:8021`;
- require `/readyz` to report ready, verify the actual MCP protocol
  and log a sanitized structured receipt on the existing
  `infra-access` **`operations-history`** branch without any secrets;
- roll back only the tunnel sidecar if connectivity fails, leaving the
  running Atlas app untouched.

### Docker Compose file-secret permissions (active runtime)

Docker Compose delivers a file-sourced `secrets:` entry as a **bind mount**;
`uid`, `gid` and `mode` fields in the Compose long syntax do **not**
remap file ownership for a file source. See the
[Docker Compose specification](https://docs.docker.com/reference/compose-file/services/#secrets).

[Read-only diagnostic #283](https://github.com/Dmitry-dev-pet/infra-access/issues/283)
confirmed that the VPS lacks `setfacl` and `getfacl`. The first activation
therefore stopped safely before installing the sidecar. Rather than install
privileged host packages or relax file access, the corrected forced gateway
runs the official `tunnel-client` as the **same unprivileged numeric UID/GID**
as the verified `deploy` account. The secret is owned by `deploy` under
a private directory `0700` with mode `0600`. The gateway validates the
non-root identity, exact file owner/mode, symlink boundaries and output-free
mounted-secret `test -r /run/secrets/atlas_openai_tunnel_runtime_key`
before claiming readiness. No `0644`, root container, sudo, generic
file writer or arbitrary issue-supplied numeric user is permitted.
Never `cat`, hash, echo, print or persist the key in logs, manifests,
receipts or source files. Keep the mount read-only.

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
