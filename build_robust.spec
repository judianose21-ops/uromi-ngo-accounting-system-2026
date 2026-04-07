# -*- mode: python ; coding: utf-8 -*-
# Robust PyInstaller spec file for NGO Accounting System
# Build command: pyinstaller build_robust.spec --clean

import os
import sys
from pathlib import Path

block_cipher = None

# Get the base directory
base_dir = Path(__file__).resolve().parent

a = Analysis(
    ['main.py'],
    pathex=[str(base_dir)],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('templates', 'templates'),
        ('ngo.db', '.'),  # Include database if it exists
    ],
    hiddenimports=[
        'passlib.handlers.bcrypt',
        'bcrypt',
        'fastapi',
        'uvicorn',
        'jinja2',
        'starlette',
        'pydantic',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'numpy',
        'scipy',
        'PIL',
        'pytest',
        'unittest',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='UROMI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UROMI'
)
