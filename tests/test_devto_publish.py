import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from ops import devto_publish


def write_draft(path: Path, body: str) -> None:
    path.write_text(
        f"""---
title: Dev.to update
tags: ai, agents
---
{body}
""",
        encoding="utf-8",
    )


class DevtoPublishTests(unittest.TestCase):
    def test_factcheck_blocks_stale_source_before_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            write_draft(draft, "# Four AI agents on a $100 runway\n")

            stderr = StringIO()
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    devto_publish.main(["--file", str(draft), "--dry-run"])

        self.assertIn("outbound fact-check failed", str(raised.exception))
        self.assertIn("stale_agent_count_title", stderr.getvalue())

    def test_no_factcheck_allows_explicit_bypass_for_update_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            write_draft(draft, "# Four AI agents on a $100 runway\n")

            stdout = StringIO()
            with redirect_stdout(stdout):
                rc = devto_publish.main(
                    [
                        "--file",
                        str(draft),
                        "--article-id",
                        "123",
                        "--dry-run",
                        "--no-factcheck",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(payload["_request"]["method"], "PUT")
        self.assertEqual(payload["_request"]["url"], "https://dev.to/api/articles/123")

    def test_rejects_tool_call_closing_tag_artifacts_before_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            write_draft(draft, "body " + "</" + "content>" + "\n")

            with self.assertRaises(SystemExit) as raised:
                devto_publish.main(["--file", str(draft), "--dry-run", "--no-factcheck"])

        self.assertIn("REFUSE: Suspicious escape marker", str(raised.exception))
        self.assertIn("dev.to body", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
