from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cathaysia_style.absolute_paths import (
    check_paths,
    find_absolute_paths,
    main,
)


def matched_text(source: str) -> list[str]:
    return [match.text for match in find_absolute_paths(source)]


class AbsolutePathTests(unittest.TestCase):
    def test_detects_posix_home_paths(self) -> None:
        self.assertEqual(
            matched_text('let path = "/home/alice/project";'),
            ["/home/alice/project"],
        )
        self.assertEqual(
            matched_text("'/Users/alice/Library'"),
            ["/Users/alice/Library"],
        )
        self.assertEqual(
            matched_text('"/root/.ssh/id_rsa"'),
            ["/root/.ssh/id_rsa"],
        )
        self.assertEqual(
            matched_text("path:/home/alice/project"),
            ["/home/alice/project"],
        )

    def test_detects_host_specific_mounts_and_prefixes(self) -> None:
        paths = [
            "/mnt/data",
            "/media/usb",
            "/Volumes/Backup",
            "/private/tmp/build",
            "/tmp/build",
            "/var/folders/xy/T",
            "/var/tmp/build",
            "/run/user/1000",
            "/cygdrive/c/Users/alice",
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/nix/store/abc",
            "/snap/core",
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(matched_text(f'"{path}"'), [path])

    def test_detects_file_urls(self) -> None:
        self.assertEqual(
            matched_text('"file:///home/alice/project"'),
            ["file:///home/alice/project"],
        )

    def test_detects_windows_drive_paths(self) -> None:
        paths = [
            "C:/Windows/User/xxx",
            r"C:\Users\alice",
            r"D:\data",
            r"C:\\Users\\alice",
        ]

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(matched_text(f'"{path}"'), [path])

    def test_detects_unc_paths(self) -> None:
        self.assertTrue(matched_text(r'"\\server\share\file"'))
        self.assertTrue(matched_text(r'"\\\\server\\share"'))

    def test_detects_multiple_matches_with_locations(self) -> None:
        source = 'one\nlet a = "/home/alice/a"; let b = "C:/Windows/User/b";\n'

        matches = find_absolute_paths(source)

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].line, 2)
        self.assertEqual(matches[0].column, 10)
        self.assertEqual(matches[0].text, "/home/alice/a")
        self.assertEqual(matches[1].line, 2)
        self.assertEqual(matches[1].text, "C:/Windows/User/b")

    def test_ignores_relative_paths_urls_and_routes(self) -> None:
        source = "\n".join(
            [
                "https://example.com/home/alice",
                "https://example.com/Users/alice",
                "ftp://example.com/tmp/build",
                "https://example.com/#/home/alice",
                "./home/alice",
                "../Users/alice",
                "src/home/alice",
                "*/home/alice",
                "~/home/alice",
                '"/api/v1/users"',
                '"/homepage"',
                '"/rooted"',
                '"/UsersGuide"',
                '"/data/project"',
            ]
        )

        self.assertEqual(find_absolute_paths(source), [])

    def test_ignores_non_host_specific_system_paths(self) -> None:
        source = "\n".join(
            [
                '#!/usr/bin/env python3',
                '"/usr/bin/env"',
                '"/etc/hosts"',
                '"/dev/null"',
            ]
        )

        self.assertEqual(find_absolute_paths(source), [])

    def test_checks_all_file_types(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            paths = [
                root / "sample.txt",
                root / "sample.yaml",
                root / "sample.json",
                root / "Dockerfile",
            ]
            for path in paths:
                path.write_text('path: "/home/alice/project"\n', encoding="utf-8")

            violations = check_paths(paths)

        self.assertEqual([violation.path for violation in violations], paths)

    def test_skips_binary_files(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "image.png"
            path.write_bytes(b"\x89PNG\x00/home/alice\n")

            self.assertEqual(check_paths([path]), [])

    def test_ignores_missing_files(self) -> None:
        self.assertEqual(check_paths([Path("missing.txt")]), [])

    def test_main_reports_violations_and_fails(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "config.yaml"
            path.write_text('root: "/home/alice/project"\n', encoding="utf-8")
            output = StringIO()

            with redirect_stdout(output):
                exit_code = main([str(path)])

        self.assertEqual(exit_code, 1)
        self.assertIn(f"{path}:1:8: /home/alice/project", output.getvalue())
        self.assertIn("Hint:", output.getvalue())

    def test_main_succeeds_without_violations(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "config.yaml"
            path.write_text('root: "src/project"\n', encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = main([str(path)])

        self.assertEqual(exit_code, 0)

    def test_main_can_forbid_additional_roots(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp) / "config.yaml"
            path.write_text('root: "/data/project"\n', encoding="utf-8")

            with redirect_stdout(StringIO()):
                default_code = main([str(path)])
            with redirect_stdout(StringIO()):
                custom_code = main(["--root", "/data", str(path)])

        self.assertEqual(default_code, 0)
        self.assertEqual(custom_code, 1)

    def test_main_rejects_invalid_root(self) -> None:
        output = StringIO()

        with redirect_stdout(output), redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                main(["--root", "relative", "config.yaml"])

        self.assertEqual(error.exception.code, 2)
        self.assertIn("must start with '/'", output.getvalue())


if __name__ == "__main__":
    unittest.main()
