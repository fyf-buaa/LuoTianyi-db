"""Schema validation tests for music knowledge base markdown files."""

import re

REQUIRED_SECTIONS = ["# ", "## ", "### 基本信息", "### 来源"]
BARE_URL = "https://www.bilibili.com/"


def _get_table_field(content: str, field_name: str) -> str | None:
    """Extract the value of a markdown table field by name.

    Looks for lines of the form ``| field_name | value |`` in the ### 基本信息
    section and returns the *value* part (stripped).
    """
    lines = content.splitlines()
    in_basic_info = False
    for line in lines:
        if line.strip() == "### 基本信息":
            in_basic_info = True
            continue
        if in_basic_info and line.startswith("##"):
            in_basic_info = False
            continue
        if in_basic_info and line.startswith("|") and len(line.split("|")) >= 3:
            parts = line.split("|")
            key = parts[1].strip()
            value = parts[2].strip() if len(parts) > 2 else ""
            if key == field_name:
                return value
    return None


# ── Required sections ──────────────────────────────────────────────────


def test_required_sections(sample_clean_file: str) -> None:
    """Verify a clean file contains all required markdown sections."""
    for section in REQUIRED_SECTIONS:
        assert section in sample_clean_file, f"Missing required section: {section}"


def test_source_section_present(sample_dirty_file: str) -> None:
    """Verify that even a dirty file contains the ### 来源 section."""
    assert "### 来源" in sample_dirty_file


# ── Missing / empty field detection ────────────────────────────────────


def test_missing_singer_detected(sample_dirty_file: str) -> None:
    """Verify the dirty file has an empty 演唱 field."""
    singer = _get_table_field(sample_dirty_file, "演唱")
    assert singer is not None, "演唱 field not found"
    assert singer == "", "Expected empty 演唱 field"


def test_missing_videoid_detected(sample_dirty_file: str) -> None:
    """Verify the dirty file's 视频ID field is empty (after cleanup adds missing rows)."""
    videoid = _get_table_field(sample_dirty_file, "视频ID")
    assert videoid is not None, "视频ID field should exist (cleanup adds missing rows)"
    assert videoid == "", "Expected 视频ID to be empty in dirty file"


def test_placeholder_detected(sample_dirty_file: str) -> None:
    """Verify the dirty file contains '暂无资料' placeholders."""
    assert "暂无资料" in sample_dirty_file


def test_bare_url_detected(sample_dirty_file: str) -> None:
    """Verify the dirty file contains a bare bilibili URL instead of a specific video link."""
    assert BARE_URL in sample_dirty_file
