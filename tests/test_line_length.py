from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.line_length import check_paths


class LineLengthTests(unittest.TestCase):
    def test_reports_files_over_limit(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "mod.rs"
            path.write_text("one\ntwo\nthree\n", encoding="utf-8")

            violations = check_paths([path], max_lines=2)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].line_count, 3)

    def test_ignores_missing_files(self) -> None:
        violations = check_paths([Path("missing.rs")], max_lines=2)

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
