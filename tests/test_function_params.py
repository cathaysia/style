from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from cathaysia_style import function_params


class FunctionParamsTests(unittest.TestCase):
    def test_parse_args_defaults(self) -> None:
        args = function_params.parse_args(["src/lib.rs"])
        self.assertEqual(args.max_params, 4)
        self.assertEqual(args.paths, [Path("src/lib.rs")])

    def test_parse_args_custom_max_params(self) -> None:
        args = function_params.parse_args(["--max-params", "2", "src/lib.rs"])
        self.assertEqual(args.max_params, 2)

        args = function_params.parse_args(["--max-parameters", "6", "src/lib.rs"])
        self.assertEqual(args.max_params, 6)

    def test_parse_args_rejects_negative_value(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            function_params.parse_args(["--max-params", "-1", "src/lib.rs"])
        self.assertEqual(error.exception.code, 2)

    def test_build_rule_generates_valid_content(self) -> None:
        rule = function_params.build_rule(4)
        self.assertIn("id: max-function-params", rule)
        self.assertIn("maximum allowed is 4", rule)
        self.assertIn("has-self", rule)
        self.assertIn("self_parameter", rule)
        self.assertIn("$P1, $P2, $P3, $P4, $P5", rule)

    def test_build_rule_rejects_negative_value(self) -> None:
        with self.assertRaises(ValueError):
            function_params.build_rule(-1)

    def test_find_ast_grep_ignores_system_sg(self) -> None:
        completed = Mock(stdout="invalid option\n", stderr="")
        with patch(
            "cathaysia_style.function_params.shutil.which",
            side_effect=lambda name: "/usr/bin/sg" if name == "sg" else None,
        ), patch(
            "cathaysia_style.function_params.Path.is_file",
            return_value=False,
        ), patch(
            "cathaysia_style.function_params.subprocess.run",
            return_value=completed,
        ):
            self.assertIsNone(function_params.find_ast_grep())
            self.assertEqual(function_params.ast_grep_executable(), "ast-grep")

    def test_command_structure(self) -> None:
        rule_file = Path("/tmp/rule.yml")
        files = [Path("src/a.rs"), Path("src/b.rs")]
        cmd = function_params.command(rule_file, files, executable="sg")

        self.assertEqual(cmd[0], "sg")
        self.assertEqual(cmd[1], "scan")
        self.assertEqual(cmd[cmd.index("--rule") + 1], str(rule_file))
        self.assertIn("--error", cmd)
        self.assertEqual(cmd[cmd.index("--color") + 1], "never")
        self.assertEqual(cmd[cmd.index("--report-style") + 1], "short")
        self.assertEqual(cmd[-2:], ["src/a.rs", "src/b.rs"])

    def test_main_returns_zero_when_no_paths_or_no_existing_files(self) -> None:
        self.assertEqual(function_params.main([]), 0)
        self.assertEqual(function_params.main(["/nonexistent/path/file.rs"]), 0)

    def test_main_runs_ast_grep_and_propagates_success(self) -> None:
        with TemporaryDirectory() as temp:
            test_file = Path(temp) / "test.rs"
            test_file.write_text("fn ok() {}\n")

            completed = Mock(returncode=0)
            with patch("cathaysia_style.function_params.subprocess.run", return_value=completed) as run:
                exit_code = function_params.main([str(test_file)])

            self.assertEqual(exit_code, 0)
            cmd = run.call_args.args[0]
            self.assertEqual(cmd[1], "scan")
            self.assertIn("--rule", cmd)
            self.assertEqual(cmd[-1], str(test_file))

    def test_main_prints_hint_on_failure(self) -> None:
        with TemporaryDirectory() as temp:
            test_file = Path(temp) / "test.rs"
            test_file.write_text("fn too_many(a: i32, b: i32, c: i32, d: i32, e: i32) {}\n")

            completed = Mock(returncode=1)
            output = StringIO()
            with patch("cathaysia_style.function_params.subprocess.run", return_value=completed), \
                    redirect_stdout(output):
                exit_code = function_params.main([str(test_file)])

            self.assertEqual(exit_code, 1)
            self.assertIn("Hint: Consider grouping related parameters", output.getvalue())

    def test_main_handles_missing_executable(self) -> None:
        with TemporaryDirectory() as temp:
            test_file = Path(temp) / "test.rs"
            test_file.write_text("fn ok() {}\n")

            output = StringIO()
            with patch(
                "cathaysia_style.function_params.subprocess.run",
                side_effect=FileNotFoundError("not found"),
            ), redirect_stdout(output):
                exit_code = function_params.main([str(test_file)])

            self.assertEqual(exit_code, 1)
            self.assertIn("not found. Please install ast-grep", output.getvalue())

    @unittest.skipIf(
        function_params.find_ast_grep() is None,
        "ast-grep is not installed",
    )
    def test_integration_detects_too_many_parameters(self) -> None:
        with TemporaryDirectory() as temp:
            sample = Path(temp) / "sample.rs"
            sample.write_text(
                """
fn ok(a: i32, b: i32, c: i32, d: i32) {}

fn too_many(a: i32, b: i32, c: i32, d: i32, e: i32) {}

impl Foo {
    fn method_ok(&self, a: i32, b: i32, c: i32, d: i32) {}
    fn method_too_many(&mut self, a: i32, b: i32, c: i32, d: i32, e: i32) {}
    fn method_val_ok(self, a: i32, b: i32, c: i32, d: i32) {}
}

trait Bar {
    fn trait_ok(a: i32, b: i32, c: i32, d: i32);
    fn trait_too_many(a: i32, b: i32, c: i32, d: i32, e: i32);
}
""".lstrip(),
            )

            with redirect_stdout(StringIO()):
                exit_code = function_params.main(
                    [str(sample)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self.assertEqual(exit_code, 1)

    @unittest.skipIf(
        function_params.find_ast_grep() is None,
        "ast-grep is not installed",
    )
    def test_integration_passes_when_within_limits(self) -> None:
        with TemporaryDirectory() as temp:
            sample = Path(temp) / "sample.rs"
            sample.write_text(
                """
fn ok(a: i32, b: i32, c: i32, d: i32) {}

impl Foo {
    fn method_ok(&self, a: i32, b: i32, c: i32, d: i32) {}
}
""".lstrip(),
            )

            with redirect_stdout(StringIO()):
                exit_code = function_params.main(
                    [str(sample)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self.assertEqual(exit_code, 0)

    @unittest.skipIf(
        function_params.find_ast_grep() is None,
        "ast-grep is not installed",
    )
    def test_integration_custom_limit(self) -> None:
        with TemporaryDirectory() as temp:
            sample = Path(temp) / "sample.rs"
            sample.write_text(
                """
fn three_params(a: i32, b: i32, c: i32) {}
fn two_params(a: i32, b: i32) {}
""".lstrip(),
            )

            with redirect_stdout(StringIO()):
                # Default max 4: passes
                self.assertEqual(
                    function_params.main(
                        [str(sample)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    ),
                    0,
                )

                # Custom max 2: fails because three_params > 2
                self.assertEqual(
                    function_params.main(
                        ["--max-params", "2", str(sample)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    ),
                    1,
                )


if __name__ == "__main__":
    unittest.main()
