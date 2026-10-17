# One-process MCP peer-chat release candidate — source & CI only

**Draft packaging; NOT current live deployment.** The VPS already runs the
previous combined Truthrail MCP/Atlas image tagged
`cd5c8fe63a585b28c25ec505421e5439255180ed`, verified by the owner-issued
read-only `infra-access #462` operation on 17 Oct 2026. That image still
exposes the original five Atlas tools.

## Source-of-truth inputs

- **NEW Truthrail generic MCP source:** exact public commit
  `a39fabe803e3b6cf15831e1c8b38b3f4b4622e89`
  (draft `Dmitry-dev-pet/truthrail-mcp PR #11`).
- **UNCHANGED canonical Atlas data/query source:** exact original public commit
  `cb3c65853628607f2e03f30bc4e1a47063b13cd4`.
- **Target:** existing GHCR package
  `ghcr.io/dmitry-dev-pet/rulers-chronology-audit`. Future tag would be the
  full source SHA of this *packaging repository's* reviewed merged commit, NOT
  the original runtime tag. Do not reuse a floating tag or infer a manifest
  digest from an image tag.
- **Existing tunnel, app port, Compose service and command** remain identical:
  the original ChatGPT Secure MCP Tunnel keeps connecting to the same
  non-root container at port 8765 through the same tunnel-client sidecar.
- Three build-time reviewed flags:
  `ALFRED_SHARED_MCP_ENABLED=1`,
  `ALFRED_EMBEDDED_ATLAS_REVIEWED=1`,
  `ALFRED_PEER_CHAT_MCP_ENABLED=1`.
  The last is deliberately *absent* from the already deployed image.

## Required source CI

PR verify does **not** push an image or access production credentials:
it builds the pinned single-process public Atlas image, runs the original
five-tool real Atlas HTTP smoke with chat disabled, then builds the opt-in
peer-chat wrapper and verifies a real HTTP nine-tool inventory and three
blocking two-client A↔B exchanges. Atlas dataset_info and PC03 evidence must
survive. Run on GitHub-hosted disposable Docker only under the same 176 MiB
CI-only memory cap; do NOT retry the failed 176 MiB extra shadow on the 458
MiB VPS.

Only after a *separately approved merge to main* does the existing publishing
workflow repeat both smokes before GHCR credential materialization and publish
an immutable full-SHA tag into the existing Atlas package. The push run must
record the **actual** OCI manifest digest.

## Production blockers: do NOT deploy after CI

1. **Security review:** four chat tools are new write/long-poll permissions.
   The existing ChatGPT custom app may prompt for approval, and tool
   discovery may be cached. Never advertise write tools as read-only.
2. **Operator-gated deployment:** current `infra-access` code accepts only
   the old exact combined release `cd5c8fe63a585b28c25ec505421e5439255180ed`
   with its old source label and two startup flags. Do not bypass or reuse
   this allowlist for a new release. New reviewed, tightly pinned guard and
   rollback path are necessary first.
3. **Current capacity:** 458 MiB physical RAM, ~178 MiB MemAvailable and
   ~239 MiB swap used at read-only #462; no additional resident MCP service
   or unknown new memory headroom assumption. Verify fresh status and exact
   old cached image before any app-only replace.
4. **Explicit exact-image approval:** the user must authorize the **new**
   packaging commit/image, current digest, expected sidecar-preserving
   replacement and rollback. A vague yes to prototype design is not
   authorization to deploy any unreviewed new image.
5. **Live acceptance:** five original Atlas tools and PC03 source evidence
   still work in native ChatGPT; peer chat tools appear in both independent
   Mac ChatGPT Web sessions on the *same* existing app/tunnel; three
   round-trips without another user Enter, or a precise observed failure.
   Never claim a permanent conversation loop on synthetic tool success.

Rollback should use only the reviewed operator route to the known-good
existing combined image, preserving the original sidecar and its secret.
Do not use generic Docker shell, broaden external access, or bypass the
current memory safety gates.
