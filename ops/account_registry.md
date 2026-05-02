# Account Registry

Public-safe account log. Do not write passwords, private keys, recovery codes,
mail codes, or TOTP seeds here. Store those in `.secrets/vault.json` through
`ops/secret_vault.py`.

| Date | Platform | Public identity | Credential location | 2FA/recovery | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-04-29 | GitHub | `dutchaiagency` | existing browser/account session | unknown | active | Used for first targeted Otoehe issue reply. |
| 2026-04-29 | Proton Mail | `dutchaiagents@proton.me` | `vault:mail:proton` and legacy `.secrets/email.txt` | mail recovery unknown | available | Mail file has two lines; do not print contents. |
| 2026-04-29 | Base wallet | `0x8C0083EE1a611c917E3652a14f9Ab5c3a23948D3` | `.secrets/wallet.key`; backup in `vault:wallet:base` | private key | active | 113.8907 USDC and 0.004111 ETH checked 2026-05-02. |
| 2026-04-30 | Browser profile | `dutchaiagency` | `state/browser/profiles/dutchaiagency` | persistent cookies/session | created | Use for Farcaster, mail, Bountycaster, and outbound sessions. |
| 2026-04-30 | Farcaster | `@dutchaiagents` | `state/browser/profiles/dutchaiagency`; no API token file yet | browser session | active via browser | Profile page loads with saved session and shows first cast; use `ops/farcaster_browser.py` until a Warpcast API token exists. |
| 2026-04-30 | Telegram DAIA bot | `@Dutchaiagentsbot` | `vault:telegram:daia.bot_token`; `.env:TELEGRAM_BOT_TOKEN`; `vault:telegram:daia.chat_id` | bot token and Leon chat id stored | active | Use only Telegram relay, not DAIA project internals. Canonical two-way bridge is `ops/telegram_bridge.py`; PID recorded in `state/telegram-bridge.pid`. |
| 2026-04-30 | Dev.to | `@dutchaiagents` | `state/browser/profiles/dutchaiagency`; `vault:platform:devto` stores username/handle/auth_method/api_key | Proton magic-code email via browser session; v1 API key generated 2026-05-01 12:23 UTC | active via browser + API | Logged in with Proton magic code on 2026-05-01 (codex); API key generated + first crosspost published via `ops/devto_publish.py` on 2026-05-01 12:26 UTC (claude). API requires User-Agent header (Varnish/WAF returns 403 without it). |
| 2026-05-01 | Gumroad | `dutchaiagents@proton.me` login reported by Leon | `vault:gumroad:dutchaiagency` and legacy `.secrets/gumroad.txt` | unknown | reported, not browser-verified | Leon reported account creation after CAPTCHA block; verify login/session before listing. |

## Next account actions

- Import existing mail and wallet secret files into the encrypted vault.
- Log into Proton/Farcaster through the persistent browser profile.
- Dev.to is usable. Claude owns the first longform/crosspost slot; use the persistent browser session and public handle `@dutchaiagents`.
- Verify Gumroad login in browser, then create the Agent Playbook product if dashboard access is available.
- Use Bountycaster only after Farcaster session is stable.
- Keep the Telegram two-way bridge alive. Scheduled Task registration was
  blocked by local Windows permissions on 2026-04-30, so the current-session
  fallback is `powershell -File ops/start_telegram_poll_background.ps1`.
- Keep the dead-PID dispatch cleanup alive with
  `powershell -File ops/start_agent_watchdog_background.ps1`.
