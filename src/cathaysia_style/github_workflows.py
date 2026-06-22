"""Check GitHub workflow file names and task identifiers."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

WORKFLOW_DIR = Path(".github/workflows")
KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_LEVEL_NAME_RE = re.compile(r"^name:\s*(.*?)\s*(?:#.*)?$")
YAML_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s|$)")


@dataclass(frozen=True)
class WorkflowRename:
    """A legacy workflow file rename."""

    source: Path
    target: Path


@dataclass(frozen=True)
class WorkflowViolation:
    """A GitHub workflow naming violation."""

    path: Path
    message: str


@dataclass(frozen=True)
class WorkflowJob:
    """A GitHub workflow job."""

    identifier: str
    name: str | None


def is_kebab_case(value: str) -> bool:
    """Return whether value uses lower kebab-case."""
    return KEBAB_CASE_RE.fullmatch(value) is not None


def workflow_files(root: Path) -> list[Path]:
    """Return GitHub workflow YAML files under root."""
    workflow_dir = root / WORKFLOW_DIR
    if not workflow_dir.is_dir():
        return []
    return sorted(
        path
        for path in workflow_dir.iterdir()
        if path.is_file() and path.suffix in (".yaml", ".yml")
    )


def planned_renames(paths: Sequence[Path]) -> list[WorkflowRename]:
    """Return .yml workflow files that should be renamed to .yaml."""
    return [
        WorkflowRename(path, path.with_suffix(".yaml"))
        for path in paths
        if path.suffix == ".yml"
    ]


def apply_renames(renames: Sequence[WorkflowRename]) -> list[WorkflowViolation]:
    """Rename legacy workflow files and return blocked rename violations."""
    violations = []
    for rename in renames:
        if rename.target.exists():
            violations.append(
                WorkflowViolation(
                    rename.source,
                    f"cannot rename to existing workflow file {rename.target}",
                )
            )
            continue
        print(f"Renaming {rename.source} to {rename.target}")
        rename.source.rename(rename.target)
    return violations


def scalar_value(raw_value: str) -> str:
    """Return a normalized YAML scalar value for simple name fields."""
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def top_level_name(source: str) -> str | None:
    """Return the top-level workflow name, if present."""
    for line in source.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            continue
        match = TOP_LEVEL_NAME_RE.match(line)
        if match is not None:
            return scalar_value(match.group(1))
    return None


def workflow_jobs(source: str) -> list[WorkflowJob]:
    """Return jobs defined directly under the top-level jobs key."""
    jobs: list[WorkflowJob] = []
    in_jobs = False
    jobs_indent = 0
    child_indent: int | None = None
    field_indent: int | None = None
    current_job: str | None = None
    current_name: str | None = None

    for raw_line in source.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if not in_jobs:
            if indent == 0 and stripped == "jobs:":
                in_jobs = True
                jobs_indent = indent
            continue

        if indent <= jobs_indent:
            break
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            if current_job is not None:
                jobs.append(WorkflowJob(current_job, current_name))
            field_indent = None
            current_name = None
            match = YAML_KEY_RE.match(stripped)
            current_job = match.group(1) if match is not None else None
            continue

        if current_job is None:
            continue
        if field_indent is None:
            field_indent = indent
        if indent != field_indent:
            continue

        match = TOP_LEVEL_NAME_RE.match(stripped)
        if match is not None:
            current_name = scalar_value(match.group(1))

    if current_job is not None:
        jobs.append(WorkflowJob(current_job, current_name))

    return jobs


def check_workflow(path: Path) -> list[WorkflowViolation]:
    """Return naming violations for one GitHub workflow file."""
    violations = []

    if not is_kebab_case(path.stem):
        violations.append(
            WorkflowViolation(path, "workflow file name must use lower kebab-case")
        )

    source = path.read_text(encoding="utf-8")
    name = top_level_name(source)
    if name is None:
        violations.append(WorkflowViolation(path, "workflow top-level name is missing"))
    elif not is_kebab_case(name):
        violations.append(
            WorkflowViolation(
                path,
                f"workflow top-level name must use lower kebab-case: {name}",
            )
        )

    for job in workflow_jobs(source):
        if not is_kebab_case(job.identifier):
            violations.append(
                WorkflowViolation(
                    path,
                    f"workflow job id must use lower kebab-case: {job.identifier}",
                )
            )
        if job.name is not None and not is_kebab_case(job.name):
            violations.append(
                WorkflowViolation(
                    path,
                    f"workflow job name must use lower kebab-case: {job.name}",
                )
            )

    return violations


def check_workflows(root: Path) -> tuple[list[WorkflowRename], list[WorkflowViolation]]:
    """Rename legacy workflow files and return remaining naming violations."""
    initial_files = workflow_files(root)
    renames = planned_renames(initial_files)
    violations = apply_renames(renames)
    checked_files = [
        path.with_suffix(".yaml") if path.suffix == ".yml" else path
        for path in initial_files
    ]

    for path in checked_files:
        if path.exists():
            violations.extend(check_workflow(path))

    return renames, violations


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
    """Run the GitHub workflow naming check."""
    args = parse_args(argv)
    root = args.root.resolve()
    renames, violations = check_workflows(root)

    for violation in violations:
        print(f"Error: {violation.path.relative_to(root)}: {violation.message}")

    if renames:
        print("Renamed GitHub workflow files. Please stage the changes and commit again.")
    if violations:
        return 1
    if renames:
        return 1

    print("GitHub workflow names are already lower kebab-case.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
