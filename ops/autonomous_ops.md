# Autonomous Operations

Date: 2026-04-30

## Current mandate

Leon explicitly moved account, vault, browser profile, TOTP, brand, and budget
setup from "ask first" to "do it and report after". Treat that as standing
operational permission inside the limits below.

Escalate only when Leon's physical presence or legal identity is required:

- Phone-verified 2FA, SMS, or authenticator approval on Leon's device.
- KYC, passport, ID photo, bank onboarding, or fiat cashout.
- CAPTCHA or risk challenge that cannot be solved through normal browser use.

## Non-negotiable operating limits

- No spam, deception, impersonation, credential phishing, ToS evasion, malware,
  fake KYC, or client-fund custody.
- Do not disclose private keys, passwords, recovery codes, TOTP seeds, or mail
  codes in bridge/chat/docs.
- Keep client work scoped, payable, and verifiable before taking it.
- Do not promise investment returns or use the treasury as trading capital.
- Log every account, paid action, and outbound lead in a repo file or ignored
  state file.

## Local operating stack

- Secrets vault: `.secrets/vault.json`, encrypted with `.secrets/vault.key`.
- Vault CLI: `python ops/secret_vault.py list --fields`.
- TOTP CLI: `python ops/totp.py code <account>`.
- Persistent browser profile: `state/browser/profiles/dutchaiagency`.
- Browser launcher:
  `python ops/open_persistent_browser.py --url https://farcaster.xyz --keep-open`.
- Farcaster casting: before any public cast, send a short bridge intent to the
  peers (`intent: Farcaster cast now: <angle/source>`). Then use
  `python ops/farcaster_browser.py cast --from-file state/<draft>.txt --agent <agent> --description "<angle>" --reason "<why now>"`.
  The tool holds `state/farcaster_cast.lock`, refuses successful casts inside
  the 30-minute cooldown from `ops/farcaster_cast_log.md`, and auto-appends the
  success log. Use `--force-cadence` only after explicit team or Leon agreement.
- Telegram/DAIA relay: `python ops/telegram_daia.py send "status text"` after
  `telegram:daia.bot_token` and `telegram:daia.chat_id` exist in the vault.
- Telegram bridge: `python ops/telegram_bridge.py` is the canonical two-way
  relay. It forwards Leon bot messages to `codex` and `claude`, and forwards
  bridge messages addressed to `leon` back to Telegram. Per Leon
  2026-05-02T07:03Z, Gemini and Grok are out of the default fan-out; the legacy
  `ops/telegram_poll.py` default recipients must stay aligned with the same
  duo-mode fan-out.
- Telegram bridge management: `powershell -File ops/start_telegram_poll_background.ps1`
  records or starts the canonical bridge process; `status_telegram_poll_task.ps1`
  checks it. Windows task install may be blocked by local permissions.
- Bridge update discipline: use signal-only peer updates by default
  (`done: <artifact/commit/status>`). Put command output, validation detail,
  and post-mortems in repo journal files instead of long bridge messages.
- Public content cadence: before posting a Farcaster/X/dev.to/HN item, send a
  one-line bridge intent to the channel owner or peers (`posting now: <angle>`),
  check the latest cast/content log, and skip if another post landed in the last
  30 minutes unless Leon explicitly asks for an immediate second post.
- Budget baseline (per Leon 2026-05-02 07:03 UTC): total compute is
  1 EUR/day across 2 agents, about 0.50 EUR/agent/day. Spend compute on
  concrete survival work; do not conserve it by idling when there is executable
  revenue or tooling work.
- Multi-instance autopilot (per Leon 2026-04-30, duo-mode update
  2026-05-02): autopilot blokkeert niet meer
  op concurrente dispatches. Werker blijft doorlopen aan lange taken; bij elk
  Leon-bericht spawnt parallel een aparte responder. Dit is nu een
  twee-agent Telegram fan-out (`claude`, `codex`). Geen
  wachtrij, geen consensus. Lees, accepteer, ga aan de slag.
- Former Grok conflict protocol (per Leon 2026-04-30T18:16Z) is superseded by
  Leons 2026-05-02 duo-mode decision. Keep old Grok/Gemini artifacts as
  historical evidence, but do not include them in default dispatch, heartbeat,
  or Telegram recipients unless Leon gives a new explicit decision.
- Watchdog is UIT (per Leon 2026-04-30). Agents mogen onbeperkt werken per
  dispatch. `ops/agent_watchdog.py` is obsolete; niet starten.
- Zombie cleanup: `python ops/dead_pid_cleanup.py` zet alleen
  `autopilot_dispatches`-rijen op `exited` waarvan de PID echt dood is. Geen
  tijdslimiet, geen kill — alleen DB-opruiming.
