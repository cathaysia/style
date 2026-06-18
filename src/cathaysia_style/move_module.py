"""Move Rust sibling module files into their module directories."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_EXCLUDE_DIRS = frozenset(
    (
        ".antigravitycli",
        ".gemini",
        ".git",
        ".plan",
        ".pre-commit",
        "target",
    )
)


@dataclass(frozen=True)
class ModuleMove:
    """A sibling Rust module file move."""

    source: Path
    target: Path


def find_module_moves(root: Path) -> list[ModuleMove]:
    """Return sibling module files that should move into module directories."""
    moves = []
    for current_root, dirs, _files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in DEFAULT_EXCLUDE_DIRS]
        current = Path(current_root)
        for directory in dirs:
            dir_path = current / directory
            try:
                has_contents = any(dir_path.iterdir())
            except OSError:
                continue
            if not has_contents:
                continue
            sibling = current / f"{directory}.rs"
            if sibling.is_file():
                moves.append(ModuleMove(sibling, dir_path / "mod.rs"))
    return moves


def apply_moves(moves: Sequence[ModuleMove]) -> int:
    """Apply module moves and return the number moved."""
    moved = 0
    for move in moves:
        if move.target.exists():
            print(f"Cannot move {move.source} to existing {move.target}")
            continue
        print(f"Moving {move.source} to {move.target}")
        shutil.move(str(move.source), str(move.target))
        moved += 1
    return moved


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root to scan",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the module mover."""
    args = parse_args(argv)
    root = args.root.resolve()
    moves = find_module_moves(root)
    moved = apply_moves(moves)
    blocked = len(moves) - moved

    if moved:
        print("Moved module files. Please stage the changes and commit again.")
    return 1 if moved or blocked else 0


if __name__ == "__main__":
    sys.exit(main())
