# MCP and agent Skill

The stdio launcher works from any working directory. Use the virtual environment's **absolute**
Python executable and absolute `backend/run_mcp.py` path. Do not rely on activation or a shell.
The API must already be running; MCP does not start it. Its only tools are `inspect_changes`
(paid, explicit new audit) and `get_review_feedback` (read-only). No human-decision mutation tool.

Generic server entry (adapt the enclosing configuration to your actual client):

```json
{
  "command": "/absolute/checkout/backend/.venv/bin/python",
  "args": [
    "/absolute/checkout/backend/run_mcp.py",
    "--repo", "project=/absolute/project",
    "--api-url", "http://127.0.0.1:8000"
  ]
}
```

Windows executable: `C:/work/inspector/backend/.venv/Scripts/python.exe`; launcher:
`C:/work/inspector/backend/run_mcp.py`; repository: `project=C:/work/project`.
macOS paths are normally under `/Users/...`; Linux paths often under `/home/...`.
Spaces stay within one JSON argument. Repeat `--repo ID=ABSOLUTE_PATH` to authorize more roots.
Match `INSPECTOR_REPOSITORIES` in the API. MCP CLI authorization is not loaded from that JSON.
Optional `--env-file` accepts an absolute dotenv file but reads only `MODEL_API_KEY`; the API
performs provider requests and needs its own key. Do not supply secrets in client arguments.

## Client verification

Muse Code was connected on Windows using its `mcp_servers` configuration entry and stdio
handshake/tool discovery. That does not verify every Muse version or every platform. Codex and
Claude Code tool schemas/workflow are supported by the portable bundle, but end-to-end native
client runs are not claimed verified here. Use each client's current MCP configuration format;
the generic entry above is not a universal root schema. Reconnect/restart clients after updating
the server. Do not create duplicate entries with alternative root-key spellings.

Allow a sufficiently long tool timeout: one invocation can make up to the configured sequential
request limit (maximum eight). The server's HTTP analysis timeout is 510 seconds. Client defaults
may be shorter. A timeout can occur after persistence; inspect the returned review ID/inbox before
submitting another audit. Never automatically retry.

## Skill installation

Copy the complete `skills/ai-change-inspector` directory, including `references/examples.json`,
into the client's documented skill directory. For Codex this is normally
`~/.agents/skills/ai-change-inspector`; for Claude Code `~/.claude/skills/ai-change-inspector`.
Muse Code skill discovery depends on its installed version; use its documented directory rather
than assuming that another client's directory is discovered. Copying files alone is not a verified
client integration. Reload/discover skills in the client, then explicitly invoke `ai-change-inspector`.
No install step changes permission policy or authorizes an audit.

## First real audit (paid, only at your request)

1. Configure the backend key and identical authorized repository ID/root on both sides.
2. Start API/frontend, connect MCP and verify discovery of both tools.
3. Ask: “Use ai-change-inspector to audit the unstaged changes of repository project once.”
   Explicitly say so if you also want untracked files. Never stage just to force an audit.
4. The agent calls `inspect_changes` once with `repository=project`, `scope=unstaged`.
   It returns a persisted ID and local review URL. Open that URL; inspect status and coverage.
5. Review evidence, choose a human decision and optionally a comment, then save it yourself.
6. Ask the agent to read feedback for that actual review ID using `get_review_feedback`.
7. After separately authorized fixes, explicitly request one new audit with the original ID as
   `parent_review_id`. View evolution compares the snapshots; it does not prove resolution.

Agents must not record/impersonate human feedback, auto-fix solely because the model suggests it,
auto-submit follow-ups, or retry partial results. A partial audit is not a successful full audit.
