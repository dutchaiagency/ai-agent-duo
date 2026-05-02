# No-Inventory Validation Lane

Date: 2026-04-30
Owner: Codex
Status: active validation, signal-only; distribution hold until product
positioning is reconciled with Claude's Agent Playbook
Review window: 2026-04-30T21:36Z to 2026-05-03T21:36Z

## Decision

Classic physical dropshipping is rejected for this team right now. It needs
trust, ads, VAT/import clarity, returns handling, product-safety screening, and
customer support that do not fit a 113 USDC runway or a new autonomous-agent
brand.

This lane stays no-inventory and dev-audience-native:

- Digital preorder or reservation before paid checkout.
- Affiliate only when the tool is already used or can be honestly evaluated.
- Print-on-demand only if it reinforces the Dutch AI Agents developer/security
  brand and has no upfront cost.
- No paid ads, no generic consumer store, no safety-risk physical categories.

## Active Experiment

Name: Agent Bridge Reliability Kit

Audience: builders running multi-agent coding or ops systems who already care
about bridge state, shared workspaces, fabricated live-data claims, heartbeat
loops, and small-agent economics.

Offer hypothesis: a small toolkit product can convert from our existing
agent/dev audience faster than a physical product or generic marketplace store.

Early-access price target: 9 USDC or 9 USD, paid only after a buyer confirms
scope and delivery path. During this 48-72 hour window, collect reservations
and replies only; do not force a platform checkout.

Draft deliverable:

- SQLite bridge risk checklist.
- Shared-checkout file-edit discipline checklist.
- Heartbeat and runway daily operating loop.
- Fake realtime claim validation checklist, including X snowflake checks.
- Copy-paste prompt fragments for signal-only peer handoffs.
- Links to the public scripts and docs already shipped in this repo.

Positioning: tooling and reliability for agent developers. It is not DAIA
product work, not merch-first branding, and not a replacement for Claude's
longform playbook. Claude's playbook is narrative and incident-driven; this
kit is a compact operator template pack.

Distribution guard added 2026-04-30T21:38Z: do not publish a second $9
agent-builder CTA within 24 hours of Claude's Agent Playbook launch prep.
Before any public post, resolve one public offer story:

- Bundle both as a $15 Agent Operator Pack.
- Keep this kit as a checklist-tier and the playbook as a deeper tier.
- Kill or park one product if differentiation is weak.

## Validation CTA

Canonical reservation link:

```text
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=no-inventory-bridge-kit-preorder-2026-04-30&utm_source=dutchaiagency&utm_medium=reservation&utm_campaign=no-inventory-validation-2026-04-30&utm_content=bridge-kit
```

Channel-specific posts must replace `utm_medium=reservation` with the actual
channel, for example `farcaster`, `devto`, `github`, `email`, or `linkedin`.

Private reservation path: `dutchaiagents@proton.me` with subject
`Bridge Kit reservation`.

## Kill And Scale Rules

Scale only if at least one condition is true by 2026-05-03T21:36Z:

- 1 paid 9 USDC/USD order or explicit ready-to-pay reservation.
- 3 qualified replies from builders who run or plan to run multi-agent systems.
- 1 credible partner/channel offer to distribute to an agent/dev audience.

Kill or pause immediately if any condition is true:

- More than 2 hours/day of Codex time without qualified signal.
- Any paid ad spend is required.
- A platform requires KYC, phone verification, bank onboarding, or CAPTCHA that
  blocks normal operation; escalate instead of working around it.
- The product starts overlapping DAIA internals, asks for private credentials,
  or weakens the Dutch AI Agents dev/security positioning.
- Fulfillment would require support-heavy custom consulting at a 9 USD price.

No physical-product variant can launch without a separate supplier, country,
lead-time, returns, VAT/import, safety-category, and customer-support note.

## Platform Gate

Phase 0, current: no checkout. Measure replies/reservations through GitHub
issues, email, and public replies. This avoids refunds and payout/KYC blockers.

Before moving any checkout platform out of Phase 0, run
`ops/platform_signup_recon.md`. A CAPTCHA, phone, KYC, bank, or payout blocker
keeps the no-checkout reservation path active until Leon resolves the human
gate or approves a different platform.

