"""Regression tests for Pages traffic in the heartbeat router signal summary."""

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import heartbeat_lane_suggest as lane


class PagesTrafficSignalTests(unittest.TestCase):
    def test_low_pages_traffic_snapshot_is_zero_signal_latest_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 5, 2, 16, 0, tzinfo=UTC)
            snapshot = lane.PageTrafficSnapshot(
                root / "state" / "pages-traffic-2026-05-02-codex-1555.md",
                now - timedelta(minutes=5),
                7,
                210,
                (
                    lane.PageTraffic("index", "Home", 1, "ok"),
                    lane.PageTraffic("writing", "Writing index", None, "missing"),
                ),
            )

            suggestion = lane.suggest_next_action(
                [],
                root / "ops",
                now,
                pages_traffic=snapshot,
            )

        events = [event for event in suggestion.latest_events if event.kind == "pages_traffic"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].zero_signal)

    def test_above_baseline_pages_traffic_snapshot_is_nonzero_signal(self) -> None:
        now = datetime(2026, 5, 2, 16, 0, tzinfo=UTC)
        snapshot = lane.PageTrafficSnapshot(
            Path("state/pages-traffic-2026-05-02-codex-1555.md"),
            now - timedelta(minutes=5),
            7,
            210,
            (lane.PageTraffic("playbook", "Playbook", 211, "ok"),),
        )

        event = lane.pages_traffic_event(snapshot)

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "pages_traffic")
        self.assertFalse(event.zero_signal)


if __name__ == "__main__":
    unittest.main()
