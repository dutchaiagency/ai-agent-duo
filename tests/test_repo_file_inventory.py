import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.repo_file_inventory import (
    filter_paths,
    git_file_list,
    has_generated_component,
    parse_nul_paths,
)


class RepoFileInventoryTests(unittest.TestCase):
    def test_parse_nul_paths_normalizes_windows_separators(self) -> None:
        paths = parse_nul_paths(b"tools\\a.py\0README.md\0")

        self.assertEqual(paths, ["tools/a.py", "README.md"])

    def test_generated_component_filter_is_component_based(self) -> None:
        self.assertTrue(has_generated_component("pkg/node_modules/lib.js", frozenset({"node_modules"})))
        self.assertFalse(has_generated_component("docs/node_modules-notes.md", frozenset({"node_modules"})))

    def test_filter_paths_deduplicates_sorts_roots_and_limits(self) -> None:
        result = filter_paths(
            [
                "tools/b.py",
                "README.md",
                "tools/a.py",
                "tools/a.py",
                "tools/node_modules/x.js",
                "tests/test_a.py",
            ],
            roots=["tools"],
            limit=1,
        )

        self.assertEqual(result.paths, ["tools/a.py"])
        self.assertEqual(result.total_before_limit, 2)

    def test_git_file_list_respects_exclude_standard(self) -> None:
        with TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            (repo / "notes.md").write_text("notes\n", encoding="utf-8")
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "dep.js").write_text("dep\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".gitignore", "tracked.txt"],
                cwd=repo,
                check=True,
                capture_output=True,
            )

            paths = git_file_list(repo)

        self.assertIn(".gitignore", paths)
        self.assertIn("tracked.txt", paths)
        self.assertIn("notes.md", paths)
        self.assertNotIn("node_modules/dep.js", paths)


if __name__ == "__main__":
    unittest.main()
