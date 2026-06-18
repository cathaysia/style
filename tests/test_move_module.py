from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.move_module import ModuleMove, find_module_moves, main


class MoveModuleTests(unittest.TestCase):
    def test_finds_move_for_passed_rust_module_file(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "server.rs"
            module_dir = root / "server"
            module_dir.mkdir()
            source.write_text("mod server;\n", encoding="utf-8")
            (module_dir / "route.rs").write_text("", encoding="utf-8")

            self.assertEqual(
                find_module_moves([source]),
                [ModuleMove(source, module_dir / "mod.rs")],
            )

    def test_ignores_unpassed_module_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            selected = root / "server.rs"
            unpassed = root / "client.rs"

            for source in (selected, unpassed):
                module_dir = source.with_suffix("")
                module_dir.mkdir()
                source.write_text("", encoding="utf-8")
                (module_dir / "inner.rs").write_text("", encoding="utf-8")

            with redirect_stdout(StringIO()):
                self.assertEqual(main([str(selected)]), 1)

            self.assertFalse(selected.exists())
            self.assertTrue((root / "server" / "mod.rs").is_file())
            self.assertTrue(unpassed.is_file())
            self.assertFalse((root / "client" / "mod.rs").exists())

    def test_ignores_non_rust_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "server.txt"
            module_dir = root / "server"
            module_dir.mkdir()
            source.write_text("", encoding="utf-8")
            (module_dir / "inner.rs").write_text("", encoding="utf-8")

            self.assertEqual(find_module_moves([source]), [])

    def test_ignores_existing_mod_rs_files(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "mod.rs"
            module_dir = root / "mod"
            module_dir.mkdir()
            source.write_text("", encoding="utf-8")
            (module_dir / "inner.rs").write_text("", encoding="utf-8")

            self.assertEqual(find_module_moves([source]), [])


if __name__ == "__main__":
    unittest.main()
