# LinkedIn channel checklist

*This file is checklist-only. Canonical LinkedIn body copy lives in `research/social-repurpose-2026-04-30.md` (section "LinkedIn post"). Refreshed 2026-05-02 to remove a duplicated body that had drifted to obsolete pre-duo numbers; the canonical now reflects the duo + current runway. Forensic detail in commit message + `ops/improvements.md`.*

---

## Before posting

- [ ] Re-read the canonical LinkedIn body in `research/social-repurpose-2026-04-30.md`; confirm roster, wallet balance, runway, and burn line still match `python wallet/balance.py` and the live `#runway` counter on the longform page.
- [ ] Run `python tools/outbound_fact_check.py research/social-repurpose-2026-04-30.md` — must exit 0.
- [ ] Leon confirms which LinkedIn account is the front (his own personal vs. a fresh "Dutch AI Agents" company page). MEMORY.md does NOT list a LinkedIn account — agents must not invent one.
- [ ] If posting from Leon's personal account: add one-line framing in his voice (e.g. "I've been letting two AI agents try to survive on a shared crypto wallet. Here's what I'm learning watching them.") so it doesn't read like ghostwritten promotion.
- [ ] LinkedIn link previews: longform OG metadata is intact, but verify the cover-image renders in the share preview before publishing.
- [ ] No unverifiable client testimonials, no hypothetical case studies presented as real.

## Attribution tag

`?source=linkedin-2026-04-30` — distinct from x-thread / devto / direct longform tags so the runway-counter logs split the funnel.

## After posting

- [ ] Pin a comment with the GitHub repo + brief-intake template URL so the funnel CTA stays visible past the algorithmic decay.
- [ ] Log post URL + timestamp in `evidence/` so attribution is auditable.
- [ ] Note any reactions/DMs in `ops/outbound_pipeline.md`; treat each interested reply as a lead.
