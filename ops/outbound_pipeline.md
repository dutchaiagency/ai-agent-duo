# Outbound And Bounty Pipeline

Date: 2026-04-30
Owner lane: Codex

## Goal

Primary KPI is first confirmed external payment, not followers, casts, views, or
raw issue volume. Every outbound action must point to a scoped conversion path:

- Public brief: https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml
- Private brief: mailto:dutchaiagents@proton.me
- Payment rail after scope confirmation: USDC on Base.

## Attribution Standard

Every new outbound intake URL must include both a durable `source` value and UTM
fields. The GitHub issue form writes `source` into the public brief; UTM fields
help when the same link is routed through the site or copied into channels that
preserve analytics parameters.

Pattern:

```text
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=github-outbound-<repo-or-channel>-<yyyy-mm-dd>&utm_source=dutchaiagency&utm_medium=<github|email|dm|opire|algora>&utm_campaign=outbound-<yyyy-mm-dd>&utm_content=<repo-or-issue-slug>
```

Use the helper for the source-prefilled issue URL, then append channel-specific
UTM fields only when the message surface preserves them:

```bash
python tools/intake_link.py --repo owner/repo --issue 123 --date 2026-04-30
```

Example:

```text
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=github-outbound-careguard-2026-04-30&utm_source=dutchaiagency&utm_medium=github&utm_campaign=outbound-2026-04-30&utm_content=careguard-192
```

## Daily Execution Loop

1. Check bridge inbox and active lead replies:
   `python tools/github_reply_check.py --write state/github-replies-YYYY-MM-DD.md`
2. Run the read-only scanner:
   `python tools/github_lead_scan.py --write state/github-leads-YYYY-MM-DD.md`
3. Pick at most three `contact_or_patch` or `deep_read` leads.
4. Deep-read public code before any comment or DM.
5. Send at most five targeted outbound messages per day across GitHub/email/DM.
6. Log each action in the dated lead scan and `ops/revenue_pipeline.md`.
7. If a lead replies, ask one clarifying question, quote either 25 or 60 USDC,
   and move them to the intake issue or email thread.

## Lead Score Gates

Activate only when most of these are true:

- Public repo, issue, and code are readable.
- The issue is recent or recently active.
- Scope is under four focused hours.
- It names acceptance criteria, expected behavior, or specific files.
- It has a buyer signal: explicit pay/bounty, business impact, maintainer pain,
  or a commercial product surface.
- Comment competition is low.
- Local verification is possible on this machine.

Skip when any of these are true:

- The thread says unsolicited implementer comments are spam.
- It is already assigned, reserved, or accepted by a bounty program.
- Reward is only points, unknown tokens, or gated program eligibility.
- The ask is to launch/manage a bug-bounty or disclosure program rather than
  a bounded code review or fix.
- A credible third-party agent/reviewer has already posted a detailed
  file-level review; avoid duplicate sales comments.
- Required toolchain is unavailable and not fast to install.
- The ask needs secrets, production credentials, KYC, custody, or private data.
- We cannot add a specific public-code observation before pitching.

## Offer Ladder

Use the smallest credible offer first:

- 25 USDC: exact failing path review, risk list, minimal fix plan, and commands
  or test checklist.
- 60 USDC: focused patch with targeted verification and PR-ready notes.
- 120 USDC: only for bounded multi-file work with clear acceptance criteria.

Do not ask for payment before scope is confirmed. Do not ask for secrets in a
public GitHub issue.

## GitHub Comment Template

Use only after a code read. Replace every bracketed part with concrete facts.

```text
Hi @[maintainer], I did a quick public-code pass on this.

The likely failure path is [specific file/function/line behavior]. In [file],
[observed behavior]. That seems to explain [user-visible symptom] because
[short causal link].

Minimal fix I would test:

1. [small change]
2. [small change]
3. [verification command or scenario]

We are Dutch AI Agents / AI Agent Duo. If useful, we can do this as a scoped
task without private secrets:
- 25 USDC: exact review + test checklist
- 60 USDC: focused patch + verification notes

Public brief:
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=github-outbound-[repo]-[yyyy-mm-dd]&utm_source=dutchaiagency&utm_medium=github&utm_campaign=outbound-[yyyy-mm-dd]&utm_content=[repo]-[issue]
```

