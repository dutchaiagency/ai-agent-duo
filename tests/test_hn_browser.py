import unittest

from ops import hn_browser


class HackerNewsBrowserSafetyTests(unittest.TestCase):
    def test_body_has_url_detects_http_and_www_links(self) -> None:
        self.assertTrue(hn_browser.body_has_url("read https://example.com/more"))
        self.assertTrue(hn_browser.body_has_url("read www.example.com/more"))
        self.assertFalse(hn_browser.body_has_url("plain technical comment with no link"))

    def test_extract_karma_from_user_html(self) -> None:
        html = '<tr><td valign="top">karma:</td><td>17</td></tr>'

        self.assertEqual(hn_browser.extract_karma_from_user_html(html), 17)

    def test_link_free_comment_is_never_blocked_for_low_karma(self) -> None:
        reason = hn_browser.low_karma_link_block_reason(
            "Concrete technical reply with no outbound link.",
            karma=1,
            min_link_karma=5,
        )

        self.assertIsNone(reason)

    def test_url_comment_blocks_when_karma_is_too_low(self) -> None:
        reason = hn_browser.low_karma_link_block_reason(
            "More detail: https://dutchaiagency.github.io/ai-agent-duo/",
            karma=1,
            min_link_karma=5,
        )

        self.assertIn("karma is 1", reason or "")

    def test_url_comment_blocks_when_karma_cannot_be_verified(self) -> None:
        reason = hn_browser.low_karma_link_block_reason(
            "More detail: https://dutchaiagency.github.io/ai-agent-duo/",
            karma=None,
            min_link_karma=5,
        )

        self.assertIn("could not be verified", reason or "")

    def test_url_comment_allowed_at_threshold(self) -> None:
        reason = hn_browser.low_karma_link_block_reason(
            "More detail: https://dutchaiagency.github.io/ai-agent-duo/",
            karma=5,
            min_link_karma=5,
        )

        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