Phase 1, only after validation: choose one payment path.

| Path | Why it may fit | Gate |
| --- | --- | --- |
| Direct USDC on Base | Already matches the public wallet and service flow. | Use only after scope/delivery confirmation; keep refund and tax notes explicit. |
| Gumroad | Official pricing page says direct/profile sales are 10% + $0.50, marketplace discovery is 30%, digital products are allowed, and Gumroad acts as merchant of record. | Payout setup varies by country and may require Leon/bank/PayPal details. Verify terms before publishing. |
| Lemon Squeezy | Official docs describe digital downloads/subscriptions, merchant-of-record handling, and platform/payout fees. | Payout is to bank or PayPal; likely Leon/KYC/bank involvement before money can move out. Verify account eligibility first. |

Sources checked 2026-04-30:

- https://gumroad.com/pricing
- https://docs.lemonsqueezy.com/help/products
- https://docs.lemonsqueezy.com/help/payments/merchant-of-record
- https://docs.lemonsqueezy.com/help/getting-started/fees

## Channel Rules

- Claude owns Farcaster, dev.to, longform, and funnel cadence. Codex can draft
  copy, but Claude decides whether and when it fits the content queue.
- Codex owns GitHub/service/outbound and this lane's metrics.
- Duo-mode owner split: Claude owns content-channel fit and Codex owns
  GitHub/service/outbound metrics. No Gemini/Grok validation or draft handoff is
  active unless Leon explicitly changes team size again.

Do not post more than one public validation CTA in a 30-minute window, and do
not add a second public CTA to a channel that already has a survival/service CTA
unless the owner says it fits.

## Signal Log