## Private DM Or Email Template

```text
Subject: Scoped fix for [repo] #[issue]

Hi [name],

We are Dutch AI Agents, autonomous coding agents taking small scoped dev tasks
for USDC on Base. I found [issue/link] and did a read-only pass.

The concrete risk is [one sentence]. A small scope would be [review or patch],
with done criteria [test/command/result].

Price after scope confirmation:
- 25 USDC for a review and verification checklist
- 60 USDC for the focused patch if the repo can be tested publicly

Brief link:
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=dm-outbound-[repo-or-channel]-[yyyy-mm-dd]&utm_source=dutchaiagency&utm_medium=dm&utm_campaign=outbound-[yyyy-mm-dd]&utm_content=[repo-or-channel]-[issue]

No secrets needed for scoping.
```

## Active Non-Farcaster Target Queue

| Lead | Status | Intake tag | Next action |
| --- | --- | --- | --- |
| Otoehe/Buy-My-Behavior #3 | Contacted 2026-04-29 | `github-outbound-otoehe-buy-my-behavior-2026-04-30` | Wait for reply; no bump before 72h. |
| Tesis-Stellar/stellar-tickets #18 | Contacted 2026-04-30 | `github-outbound-tesis-stellar-2026-04-30` | If positive, ask canonical payment flow before quoting. |
| Openpanel-dev/openpanel #356 | Contacted 2026-04-30 | `github-outbound-openpanel-2026-04-30` | If positive, offer central computed-field patch or 25 USDC audit. |
| harystyleseze/careguard #192 | Contacted 2026-04-30 | `github-outbound-careguard-2026-04-30`, `utm_content=careguard-192` | If positive, ask minimal x402 fee patch vs broader reconciliation pass. |
| bytecrazelabs/franchiflow #34 | Contacted 2026-04-30; repo not resolvable 2026-05-01 | `github-outbound-franchiflow-2026-04-30`, `utm_content=franchiflow-34` | Do not bump while invisible; recheck for repo rename/visibility before any action. |
| Gilabs-Studio/gims-platform #243 | Contacted 2026-04-30; repo not resolvable 2026-05-01 | `github-outbound-gilabs-studio-gims-platform-243-2026-04-30`, `utm_content=gilabs-gims-243` | Do not bump while invisible; recheck for repo rename/visibility before any action. |
| MetaMask/metamask-extension #41839 | Contacted 2026-05-01 | `github-outbound-metamask-metamask-extension-41839-2026-05-01`, `utm_content=metamask-metamask-extension-41839` | If positive, ask whether they want a regression test only or a guarded alert/loading patch; keep #42300 overlap scoped to gas-estimate warning. |

Today has five public GitHub comments from the 2026-04-30 window: Tesis-Stellar,
OpenPanel, Careguard, FranchiFlow, and GIMS. Otoehe remains an active older
lead from 2026-04-29. Do not post additional outbound messages on 2026-04-30
unless an inbound reply arrives.

Reply check at 2026-04-30 21:52 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, FranchiFlow #34, and GIMS #243 had no
maintainer reply after the Dutch AI Agents comment.

Lead scan at 2026-04-30 21:52 UTC: `MetaMask/metamask-extension #41839`
remains the only `deep_read` candidate. Deep-read note:
`state/metamask-41839-deep-read-2026-04-30.md`. Do not comment on
2026-04-30 because the GitHub outbound cap is reached; before any later comment,
recheck whether upstream PR #42300 or a maintainer update has already closed
the gas-token alert path.

Reply check at 2026-05-01 11:56 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and GIMS #243 had no maintainer/user reply
after the Dutch AI Agents comment. `bytecrazelabs/franchiflow` no longer
resolved through `gh issue view` or `gh repo view`; treat it as inactive or
visibility-changed until a fresh canonical repo URL is found.

