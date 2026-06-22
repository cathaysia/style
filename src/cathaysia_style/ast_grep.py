from __future__ import annotations

import subprocess
import shutil
import sys
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence


def ast_grep_executable() -> str:
    executable = shutil.which("sg")
    if executable is not None:
        return executable

    sibling = Path(sys.executable).with_name("sg")
    if sibling.is_file():
        return str(sibling)

    return "sg"


def copy_resource_tree(source, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            copy_resource_tree(child, target)
        else:
            target.write_bytes(child.read_bytes())


def materialize_config(destination: Path) -> Path:
    package = resources.files("cathaysia_style")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "sgconfig.yml").write_bytes(
        package.joinpath("sgconfig.yml").read_bytes(),
    )
    copy_resource_tree(
        package.joinpath("ast_grep_rules"),
        destination / "ast_grep_rules",
    )
    return destination / "sgconfig.yml"


def command(args: Sequence[str], config: Path | None = None) -> list[str]:
    config = config or resources.files("cathaysia_style").joinpath("sgconfig.yml")
    return [
        ast_grep_executable(),
        "scan",
        "--config",
        str(config),
        "--color",
        "never",
        "--report-style",
        "short",
        "--update-all",
        "--error",
        *args,
    ]


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    with TemporaryDirectory(prefix="cathaysia-ast-grep-") as temp:
        config = materialize_config(Path(temp))
        return subprocess.run(command(args, config), cwd=Path.cwd(), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
