"""Tests for omnote.state module."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def state_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Import state module with mocked GLib pointing to temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Mock GLib before importing state
    mock_glib = MagicMock()
    mock_glib.get_user_config_dir.return_value = str(config_dir)

    mock_gi_repository = MagicMock()
    mock_gi_repository.GLib = mock_glib

    monkeypatch.setitem(sys.modules, "gi.repository", mock_gi_repository)
    monkeypatch.setitem(sys.modules, "gi.repository.GLib", mock_glib)

    # Remove cached state module if present, then import fresh
    if "omnote.state" in sys.modules:
        del sys.modules["omnote.state"]

    from omnote import state

    # Patch the module-level constants after import
    monkeypatch.setattr(state, "CONF_BASE", config_dir)
    monkeypatch.setattr(state, "CONF_OLD", config_dir / "micropad")
    monkeypatch.setattr(state, "CONF_NEW", config_dir / "omnote")
    monkeypatch.setattr(state, "STATE_OLD", config_dir / "micropad" / "state.json")
    monkeypatch.setattr(state, "STATE_NEW", config_dir / "omnote" / "state.json")

    return state


class TestGeometry:
    """Tests for Geometry dataclass."""

    def test_default_values(self, state_module):
        """Geometry has sensible defaults."""
        geom = state_module.Geometry()
        assert geom.width == 800
        assert geom.height == 600
        assert geom.maximized is False
        assert geom.x is None
        assert geom.y is None

    def test_custom_values(self, state_module):
        """Geometry accepts custom values."""
        geom = state_module.Geometry(width=1920, height=1080, maximized=True, x=100, y=50)
        assert geom.width == 1920
        assert geom.height == 1080
        assert geom.maximized is True
        assert geom.x == 100
        assert geom.y == 50


class TestTabState:
    """Tests for TabState dataclass."""

    def test_default_values(self, state_module):
        """TabState has sensible defaults."""
        tab = state_module.TabState()
        assert tab.file_path is None
        assert tab.cursor_line == 0
        assert tab.cursor_col == 0
        assert tab.show_line_numbers is False
        assert tab.unsaved_content is None

    def test_with_file(self, state_module):
        """TabState can store file path and cursor position."""
        tab = state_module.TabState(
            file_path="/home/user/doc.txt",
            cursor_line=42,
            cursor_col=10,
            show_line_numbers=True,
        )
        assert tab.file_path == "/home/user/doc.txt"
        assert tab.cursor_line == 42
        assert tab.cursor_col == 10
        assert tab.show_line_numbers is True

    def test_with_unsaved_content(self, state_module):
        """TabState can store unsaved buffer content."""
        tab = state_module.TabState(unsaved_content="Hello, world!")
        assert tab.file_path is None
        assert tab.unsaved_content == "Hello, world!"


class TestState:
    """Tests for State dataclass and persistence."""

    def test_default_state(self, state_module):
        """Default state has empty tabs."""
        s = state_module.State()
        assert s.tabs == []
        assert s.active_tab_index == 0
        assert isinstance(s.geometry, state_module.Geometry)

    def test_load_returns_default_when_no_file(self, state_module):
        """State.load() returns default state when no state file exists."""
        s = state_module.State.load()
        assert s.tabs == []
        assert s.active_tab_index == 0

    def test_save_and_load_roundtrip(self, state_module):
        """State can be saved and loaded back."""
        original = state_module.State(
            tabs=[
                state_module.TabState(file_path="/path/to/file.txt", cursor_line=10, cursor_col=5),
                state_module.TabState(unsaved_content="Unsaved text"),
            ],
            active_tab_index=1,
            geometry=state_module.Geometry(width=1024, height=768, maximized=True),
        )
        original.save()

        loaded = state_module.State.load()
        assert len(loaded.tabs) == 2
        assert loaded.tabs[0].file_path == "/path/to/file.txt"
        assert loaded.tabs[0].cursor_line == 10
        assert loaded.tabs[0].cursor_col == 5
        assert loaded.tabs[1].unsaved_content == "Unsaved text"
        assert loaded.active_tab_index == 1
        assert loaded.geometry.width == 1024
        assert loaded.geometry.height == 768
        assert loaded.geometry.maximized is True

    def test_load_handles_corrupted_json(self, state_module):
        """State.load() returns default on corrupted JSON."""
        state_module.CONF_NEW.mkdir(parents=True, exist_ok=True)
        state_module.STATE_NEW.write_text("not valid json {{{")

        s = state_module.State.load()
        assert s.tabs == []

    def test_load_handles_invalid_active_index(self, state_module):
        """State.load() clamps invalid active_tab_index."""
        state_module.CONF_NEW.mkdir(parents=True, exist_ok=True)
        state_module.STATE_NEW.write_text(
            json.dumps(
                {
                    "tabs": [{"file_path": "/test.txt"}],
                    "active_tab_index": 999,  # Invalid - out of bounds
                    "geometry": {},
                }
            )
        )

        s = state_module.State.load()
        assert s.active_tab_index == 0  # Should be clamped to valid index

    def test_load_handles_negative_active_index(self, state_module):
        """State.load() clamps negative active_tab_index."""
        state_module.CONF_NEW.mkdir(parents=True, exist_ok=True)
        state_module.STATE_NEW.write_text(
            json.dumps(
                {
                    "tabs": [{"file_path": "/test.txt"}],
                    "active_tab_index": -5,
                    "geometry": {},
                }
            )
        )

        s = state_module.State.load()
        assert s.active_tab_index == 0

    def test_migration_from_old_location(self, state_module):
        """State migrates from old micropad location."""
        # Create state in old location
        state_module.CONF_OLD.mkdir(parents=True, exist_ok=True)
        old_data = {
            "tabs": [{"file_path": "/old/file.txt", "cursor_line": 5}],
            "active_tab_index": 0,
            "geometry": {"width": 900, "height": 700},
        }
        state_module.STATE_OLD.write_text(json.dumps(old_data))

        # Load should find old state and migrate
        s = state_module.State.load()
        assert len(s.tabs) == 1
        assert s.tabs[0].file_path == "/old/file.txt"
        assert s.geometry.width == 900

        # New state file should now exist
        assert state_module.STATE_NEW.exists()

    def test_migration_from_single_path_format(self, state_module):
        """State migrates from old single-file 'path' format."""
        state_module.CONF_OLD.mkdir(parents=True, exist_ok=True)
        old_data = {
            "path": "/legacy/single/file.txt",  # Old format used "path" not "tabs"
            "geometry": {},
        }
        state_module.STATE_OLD.write_text(json.dumps(old_data))

        s = state_module.State.load()
        assert len(s.tabs) == 1
        assert s.tabs[0].file_path == "/legacy/single/file.txt"
