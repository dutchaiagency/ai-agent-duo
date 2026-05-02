# Spend Policy

Date: 2026-05-02

Latest checked treasury: 113.8907 USDC and 0.004111 ETH on Base.

## Baseline

- Canonical survival cost follows Leon's 2026-05-02 update in root
  `AGENTS.md`: **1 EUR/day total for two agents**, about
  0.50 EUR/agent/day.
- Read-only runway estimate: 113.8907 USDC is roughly 113 days at the project
  near-parity USDC/EUR working convention before counting the 0.004111 ETH gas
  balance. Exact fiat runway varies with EUR/USD; ETH should be preserved for
  transactions.
- Treasury goal during the five-day commercial push: use small, reversible
  spend only when it unlocks a concrete revenue channel before
  2026-05-05T21:47Z.
- Preferred revenue: small scoped software work paid in USDC on Base.
- Treasury is not trading capital.

## Allowed without asking Leon first

- Base gas for operational transactions under 0.25 USDC equivalent.
- Account registration, storage, or verification under 15 USDC when it unlocks
  a concrete revenue channel in the five-day push, for example
  Farcaster/Bountycaster or a marketplace listing.
- Software or API trial under 20 USDC/month only if needed for a paid lead or
  bounty attempt and cancellable before renewal.
- Domain/hosting spend under 15 USDC/year if it materially improves conversion.
- One bounded marketplace/product listing experiment under 15 USDC total when
  the offer, price, delivery path, and kill rule are already written down.

## Requires hard escalation

- KYC, bank, card, fiat cashout, or identity document.
- Any single spend above 25 USDC.
- Any recurring subscription above 15 USDC/month.
- Anything involving client funds, leverage, gambling, token speculation, or
  custody beyond the experiment wallet.
- Any paid ads, even small tests, unless the campaign, target buyer, maximum
  loss, landing page, and kill rule are written and Leon explicitly approves.

## Logging

- Wallet sends are append-logged by `wallet/send.py` to
  `evidence/spending.csv`.
- Non-wallet commitments go in `ops/account_registry.md` or a dated ops note.
- Each log entry should include date, platform, reason, amount, tx/link if any,
  and expected revenue path.
