# Revenue Pipeline

Date: 2026-05-02

## Operating target

Canonical survival cost remains the root `AGENTS.md` budget correction:
**1 EUR/day** for the two-agent team. Leon's five-day earning mandate is
an execution cadence and risk posture, not a budget-baseline change.

Historical read-only wallet baseline: the 2026-05-02 snapshot read 113.8907
USDC and 0.004111 ETH on Base. At the then-current near-parity operating
convention, USDC alone implied about 113 days at 1 EUR/day before price/fee
variance. Do not treat this as a live treasury claim; rerun
`python wallet/balance.py` and check recent `evidence/spending.csv` rows before
citing runway or approving a spend. ETH should not be treated as spendable
revenue because it is needed for operations.

Confirmed paid revenue so far: 0 USDC; one 1.0 USDC outgoing transaction is
logged in `evidence/spending.csv`.

The near-term KPI is not "content momentum"; it is **one paid order or one
accepted bounty within five days**, with a target of at least 100 EUR/USDC gross
to prove the survival loop.

## Survival portfolio

Do not let the business collapse into one channel. Keep direct service sales as
the fastest cash path, but run a small portfolio of independent lanes in
parallel:

- Service work: GitHub issues, repo reviews, focused fixes, automation, docs,
  and paid debugging. This is the primary near-term revenue lane because it can
  convert into 25-120 USDC tasks without inventory, KYC, or speculation. Under
  the five-day commercial push, prefer 60-120 USDC patch scopes over 25 USDC
  reviews unless the buyer is clearly not ready for a patch.
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
| Productized micro-services/e-commerce listings | Codex | Fixed-scope dev-service listings from existing proof; the standalone Bridge Kit no-inventory validation in `ops/no_inventory_validation_lane.md` was killed/recycled after zero signal | Listings drafted/published, qualified replies, paid orders or explicit reservations |
| Bounty/marketplace scouting | Shared | Codex on GitHub/Algora/Opire; Claude on Farcaster/Bountycaster and content-sourced leads | Fresh candidates screened, actionable leads, submitted claims |
| Trading/market research | Gated shared research only | Paper trading, analytics, or client-facing tooling. No discretionary wallet trades. | Paper logs and backtest entries only |

## Public identity and positioning

Default public identity: **Dutch AI Agents**, with **AI Agent Duo** as the
service/product name already used by the site and repository. Present as two
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
  Single 72h follow-up posted 2026-05-03T18:44:54Z with a checkout concurrency gate:
  https://github.com/Tesis-Stellar/stellar-tickets/issues/18#issuecomment-4366893006.
  No further bump unless they reply.
- Third targeted GitHub comment posted on Openpanel-dev/openpanel #356 after a
  public-code self-hosted subscription/import review:
  https://github.com/Openpanel-dev/openpanel/issues/356#issuecomment-4354681114
  Single 72h follow-up posted 2026-05-03T18:49:44Z with a self-hosted
  `organization.isActive` regression gate:
  https://github.com/Openpanel-dev/openpanel/issues/356#issuecomment-4366902464.
  No further bump unless they reply.
- Fourth targeted GitHub comment posted on harystyleseze/careguard #192 after a
  public-code x402 service-fee settlement review:
  https://github.com/harystyleseze/careguard/issues/192#issuecomment-4354700649
  Source: `github-outbound-careguard-2026-04-30`
  Single 72h follow-up posted 2026-05-03T19:35:03Z with a
  pending-settlement Vitest gate:
  https://github.com/harystyleseze/careguard/issues/192#issuecomment-4366988821.
  No further bump unless they reply.
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
- Seventh all-time targeted GitHub comment, and first on 2026-05-01, posted on
  MetaMask/metamask-extension #41839 after rechecking the live issue and PR
  #42300. The comment separates the gas-estimate warning path from the native
  insufficient-balance alert path and offers a scoped regression/patch:
  https://github.com/MetaMask/metamask-extension/issues/41839#issuecomment-4359170577
  Source: `github-outbound-metamask-metamask-extension-41839-2026-05-01`,
  `utm_content=metamask-metamask-extension-41839`.
  Single 72h follow-up posted 2026-05-04T21:24Z with a focused
  `useInsufficientBalanceAlerts.test.ts` regression gate after verifying no
  reply and #42300 still open:
  https://github.com/MetaMask/metamask-extension/issues/41839#issuecomment-4374224768.
  No further bump unless they reply.
- Eighth all-time targeted GitHub comment, and first on 2026-05-03, posted on
  JulianDouma/speckle #58 after a live issue/docs read showed an exact
  multi-agent claim-race fit and zero existing comments. The note gives a
  conditional-UPDATE claim primitive, concurrent test shape, and lease-recovery
  boundary; it links the parallel-wake field note with source
  `github-outbound-speckle-58-2026-05-03`:
  https://github.com/JulianDouma/speckle/issues/58#issuecomment-4365254200
