"""Build an extracted installation bundle and a single-file portable executable."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def build_command(mode):
    if mode not in ("installed", "portable"):
        raise ValueError("Unknown build mode")
    return [
        sys.executable, "-m", "PyInstaller", "--name=InputLock",
        "--onedir" if mode == "installed" else "--onefile", "--windowed",
        "--clean", "--noconfirm", "--noupx", f"--workpath=build/{mode}",
        "--distpath=dist",
        "--icon=assets/icon.ico", "--add-data=assets/icon.png:assets",
        "--add-data=assets/icon.ico:assets", "--add-data=assets/keyboard.png:assets",
        "--add-data=assets/mouse.png:assets",
        "--collect-data=customtkinter", "--copy-metadata=customtkinter",
        "--copy-metadata=Pillow", "--copy-metadata=darkdetect", "--copy-metadata=packaging", "--add-data=LICENSE:.", "--add-data=NOTICE:.",
        "--version-file=version_info.txt", "main.py",
    ]


def main():
    if os.name != "nt":
        raise SystemExit("O .exe deve ser compilado no Windows. Use o workflow Windows build no GitHub.")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                   cwd=ROOT, check=True)
    for mode in ("installed", "portable"):
        subprocess.run(build_command(mode), cwd=ROOT, check=True)
    print("Instalador: dist/InputLock/InputLock.exe | Portátil: dist/InputLock.exe")


if __name__ == "__main__":
    main()
