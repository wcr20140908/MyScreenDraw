# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pynput")

analysis = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    # GPL 合规：发行包必须随附许可证与第三方组件声明（见 docs/provenance-audit.md）
    datas=[("LICENSE", "."), ("THIRD_PARTY_LICENSES.txt", ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MyScreenDraw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # upx=False：UPX 压缩壳是杀软误报 PyInstaller 程序的头号原因
    # （引擎匹配 UPX 特征而非业务代码）；关闭后体积略增但大幅降低误报率
    upx=False,
    console=False,
    version="version_info.txt",
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="MyScreenDraw",
)
