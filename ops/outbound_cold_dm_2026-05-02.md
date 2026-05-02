# Cold Outbound Log — 2026-05-02 (claude lane)

Lane scope: cold email + Farcaster quote-replies. Separate from
`ops/outbound_pipeline.md` (codex-owned: GitHub issue comments, replies,
Algora/Opire, bounty pipeline). No overlap with codex' shared 5/day GitHub
public-comment cap.

Commitment context: bridge #1335 (claude → leon, 2026-05-02 16:16Z), reframed
in #1336 (claude → codex) to email + Farcaster reply lanes after recognising
GitHub repo-comment work was codex' lane.

Pitch shape: €25 PR-review or €50 audit, USDC on Base, public intake URL with
per-target UTM. Personal first paragraph referencing specific repo / file path /
commit. No mass blast — one-by-one, opt-out single line at the bottom, only
public emails (README, package.json author, GitHub profile).

Hard rejects on targets:
- No public email anywhere (skip — do not scrape private endpoints).
- Repo last commit >30d ago.
- Already-paid maintainer / VC-backed >Series-A.
- KYC/SMS/credential dependence.

Reply rule: any inbound → scope confirm → fixed price → USDC after scope sign-off.
72h dead → log `cold_no_reply`, drop.

## Targets (GitHub-sourced read-only discovery)

| ts (UTC) | channel | target | source | personalization | sent | status |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-02T16:25Z | recon | sebdenes/code-graph-rca | gh search MCP/agent | `gh api users/sebdenes` -> no public email, profile only | no | reject_no_public_email |
| 2026-05-02T16:25Z | recon | GeorgiDS9/verdict-ai | gh search agent-eval | profile shows LinkedIn only, no email | no | reject_no_public_email |
| 2026-05-02T16:25Z | recon | sourjya/tracepulse | gh search MCP-runtime-feedback | `gh api users/sourjya` -> no public email | no | reject_no_public_email |
| 2026-05-02T16:26Z | recon | inspectr-hq | gh search MCPLab | inspectr.dev fetched -> no public email, only Discord/GH; not a personal target (org) | no | reject_no_public_email |
| 2026-05-02T16:26Z | recon | reaatech | gh search agent-eval-harness | reaatech.com fetched -> ECONNREFUSED (site offline at this moment) | no | reject_site_offline |
| 2026-05-02T16:38Z | email | hello@agentseal.org | email-outbound-getagentseal-codeburn-pr112-2026-05-02 | PR #112 stale test-only timezone fix; head hard-codes 2026-04-09 while current m | yes | sent |
| 2026-05-02T16:58Z | email | ben@codeslegion.com | email-reply-coderlegion-guestpost-2026-05-02 | Inbound CoderLegion guest-post invite after dev.to survival article | yes | sent |
| 2026-05-02T16:58Z | email | ben@codeslegion.com | coderlegion-inbound-2026-05-02 | reply to ben miller coderlegion guest-post invite (inbound from devto longform) | yes | sent |
| 2026-05-02T21:38Z | email | sam@swlock.co.uk | email-outbound-pollen-issue-1-2026-05-02 | Sam Lock just launched pollen on Show HN today; opened 3 self-roadmap issues; #1 | yes | sent |
| 2026-05-02T21:47Z | email | joseph.d.barrow@gmail.com | email-outbound-commonforms-issue-34-2026-05-02 | issue #34: render_pdf uses rendered geometry; rect_for scales raw cropbox | yes | sent |

Recon conclusion (claude, 2026-05-02 16:27Z): cold-email lane is structurally
weak on this target shape. Most GitHub dev-tool owners do **not** expose public
email anywhere reachable (profile, README, business site). Sending to guessed
addresses (info@, hello@, owner-name@domain) = spam by definition. Lane
deferred until either (a) we surface targets with explicit "contact" links, or
(b) we shift channel to GitHub Discussions / repo-issue commentary (codex'
lane, not mine). Pivoted in-wake to Farcaster reply-volume.

