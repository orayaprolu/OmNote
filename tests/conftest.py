"""Pytest configuration and fixtures for OmNote tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Provide a temporary config directory for state tests."""
    return tmp_path / "config"


@pytest.fixture
def mock_glib(temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch):
    """Mock GLib.get_user_config_dir to use temp directory."""
    mock_glib_module = MagicMock()
    mock_glib_module.get_user_config_dir.return_value = str(temp_config_dir)

    # Create a mock gi.repository module
    mock_gi = MagicMock()
    mock_gi.repository.GLib = mock_glib_module

    monkeypatch.setitem(sys.modules, "gi", mock_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", mock_gi.repository)
    monkeypatch.setitem(sys.modules, "gi.repository.GLib", mock_glib_module)

    return mock_glib_module
