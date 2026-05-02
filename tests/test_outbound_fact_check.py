import tempfile
import unittest
from pathlib import Path

from tools.outbound_fact_check import check_paths


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class OutboundFactCheckTests(unittest.TestCase):
    def test_current_hn_companion_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]

        findings = check_paths((root / "research/longform-survival-experiment-hn.md",))

        self.assertEqual(findings, [])

    def test_flags_stale_four_agent_budget_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            write(
                draft,
                """# Four AI agents on a $100 runway

Four autonomous coding agents share one wallet.
Compute costs 1.50 EUR/day.
Today: 115.89 USDC, about 77 days.
Six lukewarm casts produced no signal.
""",
            )

            findings = check_paths((draft,))

        self.assertEqual(
            [finding.code for finding in findings],
            [
                "stale_agent_count_title",
                "stale_agent_roster",
                "stale_daily_burn",
                "stale_wallet_balance",
                "stale_runway_days",
                "stale_cast_count",
            ],
        )

    def test_allows_historical_four_agent_context_without_stale_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            write(
                draft,
                "We started as four; gemini and grok dropped after a week.",
            )

            findings = check_paths((draft,))

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
