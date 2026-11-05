"""Validated per-user preferences. No writes beside the executable."""

import json
import os
from pathlib import Path

from core import normalize_shortcut

DEFAULTS = {"shortcut": "ctrl+q", "duration": 60, "delay": 3}
DURATIONS = {"Sem limite": 0, "30 segundos": 30, "1 minuto": 60,
             "5 minutos": 300, "15 minutos": 900}


def config_path():
    base = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return base / "InputLock" / "settings.json"


def load_config(path=None):
    path = Path(path) if path else config_path()
    config = DEFAULTS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        config["shortcut"] = normalize_shortcut(data.get("shortcut", DEFAULTS["shortcut"]))
        if type(data.get("duration")) is int and data["duration"] in DURATIONS.values():
            config["duration"] = data["duration"]
        if type(data.get("delay")) is int and data["delay"] in (0, 3, 5):
            config["delay"] = data["delay"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return config


def save_config(config, path=None):
    path = Path(path) if path else config_path()
    data = {"shortcut": normalize_shortcut(config["shortcut"]),
            "duration": config["duration"], "delay": config["delay"]}
    if data["duration"] not in DURATIONS.values() or data["delay"] not in (0, 3, 5):
        raise ValueError("Tempo inválido.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