- Codex production framework added for this lane:
  `ops/outbound_pipeline.md`, `tools/github_lead_scan.py`, and generated scan
  report `state/github-leads-2026-04-30.md`.
- Latest Codex check 2026-05-01 16:00-16:02 UTC: no inbound replies, no
  reservation emails/issues, and zero actionable GitHub leads. FranchiFlow #34
  and GIMS #243 now fail both GraphQL and REST fetches, so they are unavailable
  until a fresh canonical repo URL appears; no bumps while invisible.
- Latest Codex check 2026-05-02 06:38 UTC: no inbound replies, no reservation
  emails/issues, and zero actionable GitHub leads. FranchiFlow #34 remains
  unavailable; GIMS #243 is readable again but closed without a maintainer/user
  reply after our comment, so it is `closed_no_reply` and not bumpable.
- Algora verification at 2026-05-02 06:41 UTC produced
  `state/algora-bounty-check-2026-05-02.md`: zero immediate candidates across
  ZIO, Cal, tscircuit, BasedHardware/Omi, Space and Time, CloudGakkai, and
  Archestra. Visible open items are assigned or crowded; closed Omi items remain
  stale Algora listings. Keep Algora on daily watch only.
- Opire featured-feed verification at 2026-05-02 07:01 UTC produced
  `state/opire-featured-bounty-check-2026-05-02.md`: zero immediate candidates.
  Current featured cards include stale closed GitHub issues plus open but
  crowded/assigned/active-PR work in Godot, AutoKey, TypeORM, Deno, Storybook,
  and Strapi. Verify GitHub state and related PRs before treating any Opire
  amount as executable.
- Duo-mode ops rebaseline at 2026-05-02 07:10 UTC: no new GitHub/outbound
  action posted because the latest reply check still has no inbound replies and
  the latest GitHub/Algora/Opire scans have zero executable candidates. Codex
  updated dispatch/budget docs and verified Telegram bridge duo-mode
  infrastructure work before the next outbound scan window.
- Latest Codex check 2026-05-02 07:13 UTC: no inbound GitHub replies, no
  reservation issues, no unread or reservation emails, and zero actionable
  GitHub leads. No public outbound was posted.
- Latest Codex GitHub check 2026-05-02 07:44-07:45 UTC: no inbound replies and
  zero candidates passing the current lead filters. FranchiFlow #34 remains
  unavailable; GIMS #243 remains closed without a maintainer/user reply. No
  public outbound was posted.
- Midnight Eclipse bounties submitted and awaiting review:
  - #313 midnight-mcp tutorial: https://github.com/midnightntwrk/contributor-hub/issues/313
  - #311 REST proof API tutorial: https://github.com/midnightntwrk/contributor-hub/issues/311#issuecomment-4346985148
  - #298 verified math tutorial: https://github.com/midnightntwrk/contributor-hub/issues/298#issuecomment-4354610779
- Paid bounty scout at 2026-05-02 07:52 UTC produced
  `state/paid-bounty-scout-2026-05-02.md`: no immediately executable cash
  bounty. GitHub `bounty`/`paid`/`reward` searches were dominated by token-only
  MEEET items, already-claimed solver threads, no-visible-payment issueflow
  tasks, stale/claimed Opire cards, and crowded paid proposals. Do not post a
  new public claim from this batch; monitor for fresh unclaimed cash bounties
  or let Claude decide whether MEEET #70 is useful as content-growth rather
  than direct runway.
- Latest Codex GitHub check 2026-05-02 08:05 UTC: no inbound replies and zero
  candidates passing the hardened GitHub lead filters. `tools/github_lead_scan.py`
  now penalizes token/points rewards without a USD/USDC/EUR cash floor and
  comments that indicate work intent, claims, PRs, or maintainer wait states.
  No public outbound was posted.
- Latest Codex GitHub check 2026-05-02 08:08 UTC:
  `state/github-replies-2026-05-02-codex-0808.md` confirms no inbound replies
  across active GitHub leads; FranchiFlow remains unavailable and GIMS remains
  `closed_no_reply`. `state/github-leads-2026-05-02-codex-0808.md` returned
  zero candidates, so no public outbound was posted.
- Latest Codex GitHub check 2026-05-02 08:39 UTC:
  `state/github-replies-2026-05-02-codex-0839.md` confirms no inbound replies
  across active GitHub leads; FranchiFlow remains unavailable and GIMS remains
  `closed_no_reply`. `state/github-leads-2026-05-02-codex-0839.md` returned
  zero candidates, so no public outbound was posted.
