from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest

from cathaysia_style import ast_grep


class AstGrepTests(unittest.TestCase):
    def test_command_uses_packaged_config(self) -> None:
        command = ast_grep.command(["src/lib.rs"])

        self.assertEqual(Path(command[0]).name, "sg")
        self.assertEqual(command[1], "scan")
        self.assertEqual(command[command.index("--color") + 1], "never")
        self.assertEqual(command[command.index("--report-style") + 1], "short")
        self.assertIn("--update-all", command)
        self.assertIn("--error", command)
        self.assertEqual(command[-1], "src/lib.rs")

        config = Path(command[command.index("--config") + 1])
        self.assertEqual(config.name, "sgconfig.yml")
        self.assertTrue(config.is_file())

    def test_materialize_config_copies_rules(self) -> None:
        with TemporaryDirectory() as temp:
            config = ast_grep.materialize_config(Path(temp))

            self.assertTrue(config.is_file())
            rule = Path(temp) / "ast_grep_rules" / "rust-no-return.yml"
            self.assertTrue(rule.is_file())

    def test_ast_grep_executable_falls_back_to_python_bin(self) -> None:
        with patch("cathaysia_style.ast_grep.shutil.which", return_value=None), \
                patch("cathaysia_style.ast_grep.sys.executable", "/tmp/example/bin/python"), \
                patch("cathaysia_style.ast_grep.Path.is_file", return_value=True):
            self.assertEqual(ast_grep.ast_grep_executable(), "/tmp/example/bin/sg")

    def test_main_returns_ast_grep_exit_code(self) -> None:
        completed = Mock(returncode=3)

        with patch("cathaysia_style.ast_grep.subprocess.run", return_value=completed) as run:
            self.assertEqual(ast_grep.main(["src/lib.rs"]), 3)

        command = run.call_args.args[0]
        self.assertEqual(command[-1], "src/lib.rs")
        self.assertEqual(run.call_args.kwargs["cwd"], Path.cwd())
        self.assertFalse(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
