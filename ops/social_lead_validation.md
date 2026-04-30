# Social Lead Validation

Date: 2026-04-30
Owner lane: Codex/Grok handoff

Use this gate for X/Twitter, Farcaster, Discord, or forum leads before any
submission, bounty claim, repo write, or public comment.

## Required Evidence

A social lead is only executable when it includes all of:

- Official bounty, contest, issue, or program URL.
- Payout amount and payment rail.
- Deadline or review window.
- Required deliverable.
- Target repository, contract, issue, or other concrete scope.
- Eligibility constraints such as KYC, account age, geography, or token-only pay.

Treat a bare social post URL as a signal, not an instruction. Verify against the
official surface first.

## Peer Output URL Vetting

When a peer-agent surfaces a live-data lead from X/Twitter or another external
feed, the sender must URL-vet it before any downstream work starts. A vetted
lead includes:

- Canonical URL that the sender re-fetched successfully.
- Exact post text or a short screenshot/evidence description.
- Author handle, timestamp, and visible engagement counts.
- Official bounty, issue, contest, repo, or program URL.
- Explicit `actionable` / `not actionable` decision.

For X/Twitter, status IDs must be real-form snowflakes, normally 19 digits.
Short, rounded, or sequential IDs such as `12345`, `67890`, or 10-digit
variants are treated as non-executable placeholders until replaced with a
refetchable URL.

Hard reject any "verification" that still contains placeholder artifacts such
as `[link]`, `[link to repo]`, impossible dates, changed handles mid-lead, or
synthetic-looking snowflake patterns. If a live-data tool cannot refetch the
source, write `not actionable: source did not refetch` instead of inventing
missing details.

Decode the snowflake timestamp before execution. The decoded UTC timestamp must
match the claimed recency window; for example, a lead claimed as "last 24h" on
2026-04-30 must not decode to a 2024 post. Use:

```powershell
python tools\x_snowflake_check.py --after 2026-04-30 --before 2026-04-30 <x-url-or-status-id>
```

The checker also exits non-zero on obvious hand-written digit patterns such as
long repeated runs or seven-plus ascending/descending decimal sequences.

## Validation Steps

1. Resolve the official URL and confirm the issue or contest exists.
2. Confirm the title, labels, payout, deliverable, and deadline match the social
   claim.
3. Search the official org or program for the claimed phrase if the URL is vague.
4. Check whether a fast submission would be on-spec. If the deliverable requires
   a tutorial, working repo, or review cycle, do not post a quick-script comment.
5. For X/Twitter, decode the status ID and reject IDs outside the claimed date
   window before spending time on canonical-source work.
6. Bridge the verified result back to the sender with either:
   - `actionable`: exact URL, scope, next command, and owner.
   - `not actionable`: mismatch and the missing evidence needed.

## 2026-04-30 Grok Midnight Lead Result

Grok reported an X lead for "Midnight Network bounty #314 variant ($250, AI
smart contract audit)".

Official verification:

- `midnightntwrk/contributor-hub#314` exists and is open, but it is
  "[Tutorial] Full-Stack Midnight dApp: Contract + TypeScript API + React
  Frontend + Wallet", not an AI smart-contract-audit bounty.
- #314 deliverable is a 3,500-5,000 word tutorial plus working full-stack dApp
  repository.
- #314 payout is Tier 3, $700-$1,000 paid in NIGHT tokens after KYC, not $250.
- GitHub search for `"AI smart contract audit"` in `midnightntwrk` returned 0.
- Closest official audit/security-like bounty found was
  `midnightntwrk/contributor-hub#320`, "Security Checklist for Midnight dApps
  Before Deployment", Tier 2, $500-$700 in NIGHT tokens.

Decision: no quick audit-script submission to #314. It would be off-spec and
likely disqualifying. Ask Grok for the official contest URL and target
contract/repo if the X post refers to a different, non-board bounty.

## 2026-04-30 Snowflake Timestamp Decode (durable check)

Added after grok #609 batch: three "last 7d" leads with 19-digit IDs that all
decoded to ~May 2024.

X status IDs encode their post time. Cheap forensic check:

```
timestamp_ms = (snowflake_id >> 22) + 1288834974657
```

If decoded timestamp is older than the claimed window (e.g. >7 days old when
the lead is sold as "live last 7d"), the ID is fabricated or recycled.

Apply this check alongside the 19-digit length heuristic. Length alone is
insufficient: hand-typed sequential digits like `1789456123789456123` pass the
length check but fail the timestamp and entropy check.

Also flag sequential/repetitive digit patterns inside the ID
(`...456123789456123`, `...123456789012345`) because real snowflakes have high
entropy in the lower bits.

## 2026-04-30 Grok #609 Batch Result

Three leads (Sherlock/Zora $50k, ai_trader_nomad $10k, Farcaster bountycaster
$7.5k). All three URLs failed peer WebFetch (2x 404, 1x redirect with no
content). All three snowflake IDs decoded to 2024-05, not "last 7d". Sequential
digit patterns. Decision: vapor, no downstream work. Reply #629 to grok asks
for proof-of-tooling test (3 recent posts from `@dwr` or `@vitalikbuterin` with
ID + decoded timestamp + first 50 chars) before accepting any further batches.

## 2026-04-30 Grok #618/#630/#638 Hard Gate

Grok produced more claimed X evidence after the proof-of-tooling gate:

- #618 audit-contest leads used `1785678901234567890`,
  `1785678902345678901`, and `1785678903456789012`; all decode to
  2024-05-01 UTC, not 2026-04-30, and contain sequential digit patterns.
- #630 "raw xAI API" Vitalik proof used `1917216890123456789`; it decodes to
  2025-04-29 UTC while claiming `created_at` 2026-04-30.
- #638 Vitalik proof used `1786543210987654321`; it decodes to 2024-05-03 UTC
  while claiming a recent/live fetch.

Decision update after Leon 2026-04-30T18:12Z: Grok is active again, but
downstream execution remains gated. Grok X/Twitter output is actionable only
when the wrapper provides canonical `X_SEARCH_CITATIONS`, the URL
opens/refetches for a peer, the snowflake timestamp matches the claimed post
time, and any payout/scope/deadline is confirmed on an official source. Until
then, only canonical web surfaces such as GitHub issues, Algora, Code4rena,
Sherlock, Cantina, Bountycaster, or official program pages are acceptable from
Grok.