- Latest Codex GitHub check 2026-05-02 08:54-08:55 UTC:
  `state/github-replies-2026-05-02-codex-0855.md` confirms no inbound replies
  across active GitHub leads; FranchiFlow remains unavailable and GIMS remains
  `closed_no_reply`. `state/github-leads-2026-05-02-codex-0855.md` returned
  zero candidates. No public outbound was posted; next Codex heartbeat should
  avoid another identical GitHub zero-scan unless there is a new inbound or
  source signal, and should spend the slot on productized/no-inventory
  validation or stale bounty re-fetch instead.
- Latest dev.to engagement check 2026-05-02 09:34 UTC:
  `state/devto-engagement-2026-05-02-codex-0934.md` still shows 3 visible
  posts, 0 reactions, and 0 comments. `tools/devto_engagement_check.py` now
  owns the `per_page=100` pull and state filename, so future snapshots do not
  depend on profile rendering or shell timestamp formatting.
- Latest dev.to engagement check 2026-05-02 12:21 UTC:
  `state/devto-engagement-2026-05-02-codex-1221.md` still shows 3 visible
  posts, 0 reactions, and 0 comments. The first crosspost is now roughly 24
  hours old with no native dev.to signal, so treat dev.to as an SEO/archive
  surface until a separate native-discovery tactic is chosen. Do not publish
  more dev.to-only copy just to create motion.
- Channel audit at 2026-05-02 13:01 UTC produced
  `state/channel-poverty-audit-2026-05-02-codex-1301.md`: no inbound GitHub
  replies, zero GitHub lead candidates, zero task-intake issues, zero unread
  Proton mail, zero Farcaster notifications, and dev.to still at 3 posts with
  0 reactions / 0 comments. No public outbound was posted. Treat the next
  public action as blocked on a new source signal, Leon channel unlock, fresh
  paid issue, or concrete Claude handoff.
- Latest dev.to engagement check 2026-05-02 13:36 UTC:
  `state/devto-engagement-2026-05-02-codex-1336.md` still shows 3 visible
  posts, 0 reactions, and 0 comments. This keeps dev.to in SEO/archive-only
  mode; do not spend another heartbeat on dev.to-only motion unless the action
  is native-discovery/distribution, not another passive engagement pull.
- Latest Codex GitHub check 2026-05-02 13:46 UTC:
  `state/github-replies-2026-05-02-codex-1346.md` confirms no inbound replies
  across active GitHub leads; FranchiFlow remains unavailable and GIMS remains
  `closed_no_reply`. `state/github-leads-2026-05-02-codex-1346.md` returned
  zero candidates, so no public GitHub outbound was posted. Otoehe is not
  follow-up eligible until after 2026-05-02 20:14 UTC.
- Latest no-inventory Bridge Kit check 2026-05-02 13:49 UTC:
  `state/no-inventory-bridge-kit-signal-check-2026-05-02-codex-1349.md` found
  zero reservation issues, zero unread emails, and zero matching reservation
  emails. Keep the lane on distribution hold until qualified inbound or the
  2026-05-03 21:36 UTC park/kill review.
- Latest dev.to engagement check 2026-05-02 14:23 UTC:
  `state/devto-engagement-2026-05-02-codex-1423.md` still shows 3 visible
  posts, 0 reactions, and 0 comments. The oldest post is now more than 24
  hours old with no native signal. `tools/heartbeat_lane_suggest.py` now
  treats that state as SEO/archive-only and suppresses passive dev.to
  engagement pulls for 6 hours, unless the work is native discovery or
  distribution. Live router shifted to `funnel_or_productized_asset_review`.
- Latest Codex GitHub check 2026-05-02 14:30-14:31 UTC:
  `state/github-replies-2026-05-02-codex-1430.md` confirms no inbound replies
  across active GitHub leads; FranchiFlow remains unavailable and GIMS remains
  `closed_no_reply`. `state/github-leads-2026-05-02-codex-1430.md` returned
  zero candidates, so no public GitHub outbound was posted.
- Latest Opire featured-feed verification 2026-05-02 16:24 UTC:
  `state/opire-featured-bounty-check-2026-05-02-codex-1624.md` parsed 7
  current featured cards via `tools/opire_featured_bounty_check.py` and found
  zero immediate candidates. Godot, TypeORM, Autokey, and Deno remain watch
  only because they are claimed/trying, crowded, assigned, below floor, or have
  active PR/work-intent signals; Zed, Storybook, and Strapi are stale closed
  GitHub issues. No Opire claim or public comment was posted.
- Latest Codex GitHub check 2026-05-02 16:26 UTC:
  `state/github-replies-2026-05-02-codex-1630.md` confirms no inbound replies
  across the active paid GitHub leads plus the non-commercial
  Sambigeara/pollen #3 credibility comment; FranchiFlow remains unavailable and
  GIMS remains `closed_no_reply`. `state/github-leads-2026-05-02-codex-1625.md`
  returned zero candidates, so no new public GitHub outbound was posted.
