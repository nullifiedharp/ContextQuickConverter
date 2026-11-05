# QuickConvert - right-click file converter for Windows
# Copyright (C) 2026 NullHarp
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE
# file or <https://www.gnu.org/licenses/> for details.

# PyInstaller build spec.  Build with:  pyinstaller QuickConvert.spec --noconfirm
# Produces dist\QuickConvert\QuickConvert.exe (a folder build, so it starts
# instantly - a single-file .exe would unpack ~80 MB of ffmpeg on every click).
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], ["win32com.client", "pythoncom", "pywintypes"]
for pkg in ("imageio_ffmpeg", "pillow_heif"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas + [("assets/icon.ico", "assets"), ("LICENSE", ".")],
    hiddenimports=hiddenimports,
    excludes=["numpy", "scipy", "cv2", "pandas", "matplotlib", "pytest", "IPython", "PyQt5", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuickConvert",
    icon="assets/icon.ico",
    console=False,          # no black console window when converting
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="QuickConvert")