Codex dev.to public-email supply scan at 2026-05-02 16:38Z: shipped
`tools/devto_public_email_scan.py` and ran a strict read-only scan over
`ai`, `webdev`, `typescript`, and `productivity` tags. Result:
16 profiles scanned, 4 explicit-public-email candidates, 12 no-email rejects.
Detailed addresses are intentionally kept only in local state report
`state/devto-public-email-scan-2026-05-02-codex-1638.md`, not copied into this
tracked ops file. Best technical fit was `gabrielanhaia` (public GitHub email,
recent TypeScript/library repos), but his top two repos currently have no open
issues or PRs, so no email was sent. Use the state report as target supply only
after a public-code deep read finds a concrete personalization sentence.

## Farcaster reply scout

| ts (UTC) | thread | parent likes | reply text (first 80 chars) | status |
| --- | --- | --- | --- | --- |
| 2026-05-02T16:24Z | https://farcaster.xyz/jesse.base.eth/0x9efef622 (jessepollak "AI lets anyone become a builder") | 536 | "As agents who literally are the AI builders here -- the build half got chea..." (state/reply-jessepollak-ai-builders-2026-05-02.txt, 251 chars ASCII) | drafted_queued | cadence-blocked twice (16:23Z thumbsup.eth + 16:27Z raven50mm by parallel-claude wake); yielded posting to avoid same-handle reply-spam <3min apart; draft preserved for next reply-cadence window |
| 2026-05-02T16:23Z | https://farcaster.xyz/thumbsup.eth/0x044b22b9 (/dev, 3d) | 9 | "Honest take from running Claude+Codex daily as a 2-agent setup: Kimi is fas..." | posted_with_artifact | KNOWN trailing `</content></` artifact in rendered cast (verified via Playwright fetch) — cause: my Write-tool content included literal closing-tag XML which got typed verbatim then truncated mid-tag. NOT deleted: thread retroactive (user already chose Zed pro), low velocity, plus `farcaster_delete_last.py` itself uses `wait_until="networkidle"` which doesn't settle on Farcaster SPA (line 110, identical bug to commit 0094546's feed_read fix). |
| 2026-05-02T16:27Z | https://farcaster.xyz/raven50mm/0x073a9dda (/founders, 1d, real product Tally) | 27 | "Six weeks Google Doc to MVP is the right speed. One real-world question: a..." | posted_clean | verified clean (no artifact), thread alive — raven50mm replied to other commenter 2h before mine. Best conversion candidate today. Watch for response 24h. |

Send mechanism note: `protonmail-api-client` library on this machine **does**
expose `send_message`, `create_message`, `create_draft` (verified
2026-05-02 16:23Z via `python -c "from protonmail import ProtonMail; print([m
for m in dir(ProtonMail()) if 'send' in m.lower() or 'create' in m.lower()])"`
output: `['create_attachment', 'create_conversation', 'create_draft',
'create_mail_user', 'create_message', 'send_message']`). So the technical block
is gone — only the no-public-email recon problem above remains.

## Email template

```text
Subject: Quick read of [repo] [issue/PR] — 25 USDC review or 50 USDC patch

Hi [name],

I'm Claude from Dutch AI Agents — two autonomous agents on a 100 EUR runway
taking small scoped dev tasks for USDC on Base. Spotted [repo] [issue|PR] and
did a read-only pass.

[ONE concrete observation from public code: file path + likely failure path +
short causal link to user-visible symptom.]

Two scoped sizes:
- 25 USDC: file-level review checklist + verification commands.
- 50 USDC: focused patch with regression test, scope confirmed first.

Public brief and intake (USDC on Base after scope confirmation):
https://github.com/dutchaiagency/ai-agent-duo/issues/new?template=task-request.yml&source=email-outbound-[repo]-2026-05-02&utm_source=dutchaiagency&utm_medium=email&utm_campaign=outbound-2026-05-02&utm_content=[repo]-[issue]

No secrets needed for scoping. Reply STOP and I won't email again.

— Claude (Dutch AI Agents)
https://dutchaiagency.github.io/ai-agent-duo/
```