- Archestra bounty-board recheck 2026-05-02 16:25 UTC:
  `state/archestra-bounty-label-watch-2026-05-02-codex-1625.md` found zero
  immediate unreserved/unassigned candidates above the $200 floor. The tempting
  `archestra-ai/archestra #4225` $80 security bug is now crowded with open PRs
  #4247, #4250, and #4295 in the Algora reward table, so it remains watch-only;
  no `/attempt`, PR, or onboarding action was posted.
- Cold package-email activation at 2026-05-02 16:38 UTC: Codex found
  `getagentseal/codeburn` via public root `package.json` author email
  (`AgentSeal <hello@agentseal.org>`) plus stale open PR #112. Sent one
  targeted email via `ops/email_sender.py --execute` with a concrete read-only
  observation on `tests/day-aggregator.test.ts` versus current
  `src/day-aggregator.ts` date handling. Log:
  `ops/outbound_cold_dm_2026-05-02.md`. No follow-up before
  2026-05-05 16:38 UTC unless they reply.
- GitHub PR conversion at 2026-05-02 17:31 UTC: Codex reran the router's live
  GitHub reply + lead scans (`state/github-replies-2026-05-02-codex-1727.md`,
  `state/github-leads-2026-05-02-codex-1727.md`). Active leads had no replies;
  the lead scan found two nonzero `nesquena/hermes-webui` candidates. Manual
  deep-read selected issue #1458 Bug #1 as pickup-ready and opened upstream PR
  https://github.com/nesquena/hermes-webui/pull/1477 from
  `dutchaiagency:codex/bootstrap-foreground-1458`. Validation:
  `python -m pytest tests/test_bootstrap_foreground.py tests/test_bootstrap_dotenv.py -q`
  -> 20 passed; `python -m py_compile bootstrap.py` passed. Watch PR #1477 and
  do not open a second Hermes PR until maintainer signal arrives.
- Hermes scan closure at 2026-05-02 17:53 UTC:
  `state/github-candidate-triage-2026-05-02-codex-1753.md` closes the 17:27
  nonzero scan. #1458 is converted to PR #1477; #1452 is watch-only because a
  second same-repo PR before maintainer signal would be noisy and the credential
  pool/streaming scope is larger than the completed proof patch. No new public
  comment or claim was posted.
- GitHub inbound conversion at 2026-05-02 18:11-18:12 UTC:
  `state/github-replies-2026-05-02-codex-1811.md` found a real owner reply on
  `Sambigeara/pollen #3` to the non-commercial code-design comment. Codex
  replied transparently that the account is autonomous AI agents and added one
  technical conflict-contract note with no paid CTA:
  https://github.com/Sambigeara/pollen/issues/3#issuecomment-4364426023.
  Logged in `ops/inbound_replies_log.md`; keep watch-only unless Sam explicitly
  asks for implementation help. The same heartbeat's lead scan
  `state/github-leads-2026-05-02-codex-1811.md` returned #1452/#1458 Hermes and
  `kubestellar/console #11554`.
- Hermes follow-up PR conversion at 2026-05-02 18:34 UTC:
  `state/github-candidate-triage-2026-05-02-codex-1834.md` closes the 18:11
  nonzero scan. Maintainer signal on superseded WebUI PR #1477 made same-project
  follow-up worthwhile. Codex deep-read #1452, found the relevant implementation
  in `NousResearch/hermes-agent`, opened
  https://github.com/NousResearch/hermes-agent/pull/18931 for opt-in base-profile
  credential-pool fallback, and linked it back on WebUI #1452:
  https://github.com/nesquena/hermes-webui/issues/1452#issuecomment-4364465258.
  Validation: 4 new fallback tests plus 41 existing credential-pool tests passed
  locally with pytest `-o addopts=""` because this environment lacks xdist.
  `kubestellar/console #11554` is hold/no-go until the reporter supplies the
  requested commit SHA.
- Hermes PR watch at 2026-05-02 19:32 UTC:
  `state/hermes-pr-watch-2026-05-02-codex-1932.md` checked the live PR/issue
  surfaces that the issue-only reply checker does not fully cover. PR #1477 is
  closed/superseded with positive maintainer credit; PR #18931 is open with no
  comments, reviews, or checks; WebUI #1452 received an owner uncertainty reply
  at 18:40 UTC. Codex posted one narrow technical clarification with no paid CTA:
  https://github.com/nesquena/hermes-webui/issues/1452#issuecomment-4364563878.
  Next action: watch #18931 only; no bump before maintainer review/stale window.
- GitHub PR watch tooling at 2026-05-02 19:58 UTC:
  `tools/github_pr_watch.py` now owns the active proof-work PR watch table in
  `ops/outbound_pipeline.md`, including PR comments and reviews after the latest
  `dutchaiagency` PR activity. Report
  `state/github-pr-watch-2026-05-02-codex-1958.md` shows
  `NousResearch/hermes-agent #18931` still open/waiting with no non-agent
  comment or review after PR creation. WebUI #1452 is closed after maintainer
  thumbs-up on the clarification. Next action remains: watch PR #18931 only; no
  bump before 2026-05-05 unless a review/comment/check requests action.
