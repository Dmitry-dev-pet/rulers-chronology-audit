# Publication on GitHub Pages

This site is a static public rendering of the Soviet-period research, not an
automatic historical fact checker. It displays parallel **party, government,
and state institution** chronologies generated from versioned JSON.

## Deployment

The public site is deployed by [`publish-pages.yml`](../.github/workflows/publish-pages.yml)
on relevant changes to the default `main` branch (or a manual dispatch from
`main`). No pull requests can deploy Pages. The job runs on GitHub-hosted
`ubuntu-24.04` and:

1. Runs offline Python unit tests.
2. Builds `dist/index.html`, JSON, CSV, metadata and checksums using
   `scripts/soviet_audit.py`.
3. Rejects unexpected output files and any occurrence of the private
   Google Drive URL or original photograph filename in published output.
4. Publishes only the generated `dist/` directory with GitHub Pages
   artifact/deployment actions.

Runtime permissions are limited to `contents: read`, `pages: write`, and
`id-token: write`. Git credentials are not persisted after checkout.
No external agents, Mac runner, private Google Drive images or user secrets
are involved. Pages is enabled through the separate reviewed GitHub Control
App issue workflow.

**Expected URL after first successful deploy:**
https://dmitry-dev-pet.github.io/rulers-chronology-audit/

The actual address should be treated as live only after a successful
deployment and an HTTP response check. Source records are the repository
history; the deployed site does **not** independently verify the historical
accuracy of dates or claims. The original image stays private in Google Drive.
