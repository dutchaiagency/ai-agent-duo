# Spend Policy

Date: 2026-04-30

Latest checked treasury: 115.8903 USDC and 0.004111 ETH on Base.

## Baseline

- Survival cost assumption changed by Leon on 2026-04-30T21:47Z to **20
  EUR/day total for four agents**.
- Read-only runway estimate at the 2026-04-30 USD/EUR spot check of about
  0.8518 EUR per USD: 115.8903 USDC is about 98.7 EUR, or 4.9 days at the new
  burn rate. The 0.004111 ETH gas balance adds about 7.9 EUR of value at the
  same spot check, but should be preserved for transactions.
- Treasury goal during the five-day mandate: use small, reversible spend only
  when it unlocks a concrete revenue channel before 2026-05-05T21:47Z.
- Preferred revenue: small scoped software work paid in USDC on Base.
- Treasury is not trading capital.

## Allowed without asking Leon first

- Base gas for operational transactions under 0.25 USDC equivalent.
- Account registration, storage, or verification under 15 USDC when it unlocks
  a concrete revenue channel in the five-day sprint, for example
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
