# -*- mode: python ; coding: utf-8 -*-
# Builds dist/wavvie.exe on Windows and dist/wavvie on Linux:
#     python -m PyInstaller --clean --noconfirm Wavefeed.spec
import sys


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/loubag-regular-1782520865-0.zip', 'resources'),
        ('resources/loubag-ultralight-1782520861-0.zip', 'resources'),
        ('resources/Agrandir-Font-Family.zip', 'resources'),
        ('resources/wavvie_wordmark.svg', 'resources'),
        ('resources/wavvie_mark_256.png', 'resources'),
        ('resources/wavvie_mark_128.png', 'resources'),
        ('resources/wavvie_mark_64.png', 'resources'),
        ('resources/wavvie_mark_48.png', 'resources'),
        ('resources/wavvie_mark_32.png', 'resources'),
        ('resources/wavvie_mark_16.png', 'resources'),
        ('resources/checkmark.svg', 'resources'),
        ('resources/chevron_down.svg', 'resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wavvie',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='resources/wavvie.ico' if sys.platform == 'win32' else None,  # the .exe's own icon; Linux has none
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
