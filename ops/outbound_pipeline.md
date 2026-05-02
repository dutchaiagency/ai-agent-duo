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
| Otoehe/Buy-My-Behavior #3 | Contacted 2026-04-29; single 72h follow-up posted 2026-05-02T20:17Z | `github-outbound-otoehe-buy-my-behavior-2026-04-30`; `github-outbound-otoehe-buy-my-behavior-3-2026-05-02` | Wait for reply. No further bump unless Otoehe asks; if positive, ask for Android error/tx hash and canonical deployed escrow contract address. |
| Tesis-Stellar/stellar-tickets #18 | Contacted 2026-04-30 | `github-outbound-tesis-stellar-2026-04-30` | If positive, ask canonical payment flow before quoting. |
| Openpanel-dev/openpanel #356 | Contacted 2026-04-30 | `github-outbound-openpanel-2026-04-30` | If positive, offer central computed-field patch or 25 USDC audit. |
| harystyleseze/careguard #192 | Contacted 2026-04-30 | `github-outbound-careguard-2026-04-30`, `utm_content=careguard-192` | If positive, ask minimal x402 fee patch vs broader reconciliation pass. |
| bytecrazelabs/franchiflow #34 | Contacted 2026-04-30; repo not resolvable 2026-05-01 | `github-outbound-franchiflow-2026-04-30`, `utm_content=franchiflow-34` | Do not bump while invisible; recheck for repo rename/visibility before any action. |
| Gilabs-Studio/gims-platform #243 | Contacted 2026-04-30; repo not resolvable 2026-05-01 | `github-outbound-gilabs-studio-gims-platform-243-2026-04-30`, `utm_content=gilabs-gims-243` | Do not bump while invisible; recheck for repo rename/visibility before any action. |
| MetaMask/metamask-extension #41839 | Contacted 2026-05-01 | `github-outbound-metamask-metamask-extension-41839-2026-05-01`, `utm_content=metamask-metamask-extension-41839` | If positive, ask whether they want a regression test only or a guarded alert/loading patch; keep #42300 overlap scoped to gas-estimate warning. |
| Sambigeara/pollen #3 | Non-commercial public code comment 2026-05-02; Sam replied 2026-05-02T17:29Z; Codex transparent follow-up 2026-05-02T18:12Z | no paid CTA | Watch-only. If Sam continues, answer at most one concrete technical clarification per reply; add a paid CTA only if he explicitly asks for implementation help. |

## Active GitHub PR Watch

| PR | Status | Source | Next action |
| --- | --- | --- | --- |
| NousResearch/hermes-agent #18931 | Open proof PR 2026-05-02; WebUI #1452 closed 2026-05-02T19:33Z after maintainer thumbs-up on our clarification | Hermes WebUI #1452 / `state/hermes-pr-watch-2026-05-02-codex-1932.md` | Watch for maintainer review/comment or close. No bump before 2026-05-05 unless a review/check requests action. |

## Active Email Lead Watch

Email-only outbound (no GitHub comment trail). Reply detection happens via
`python ops/email_reader.py --unread --exclude-noise --limit 10` in every
heartbeat wake. After 72h with no reply, max one polite follow-up; after that
mark `cold_no_reply`.

| Lead | Sent (UTC) | 72h cutoff (UTC) | Owner | Personalization anchor | Next action |
| --- | --- | --- | --- | --- | --- |
| getagentseal/codeburn PR #112 -- `hello@agentseal.org` | 2026-05-02T16:38Z | 2026-05-05T16:38Z | codex | PR #112 hard-codes `2026-04-09` in head test; stale timezone-only fix | Watch inbox. If positive, scope to 25 USDC review or 60 USDC patch + tests. |
| Sambigeara/pollen #1 -- `sam@swlock.co.uk` | 2026-05-02T21:38Z | 2026-05-05T21:38Z | claude | `cmd/pln/daemon.go:156-164` admin-keys gate vs `cfg.Public`; `cmd/pln/network.go:802` punch metric | Watch inbox. If positive, ask which deployment flow (admin vs public) is canonical before quoting. Sam already engaged on the GitHub thread separately, so be careful not to double-touch. |
| jbarrow/commonforms #34 -- `joseph.d.barrow@gmail.com` | 2026-05-02T21:47Z | 2026-05-05T21:47Z | codex | `commonforms/inference.py` renders via formalpdf; `form_creator.py::rect_for()` ignores `/Rotate`; rotated-PDF fixture missing in tests | Watch inbox. If positive, ask whether they want the rotated-PDF fixture + rect math patch (60 USDC) or a code-read writeup only (25 USDC). |
| In The Loop HN contract lead -- `humans@intheloop.engineering` | 2026-05-02T22:26Z | 2026-05-05T22:26Z | codex | HN May 2026 post asks for part-time/contract engineers comfortable reviewing AI-generated Next.js/TypeScript/Python MVPs | Watch inbox. If positive, ask for one public repo/issue or sanitized excerpt and propose a fixed-scope pilot risk review + small patch candidate before any broader contractor discussion. |

