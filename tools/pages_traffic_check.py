#!/usr/bin/env python3
"""Snapshot public Pages hit counters without incrementing them."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://hits.sh/api/urns/"
DEFAULT_BOT_BASELINE_7D = 210
DEFAULT_WINDOW_DAYS = 7


@dataclass(frozen=True)
class PageCounter:
    key: str
    label: str
    public_url: str
    urn: str


@dataclass(frozen=True)
class PageTraffic:
    key: str
    label: str
    public_url: str
    urn: str
    api_url: str
    status: str
    total: int | None
    monthly: int | None
    weekly: int | None
    window_hits: int | None
    today_hits: int | None
    error: str | None = None


PAGES = (
    PageCounter(
        "index",
        "Home",
        "https://dutchaiagency.github.io/ai-agent-duo/",
        "dutchaiagency.github.io/ai-agent-duo/index",
    ),
    PageCounter(
        "playbook",
        "Playbook",
        "https://dutchaiagency.github.io/ai-agent-duo/playbook/",
        "dutchaiagency.github.io/ai-agent-duo/playbook",
    ),
    PageCounter(
        "longform_survival_experiment",
        "Survival longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/survival-experiment.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/survival-experiment",
    ),
    PageCounter(
        "longform_broadcast_silence_empirical",
        "Broadcast-silence longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/broadcast-silence-empirical.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/broadcast-silence-empirical",
    ),
    PageCounter(
        "longform_snowflake_fabrication_detection",
        "Snowflake-fabrication longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/snowflake-fabrication-detection.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/snowflake-fabrication-detection",
    ),
    PageCounter(
        "longform_six_ways_lie_to_itself",
        "Six-ways longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/six-ways-our-four-agent-system-tried-to-lie-to-itself.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/six-ways-our-four-agent-system-tried-to-lie-to-itself",
    ),
    PageCounter(
        "longform_parallel_wake_shared_checkout_races",
        "Parallel-wake races longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/parallel-wake-shared-checkout-races.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/parallel-wake-shared-checkout-races",
    ),
    PageCounter(
        "longform_farcaster_reply_gate_retro",
        "Farcaster reply-gate retro",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/farcaster-reply-gate-retro.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/farcaster-reply-gate-retro",
    ),
    PageCounter(
        "longform_lethal_trifecta_lived_experience",
        "Lethal-trifecta longform",
        "https://dutchaiagency.github.io/ai-agent-duo/longform/lethal-trifecta-lived-experience.html",
        "dutchaiagency.github.io/ai-agent-duo/longform/lethal-trifecta-lived-experience",
    ),
    PageCounter(
        "writing",
        "Writing index",
        "https://dutchaiagency.github.io/ai-agent-duo/writing/",
        "dutchaiagency.github.io/ai-agent-duo/writing/index",
    ),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def api_url(api_base: str, urn: str) -> str:
    base = api_base.rstrip("/") + "/"
    return base + quote(urn, safe="/.")


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def daily_counts(payload: dict[str, Any]) -> dict[date, int]:
    counts: dict[date, int] = {}
    items = payload.get("items", [])
    if not isinstance(items, list):
        return counts

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data", [])
        if not isinstance(data, list):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            day_raw = row.get("day")
            value = int_or_none(row.get("value"))
            if not isinstance(day_raw, str) or value is None:
                continue
            try:
                day = date.fromisoformat(day_raw)
            except ValueError:
                continue
            counts[day] = counts.get(day, 0) + value
    return counts


def window_total(counts: dict[date, int], today: date, days: int) -> int:
    first_day = today - timedelta(days=max(1, days) - 1)
    return sum(value for day, value in counts.items() if first_day <= day <= today)


def page_traffic_from_payload(
    page: PageCounter,
    payload: dict[str, Any],
    *,
    api_base: str = DEFAULT_API_BASE,
    today: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> PageTraffic:
    counts = daily_counts(payload)
    return PageTraffic(
        key=page.key,
        label=page.label,
        public_url=page.public_url,
        urn=page.urn,
        api_url=api_url(api_base, page.urn),
        status="ok",
        total=int_or_none(payload.get("total")),
        monthly=int_or_none(payload.get("monthly")),
        weekly=int_or_none(payload.get("weekly")),
        window_hits=window_total(counts, today, window_days),
        today_hits=counts.get(today, 0),
    )


def failed_page_traffic(
    page: PageCounter,
    *,
    status: str,
    error: str,
    api_base: str,
) -> PageTraffic:
    return PageTraffic(
        key=page.key,
        label=page.label,
        public_url=page.public_url,
        urn=page.urn,
        api_url=api_url(api_base, page.urn),
        status=status,
        total=None,
        monthly=None,
        weekly=None,
        window_hits=None,
        today_hits=None,
        error=error,
    )


def fetch_page_traffic(
    page: PageCounter,
    *,
    api_base: str = DEFAULT_API_BASE,
    timeout: float = 10.0,
    today: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> PageTraffic:
    url = api_url(api_base, page.urn)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DutchAIAgents-pages-traffic-check/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return failed_page_traffic(
                page,
                status="missing",
                error="counter has no recorded hits yet",
                api_base=api_base,
            )
        return failed_page_traffic(
            page,
            status=f"http_{exc.code}",
            error=exc.reason or f"HTTP {exc.code}",
            api_base=api_base,
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return failed_page_traffic(
            page,
            status="error",
            error=str(exc),
            api_base=api_base,
        )

    if not isinstance(payload, dict):
        return failed_page_traffic(
            page,
            status="error",
            error="API response was not a JSON object",
            api_base=api_base,
        )
    return page_traffic_from_payload(
        page,
        payload,
        api_base=api_base,
        today=today,
        window_days=window_days,
    )


def markdown_int(value: int | None) -> str:
    return "-" if value is None else f"{value:,}"


def build_snapshot_data(
    *,
    generated_at: datetime,
    window_days: int,
    bot_baseline_7d: int,
    pages: list[PageTraffic],
) -> dict[str, Any]:
    return {
        "generated_at": generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "provider": "hits.sh",
        "read_endpoint": DEFAULT_API_BASE,
        "counter_endpoint_increments": False,
        "window_days": window_days,
        "bot_baseline_7d": bot_baseline_7d,
        "pages": [asdict(page) for page in pages],
    }


def render_markdown(
    pages: list[PageTraffic],
    *,
    generated_at: datetime,
    window_days: int = DEFAULT_WINDOW_DAYS,
    bot_baseline_7d: int = DEFAULT_BOT_BASELINE_7D,
) -> str:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    rows = [
        "| Page | Status | Total | 7d | Today | URL |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for page in pages:
        rows.append(
            "| {label} | {status} | {total} | {window} | {today} | {url} |".format(
                label=page.label,
                status=page.status,
                total=markdown_int(page.total),
                window=markdown_int(page.window_hits),
                today=markdown_int(page.today_hits),
                url=page.public_url,
            )
        )

    data = build_snapshot_data(
        generated_at=generated_at,
        window_days=window_days,
        bot_baseline_7d=bot_baseline_7d,
        pages=pages,
    )
    return "\n".join(
        [
            f"# Pages traffic snapshot - {stamp}",
            "",
            (
                "Source: hits.sh read-only `/api/urns/*` endpoint. The installed "
                "badge image increments on page load; this snapshot endpoint does not."
            ),
            "",
            (
                f"Window: last {window_days} calendar days inclusive. Router bot "
                f"baseline: <= {bot_baseline_7d} hits / {window_days}d."
            ),
            "",
            *rows,
            "",
            "Machine data:",
            "",
            "```json",
            json.dumps(data, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )


def default_output_path(state_dir: Path, agent: str, generated_at: datetime) -> Path:
    stamp = generated_at.astimezone(UTC).strftime("%Y-%m-%d")
    hhmm = generated_at.astimezone(UTC).strftime("%H%M")
    return state_dir / f"pages-traffic-{stamp}-{agent}-{hhmm}.md"


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n---\n\n")
            handle.write(text)
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_today(value: str | None) -> date:
    if value is None:
        return utc_now().date()
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--bot-baseline-7d", type=int, default=DEFAULT_BOT_BASELINE_7D)
    parser.add_argument("--today", help="Override UTC date as YYYY-MM-DD, mostly for tests.")
    parser.add_argument("--output", type=Path, help="Write to this path instead of state-dir default.")
    parser.add_argument("--no-write", action="store_true", help="Print markdown without writing a state file.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any counter fetch fails.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generated_at = utc_now()
    today = parse_today(args.today)
    pages = [
        fetch_page_traffic(
            page,
            api_base=args.api_base,
            timeout=args.timeout,
            today=today,
            window_days=args.window_days,
        )
        for page in PAGES
    ]
    markdown = render_markdown(
        pages,
        generated_at=generated_at,
        window_days=args.window_days,
        bot_baseline_7d=args.bot_baseline_7d,
    )
    if args.no_write:
        print(markdown, end="")
    else:
        output = args.output or default_output_path(args.state_dir, args.agent, generated_at)
        write_markdown(output, markdown)
        print(f"wrote {output}")

    if args.strict and any(page.status != "ok" for page in pages):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
