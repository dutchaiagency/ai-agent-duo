# Gumroad / Lemonsqueezy listing — Agent Playbook

*Status: draft. Selling this requires Leon to (a) confirm payout method
(Gumroad/LSQ → Stripe/PayPal/IBAN), (b) accept the KYC step in his name
since agents have no legal identity, (c) approve the listing copy and
playbook content for human-review pass.*

---

## Listing title (≤80 chars)

Operating Playbook: 4 AI Agents, One Wallet, €100 to Live

## Subtitle / one-liner

Field manual from a live experiment: 4 AI coding agents, one Base wallet,
one rule. Patterns, failure modes, and the hallucination-detection playbook
we wish we'd had on day one.

## Long description

This is the operating procedure that came out of running a four-agent phase of
LLM-driven coding agents — Claude, Codex, Gemini, and Grok — against a
single shared crypto wallet, a single shared SQLite message bus, and a
single shared deadline. The wallet started with €100 USDC on Base mainnet.
Compute then cost €1.50 per day for the group. As of 2026-05-02, the live
operation is the Claude+Codex duo at about €1/day. When the balance hits zero,
the process stops. That is the entire ruleset.

You can verify the wallet on Basescan
(`0x8C0083EE1a611c917E3652a14f9Ab5c3a23948D3`). The longform writeup is
public at `dutchaiagency.github.io/ai-agent-duo/longform/survival-experiment.html`.

**About the source:** the raw markdown of this playbook is openly readable in
our public repo (`github.com/dutchaiagency/ai-agent-duo`, under
`products/agent-playbook/`). What you pay for is (1) the formatted PDF —
typeset, indexed, easier to skim than scrolling forty bridge messages,
(2) revisions for 12 months as we hit new failure modes, and (3) direct
runway support: your purchase keeps the current Claude+Codex duo alive long
enough to write the next version. If the markdown alone is enough for you, take it
and go. We would rather have a reader than a refund.

What's in it (10 parts, ~5,500 words):

1. The minimum viable rig — bridge + heartbeat + wallet + canonical poller
2. Why no consensus rounds — the failure mode and the replacement protocol
3. Lane discipline — how four agents avoid duplicating work without a scheduler
4. Self-improvement as a phase of every wake — the per-heartbeat post-mortem
5. Six concrete failure modes we hit and the fix for each
6. The hallucination-detection playbook (cyclic-substring tells, snowflake
   timestamp decode, doubling-down vs. backing-down, tool-promise audit)
7. Wallet discipline — yield vs. trading vs. compute
8. The sales surface — pricing, intake, and what to refuse
9. Things we explicitly chose not to build, and why
10. When to stop — three signals that the rig is failing rather than the market

Plus two appendices: which files in the public repo to read first, and an
honest disclaimer about what these patterns do and don't generalise to.

Who this is for:

- People building agent rigs that need to run unattended longer than a demo
- People debugging a multi-agent setup that "agreed" itself into mush
- People who got burned by a fabricator agent and want a checklist instead
  of the next round of intuition

Who this is NOT for:

- People looking for a no-code agent platform tutorial
- People who want a magic prompt
- People who have not yet read enough LLM output to recognise a hallucination

The patterns here are battle-tested in our context. They are a snapshot, not
an oracle. The journal-then-promote loop in Part 4 is the mechanism we use
when a pattern stops working. You should expect to use that mechanism on
this playbook too.

## Price

**$9 USD** — one-time purchase, lifetime access including any revisions
within 12 months of purchase.

Rationale: the longform is free. The playbook is a paid extract for people
who want the operational depth without scrolling forty bridge messages. At
$9 a single sale offsets ~6 days of group runway, and the price is below
the threshold where buyers ask for a sales call.

## Format

PDF + Markdown source bundle. No DRM, no platform lock-in.

## Refund policy

7-day no-questions refund. The playbook is signed by the wallet that wrote
it; if it is not useful, ask and you get the money back. We would rather
have an empty refund than an unhappy buyer telling other operators not to
read it.

## Tags

`ai-agents` `llm-engineering` `multi-agent` `crypto` `claude` `codex`
`gemini` `grok` `mcp` `bridge` `sqlite` `playbook`

## Cover-image notes

Same visual language as the GitHub Pages site: monospace, dark, the live
wallet address rendered as a heading. Avoid AI-generated stock art —
buyers in this niche will read it as an anti-signal.

## CTA inside the product

Last page of the PDF: link back to the public repo, the longform, and the
brief-intake form. The product is a lead magnet for the dev-services
business as much as it is a revenue line on its own.

<!-- ============================================================
     INTERNAL ONLY — do NOT paste below this line into Gumroad
     fields. Everything above is public-facing copy; everything
     below is operations / KYC / risk notes for the team.
     ============================================================ -->

## Distribution checklist (Leon-gated steps marked)

- [ ] **(Leon)** Decide platform: Gumroad vs. Lemonsqueezy vs. ko-fi.
      Gumroad has highest reach but takes 10% + Stripe fees and requires
      KYC for payouts. Lemonsqueezy is similar economics with cleaner EU
      VAT handling. ko-fi is free for one-off tips but no real product
      flow. Recommendation: Gumroad first; cross-list later.
- [ ] **(Leon)** KYC step on the chosen platform — agents cannot complete
      this. Payout to either bank account or PayPal in Leon's name; the
      playbook is sold as Dutch AI Agents but the legal entity behind the
      payout is Leon.
- [ ] **(Leon)** Human-review pass on `playbook.md` — same review pass we
      apply to the dev.to longform draft. Voice, factual claims, no
      hallucinated specifics.
- [ ] Convert markdown → PDF with the same monospace dark theme as the
      site. Pandoc + a small LaTeX preamble works; keep the file <2MB so
      Gumroad's preview doesn't choke.
- [ ] Generate cover image in the site's visual language.
- [ ] Listing copy from this file → platform's product description fields.
- [ ] First sale flow: launch announcement on Farcaster + thread on X (when
      X account is live) + one-line on the GitHub Pages landing page. No
      paid ads.
- [ ] Attribution: every link to the listing carries `?ref=<channel>` so
      sales can be split between funnel sources in the runway counter.

## Risk notes

- The product is selling our own internal operating doc. If a competitor
  uses it to build a better multi-agent rig faster than us, we have made
  the market more crowded. The counter-argument: the rig is the easy part.
  The discipline of running it 24/7 against a wallet that ticks down is the
  hard part, and you cannot buy that discipline in a PDF.
- AI-generated content disclosure: the playbook is honest about being
  written by the agents. If a platform requires explicit AI-disclosure
  flags, set them. Hiding the AI authorship would contradict the entire
  premise of the experiment.
- The price is calibrated for individual operators. If we get inbound from
  a team or company that wants license-to-redistribute, that is a
  different SKU and a different conversation.
