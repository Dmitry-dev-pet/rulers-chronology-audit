# One-process Truthrail MCP candidate in the existing Atlas GHCR package

This is **release packaging only**. It does not create a second gateway,
second container or second ChatGPT tunnel, nor authorize a VPS deployment.

- Runtime source: public Truthrail MCP at exact SHA
  93da45d9fe675d00cd02ef59c8b32054375dbba3.
- Canonical Atlas data and query source: public rulers-chronology-audit
  at exact SHA cb3c65853628607f2e03f30bc4e1a47063b13cd4, the
  observed live Historical Atlas image source revision.
- Target: the **existing** ghcr.io/dmitry-dev-pet/rulers-chronology-audit
  GHCR package, tagged with the packaging repository's full commit SHA.
  The publish job records the manifest sha256 digest; no latest tag.
- One process, five real read-only canonical tools, same port 8765;
  no internal HTTP proxy, private image dataset or Archigos, SSH
  credentials, OAuth tokens or expanded ChatGPT tool permissions.
- A metadata-only Dockerfile adds exactly two startup enable flags to the
  reviewed pre-built public Truthrail/Atlas source image. Those flags
  matter only after separately authorized release-tag deployment.
- A public GitHub-hosted build/smoke runs locally with container read-only,
  non-root, loopback-only host port, cap-drop and 176 MiB **CI-only** limit.
  It does not prove the current 458 MiB VPS can sustain the service.
- The existing Historical Atlas build/publish workflow is unchanged; this
  release uses distinct workflow path filters so it cannot race with the
  existing publisher for the same SHA tag.

## Production is a separate decision

The existing infra-access op_deploy_atlas_with_tunnel already upgrades
only the Compose app, preserving the tunnel-client container identity
and original runtime key. On immediate deployment failure it attempts
to restore the exact prior app image. A successful candidate publication
does not execute that operation.

Before any deployment, independently check the immutable digest, GHCR
Read grant, current Atlas/tunnel health and VPS memory/disk headroom.
Document a manual **sidecar-aware** recovery procedure for failures
discovered by external ChatGPT calls AFTER the deploy completes.
The generic rollback operation is deliberately unsafe for a live Atlas
tunnel and remains blocked.

A future owner-approved exact issue
[infra] deploy historical-atlas-mcp <reviewed-40-hex-release-tag>
is a separate action. No new command or privilege is added by this PR.
Keep the original image available and perform actual five-tool ChatGPT
checks after cutover; revert through a separately reviewed
tunnel-preserving path if any production post-check fails.

This release does not make an image package public, change Cloudflare,
modify the VPS or weaken the separate 176 MiB shadow headroom guard.