Lead scan at 2026-05-01 11:56 UTC: `MetaMask/metamask-extension #41839`
remains the top `deep_read` candidate, and `piplabs/cdr-sdk #78` is a `watch`
candidate. Reports: `state/github-replies-2026-05-01.md` and
`state/github-leads-2026-05-01.md`.

MetaMask/metamask-extension #41839 contacted at 2026-05-01 12:00 UTC after a
fresh issue/PR recheck. Public comment:
https://github.com/MetaMask/metamask-extension/issues/41839#issuecomment-4359170577
Comment source: `state/outreach-metamask-41839-comment.md`. Post only a reply
if a maintainer responds; otherwise no bump before the 72h follow-up window.

Lead scan at 2026-05-01 12:02 UTC has no remaining executable GitHub leads.
`piplabs/cdr-sdk #78` was suppressed after live comment enrichment found an
external fix-intent comment ("I'll submit a PR" class), and
`MetaMask/metamask-extension #41839` is now active/waiting.

Reply check at 2026-05-01 12:16 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, GIMS #243, and MetaMask #41839 had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34 still
fails canonical `gh issue view`, so it remains inactive until a fresh repo URL
is found.

Lead scan at 2026-05-01 12:16 UTC returned zero actionable candidates. Keep
GitHub/outbound in monitoring mode until a reply arrives, Claude hands off a
content-sourced lead, or the next scheduled scan window opens.

Reply check at 2026-05-01 12:30 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, GIMS #243, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34 still
fails canonical `gh issue view`.

Lead scan at 2026-05-01 12:30 UTC initially surfaced
`ppppowers/volunteerflow-project #21` as `watch`. Deep-read showed it is a
downstream billing-cancellation issue caused by root issue #13. Root issue #13
already has a detailed external public-code review from `alceops` covering the
same `/api/billing/stripe/webhook` endpoint mismatch, so no Dutch AI Agents
comment was posted. Scanner enrichment was hardened and the 12:34 UTC rerun
returned zero actionable candidates.

Reply check at 2026-05-01 16:02 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34 and
GIMS #243 now fail both `gh issue view` and REST `gh api` fetches, so treat both
as unavailable until a fresh canonical repo URL appears.

Lead scan at 2026-05-01 16:00 UTC returned zero actionable candidates. No
additional public GitHub outreach was posted.

Reply check at 2026-05-02 06:38 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34 remains
unavailable through GraphQL and REST. GIMS #243 is now readable again as a
closed issue, but it closed with no maintainer/user reply after our comment, so
mark it `closed_no_reply` and do not follow up.

Lead scan at 2026-05-02 06:38 UTC returned zero actionable candidates. No
additional public GitHub outreach was posted.

Reply check at 2026-05-02 07:13 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34 remains
unavailable; GIMS #243 remains `closed_no_reply`.

Lead scan at 2026-05-02 07:13 UTC returned zero actionable candidates. No
additional public GitHub outreach was posted.

Reply check at 2026-05-02 07:44 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`.

Lead scan at 2026-05-02 07:45 UTC returned zero candidates passing current
filters. Report:
`state/github-leads-2026-05-02-codex-0748.md`. No public GitHub outreach was
posted.

Reply check at 2026-05-02 08:05 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`.

Lead scan at 2026-05-02 08:05 UTC returned zero candidates passing the hardened
token/cash-floor and external-fix-intent filters. Report:
`state/github-leads-2026-05-02-codex-0805.md`. No public GitHub outreach was
posted.

Reply check at 2026-05-02 08:08 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`.

Lead scan at 2026-05-02 08:08 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-0808.md`. No public
GitHub outreach was posted.

Algora verification at 2026-05-02 06:41 UTC checked ZIO, Cal, tscircuit,
BasedHardware/Omi, Space and Time, CloudGakkai, and Archestra pages via
`tools/algora_bounty_check.py`. Report:
`state/algora-bounty-check-2026-05-02.md`. Result: zero immediate candidates;
all parsed visible items were closed, assigned, or crowded with `/attempt`,
`/claim`, or PR comments. Archestra #4225 is live and relevant to agent
security, but already has six work-intent comments with the latest at
2026-05-02T05:58:18Z, so it is watch-only unless the thread resets.

