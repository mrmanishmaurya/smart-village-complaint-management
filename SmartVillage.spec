# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('database', 'database'),
    ('smart_village.ico', '.'),
]

if os.path.exists('.env'):
    datas.append(('.env', '.'))

hiddenimports = [
    'sqlite3',
    'mysql.connector',
    'mysql.connector.locales',
    'mysql.connector.plugins',
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'pythonnet',
    'clr_loader',
    'jinja2',
    'werkzeug',
    'dotenv',
]

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SmartVillage',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='smart_village.ico',
)
