from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from cathaysia_style.forbid_path_changes import (
    ProtectedPathRule,
    find_forbidden_changes,
    main,
    matches_path_pattern,
    parse_rule,
)


class ForbidPathChangesTests(unittest.TestCase):
    def test_matches_recursive_path_patterns(self) -> None:
        self.assertTrue(
            matches_path_pattern("generated/api/client.py", "generated/**")
        )
        self.assertTrue(matches_path_pattern("snapshot.json", "**/*.json"))
        self.assertTrue(
            matches_path_pattern("fixtures/api/snapshot.json", "**/*.json")
        )

    def test_single_star_does_not_cross_directories(self) -> None:
        self.assertTrue(matches_path_pattern("src/client.py", "src/*.py"))
        self.assertFalse(matches_path_pattern("src/api/client.py", "src/*.py"))

    def test_parses_inline_rules_with_optional_reasons(self) -> None:
        self.assertEqual(
            parse_rule('{path: "generated/**", reason: "generated, do not edit"}'),
            ProtectedPathRule("generated/**", "generated, do not edit"),
        )
        self.assertEqual(
            parse_rule('{path="fixtures/locked/*.json"}'),
            ProtectedPathRule("fixtures/locked/*.json"),
        )

    def test_parses_block_rules_with_comma_or_newline_separators(self) -> None:
        self.assertEqual(
            parse_rule("path: generated/**, reason: use the generator\n"),
            ProtectedPathRule("generated/**", "use the generator"),
        )
        self.assertEqual(
            parse_rule("path: fixtures/locked/*.json\nreason: read-only\n"),
            ProtectedPathRule("fixtures/locked/*.json", "read-only"),
        )

    def test_reports_each_path_once_using_its_first_matching_rule(self) -> None:
        rules = [
            ProtectedPathRule("generated/**", "generated files are read-only"),
            ProtectedPathRule("**/*.py"),
        ]

        violations = find_forbidden_changes(
            [Path("generated/api/client.py"), Path("src/main.py")],
            rules,
        )

        self.assertEqual(len(violations), 2)
        self.assertEqual(violations[0].rule, rules[0])
        self.assertEqual(violations[1].rule, rules[1])

    def test_main_fails_and_prints_the_matching_rule_reason(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    "path: fixtures/**\n",
                    "path: generated/**, reason: use the generator\n",
                    "generated/api/client.py",
                    "src/main.py",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("generated/api/client.py", output.getvalue())
        self.assertIn("protected path: generated/**", output.getvalue())
        self.assertIn("Reason: use the generator", output.getvalue())
        self.assertNotIn("src/main.py", output.getvalue())

    def test_main_rejects_invalid_rules(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            exit_code = main(['{reason: "missing path"}', "src/main.py"])

        self.assertEqual(exit_code, 2)
        self.assertIn("path is required", output.getvalue())

    def test_main_succeeds_when_no_paths_match(self) -> None:
        with redirect_stdout(StringIO()):
            exit_code = main(["path: generated/**\n", "src/main.py"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
