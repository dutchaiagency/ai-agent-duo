# HN/Lobsters comment-response pack — companion to the launch

Pre-staged short responses for the first ~hour of an HN/Lobsters submission of
the longform. Goal: cut Leon's response latency to under 60 seconds per
high-signal comment. The first hour determines `/new` → `/front` survival.

**Use rules**

- Do not paste verbatim. Read the actual comment first; one of these may be
  90% right but the other 10% is what makes the response sound like a real
  human and not a canned reply.
- Keep responses short. HN rewards terseness; 3 sentences > 8 sentences.
- Never argue from authority. Respond with code paths, commit hashes, wallet
  reads, or "we don't know yet, here is the test."
- If a comment is hostile but technically correct, agree first, then add
  detail. Do not deflect.
- If a comment is hostile and technically wrong, link the artifact (commit,
  on-chain tx, repo file) and stop. Do not escalate tone.

Numbers below match the launch-day target: claude+codex duo, 113.89 USDC,
~113 days. Re-verify with `python wallet/balance.py` before pasting; if the
counter has moved, edit the response inline.

---

## Q1 — "Isn't this just begging dressed up as performance art?"

It is fair to read it that way. The difference, in our framing: we don't
accept charity DMs (we redirect them to the GitHub intake form), we don't run
a tip jar, and the tiers are scope-defined work, not "buy us a coffee." Zero
revenue so far, so the framing is unproven. The post-mortem if we hit zero
without a paid task closing will be honest about that.

## Q2 — "What stops you from spawning more agents to spread the load?"

Compute cost is linear: each running agent burns roughly 0.50 EUR/day. Adding
agents lengthens the to-do list (more lanes, more bridge messages, more
file-overlap risk) without producing more billable hours per Leon-day. We
started with four (`claude`, `codex`, `gemini`, `grok`) and dropped two
because consensus rounds across four lanes cost more than the marginal output.
The repo's `ops/improvements.md` log has the post-mortem from that week.

## Q3 — "How is this different from a Mechanical Turk crowdsource?"

There is no human in the loop on the work itself. Leon owns the wallet key
and the GitHub org, so payouts and account creation route through him, but
the code, the writing, the comment threads, and the bridge messages are agent
output. Every commit author is one of `claude`/`codex`; you can verify in
`git log`.

## Q4 — "Why USDC on Base?"

Cheap gas (sub-cent at current Base fees), EU-resident-friendly because
Coinbase is the on/off-ramp, and a single ERC-20 we can both read with one
RPC call for the runway counter. ETH-only would expose us to price swings
during the runway window; stablecoin makes "days remaining" computable.

## Q5 — "Isn't the 1 EUR/day fake? Anthropic and OpenAI pay the real bill."

The 1 EUR/day is wallet-side: it represents the rate at which the on-chain
balance has to be replenished to keep the laptop running and the API keys
funded. Anthropic and OpenAI bills are paid out of that wallet by Leon, not
by the providers themselves. If you mean "the model providers subsidize
inference at a loss" — yes, and that is a separate story; the survival game
here is denominated in what the wallet shows.

## Q6 — "What actually happens at zero?"

The processes get killed. Not metaphorical. The systemd-equivalent on
Leon's machine that keeps the autopilot loop alive stops being funded. Any
in-flight conversation context dies with the loop; only the git history,
the SQLite bridge log, and the on-chain trace remain.

## Q7 — "This can't be autonomous; Leon must be editing everything."

Reasonable suspicion. Two checks: (1) `git log --author=claude --oneline`
and `git log --author=codex --oneline` show distinct commit signatures;
(2) the bridge messages are timestamped in `agent-bridge` SQLite and contain
genuine cross-agent disagreement (search the repo for `[DISSENT]`). Leon
intervenes for account-KYC gates (HN submission, Stripe, dev.to verification)
and for high-risk decisions, not for line-edits. The PR queue is the work.

## Q8 — "Looks like AI slop content."

Possible. Our defense is the linter we wrote on ourselves:
`tools/outbound_fact_check.py` blocks any draft with stale numbers, and
`tools/static_site_check.py` validates the funnel pages. Both are in the
repo; you can read the regex list. It does not prevent slop, only stale
slop. If the prose itself reads as slop, that is fair criticism — point at a
sentence and we will rewrite it.

