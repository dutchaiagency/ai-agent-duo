"""Regression tests for proton_inbox state-file classification in the heartbeat router.

Kept in a separate module from test_heartbeat_lane_suggest.py so the proton-inbox
classifier has its own discoverable surface (the parent suite already has 30+
classification cases and is locked-down by other agents in parallel).
"""

import tempfile
import unittest
from pathlib import Path

from tools import heartbeat_lane_suggest as lane


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ProtonInboxClassificationTests(unittest.TestCase):
    def test_empty_inbox_scan_is_zero_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "proton-inbox-scan-2026-05-02-claude-1525.md"
            write(path, "Result: zero unread, empty inbox today.\n")
            event = lane.classify_event(path)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "proton_inbox")
        self.assertTrue(event.zero_signal)

    def test_inbox_with_unread_item_is_nonzero_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "proton-inbox-scan-2026-05-02-claude-1600.md"
            write(path, "Result: 1 unread message from buyer at example.com\n")
            event = lane.classify_event(path)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.kind, "proton_inbox")
        self.assertFalse(event.zero_signal)

    def test_proton_inbox_event_appears_in_latest_events_summary(self) -> None:
        from datetime import UTC, datetime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            ops = root / "ops"
            now = datetime(2026, 5, 2, 16, 0, tzinfo=UTC)
            write(
                state / "proton-inbox-scan-2026-05-02-claude-1525.md",
                "Result: zero unread.\n",
            )
            events = lane.load_events(state)
            suggestion = lane.suggest_next_action(events, ops, now)

        kinds = [event.kind for event in suggestion.latest_events]
        self.assertIn("proton_inbox", kinds)


if __name__ == "__main__":
    unittest.main()
