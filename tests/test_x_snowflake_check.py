import unittest
from datetime import UTC, date, datetime

from tools.x_snowflake_check import (
    decode_snowflake_utc,
    extract_status_id,
    has_modern_status_id_length,
    has_synthetic_digit_pattern,
    in_window,
    looks_like_real_snowflake,
)


class XSnowflakeCheckTests(unittest.TestCase):
    def test_extracts_status_id_from_x_url(self) -> None:
        self.assertEqual(
            extract_status_id("https://x.com/SherlockDefi/status/1789456123789456123"),
            1789456123789456123,
        )

    def test_decodes_claimed_grok_id_to_2024_not_2026(self) -> None:
        created_at = decode_snowflake_utc(1789456123789456123)

        self.assertEqual(created_at.date(), date(2024, 5, 12))

    def test_window_check_rejects_stale_id(self) -> None:
        created_at = datetime(2024, 5, 12, tzinfo=UTC)

        self.assertFalse(
            in_window(created_at, after=date(2026, 4, 30), before=date(2026, 4, 30))
        )

    def test_flags_sequential_handwritten_pattern(self) -> None:
        self.assertTrue(has_synthetic_digit_pattern(1785678901234567890))

    def test_allows_non_patterned_numeric_id(self) -> None:
        self.assertFalse(has_synthetic_digit_pattern(1917216837462059184))

    def test_flags_non_modern_status_id_length(self) -> None:
        self.assertFalse(has_modern_status_id_length(12345))

        ok, reason = looks_like_real_snowflake(12345)

        self.assertFalse(ok)
        self.assertEqual(reason, "wrong_length")

    def test_full_gate_allows_recent_non_synthetic_id(self) -> None:
        ok, reason = looks_like_real_snowflake(
            1917216837462059184,
            after=date(2025, 4, 1),
            before=date(2025, 5, 31),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_rejects_non_numeric_id(self) -> None:
        with self.assertRaises(ValueError):
            extract_status_id("https://x.com/example/status/not-real")


if __name__ == "__main__":
    unittest.main()