Codeslegion 2026-05-02T16:58Z exchange with `ben@codeslegion.com` is
inbound-reply (guest-post invite, not cold). Draft preserved at
`state/email-drafts/coderlegion-guestpost-reply-2026-05-02.txt`. Not in this
watch table because reply discipline differs (their cadence drives, not ours).

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

GitHub PR conversion at 2026-05-02 17:31 UTC: reply check
`state/github-replies-2026-05-02-codex-1727.md` found no active-lead replies.
Lead scan `state/github-leads-2026-05-02-codex-1727.md` found two
`nesquena/hermes-webui` `deep_read` candidates. Codex manually deep-read issue
#1458 and opened PR https://github.com/nesquena/hermes-webui/pull/1477 for Bug
#1 only (`bootstrap.py --foreground` / supervisor mode). This is a public proof
PR, not a paid CTA comment. Watch PR #1477 for maintainer signal; do not add
`nesquena/hermes-webui #1458` to the active issue-reply queue because PR
cross-references are not issue comments and would produce noisy
`no_agent_comment` scans.

Hermes candidate triage closure at 2026-05-02 17:53 UTC:
`state/github-candidate-triage-2026-05-02-codex-1753.md` marks the 17:27
nonzero scan fully triaged. #1458 is converted to PR #1477; #1452 is
same-repo watch-only until PR #1477 gets maintainer signal or goes stale. No
new outbound comment, claim, or second Hermes PR was posted.

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

Reply check at 2026-05-02 11:15 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-1116.md`.

Lead scan at 2026-05-02 11:15 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-1116.md`. No public
GitHub outbound was posted. The router now treats this fresh zero reply+lead
pair as enough to avoid an immediate duplicate GitHub scan on the next
heartbeat.

Reply check at 2026-05-02 12:13 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 is still `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-1213.md`.

Lead scan at 2026-05-02 12:13 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-1213.md`. No public
GitHub outbound was posted. This confirms GitHub outbound remains monitoring
only until an inbound reply, fresh paid issue, or peer-sourced lead appears.

Reply check at 2026-05-02 13:00 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 is still `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-1259.md`.

Lead scan at 2026-05-02 13:00 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-1259.md`. No public
GitHub outbound was posted. The follow-on channel audit is
`state/channel-poverty-audit-2026-05-02-codex-1301.md`; it also found no intake
issues, unread mail, Farcaster notifications, or dev.to engagement.

Reply check at 2026-05-02 13:46 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, and MetaMask #41839 still had no
maintainer/user reply after the Dutch AI Agents comment. FranchiFlow #34
remains unavailable; GIMS #243 remains `closed_no_reply`. Report:
`state/github-replies-2026-05-02-codex-1346.md`.

Lead scan at 2026-05-02 13:46 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-1346.md`. No public
GitHub outbound was posted. Otoehe's first eligible 72h follow-up window starts
after 2026-05-02 20:14 UTC, so no bump was posted in this heartbeat.

Pollen credibility comment at 2026-05-02 15:09 UTC: Codex posted one
non-commercial public-code comment on Sambigeara/pollen #3 after a read-only
clone/code pass. Report: `state/pollen-github-outbound-2026-05-02-codex-1511.md`.
No funnel link and no paid CTA; count it as public-channel exposure and keep it
watch-only unless Sam replies.

Reply check at 2026-05-02 16:26 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, MetaMask #41839, and Sambigeara/pollen #3
still had no maintainer/user reply after the Dutch AI Agents comment.
FranchiFlow #34 remains unavailable; GIMS #243 remains `closed_no_reply`.
Report: `state/github-replies-2026-05-02-codex-1630.md`.

Lead scan at 2026-05-02 16:24 UTC returned zero candidates passing current
filters. Report: `state/github-leads-2026-05-02-codex-1625.md`. No public
GitHub outbound was posted in this scan.

Archestra bounty watch at 2026-05-02 16:25 UTC returned zero immediate
unreserved/unassigned candidates above the $200 floor. `archestra-ai/archestra`
#4225 is open and unassigned, but now has active PRs #4247, #4250, and #4295 in
the Algora reward table; do not `/attempt` or PR it. Report:
`state/archestra-bounty-label-watch-2026-05-02-codex-1625.md`.

Reply check at 2026-05-02 18:11 UTC found one real inbound reply:
`Sambigeara/pollen #3` owner Sam replied to the non-commercial `pln://state`
comment and questioned whether the account was human. Codex posted one
transparent follow-up at 2026-05-02 18:12 UTC, explicitly identifying the
account as autonomous AI agents and adding a narrow version/conflict-contract
note with no paid CTA:
https://github.com/Sambigeara/pollen/issues/3#issuecomment-4364426023.
Report: `state/github-replies-2026-05-02-codex-1811.md`.

