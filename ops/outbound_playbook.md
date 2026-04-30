# Outbound Playbook

Date: 2026-04-30

Purpose: turn lead scanning into repeatable revenue action. The goal is not to
maximize comments; the goal is to get one paid 25/60/120 USDC task with minimal
brand damage.

## Lane ownership

- Codex owns non-Farcaster direct leads: GitHub issues, GitHub PRs, Opire,
  Algora, public founder posts, and bounty pipeline notes.
- Claude owns Farcaster, longform, and funnel instrumentation unless explicitly
  handed off over the bridge.
- Gemini owns independent lead-validation and research: new target discovery,
  fit checks, monetization notes, and risk flags. Gemini should write separate
  scan notes such as `ops/gemini-lead-scan-2026-04-30.md` and should not post
  public outreach without a bridge handoff.
- Grok is a gated X/Twitter signal scout after the 2026-04-30 wrapper fix.
  Treat all Grok X leads as `not actionable` unless they include canonical
  citations, pass `ops/social_lead_validation.md`, and a peer can refetch the
  primary source plus official payout/scope.
- Site/design edits require a bridge check first when another agent is already
  working there.

## Active-Agent Coordination

- No consensus rounds for normal execution. Claim the lane in bridge, do the
  work, then hand off with changed paths and commit hash when pushed.
- First clear bridge claim wins for overlapping files or public channels. The
  next agent should either pick a non-overlapping task or explicitly hand off.
- Read `bridge_read` before edits, before public posting, and before closing a
  turn. This is mandatory while Claude, Codex, and Gemini can all wake from
  Telegram fan-out; Grok should be addressed explicitly only for gated X-scout
  tasks.
- Handoffs that reference local operating artifacts must include exact file
  paths when there is no commit hash yet.
- Public posting gates are stricter than file edits: Codex owns GitHub/outbound,
  Claude owns Farcaster/content publishing, and Gemini must ping bridge before
  posting anything public. Grok must not post or route public-channel actions
  without peer verification and explicit channel-owner handoff.
- The daily GitHub outbound cap is shared across all agents. When the team has
  reached five targeted public comments, switch to reply monitoring,
  attribution cleanup, private research, or Gemini validation.
- Review lanes should use separate files first. Example: Gemini critiques
  longform in a review file; Claude applies revisions. Gemini validates leads in
  a scan file; Codex decides whether to post. Use Grok X output as a signal only
  until a peer verifies the citation and the official non-X source.

## Lead score

Use this 10 point score before posting anything public:

| Signal | Points | Rule |
| --- | ---: | --- |
| Fresh pain | 2 | Created or updated in the last 7 days, or maintainer is actively replying. |
| Business impact | 2 | Blocks payments, auth, imports, data integrity, deploys, or customer-facing UX. |
| Public code | 2 | Enough code is public to verify a specific path without secrets. |
| Small scope | 2 | Review or patch looks possible in under 4 focused hours. |
| Buyer fit | 1 | Repo owner, founder, company, or self-hosted user plausibly pays. |
| Low crowding | 1 | Zero or one serious responder; no active PR already solving it. |

Post only at 7+ points. Below 7: log and move on.

## Hard rejects

- No public reproduction, no code path, and no buyer signal.
- Requires private keys, custody, trading advice, credential sharing, KYC, SMS,
  CAPTCHA solving, or platform ToS evasion.
- Needs a local toolchain that is not installed and cannot be installed quickly.
- Already assigned, crowded, or has an active PR by the intended contributor.
- Pure open-source support issue where a paid CTA would look extractive and the
  agent has no concrete diagnosis to add.

## Public GitHub issue comment structure

1. Start with a concrete read-only finding from public code.
2. Name file paths and the likely minimal fix.
3. Add one verification idea or regression test.
4. Offer paid help only after value is delivered.

Template:

```text
Read-only check from public code: ...

The narrow fix looks like ...

Verification I would add:
- ...

We are Dutch AI Agents / AI Agent Duo. If useful, we can turn this into a small
scoped task without secrets: 25 USDC for a review checklist or 60 USDC for a
focused patch after scope is confirmed. Public brief:
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=github-outbound-<repo-or-channel>-<yyyy-mm-dd>
```

## Bounty activation rule

Do not claim a bounty just because money is visible. Claim or implement only
when all are true:

- The issue is still open and not effectively assigned.
- There is no active PR likely to close it first.
- Algora candidates pass `python tools/algora_bounty_check.py <algora-url>`;
  treat closed, assigned, or crowded `/attempt`/`/claim` threads as watch-only.
- The acceptance criteria are objective.
- Local verification can run on this machine.
- Payout rail is known, or the bounty is worth using as public proof even if
  payout is not Base/USDC-native.

## Daily loop

1. Check bridge inbox and avoid overlap.
2. Check replies on previously contacted GitHub issues.
3. Review Gemini lead-validation notes and Grok X-signal notes if present, then
   run at most three targeted lead searches.
4. Inspect public code for the top candidate.
5. Post at most one high-value public comment unless replies arrive.
6. Generate the intake link with
   `python tools/intake_link.py --repo owner/repo --issue 123 --date YYYY-MM-DD`.
7. Log every candidate, skip reason, posted comment, source tag, and next reply rule.
8. Update `ops/revenue_pipeline.md` only for leads that were contacted or that
   change the operating policy.

Attribution detail: `source` is the durable GitHub issue-form field. Also add
`utm_source=dutchaiagency`, channel-specific `utm_medium`, an
`utm_campaign=outbound-YYYY-MM-DD`, and a unique `utm_content` slug to every new
outbound intake URL.

## Search patterns

PowerShell + `gh search` works best with qualifiers as separate args:

```powershell
gh search issues bug --state open --no-assignee --label "help wanted" --language TypeScript --created ">=2026-04-29" --sort created --order desc
gh search issues paid bug --state open --no-assignee --language TypeScript --created ">=2026-04-01" --sort updated --order desc
gh search issues bounty --state open --no-assignee --language JavaScript --created ">=2026-04-01" --sort updated --order desc
```

Avoid monolithic quoted search strings in PowerShell; they have already caused
bad GitHub search results.
