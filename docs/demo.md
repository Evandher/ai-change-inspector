# Judge walkthrough

## A: No credentials, no provider requests

1. Run setup/start, open the local frontend and choose **Diff explorer**.
2. Load an included example and click **Parse diff**. Inspect files, hunks, added/deleted lines
   and metadata. This uses the actual local parser, not simulated model output.
3. Switch EN/ES and use keyboard navigation. Do not click **Review with Muse Spark**.
4. Open Review inbox: a fresh installation is empty by design; no private reviews are seeded.

This path demonstrates deterministic parsing and navigation. It does not demonstrate model findings,
human feedback, comparisons or recovery without persisted analyses. Automated mocked tests cover
those flows without credits; they are not presented as real Muse Spark output. No demo mode or
synthetic provider has been silently enabled in the application.

## B: Own API credentials

Follow [MCP and first audit](mcp.md). Use a small non-sensitive Git diff that you own, a known
repository ID and one explicit scope. Review the captured snapshot before model submission when
using the manual explorer. The MCP audit captures and submits in the same explicitly paid action.
Open the returned review URL, inspect coverage and citations, save human feedback, then request
read-only feedback retrieval. A child review requires another explicit paid request.

For partial results, inspect diagnostics. In Review Detail select only eligible failed/incomplete
batches and review the confirmation's request count/output budget before confirming. This is paid.
Do not recover just to demonstrate the screen; mocks verify the interaction without credits.

## Release checklist â€” November 4, 2026

- [ ] Run documented setup/start on a clean Windows checkout; retain logs without secrets.
- [ ] Run Linux and macOS validation or keep their unverified labels.
- [x] Capture the local parser screenshot using a synthetic example; no private review data.
- [ ] Inspect current tree AND historical Git objects for secrets/private notes.
- [ ] Decide whether historical internal notes require an authorized history cleanup.
- [ ] Confirm GPLv3 and dependency notices for the actual distribution.
- [ ] Run all tests/lint/build and a stdio handshake; never use a paid audit as an install check.
- [ ] Publish only after separately authorized staging/commit/push and final review.

The hackathon date above is supplied by the project owner; submission rules must be checked with
the organizer independently. Preparation does not submit or publish the project.
