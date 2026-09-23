from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cathaysia_style import linear_history


def create_git_repo(path: Path) -> None:
    """Initialize a git repo with user name and email configured."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)


def commit_file(path: Path, filename: str, content: str, message: str) -> str:
    """Create a file, add it, commit it, and return the commit hash."""
    file_path = path / filename
    file_path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", filename], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True)
    return result.stdout.strip()


class LinearHistoryTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = linear_history.parse_args([])
        self.assertIsNone(args.base)
        self.assertEqual(args.target, "HEAD")
        self.assertIsNone(args.repo)
        self.assertEqual(args.revisions, [])

    def test_parse_args_base_flag_without_value(self) -> None:
        args = linear_history.parse_args(["--base"])
        self.assertEqual(args.base, "auto")

    def test_parse_args_base_flag_with_value(self) -> None:
        args = linear_history.parse_args(["--base", "origin/master"])
        self.assertEqual(args.base, "origin/master")

    def test_parse_args_target_and_repo(self) -> None:
        args = linear_history.parse_args(["--target", "my-feature", "--repo", "/tmp/repo"])
        self.assertEqual(args.target, "my-feature")
        self.assertEqual(args.repo, Path("/tmp/repo"))

    def test_parse_args_positional_revisions(self) -> None:
        args = linear_history.parse_args(["origin/master..HEAD"])
        self.assertEqual(args.revisions, ["origin/master..HEAD"])

    def test_parse_args_rejects_base_with_positional_revisions(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            linear_history.parse_args(["--base", "main", "main..HEAD"])
        self.assertEqual(error.exception.code, 2)

    def test_not_a_git_repo(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self.assertFalse(linear_history.is_git_repo(temp_path))
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 2)
            self.assertIn("Not a git repository", out.getvalue())

    def test_empty_repo_succeeds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            self.assertTrue(linear_history.is_git_repo(temp_path))
            self.assertFalse(linear_history.has_commits(temp_path))
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(out.getvalue(), "")

    def test_linear_history_succeeds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "f1.txt", "1", "first commit")
            commit_file(temp_path, "f2.txt", "2", "second commit")
            commit_file(temp_path, "f3.txt", "3", "third commit")

            self.assertTrue(linear_history.has_commits(temp_path))
            self.assertFalse(linear_history.is_merge_in_progress(temp_path))
            violations = linear_history.check_linear_history(repo_path=temp_path)
            self.assertEqual(violations, [])

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(out.getvalue(), "")

    def test_single_merge_commit_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            default_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=temp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

            # Create branch feat
            subprocess.run(["git", "checkout", "-b", "feat"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "feat.txt", "feat", "feat commit")

            # Checkout main/master
            subprocess.run(["git", "checkout", default_branch], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "main.txt", "main", "main commit")

            # Merge feat into main with --no-ff
            subprocess.run(
                ["git", "merge", "feat", "--no-ff", "-m", "Merge branch feat into main"],
                cwd=temp_path,
                check=True,
                capture_output=True,
            )

            violations = linear_history.check_linear_history(repo_path=temp_path)
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].subject, "Merge branch feat into main")

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 1)
            output = out.getvalue()
            self.assertIn("Non-linear history detected. Found 1 merge commit:", output)
            self.assertIn("Merge branch feat into main", output)
            self.assertIn("Hint: Cathaysia repositories require a linear commit history", output)

    def test_multiple_merge_commits_fail(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            default_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=temp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

            # First merge
            subprocess.run(["git", "checkout", "-b", "feat1"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "feat1.txt", "1", "feat1 commit")
            subprocess.run(["git", "checkout", default_branch], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "main1.txt", "m1", "main commit 1")
            subprocess.run(
                ["git", "merge", "feat1", "--no-ff", "-m", "Merge feat 1"],
                cwd=temp_path,
                check=True,
                capture_output=True,
            )

            # Second merge
            subprocess.run(["git", "checkout", "-b", "feat2"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "feat2.txt", "2", "feat2 commit")
            subprocess.run(["git", "checkout", default_branch], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "main2.txt", "m2", "main commit 2")
            subprocess.run(
                ["git", "merge", "feat2", "--no-ff", "-m", "Merge feat 2"],
                cwd=temp_path,
                check=True,
                capture_output=True,
            )

            violations = linear_history.check_linear_history(repo_path=temp_path)
            self.assertEqual(len(violations), 2)
            self.assertEqual(violations[0].subject, "Merge feat 2")
            self.assertEqual(violations[1].subject, "Merge feat 1")

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 1)
            output = out.getvalue()
            self.assertIn("Found 2 merge commits:", output)
            self.assertIn("Merge feat 1", output)
            self.assertIn("Merge feat 2", output)

    def test_merge_in_progress_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            default_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=temp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

            subprocess.run(["git", "checkout", "-b", "feat"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "feat.txt", "feat", "feat commit")

            subprocess.run(["git", "checkout", default_branch], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "main.txt", "main", "main commit")

            # Merge with --no-commit to leave merge in progress
            subprocess.run(
                ["git", "merge", "feat", "--no-commit", "--no-ff"],
                cwd=temp_path,
                check=True,
                capture_output=True,
            )
            self.assertTrue(linear_history.is_merge_in_progress(temp_path))

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 1)
            output = out.getvalue()
            self.assertIn("Git merge in progress (MERGE_HEAD exists)", output)
            self.assertIn("git merge --abort", output)

    def test_base_option_filters_range(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            default_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=temp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

            # Merge old branch on default_branch
            subprocess.run(["git", "checkout", "-b", "old-feat"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "old.txt", "old", "old feat commit")
            subprocess.run(["git", "checkout", default_branch], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "main-old.txt", "mo", "main commit before merge")
            subprocess.run(
                ["git", "merge", "old-feat", "--no-ff", "-m", "Old merge commit"],
                cwd=temp_path,
                check=True,
                capture_output=True,
            )

            # Now create new feature branch from current default_branch and make linear commits
            subprocess.run(["git", "checkout", "-b", "new-feat"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "new1.txt", "1", "new feat commit 1")
            commit_file(temp_path, "new2.txt", "2", "new feat commit 2")

            # Checking full HEAD includes the old merge commit -> fails
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path)])
            self.assertEqual(exit_code, 1)
            self.assertIn("Old merge commit", out.getvalue())

            # Checking with --base default_branch checks default_branch..HEAD which is linear -> succeeds
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path), "--base", default_branch])
            self.assertEqual(exit_code, 0)
            self.assertEqual(out.getvalue(), "")

            # Checking with positional range default_branch..HEAD -> succeeds
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path), f"{default_branch}..HEAD"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(out.getvalue(), "")

    def test_base_auto_detects_default_branch(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            default_branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=temp_path, check=True, capture_output=True, text=True
            ).stdout.strip()

            subprocess.run(["git", "checkout", "-b", "feat"], cwd=temp_path, check=True, capture_output=True)
            commit_file(temp_path, "feat.txt", "feat", "linear feat")

            # Ensure find_default_base detects default_branch (master or main)
            detected = linear_history.find_default_base(temp_path)
            self.assertEqual(detected, default_branch)

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path), "--base", "auto"])
            self.assertEqual(exit_code, 0)

    def test_invalid_revision_fails(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            create_git_repo(temp_path)
            commit_file(temp_path, "base.txt", "base", "initial commit")

            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main(["--repo", str(temp_path), "nonexistent_ref_12345..HEAD"])
            self.assertEqual(exit_code, 2)
            self.assertIn("Error:", out.getvalue())

    def test_git_not_found(self) -> None:
        with patch("cathaysia_style.linear_history.shutil.which", return_value=None):
            out = StringIO()
            with redirect_stdout(out):
                exit_code = linear_history.main([])
            self.assertEqual(exit_code, 2)
            self.assertIn("not found", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