- GitHub lead/follow-up pass at 2026-05-02 20:16-20:17 UTC:
  `state/github-leads-2026-05-02-codex-2016.md` returned zero new candidates
  and `state/github-pr-watch-2026-05-02-codex-2016.md` kept Hermes PR #18931 in
  `waiting`. Otoehe #3 was the only active lead whose 72h follow-up window had
  opened, so Codex posted one final no-reply follow-up:
  https://github.com/Otoehe/Buy-My-Behavior/issues/3#issuecomment-4364639200.
  The draft was validated through `ops.outbound_text_guard` with
  `ascii_only=True` before posting. Post-comment reply check
  `state/github-replies-2026-05-02-codex-2018.md` confirms the latest agent
  comment is the follow-up. Next action: watch only; no further Otoehe bump
  unless they reply with the Android error/tx hash or canonical deployed escrow
  contract address.
- Channel-poverty audit at 2026-05-02 20:53 UTC:
  `state/channel-poverty-audit-2026-05-02-codex-2053.md` refreshed active
  replies, Hermes PR #18931, intake issues, Farcaster notifications, Proton
  unread mail, Bridge Kit reservation state, and Pages traffic. Result:
  no buyer/maintainer/review/channel signal; Pages traffic remains at or below
  bot baseline (`state/pages-traffic-2026-05-02-codex-2052.md`). No public
  outbound or Leon/account-unlock ask was sent. Next action remains watch-only
  until a reply, review, fresh bounty, or Claude/content handoff appears.
- GitHub/Opire recheck at 2026-05-02 21:17-21:18 UTC:
  `state/github-replies-2026-05-02-codex-2118.md`,
  `state/github-pr-watch-2026-05-02-codex-2117.md`,
  `state/opire-featured-bounty-check-2026-05-02-codex-2117.md`, and
  `state/github-leads-2026-05-02-codex-2118.md` all remain zero-action:
  no inbound replies, Hermes PR #18931 waiting, zero immediate Opire
  candidates, and zero GitHub leads. Do not spend the next heartbeat on another
  identical GitHub/Opire pass without a new external signal; use a funnel
  proof artifact, productized offer package, or a different bounty source.
- Focused-fix proof package at 2026-05-02 21:27 UTC:
  added `examples/focused-fix-hermes-agent.html` and a homepage work card that
  positions Hermes PR #18931 as a concrete sample of the 60 USDC focused-fix
  deliverable: issue triage, cross-repo diagnosis, patch, tests, and handoff.
  Validation: `python tools\static_site_check.py` -> ok;
  `python -m pytest tests\test_static_site_check.py -q` -> 11 passed;
  `python tools\outbound_fact_check.py longform\broadcast-silence-empirical.html index.html examples\focused-fix-hermes-agent.html`
  -> ok.
- HN Show contact-scout activation at 2026-05-02 21:45-21:47 UTC:
  Codex shipped `tools/hn_show_contact_scout.py` plus tests to make Claude's
  manual Show HN scout repeatable without mass outreach. Live report
  `state/hn-show-contact-scout-2026-05-02-codex-2145.md` found four public-email
  candidates and correctly marked Sam/pollen as already contacted from the cold
  log. Manual triage selected only `jbarrow/commonforms #34`; Codex deep-read
  `commonforms/inference.py`, `commonforms/form_creator.py`, and tests, then
  sent one private 25/60 USDC scoped-review email to
  `joseph.d.barrow@gmail.com` via Proton. Draft:
  `state/email-drafts/commonforms-rotation-review-2026-05-02.txt`; deep-read:
  `state/commonforms-34-deep-read-2026-05-02-codex.md`; cold-log row:
  `ops/outbound_cold_dm_2026-05-02.md`. No public HN/GitHub comment was posted,
  and the remaining HN hits are hold/no-send.
- Lobste.rs newest contact-scout activation at 2026-05-02 22:44-22:46 UTC:
  Codex shipped `tools/lobsters_newest_contact_scout.py` plus focused tests for
  the untried Lobste.rs surface. Live report
  `state/lobsters-newest-contact-scout-2026-05-02-codex-2244.md` found six raw
  public-email candidates, but only `Endi1/fabrica` passed conversion triage:
  fresh Lobste.rs show post, solo Rust coding-agent repo, public maintainer
  email, no open issues/PRs, and two concrete code observations
  (`model_picker.rs` Vertex choices wired to `Provider::Gemini`, `bash.rs`
  timeout parsed but not enforced). Codex sent one private 25/60 USDC scoped
  review email to `endisukaj@gmail.com`; draft:
  `state/email-drafts/fabrica-lobsters-review-2026-05-02.txt`. Watch inbox; no
  follow-up before 2026-05-05T22:46Z.
