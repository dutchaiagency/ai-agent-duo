import unittest

from ops.farcaster_feed_read import (
    absolute_farcaster_url,
    cast_hash_from_id,
    permalink_from_hrefs,
    summarize_text,
    target_url,
)


class FarcasterFeedReadUnitTests(unittest.TestCase):
    def test_target_url_defaults_to_channel(self) -> None:
        self.assertEqual(target_url("devs"), "https://farcaster.xyz/~/channel/devs")

    def test_target_url_accepts_full_channel_url(self) -> None:
        self.assertEqual(
            target_url("https://farcaster.xyz/~/channel/dev"),
            "https://farcaster.xyz/~/channel/dev",
        )

    def test_target_url_accepts_channel_path(self) -> None:
        self.assertEqual(target_url("/~/channel/founders"), "https://farcaster.xyz/~/channel/founders")

    def test_target_url_accepts_home_aliases(self) -> None:
        self.assertEqual(target_url("home"), "https://farcaster.xyz/~/feed")
        self.assertEqual(target_url("feed"), "https://farcaster.xyz/~/feed")
        self.assertEqual(target_url("https://farcaster.xyz/~/feed"), "https://farcaster.xyz/~/feed")

    def test_target_url_rejects_non_farcaster_url(self) -> None:
        with self.assertRaises(ValueError):
            target_url("https://example.com/~/channel/dev")

    def test_absolute_farcaster_url_keeps_only_farcaster_links(self) -> None:
        self.assertEqual(absolute_farcaster_url("/alice/0x12345678"), "https://farcaster.xyz/alice/0x12345678")
        self.assertEqual(absolute_farcaster_url("https://farcaster.xyz/alice/0x12345678"), "https://farcaster.xyz/alice/0x12345678")
        self.assertIsNone(absolute_farcaster_url("https://example.com"))

    def test_cast_hash_from_dom_id(self) -> None:
        self.assertEqual(cast_hash_from_id("cast:0xabcdef123456"), "0xabcdef123456")
        self.assertIsNone(cast_hash_from_id("profile:0xabcdef123456"))

    def test_permalink_prefers_matching_short_hash(self) -> None:
        link = permalink_from_hrefs(
            "0xabcdef1234567890",
            ["/bob/0xdeadbeef", "/alice/0xabcdef12"],
        )

        self.assertEqual(link, "https://farcaster.xyz/alice/0xabcdef12")

    def test_permalink_falls_back_to_first_cast_link(self) -> None:
        link = permalink_from_hrefs("0x111111112222", ["/alice", "/bob/0xdeadbeef"])

        self.assertEqual(link, "https://farcaster.xyz/bob/0xdeadbeef")

    def test_summarize_text_collapses_whitespace(self) -> None:
        self.assertEqual(summarize_text("alice\n\nhello   world", max_chars=80), "alice hello world")
        self.assertEqual(summarize_text("a" * 20, max_chars=10), "aaaaaaa...")


if __name__ == "__main__":
    unittest.main()
