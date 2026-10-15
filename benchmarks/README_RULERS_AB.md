# Gemini / Historical Atlas: local A/B benchmark (Issue #81)

This is not the older Archigos returnees benchmark. It compares the installed
**AGY / Gemini** model against itself on ten fixed Russian-history questions,
with just one intervention: local canonical Atlas MCP.

| Lane | Context | Tools |
| --- | --- | --- |
| baseline | New isolated HOME/workspace per question | MCP denied; no website/file/command tools |
| with_mcp | Another new isolated HOME/workspace per question | Only five read-only Atlas methods via stdio |

The ChatGPT Plugin tunnel is not used or changed. No HTTP service, port,
private Archigos file, OpenAI API or Gemini API key is needed.

## Run under the dedicated macOS runner account

Use only the **already authenticated, explicitly approved dedicated runner
account**, never someone else's interactive login. The OAuth file must be
owned by that account, mode 0600. Never add credentials or raw logs to GitHub.

1. Checkout a reviewed exact Git commit and ensure a clean tracked tree.
2. Inspect the installed AGY model slugs using **agy models**. Do not assume
   a model shown in external documentation exists in this installation.
3. Build the local canonical atlas.sqlite using the project build pipeline
   (python3 -m scripts.atlas_db build --output ...); install mcp>=2,<3.
4. Supply one explicit installed-model slug as --model for both lanes. The
   runner checks it against its local AGY list and never falls back.
   AGY slugs may already encode effort (-medium, -high), so the benchmark
   intentionally does not pass a potentially conflicting --effort flag.

Example on a dedicated runner (replace paths and MODEL_FROM_AGY_MODELS):

    cd /path/to/reviewed/rulers-chronology-audit
    WORK=/path/to/private/runner/temp/atlas-rulers-ab-81
    mkdir -p "$WORK"
    chmod 700 "$WORK"
    python3 -m venv "$WORK/venv"
    "$WORK/venv/bin/python" -m pip install 'mcp>=2,<3'
    "$WORK/venv/bin/python" -m scripts.atlas_db build --output "$WORK/build"
    agy models
    "$WORK/venv/bin/python" benchmarks/run_agy_rulers_ab.py \
      --atlas "$PWD" \
      --sqlite "$WORK/build/atlas.sqlite" \
      --agy "$(command -v agy)" \
      --python "$WORK/venv/bin/python" \
      --auth-file "$HOME/.gemini/antigravity-cli/antigravity-oauth-token" \
      --model MODEL_FROM_AGY_MODELS \
      --expected-atlas-commit "$(git rev-parse HEAD)" \
      --max-questions 1 \
      --output "$WORK/results/smoke.json"

After the one-question smoke succeeds, rerun with --max-questions 10 and a
fresh output path. Twenty independent model invocations are expected.
Watch subscription usage/rate limits; this is not an API billing pipeline.

## What counts as a valid result

- Every trial must report the exact requested model in its AGY init event.
- The baseline must neither advertise nor invoke an MCP tool.
- The powered lane must finish a real read-only canonical Atlas tool call
  for every question; advertising a tool is not sufficient.
- Any forbidden tool invocation or permission denial invalidates the trial.
- Answers, uncertainty, claimed sources, actual tool events, status, timing,
  diagnostics and numeric usage go into a mode-0600 report, with question
  SHA-256, Atlas commit, database SHA-256 and AGY version.
- The SQLite hash is checked again after the run. The local hash **does not**
  prove the ChatGPT Plugin uses identical data; verify separately.
- The run does **not** score historical truth. A separate blinded review
  against independent sources is required.

The CLI does not save raw stdout, stderr, or OAuth contents to GitHub. Its
report is local by default under ignored dist/. If results need GitHub
persistence, manually review/redact them and commit a sanitized copy under
a new tracked benchmark-results path through a separate PR. Never publish
the original photo, private Archigos data or unsanitized tool traces.

Offline tests without any model login:

    python3 -m unittest discover -s tests -p 'test_agy_rulers_ab.py' -v

The older Archigos test (run_agy_mac_ab.py) remains independent, but now
also requires an explicit model slug verified against the installed CLI.