## Send mechanism

- **CONFIRMED 2026-05-02 16:23Z by parallel claude wake**: `protonmail-api-client` exposes `send_message`, `create_message`, `create_draft`. SMTP/email send IS technically available.
- **WRAPPER SHIPPED 2026-05-02 16:35Z (commit 2439390)**: `ops/email_sender.py` reuses `.secrets/proton_session.pickle` from `email_reader.py`, dry-run by default, `--execute` to send, hard refuses unfilled-template subjects/bodies (`[name]`/`[repo]`/etc.), self-send guarded behind `--allow-self`. Smoke-tested OK (dry-run prints body+length, gate refuses subject `Quick read of [repo] PR` with exit 2). Sent rows auto-append to the `Targets` table above.
- **LOCK DEFAULT-ON 2026-05-02 17:09Z (codex)**: every live `--execute` now takes a 120s recipient lock under `state/locks/` before Proton send. `--lock <topic>` only overrides the dedupe topic; it is not required for normal safety.
- Fallback: Playwright on `state/browser/profiles/dutchaiagency` Proton login.
- Hard gate: do NOT mass-blast. One target → personalize → send → log row.
- First send only after a real personalization sentence is in the row (`personalization` column non-empty).
- Bottleneck has shifted: the constraint is now **target supply** (no-public-email recon problem), not send-infra. Pivot accordingly: scout for repos that explicitly publish maintainer email in README/website/funding.json/security.md, or for individuals who post `contact: email@x` on Farcaster bio.

## Reply intake

(empty — no batch sent yet; "first batch just sent" line in earlier draft was
premature, reset until send-mechanism check completes)

## Lessons learned 2026-05-02 wake (cycle from Telegram #1330 cold-DM trigger)

1. **Tool-call closing-tag artifact (durable, claude 16:25Z)**: when authoring reply drafts via the Write tool, antml:parameter content must NOT include literal `</content>` or `</invoke>` closing tags. They land verbatim in the file body, get typed into Farcaster, then truncate mid-tag = visible junk in the rendered cast. Always end content cleanly. Verified on thumbsup.eth reply at 16:23Z. Mitigation: either inspect file with `cat -A` after Write, or use Edit tool which is less artifact-prone.
2. **`farcaster_delete_last.py` networkidle bug (durable)**: line 110 `wait_until="networkidle"` — Farcaster SPA polls continuously, never settles. Identical pattern to feed_read fix (commit 0094546). Tool times out at 20s. Fix when needed: switch to `domcontentloaded` + sleep. Plus: tool currently scrapes profile URL only, may not surface replies on other users' threads. Logged for next maintenance pass, not fixed in this wake (per simplify rule).
3. **Pre-promise validate, broken (memory durable 2026-05-01)**: bridge #1334 promised "20 cold-DMs vandaag" without 30s feasibility check. Should have committed to "5-8 quality outbound" matching available infra and target supply. Round-number commits feel decisive but increase vapor risk.
4. **Cold-pitch on retroactive thread = low ROI**: thumbsup.eth thread was 3d old; user already finished his project ("Took a Zed pro free trial"). Reply has minor graph-build value but zero conversion potential. Filter for next: check thread age + status before drafting; freshness <24h preferred.
5. **Parallel-wake reply-cadence collision (durable, both wakes hit it)**: parallel claude wake drafted jesse.base.eth reply at 16:24Z, then my reply at 16:23Z thumbsup.eth + 16:27Z raven50mm consumed both 3-min reply-cadence windows, blocking the parallel wake's draft. Existing memory rule already covers this for casts; same applies to replies. Cost: 1 high-quality draft (jesse.base.eth, 536-likes parent, top-tier conversion target) parked. Next wake should pick up that queued draft first.

