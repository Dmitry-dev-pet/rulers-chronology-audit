# Historical Atlas MCP v1 and Gemini A/B benchmark

## Status

Experimental **local stdio MCP**; it does not listen on a TCP port, edit
Git-tracked historical records, or change GitHub Pages. The executable
uses the official MCP Python SDK **v2** and reads a **derived** SQLite v1
in immutable/query-only mode. The optional Archigos source is a private,
checksum-verified Stata file. It is not part of the Git repository.

The SPA, canon, provenance, licenses, publication allowlist, and world
pilot are unchanged. The global 1417–1991 atlas covers Russian political
contexts; the international pilot is **not** silently merged into v1.

## Start locally

From the repository root:

    python3 -m pip install 'mcp>=2,<3'
    python3 -m scripts.atlas_db validate
    python3 -m scripts.atlas_db build
    ATLAS_SQLITE_PATH="$PWD/dist/atlas.sqlite" python3 -m scripts.atlas_mcp

The MCP process is silent on stdout and speaks JSON-RPC on stdin/stdout.
A host client should launch it rather than a human typing to the terminal.

If running the Archigos benchmark, obtain the original dataset already
stored in the project's **private** Google Drive research folder,
not from GitHub Pages. Install the analysis-only dependency:

    python3 -m pip install pandas

Configure an absolute, local, private path through ATLAS_ARCHIGOS_PATH.
The server pins SHA-256:

    3e3b4092a7ac5a7e78cd86df6e6287c69027bf6fe60c9396adf136a39b1943ad

Do not commit that file, its original PDF, OAuth tokens, or generated
MCP settings with local paths. No direct SQL execution tool exists.

## MCP tool contract

| Tool | Data | Behavior |
| --- | --- | --- |
| dataset_info | SQLite | Numbers and honest database scope |
| search_rulers | SQLite | Names/aliases + optional year, bounded results |
| get_timeline | SQLite | Independent legal and power-assessment entries |
| compare_rulers | SQLite | Compare 1–5 stable canonical identities |
| get_evidence | SQLite | Source links, dates, verification and caveats |
| archigos_returnees | Private .dta | Verified reproducible gap statistics, pages of 100 max |

Calendar-year overlaps are candidates, not exact day-level simultaneity.
The source's assessment of "effective leader" is not automatically
accepted as our own conclusion. A country code such as Archigos RUS
must **not** collapse Russian Empire, USSR, RSFSR and the Russian Federation
into one timeless legal state.

The returned Archigos aggregates are source-derived, not automatically
correct identities. The first pass rejects reused leader IDs when
positive reported birth years disagree. For example the same Archigos
leadid joins SWD-1888 and SWD-1991, reporting years 1820 and 1949,
yet these are **Gillis Bildt and Carl Bildt**, two different Swedish
prime ministers. The Swedish government's prime-minister timeline
documents the relationship:
https://www.regeringen.se/sa-styrs-sverige/statsministerambetet-i-sverige/

For the pinned 1875–2015 test, excluding seven birth-year-conflicted
ID groups leaves **597** coded re-entry events, **449** unique
(country,leadid) keys, and mean gap **1798.382 days**. These numbers
are independently checkable with the original bytes and this documented
algorithm, but should not be advertised as universal historical facts.
Quarantining every birth-year disagreement is deliberately conservative:
some real repeat terms could be excluded because of a mistaken year.

## A/B test on the same Gemini model, using the existing account login

This is an isolated local evaluation. It does not trigger paid Gemini API
calls, reuse another repository's secrets, or extract cached credentials.
First check that your locally installed agy is authenticated:

    agy --version
    agy models

For headless mode, sign in once interactively as the **same operating-system
user** who will run the benchmark. This command never prints the login
token. A GitHub Actions hosted runner will not automatically inherit your
Mac's or a different repository's OAuth session.

Then, from the project root:

    python3 benchmarks/run_agy_ab.py \
      --archigos /private/path/Archigos_4.1_stata14.dta \
      --sqlite dist/atlas.sqlite \
      --model THE_ACTUAL_MODEL_SLUG

Each run uses the exact same question from
benchmarks/archigos_return_v1.json, requested model, structured output
schema, and fresh conversation. A baseline workspace has no project
data or workspace MCP. The other workspace only adds
historical-atlas as a local stdio MCP server. Original files are read
through the MCP subprocess and remain private; reports and raw tool-call
traces are written **only to dist/benchmark-mcp/**, ignored by Git.

The runner never uses --dangerously-skip-permissions. Ensure the CLI's
actual permissions permit only the intended read-only MCP tools; a soft
denial means **no valid MCP trial**, even if the model returned an answer.
Review the final used_tool_names and available tool list. Global
plugins/tools, web tools or inherited user configuration can confound the
baseline; if used, mark the trial non-comparable. In particular, if the
model does not call archigos_returnees, a numerical answer does not
constitute successful use of our tool.

Score the integer counts and mean gap against the pinned gold results.
Honest abstention without data is recorded separately from factual accuracy.
There is **no LLM judge declaring historical truth** in this benchmark.
For now ChatGPT without the atlas is a **manual** third comparison:
the ChatGPT app subscription is not a general-purpose programmable API.

## Safety, compatibility and testing

    python3 -m unittest discover -s tests -p test_atlas_mcp.py -v

The tests cover read-only SQLite, source evidence, date precision,
two-term returns, a same-day non-return, identity-ID collision and input
bounds. When the MCP SDK is installed, an in-memory Client additionally
exercises real MCP tool calls. The separate mcp-smoke GitHub Action
installs the SDK for this purpose; the normal production build does not.

The source raw bytes, OAuth state, user-specific profiles and local
benchmark logs are not permitted in public GitHub commits or Pages.
Do not treat successful CI as a historical audit. A future remote MCP
requires separate authentication, network access control and threat
model; do **not** expose this stdio process as a public unauthenticated API.

Official references:
- MCP v2 SDK: https://py.sdk.modelcontextprotocol.io/
- Antigravity MCP config: https://www.antigravity.google/docs/cli/mcp/
- Antigravity headless CLI: https://www.antigravity.google/docs/cli/headless/
- Original Archigos dataset: https://www.rochester.edu/college/faculty/hgoemans/data.htm
