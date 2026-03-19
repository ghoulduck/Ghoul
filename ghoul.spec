# -*- mode: python ; coding: utf-8 -*-
"""
ghoul.spec — PyInstaller spec for building Ghoul as a standalone executable.

Usage:
    pip install pyinstaller
    pyinstaller ghoul.spec

The resulting executable will be in dist/ghoul/ (one-dir) or dist/ghoul (one-file).
"""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT = os.path.abspath(os.path.dirname(SPECPATH))

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'ghoul'), 'ghoul'),
        (os.path.join(ROOT, 'requirements.txt'), '.'),
        (os.path.join(ROOT, 'README.md'), '.'),
        (os.path.join(ROOT, '.env.example'), '.'),
    ],
    hiddenimports=[
        'anthropic',
        'requests',
        'bs4',
        'yaml',
        'jsonlines',
        'ghoul',
        'ghoul.agent',
        'ghoul.backup',
        'ghoul.config',
        'ghoul.data_collector',
        'ghoul.evaluator',
        'ghoul.executor',
        'ghoul.fine_tuner',
        'ghoul.improver',
        'ghoul.memory',
        'ghoul.orchestrator',
        'ghoul.specialist',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ghoul',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ghoul',
)
