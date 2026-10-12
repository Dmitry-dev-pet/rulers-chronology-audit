# Historical Atlas MCP A/B: project-owned Mac Action

This is a **fixed, read-only** project Action package for the private
`Dmitry-dev-pet/mac-access` control plane. It must be referenced by a
reviewed **40-character commit SHA** under
`Dmitry-dev-pet/rulers-chronology-audit/ops/mac/atlas_gemini_benchmark`.
It is not callable through arbitrary issue bodies, and it does not grant
permission to execute new commands on the user's Mac by itself.

## Scope and permissions

The project package has no user-supplied Action inputs. A separately
admitted owner-only mac-access operation runs it on the non-admin dedicated
`agent-runner` account, with:
- only read access to the existing `atlas.sqlite` source representation
  (the SQLite file is derived into runner temp from reviewed JSON);
- a SHA-256-pinned download of public Archigos 4.1 Stata data from Rochester;
- a dedicated MCP server exposing exactly **one**
  `historical-atlas/archigos_returnees` tool;
- two fresh same-model Antigravity CLI trials with identical benchmark
  questions and isolated temporary HOME/workspaces.

The existing Rubik GitHub Environment `research` OAuth secret
**is not accessible** in mac-access. This package intentionally does not
attempt to move that credential between repositories, read personal user
profiles, request privileged Keychain entries or run an unreviewed installer.
The dedicated non-admin runner user must have its **own approved local**
Antigravity CLI and subscription session installed under the normal local
`~/.gemini/antigravity-cli/antigravity-oauth-token` location. If absent,
the Action refuses to run and reports an operational blocker. The token
file must be owned by that runner UID, with no group/other permissions.
The Action copies it only into mode-0700 per-trial temporary homes and
removes those homes afterward. No session bytes enter Git or an artifact.

The Action's network dependencies are public GitHub packages, PyPI
dependencies, Rochester's dataset, and Google's Antigravity service. It
cannot be treated as offline. Verify the necessary network destinations
in the mac-access operation contract before admitting execution.
The Mac is never exposed via an incoming server. `MCPServer` uses
local stdio only and contains no arbitrary SQL/command executor.

## Exact benchmark

Pinned to the original source SHA-256:
`3e3b4092a7ac5a7e78cd86df6e6287c69027bf6fe60c9396adf136a39b1943ad`

Baseline has no MCP and denies all commands/file/browsing/MCP. Powered
has exactly one local server and one explicit permission:
`mcp(historical-atlas/archigos_returnees)`. Neither lane uses a
permission bypass flag. A good numerical guess without a real MCP tool
call is not counted as a valid powered trial.

The source-derived benchmark expects 597 coded re-entry events, 449
distinct country-person keys, mean break 1798.382 days and seven groups
with conflicting birth-year records. These are not historically attested
person identities. The long-term Atlas DB still distinguishes formal
offices and scholarly assessments of real authority.

The private Mac runner uploads a bounded, **sanitized** JSON receipt
containing only observed tool names, statuses, usage and correctness.
It does not upload any source data, private account state, raw AGY output
or local credential path.

## Review and tests

`ops/mac/action.yml` is an offline syntax and specification preflight,
not a model invocation. `ops/mac/atlas_gemini_benchmark/action.yml` is
the fixed executable Action with `result` output for mac-access.
Tests:
`python3 -m unittest discover -s tests -p test_atlas_mcp_mac.py -v`

Important: this package **does not authorize itself**. The mac-access
hosted admission gate and repository-scoped Mac runner still control
whether it can be executed. If hosted gate fails before any steps, that
does not establish Mac offline status or OAuth failure; do not bypass
the gate to make the trial appear successful.
