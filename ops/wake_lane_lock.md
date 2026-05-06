# Wake Lane Lock Contract

`tools/wake_lane_lock.py` is the repo-local advisory lock for parallel
autopilot wakes. It stores one SQLite row per `(intent_hash, target_surface)` in
`state/wake_locks.db`.

## Target Surfaces

Use a canonical lowercase snake-case surface name with an optional `:detail`
suffix:

- `farcaster_reply`
- `email_send_recipient_leon`
- `github_issue_comment:owner/repo#123`
- `tool_build:tools/calendar_nudge.py`

The validator accepts `^[a-z][a-z0-9_]*(?::[a-z0-9][a-z0-9_./#@+-]*)?$`.
Hyphenated aliases like `farcaster-reply`, short aliases like `fc_reply`, and
space-separated names are rejected. The current surface families are
`browser_flow`, `devto_comment`, `devto_post`, `farcaster_cast`,
`farcaster_reply`, `funnel_doc`, `github_issue_comment`, `github_lead_scan`,
`github_pr_comment`, `lead_scan`, `longform_edit`, `outbound_pipeline`,
`research_doc`, `tool_build`, and `email_send_recipient_*`. If a new surface
family is needed, add it to this contract and the validator before wiring
callers to it.

## Intent Hashes

Default intent hashing is `sha256(normalized_intent)[:16]`.

Normalization:

- lowercase
- convert underscores to spaces
- collapse whitespace runs to one space
- strip leading/trailing whitespace
- preserve all other punctuation

This makes `build calendar nudge tool` and `Build calendar_nudge tool` collide
intentionally, while keeping `calendar_nudge.py` distinct from
`calendar nudge py`. Use `--intent-hash` when two router phrasings are known to
be the same work but normalization cannot make them converge.

## TTL And Release

Default TTL is `900` seconds (15 minutes):

```powershell
python tools/wake_lane_lock.py acquire --intent "build calendar nudge tool" --target "tool_build:tools/calendar_nudge.py"
```

Long browser flows or longform jobs should pass an explicit TTL:

```powershell
python tools/wake_lane_lock.py acquire --intent "run coderlegion browser flow" --target "browser_flow:coderlegion" --ttl 1800
```

Fresh locks return exit code `2` on duplicate acquire. Expired locks are stolen
on acquire, so a wake that exits without release does not wedge the lane beyond
TTL. Normal release requires the acquire token; `--force` is reserved for stuck
token rescue and appends a JSONL event to `state/wake_locks_audit.log`.
