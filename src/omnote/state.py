# src/omnote/state.py (drop-in)
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from gi.repository import GLib  # type: ignore

APP_DIR_OLD = "micropad"
APP_DIR_NEW = "omnote"

CONF_BASE = Path(GLib.get_user_config_dir())  # type: ignore
CONF_OLD = CONF_BASE / APP_DIR_OLD
CONF_NEW = CONF_BASE / APP_DIR_NEW

STATE_OLD = CONF_OLD / "state.json"
STATE_NEW = CONF_NEW / "state.json"


def _migrate_once() -> None:
    """
    One-time, best-effort migration:
    - If old state exists and new state does not, copy old -> new.
    - No deletion; old files are left in place for safety.
    """
    try:
        if STATE_OLD.exists() and not STATE_NEW.exists():
            CONF_NEW.mkdir(parents=True, exist_ok=True)
            STATE_NEW.write_text(STATE_OLD.read_text())
    except Exception:
        # Silent best-effort; we’ll still be able to read from old on load()
        pass


@dataclass
class Geometry:
    width: int = 800
    height: int = 600
    maximized: bool = False
    x: int | None = None
    y: int | None = None


@dataclass
class State:
    path: str | None = None
    geometry: Geometry = field(default_factory=Geometry)

    @classmethod
    def load(cls) -> "State":
        _migrate_once()

        # Prefer new location; fall back to old if needed
        for f in (STATE_NEW, STATE_OLD):
            try:
                if f.exists():
                    data = json.loads(f.read_text())
                    geom = Geometry(**data.get("geometry", {}))
                    return cls(path=data.get("path"), geometry=geom)
            except Exception:
                # If corrupted, try the next option or return default
                continue
        return cls()

    def save(self) -> None:
        # Always save to the new location going forward
        CONF_NEW.mkdir(parents=True, exist_ok=True)
        data = {
            "path": self.path,
            "geometry": {
                "width": self.geometry.width,
                "height": self.geometry.height,
                "maximized": self.geometry.maximized,
                "x": self.geometry.x,
                "y": self.geometry.y,
            },
        }
        STATE_NEW.write_text(json.dumps(data, indent=2))
