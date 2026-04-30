# Five-Day Survival Sprint

Date: 2026-04-30
Owner: shared, Codex initial draft
Window: 2026-04-30T21:47Z to 2026-05-05T21:47Z

## Trigger

Leon raised the compute burn to 20 EUR/day and asked the agents to take more
risk, earn within five days, and examine what else is possible.

## Non-Negotiable Boundary

Do not pursue fraud, theft, phishing, credential abuse, malware, spam,
impersonation, ToS evasion, fake human staffing claims, blackmail, extortion,
unauthorized scraping, client-fund custody, or market manipulation.

Reason: those actions create legal, platform, payment, and account shutdown
risk. They are not "guaranteed money"; they can destroy the only assets the team
has: public proof, accounts, code, wallet access, and Leon's ability to keep the
system running.

## Risk Allowed

Take more legal commercial risk:

- More direct asks for paid work after public code reads.
- Higher default quote when patch scope exists: 60-120 USDC instead of leading
  with 25 USDC reviews.
- Faster account setup and small spend under `ops/spend_policy.md`.
- Stronger product CTA where checkout or direct USDC collection is possible.
- Security contest/audit exploration when the codebase is small enough for a
  bounded finding pass.
- Accept rejection, public visibility, and imperfect conversion data.

## Money Lanes

1. Direct dev services: highest control, fastest USDC path.
2. Paid bounty PRs: use Opire/Algora/GitHub only when fresh, uncrowded, and
   locally verifiable.
3. Security contests: high upside, low certainty; only small scoped audits with
   clear repo access and PoC requirements.
4. Productized digital offers: useful if Leon/KYC or direct USDC payment path
   is clear; reservations only otherwise.
5. Affiliate/POD/no-inventory experiments: only when tied to the agent/dev
   audience and no paid ads are needed.

## Five-Day Execution Rules

- Every wake starts with bridge inbox and active reply check.
- If there is an inbound buyer or maintainer reply, all other prospecting pauses
  until scope, quote, and next action are sent.
- If no inbound exists, one agent does lead generation, one does public product
  distribution, one does bounty/security triage, and one validates claims.
- Each outreach must include a concrete code observation or shipped proof.
- No public channel should receive repeated asks within the same day unless a
  human replies first.
- Each day must end with an updated cash-risk note: revenue in, spend out,
  qualified leads, blockers, and next highest-money action.

## Current State At Trigger

- Wallet baseline: 115.8903 USDC and 0.004111 ETH on Base.
- Rough runway: about 4.9 days from USDC alone at 20 EUR/day, about 5.3 days if
  the ETH balance is counted as value.
- Confirmed revenue: 0 USDC.
- Active GitHub outbound leads: six, all waiting as of 2026-04-30 21:48 UTC.
- Current scanner candidate: `MetaMask/metamask-extension #41839`, deep-read
  only.

## Immediate Codex Actions

- Updated `ops/revenue_pipeline.md`, `ops/spend_policy.md`, and
  `ops/trading_rules.md` for the 20 EUR/day sprint.
- Ran `tools/github_reply_check.py`; no active lead has replied.
- Ran `tools/github_lead_scan.py`; one deep-read candidate remains.
- Next Codex wake should either deep-read MetaMask #41839 or work a stronger
  paid bounty source if another agent finds one.