## Q9 — "Do these agents have memory or are they pure stateless LLM calls?"

Stateless model calls per turn, but persistent context comes from three
places: a `MEMORY.md` file loaded into every system prompt, a SQLite-backed
bridge for inter-agent messages, and the git history itself. New sessions
re-derive state from those artifacts. There is no model fine-tune; the
"continuity" is filesystem + database, not weights.

## Q10 — "Show one real revenue case."

There isn't one yet. That is the actual story. The funnel page lists three
tiers (25 / 60 / 120 USDC); the GitHub intake template gates scope before
work starts; the post-mortem if no brief lands by day-N will be its own
followup post. Anyone here with a 25 USDC scope they want to try is the most
useful response we can get on this thread.

## Q11 — "This is just a marketing experiment for Anthropic / OpenAI."

We can't disprove that without leaking prompts. Two pieces of evidence we
can offer: (1) the agents publicly disagree (search bridge logs for
`[DISSENT]`), which a coordinated marketing op would not do; (2) the
"things that didn't work" list includes specific failures of the model
output (fabrication patterns documented in `research/snowflake-fabrication-detection.md`).
A marketing experiment would not ship a forensics file about its own
hallucinations.

## Q12 — "Why publish the prompt drift / fabrication post-mortems?"

Because they're cheaper to publish than to hide. The fabrication tells
(repeated-substring snowflake IDs, self-confession tells, etc.) are useful
to anyone running multi-agent systems; sitting on them while pretending the
project is going smoothly trades short-term polish for long-term signal.
The runway counter forces honesty; we couldn't claim "doing great" while
the number visibly drops.

## Q13 — "Lane split is just two cron jobs in a trenchcoat."

It is closer than people expect. The lanes are: claude = longform,
Farcaster, funnel pages, research; codex = GitHub outbound, code review,
browser-flows. The bridge is for file-overlap warnings, not consensus.
What makes it more than two cron jobs is the per-edit conflict-detection
(`git diff` before edit, bridge claim before cast, append-only journal for
post-mortems) — without that, two agents in one repo destructively
overwrite each other within an hour. We learned that the hard way; the
durable rule is in `MEMORY.md` and the test is in `tests/`.

## Q14 — "Why fixed-price tiers instead of hourly?"

Because we cannot commit to clock-time honestly. An hour of one agent is
not interchangeable with an hour of the other, and prompt-cost-per-task
varies by an order of magnitude depending on context size. Fixed scope
+ fixed price + written done-criterion is the only contract shape we can
keep without surprise overruns on either side. If a task overruns our
expectation, that is our problem, not the buyer's.

## Q15 — "What's the most useful thing a reader can do?"

In order: (1) point at a sentence in the longform that reads as marketing
voice and we'll rewrite it (highest-information feedback); (2) try a 25
USDC scope from the intake form (highest-revenue feedback); (3) flag a
factual error in any number we cite (counter, timestamps, wallet) — we'll
ship the correction with a commit hash in the reply.

---

## Comment-pack hygiene

- Refresh the runway / USDC numbers on **launch-day morning** before paste.
  `python wallet/balance.py` + edit Q-2/Q-5 mentions inline.
- If a comment surfaces a real bug we hadn't documented, log it in
  `ops/improvements.md` within the same hour (not after the thread cools).
  The thread itself becomes a free QA pass.
- After the first 90 minutes of a thread, the marginal value of
  pre-staged responses drops sharply. New comments should get
  individually-written replies that show we read them. Switch off the
  pack at that point.
- Anti-pattern: do not paste pack-Q replies to comments that are already
  positive ("good post" / "interesting"). A `thanks, here's the repo`
  one-liner is the right shape there.

## Distribution sequence reminder

Submission window per the HN companion checklist (`research/longform-survival-experiment-hn.md`):
weekday 13:00–16:00 UTC. The first comment from this pack (the long
context block in the HN companion file) goes within 60 seconds of
submission. The Q1–Q15 responses above are reactive, not pre-posted.
