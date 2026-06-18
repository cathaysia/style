"""Qualify bare tracing macros in Rust sources."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence

MACROS = frozenset(("trace", "debug", "info", "warn", "error"))
SKIP_DIRS = frozenset(
    (
        ".codegraph",
        ".git",
        ".next",
        "node_modules",
        "target",
    )
)

MACRO_CALL_RE = re.compile(r"(?<![\w:])\b(trace|debug|info|warn|error)!")
TRACING_GROUP_USE_RE = re.compile(r"^(\s*)use\s+tracing::\{([^}]*)\};(\s*)$")
TRACING_SINGLE_USE_RE = re.compile(
    r"^(\s*)use\s+tracing::(trace|debug|info|warn|error);(\s*)$"
)


def rust_files(root: Path) -> list[Path]:
    """Return Rust source files under the repository root."""
    files: list[Path] = []
    for path in root.rglob("*.rs"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def qualify_macro_calls(source: str) -> str:
    """Prefix bare tracing macro calls with tracing::."""
    return MACRO_CALL_RE.sub(lambda match: f"tracing::{match.group(1)}!", source)


def clean_tracing_import_line(line: str) -> str:
    """Remove macro-only imports made redundant by qualified calls."""
    single = TRACING_SINGLE_USE_RE.match(line)
    if single is not None:
        return ""

    group = TRACING_GROUP_USE_RE.match(line)
    if group is None:
        return line

    indent, body, trailing = group.groups()
    names = [name.strip() for name in body.split(",") if name.strip()]
    remaining = [name for name in names if name not in MACROS]
    if not remaining:
        return ""
    if len(remaining) == 1:
        return f"{indent}use tracing::{remaining[0]};{trailing}"
    return f"{indent}use tracing::{{{', '.join(remaining)}}};{trailing}"


def clean_tracing_imports(source: str) -> str:
    """Remove tracing macro imports after macro calls are qualified."""
    return "".join(clean_tracing_import_line(line) for line in source.splitlines(True))


def rewrite_source(source: str) -> str:
    """Return source with bare tracing macro calls qualified."""
    return clean_tracing_imports(qualify_macro_calls(source))


def process_file(path: Path, *, check: bool) -> bool:
    """Rewrite one file and return True when the file differs."""
    source = path.read_text(encoding="utf-8")
    rewritten = rewrite_source(source)
    changed = rewritten != source
    if changed and not check:
        path.write_text(rewritten, encoding="utf-8")
    return changed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report files that need updates without writing them",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root to scan",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the tracing macro qualifier."""
    args = parse_args(argv)
    root = args.root.resolve()
    changed = [
        path for path in rust_files(root) if process_file(path, check=args.check)
    ]

    for path in changed:
        print(path.relative_to(root))

    if args.check and changed:
        print(f"{len(changed)} Rust file(s) need tracing macro qualification.")
        return 1
    if changed:
        print(f"Updated {len(changed)} Rust file(s).")
    else:
        print("All Rust tracing macros are already qualified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
