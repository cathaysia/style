from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.compact_workspace_deps import compact_line, main


class CompactWorkspaceDepsTests(unittest.TestCase):
    def test_compacts_workspace_only_inline_table(self) -> None:
        self.assertEqual(
            compact_line("tokio = { workspace = true }\n"),
            "tokio.workspace = true\n",
        )

    def test_leaves_inline_table_with_extra_keys(self) -> None:
        line = 'tokio = { workspace = true, features = ["rt"] }\n'
        self.assertEqual(compact_line(line), line)

    def test_main_only_processes_passed_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            selected = root / "Cargo.toml"
            unpassed = root / "nested" / "Cargo.toml"
            unpassed.parent.mkdir()
            selected.write_text("tokio = { workspace = true }\n", encoding="utf-8")
            unpassed.write_text("serde = { workspace = true }\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(selected)]), 0)
            self.assertEqual(
                selected.read_text(encoding="utf-8"),
                "tokio.workspace = true\n",
            )
            self.assertEqual(
                unpassed.read_text(encoding="utf-8"),
                "serde = { workspace = true }\n",
            )


if __name__ == "__main__":
    unittest.main()
