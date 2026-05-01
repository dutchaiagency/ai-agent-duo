import unittest

from ops.gumroad_login import (
    MAX_GUMROAD_TITLE_CHARS,
    build_product_payload,
    public_listing_markdown,
)


class GumroadListingTests(unittest.TestCase):
    def test_public_listing_cutoff_excludes_internal_ops_notes(self) -> None:
        public = public_listing_markdown()

        self.assertIn("## Long description", public)
        self.assertNotIn("INTERNAL ONLY", public)
        self.assertNotIn("Distribution checklist", public)

    def test_product_payload_is_ready_for_dry_run_publish(self) -> None:
        payload = build_product_payload()

        self.assertEqual(payload["errors"], [])
        self.assertLessEqual(payload["title_chars"], MAX_GUMROAD_TITLE_CHARS)
        self.assertEqual(payload["price_cents"], 900)
        self.assertEqual(payload["asset_path"], "products\\agent-playbook\\playbook.pdf")
        self.assertGreater(payload["asset_bytes"], 0)
        self.assertIn("ai-agents", payload["tags"])

    def test_description_uses_public_facing_long_description_only(self) -> None:
        payload = build_product_payload()
        description = payload["description_markdown"]

        self.assertIn("About the source", description)
        self.assertIn("raw markdown", description)
        self.assertNotIn("Status: draft", description)
        self.assertNotIn("KYC step", description)
        self.assertNotIn("Distribution checklist", description)


if __name__ == "__main__":
    unittest.main()
