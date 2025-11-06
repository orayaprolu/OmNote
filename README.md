# MicroPad
A tiny, plain-text notepad for Omarchy (GTK4 + libadwaita). Lean UI, NASA-ish code hygiene.

## Arch runtime
sudo pacman -S python python-gobject gtk4 libadwaita

## Dev setup
python -m venv .venv && source .venv/bin/activate
pip install ruff mypy pytest

## Run
make run

## Checks
make lint type test

Shortcuts:
- Ctrl+F (find), F3 / Shift+F3 (next/prev)
- Ctrl+H (replace row), Replace / Replace All
- Ctrl+S / Ctrl+Shift+S / Ctrl+N / Ctrl+O / Ctrl+Q

Paths:
- Config: ~/.config/omnote/state.json
- Autosave: ~/.cache/omnote/autosave.txt