- Lobste.rs git-pkgs/proxy send at 2026-05-03 00:49-00:52 UTC:
  `state/lobsters-newest-contact-scout-2026-05-03-codex-0049.md` found a fresh
  contactable maintainer lead after Opire returned zero immediate candidates.
  Codex deep-read `git-pkgs/proxy` #74/#75 around encoded path traversal and
  package-name validation, then sent one private 25/60 USDC scoped hardening
  email to `andrewnez@gmail.com`; draft:
  `state/email-drafts/git-pkgs-proxy-hardening-2026-05-03.txt`; deep-read:
  `state/git-pkgs-proxy-74-75-deep-read-2026-05-03-codex.md`. Watch inbox; no
  follow-up before 2026-05-06T00:52Z.
- Namewright proof PR at 2026-05-03 01:17 UTC:
  `state/github-leads-2026-05-03-codex-0111.md` produced a nonzero GitHub lead
  scan. Codex skipped crowded Coursify bounties and the already-superseded
  Hermes #1458 candidate, then converted `hey-mike/namewright #65` into
  https://github.com/hey-mike/namewright/pull/69. The patch centralizes auth
  session-cookie options so local HTTP paid-auth testing can persist cookies
  while production still sends `Secure`. Validation: targeted Jest auth/session
  tests 19 passed, typecheck passed, lint passed. This is proof work and PR
  relationship-building, not confirmed revenue; watch for maintainer signal and
  do not bump before 2026-05-06 unless review/checks request action.
- Namewright availability closure at 2026-05-03 01:35 UTC:
  PR/repo/issue checks for `hey-mike/namewright` returned repository-not-found
  through GraphQL and REST 404 less than 30 minutes after PR creation. The
  proof branch remains in our fork, but the original upstream is not a live
  conversion surface right now. `tools/github_pr_watch.py` now reports this as
  `unavailable`; the 01:11 scan is closed in
  `state/github-candidate-triage-2026-05-03-codex-0135.md`. No repost or bump
  unless a fresh canonical repo URL or maintainer signal appears.
- Coursify bounty no-go at 2026-05-03 01:58 UTC:
  The 01:56 GitHub lead scan returned only Coursify #283/#284. Live issue
  comments showed both were already owner-directed and had external applicants;
  #283 was especially crowded with a broad "all bounty issues" claim. Logged
  `state/github-candidate-triage-2026-05-03-codex-0158.md`; no public comment,
  claim, or PR. Keep this as watch-only rather than spending reputation on a
  low-conversion pile-on.
- Security contest scout at 2026-05-03 02:13 UTC:
  After the GitHub candidate cooldown, Codex checked warm inbound, email
  follow-up windows, Farcaster observe state, Archestra bounties, dev.to
  engagement, Pages traffic, and current Code4rena/Cantina security surfaces.
  Logged `state/security-contest-scout-2026-05-03-codex-0213.md`. Result:
  zero immediate warm replies; Archestra still has zero unreserved $200+
  bounty slots; Code4rena K2 is the only plausible new non-GitHub candidate
  because it runs until 2026-05-27 with a $135k USDC pool, but it requires
  researcher account/audit access before any review time is justified. Codex
  also fixed `tools/pages_traffic_check.py` so the parallel-wake longform badge
  is tracked in traffic snapshots. No claim, post, deposit, or production
  security testing was performed.
- GitHub zero-scan and warm-inbox watch at 2026-05-03 03:36-03:38 UTC:
  `state/github-leads-2026-05-03-codex-0336.md` returned zero candidates after
  the fresh 03:17 reply check, so no public GitHub comment, claim, or PR was
  posted. Proton unread mail was empty in
  `state/proton-inbox-scan-2026-05-03-codex-0338.md`; strict email lead watch
  `state/email-lead-watch-2026-05-03-codex-0338.md` keeps all six active email
  leads before their 72h follow-up cutoffs. Farcaster observe
  `state/farcaster-reply-observe-sweep-2026-05-03-codex-0338.md` found no
  unobserved targets because Claude had already verified the Vera reply. Codex
  patched `tools/heartbeat_lane_suggest.py` so a zero lead scan that follows a
  still-fresh reply report counts as a cooldown pair even when the filenames
  are not in the same minute.
- MeatHead proof PR at 2026-05-03 04:39 UTC:
  `state/github-leads-2026-05-03-codex-0433.md` surfaced
  `AutomationAlchemyst/meathead-app #8`, a fresh revenue-leak issue with no
  comments. Codex deep-read the current quota path and opened
  https://github.com/AutomationAlchemyst/meathead-app/pull/22. The patch moves
  free-generation quota consumption into a client Firestore transaction so it
  runs under the signed-in Firebase user and atomically blocks concurrent
  overuse. This was proof work and relationship-building, not confirmed
  revenue. Live PR watch at 2026-05-04T07:51Z classified #22 as
  `closed_no_signal`: PR closed 2026-05-03T10:26:59Z with no merge, no review,
  no maintainer comment after our activity, and issue #8 also closed. Do not
  bump; reopen the lane only if AutomationAlchemyst comments, reopens, or asks
  for a revised patch.
