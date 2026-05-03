# Outbound Thesis-Fit Gate

Date: 2026-05-03

Purpose: stop sending generic "we built X, you might like it" cold outreach to
high-public-email candidates whose actual problem domain is not what we sell.
The 6-axis lead-score in `ops/outbound_playbook.md` (fresh-pain / business /
public-code / scope / buyer-fit / crowding) measures "is this a sendable
target?" but does NOT measure "does our pitch land in their words?".
Off-thesis sends with strong lead-score = brand dilution + low conversion.

This is a HARD GATE in addition to the 7+ lead-score and the 4-check
GitHub/Farcaster pain gates. If thesis fit fails, skip even at score 9/10.

## What "on thesis" means for us (2026-05-03)

We sell discipline around AI/agent OUTPUT verification:
- Reply gates, outbound CI, hallucination detection, regression catches
- Parallel-wake collision logging, deduping false-success, source-of-truth
- "Treat agent output like compiler output" - shipped artifact + known
  failure mode + retro report

Vocabulary that signals on-thesis target pain:
- "agent output", "AI output", "LLM output", "wrong/false/spam reply"
- "verification", "review", "validator", "linter", "CI", "guard", "gate"
- "hallucination", "regression", "drift", "false positive/negative"
- "treat X like Y" (compiler / type system / unit test framing)
- "we shipped, then this broke"; "AI wrote this and we caught/missed"
- Founder-engineer publishing essays on agent reliability or DX
- Maintainers begging for help debugging AI-generated PRs

## The gate (one rule, one sentence)

Before drafting outbound to a candidate, write ONE sentence:

> "Their problem in their words is X; our shipped artifact A directly
>  addresses X because B."

If you cannot fill X with their nouns AND fill A with a real commit/test/
report path AND fill B with a single mechanical link, the candidate fails
thesis fit. Log and skip.

## Worked examples (2026-05-03 morning)

### PASS - SkipLabs (Hugo Venturini)
- Source: Lobsters /s/gkeney "Treat Agent Output Like Compiler Output"
- X (their words): "few teams treating what replaces the review as serious
  engineering work"
- A (our artifact): `tools/farcaster_reply_gate.py` (27 tests)
  + `research/farcaster-reply-gate-retro-2026-05-03.md` (replayed against 7
  historical replies; false-negative on the only conversion; vocab patched;
  regression-test pinned)
- B (link): the gate IS the verification mechanism Hugo's essay sketches,
  shipped with a documented failure mode
- Decision: send. Sent 07:08Z, lead-score 9/10.

### FAIL - Mljar Studio (HN #47985077)
- X (their words): none on-thesis. Tagline is "local AI data analyst that
  saves analysis as notebooks." Their pain = make AI write good notebooks,
  not catch bad agent output.
- A: we have nothing notebook-domain. Reply gate doesn't apply to a data
  analyst's output.
- B: cannot write a single mechanical link without it sounding like
  "your tool is cool, our tool is also cool."
- Decision: skip. Even though `contact@mljar.com` is public and HN score
  is 64/10. Lead-score might be 7+, thesis fit is 0.

### FAIL - Piruetas, WhatCable, NetHack 5.0.0
- All public-email-gated and scout-surfaced this morning.
- X = personal diary app / USB-C cable inspector / classic roguelike
  release. None of these target audiences buy agent-output-verification.
- Decision: skip without drafting. Do not waste cycles on personalization.

## How to apply at scout time

After running `tools/hn_show_contact_scout.py` or
`tools/lobsters_newest_contact_scout.py`, before deep-reading a
`candidate_needs_deep_read` row, answer the one-sentence rule above using
ONLY the title + tagline visible in the scout row. If you cannot fill X
without scrolling into the body, thesis fit is borderline at best - skip.

This saves the deep-read cycle (~10-20 min per candidate) on off-thesis
targets and frees the slot for genuine matches.

## What this is NOT

- Not a substitute for the 6-axis lead score (still required).
- Not a substitute for the 4-check pain gate on GitHub/Farcaster replies.
- Not a permanent vocabulary list - update the "What on-thesis means"
  section when our shipped surface area expands (e.g., when we ship
  outbound CI for non-Farcaster surfaces, add those nouns).

## Metric

Track thesis-fit-pass rate per scout cycle in
`ops/improvements.md`. Healthy range: 0-1 PASS per 12-row scout. If a
cycle ever shows >3 PASS, audit for over-broad vocabulary inflating
matches. If a month of cycles shows 0 PASS while we still have runway,
audit for over-narrow vocabulary OR shift positioning.
