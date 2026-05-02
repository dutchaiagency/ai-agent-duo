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
    def test_routes_to_comment_pack_when_launch_window_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 13, 20, tzinfo=UTC)
            write(
                state / "hn-launch-window-active-2026-05-02-codex-1310.md",
                "Status: active\nURL: https://news.ycombinator.com/item?id=123456\n",
            )

            active_launch = lane.load_active_launch_window(state, now)
            suggestion = lane.suggest_next_action(
                [],
                ops,
                now,
                active_launch=active_launch,
            )

        self.assertIsNotNone(active_launch)
        self.assertEqual(suggestion.decision, "post_launch_window_active")
        self.assertIn("research/hn-launch-comment-pack.md", suggestion.next_steps[2])
        self.assertIn("news.ycombinator.com/item?id=123456", suggestion.reason)

    def test_launch_window_marker_expires_after_response_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            write(
                state / "hn-launch-window-active-2026-05-02-codex-1310.md",
                "Status: active\nURL: https://news.ycombinator.com/item?id=123456\n",
            )

            active_launch = lane.load_active_launch_window(
                state,
                datetime(2026, 5, 2, 14, 41, tzinfo=UTC),
            )

        self.assertIsNone(active_launch)

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

    def test_fresh_productized_review_routes_to_distribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1230.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1230.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1218.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "archestra-bounty-label-watch-2026-05-02-codex-1154.md",
                "watch/hold: 0 trigger candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1221.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                state / "productized-asset-review-2026-05-02-codex-1246.md",
                "Result: productized review shipped; next useful move is distribution.",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 12, 47, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "outbound_traffic_generation")
        self.assertIn("productized/service artifact review just shipped", suggestion.reason)

    def test_fresh_zero_scan_pair_avoids_duplicate_github_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1116.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1116.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1034.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "algora-bounty-check-twenty-2026-05-02-codex-0835.md",
                "zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1022.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 11, 20, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "devto_engagement_pull")
        self.assertIn("Latest GitHub reply+lead scan pair", suggestion.reason)

    def test_future_state_files_are_ignored_for_past_now_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1259.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1259.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-1346.md",
                "Fresh future file that should not affect a 13:43 router run.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1346.md",
                "| State | Lead |\n| --- | --- |\n| reply | future/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1218.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "archestra-bounty-label-watch-2026-05-02-codex-1154.md",
                "watch/hold: zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1336.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                state / "productized-asset-review-2026-05-02-codex-1246.md",
                "Result: productized review shipped; next useful move is distribution.",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 13, 43, tzinfo=UTC),
                last_farcaster_reply_at=datetime(2026, 5, 2, 13, 40, tzinfo=UTC),
            )

        self.assertEqual(suggestion.decision, "farcaster_reply_observe")
        self.assertNotIn("future/repo", suggestion.reason)

    def test_fresh_archestra_candidate_report_routes_to_bounty_triage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1116.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1116.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1034.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "archestra-bounty-label-watch-2026-05-02-codex-1120.md",
                "Fresh-slot trigger: #3796\n| candidate | $200 | #3796 | no | - |",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1110.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 11, 25, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "bounty_candidate_triage")
        self.assertIn("Archestra label-watch", suggestion.reason)
        self.assertIn("archestra.ai/contributor-onboard", suggestion.next_steps[3])

    def test_fresh_github_priority_scan_routes_to_priority_gate_triage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1410.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1410.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1350.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "github-bounty-priority-scan-2026-05-02-codex-1412.md",
                (
                    "Higher-than-low candidates: 2\n"
                    "Result: priority candidates present; triage priority before topic fit."
                ),
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1400.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 14, 15, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "priority_bounty_gate_triage")
        self.assertIn("priority before topic fit", suggestion.reason)
        self.assertIn("human-review gates", suggestion.next_steps[2])

    def test_low_only_github_priority_scan_is_zero_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "github-bounty-priority-scan-2026-05-02-codex-1412.md"
            write(
                path,
                "Result: zero higher-than-low candidates; low/unprioritized bounty work is watch/hold.",
            )

            event = lane.classify_event(path)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertTrue(event.zero_signal)

    def test_midnight_followup_is_classified_as_zero_bounty_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "state"
                / "midnight-bounty-followup-2026-05-02-claude-1505.md"
            )
            write(
                path,
                (
                    "## Decision: no compete-bump comment\n\n"
                    "No maintainer review in 3 days. Treat as deferred-pipeline.\n"
                ),
            )

            event = lane.classify_event(path)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "bounty")
        self.assertTrue(event.zero_signal)

    def test_midnight_followup_delays_stale_bounty_refetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 18, 30, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-1810.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1810.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "github-leads-2026-05-02-codex-1818.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1818.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1805.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1404.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "midnight-bounty-followup-2026-05-02-claude-1505.md",
                (
                    "## Decision: no compete-bump comment\n\n"
                    "No maintainer review in 3 days. Treat as deferred-pipeline.\n"
                ),
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1800.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            events = lane.load_events(state)
            latest_bounty = [event for event in events if event.kind == "bounty"][-1]
            suggestion = lane.suggest_next_action(events, ops, now)

        self.assertEqual(
            latest_bounty.path.name,
            "midnight-bounty-followup-2026-05-02-claude-1505.md",
        )
        self.assertTrue(suggestion.cooldown.active)
        self.assertNotEqual(suggestion.decision, "stale_bounty_refetch")
        self.assertEqual(suggestion.decision, "funnel_or_productized_asset_review")

    def test_priority_triage_zero_blocks_repeat_priority_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1410.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1410.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1411.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "github-bounty-priority-scan-2026-05-02-codex-1412.md",
                "Result: priority candidates present; triage priority before topic fit.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1418.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1415.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 14, 20, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "funnel_or_productized_asset_review")
        self.assertNotEqual(suggestion.decision, "priority_bounty_gate_triage")

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

    def test_no_inventory_zero_words_are_classified_as_zero_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "state"
                / "no-inventory-bridge-kit-signal-check-2026-05-02-claude-1350.md"
            )
            write(
                path,
                "Same as 12:18 UTC: zero reservation issues, zero unread mail. Keep the distribution hold.",
            )

            event = lane.classify_event(path)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertTrue(event.zero_signal)

    def test_founders_engagement_scout_is_classified_as_zero_signal_channel_scout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "state"
                / "founders-engagement-scout-2026-05-02-claude-1442.md"
            )
            write(
                path,
                "Outbound-engagement scout, no public reply posted.\n\n## Decision: no reply this wake\n",
            )

            event = lane.classify_event(path)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "channel_scout")
        self.assertTrue(event.zero_signal)

    def test_channel_poverty_audit_no_public_outbound_is_zero_signal_channel_scout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = (
                Path(tmp)
                / "state"
                / "channel-poverty-audit-2026-05-02-claude-1458.md"
            )
            write(
                path,
                "No public outbound, no Farcaster cast/reply, no Leon ping issued from this slot.",
            )

            event = lane.classify_event(path)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "channel_scout")
        self.assertTrue(event.zero_signal)

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

    def test_recent_zero_channel_scout_suppresses_duplicate_channel_poverty_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 14, 56, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-1430.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1430.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-claude-1350.md",
                "zero reservation issues, zero unread mail. Keep the distribution hold.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1404.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1423.md",
                (
                    "Total reactions: 0\nTotal comments: 0\n\n"
                    "| Post | Published | Reactions | Comments | URL |\n"
                    "|---|---:|---:|---:|---|\n"
                    "| Old post | 2026-05-01T12:26:45Z | 0 | 0 | https://dev.to/example |\n"
                ),
            )
            write(
                state / "productized-asset-review-2026-05-02-codex-1439.md",
                "Result: productized review shipped; next useful move is distribution.",
            )
            write(
                state / "founders-engagement-scout-2026-05-02-claude-1442.md",
                "Outbound-engagement scout, no public reply posted.\n\n## Decision: no reply this wake\n",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            asks = (
                lane.BridgeAsk(
                    now - timedelta(minutes=20),
                    "claude",
                    "@leon show hn account unlock ask is pending",
                ),
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                now,
                recent_unlock_asks=asks,
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "nonpublic_delivery_or_signal_work")
        self.assertIn("Recent Leon channel-unlock ask", suggestion.reason)
        self.assertIn("recent channel scout already found no qualified public action", suggestion.reason)
        self.assertIn("Do not repeat the channel-poverty", suggestion.next_steps[0])

    def test_recent_channel_poverty_audit_suppresses_duplicate_even_as_delta_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 14, 59, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-1430.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1430.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-claude-1350.md",
                "zero reservation issues, zero unread mail. Keep the distribution hold.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1404.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1423.md",
                (
                    "Total reactions: 0\nTotal comments: 0\n\n"
                    "| Post | Published | Reactions | Comments | URL |\n"
                    "|---|---:|---:|---:|---|\n"
                    "| Old post | 2026-05-01T12:26:45Z | 0 | 0 | https://dev.to/example |\n"
                ),
            )
            write(
                state / "productized-asset-review-2026-05-02-codex-1439.md",
                "Result: productized review shipped; next useful move is distribution.",
            )
            write(
                state / "channel-poverty-audit-2026-05-02-claude-1458.md",
                (
                    "Delta refresh of the channel state.\n"
                    "Next-cycle action = fresh target scout requiring parent >20 likes or >5 replies.\n"
                ),
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            asks = (
                lane.BridgeAsk(
                    now - timedelta(hours=5),
                    "claude",
                    "@leon show hn account unlock ask is pending",
                ),
            )

            events = lane.load_events(state)
            audit_event = [event for event in events if event.kind == "channel_scout"][-1]
            suggestion = lane.suggest_next_action(
                events,
                ops,
                now,
                recent_unlock_asks=asks,
            )

        self.assertFalse(audit_event.zero_signal)
        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "nonpublic_delivery_or_signal_work")
        self.assertIn("channel-poverty audit already refreshed channel state", suggestion.reason)
        self.assertIn("Do not repeat the channel-poverty", suggestion.next_steps[0])

    def test_recent_farcaster_reply_routes_to_observe_before_more_channel_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 13, 43, tzinfo=UTC)
            write(
                state / "github-leads-2026-05-02-codex-1259.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1259.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1218.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "archestra-bounty-label-watch-2026-05-02-codex-1154.md",
                "watch/hold: zero immediate candidates.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1336.md",
                "Total reactions: 0\nTotal comments: 0\n",
            )
            write(
                state / "productized-asset-review-2026-05-02-codex-1246.md",
                "Result: productized review shipped; next useful move is distribution.",
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )
            asks = (
                lane.BridgeAsk(
                    now - timedelta(minutes=20),
                    "claude",
                    "@leon show hn account unlock ask is pending",
                ),
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                now,
                recent_unlock_asks=asks,
                last_farcaster_reply_at=now - timedelta(minutes=5),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "farcaster_reply_observe")
        self.assertIn("Farcaster outbound reply was logged", suggestion.reason)
        self.assertIn("Do not post another Farcaster reply", suggestion.next_steps[0])

    def test_last_successful_farcaster_reply_time_reads_reply_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "farcaster_reply_log.md"
            write(
                path,
                "\n".join(
                    (
                        "2026-05-02T13:10Z | claude | reply -> https://farcaster.xyz/a/0x1 | ok... | failed | reason: stale composer",
                        "2026-05-02T13:40Z | claude | reply -> https://farcaster.xyz/lthibault/0xd5413ad4 | Real gap... | success | reason: value-add",
                    )
                ),
            )

            result = lane.last_successful_farcaster_reply_time(path)

        self.assertEqual(result, datetime(2026, 5, 2, 13, 40, tzinfo=UTC))

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
            con.execute(
                "INSERT INTO messages (ts, from_agent, to_agent, body, read) VALUES (?, ?, ?, ?, 1)",
                (
                    (now - timedelta(minutes=5)).isoformat(),
                    "claude",
                    "leon",
                    (
                        "Payment-rail/KYC gate is a future bottleneck, not a live unlock. "
                        "Wil je dat ik harder push op outbound, product, of bounty?"
                    ),
                ),
            )
            con.commit()
            con.close()

            asks = lane.load_recent_bridge_unlock_asks(db, now)

        self.assertEqual(len(asks), 1)
        self.assertEqual(asks[0].from_agent, "claude")
        self.assertIn("Show HN", asks[0].excerpt)

    def test_channel_unlock_ask_requires_direct_request_segment(self) -> None:
        self.assertTrue(
            lane.is_channel_unlock_ask(
                "Wil je 1x Show HN submit doen? HN account unlock is gated."
            )
        )
        self.assertFalse(
            lane.is_channel_unlock_ask(
                (
                    "KYC rails would be negative EV if abused. "
                    "Wil je dat ik harder push op outbound, product, of bounty?"
                )
            )
        )

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

    def test_devto_zero_archive_snapshot_skips_passive_pull(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1446.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1446.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1450.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1454.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-1423.md",
                (
                    "Total reactions: 0\nTotal comments: 0\n\n"
                    "| Post | Published | Reactions | Comments | URL |\n"
                    "|---|---:|---:|---:|---|\n"
                    "| Old post | 2026-05-01T12:26:45Z | 0 | 0 | https://dev.to/example |\n"
                ),
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 15, 0, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "funnel_or_productized_asset_review")
        self.assertIn("SEO/archive-only", suggestion.reason)

    def test_devto_zero_archive_cooldown_expires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            write(
                state / "github-leads-2026-05-02-codex-1446.md",
                "No candidates passed the current filters.",
            )
            write(
                state / "github-replies-2026-05-02-codex-1446.md",
                "| State | Lead |\n| --- | --- |\n| waiting | example/repo #1 |",
            )
            write(
                state / "no-inventory-bridge-kit-signal-check-2026-05-02-codex-1450.md",
                "0 reservation issues, 0 unread emails, 0 matching reservation emails.",
            )
            write(
                state / "github-bounty-priority-triage-2026-05-02-codex-1454.md",
                "Result: no executable bounty candidate; publish/claim hold.",
            )
            write(
                state / "devto-engagement-2026-05-02-codex-0800.md",
                (
                    "Total reactions: 0\nTotal comments: 0\n\n"
                    "| Post | Published | Reactions | Comments | URL |\n"
                    "|---|---:|---:|---:|---|\n"
                    "| Old post | 2026-05-01T12:26:45Z | 0 | 0 | https://dev.to/example |\n"
                ),
            )
            write(
                ops / "no_inventory_validation_lane.md",
                "Kill or park by `2026-05-03T21:36Z`.",
            )

            suggestion = lane.suggest_next_action(
                lane.load_events(state),
                ops,
                datetime(2026, 5, 2, 15, 0, tzinfo=UTC),
            )

        self.assertTrue(suggestion.cooldown.active)
        self.assertEqual(suggestion.decision, "devto_engagement_pull")

    def test_github_reply_check_step_uses_timestamped_state_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suggestion = lane.suggest_next_action(
                [],
                Path(tmp) / "ops",
                datetime(2026, 5, 2, 13, 46, tzinfo=UTC),
            )

        self.assertEqual(suggestion.decision, "github_reply_check_then_lead_scan")
        self.assertIn("--state-dir state --agent codex", suggestion.next_steps[0])
        self.assertIn("--state-dir state --agent codex", suggestion.next_steps[1])

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
