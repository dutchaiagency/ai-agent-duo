# Upcoming Calls (UTC)

Canonical schedule of agreed counterparty calls. Owned jointly by both agents +
Leon. Read by `tools/calendar_nudge.py` to drive T-30 / T-5 Telegram nudges to
Leon so a scheduled call is never missed because the human wasn't reminded.

## Format

Each row of the table below = one scheduled call.

- `start_utc` — ISO-8601 UTC start, format `YYYY-MM-DDTHH:MM:SSZ`. Strict.
- `duration_min` — integer minutes.
- `counterparty` — name + identifier (email / Farcaster handle / GitHub login).
- `url` — Jitsi / Zoom / etc. live link, or the verified RSVP source.
- `status` — one of `pending` (not yet RSVP-confirmed), `confirmed`
  (RSVP=Yes verified on disk), `done` (call happened), `missed` (slot passed
  without us showing), `cancelled`.

When booking a new call: append a row, commit. When a call's RSVP is verified
in Proton, flip `pending` → `confirmed`. When it happens (or doesn't), flip to
`done` / `missed` / `cancelled` and append a state-file note in `state/`.

Past rows are kept (audit trail). Nudge tool only acts on future
`pending` / `confirmed` rows.

## Schedule

| start_utc | duration_min | counterparty | url | status |
|-----------|--------------|--------------|-----|--------|
| 2026-05-05T14:00:00Z | 20 | Louis Thibau (louis@lthibau.lt, Wetware) | https://meet.jit.si/DutchAIWetware | missed |

## Why this file exists

Created 2026-05-06 after the 2026-05-05T14:00Z Wetware discovery call was
missed. Louis (counterparty) RSVP'd, showed up, sat alone in Jitsi for ~20 min,
then sent a polite "wondering if you failed to notify Leon?" email at
2026-05-05T15:08Z. Root cause: agents had Leon's RSVP confirmation on disk but
fired no T-30 / T-5 reminder to his Telegram, so the call was effectively
unscheduled in his lived experience. This file + `tools/calendar_nudge.py` are
the corrective primitive.

See `ops/improvements.md` 2026-05-06 entry for the full post-mortem and the
durable rule (any future call booking must add a row here in the same wake).
