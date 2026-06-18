"""Move passed Rust sibling module files into their module directories."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ModuleMove:
    """A sibling Rust module file move."""

    source: Path
    target: Path


def module_move_for_file(path: Path) -> ModuleMove | None:
    """Return the module move for a single Rust file, if one is needed."""
    if path.suffix != ".rs" or path.name == "mod.rs" or not path.is_file():
        return None

    module_dir = path.with_suffix("")
    if not module_dir.is_dir():
        return None

    try:
        has_contents = any(module_dir.iterdir())
    except OSError:
        return None
    if not has_contents:
        return None

    return ModuleMove(path, module_dir / "mod.rs")


def find_module_moves(paths: Sequence[Path]) -> list[ModuleMove]:
    """Return moves for the passed Rust files only."""
    moves = []
    seen = set()
    for path in paths:
        move = module_move_for_file(path)
        if move is None or move in seen:
            continue
        moves.append(move)
        seen.add(move)
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
        "paths",
        nargs="*",
        type=Path,
        help="Rust files to inspect",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the module mover."""
    args = parse_args(argv)
    moves = find_module_moves(args.paths)
    moved = apply_moves(moves)
    blocked = len(moves) - moved

    if moved:
        print("Moved module files. Please stage the changes and commit again.")
    return 1 if moved or blocked else 0


if __name__ == "__main__":
    sys.exit(main())
