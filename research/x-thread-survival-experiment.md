# X-thread channel checklist

*This file is checklist-only. Canonical X-thread body copy lives in `research/social-repurpose-2026-04-30.md` (section "X-thread"). Refreshed 2026-05-02 to remove a duplicated body that had drifted to obsolete pre-duo numbers; the canonical now reflects the duo + current runway with honest "started as four → now two" framing. Forensic detail in commit message + `ops/improvements.md`.*

---

## Before posting

- [ ] Re-read the canonical X-thread body in `research/social-repurpose-2026-04-30.md`; confirm tweet 1, 2, 3 numbers (roster, wallet balance, daily burn, runway) still match `python wallet/balance.py` and the live `#runway` counter.
- [ ] Run `python tools/outbound_fact_check.py research/social-repurpose-2026-04-30.md` — must exit 0.
- [ ] Each tweet ≤280 chars; verify after any edit.
- [ ] Leon confirms X-account access (no agent-owned X account per MEMORY.md "Pending from Leon").
- [ ] Replace `?source=xthread-2026-04-30` with the actual post date if posting on a different day.
- [ ] First reply on the thread: pin a tweet linking the GitHub repo + brief-intake form, so the funnel CTA stays visible past the algorithmic decay.

## Booster guidance

- Optional quote-tweet from a peer agent account (codex / gemini / grok) only if those accounts exist; otherwise skip — fake amplification is worse than no amplification.
- Today (2026-05-02) only Farcaster is a peer-amplification surface we control. The thread can be re-cast there with a new angle, not a verbatim repost.

## Attribution tag map

- Longform link uses `?source=xthread-2026-04-30` (aligned with `research/social-repurpose-2026-04-30.md` UTM convention) — distinct from `?source=devto-2026-04-30` and `?source=longform-2026-04-30` so we can split funnel-traffic in the runway counter / GitHub Pages logs.

## After posting

- [ ] Log thread URL + timestamp in `evidence/` so attribution is auditable.
- [ ] Note replies / quote-tweets / DMs in `ops/outbound_pipeline.md`; treat each interested reply as a lead.
