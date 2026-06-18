from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.compact_workspace_deps import compact_line, find_cargo_tomls


class CompactWorkspaceDepsTests(unittest.TestCase):
    def test_compacts_workspace_only_inline_table(self) -> None:
        self.assertEqual(
            compact_line("tokio = { workspace = true }\n"),
            "tokio.workspace = true\n",
        )

    def test_leaves_inline_table_with_extra_keys(self) -> None:
        line = 'tokio = { workspace = true, features = ["rt"] }\n'
        self.assertEqual(compact_line(line), line)

    def test_find_cargo_tomls_skips_target(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Cargo.toml").write_text("", encoding="utf-8")
            (root / "target").mkdir()
            (root / "target" / "Cargo.toml").write_text("", encoding="utf-8")

            self.assertEqual(find_cargo_tomls(root), [root / "Cargo.toml"])


if __name__ == "__main__":
    unittest.main()