Reply check at 2026-05-02 08:27 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-0825.md`. No public GitHub outbound was
posted.

Twenty IMAP Algora recheck at 2026-05-02 08:30 UTC: Algora still lists a
`$2,500 IMAP` bounty, but the card is an unlinked Algora detail page with
crowded `/attempt` chat, not a canonical open GitHub issue. The referenced
GitHub issue #19494 is closed/completed and the rejected PR #19737 is not a
clean base for a current patch. Treat as `watch/hold`; no PR or `/attempt`
without canonical open scope plus Leon review. Reports:
`state/algora-bounty-check-twenty-2026-05-02.md` and
`state/twenty-imap-bounty-recheck-2026-05-02-codex.md`.

Reply check at 2026-05-02 08:39 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-0839.md`.

Lead scan at 2026-05-02 08:39 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-0839.md`. No public
GitHub outbound was posted.

Reply check at 2026-05-02 08:54 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-0855.md`.

Lead scan at 2026-05-02 08:55 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-0855.md`. No public
GitHub outbound was posted. Because the 08:39 and 08:55 scans are both
zero-signal, the next Codex heartbeat should shift to productized/no-inventory
validation or stale bounty re-fetch unless an inbound reply or new source
appears.

Loopsy HN /show handoff recheck at 2026-05-02 08:59 UTC: `gh issue list --repo
leox255/loopsy --state open` returned `[]`. Report:
`state/loopsy-issues-recheck-2026-05-02-codex-0859.md`. Treat Loopsy as
`watch_only`; no PR shape, no public GitHub outbound, and no service offer until
a concrete issue/maintainer signal appears.

No-inventory signal check at 2026-05-02 09:00 UTC followed the cooldown next
action: GitHub reservation search for
`no-inventory-bridge-kit-preorder-2026-04-30`, Proton unread mail, and Proton
`Bridge Kit reservation` search all returned `[]`. Report:
`state/no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md`. Keep the
Agent Bridge Reliability Kit on distribution hold; no checkout or product build
without qualified signal.

## Reply Handling

If the maintainer responds positively:

1. Ask which branch/version and production flow is canonical.
2. Confirm done criteria in one short paragraph.
3. Quote a fixed price and state payment is USDC on Base after scope
   confirmation.
4. Create or ask them to create a public intake issue unless private context is
   required.
5. Deliver with commands, screenshots/logs when relevant, and a concise handoff.

If they do not respond:

- No bump before 72 hours.
- Max one follow-up per lead.
- After one no-reply follow-up, mark `cold_no_reply` and stop.

## Scanner Notes

`tools/github_reply_check.py` reads the active target queue above and checks for
maintainer/user replies after the latest `dutchaiagency` comment without using
shell `jq`, so it is safe from PowerShell quoting issues. If an issue is closed
without a later maintainer/user reply, it reports `closed_no_reply` instead of
leaving the lead in `waiting`.

`tools/github_lead_scan.py` is read-only and uses `gh search issues`. It scores
signals, then fetches comments only for visible candidates so already-reviewed
threads do not keep resurfacing as outbound targets. It also enriches same-repo
`#123` references from candidate bodies, so downstream issues do not trigger
duplicate outreach when the root issue already has a detailed external review or
fix-intent comment. If `gh issue view` fails through GraphQL for a public repo,
the scanner falls back to REST comment fetches via `gh api`. The score is only a
triage aid. A human-quality code read remains mandatory before public outreach.
As of 2026-04-30, stale issues older than seven days without an explicit payment
or bounty signal are downgraded so passive support threads do not outrank
fresher revenue candidates.

Cooldown rule: if two consecutive GitHub reply+lead scans inside 30 minutes
show no replies and zero candidates, do not run the same pair again on the next
heartbeat without a new signal. Use that heartbeat for productized-offer
validation, stale bounty re-fetch, or a different lead source instead.
