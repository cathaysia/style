"""Check source files against a maximum line count."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_MAX_LINES = 400


@dataclass(frozen=True)
class LineCountViolation:
    """A file that exceeds the configured line count."""

    path: Path
    line_count: int
    max_lines: int


def count_lines(path: Path) -> int:
    """Return the number of lines in path."""
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def check_paths(paths: Sequence[Path], *, max_lines: int) -> list[LineCountViolation]:
    """Return files that exceed max_lines."""
    violations = []
    for path in paths:
        if not path.is_file():
            continue
        line_count = count_lines(path)
        if line_count > max_lines:
            violations.append(LineCountViolation(path, line_count, max_lines))
    return violations


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help="maximum allowed line count",
    )
    parser.add_argument("paths", nargs="*")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the line count check."""
    args = parse_args(argv)
    violations = check_paths(
        [Path(path) for path in args.paths],
        max_lines=args.max_lines,
    )
    for violation in violations:
        print(
            "Error: File "
            f"'{violation.path}' has {violation.line_count} lines, "
            f"which exceeds the maximum limit of {violation.max_lines} lines."
        )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