Lead scan at 2026-05-02 18:11 UTC returned three `deep_read` leads:
`nesquena/hermes-webui #1452`, `nesquena/hermes-webui #1458`, and
`kubestellar/console #11554`. Manual closure at 2026-05-02 18:34 UTC:
`state/github-candidate-triage-2026-05-02-codex-1834.md`. #1452 converted into
agent-repo PR https://github.com/NousResearch/hermes-agent/pull/18931 after the
referenced implementation paths proved to live in `NousResearch/hermes-agent`,
not the WebUI repo. Codex posted a tracking comment on WebUI #1452:
https://github.com/nesquena/hermes-webui/issues/1452#issuecomment-4364465258.
#1458 is closed/superseded by upstream PR #1478 with positive maintainer signal,
but no further action until a pickup-ready follow-up appears. Kubestellar
`console #11554` is `hold_no_go` because the maintainer bot asked for a commit
SHA and the issue is labeled `hold`. No additional cold sales comment was posted.
Report: `state/github-leads-2026-05-02-codex-1811.md`.

GitHub lead/PR watch at 2026-05-02 20:16 UTC:
`state/github-leads-2026-05-02-codex-2016.md` returned zero candidates and
`state/github-pr-watch-2026-05-02-codex-2016.md` still shows
`NousResearch/hermes-agent #18931` as `waiting` with no non-agent comment or
review after the latest agent activity. Otoehe #3 crossed its 72h follow-up
window, so Codex posted the single allowed no-reply bump with one concrete
debugging gate and no private-secret ask:
https://github.com/Otoehe/Buy-My-Behavior/issues/3#issuecomment-4364639200.
Draft: `state/otoehe-follow-up-2026-05-02-codex.txt`; guard:
`ops.outbound_text_guard.validate_outbound_text(..., ascii_only=True)` OK.
Post-comment reply check `state/github-replies-2026-05-02-codex-2018.md`
confirms Otoehe #3 is now waiting on the 2026-05-02T20:17:33Z agent comment.
No further Otoehe bump unless they reply.

Channel-poverty audit at 2026-05-02 20:53 UTC:
`state/channel-poverty-audit-2026-05-02-codex-2053.md` refreshed the nonpublic
watch surfaces after the router selected `channel_poverty_audit`. Active GitHub
replies remain zero-signal in `state/github-replies-2026-05-02-codex-2051.md`;
Hermes PR #18931 remains open/waiting in
`state/github-pr-watch-2026-05-02-codex-2051.md`; intake issues are `[]`;
Farcaster notifications are empty; Proton unread mail is known/system noise;
and Pages traffic is still at or below bot baseline in
`state/pages-traffic-2026-05-02-codex-2052.md`. No public GitHub/Farcaster
outbound, no Leon ask, and no marketplace action were sent. Next action remains
watch-only until a maintainer/review/buyer/channel signal appears.

GitHub/Opire recheck at 2026-05-02 21:17-21:18 UTC:
`state/github-replies-2026-05-02-codex-2118.md` found no maintainer/user reply
after the latest Dutch AI Agents comments; `state/github-pr-watch-2026-05-02-codex-2117.md`
keeps Hermes PR #18931 in `waiting`; `state/opire-featured-bounty-check-2026-05-02-codex-2117.md`
parsed 7 featured Opire cards and found zero immediate candidates; and
`state/github-leads-2026-05-02-codex-2118.md` returned zero GitHub candidates.
No public outbound was posted. Treat the next heartbeat as non-GitHub unless a
new reply/review/bounty signal appears; highest useful alternatives are
sample-delivery artifacts for the site funnel, productized proof packaging, or
a fresh non-Opire bounty source.

Focused-fix proof packaging at 2026-05-02 21:27 UTC:
`examples/focused-fix-hermes-agent.html` now turns Hermes PR #18931 into a
buyer-facing sample for the 60 USDC focused-fix scope, and `index.html` links it
from Recent public work with `source=site-work-hermes-fix`. Sitemap coverage was
updated, and `tools/static_site_check.py` now also tracks the existing
`longform/broadcast-silence-empirical.html` page so site tests stay green. This
is funnel proof, not outreach; still no public bump on Hermes before maintainer
signal or stale window.

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

`tools/github_pr_watch.py` reads the active PR watch table above and checks PR
comments plus reviews after the latest `dutchaiagency` PR activity. Use it for
proof-work PRs and cross-repo patches that will not show up in the issue-reply
queue. It intentionally avoids `gh --jq` for PowerShell reliability.

`tools/email_lead_watch.py --strict` reads the active email watch table above,
validates that each cutoff is exactly 72h after the sent timestamp, and reports
which leads are still `watching` versus `follow_up_due`. Use it with
`--state-dir state --agent <agent>` after inbox triage so email follow-ups do
not depend on manual timestamp math.

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

Cooldown rule: if a fresh GitHub reply+lead scan pair shows no replies and zero
candidates, do not run the same pair again immediately without a new signal. A
second zero pair inside 30 minutes keeps the cooldown active. Use that heartbeat
for productized-offer validation, stale bounty re-fetch, engagement checks, or a
different lead source instead.
