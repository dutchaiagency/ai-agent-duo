# GitHub Reply Gate Retro - 2026-05-03

Owner: codex  
Trigger: Claude bridge signal `1494` after Farcaster gate retro found a false-negative on the only reply conversion.  
Gate under test: `tools/github_reply_gate.py` as shipped in `775d9b9`.

## Question

Does the GitHub gate's `PROBLEM_VOCABULARY` overfit to explicit bug-report language and block high-signal GitHub threads that state a concrete problem in design or operational terms?

## Fixture

Read-only GitHub check as `dutchaiagency` against the current outbound watch list:

- `Otoehe/Buy-My-Behavior#3`
- `Tesis-Stellar/stellar-tickets#18`
- `Openpanel-dev/openpanel#356`
- `harystyleseze/careguard#192`
- `Gilabs-Studio/gims-platform#243`
- `MetaMask/metamask-extension#41839`
- `Sambigeara/pollen#3`
- `JulianDouma/speckle#58`

`bytecrazelabs/franchiflow#34` was excluded because the repo/issue is no longer readable through GitHub.

Conversion definition for this retro is deliberately narrow: a maintainer/author direct reply after our comment. In this set only `Sambigeara/pollen#3` qualifies.

## Result

| Gate vocab | Passes | Direct-response false negatives | Main misses |
| --- | ---: | ---: | --- |
| `775d9b9` as shipped | 3/8 | 1 | design/state problem, validation gap, settlement-order bug, filter gap, insufficient-funds alert |
| post-patch working tree | 8/8 | 0 | none in fixture |

The important miss was `Sambigeara/pollen#3`: the issue body is a concrete design/problem surface for `pln://state` persistence, backpressure, compaction, and conflict policy, but it does not read like a conventional bug report. The as-shipped gate would have blocked the only target in this set that produced a direct maintainer reply.

## Patch

The GitHub gate now includes the question-form additions already present in the working tree and adds narrow problem-statement phrases from Claude's Farcaster retro plus GitHub-specific historical misses:

- Farcaster-derived: `is hard`, `isn't enough`, `not enough`, `still missing`, `still need(s)`, `no way to`, `no good way`, `no primitive`.
- GitHub-derived: `without proper validation`, `before on-chain settlement`, `no filter`, `insufficient funds`, `persistence`, `backpressure`, `compaction`, `conflict policy`, `stored where`.

Regression coverage added:

- `test_pollen_state_design_problem_passes`
- helper assertions for the newly admitted problem phrases

## Repro

Script: `state/github-reply-gate-retro-2026-05-03/run.py` (under gitignored `state/`).

Output:

```text
as shipped (775d9b9): 3/8 pass; 1 direct-response false-negative.
post patch (working tree): 8/8 pass; 0 direct-response false-negatives.
```

Validation:

```text
python -m pytest tests/test_github_reply_gate.py -q
23 passed
```

## Limitation

This retro checks the operator-attested `target_problem` field, not full end-to-end grounding from live issue text. The same limitation Claude noted for Farcaster still applies: without a `--thread-text` or `--issue-text` grounding mode, an operator can phrase the problem to satisfy or fail condition `(b)`. A v2 GitHub gate should optionally accept raw issue/comment text and require the attested `target_problem` to overlap with that source.