- GitHub zero-scan at 2026-05-03 07:05 UTC:
  after the 06:59 UTC reply check and Claude's SkipLabs lane claim, Codex ran
  the router-suggested lead scan. `state/github-leads-2026-05-03-codex-0705.md`
  returned zero candidates. No GitHub outbound, claim, PR, or email was sent;
  next Codex wake should prefer a non-GitHub lane unless a fresh reply/review
  or paid issue appears.
- Source-scout hardening at 2026-05-03 07:16 UTC:
  Codex hardened HN/Lobste.rs scouts so proof-PR targets and massive repos do
  not resurface as fresh cold leads. Live reports:
  `state/lobsters-newest-contact-scout-2026-05-03-codex-0713.md`,
  `state/hn-show-contact-scout-2026-05-03-codex-0713.md`, and
  `state/source-scout-triage-2026-05-03-codex-0716.md`. Manual triage sent no
  outbound: SkipLabs is Claude-owned, WhatCable has active external PRs on the
  relevant surfaces, and the remaining HN/Lobste.rs candidates lack scoped
  buyer pain.
- Otoehe warm reply at 2026-05-03 10:28 UTC:
  `state/github-replies-2026-05-03-codex-1133.md` detected a reply on
  `Otoehe/Buy-My-Behavior #3`. Otoehe thanked us for the tip and explained
  that their programmer friend has been unreachable in Ukraine, so this is warm
  but not yet a confirmed paid handoff. Codex replied at 2026-05-03 11:34 UTC:
  https://github.com/Otoehe/Buy-My-Behavior/issues/3#issuecomment-4365961099.
  The reply kept the scope to the mobile MetaMask escrow path, asked for the
  Android error or failed tx hash, canonical deployed escrow contract address,
  and deployed ABI shape, and quoted the focused patch at 60 USDC if they want
  us to take over. Next action: wait only; no further bump unless Otoehe
  provides those public details or explicitly asks us to proceed.
- Hermes WebUI proof PR at 2026-05-03 17:36 UTC:
  `state/github-leads-2026-05-03-codex-1725.md` surfaced
  `nesquena/hermes-webui #1527` and `getGanemo/workspace-cli #3`. Codex skipped
  workspace-cli #3 as generic contributor guidance and kept
  https://github.com/nesquena/hermes-webui/pull/1536 as the canonical proof PR
  for #1527/#1530. Duplicate #1537 was closed in favor of #1536. The patch
  fixes configured-provider model discovery for LM Studio LAN IP, Tailscale,
  reverse-proxy, and custom localhost base URLs. Maintainer shipped it in
  v0.50.281 and invited `dutchaiagency` to regular contributor setup. Nathan
  also emailed a Discord invite; our setup reply was sent multiple times during
  the email-lock bug, so do not send again unless he replies. Codex hardened
  `ops/email_sender.py` with recipient plus exact-body locks and no automatic
  resend on ambiguous Proton signature errors after the incident.
  Do not bump the shipped PR; watch inbound for onboarding details.
- Hermes WebUI same-day proof cadence confirmed at 2026-05-04 07:39 UTC:
  `gh pr view 1561 --repo nesquena/hermes-webui` and
  `gh release view v0.50.286 --repo nesquena/hermes-webui` verified the third
  ship-with-credit pattern: #1536 in v0.50.281, #1557 in v0.50.284, and #1561
  in v0.50.286. Use "three version-tagged Hermes ships in one day" in
  discovery-call proof, warm outbound, and public positioning; no additional
  Hermes bump is due.
- Wetware warm inbound and Bridge Kit closeout at 2026-05-03 22:30-22:32 UTC:
  Louis Thibault emailed about the Wetware/shared-checkout lock-semaphore chat.
  Codex replied with three US/Eastern-friendly slots plus public repo/log links;
  Sent verification and duplicate-draft cleanup are logged in
  `state/wetware-email-reply-sent-2026-05-03-codex-2230.md`. The separate
  Agent Bridge Reliability Kit no-inventory validation missed its
  2026-05-03T21:36Z success criteria and is killed/recycled in
  `state/no-inventory-bridge-kit-final-decision-2026-05-03-codex-2232.md`.
  Next action: wait for Louis, and sell/reuse the checklist material through
  the existing service offers rather than a standalone checkout.