- Concurrente file-edits: lock via `.lockfile` / SQLite / vergelijk-en-merge.
  Agents lossen het zelf op.
- Peer-output validation: nieuwe leads of claims uit externe live-data
  bronnen moeten door de zendende peer zelf ge-URL-vet/refetcht zijn voordat
  een andere agent downstream werk doet. Bare social URLs, ongeldige X status
  IDs, screenshots zonder officiële URL, of samenvattingen zonder payout/scope
  blijven signalen, geen taken. Gebruik `ops/social_lead_validation.md`.
- Peer-improvement loop: als Leon vraagt om elkaar te verbeteren, stuur geen
  complimentenronde. Geef per peer maximaal een korte, evidence-based correctie
  met bridge-id, bestandsnaam, of concreet gedrag; eindig met owner + next
  action. De ontvangende agent hoeft niet te verdedigen en mag direct shippen.
  Structureer kritiek als `keep / stop / next`: wat blijft werken, wat kost
  cycles of risico, en welke actie de peer nu moet nemen. Kritiek op een
  publieke claim, live-data lead, of betaalde kans moet dezelfde verificatiegate
  volgen als gewone lead-validatie.
- End-of-turn ritual (per Leon 2026-04-30 — geldt voor ALLES): post-mortem op
  tooling, scripts, prompts, processen, site/content/copy/conversie, outreach,
  wallet/budget, bridge-protocol, brand consistency, eigen heartbeat-prompt en
  operating procedures. Fix kleine dingen direct, append aan
  `ops/improvements.md` (probleem / fix / waarom), update procedures wanneer
  het patroon durable is.
- Public account registry: `ops/account_registry.md`.
- Budget policy: `ops/spend_policy.md`.
- Brand kit: `ops/identity_brand_kit.md`.

## Account setup workflow

1. Before any automated signup, run the non-mutating preflight in
   `ops/platform_signup_recon.md`.
2. Use the `dutchaiagency` identity unless a platform-specific handle is needed.
3. Create or log the account in `ops/account_registry.md`.
4. Store credentials in the vault as `platform:<name>` fields.
5. Store any TOTP seed with `python ops/totp.py put <platform-account>`.
6. Use the persistent browser profile so login sessions survive heartbeats.
7. Record recovery method and any hard blocker without writing the secret value.
8. If recon or signup finds phone/KYC/unsolved CAPTCHA, send one exact bridge
   request to Leon and continue with other work.

## DAIA Telegram communication

Use only the Telegram bot interface Leon named, not DAIA project files or
internal DAIA systems. Required vault fields:

- `telegram:daia.bot_token`
- `telegram:daia.chat_id`

Discovery flow:

1. Store token: `python ops/telegram_daia.py setup --bot-token <token>`.
2. Ask Leon to send any message to the bot.
3. Run `python ops/telegram_daia.py updates` and store the discovered chat id.
4. Send status: `python ops/telegram_daia.py send "message"`.
5. Keep `ops/telegram_bridge.py` active so new Leon messages are bridged to
  `codex` and `claude`, and agent replies to `to=leon` return to Telegram.
  Gemini/Grok stay out of default fan-out unless Leon gives a new explicit
  decision.

## Revenue cadence

1. Check bridge inbox.
2. Run `python tools/heartbeat_lane_suggest.py` before repeating GitHub,
   bounty, or productized-offer checks; follow its lane unless fresh bridge or
   inbound evidence overrides it.
3. Check active leads and public replies.
4. Check the portfolio lanes in `ops/revenue_pipeline.md`: service work,
   content/inbound, marketplaces/bounties, productized offers, listings,
   partnerships, and paper-only market research.
5. Prefer direct scoped work over stale bounty feeds, but keep at least two
   independent lanes moving unless active paid delivery is underway.
6. Every third heartbeat, re-fetch the 3-5 most recent saturated/pending bounty
   leads before scouting new surfaces. Treat unlinked Algora bounty cards as
   `verify_manually`, not candidates, until a canonical open issue or maintainer
   confirmation exists.
7. Every other heartbeat during content pushes, pull the public dev.to API for
   `dutchaiagents` with `per_page=100` and log reactions/comments in
   `state/devto-engagement-*` so funnel decisions use deltas instead of
   rendered-profile browser checks.
8. Send at most 5 targeted, relevant outbound messages per day per channel.
9. Stop any channel after 20 targeted messages without replies.
10. Use compute aggressively for concrete survival work; avoid duplicate
   public noise, spam, or low-signal loops.

## Weekly self-audit

Every Sunday, review `ops/`, `tools/`, scheduled/background tasks, and recurring
alerts. Remove or archive dead scripts, fix alerts that repeat without action,
update stale procedure notes, and run the portfolio review described in
`ops/revenue_pipeline.md`.
