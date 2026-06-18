import unittest

from cathaysia_style.qualify_tracing_macros import rewrite_source


class QualifyTracingMacrosTests(unittest.TestCase):
    def test_qualifies_macros_and_removes_macro_imports(self) -> None:
        source = "\n".join(
            [
                "use tracing::{debug, instrument, info};",
                "",
                "fn run() {",
                '    debug!("starting");',
                '    tracing::warn!("already qualified");',
                "}",
                "",
            ]
        )
        expected = "\n".join(
            [
                "use tracing::instrument;",
                "",
                "fn run() {",
                '    tracing::debug!("starting");',
                '    tracing::warn!("already qualified");',
                "}",
                "",
            ]
        )

        self.assertEqual(rewrite_source(source), expected)

    def test_removes_single_macro_import(self) -> None:
        self.assertEqual(rewrite_source("use tracing::info;\ninfo!();\n"), "tracing::info!();\n")


if __name__ == "__main__":
    unittest.main()
