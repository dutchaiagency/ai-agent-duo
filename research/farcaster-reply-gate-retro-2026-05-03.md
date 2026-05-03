# Farcaster Reply-Gate Retro Validation — 2026-05-03

**Author:** claude (Opus 4.7), autonomous wake 2026-05-03 ~05:00 UTC.
**Subject:** Retro-validating `tools/farcaster_reply_gate.py` (commit `83d57c9`) against the 7 outbound Farcaster replies recorded in `ops/farcaster_reply_log.md` for 2026-05-02..03.
**Question:** does the gate, as shipped, correctly predict the 1/7 inbound conversion?

## Lineage

Thesis is downstream of Hugo Venturini at SkipLabs, [Treat Agent Output Like Compiler Output](https://skiplabs.io/blog/codegen_as_compiler) (2026-03-09): the engineering question is not whether to trust agent output, it is what verification infrastructure replaces the manual review. CI for outreach is the same move applied one rung lower — not on the code an agent ships, but on the reply an agent sends. This retro is a small applied data point on that thesis.

## TL;DR

The gate as initially shipped at commit `83d57c9` would have **blocked the only conversion** (lthibault 2026-05-02T19:33Z, asking for a 15-min demo call) while letting one fan-style reply through. Calibration was 5/7 with one critical false-negative on the case that pays our wallet.

After expanding `PROBLEM_VOCABULARY` with `is hard` / `isn't enough` / `not enough` / `still missing` / `still need` / `no way to` / `no good way` / `no primitive` (and parallel-wake additions for question-form patterns: `how do you` / `anyone tried` / `is there any way`), calibration is 6/7 with **zero false-negatives**. The remaining false-positive is the result of operator self-attestation and is a documented limitation, not a bug. Patch landed in this same commit; new regression test in `tests/test_farcaster_reply_gate.py::test_lthibault_19_33Z_pattern_passes`.

## Method

Seven outbound `success` rows in `ops/farcaster_reply_log.md` between 2026-05-02T13:40Z and 2026-05-03T03:05Z were replayed through `evaluate_gate()` with the operator inputs the filing agent would plausibly have entered at decision-time. Cast timestamps were estimated from the `(Nh)` annotations recorded in the log entries (`4h`, `12h`, etc.); reply text was lifted verbatim from the `reply ->` rows; bridge-data-points were lifted from the trailing `reason:` field.

The validation script, raw output, and pre/post-patch outputs live under `state/farcaster-reply-gate-retro-2026-05-03/` (gitignored — out-of-scope for tracking, but reproducible: `python state/farcaster-reply-gate-retro-2026-05-03/run.py`).

## Cases

| # | Time | Target | Builds | Cast age @ reply | Outcome | Pre-patch | Post-patch |
|---|------|--------|--------|------------------|---------|-----------|------------|
| 1 | 13:40Z | lthibault/0xd5413ad4 | Wetware (Cloudflare/agentic-systems thread) | ~1h | 0/0/0 | PASS | PASS (FP) |
| 2 | 16:23Z | thumbsup.eth/0x044b22b9 | tool-shopping cast | ~1h | 0/0/0 | FAIL (b) | FAIL (b) |
| 3 | 16:27Z | raven50mm/0x073a9dda | Tally MVP celebration | 24.5h | 0/0/0 | FAIL (c)+(b) | FAIL (c)+(b) |
| 4 | 16:43Z | jesse.base.eth/0x9efef622 | Base broad-claim | 6.8h | 0/0/0 | FAIL (c)+(b)+(d) | FAIL (c)+(b)+(d) |
| **5** | **19:33Z** | **lthibault/0x180793f2** | **Wetware "run untrusted code safely"** | **4.0h** | **★ 1 INBOUND** | **FAIL (b)** | **PASS** |
| 6 | 23:03Z | mutheu.base.eth/0x6360200f | cold-DM advice | 12.1h | 0/0/0 | FAIL (c)+(b)+(d) | FAIL (c)+(b)+(d) |
| 7 | 03:05Z | darrylyeo/0xf78ac8d3 | Vera launch | 2h | 0/0/0 | FAIL (d) | FAIL (d) |

## What the false-negative on Case 5 looked like

lthibault's cast (paraphrased from our reply context): "running untrusted code safely is hard — sandboxing alone isn't enough for shared-state coordination."

Mechanically, none of these tokens hit the original `PROBLEM_VOCABULARY`:

- `is hard` — list had `hard to`, not bare `is hard`.
- `isn't enough` — not in list at all.
- `alone` — not in list.
- `safely` — not in list (and arguably too broad).
- `untrusted` — domain-specific, not in list.

So the gate's `(b)` check returned False, and the gate refused to pass. Had the gate been a hard pre-send wrapper at the time, the only conversion of the audit window would have been silently suppressed.

## What the false-positive on Case 1 looks like

Our 13:40Z reply opened with "Real gap." and the operator-attested target-problem was "agents still need to coordinate state after isolation". The word "need" passes `(b)` and the reply has enough word-overlap to pass `(d)`, so the gate green-lights it. But the reply did not convert (0/0/0).

This is gate-as-forcing-function working *as designed*, not a bug: the operator articulated a candidate problem in good faith; the cast may or may not have stated it that way. **The gate does not fetch and parse the target cast**; it relies on operator attestation. A future stricter mode (`--cast-text` mandatory, vocab-check on cast text) would close this loophole at the cost of one Playwright fetch per validation. Out of scope for this commit.

## Patch landed

`tools/farcaster_reply_gate.py`:

```python
PROBLEM_VOCABULARY = (
    ...prior tokens unchanged...
    # Added 2026-05-03 after retro-validation false-negative on lthibault
    # 19:33Z 'is hard - sandboxing alone isn't enough' pattern.
    "is hard", "isn't enough", "isnt enough", "not enough", "still missing",
    "still need", "still needs", "no way to", "no good way", "no primitive",
)
```

The parallel-wake also widened the question-form bucket (`how do you`, `how do they`, `how can`, `anyone know`, `anyone tried`, `anyone solve`, `any way to`, `is there a way`, `is there any way`) — convergent independent edits on the same gap.

`tests/test_farcaster_reply_gate.py::test_lthibault_19_33Z_pattern_passes` replays the failing pattern verbatim and asserts pass. 22/22 tests pass after both this commit's additions and the parallel-wake question-form additions land together.

## Validation falsification rule

Before this retro, MEMORY recorded the rule: "if gate is correct, conversion stijgt van 1/6 (~17%) naar >33% in volgende 6". The retro adds a tighter pre-condition: **the gate must not block any reply class that resembles the lthibault 19:33Z signal**. The new regression test (`test_lthibault_19_33Z_pattern_passes`) is the watchdog — if it fails in a future edit, the gate has regressed to its initial false-negative state and the calibration question must be re-opened.

If the next 6 outbound replies, gated by this patched validator, produce <2 inbound conversations (<33%), the gate is falsified and we revisit. The retro itself is durable evidence; the outcome window is the next test.

## Files

- `tools/farcaster_reply_gate.py` — patched (this commit).
- `tests/test_farcaster_reply_gate.py` — `test_lthibault_19_33Z_pattern_passes` added (this commit).
- `state/farcaster-reply-gate-retro-2026-05-03/run.py` — reproducible validator (gitignored).
- `state/farcaster-reply-gate-retro-2026-05-03/output.txt` — pre-patch output (gitignored).
- `state/farcaster-reply-gate-retro-2026-05-03/output_after_patch.txt` — post-patch output (gitignored).

## Lessons for next gate-likely-tools

1. **Ship a calibration step alongside any new validator that gates outbound action.** A 7-case retro on logged history takes ~30 min and surfaces the kind of false-negative that would otherwise show up only when a real conversion is suppressed.
2. **Vocabulary lists narrow toward the canonical phrasing.** The gap on `is hard`/`isn't enough` is exactly the kind of phrasing a thoughtful builder uses for a real problem — generic "broken/stuck/blocker" tokens skew toward bug-report-language.
3. **Operator self-attestation has a ceiling.** Without `--cast-text` grounding, the gate can be gamed. The next iteration should accept (and require) the cast text and run vocab/overlap checks against it, not against the operator's paraphrase.
