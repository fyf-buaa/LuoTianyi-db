"""Integration tests for bin/correct-refs.py transformation functions.

These tests actually import and run the correction functions from correct-refs.py
to verify they produce correct output on known fixtures.
"""

import sys
from pathlib import Path

import pytest

# Add bin/ to path so we can import correct-refs.py
BIN_DIR = Path(__file__).parent.parent.parent / "bin"
sys.path.insert(0, str(BIN_DIR))

# Sample content with a bare Chinese name in singer field (needs slug normalization)
CONTENT_WITH_BARE_CHINESE = """# music:test-song
## Test Song

### 基本信息
| 字段 | 值 |
|------|----|
| 曲名 | Test Song |
| P主 | creator:test-p |
| 演唱 | 洛天依 |
| 发行日期 | 2023-01-01 |
| 首发平台 | bilibili |
| 引擎 | vocaloid |
| 风格 | 流行 |
| 标签 | 独唱, VOCALOID |

### 创作团队
- **P主/作者**: test-p - A test producer

### 歌曲背景

Test description.

### 来源

- [bilibili](https://www.bilibili.com/)
"""

# Sample content with core:中文名 in singer field (needs slug mapping)
CONTENT_WITH_CORE_CHINESE = """# music:test-song2
## Test Song 2

### 基本信息
| 字段 | 值 |
|------|----|
| 曲名 | Test Song 2 |
| P主 | creator:test-p |
| 演唱 | core:洛天依 |
| 发行日期 | 2023-01-01 |
| 首发平台 | bilibili |
| 引擎 | vocaloid |
| 风格 | 流行 |
| 标签 | 独唱, VOCALOID |

### 创作团队
- **P主/作者**: test-p - A test producer

### 歌曲背景

Test description.

### 来源

- [bilibili](https://www.bilibili.com/)
"""


def _import_correct_refs():
    """Import correct_refs module via spec loader."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("correct_refs", 
        Path(__file__).parent.parent.parent / "bin" / "correct-refs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_correct_refs():
    """Verify correct-refs.py can be imported without errors."""
    mod = _import_correct_refs()
    assert hasattr(mod, "normalize_singer_prefix")
    assert hasattr(mod, "parse_basic_info_table")
    assert hasattr(mod, "_is_slug_like")


def test_normalize_singer_prefix_adds_core():
    """Verify bare Chinese name gets core: prefix."""
    mod = _import_correct_refs()
    result, changes = mod.normalize_singer_prefix(CONTENT_WITH_BARE_CHINESE)
    assert len(changes) > 0, "Should detect bare singer name"
    assert any("normalize_singer_prefix" in c for c in changes)


def test_parse_basic_info_table():
    """Verify table parsing extracts fields correctly."""
    mod = _import_correct_refs()
    fields = mod.parse_basic_info_table(CONTENT_WITH_BARE_CHINESE)
    assert fields.get("曲名") == "Test Song"
    assert fields.get("P主") == "creator:test-p"
    assert fields.get("演唱") == "洛天依"
    assert fields.get("发行日期") == "2023-01-01"


def test_extract_creator_slug():
    """Verify creator slug extraction from P主 field."""
    mod = _import_correct_refs()
    fields = mod.parse_basic_info_table(CONTENT_WITH_BARE_CHINESE)
    slug = mod.extract_creator_full(fields)
    assert slug == "creator:test-p"


def test_is_slug_like():
    """Verify slug detection logic."""
    mod = _import_correct_refs()
    assert mod._is_slug_like("test-p") == True
    assert mod._is_slug_like("qianyimohua") == True
    assert mod._is_slug_like("洛天依") == False


def test_has_cjk():
    """Verify CJK character detection."""
    mod = _import_correct_refs()
    assert mod._has_cjk("洛天依") == True
    assert mod._has_cjk("test-p") == False
