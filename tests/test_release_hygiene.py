"""Release hygiene and version consistency checks."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_is_stable_release(self):
        from version import VERSION, APP_VERSION
        self.assertEqual(VERSION, "5.2.2")
        self.assertEqual(APP_VERSION, "v5.2.2")

    def test_no_beta_references_remain_in_release_sources(self):
        paths = [
            ROOT / "version.py", ROOT / "main.py", ROOT / "README.md",
            ROOT / "README.en.md", ROOT / "SECURITY.md", ROOT / "CHANGELOG.md",
            ROOT / "docs" / "provenance-audit.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn("5.2.2-" + "beta", path.read_text(encoding="utf-8"))

    def test_documentation_links_resolve(self):
        markdown_paths = list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md"))
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
        for source in markdown_paths:
            text = source.read_text(encoding="utf-8")
            for target in link_pattern.findall(text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                with self.subTest(source=source.name, target=target):
                    self.assertTrue((source.parent / target).resolve().exists())


if __name__ == "__main__":
    unittest.main()
