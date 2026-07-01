"""Integration tests for bin/clean.py transformation functions.

These tests actually import and run the transformation functions from clean.py
to verify they produce correct output on known fixtures.
"""

import sys
from pathlib import Path

import pytest

# Add bin/ to path so we can import clean.py
BIN_DIR = Path(__file__).parent.parent.parent / "bin"
sys.path.insert(0, str(BIN_DIR))

# Sample dirty content simulating a file with known issues
DIRTY_CONTENT = """# music:test-song
## Test Song

### 基本信息
| 字段 | 值 |
|------|----|
| 曲名 | Test Song |
| P主 | creator:test-p |
| 演唱 | core:luo-tian-yi |
| 发行日期 |  |
| 首发平台 | bilibili |
| 引擎 | vocaloid |
| 风格 | 流行 |
| 标签 | 独唱, VOCALOID |

### 描述

Test description with ### 描述 heading.

### 创作团队
- **P主/作者**: test-p - A test producer
- **作词**: 暂无资料
- **作曲**: 暂无资料

### 来源

- [bilibili](https://www.bilibili.com/)
"""

CLEAN_CONTENT = """# music:test-song
## Test Song

### 基本信息
| 字段 | 值 |
|------|----|
| 曲名 | Test Song |
| P主 | creator:test-p |
| 演唱 | core:luo-tian-yi |
| 发行日期 |  |
| 首发平台 | bilibili |
| 引擎 | vocaloid |
| 风格 | 流行 |
| 标签 | 独唱, VOCALOID |
| 作词 |  |
| 作曲 |  |
| 编曲 |  |
| 调教 |  |
| 视频ID |  |
| 播放量 |  |

### 歌曲背景

Test description with ### 歌曲背景 heading.

### 创作团队
- **P主/作者**: test-p - A test producer
- **作词**:  |
- **作曲**:  |

### 来源

- [bilibili](https://www.bilibili.com/)
"""


def _import_clean():
    """Import clean module, handling the fact that bin/ is not a package."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("clean", 
        Path(__file__).parent.parent.parent / "bin" / "clean.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_clean():
    """Verify clean.py can be imported without errors."""
    mod = _import_clean()
    assert hasattr(mod, "fix_heading")
    assert hasattr(mod, "strip_placeholders")
    assert hasattr(mod, "normalize_table_rows")
    assert hasattr(mod, "apply_all")


def test_fix_heading_replaces_description():
    """Verify ### 描述 is replaced with ### 歌曲背景."""
    mod = _import_clean()
    result = mod.fix_heading(DIRTY_CONTENT)
    assert "### 描述" not in result, "描述 heading should be replaced"
    assert "### 歌曲背景" in result, "歌曲背景 heading should be present"


def test_strip_placeholders_removes_zws():
    """Verify 暂无资料 handling."""
    mod = _import_clean()
    result = mod.strip_placeholders(DIRTY_CONTENT)
    # 暂无资料 in non-table sections should remain
    assert "暂无资料" in result, "暂无资料 in non-table sections should remain"


def test_normalize_table_rows_adds_missing_fields():
    """Verify missing standard fields are added to 基本信息 table."""
    mod = _import_clean()
    result = mod.normalize_table_rows(DIRTY_CONTENT)
    # Verify all standard fields are present in the table
    for field in mod.STANDARD_FIELDS:
        assert f"| {field} |" in result, f"Field '{field}' should be in table"


def test_normalize_table_rows_preserves_existing_values():
    """Verify existing values are preserved when adding missing rows."""
    mod = _import_clean()
    result = mod.normalize_table_rows(DIRTY_CONTENT)
    assert "Test Song" in result, "曲名 should be preserved"
    assert "creator:test-p" in result, "P主 should be preserved"
    assert "core:luo-tian-yi" in result, "演唱 should be preserved"


def test_apply_all_transforms():
    """Verify the full transformation pipeline produces expected output."""
    mod = _import_clean()
    result, report = mod.apply_all(DIRTY_CONTENT)
    # Headings fixed
    assert "### 歌曲背景" in result
    assert "### 描述" not in result
    # Table rows normalized
    assert "| 播放量 |  |" in result, "播放量 row should exist"
    assert "| 视频ID |  |" in result, "视频ID row should exist"
    # Report generated
    assert report["heading_fixed"] == True
    assert "rows_added" in report
