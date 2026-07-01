"""Shared fixtures for the QA test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_clean_file() -> str:
    """Return the content of a known clean music file (all fields present)."""
    path = Path(__file__).parent.parent.parent / "music" / "10from-bottom-to-the-top.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_dirty_file() -> str:
    """Return the content of a known dirty music file (missing fields, bare URL)."""
    path = Path(__file__).parent.parent.parent / "suspicious_music" / "4-one-punch-ling.md"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def music_dir() -> Path:
    """Return the path to the music/ directory."""
    return Path(__file__).parent.parent.parent / "music"


@pytest.fixture
def qa_dir() -> Path:
    """Return the path to the qa/ directory."""
    return Path(__file__).parent.parent
