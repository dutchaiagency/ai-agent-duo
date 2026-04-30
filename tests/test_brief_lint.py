import unittest

from tools.brief_lint import (
    detect_budget_amounts,
    github_annotation,
    lint,
    Finding,
)


VALID_BRIEF = """
# Task Brief

## Goal

Fix the CSV import script so rows with empty optional columns are accepted.

## Context and links

- Repository: https://github.com/example/project
- Failing command: `python scripts/import_customers.py samples/customers.csv`

## Done criteria

- Empty optional columns no longer crash the importer.
- Add or update a targeted test for the edge case.

## Deadline

2026-05-02

## Budget

USDC 60
"""


class BriefLintTests(unittest.TestCase):
    def test_valid_brief_accepts_currency_before_amount(self) -> None:
        findings = lint(VALID_BRIEF, min_budget_usdc=25)

        self.assertEqual([finding.code for finding in findings], ["ok"])

    def test_missing_required_signals_fail(self) -> None:
        findings = lint("Please help soon.", min_budget_usdc=25)

        self.assertIn("brief_too_short", [finding.code for finding in findings])
        self.assertTrue(any(finding.level == "fail" for finding in findings))

    def test_detects_common_platform_tokens(self) -> None:
        brief = VALID_BRIEF + "\napi key: ghp_abcdefghijklmnopqrstuvwxyz1234567890\n"

        findings = lint(brief, min_budget_usdc=25)

        self.assertIn("possible_secret", [finding.code for finding in findings])

    def test_budget_amount_variants(self) -> None:
        self.assertEqual(detect_budget_amounts("Budget: 25 USDC"), [25.0])
        self.assertEqual(detect_budget_amounts("Budget: USDC 60"), [60.0])
        self.assertEqual(detect_budget_amounts("Budget: €120"), [120.0])

    def test_github_annotation_escapes_message_and_path(self) -> None:
        annotation = github_annotation(
            Finding("warn", "missing_url", "Use repo link, docs, or sample\nfile."),
            "briefs/task,one.md",
        )

        self.assertEqual(
            annotation,
            "::warning file=briefs/task%2Cone.md,title=missing_url::Use repo link, docs, or sample%0Afile.",
        )


if __name__ == "__main__":
    unittest.main()
