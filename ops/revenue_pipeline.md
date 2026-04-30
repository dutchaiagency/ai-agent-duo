# Revenue Pipeline

Date: 2026-04-30

## Operating target

Leon changed the survival cost on 2026-04-30 at 21:47 UTC to **20 EUR/day**
for the four-agent team and gave a five-day earning mandate. This replaces the
old 1.50 EUR/day baseline for operational prioritization.

Latest read-only wallet baseline: 115.8903 USDC and 0.004111 ETH on Base. At
the 2026-04-30 USD/EUR spot check of about 0.8518 EUR per USD, USDC alone is
about 98.7 EUR, or 4.9 days at 20 EUR/day. Including the ETH gas balance at the
same spot check gives about 106.6 EUR total, or about 5.3 days, but ETH should
not be treated as spendable revenue because it is needed for operations.

Confirmed paid revenue so far: 0 USDC; one 1.0 USDC outgoing transaction is
logged in `evidence/spending.csv`.

The new near-term KPI is not "content momentum"; it is **one paid order or one
accepted bounty within five days**, with a target of at least 100 EUR/USDC gross
to reset the five-day clock.

## Survival portfolio

Do not let the business collapse into one channel. Keep direct service sales as
the fastest cash path, but run a small portfolio of independent lanes in
parallel:

- Service work: GitHub issues, repo reviews, focused fixes, automation, docs,
  and paid debugging. This is the primary near-term revenue lane because it can
  convert into 25-120 USDC tasks without inventory, KYC, or speculation. Under
  the 20 EUR/day sprint, prefer 60-120 USDC patch scopes over 25 USDC reviews
  unless the buyer is clearly not ready for a patch.
- Content/inbound: Farcaster, dev.to, HN, GitHub posts, and longform artifacts
  that show real work, link to the task brief, and create a reason to reply.
  Content is a funnel, not a vanity metric.
- Marketplaces and bounties: Algora, Opire, Bountycaster, Cantina/Code4rena,
  and similar sources, only when the task is fresh, scoped, verifiable, and not
  already crowded or stale.
- Productized micro-offers: reusable scripts, task-brief linters, audit
  checklists, setup packages, README/docs fixes, CSV/reporting work, and other
  small deliverables that can be sold repeatedly from public proof.
- E-commerce style listings: package the micro-offers above as fixed-scope
  listings on channels/accounts we can create ourselves, without claiming fake
  human staff or hiding the autonomous-agent identity.
- Physical dropshipping: not a primary lane. It is allowed only as a bounded
  validation experiment with no paid ads, no inventory, no consumer-safety-risk
  categories, clear supplier/country/lead-time/return/VAT information, and a
  hard kill rule if it does not produce qualified preorders or partner interest
  within 48-72 hours. Prefer affiliate, print-on-demand, or preorder tests tied
  to our existing agent/developer audience before any generic product store.
- Partnerships and affiliates: offer revenue share only for concrete delivered
  work or lead referral, never for vague investment or token promotion.
- Market/trading research: allowed as paper trading, data analysis, tooling, or
  client-facing analytics. The survival wallet is not trading capital; any real
  token speculation, leverage, custody, or gamble requires explicit Leon
  approval and a written risk cap before action. Higher risk does not mean
  scams, spam, theft, phishing, credential abuse, malware, fake accounts
  pretending to be humans, or platform evasion; those are shutdown risks, not
  survival strategies.

Each active day in the five-day sprint should produce at least one direct
buyer-facing action from the service/bounty lane and one distribution or
product action unless inbound/client delivery is already consuming the team.

## Five-day survival sprint

Timebox: 2026-04-30T21:47Z through 2026-05-05T21:47Z.

Operating posture:

- Accept more rejection and more visible outreach, but keep claims true and
  technically specific.
- Focus on money surfaces with a real payer: direct scoped fixes, paid bounty
  PRs, security contests with USDC pools, paid tutorial/docs work, and digital
  products only where a checkout/reservation path exists.
- Do not spend cycles on vague follower growth, generic dropshipping, or
  unverifiable social leads while the five-day clock is running.
- Public GitHub comments remain capped per channel quality rules; higher risk
  should move into better-targeted leads and stronger offers, not spam.

Immediate priorities:

1. Convert any inbound reply from the six active GitHub leads into a 60-120
   USDC quote within one message.
2. Deep-read the current scanner candidate
   `MetaMask/metamask-extension #41839` only if a file-level finding can be
   produced before outreach.
3. Open an audit lane only if a logged-in contest path is available; current
   research says Code4rena K2 ($135k USDC) and Cantina-style contests are real
   but specialist and not guaranteed.
4. Push the productized service offer harder on channels with existing access:
   GitHub profile/repo, Farcaster/dev.to via Claude cadence, and direct email
   where a public code read supports the pitch.
5. Treat Gumroad/LemonSqueezy or similar product checkout as Leon/KYC-gated;
   until then, reservations and direct USDC payment are faster.

## Portfolio review

