# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Exorcist onefile console exe.

Build:  python -m PyInstaller exorcist.spec
Output: dist/exorcist.exe
"""
import os

block_cipher = None

a = Analysis(
    [os.path.join('src', 'exorcist_main.py')],
    pathex=[os.path.abspath('src')],
    binaries=[],
    datas=[(os.path.join('src', 'exorcist', 'data', '*.yaml'), os.path.join('exorcist', 'data'))],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='exorcist',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)
