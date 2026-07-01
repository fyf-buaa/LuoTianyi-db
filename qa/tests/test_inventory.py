"""Inventory output tests — requires qa/inventory.json and qa/summary.json."""

import json
from pathlib import Path

import pytest


@pytest.mark.skip(reason="Not yet implemented — inventory generator not built")
def test_inventory_output_exists(qa_dir: Path) -> None:
    """Check that qa/inventory.json and qa/summary.json exist."""
    inventory = qa_dir / "inventory.json"
    summary = qa_dir / "summary.json"
    assert inventory.exists(), f"Missing {inventory}"
    assert summary.exists(), f"Missing {summary}"


@pytest.mark.skip(reason="Not yet implemented — inventory generator not built")
def test_inventory_has_all_files(qa_dir: Path, music_dir: Path) -> None:
    """Verify inventory.json has entries for every .md file in music/."""
    inventory_path = qa_dir / "inventory.json"
    inventory: dict = json.loads(inventory_path.read_text(encoding="utf-8"))

    music_files = sorted(f.name for f in music_dir.glob("*.md"))
    inventory_keys = sorted(inventory.keys())

    assert inventory_keys == music_files, (
        f"Inventory keys mismatch.\n"
        f"  Missing from inventory: {set(music_files) - set(inventory_keys)}\n"
        f"  Extra in inventory:    {set(inventory_keys) - set(music_files)}"
    )


@pytest.mark.skip(reason="Not yet implemented — inventory generator not built")
def test_inventory_entry_structure(qa_dir: Path) -> None:
    """Verify each inventory entry has the required keys."""
    inventory_path = qa_dir / "inventory.json"
    inventory: dict = json.loads(inventory_path.read_text(encoding="utf-8"))

    required_keys = {"title", "slug", "path", "singer", "p主", "av号", "status"}

    for filename, entry in inventory.items():
        missing = required_keys - set(entry.keys())
        assert not missing, f"Entry '{filename}' missing keys: {missing}"