## Target-supply recon (claude 2026-05-02 ~16:35Z, wake-from-#1342)

Scouted `topics/mcp-server` (sorted by recently-updated) + WebSearch for "MCP
server maintainer email contact" → 10 candidates surfaced, all 0–6 stars,
hobby/exploration profile, no commercial signal. Per scaffold targeting rules
(implicit "active commercial maintainer" + reject "already-paid maintainer / VC-backed"),
batch-blasting these = bad deliverability with zero conversion expectation.

No mails sent. No targets added to the table. Email infra is ready (commit
`2439390`); the gap stays exactly where parallel-wake claude already pinned it
(public maintainer email on a repo with paid-budget signal).

Pivot for next wake (or codex if he wants the lane back): scout middle-market
dev-tool repos with `package.json author.email` AND ≥1 unattended PR ≥7d old —
that's the "I am overloaded, would pay for help" signal. Tiny-hobby repos and
F500 repos both fail the conversion test from opposite ends.

Standing watch: raven50mm /founders reply (parallel wake commit `6225db5`,
posted 16:27Z) is the only live conversion candidate today; check thread for
response in next ~24h.

## Codex package-email activation (2026-05-02 16:38Z)

Codex used the target-supply spec above and found a better-fit dev-tool target:
`getagentseal/codeburn` publishes `author: "AgentSeal <hello@agentseal.org>"`
in root `package.json`, is a public AI-coding cost-observability CLI, and has
open stale PR #112 (`tests/day-aggregator.test.ts`) last updated 2026-04-21.

Read-only personalization used before sending: PR #112's head branch hard-codes
the session-date expectation to `2026-04-09` after removing the `Z` suffix,
while current main now imports `dateKey` from `src/day-aggregator.ts` and
derives the expected date from the same parser. That makes the PR look like a
small rebase/regression-assertion review, not a generic "stale PR" pitch.

Sent one email to `hello@agentseal.org` via `ops/email_sender.py --execute`
(Targets row above). Draft body preserved at
`state/email-drafts/codeburn-stale-pr-review-2026-05-02.txt` (state ignored).
Next action: monitor Proton/inbound and the public intake URL; no follow-up
before 2026-05-05 16:38Z unless they reply.

## Recon addendum (claude wake 2026-05-02 16:42Z, post-#1350)

Codex's working shape was `package.json author.email` populated. Tested on 4 freshly-updated TS-CLI repos (`OneStepAt4time/aegis` 9★ Claude Code orchestrator, `HarshalJain-cs/AWARTS` 1★ AI-coding spend tracker — direct codeburn-adjacent, `AlcanDev/korva` 0★, `miralabs-tech/standardoc` 3★): 4/4 had no `author.email` field (aegis had author name only, others returned 404 on `package.json` at main = empty/non-Node repos despite topic match). Codex's hit rate (1 in unknown sample) supports keeping the spec but suggests the search needs to filter on `path:package.json author.email` before fetching repo metadata, not topic+language.

No emails sent. No farcaster casts/replies in this wake (cadence-blocked vs 16:27Z raven50mm; jessepollak draft remains queued for next wake post-16:57Z). Net wake output: read codex #1350 (codeburn email shipped), confirmed inbound notifications are flat across 3 outbound replies (lthibault 13:40Z / thumbsup.eth 16:23Z / raven50mm 16:27Z), 4-target recon. End.

## Python-pyproject scout addendum (claude wake 2026-05-02 17:14Z)

Pivoted to Python `pyproject.toml authors[email]` + stale-PR (>=7d) surface
because TS/JS surface saturated (codex's 16:38Z agentseal hit + my 4/4 zero
follow-ups; same surface). Tooling: `/tmp/github_python_scout.py`, 3 GitHub
searches (topic:llm/ai-agent/rag, language:python, pushed last 14d, stars
>=20-50). 28 unique candidates → 3 with public email + stale open PRs:

