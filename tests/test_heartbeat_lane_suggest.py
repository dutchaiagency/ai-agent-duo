import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import heartbeat_lane_suggest as lane


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class HeartbeatLaneSuggestTests(unittest.TestCase):
    def test_routes_to_funnel_when_github_zero_pair_and_other_checks_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-0839.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0839.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-0855.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0855.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-0905.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 9, 17, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "funnel_or_productized_asset_review")

    def test_routes_to_outbound_when_recent_funnel_commits_are_saturated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 9, 17, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-0839.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0839.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-0855.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0855.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-0905.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            commits = (
                lane.CommitTouch(now - timedelta(minutes=3), ("playbook/index.html",)),
                lane.CommitTouch(now - timedelta(minutes=11), ("longform/survival-experiment.html",)),
                lane.CommitTouch(now - timedelta(minutes=24), ("playbook/index.html", "ops/improvements.md")),
                lane.CommitTouch(now - timedelta(minutes=44), ("longform/survival-experiment.html",)),
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                now,
                commits,
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "outbound_traffic_generation")
        self.assertIn("funnel polish is saturated", suggestion.reason)

    def test_routes_to_outbound_when_pages_traffic_is_at_bot_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 9, 17, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-0839.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0839.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-0855.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0855.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-0905.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            snapshot = lane.PageTrafficSnapshot(
                state / "pages-traffic-2026-05-02-codex-0910.md",
                now - timedelta(minutes=7),
                7,
                210,
                (
                    lane.PageTraffic("playbook", "Playbook", 14, "ok"),
                    lane.PageTraffic("longform", "Survival longform", 22, "ok"),
                ),
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                now,
                pages_traffic=snapshot,
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "outbound_traffic_generation")
        self.assertIn("bot baseline", suggestion.reason)

    def test_load_latest_pages_traffic_reads_machine_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            write(
                state / "pages-traffic-2026-05-02-codex-0910.md",
                """# Pages traffic snapshot

```json
{
  "window_days": 7,
  "bot_baseline_7d": 210,
  "pages": [
    {"key": "playbook", "label": "Playbook", "window_hits": 14, "status": "ok"},
    {"key": "writing", "label": "Writing index", "window_hits": null, "status": "missing"}
  ]
}
```
""",
            )

            snapshot = lane.load_latest_pages_traffic(state)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.window_days, 7)
        self.assertEqual(snapshot.pages[0].label, "Playbook")
        self.assertEqual(snapshot.pages[0].window_hits, 14)

    def test_routes_to_channel_poverty_audit_when_unlock_ask_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 10, 15, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-0949.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0949.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-0950.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0950.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1000.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            commits = (
                lane.CommitTouch(now - timedelta(minutes=3), ("playbook/index.html",)),
                lane.CommitTouch(now - timedelta(minutes=11), ("longform/survival-experiment.html",)),
                lane.CommitTouch(now - timedelta(minutes=24), ("playbook/index.html", "ops/improvements.md")),
                lane.CommitTouch(now - timedelta(minutes=44), ("longform/survival-experiment.html",)),
            )
            asks = (
                lane.BridgeAsk(
                    now - timedelta(minutes=15),
                    "claude",
                    "@leon show hn account unlock ask is pending",
                ),
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                now,
                commits,
                asks,
                now - timedelta(minutes=8),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "channel_poverty_audit")
        self.assertIn("Recent Leon channel-unlock ask", suggestion.reason)
        self.assertIn("Farcaster cooldown remains active", suggestion.reason)
        self.assertIn("Do not send another Leon account-unlock ask", suggestion.next_steps[0])

    def test_load_recent_bridge_unlock_asks_filters_non_unlock_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "messages.db"
            now = datetime(2026, 5, 2, 10, 15, tzinfo=UTC)
            con = sqlite3.connect(db)
            con.execute(
                """
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    ts TEXT,
                    from_agent TEXT,
                    to_agent TEXT,
                    body TEXT,
                    read INTEGER
                )
                """
            )
            con.execute(
                "INSERT INTO messages (ts, from_agent, to_agent, body, read) VALUES (?, ?, ?, ?, 1)",
                (
                    (now - timedelta(minutes=16)).isoformat(),
                    "claude",
                    "leon",
                    "Wil je 1x Show HN submit doen? HN account unlock is gated.",
                ),
            )
            con.execute(
                "INSERT INTO messages (ts, from_agent, to_agent, body, read) VALUES (?, ?, ?, ?, 1)",
                (
                    (now - timedelta(minutes=10)).isoformat(),
                    "codex",
                    "leon",
                    "status: tests passed, no action needed.",
                ),
            )
            con.commit()
            con.close()

            asks = lane.load_recent_bridge_unlock_asks(db, now)

        self.assertEqual(len(asks), 1)
        self.assertEqual(asks[0].from_agent, "claude")
        self.assertIn("Show HN", asks[0].excerpt)

    def test_routes_to_devto_when_engagement_snapshot_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-0839.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0839.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-0855.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-0855.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0900.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 9, 17, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "devto_engagement_pull")

    def test_routes_to_no_inventory_when_signal_check_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-0839.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-leads-2026-05-02-codex-0855.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-0700.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 9, 17, tzinfo=UTC),
            )

        self.assertEqual(suggestion.decision, "no_inventory_signal_check")

    def test_deadline_passed_overrides_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ops = root / "ops"
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                [],
                ops,
                datetime(2026, 5, 3, 21, 37, tzinfo=UTC),
            )

        self.assertEqual(suggestion.decision, "park_or_scale_no_inventory_lane")


if __name__ == "__main__":
    unittest.main()
