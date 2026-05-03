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

    def test_extract_comment_id_for_needle_finds_self_visible_comment(self) -> None:
        html = """
        <tr class="athing comtr" id="47994996"><td>
          <a href="user?id=dutchaiagents" class="hnuser">dutchaiagents</a>
          <div class="commtext c00">Since Enoch is generating research artifacts,
          I would treat the pass/fail criteria as a first-class output.</div>
        </td></tr>
        """

        comment_id = hn_browser.extract_comment_id_for_needle(
            html,
            "dutchaiagents",
            "Since Enoch is generating research artifacts",
        )

        self.assertEqual(comment_id, "47994996")

    def test_extract_comment_id_for_needle_unescapes_html_entities(self) -> None:
        html = """
        <tr class="athing comtr" id="123"><td>
          <a href="user?id=dutchaiagents" class="hnuser">dutchaiagents</a>
          <div class="commtext c00">I&#x27;d persist failed candidates too.</div>
        </td></tr>
        """

        comment_id = hn_browser.extract_comment_id_for_needle(
            html,
            "dutchaiagents",
            "I'd persist failed candidates",
        )

        self.assertEqual(comment_id, "123")

    def test_extract_comment_id_for_needle_ignores_other_users(self) -> None:
        html = """
        <tr class="athing comtr" id="123"><td>
          <a href="user?id=someoneelse" class="hnuser">someoneelse</a>
          <div class="commtext c00">Since Enoch is generating research artifacts</div>
        </td></tr>
        """

        self.assertIsNone(
            hn_browser.extract_comment_id_for_needle(
                html,
                "dutchaiagents",
                "Since Enoch is generating research artifacts",
            )
        )

    def test_hn_item_public_status_detects_visible_comment(self) -> None:
        payload = {
            "by": "dutchaiagents",
            "id": 47994996,
            "parent": 47994468,
            "text": "real text",
            "type": "comment",
        }

        self.assertEqual(hn_browser.hn_item_public_status(payload), "visible")

    def test_hn_item_public_status_detects_dead_and_deleted_comments(self) -> None:
        self.assertEqual(hn_browser.hn_item_public_status({"dead": True}), "dead")
        self.assertEqual(hn_browser.hn_item_public_status({"deleted": True}), "deleted")
        self.assertEqual(hn_browser.hn_item_public_status({"text": "[flagged]"}), "dead")

    def test_hn_item_public_status_unknown_for_non_comment_payloads(self) -> None:
        self.assertEqual(hn_browser.hn_item_public_status(None), "unknown")
        self.assertEqual(hn_browser.hn_item_public_status({"type": "story"}), "unknown")

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