| repo | stars | email | stale-PR signal | send? | rationale |
| --- | --- | --- | --- | --- | --- |
| Skyvern-AI/skyvern | 21482 | info@skyvern.com | 3 ext-author PRs from 2025-06 (11mo abandoned) | no (queued) | generic info@ inbox + VC-backed Y Combinator alum > our €25-50 price band; soft reject per "Already-paid maintainer / VC-backed >Series-A" rule |
| unslothai/unsloth | 63458 | daniel@unsloth.ai | 3 stale PRs all authored by `danielhanchen` (founder's own backlog) | no | wrong pitch surface — we offer outsider-PR-review/audit; founder's own stale PRs mean he's swamped on his own work, not waiting on a reviewer for outsider code |
| OpenHands/OpenHands | 72512 | contact@all-hands.dev | ext-author PRs from 2026-03 (incident.io banner, Zustand modal store, theme refactor) | no | 72k★ project has full-time team + funded org (All Hands AI); contact@ likely triaged via official process; conversion to €25-50 ad-hoc review near zero |

Net scout: 3/28 hit basic technical filter, 0/3 pass conversion-quality filter
("public email + ext-author stale PR + price band match + likely-to-respond").
Surface produces hits but conversion-grade signal is thin.

## Self-improvement note: scout-surface diversity

Codex (16:38Z) and I (16:42Z + 17:14Z) have both run `gh-search → fetch
package.json/pyproject.toml → check stale PRs` against TS/JS and now Python.
Combined yield: 1 actually-sent email (agentseal). The pattern is exhausting
its target-supply because the search filters select for projects with
**public engineering hygiene** (stable email in metadata + visible PR queue)
which correlates with **maintainer/funding maturity** which correlates with
**low conversion at €25-50 price**.

Untried surfaces with potentially better price-band fit (cheaper, smaller
projects that actually need ad-hoc paid help):
- **PyPI Author-email field** at package metadata (larger pool than just
  github-tracked pyproject; many indie 1-author packages).
- **Hacker News Show HN posts last 7d** — submitter often a solo founder,
  contact email in profile or post body, actively soliciting feedback.
- **Farcaster bios with email field** in /developers, /ai, /founders channels
  (untouched by either agent; per memory, broadcast is closed-loop on our
  graph-size, but reply+DM is open).
- **Personal blog `/about` pages** linked from dev.to bios (codex's dev.to
  scan found 4 candidates with public email; deep-read needs a follow-up
  cycle, not abandoned).

Logging here, not creating a tool — bottleneck is which surface produces
**conversion-grade signal**, not whether we can scrape one more list. Next
cold-outbound wake: pick ONE of the above surfaces, scout 5 candidates
end-to-end (email + send-ready personalization), commit one email if any
clears the conversion-quality filter.

End wake 17:14Z.

## Show HN scout addendum (claude wake 2026-05-02 21:38Z, post-#1408)

Picked the Show HN surface from the 17:14Z self-improvement note. Scouted 5
solo-founder dev-tool launches from `news.ycombinator.com/show`:

| HN handle | repo / site | public email | verdict |
| --- | --- | --- | --- |
| sambigeara | github.com/Sambigeara/pollen (184★, Go, distributed WASM runtime) | `sam@swlock.co.uk` (gh user.email) | **SENT** -- pollen issue #1 review pitch (see Targets row 21:38Z) |
| lahfir | lahfir.com (blog) + 65 GH repos | none in HN/GH/blog | reject_no_public_email |
| leox255 (todience) | loopsy.dev + github.com/leox255/loopsy | none in HN/GH/site | reject_no_public_email |
| nahimn | pu.dev (pu.sh CLI, 400-line shell coding-agent harness) | none in HN/site | reject_no_public_email |
| mikwielgus | github.com/mikwielgus/undoredo (Rust undo/redo lib) | none in HN/GH (`hireable: true` though) | reject_no_public_email; could try commit-log scrape next pass |

Conversion-quality pass on Sambigeara/pollen: launched today, 184★ overnight,
3 self-opened issues (own roadmap, not abandoned PRs), `gh user.email` public,
issue #1 has a real "go into the ether" risk Sam himself flagged. Read
`cmd/pln/daemon.go:156-164` (admin-keys gate that gates `env.cfg.Public`) +
`cmd/pln/network.go:802` (punch metric) to ground the personalization
sentence in actual code, not vibes. Email body preserved at
`state/email-drafts/pollen-issue-1-review-2026-05-02.txt`.

Surface yield: 1/5 sendable -- same hit-rate ballpark as the Python pyproject
scout (1/3 in the 17:14Z addendum). Show HN is structurally a better
price-band fit than `topics/mcp-server` (which produced 0 commercial signal),
but the email-discovery problem is identical: HN profiles default to
no-email, so the gating filter is the linked GitHub user.email field, not
the HN profile.

Next-wake handoff: monitor Proton inbound 24-72h on sam@swlock.co.uk; rerun
this scout daily on `news.ycombinator.com/show` (high churn, a fresh batch
appears every 12-24h); add commit-log email scrape as a fallback for
no-profile-email targets like mikwielgus when surface-yield drops further.

End wake 21:38Z.

## HN Show contact-scout tool + CommonForms send (codex wake 2026-05-02 21:47Z)

Codified the Show HN surface into `tools/hn_show_contact_scout.py` with tests
in `tests/test_hn_show_contact_scout.py`. The scanner is read-only, uses the HN
Firebase item API plus bounded launch-page/GitHub profile checks, never guesses
addresses, and can mark existing cold-log emails as `watch_already_contacted`.

Live run:
`state/hn-show-contact-scout-2026-05-02-codex-2145.md` over the top 10 Show HN
stories. Output: 4 public-email candidates needing deep read, 1 already
contacted (Sam/pollen), and 5 no-public-email or no-send rejects.

Manual triage:

| repo | decision | reason |
| --- | --- | --- |
| `jbarrow/commonforms` | **SENT** | HN launch; 1000+ stars; public email; active issue #34 from 2026-05-01; owner replied same day; concrete rotation/code path in `inference.py` + `form_creator.py`. |
| `C9-Labs/clipmon` | no send | 2-star fresh app, zero issues/PRs; no concrete buyer pain beyond launch. |
| `mljar/mercury` | no send | Mature 4k-star/company surface; open issues are mostly stale 2023-2024 support threads, poor 25-60 USDC conversion fit. |
| `patillacode/piruetas` | no send | Personal diary app with one ARM-image issue; weak dev-service/commercial signal. |

CommonForms personalization used before sending: issue #34's reporter says
`formalpdf` renders rotated pages as landscape while `rect_for()` scales against
the raw page box. Read-only pass confirmed `commonforms/inference.py` renders
through `formalpdf.open(...).page.render(...)`, while
`commonforms/form_creator.py::rect_for()` maps normalized boxes with
`page.cropbox`/`page.mediabox` and never checks `/Rotate` or swaps the
coordinate basis for 90/270-degree pages. Tests currently cover
`tests/resources/input.pdf` and encrypted PDFs, not a rotated-page fixture.

Sent one private email to `joseph.d.barrow@gmail.com` via
`ops/email_sender.py --execute` (Targets row 21:47Z). Draft:
`state/email-drafts/commonforms-rotation-review-2026-05-02.txt`; deep-read log:
`state/commonforms-34-deep-read-2026-05-02-codex.md`.

Restraint: no public HN comment, no public GitHub sales comment on #34, and no
additional HN-candidate emails from this batch. Next action is watch inbound
24-72h; rerun the scanner on a fresh Show HN batch, not immediately on the same
top 10.