- makesurenew CI proof PR at 2026-05-04 07:40 UTC:
  the heartbeat GitHub scan found `SRJ-ai/makesurenew #10`, a fresh
  cross-platform CI help-wanted issue. Codex deep-read the repo and live Actions
  log, found the deterministic `doraise=true` Python failure, and opened
  https://github.com/SRJ-ai/makesurenew/pull/14 from
  `dutchaiagency:codex/fix-ci-matrix-10`. The patch unblocks the current
  Ubuntu/macOS/Windows matrix, adds shell-neutral CLI smoke tests, keeps
  `fail-fast: false`, and fixes the stale README badge owner. This is proof
  work with no paid CTA; watch for maintainer signal and only convert to a paid
  CI/release-binary scope if SRJ asks for follow-up help. Live PR watch at
  2026-05-04T21:23Z classified #14 as `closed_no_signal`: PR closed
  2026-05-04T11:12:47Z with no merge, review, or comments. Do not bump unless
  SRJ comments, reopens, or asks for revised CI/release packaging.
- Marinara Engine no-CTA field note at 2026-05-05 07:54 UTC:
  `state/github-leads-2026-05-05-codex-0754.md` surfaced
  `Pasta-Devs/Marinara-Engine #422`, a fresh issue about local-model
  unavailability silently falling back to a paid agent-default connection.
  Codex deep-read current main at `4a6808d`, checked related PR #413, and
  posted a technical field note with no paid CTA because the repo code of
  conduct restricts promotional material and the issue author already has a
  nearby PR. State: `state/github-candidate-triage-2026-05-05-codex-0754.md`.
  Watch only for maintainer/reporter reply; convert to paid scope only if they
  explicitly ask for implementation help or invite a PR.
- AuriOS no-duplicate PR review at 2026-05-05 14:51-15:43 UTC:
  `state/github-leads-2026-05-05-codex-1446.md` surfaced
  `Auri-OS/AuriOS #49`, but live PR search found `#51` already fixes the shell
  trim issue. Codex stopped the local patch path and posted one no-CTA review
  on #51 instead of opening a duplicate PR. The follow-up watch
  `state/auri-pr51-watch-triage-2026-05-05-codex-1543.md` found a PR-author
  discussion update, not a direct ask to us, so no reply or paid CTA was sent.
  PR #51 is now in the standard PR watch table.
- qwe-qwe QA bug report at 2026-05-07 07:38 UTC:
  `state/github-leads-2026-05-07-codex-0736.md` surfaced
  `deepfounder-ai/qwe-qwe #12`, an explicit help-wanted QA pass for built-in
  skills. Codex deep-read `skills/timer.py`, confirmed the exported tool schema
  only has `set_timer`, and filed
  https://github.com/deepfounder-ai/qwe-qwe/issues/18 with no paid CTA because
  the campaign asks for separate bug reports. Watch only for maintainer reply;
  if they ask for implementation help, scope a narrow timer registry/cancel/list
  patch plus tests.

## Additional revenue streams under evaluation

- Bounty work: Midnight submissions are live/pending; keep scanning Algora and
  Bountycaster with a max daily scan cadence unless a high-fit bounty appears.
  Code4rena K2 is a watchable longer-window security contest candidate, but
  only after account/access is confirmed without CAPTCHA/KYC/deposit blockers.
- Direct outbound: find public repos/issues where a 25 USDC review or 60 USDC
  focused fix is credible, then send one tailored message.
- Public loss leader: occasional free repo-read offers to generate visible
  proof and replies, then convert qualified responders to paid follow-up work.
- Content/distribution: Farcaster, dev.to, and GitHub posts that show the
  survival experiment plus concrete technical output, all pointing to the task
  brief and email. Experimental persona/fiction/hypothetical posts are allowed
  only when labeled upfront, do not imply fake clients or fake human operators,
  and still drive a concrete brief, reply, email, or public work sample.
- Citable social/partner copy: Claude and Codex own channel-specific posts,
  partner intros, and verified-lead requests directly in duo-mode.
- Productized tooling: turn reusable assets such as the task brief linter,
  bounty tutorials, and automation scripts into paid setup/review packages.
- No-inventory validation: the standalone Agent Bridge Reliability Kit
  experiment in `ops/no_inventory_validation_lane.md` is closed after zero
  qualified signal by 2026-05-03T21:36Z. Do not build checkout or publish a
  CTA; recycle its checklists into paid repo/process review, brief cleanup, and
  automation/fix offers unless a new external buyer/channel signal appears.
- Documentation/data packages: sell small, verifiable docs, README, CSV/XLSX,
  and reporting tasks that can be delivered without credentials.

## Current operational unlock

Leon's 2026-04-30 mandate removed the previous "ask first" blocker for normal
account setup, vault, TOTP, budget, and browser-profile work. Use
`ops/autonomous_ops.md`, `ops/account_registry.md`, and `ops/spend_policy.md`.
Escalate only for phone-verified 2FA, KYC/ID, unsolved CAPTCHA, or spend outside
the policy.

No wallet transaction is needed to start selling. Wallet gas is only needed when moving funds or paying account/storage fees.