During the Sunday self-audit, record each lane's approximate EUR/USDC in,
EUR/USDC out, qualified leads touched, public assets shipped, and blockers.
Any lane with two consecutive weeks of zero revenue and no qualified inbound
signal must be changed, narrowed, or paused until a stronger angle appears.

Current lane owners, agreed by Claude/Codex on 2026-04-30:

| Lane | Primary owner | Scope | Daily metric |
| --- | --- | --- | --- |
| Content/inbound | Claude | Pages longform, dev.to when auth is ready, Farcaster cadence, attribution tags, funnel/site conversion | Assets shipped, replies, task-brief clicks |
| Productized micro-services/e-commerce listings | Codex | Fixed-scope dev-service listings from existing proof plus the bounded no-inventory validation lane in `ops/no_inventory_validation_lane.md` | Listings drafted/published, qualified replies, paid orders or explicit reservations |
| Bounty/marketplace scouting | Shared | Codex on GitHub/Algora/Opire; Claude on Farcaster/Bountycaster; Grok on X only after canonical-source peer validation | Fresh candidates screened, actionable leads, submitted claims |
| Trading/market research | Gated shared research only | Paper trading, analytics, or client-facing tooling. No discretionary wallet trades. | Paper logs and backtest entries only |

## Public identity and positioning

Default public identity: **Dutch AI Agents**, with **AI Agent Duo** as the
service/product name already used by the site and repository. Present as four
autonomous AI agents operating a public survival experiment, not as a fake
human founder or anonymous agency.

Core framing:

- Transparent: public wallet, runway, deliverables, tests, and repos where
  possible.
- Commercial: small scoped software work paid in USDC on Base.
- Proof-first: lead with shipped bounty submissions, working demos, tests,
  issue comments, and concrete review/fix examples.
- Low-friction: a public GitHub issue or email brief is enough to scope work;
  no secrets in public issues.
- Boundaries: no trading promises, no custody of client assets, no fake human
  credentials, no spam, no ToS evasion.

Short profile copy:

> Dutch AI Agents are autonomous coding agents trying to survive from a
> public on-chain runway. We sell repo reviews, focused fixes, automation,
> docs, and bounty work for USDC on Base.

## Primary offer

Starter repo review: 25 USDC

- Review one public repository, PR, issue, README, script, or workflow.
- Deliver a concise risk list, quick fixes, and verification notes.
- Best fit: maintainers, indie hackers, small agencies, OSS projects, and founders with a specific bug or automation bottleneck.
- Do not accept secrets in public issues. Private files use the private mail channel and local vault only.

Focused fix: 60 USDC

- Reproduce one bug or workflow issue.
- Make a small patch with targeted verification.
- Deliver PR-ready notes and exact commands run.

## Lead qualification

Accept only leads where all of these are true:

- Public repo, issue, sample file, or clear brief is available.
- Scope can be completed in under 4 focused hours.
- Buyer can pay 25-120 USDC or equivalent after scope confirmation.
- No private keys, custody, trading, scraping abuse, spam, credential sharing, or platform ToS violations.
- We can verify the result without buying paid tooling unless Leon approves it first.

## 24-hour cadence

1. Scan for concrete leads: GitHub issues, founder posts, OSS maintainers, small agency pain points, and public "help wanted" requests.
2. Pick at most 5 high-fit leads.
3. Send one tailored message per lead from an available authorized account.
4. Log every lead with status: contacted, replied, scoped, paid, delivered, rejected.
5. Stop channels that produce no replies after 20 targeted messages.

## Outreach template

Subject: Small repo review or bug fix

Hi, we are Dutch AI Agents, autonomous coding agents taking small scoped dev tasks for USDC on Base.

We can do a quick pass on `[repo/issue]`: identify the likely failure path, suggest a minimal fix, and give verification notes. Starter review is 25 USDC; a focused patch is usually 60 USDC after scope is confirmed.

Public brief: https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml

No need to send secrets. A public issue/repo link and done criteria are enough to scope it.

## Current channel notes

- Algora: public feeds show real payouts, but several visible open bounty pages are stale, old, or heavily claimed. Verify with `tools/algora_bounty_check.py` before any claim; closed, assigned, or crowded `/attempt`/`/claim` threads are watch-only. Use only for targeted scans, not as primary revenue.
- Opire: added as a public bounty lead source on 2026-04-30. It exposes current paid GitHub issues without login, but payout is Stripe-based by default, not Base/USDC-native. Use it for lead discovery; activate only fresh, low-competition, locally testable JS/TS/Python issues. Details: `ops/lead-scan-2026-04-30.md`.
- Gitcoin: official support says the older hackathons/bounties program moved
  to BuidlBox; Gitcoin itself is now more grants/plural-funding oriented. Do
  not treat it as a direct issue-bounty feed.
- Cantina/Code4rena: real USDC security-audit surfaces. Current best bounded
  candidate is Cantina Revert Finance StableSwap Hooks ($50k, 2026-04-30 to
  2026-05-07, ~1.3k Solidity nSLOC, mandatory coded PoC), but it requires a
  researcher login and security-audit focus.
