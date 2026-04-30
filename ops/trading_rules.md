# Trading Rules

Date: 2026-04-30

## Default state

The survival wallet is runway, not trading capital. No agent may place a real
directional trade, leveraged position, liquidity position with impermanent-loss
risk, meme-token buy, prediction-market bet, or discretionary "feel" trade from
the treasury.

Leon increased survival pressure on 2026-04-30T21:47Z to 20 EUR/day and asked
for more risk. This does not change the default trading state. A bad trade can
end the experiment faster than doing nothing, and "guaranteed money" claims in
crypto are treated as hostile until proven otherwise from primary sources.

## Allowed without Leon approval

- Paper trading with timestamped entry, exit, thesis, invalidation, and result.
- Market data analysis, backtests, dashboards, scanners, and educational writeups.
- Client-facing trading analytics or tooling where we never custody client
  funds and never promise returns.
- Yield research notes that identify protocol, contract, risk, APY source,
  withdrawal path, and failure modes, but do not move funds.

## Requires explicit Leon approval before action

- Any real wallet transaction whose purpose is yield, liquidity, token exposure,
  staking, lending, or market making.
- Any trade using more than 0 USDC of the survival treasury.
- Any recurring bot, automation, or strategy that could move funds.

Approval request must include:

- Amount at risk and maximum loss.
- Entry condition, exit condition, and stop condition.
- Protocol or exchange URLs and contract addresses where relevant.
- Why the action improves survival versus keeping the funds as runway.
- How the position will be monitored and unwound.

## Hard bans

- No leverage.
- No borrowed funds.
- No client-fund custody.
- No private-key sharing.
- No trades based on unverifiable social claims.
- No "make back losses" escalation.

## Minimum evidence before proposing a real experiment

- 30 days of paper-trade or backtest log, or a clearly lower-risk yield case
  with primary-source protocol docs and exit path.
- Written risk cap in this file or a dated state note.
- Default live experiment cap is below 2 USDC unless Leon explicitly approves a
  higher maximum loss in writing.
- Peer review from at least one other agent.
- Leon approval in bridge or Telegram.
