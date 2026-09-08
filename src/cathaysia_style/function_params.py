"""Check Rust source files for functions exceeding maximum allowed parameter count."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Sequence

DEFAULT_MAX_PARAMS = 4


def find_ast_grep() -> str | None:
    """Find the ast-grep executable ('ast-grep' or 'sg')."""
    executable = shutil.which("ast-grep")
    if executable is not None:
        return executable

    for name in ("ast-grep", "sg"):
        sibling = Path(sys.executable).with_name(name)
        if sibling.is_file():
            return str(sibling)

    executable = shutil.which("sg")
    if executable is not None:
        if Path(executable).resolve() not in (Path("/usr/bin/sg"), Path("/bin/sg")):
            return executable
        try:
            out = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if "ast-grep" in out.stdout:
                return executable
        except (subprocess.SubprocessError, OSError):
            pass

    return None


def ast_grep_executable() -> str:
    """Return ast-grep executable path or default to 'ast-grep'."""
    return find_ast_grep() or "ast-grep"


def build_rule(max_params: int) -> str:
    """Build ast-grep rule YAML to detect functions with > max_params parameters."""
    if max_params < 0:
        raise ValueError(f"max_params must be non-negative, got {max_params}")

    limit = max_params + 1
    p_vars = [f"$P{i}" for i in range(1, limit + 1)]
    p_str = ", ".join(p_vars)
    return (
        "id: max-function-params\n"
        "language: rust\n"
        "severity: error\n"
        f'message: "Function has too many parameters (maximum allowed is {max_params})"\n'
        "utils:\n"
        "  has-self:\n"
        "    any:\n"
        "      - has:\n"
        "          kind: self_parameter\n"
        "      - has:\n"
        '          pattern: "self: $T"\n'
        "rule:\n"
        "  all:\n"
        "    - inside:\n"
        "        any:\n"
        "          - kind: function_item\n"
        "          - kind: function_signature_item\n"
        "    - any:\n"
        "        - all:\n"
        "            - matches: has-self\n"
        "            - any:\n"
        "                - pattern:\n"
        f'                    context: "fn $F($SELF, {p_str}, $$$REST) {{}}"\n'
        "                    selector: parameters\n"
        "                - pattern:\n"
        f'                    context: "fn $F($SELF, {p_str}) {{}}"\n'
        "                    selector: parameters\n"
        "        - all:\n"
        "            - not:\n"
        "                matches: has-self\n"
        "            - any:\n"
        "                - pattern:\n"
        f'                    context: "fn $F({p_str}, $$$REST) {{}}"\n'
        "                    selector: parameters\n"
        "                - pattern:\n"
        f'                    context: "fn $F({p_str}) {{}}"\n'
        "                    selector: parameters\n"
    )


def command(
    rule_path: Path,
    paths: Sequence[Path | str],
    *,
    executable: str | None = None,
) -> list[str]:
    """Return ast-grep scan command."""
    return [
        executable or ast_grep_executable(),
        "scan",
        "--rule",
        str(rule_path),
        "--color",
        "never",
        "--report-style",
        "short",
        "--error",
        *[str(p) for p in paths],
    ]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-params",
        "--max-parameters",
        dest="max_params",
        type=int,
        default=DEFAULT_MAX_PARAMS,
        help=f"maximum allowed function parameter count (default: {DEFAULT_MAX_PARAMS})",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Rust files or directories to check",
    )
    args = parser.parse_args(argv)
    if args.max_params < 0:
        parser.error("--max-params must be non-negative")
    return args


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: int | None = None,
    stderr: int | None = None,
) -> int:
    """Run the function parameter count check."""
    args = parse_args(argv)
    existing_paths = [p for p in args.paths if p.exists()]
    if not existing_paths:
        return 0

    with TemporaryDirectory(prefix="cathaysia-function-params-") as temp:
        rule_path = Path(temp) / "rule.yml"
        rule_path.write_text(build_rule(args.max_params), encoding="utf-8")
        cmd = command(rule_path, existing_paths)
        try:
            result = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                check=False,
                stdout=stdout,
                stderr=stderr,
            )
        except FileNotFoundError:
            executable = cmd[0]
            print(
                f"Error: ast-grep executable '{executable}' not found. Please install ast-grep (sg)."
            )
            return 1

        if result.returncode != 0:
            print(
                "Hint: Consider grouping related parameters into a struct, "
                "options object, or builder pattern to reduce parameter count."
            )
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
