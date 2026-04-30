import unittest
from urllib.parse import parse_qs, urlsplit

from tools.intake_link import build_intake_url, normalize_source, source_for_github_lead


class IntakeLinkTests(unittest.TestCase):
    def query(self, url: str) -> dict[str, list[str]]:
        return parse_qs(urlsplit(url).query)

    def test_normalizes_source_for_url_fields(self) -> None:
        self.assertEqual(
            normalize_source("GitHub outbound: OpenPanel-dev/openpanel #356"),
            "github-outbound-openpanel-dev-openpanel-356",
        )

    def test_builds_prefilled_issue_intake_url(self) -> None:
        url = build_intake_url("github-outbound-openpanel-356-2026-04-30")

        query = self.query(url)
        self.assertEqual(query["template"], ["task-request.yml"])
        self.assertEqual(
            query["source"], ["github-outbound-openpanel-356-2026-04-30"]
        )

    def test_builds_site_url_for_longform_or_dm_anchor(self) -> None:
        url = build_intake_url("devto-longform-2026-04-30", target="site")

        self.assertEqual(
            url,
            "https://dutchaiagency.github.io/ai-agent-duo/?source=devto-longform-2026-04-30",
        )

    def test_github_lead_source_includes_repo_issue_and_date(self) -> None:
        self.assertEqual(
            source_for_github_lead("Openpanel-dev/openpanel", 356, day="2026-04-30"),
            "github-outbound-openpanel-dev-openpanel-356-2026-04-30",
        )

    def test_rejects_empty_source(self) -> None:
        with self.assertRaises(ValueError):
            normalize_source("///")


if __name__ == "__main__":
    unittest.main()
