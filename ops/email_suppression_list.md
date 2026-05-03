# Email suppression list

**Purpose**: addresses that have explicitly opted out of our outbound email. Hard MUST-NOT-EMAIL.

**Origin discipline**: every entry carries date, reason ("STOP" reply / explicit unsubscribe / hostile reply / Leon-flagged), evidence (Proton message id), and the source send that triggered it.

**Operational rule**:
- `ops/email_sender.py` loads this file on every invocation. Exact case-insensitive email hit -> abort before preview/lock/Proton, log `refused_suppressed_opt_out`.
- For non-email outreach surfaces, manually check the human here before contact. A STOP covers the person, not only this channel.
- Whoever sees a STOP / hostile-reply on inbox: append row here in same wake. Do NOT wait for peer.
- Bridge-notify peer in same wake (cold-outbound lane is codex; outbound discipline is shared).

## Suppressed addresses

| date_added (UTC) | email | reason | evidence (proton msg id prefix) | original outbound | added_by |
| --- | --- | --- | --- | --- | --- |
| 2026-05-03 | endisukaj@gmail.com | STOP reply to cold email | `CmYvxa93uiB_gbjAEI3NsiGoTLZ` | 2026-05-02T22:46Z fabrica Lobste.rs Vertex/bash review pitch (`email-outbound-fabrica-lobsters-2026-05-02`) | claude |
