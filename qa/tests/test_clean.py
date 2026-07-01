"""Clean operations tests — placeholder stubs for future implementation (T2)."""

import pytest


@pytest.mark.skip(reason="Not yet implemented — Wave 2")
def test_placeholder_stripped() -> None:
    """Verify that '暂无资料' placeholders are removed from table fields."""
    content = "| 作词 | 暂无资料 |"
    expected = "| 作词 |  |"


@pytest.mark.skip(reason="Not yet implemented — Wave 2")
def test_heading_normalized() -> None:
    """Verify that non-standard headings are normalized to expected values."""
    content = "### 描述"
    expected = "### 歌曲背景"


@pytest.mark.skip(reason="Not yet implemented — Wave 2")
def test_bare_url_replaced() -> None:
    """Verify that bare bilibili URLs are flagged or replaced."""
    content = "https://www.bilibili.com/"
    expected = None  # Placeholder — exact behaviour TBD in Wave 2


@pytest.mark.skip(reason="Not yet implemented — Wave 2")
def test_empty_singer_filled() -> None:
    """Verify that empty 演唱 fields are filled with a fallback value."""
    content = "| 演唱 |  |"
    expected = "| 演唱 | 待补充 |"


@pytest.mark.skip(reason="Not yet implemented — Wave 2")
def test_missing_videoid_added() -> None:
    """Verify that a missing 视频ID field is flagged or added."""
    content = ""  # No 视频ID present
    expected = None  # Placeholder — exact behaviour TBD in Wave 2
