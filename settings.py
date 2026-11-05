"""Validated per-user preferences. No writes beside the executable."""

import json
import os
from pathlib import Path

from core import normalize_shortcut

DEFAULTS = {"shortcut": "ctrl+q"}


def config_path():
    base = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return base / "InputLock" / "settings.json"


def load_config(path=None):
    path = Path(path) if path else config_path()
    config = DEFAULTS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        config["shortcut"] = normalize_shortcut(data.get("shortcut", DEFAULTS["shortcut"]))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return config


def save_config(config, path=None):
    path = Path(path) if path else config_path()
    data = {"shortcut": normalize_shortcut(config["shortcut"])}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
