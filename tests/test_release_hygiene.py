"""Release hygiene and version consistency checks."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_is_stable_release(self):
        from version import VERSION, APP_VERSION
        self.assertEqual(VERSION, "5.5.0")
        self.assertEqual(APP_VERSION, "v5.5.0")

    def test_version_info_resource_matches_version_py(self):
        """version_info.txt 里的四处版本必须和 version.py 一致。

        这条是补上一个真实的漏洞：升版时要手改 version.py、version_info.txt 的
        filevers/prodvers 两个元组和 FileVersion/ProductVersion 两个字符串、
        build.ps1 的门禁，一共五处。漏掉任何一处都不会有任何报错——程序照样跑、
        照样打包，只是资源管理器里显示旧版本号。所以让测试来核对，而不是靠记性。
        """
        from version import VERSION
        text = (ROOT / "version_info.txt").read_text(encoding="utf-8")
        major, minor, patch = (int(p) for p in VERSION.split("."))
        for field in ("filevers", "prodvers"):
            with self.subTest(field=field):
                self.assertIn(f"{field}=({major}, {minor}, {patch}, 0)", text)
        for field in ("FileVersion", "ProductVersion"):
            with self.subTest(field=field):
                self.assertIn(f"StringStruct('{field}', '{VERSION}.0')", text)

    def test_build_gate_matches_version_py(self):
        """build.ps1 的版本门禁必须盯着当前版本，否则发布构建会直接被自己拦下来。"""
        from version import VERSION
        text = (ROOT / "build.ps1").read_text(encoding="utf-8")
        self.assertIn(f'$version -ne "{VERSION}"', text)

    def test_readmes_advertise_current_version(self):
        """两份 README 顶部的「当前版本」必须是当前版本。

        用户第一眼看到的就是这一行；它停在旧版本上，等于对着新功能说自己是旧程序。

        必须锚定到那一行本身，不能只查「文件里出现过当前版本号」——CHANGELOG 的
        条目、下载链接里都会出现版本号，那样的断言在这一行明明还停在旧版本时也照样
        通过（这条正是变异测试里唯一存活下来的那个，改法就是把锚点收紧到句式上）。
        """
        from version import APP_VERSION
        patterns = {
            "README.md": re.compile(r"当前版本 \*\*(v[\d.]+)\*\*"),
            "README.en.md": re.compile(r"Current version \*\*(v[\d.]+)\*\*"),
        }
        for name, pattern in patterns.items():
            with self.subTest(name=name):
                found = pattern.findall((ROOT / name).read_text(encoding="utf-8"))
                self.assertTrue(found, f"{name} 里找不到「当前版本」那一行")
                for value in found:
                    self.assertEqual(value, APP_VERSION)

    def test_changelog_documents_current_version(self):
        """CHANGELOG 必须有当前版本的条目，且标着「当前」。"""
        from version import VERSION
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## v{VERSION}（当前）", text)

    def test_offline_claims_are_not_absolute(self):
        """文档不能再声称「完全离线 / 无更新服务 / 不写注册表」。

        v5.5.0 加了手动检查更新（默认关）和开机自启（写 HKCU\\...\\Run，默认关）。
        这两件事都是用户自己打开才发生的，但只要代码里存在这两条路径，
        「完全离线」「不内置更新服务」「不写注册表」就是不实描述——
        而这些话恰恰是用来安抚在意隐私的用户的，说错了性质最严重。
        """
        banned = ["完全离线", "无更新服务", "不内置更新服务", "不写注册表",
                  "no update service", "no registry changes"]
        for name in ("README.md", "README.en.md", "SECURITY.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in banned:
                with self.subTest(name=name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_docs_disclose_both_opt_in_exceptions(self):
        """反过来，两处例外必须写清楚：出网的地址，和注册表的位置。"""
        for name in ("README.md", "README.en.md", "SECURITY.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(name=name, what="update endpoint"):
                self.assertIn("api.github.com", text)
            with self.subTest(name=name, what="registry path"):
                self.assertIn(r"CurrentVersion\Run", text)

    def test_no_beta_references_remain_in_release_sources(self):
        paths = [
            ROOT / "version.py", ROOT / "main.py", ROOT / "README.md",
            ROOT / "README.en.md", ROOT / "SECURITY.md", ROOT / "CHANGELOG.md",
            ROOT / "docs" / "provenance-audit.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertNotIn("5.4.0-" + "beta", path.read_text(encoding="utf-8"))

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
