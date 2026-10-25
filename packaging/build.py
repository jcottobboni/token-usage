"""Gera os executáveis com PyInstaller em dist/: python packaging/build.py

Precisa de `pip install pyinstaller` e, para incluir o ícone, `pip install pystray Pillow`.
No Windows gera também o token-usage-tray.exe, sem janela de console.
"""
import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "token_usage"
# os arquivos estáticos ficam ao lado do server.py, onde o HERE do servidor procura
DATA = [f"--add-data={PKG / src}{os.pathsep}{dest}" for src, dest in
        (("index.html", "token_usage"), ("app.js", "token_usage"), ("vendor", "token_usage/vendor"))]
# o pystray escolhe o backend em tempo de execução; o PyInstaller não enxerga o import
BACKEND = {"win32": "pystray._win32", "darwin": "pystray._darwin"}.get(sys.platform)


def build(name: str, entry: Path, windowed: bool = False):
    args = ["--onefile", "--noconfirm", "--clean", f"--name={name}", f"--paths={ROOT}",
            f"--distpath={ROOT / 'dist'}", f"--workpath={ROOT / 'build'}", f"--specpath={ROOT / 'build'}", *DATA]
    if BACKEND:
        args.append(f"--hidden-import={BACKEND}")
    if windowed:
        args.append("--windowed")
    PyInstaller.__main__.run([*args, str(entry)])


if __name__ == "__main__":
    build("token-usage", PKG / "__main__.py")
    if sys.platform == "win32":
        build("token-usage-tray", ROOT / "packaging" / "tray_entry.py", windowed=True)