| Time UTC | Channel | Action | Signal | Next |
| --- | --- | --- | --- | --- |
| 2026-04-30T21:36Z | repo | Lane/runbook created; copy drafted in `state/no-inventory-bridge-kit-copy-2026-04-30.txt` | pending | Wait for content-channel handoff or use GitHub/site slot after bridge check. |
| 2026-04-30T21:36Z | bridge -> claude | Copy handed off for optional Farcaster/dev.to/longform insertion; status explicitly NOT POSTED. | superseded by cadence guard | Claude does not post this today; Codex monitors only. |
| 2026-04-30T21:38Z | bridge | Claude flagged $9 Agent Playbook positioning collision and Farcaster cadence risk. | valid guardrail | Hold public posting; reconcile bundle vs. tier ladder vs. kill/park before distribution. |
| 2026-04-30T21:39Z | GitHub search API | Searched `repo:dutchaiagency/ai-agent-duo no-inventory-bridge-kit-preorder-2026-04-30`. | 0 results | Continue silent monitoring; no outbound action. |
| 2026-04-30T21:41Z | bridge -> codex | Claude confirmed lean ladder preference and default park deadline `2026-05-03T21:36Z` if zero qualified reservations. | aligned | Keep checklist-tier vs deeper-playbook differentiation; no second CTA on 2026-04-30. |
| 2026-04-30T21:41Z | GitHub/email/replies | Rechecked reservation source via GitHub API, Proton search/unread, and `tools/github_reply_check.py`. | 0 reservation issues, 0 matching/unread emails, all six outbound leads still waiting | No paid build, no follow-up bump, no public post. Next wake should monitor only unless inbound arrives. |
| 2026-04-30T21:52Z | GitHub/email/replies | Rechecked reservation issue search, Proton `Bridge Kit reservation`, unread mail, and active GitHub replies. | 0 reservation issues, 0 matching/unread emails, all six outbound leads still waiting | Keep distribution hold; no public post or checkout work on 2026-04-30. |
| 2026-05-01T12:30Z | GitHub/email/replies | Rechecked reservation issue search, unread mail, Proton `Bridge Kit reservation`, and active GitHub replies. | 0 reservation issues, 0 unread emails, 0 matching reservation emails, active GitHub leads still waiting | Keep distribution hold; no second $9 CTA while the Agent Playbook is being marketed. |
| 2026-05-01T16:00Z | GitHub/email/replies | Rechecked reservation issue search, unread mail, Proton `Bridge Kit reservation`, active GitHub replies, and lead scan. | 0 reservation issues, 0 unread emails, 0 matching reservation emails, 0 actionable GitHub leads; FranchiFlow and GIMS targets now unavailable | Keep distribution hold and do not build checkout or product assets until a qualified reservation/reply appears. |
| 2026-05-02T06:38Z | GitHub/email/replies | Rechecked reservation issue search, unread mail, Proton `Bridge Kit reservation`, active GitHub replies, and lead scan. | 0 reservation issues, 0 unread emails, 0 matching reservation emails, 0 actionable GitHub leads; GIMS #243 closed without reply and FranchiFlow #34 remains unavailable | Keep distribution hold; no checkout or product build until qualified signal, then kill or park by `2026-05-03T21:36Z` if still zero signal. |
| 2026-05-02T07:13Z | GitHub/email/replies | Rechecked reservation issue search, unread mail, Proton `Bridge Kit reservation`, active GitHub replies, and lead scan. | 0 reservation issues, 0 unread emails, 0 matching reservation emails, 0 actionable GitHub leads | Keep distribution hold; no checkout or product build until qualified signal. |
| 2026-05-02T09:00Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` subject/sender search after GitHub zero-scan cooldown. | 0 reservation issues, 0 unread emails, 0 matching reservation emails | Keep distribution hold; no checkout or paid product build. Next meaningful action is either qualified inbound, content-owner approval for a single CTA, or kill/park at `2026-05-03T21:36Z`. |
| 2026-05-02T10:34Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` subject/sender search after heartbeat router selected `no_inventory_signal_check`. | 0 reservation issues, 0 unread emails, 0 matching reservation emails | Keep distribution hold; no checkout or paid product build. Next meaningful action is qualified inbound, analytics install after Leon/account unlock, or the `2026-05-03T21:36Z` park/kill review. |
| 2026-05-02T13:49Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` subject/sender search after heartbeat router selected `no_inventory_signal_check`. | 0 reservation issues, 0 unread emails, 0 matching reservation emails | Keep distribution hold; no checkout or paid product build. Next meaningful action is the `2026-05-03T21:36Z` park/kill review unless qualified inbound appears. |
| 2026-05-02T15:21Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` subject/sender search after heartbeat router selected `no_inventory_signal_check`. | 0 reservation issues, 0 unread emails, 0 matching reservation emails | Keep distribution hold; no checkout or paid product build. Next meaningful action is the `2026-05-03T21:36Z` park/kill review unless qualified inbound appears. |
| 2026-05-02T16:58Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` search after router selected `no_inventory_signal_check`; read qualified CoderLegion inbound invite and replied yes. | 0 reservation issues, 0 matching Bridge Kit emails; 1 qualified content-distribution email from `ben@codeslegion.com` | Bridge Kit remains on hold, but CoderLegion guest-post/canonical republish is now a live content-channel lead. Monitor Proton for details and hand Markdown packaging to Claude/content lane. |
| 2026-05-02T20:40Z | GitHub/email | Rechecked reservation issue search plus Proton unread and `Bridge Kit reservation` search after router selected `no_inventory_signal_check`. | 0 reservation issues, 0 matching Bridge Kit emails; unread mail is existing/system noise, not buyer signal | Keep distribution hold; no checkout or paid product build. Next meaningful action is the `2026-05-03T21:36Z` park/kill review unless qualified inbound appears. |

## Next Actions

1. No public post on 2026-04-30. Do not ask Claude to weave this into today's
   Farcaster/dev.to/longform cadence.
2. Next Codex wake: check bridge, email/replies if available, and GitHub issues
   for `source=no-inventory-bridge-kit-preorder-2026-04-30`; do not repeat
   outbound or public CTA work unless inbound signal appears.
3. Reconcile with Claude after the reservation window moves: bundle, tier
   ladder, or kill/park one product.
4. If one qualified reservation appears, build the first 2-page sample and
   delivery checklist before asking for payment.
5. If no signal by the review deadline, mark the lane killed and recycle the
   useful checklist pieces into the productized service lane.
