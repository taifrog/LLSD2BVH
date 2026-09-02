# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for LLSD2BVH GUI (onedir, windowed)
# Build: pyinstaller LLSD2BVH.spec  or  powershell -ExecutionPolicy Bypass -File tools/build_exe.ps1

datas = [('avatar_skeleton.xml', '.')]
binaries = []
hiddenimports = [
    'PySide6.QtXml',
    'llsd2bvh.llsd_parser', 'llsd2bvh.skeleton', 'llsd2bvh.bvh_writer', 'llsd2bvh.euler_math',
    'llsd2bvh.timeline', 'llsd2bvh.widgets.timeline_view', 'llsd2bvh.i18n',
]

a = Analysis(
    ['tools/entry_gui.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras', 'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic', 'PySide6.Qt3DRender', 'PySide6.QtAxContainer', 'PySide6.QtBluetooth',
        'PySide6.QtCharts', 'PySide6.QtConcurrent', 'PySide6.QtDataVisualization', 'PySide6.QtDBus',
        'PySide6.QtDesigner', 'PySide6.QtGraphs', 'PySide6.QtHelp', 'PySide6.QtHttpServer',
        'PySide6.QtLocation', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtNetworkAuth',
        'PySide6.QtNfc', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtQuick', 'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2', 'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
        'PySide6.QtSensors', 'PySide6.QtSerialBus', 'PySide6.QtSerialPort', 'PySide6.QtSpatialAudio',
        'PySide6.QtSql', 'PySide6.QtStateMachine', 'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtTest',
        'PySide6.QtTextToSpeech', 'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebSockets', 'PySide6.QtWebView',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LLSD2BVH',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LLSD2BVH',
)
