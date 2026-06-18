"""Compact workspace-only inline tables in Cargo.toml files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence

PATTERN = re.compile(
    r"^(\s*)"
    r"([A-Za-z0-9_-]+)"
    r"\s*=\s*"
    r"\{\s*workspace\s*=\s*true\s*\}"
    r"\s*$"
)


def compact_line(line: str) -> str:
    """Return the compacted form of a Cargo dependency line."""
    match = PATTERN.match(line)
    if match is None:
        return line
    indent, name = match.group(1), match.group(2)
    return f"{indent}{name}.workspace = true\n"


def process_file(path: Path, *, dry_run: bool = False) -> int:
    """Compact workspace deps in a single file and return the change count."""
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    new_lines = [compact_line(line) for line in lines]
    changed = sum(left != right for left, right in zip(lines, new_lines))

    if changed and not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")

    return changed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Cargo.toml files to rewrite",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the workspace dependency compactor."""
    args = parse_args(argv)
    total = 0

    for path in args.paths:
        changed = process_file(path, dry_run=args.dry_run)
        if changed:
            tag = " (dry-run)" if args.dry_run else ""
            print(f"  {path}: {changed} line(s) compacted{tag}")
            total += changed

    if total:
        verb = "Would compact" if args.dry_run else "Compacted"
        print(f"\n{verb} {total} line(s) across {len(args.paths)} file(s).")
    else:
        print("Nothing to compact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
