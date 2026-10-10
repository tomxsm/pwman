"""Paths and settings shared by all modules."""
import sys
from pathlib import Path

# Folder next to main.py (or next to the .exe once packaged with PyInstaller)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

def resource_path(name: str) -> Path:
    """Path to a bundled file (works from source and inside a PyInstaller .exe)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


ICON_PATH = resource_path("pwman.ico")

DATA_DIR = APP_DIR / "vault"
DATA_DIR.mkdir(exist_ok=True)

SALT_PATH = DATA_DIR / "salt.bin"
DB_PATH = DATA_DIR / "passwords.db"

KDF_ITERATIONS = 600_000
CLIPBOARD_CLEAR_MS = 30_000   # clear clipboard 30 seconds after copying
MIN_MASTER_LENGTH = 12