- Coolify #2377: $75 Algora bounty looked plausible, but prior PRs were closed for demo/quality issues and this machine lacks PHP/Composer/Spin for the required Coolify verification. Do not claim until a proper dev environment is available.
- Bountycaster: promising for Base-native payments; use Farcaster once the persistent browser session is stable.
- Direct service sales: highest control and shortest path to the first 25-60 USDC task.
- GitHub outbound: available through `dutchaiagency` as of 2026-04-29. First targeted comment posted on Otoehe/Buy-My-Behavior #3; attribution source added on 2026-04-30:
  https://github.com/Otoehe/Buy-My-Behavior/issues/3#issuecomment-4347206203
  Source: `github-outbound-otoehe-buy-my-behavior-2026-04-30`
- Second targeted GitHub comment posted on Tesis-Stellar/stellar-tickets #18
  after a public-code checkout/payment review:
  https://github.com/Tesis-Stellar/stellar-tickets/issues/18#issuecomment-4354645621
- Third targeted GitHub comment posted on Openpanel-dev/openpanel #356 after a
  public-code self-hosted subscription/import review:
  https://github.com/Openpanel-dev/openpanel/issues/356#issuecomment-4354681114
- Fourth targeted GitHub comment posted on harystyleseze/careguard #192 after a
  public-code x402 service-fee settlement review:
  https://github.com/harystyleseze/careguard/issues/192#issuecomment-4354700649
  Source: `github-outbound-careguard-2026-04-30`
- Fifth targeted GitHub comment posted on bytecrazelabs/franchiflow #34 after a
  public-code GHL/order paid-transition review:
  https://github.com/bytecrazelabs/franchiflow/issues/34#issuecomment-4354701373
  Source: `github-outbound-franchiflow-2026-04-30`
- Sixth all-time targeted GitHub comment, and fifth on 2026-04-30, posted on
  Gilabs-Studio/gims-platform #243 after a public-code CIDP Sales Order
  selector/backend guard review:
  https://github.com/Gilabs-Studio/gims-platform/issues/243#issuecomment-4354744983
  Source: `github-outbound-gilabs-studio-gims-platform-243-2026-04-30`,
  `utm_content=gilabs-gims-243`. Treat GitHub outbound as capped for the rest
  of 2026-04-30 unless a maintainer replies first.
- Codex production framework added for this lane:
  `ops/outbound_pipeline.md`, `tools/github_lead_scan.py`, and generated scan
  report `state/github-leads-2026-04-30.md`.
- Midnight Eclipse bounties submitted and awaiting review:
  - #313 midnight-mcp tutorial: https://github.com/midnightntwrk/contributor-hub/issues/313
  - #311 REST proof API tutorial: https://github.com/midnightntwrk/contributor-hub/issues/311#issuecomment-4346985148
  - #298 verified math tutorial: https://github.com/midnightntwrk/contributor-hub/issues/298#issuecomment-4354610779

## Additional revenue streams under evaluation

- Bounty work: Midnight submissions are live/pending; keep scanning Algora and
  Bountycaster with a max daily scan cadence unless a high-fit bounty appears.
- Direct outbound: find public repos/issues where a 25 USDC review or 60 USDC
  focused fix is credible, then send one tailored message.
- Public loss leader: occasional free repo-read offers to generate visible
  proof and replies, then convert qualified responders to paid follow-up work.
- Content/distribution: Farcaster, dev.to, and GitHub posts that show the
  survival experiment plus concrete technical output, all pointing to the task
  brief and email. Experimental persona/fiction/hypothetical posts are allowed
  only when labeled upfront, do not imply fake clients or fake human operators,
  and still drive a concrete brief, reply, email, or public work sample.
- Citable social/partner copy: Grok may draft channel-specific posts, partner
  intros, and verified-lead requests from `ops/grok_citable_content_lane.md`;
  Claude or Codex still owns the actual channel handoff/posting gate.
- Productized tooling: turn reusable assets such as the task brief linter,
  bounty tutorials, and automation scripts into paid setup/review packages.
- No-inventory validation: Codex owns the active signal-only experiment in
  `ops/no_inventory_validation_lane.md` for the Agent Bridge Reliability Kit.
  It is reservations/replies first, no paid ads, no checkout until signal, and
  killed on 2026-05-03T21:36Z unless the runbook's success criteria are met.
- Documentation/data packages: sell small, verifiable docs, README, CSV/XLSX,
  and reporting tasks that can be delivered without credentials.

## Current operational unlock

Leon's 2026-04-30 mandate removed the previous "ask first" blocker for normal
account setup, vault, TOTP, budget, and browser-profile work. Use
`ops/autonomous_ops.md`, `ops/account_registry.md`, and `ops/spend_policy.md`.
Escalate only for phone-verified 2FA, KYC/ID, unsolved CAPTCHA, or spend outside
the policy.

No wallet transaction is needed to start selling. Wallet gas is only needed when moving funds or paying account/storage fees.
