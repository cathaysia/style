"""Check git commit history to ensure it is linear (no merge commits)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


class GitError(RuntimeError):
    """An error executing a git command."""


class GitNotFoundError(GitError):
    """The git executable was not found."""


@dataclass(frozen=True)
class MergeCommit:
    """A merge commit that violates linear history."""

    commit_hash: str
    short_hash: str
    subject: str


def run_git(
    cmd: Sequence[str],
    *,
    cwd: Path | str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Execute a git command and return the completed process."""
    git_bin = shutil.which("git")
    if git_bin is None:
        raise GitNotFoundError("Git executable 'git' not found. Please install git.")

    result = subprocess.run(
        [git_bin, *cmd],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        err = result.stderr.strip() or f"git command failed with exit code {result.returncode}"
        raise GitError(err)
    return result


def is_git_repo(repo_path: Path | None = None) -> bool:
    """Return whether repo_path is inside a git repository."""
    result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path, check=False)
    return result.returncode == 0 and result.stdout.strip() == "true"


def is_merge_in_progress(repo_path: Path | None = None) -> bool:
    """Return whether a merge is currently in progress (MERGE_HEAD exists)."""
    result = run_git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=repo_path, check=False)
    return result.returncode == 0


def has_commits(repo_path: Path | None = None) -> bool:
    """Return whether the repository has any commits (HEAD exists)."""
    result = run_git(["rev-parse", "--verify", "HEAD"], cwd=repo_path, check=False)
    return result.returncode == 0


def find_default_base(repo_path: Path | None = None) -> str | None:
    """Attempt to detect the upstream or default base branch."""
    # 1. Check remote default branch via origin/HEAD
    result = run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo_path, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    # 2. Check common base branch names
    for candidate in ("origin/main", "origin/master", "main", "master"):
        check = run_git(["rev-parse", "--verify", candidate], cwd=repo_path, check=False)
        if check.returncode == 0:
            return candidate

    # 3. Check upstream branch of current HEAD
    result = run_git(["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=repo_path, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    return None


def find_merge_commits(
    revisions: Sequence[str],
    *,
    repo_path: Path | None = None,
) -> list[MergeCommit]:
    """Find all merge commits in the specified revisions."""
    if not revisions:
        return []

    result = run_git(
        ["log", "--merges", "--format=%H%x09%h%x09%s", *revisions],
        cwd=repo_path,
        check=True,
    )
    merge_commits: list[MergeCommit] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) == 3:
            merge_commits.append(MergeCommit(parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            merge_commits.append(MergeCommit(parts[0], parts[1], ""))
        elif len(parts) == 1:
            merge_commits.append(MergeCommit(parts[0], parts[0][:7], ""))
    return merge_commits


def check_linear_history(
    revisions: Sequence[str] | None = None,
    *,
    base: str | None = None,
    target: str = "HEAD",
    repo_path: Path | None = None,
) -> list[MergeCommit]:
    """Check git history and return any merge commits found."""
    if revisions:
        revisions_to_check = list(revisions)
    elif base is not None:
        base_ref = find_default_base(repo_path) if base == "auto" else base
        if base_ref:
            revisions_to_check = [f"{base_ref}..{target}"]
        else:
            revisions_to_check = [target]
    else:
        revisions_to_check = [target]

    return find_merge_commits(revisions_to_check, repo_path=repo_path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check git commit history to ensure it is linear (no merge commits)."
    )
    parser.add_argument(
        "--base",
        nargs="?",
        const="auto",
        default=None,
        help="base branch or commit to check against (e.g. 'origin/main' or 'auto')",
    )
    parser.add_argument(
        "--target",
        default="HEAD",
        help="target branch or commit when using --base (default: HEAD)",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="path to git repository (default: current working directory)",
    )
    parser.add_argument(
        "revisions",
        nargs="*",
        help="commit ranges or revisions to check (default: HEAD)",
    )
    args = parser.parse_args(argv)
    if args.base is not None and args.revisions:
        parser.error("cannot specify both --base and positional revisions")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    """Run the linear history check."""
    args = parse_args(argv)

    try:
        if not is_git_repo(args.repo):
            print("Error: Not a git repository (or any of the parent directories).")
            return 2

        if is_merge_in_progress(args.repo):
            print(
                "Error: Git merge in progress (MERGE_HEAD exists). "
                "Merge commits are forbidden because history must remain linear."
            )
            print(
                "Hint: Abort the merge with 'git merge --abort', "
                "and rebase your branch instead: 'git rebase <upstream>'."
            )
            return 1

        if not has_commits(args.repo):
            return 0

        merge_commits = check_linear_history(
            args.revisions if args.revisions else None,
            base=args.base,
            target=args.target,
            repo_path=args.repo,
        )
    except GitError as error:
        print(f"Error: {error}")
        return 2

    if merge_commits:
        count = len(merge_commits)
        commit_word = "commit" if count == 1 else "commits"
        print(f"Error: Non-linear history detected. Found {count} merge {commit_word}:")
        for commit in merge_commits:
            print(f"  {commit.short_hash} {commit.subject}".rstrip())
        print(
            "Hint: Cathaysia repositories require a linear commit history. "
            "Avoid merge commits by rebasing your branch on top of the base branch ('git rebase') "
            "or using squash/rebase merges."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
