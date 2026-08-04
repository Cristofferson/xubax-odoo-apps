# -*- mode: python ; coding: utf-8 -*-
"""Empaquetado del agente para Windows.

`onedir` y no `onefile`, a propósito: con torch dentro, un `onefile` se
descomprime en un temporal en CADA arranque — son cientos de megabytes y varios
segundos antes de que la primera cámara levante, cada vez que la tienda
enciende la máquina. `onedir` arranca de inmediato y el instalador se encarga
de que el usuario nunca vea la carpeta.

`collect_all` sobre ultralytics y torch no es exceso de celo: ambos cargan
módulos y archivos de datos por nombre en tiempo de ejecución, así que el
análisis estático de PyInstaller no los ve y el binario compila bien y truena
al abrir la cámara — que es el peor momento posible para enterarse.
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for paquete in ("ultralytics", "torch", "torchvision", "cv2"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    # Los back-ends de imagen que ultralytics abre por nombre.
    "PIL._tkinter_finder",
    # yaml.CSafeLoader existe o no según cómo se instaló PyYAML; si falta, el
    # agente cae al loader de Python y no pasa nada — pero el import tiene que
    # estar para que no truene al resolverlo.
    "yaml",
]

a = Analysis(
    ["..\\analitix_agent.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Nada de esto se usa y todo pesa.
    excludes=["tkinter", "matplotlib", "pandas", "IPython", "notebook",
              "pytest", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="analitix-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX y torch no se llevan: DLLs corruptas al vuelo
    console=True,       # el técnico necesita ver el arranque cuando calibra
    icon="analitix.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="analitix-agent",
)
