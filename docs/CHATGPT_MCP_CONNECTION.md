# ChatGPT / Alfred: private MCP connection for Historical Atlas

Status: **connection plan, not a live deployment** (2026-10-13). Tracking: [Issue #67](../issues/67). The original [MCP prototype #43](../pull/43) is already merged and remains the implementation.

## Goal and architectural boundary

Alfred (ChatGPT) should call the **existing** source-bound historical-research tools from a chat. GitHub-tracked `data/atlas/` and reviewed historical source claims remain authoritative; generated SQLite snapshots are derivative. The public Pages site is a visualization consumer, **not** the domain API. ChatGPT queries are read-only; proposals to change historical data use reviewed GitHub PRs, never an MCP write tool.

The currently tested adapter is `scripts/atlas_mcp.py` using **MCP v2 / stdio**, not a public HTTP service. Its five canonical tools are `dataset_info`, `search_rulers`, `get_timeline`, `compare_rulers`, and `get_evidence`. The optional sixth `archigos_returnees` needs a separately private Archigos input. The current derived SQLite v1 covers the Russian historical atlas, **not** full world or HPM v2 Europe. The HPM research projection from #61/#65/#66 needs a separate bounded MCP extension, preserving the namespace and `unknown` mechanism status.

## Preferred transport: OpenAI Secure MCP Tunnel on an existing VPS

Use **OpenAI Secure MCP Tunnel** to connect this already-working *stdio* adapter from a non-admin account on an approved always-on VPS through an outbound HTTPS tunnel. This avoids exposing a public HTTP MCP endpoint, requiring an always-on personal Mac, implementing our own OAuth server, or adding a second historical domain service. The tunnel is a network/transport process, **not** a second AI agent or a database-of-record.

Official reference: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels

**Activation prerequisites / explicit gates**:

1. The account owner creates an OpenAI Platform tunnel in an authorized Platform organization and obtains its **tunnel ID** and scoped **runtime API key** via the provider UI. Account and workspace association must be verified. This is an explicit owner setup, **not performed** by this repository or any GitHub writer.
2. The VPS's owning `infra-access` control plane must gain a separately reviewed, **narrow** operation to provision/manage this exact Atlas MCP and its outbound tunnel client. No arbitrary host shell/SSH and no transfer of secrets from another project. Choose an existing approved host and avoid new paid subscriptions or storage.
3. The tunnel credential is stored only in the owning runtime/GitHub Environment secret store. Never write its value, URL with token, local OAuth files, or private Archigos bytes to Git, issues, tests, artifacts, or logs.
4. The host must have a public-source immutable, reviewed repository checkout or equivalent build snapshot, Python + pinned dependencies, derived `atlas.sqlite`, and network egress to the OpenAI tunnel service. The provenance must include the source commit and generated snapshot hash.
5. Provision/verification requires a read-only smoke with the actual ChatGPT app/plugin connection. A registry declaration alone is **never** proof of connectivity.

## Existing offline build and stdio command

Run this from an immutable, reviewed repository snapshot under the approved unprivileged service user, with an isolated Python environment:

```sh
python3 -m pip install 'mcp>=2,<3'
python3 -m scripts.atlas_db validate
python3 -m scripts.atlas_db build
unset ATLAS_ARCHIGOS_PATH
export ATLAS_SQLITE_PATH="$PWD/dist/atlas.sqlite"
python3 -m scripts.atlas_mcp
```

The last process is a **stdio subprocess** launched by the MCP client/tunnel, not a normal interactive shell command. The actual `tunnel-client init` profile must use a reviewed absolute command/wrapper and a resolved tunnel ID; the profile is host-local and never committed. Review the tool's exact current quickstart for command syntax (do not rely on hard-coded binaries or URLs).

The model must not receive arbitrary SQL/file/shell execution or a Git write tool through this capability. The SQLite reader already opens `mode=ro&immutable=1` with `query_only=ON`, bounded pagination, IDs, and source caveats. Keep the optional private Archigos file **unconfigured** for the first connected smoke. Merely advertising its optional tool must not import its raw data.

## Acceptance and release gate

- GitHub CI/stdio smoke on the exact server commit; no updates to the poster, `data/atlas/`, canonical schema, original private image, or Pages as a side-effect.
- `tunnel-client doctor` and runtime health from the owning VPS control plane, without credential disclosure; the running client must have authenticated outbound tunnel access.
- In ChatGPT **web**, configure the MCP via a tunnel connection following the official developer-mode or Plugins flow. Availability on the native mobile app must be checked rather than assumed.
- Actually call `dataset_info`, `search_rulers` (e.g., `Пётр`), `get_timeline(1953)`, then `get_evidence` for a returned record; verify source links, dataset scope, no writes, errors and deadlines. At this gate `archigos_returnees` is unavailable if the private file is not explicitly provisioned.
- A question about *European transition mechanisms* must honestly say the current MCP's canonical v1 dataset does not support that conclusion. Extending read-only tools over HPM P2/P3 is a separate reviewed PR and does **not** allow inferring accession mechanisms.
- Rollback: disable/remove the ChatGPT connection and stop/disable the VPS tunnel operation, retaining Git-backed historical data unchanged.

## What is **not** authorized

No public unauthenticated MCP endpoint, no credentials inside project files, no new Auth server, no immediate production migration, no extra historical canonical data, no public Archigos or private Drive download, no Mac runner or GPU requirement, and no claim that the tunnel/app is already connected.

References: [Database provenance](DATABASE.md), [experimental MCP](MCP_BENCHMARK.md), [HPM contract](HISTORICAL_POWER_MODEL_V1.md).
