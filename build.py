"""Build the Windows portable executable with the active Python environment."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if os.name != "nt":
        raise SystemExit("O .exe deve ser compilado no Windows. Use o workflow Windows build no GitHub.")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                   cwd=ROOT, check=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--name=InputLock", "--onefile", "--windowed",
        "--clean", "--noconfirm", "--icon=assets/icon.ico", "--add-data=assets:assets",
        "--add-data=LICENSE:.", "--add-data=NOTICE:.", "--version-file=version_info.txt", "main.py",
    ], cwd=ROOT, check=True)
    print("Pronto: dist/InputLock.exe")


if __name__ == "__main__":
    main()
