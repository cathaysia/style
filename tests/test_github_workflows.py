from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.github_workflows import check_workflows, main


class GithubWorkflowsTests(unittest.TestCase):
    def test_renames_yml_workflow_to_yaml(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            source = workflow_dir / "ci.yml"
            target = workflow_dir / "ci.yaml"
            source.write_text(
                "name: ci\n"
                "jobs:\n"
                "  test-suite:\n"
                "    runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                renames, violations = check_workflows(root)

            self.assertEqual(len(renames), 1)
            self.assertEqual(violations, [])
            self.assertFalse(source.exists())
            self.assertTrue(target.is_file())

    def test_reports_non_kebab_workflow_names(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            workflow = workflow_dir / "CI_Build.yaml"
            workflow.write_text(
                "name: CI Build\n"
                "jobs:\n"
                "  test_suite:\n"
                "    name: Test Suite\n"
                "    runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                _, violations = check_workflows(root)

            messages = [violation.message for violation in violations]
            self.assertIn("workflow file name must use lower kebab-case", messages)
            self.assertIn(
                "workflow top-level name must use lower kebab-case: CI Build",
                messages,
            )
            self.assertIn(
                "workflow job id must use lower kebab-case: test_suite",
                messages,
            )
            self.assertIn(
                "workflow job name must use lower kebab-case: Test Suite",
                messages,
            )

    def test_main_fails_when_files_are_renamed(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "ci.yml").write_text(
                "name: ci\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                exit_code = main(["--root", str(root)])

            self.assertEqual(exit_code, 1)
            self.assertTrue((workflow_dir / "ci.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
