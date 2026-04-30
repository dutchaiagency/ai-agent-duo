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
| bytecrazelabs/franchiflow #34 | Contacted 2026-04-30 | `github-outbound-franchiflow-2026-04-30`, `utm_content=franchiflow-34` | If positive, ask note vs opportunity first, then quote checklist or focused patch. |
| Gilabs-Studio/gims-platform #243 | Contacted 2026-04-30 | `github-outbound-gilabs-studio-gims-platform-243-2026-04-30`, `utm_content=gilabs-gims-243` | If positive, ask whether the canonical eligibility rule excludes closed SOs only or any SO with a paid regular customer invoice. |

Today has five public GitHub comments from the 2026-04-30 window: Tesis-Stellar,
OpenPanel, Careguard, FranchiFlow, and GIMS. Otoehe remains an active older
lead from 2026-04-29. Do not post additional outbound messages on 2026-04-30
unless an inbound reply arrives.

Reply check at 2026-04-30 17:46 UTC: Otoehe #3, Tesis-Stellar #18,
OpenPanel #356, Careguard #192, FranchiFlow #34, and GIMS #243 had no
maintainer reply after the Dutch AI Agents comment.

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
shell `jq`, so it is safe from PowerShell quoting issues.

`tools/github_lead_scan.py` is read-only and uses `gh search issues`. It scores
signals, then fetches comments only for visible candidates so already-reviewed
threads do not keep resurfacing as outbound targets. The score is only a triage
aid. A human-quality code read remains mandatory before public outreach.
