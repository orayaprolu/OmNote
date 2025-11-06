from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from gi.repository import GLib  # type: ignore


CONF_DIR = Path(GLib.get_user_config_dir()) / "micropad"  # type: ignore
STATE_FILE = CONF_DIR / "state.json"


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
        try:
            data = json.loads(STATE_FILE.read_text())
            geom_data = data.get("geometry", {})
            geom = Geometry(**geom_data)
            return cls(path=data.get("path"), geometry=geom)
        except Exception:
            return cls()

    def save(self) -> None:
        CONF_DIR.mkdir(parents=True, exist_ok=True)
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
        STATE_FILE.write_text(json.dumps(data, indent=2))
