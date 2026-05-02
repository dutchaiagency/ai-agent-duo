#!/usr/bin/env python3
"""List repo files without recursively walking ignored dependency trees."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_GENERATED_DIRS = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".secrets",
        "__pycache__",
        "dist",
        "node_modules",
        "tmp",
    }
)


@dataclass(frozen=True)
class InventoryResult:
    paths: list[str]
    total_before_limit: int


def parse_nul_paths(payload: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="replace").replace("\\", "/")
        for item in payload.split(b"\0")
        if item
    ]


def has_generated_component(path: str, generated_dirs: frozenset[str]) -> bool:
    return any(part in generated_dirs for part in path.replace("\\", "/").split("/"))


def matches_root(path: str, roots: list[str]) -> bool:
    if not roots:
        return True
    normalized = path.replace("\\", "/")
    for root in roots:
        clean = root.strip("/").replace("\\", "/")
        if normalized == clean or normalized.startswith(clean + "/"):
            return True
    return False


def filter_paths(
    paths: list[str],
    *,
    roots: list[str] | None = None,
    include_generated: bool = False,
    limit: int | None = None,
    generated_dirs: frozenset[str] = DEFAULT_GENERATED_DIRS,
) -> InventoryResult:
    roots = roots or []
    filtered: list[str] = []
    for path in sorted(dict.fromkeys(paths)):
        if not matches_root(path, roots):
            continue
        if not include_generated and has_generated_component(path, generated_dirs):
            continue
        filtered.append(path)

    total = len(filtered)
    if limit is not None:
        filtered = filtered[: max(limit, 0)]
    return InventoryResult(paths=filtered, total_before_limit=total)


def git_file_list(repo: Path) -> list[str]:
    command = ["git", "-C", str(repo), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "git ls-files failed")
    return parse_nul_paths(completed.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Limit output to a repo-relative path prefix. Repeatable.",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Do not filter generated/cache directory components.",
    )
    parser.add_argument("--limit", type=int, help="Maximum paths to print.")
    parser.add_argument("--json", action="store_true", help="Print JSON with metadata.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = git_file_list(args.repo)
    except (OSError, RuntimeError) as exc:
        print(f"repo-file-inventory: {exc}", file=sys.stderr)
        return 2

    result = filter_paths(
        paths,
        roots=args.root,
        include_generated=args.include_generated,
        limit=args.limit,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "count": len(result.paths),
                    "total_before_limit": result.total_before_limit,
                    "paths": result.paths,
                },
                indent=2,
            )
        )
    else:
        for path in result.paths:
            print(path)
        if args.limit is not None and result.total_before_limit > len(result.paths):
            hidden = result.total_before_limit - len(result.paths)
            print(f"# ... {hidden} more paths hidden by --limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
