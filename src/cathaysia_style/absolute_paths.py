"""Forbid host-specific absolute paths in files of any type."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

# Host-specific locations that should be derived at runtime instead of hard-coded.
DEFAULT_ROOTS = (
    "home",
    "Users",
    "root",
    "mnt",
    "media",
    "Volumes",
    "private",
    "tmp",
    "var/folders",
    "var/tmp",
    "run/user",
    "cygdrive",
    "opt",
    "usr/local",
    "nix/store",
    "snap",
)

# A path must start at a token boundary: not inside a word, URL, glob, or home
# shorthand. This keeps https://example.com/home/user and src/home/user intact.
_LOOKBEHIND = r"(?<![\w./\\~*?#!-])"
_POSIX_SEGMENT = r"[^\s/\\\"'`<>|]+"
_WINDOWS_SEGMENT = r"[^\s\\/\"'`<>|*?]+"


def _build_pattern(roots: Sequence[str]) -> re.Pattern[str]:
    """Build the absolute path matcher for the configured roots."""
    if not roots:
        raise ValueError("at least one absolute path root is required")
    root_pattern = "|".join(
        re.escape(root.strip("/")) for root in sorted(roots, key=len, reverse=True)
    )
    posix = (
        r"/(?:"
        + root_pattern
        + r")"
        + r"(?![A-Za-z0-9_.-])"
        + r"(?:/"
        + _POSIX_SEGMENT
        + r")*"
    )
    file_url = r"file://" + posix
    windows = (
        r"(?<![A-Za-z0-9])[A-Za-z]:(?:\\+|/(?!/))"
        + _WINDOWS_SEGMENT
        + r"(?:(?:\\+|/(?!/))"
        + _WINDOWS_SEGMENT
        + r")*"
    )
    unc = r"(?<![\w\\])\\{2,}[A-Za-z0-9_.-]+\\+" + _WINDOWS_SEGMENT
    return re.compile(
        _LOOKBEHIND
        + r"(?:"
        + posix
        + r"|"
        + file_url
        + r")|"
        + windows
        + r"|"
        + unc
    )


def normalize_root(value: str) -> str:
    """Return a normalized root without its leading slash."""
    root = value.strip()
    if not root.startswith("/"):
        raise ValueError("must start with '/'")
    root = root.rstrip("/")
    if not root:
        raise ValueError("must not be the filesystem root")
    parts = root[1:].split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("must be a normalized path without '.' or '..'")
    return "/".join(parts)


def _parse_root_argument(value: str) -> str:
    """Parse a --root argument for argparse."""
    try:
        return normalize_root(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


ABSOLUTE_PATH_RE = _build_pattern(DEFAULT_ROOTS)
BINARY_SAMPLE_SIZE = 8192
TRAILING_PUNCTUATION = ".,;:)]}"


@dataclass(frozen=True)
class AbsolutePathMatch:
    """An absolute path found on a line."""

    line: int
    column: int
    text: str


@dataclass(frozen=True)
class AbsolutePathViolation:
    """An absolute path found in a file."""

    path: Path
    match: AbsolutePathMatch


def find_absolute_paths(
    text: str,
    *,
    pattern: re.Pattern[str] = ABSOLUTE_PATH_RE,
) -> list[AbsolutePathMatch]:
    """Return absolute path matches in text."""
    matches = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for match in pattern.finditer(line):
            matches.append(
                AbsolutePathMatch(
                    line_number,
                    match.start() + 1,
                    match.group(0).rstrip(TRAILING_PUNCTUATION),
                )
            )
    return matches


def _is_binary(data: bytes) -> bool:
    """Return whether data looks like a binary file."""
    return b"\0" in data[:BINARY_SAMPLE_SIZE]


def check_path(
    path: Path,
    *,
    pattern: re.Pattern[str] = ABSOLUTE_PATH_RE,
) -> list[AbsolutePathViolation]:
    """Return absolute paths found in one file."""
    if not path.is_file():
        return []

    data = path.read_bytes()
    if _is_binary(data):
        return []

    text = data.decode("utf-8", errors="ignore")
    return [
        AbsolutePathViolation(path, match)
        for match in find_absolute_paths(text, pattern=pattern)
    ]


def check_paths(
    paths: Sequence[Path],
    *,
    pattern: re.Pattern[str] = ABSOLUTE_PATH_RE,
) -> list[AbsolutePathViolation]:
    """Return absolute paths found in the given files."""
    violations = []
    for path in paths:
        violations.extend(check_path(path, pattern=pattern))
    return violations


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        dest="roots",
        action="append",
        type=_parse_root_argument,
        default=[],
        metavar="PATH",
        help="additional absolute path root to forbid (repeatable), e.g. /data",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="files to check",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Reject files that contain host-specific absolute paths."""
    args = parse_args(argv)
    roots = tuple(dict.fromkeys([*DEFAULT_ROOTS, *args.roots]))
    pattern = _build_pattern(roots)
    violations = check_paths(args.paths, pattern=pattern)
    if not violations:
        return 0

    print("Error: host-specific absolute paths must not appear in files.")
    for violation in violations:
        match = violation.match
        print(
            f"  {violation.path}:{match.line}:{match.column}: {match.text}"
        )
    print(
        "Hint: Use a relative path, a path derived from the repository root, "
        "or an environment variable instead."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
