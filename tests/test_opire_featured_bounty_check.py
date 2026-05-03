import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools import opire_featured_bounty_check as opire


def card(
    *,
    amount_cents: int = 20000,
    claimer_users: tuple[str, ...] = (),
    trying_users: tuple[str, ...] = (),
) -> opire.OpireCard:
    return opire.OpireCard(
        opire_id="01TEST",
        title="Fix payment webhook",
        github_url="https://github.com/acme/app/issues/42",
        repo="acme/app",
        number=42,
        amount_cents=amount_cents,
        unit="USD_CENT",
        languages=("TypeScript",),
        claimer_users=claimer_users,
        trying_users=trying_users,
        opire_url="https://app.opire.dev/issues/01TEST",
    )


def issue(
    *,
    state: str = "OPEN",
    assignees: tuple[str, ...] = (),
    comments_count: int = 2,
    work_intent_comments: int = 0,
    open_prs: tuple[opire.PullRequest, ...] = (),
) -> opire.GithubIssue:
    return opire.GithubIssue(
        repo="acme/app",
        number=42,
        state=state,
        title="Fix payment webhook",
        url="https://github.com/acme/app/issues/42",
        assignees=assignees,
        comments_count=comments_count,
        work_intent_comments=work_intent_comments,
        open_prs=open_prs,
    )


class OpireFeaturedBountyCheckTests(unittest.TestCase):
    def test_parse_featured_cards_from_next_flight_payload(self) -> None:
        payload = [
            "$",
            "section",
            None,
            {
                "children": [
                    [
                        "$",
                        "$L25",
                        None,
                        {
                            "featuredIssues": [
                                {
                                    "id": "01ABC",
                                    "title": "Helix keymap",
                                    "url": "https://github.com/zed-industries/zed/issues/4642",
                                    "programmingLanguages": ["Rust"],
                                    "pendingPrice": {"value": 30000, "unit": "USD_CENT"},
                                    "claimerUsers": [],
                                    "tryingUsers": [{"username": "builder"}],
                                }
                            ]
                        },
                    ]
                ]
            },
        ]
        encoded = json_escape("12:" + opire.json.dumps(payload))
        html = f'<script>self.__next_f.push([1,"{encoded}"])</script>'

        cards = opire.parse_featured_cards(html)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].repo, "zed-industries/zed")
        self.assertEqual(cards[0].number, 4642)
        self.assertEqual(cards[0].amount_dollars, 300)
        self.assertEqual(cards[0].trying_users, ("builder",))

    def test_classifies_closed_issue_as_skip(self) -> None:
        result = opire.classify_card(card(), issue(state="CLOSED"))

        self.assertEqual(result.decision, "skip")
        self.assertIn("closed", result.note)

    def test_classifies_claimed_or_trying_card_as_watch(self) -> None:
        result = opire.classify_card(
            card(claimer_users=("dev1",), trying_users=("dev2",)),
            issue(),
        )

        self.assertEqual(result.decision, "watch")
        self.assertIn("Opire claimer", result.note)
        self.assertIn("Opire trying", result.note)

    def test_classifies_clean_open_card_as_candidate(self) -> None:
        result = opire.classify_card(card(), issue())

        self.assertEqual(result.decision, "candidate")

    def test_zero_candidate_markdown_uses_router_zero_phrase(self) -> None:
        markdown = opire.render_markdown(
            [opire.classify_card(card(), issue(state="CLOSED"))],
            generated_at=datetime(2026, 5, 2, 16, 30, tzinfo=UTC),
        )

        self.assertIn("zero immediate candidates", markdown)

    def test_state_snapshot_path_is_heartbeat_parseable(self) -> None:
        path = opire.state_snapshot_path(
            Path("state"),
            "Codex Agent",
            datetime(2026, 5, 2, 16, 30, tzinfo=UTC),
        )

        self.assertEqual(
            path.as_posix(),
            "state/opire-featured-bounty-check-2026-05-02-codex-agent-1630.md",
        )


def json_escape(value: str) -> str:
    return opire.json.dumps(value)[1:-1]


if __name__ == "__main__":
    unittest.main()
