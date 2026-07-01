"""Inventory scanner for music knowledge base.

Scans all .md files in ./music/, parses the "基本信息" markdown table,
and produces two JSON files:
  - qa/inventory.json — per-file metrics
  - qa/summary.json  — aggregated statistics

Usage:
    python bin/inventory.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────
MUSIC_DIR = Path(__file__).resolve().parent.parent / "music"
QA_DIR = Path(__file__).resolve().parent.parent / "qa"
INVENTORY_PATH = QA_DIR / "inventory.json"
SUMMARY_PATH = QA_DIR / "summary.json"

TABLE_FIELDS = [
    "曲名",
    "P主",
    "演唱",
    "发行日期",
    "首发平台",
    "引擎",
    "风格",
    "标签",
    "视频ID",
    "播放量",
]

# Set of bare bilibili base URLs (without any video path).
BARE_BILIBILI_URLS = frozenset({
    "https://www.bilibili.com/",
    "https://www.bilibili.com",
    "http://www.bilibili.com/",
    "http://www.bilibili.com",
})

HEADING_SOURCE = "### 来源"
HEADING_BACKGROUND = "### 歌曲背景"
HEADING_WRONG = "### 描述"
HEADING_BASIC_INFO = "### 基本信息"


def parse_table_fields(content: str) -> dict[str, str]:
    """Extract key-value pairs from the ``### 基本信息`` markdown table.

    Returns a dict mapping field name -> value (stripped).  Fields that
    appear in the table with an empty value get an empty string.  Fields
    that are not found at all are omitted.
    """
    fields: dict[str, str] = {}
    in_basic_info = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == HEADING_BASIC_INFO:
            in_basic_info = True
            continue

        # A new heading of the same or higher level ends the section.
        if in_basic_info and stripped.startswith("##"):
            in_basic_info = False
            continue

        if in_basic_info and stripped.startswith("|") and stripped.endswith("|"):
            # Split on | and extract parts 1 (key) and 2 (value)
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 3:
                key = parts[1]
                if key and key != "---":  # skip table header separator: |------|----|
                    value = parts[2] if len(parts) > 2 else ""
                    fields[key] = value

    return fields


def get_table_field(fields: dict[str, str], name: str) -> str | None:
    """Return the field value, or None if the field is absent."""
    return fields.get(name, None)


def has_table_field_nonempty(fields: dict[str, str], name: str) -> bool:
    """Return True if the field exists and has a non-empty value."""
    val = fields.get(name)
    return val is not None and val != ""


def find_source_urls(content: str) -> list[str]:
    """Extract all source URLs from the ``### 来源`` section."""
    urls: list[str] = []
    in_source = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == HEADING_SOURCE:
            in_source = True
            continue
        if in_source:
            # Stop at the next heading of any level
            if stripped.startswith("#"):
                break
            # Look for markdown links: [text](url) or bare URLs
            link_match = re.search(r"\]\(([^)]+)\)", stripped)
            if link_match:
                urls.append(link_match.group(1))
            else:
                # Check if the line itself looks like a URL
                url_match = re.search(
                    r"https?://[^\s]+", stripped
                )
                if url_match:
                    urls.append(url_match.group(0))

    return urls


def extract_creator_slug(fields: dict[str, str]) -> str | None:
    """Extract the creator slug from the ``P主`` field.

    Format is ``creator:<slug>``.  Returns the slug or None.
    """
    val = fields.get("P主")
    if val and val.startswith("creator:"):
        return val[len("creator:"):]
    return None


def extract_singer_field(fields: dict[str, str]) -> str | None:
    """Return the raw 演唱 field value, or None if absent/empty."""
    val = fields.get("演唱")
    if val and val.strip():
        return val.strip()
    return None


def extract_slug(filepath: Path) -> str:
    """Extract the slug from the first line ``# music:<slug>``.

    Falls back to the filename stem if the header is missing or malformed.
    """
    try:
        with open(filepath, encoding="utf-8-sig") as fh:
            first_line = fh.readline().strip()
        if first_line.startswith("# music:"):
            return first_line[len("# music:"):].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return filepath.stem


def has_wrong_heading(content: str) -> bool:
    """Check if ``### 描述`` is used instead of ``### 歌曲背景``."""
    return HEADING_WRONG in content


def has_source_section(content: str) -> bool:
    """Check if the ``### 来源`` section exists."""
    return HEADING_SOURCE in content


def has_placeholder(content: str) -> bool:
    """Check if ``暂无资料`` appears anywhere in the file."""
    return "暂无资料" in content


def has_bare_bilibili_url(source_urls: list[str]) -> bool:
    """Check if any extracted source URL is a bare bilibili base URL.

    A bare URL is exactly ``https://www.bilibili.com/`` (or without trailing
    slash) with no further path, e.g. as a source link to the homepage.
    """
    for url in source_urls:
        # Strip trailing slash before comparison
        normalized = url.rstrip("/")
        if normalized in BARE_BILIBILI_URLS or url in BARE_BILIBILI_URLS:
            return True
    return False


def scan_file(filepath: Path) -> dict:
    """Scan a single music markdown file and return its metrics dict."""
    try:
        text = filepath.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"  [WARN] Cannot read {filepath.name}: {exc}", file=sys.stderr)
        return {
            "file": str(filepath.relative_to(filepath.parent.parent)),
            "slug": extract_slug(filepath),
            "error": str(exc),
            "lines": 0,
        }

    slug = extract_slug(filepath)
    fields = parse_table_fields(text)
    source_urls = find_source_urls(text)

    has_title = has_table_field_nonempty(fields, "曲名")
    has_creator = has_table_field_nonempty(fields, "P主")
    creator_slug = extract_creator_slug(fields)
    has_singer = has_table_field_nonempty(fields, "演唱")
    singer_raw = extract_singer_field(fields)
    has_date = has_table_field_nonempty(fields, "发行日期")
    date_val = fields.get("发行日期") or None
    has_platform = has_table_field_nonempty(fields, "首发平台")
    has_engine = has_table_field_nonempty(fields, "引擎")
    has_style = has_table_field_nonempty(fields, "风格")
    has_tags = has_table_field_nonempty(fields, "标签")
    has_videoid = has_table_field_nonempty(fields, "视频ID")
    videoid_val = fields.get("视频ID") or None
    has_plays = has_table_field_nonempty(fields, "播放量")
    plays_val = fields.get("播放量") or None

    lines_count = len(text.splitlines())

    entry: dict = {
        "file": str(filepath.relative_to(filepath.parent.parent)),
        "slug": slug,
        "has_title": has_title,
        "has_creator_slug": has_creator,
        "has_singer": has_singer,
        "has_date": has_date,
        "has_platform": has_platform,
        "has_engine": has_engine,
        "has_style": has_style,
        "has_tags": has_tags,
        "has_videoid": has_videoid,
        "has_plays": has_plays,
        "has_placeholder": has_placeholder(text),
        "has_bare_bilibili_url": has_bare_bilibili_url(source_urls),
        "has_wrong_heading": has_wrong_heading(text),
        "has_source_section": has_source_section(text),
        "source_urls": source_urls,
        "lines": lines_count,
    }

    if creator_slug is not None:
        entry["creator_slug"] = creator_slug
    if singer_raw is not None:
        entry["singer_field"] = singer_raw
    if date_val is not None:
        entry["date"] = date_val
    if videoid_val is not None:
        entry["videoid"] = videoid_val
    if plays_val is not None:
        entry["plays_raw"] = plays_val

    return entry


def build_summary(inventory: list[dict]) -> dict:
    """Aggregate per-file metrics into summary statistics."""
    total = len(inventory)

    missing_singer = sum(1 for e in inventory if not e.get("has_singer"))
    missing_date = sum(1 for e in inventory if not e.get("has_date"))
    missing_videoid = sum(1 for e in inventory if not e.get("has_videoid"))
    missing_creator_slug = sum(1 for e in inventory if not e.get("has_creator_slug"))
    missing_plays = sum(1 for e in inventory if not e.get("has_plays"))
    missing_title = sum(1 for e in inventory if not e.get("has_title"))
    missing_platform = sum(1 for e in inventory if not e.get("has_platform"))
    missing_engine = sum(1 for e in inventory if not e.get("has_engine"))
    missing_style = sum(1 for e in inventory if not e.get("has_style"))
    missing_tags = sum(1 for e in inventory if not e.get("has_tags"))

    has_placeholder = sum(1 for e in inventory if e.get("has_placeholder"))
    has_bare_bilibili_url = sum(1 for e in inventory if e.get("has_bare_bilibili_url"))
    has_wrong_heading = sum(1 for e in inventory if e.get("has_wrong_heading"))
    missing_source_section = sum(1 for e in inventory if not e.get("has_source_section"))

    with_videoid = sum(1 for e in inventory if e.get("has_videoid"))
    without_videoid = total - with_videoid

    # Field-level counts (what values do we see for each field?)
    field_counts: dict[str, dict[str, int]] = {}
    field_names = [
        "has_title", "has_creator_slug", "has_singer", "has_date",
        "has_platform", "has_engine", "has_style", "has_tags",
        "has_videoid", "has_plays",
    ]
    for fname in field_names:
        present = sum(1 for e in inventory if e.get(fname))
        field_counts[fname] = {"present": present, "missing": total - present}

    return {
        "total_files": total,
        "missing_title": missing_title,
        "missing_creator_slug": missing_creator_slug,
        "missing_singer": missing_singer,
        "missing_date": missing_date,
        "missing_platform": missing_platform,
        "missing_engine": missing_engine,
        "missing_style": missing_style,
        "missing_tags": missing_tags,
        "missing_videoid": missing_videoid,
        "missing_plays": missing_plays,
        "has_placeholder": has_placeholder,
        "has_bare_bilibili_url": has_bare_bilibili_url,
        "has_wrong_heading": has_wrong_heading,
        "missing_source_section": missing_source_section,
        "with_videoid": with_videoid,
        "without_videoid": without_videoid,
        "field_counts": field_counts,
    }


def has_errors(entry: dict) -> bool:
    """Check if a per-file entry has an error field."""
    return "error" in entry


def main() -> None:
    """Main entry point."""
    music_path = MUSIC_DIR
    if not music_path.is_dir():
        print(f"[ERROR] Music directory not found: {music_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure qa/ exists
    QA_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all .md files
    md_files = sorted(music_path.glob("*.md"))
    total = len(md_files)
    print(f"Scanning {total} files in {music_path} ...", file=sys.stderr)

    inventory: list[dict] = []
    error_count = 0

    for idx, fpath in enumerate(md_files, start=1):
        entry = scan_file(fpath)
        inventory.append(entry)
        if has_errors(entry):
            error_count += 1
        if idx % 500 == 0 or idx == total:
            print(f"  [{idx:>5}/{total}] ({error_count} errors)", file=sys.stderr)

    # Compute summary
    summary = build_summary(inventory)

    # Write outputs
    INVENTORY_PATH.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nDone.", file=sys.stderr)
    print(f"  Inventory: {INVENTORY_PATH} ({len(inventory)} entries)", file=sys.stderr)
    print(f"  Summary:   {SUMMARY_PATH}", file=sys.stderr)

    # Print brief summary to stderr
    s = summary
    print(
        f"\n"
        f"  total_files:           {s['total_files']:>5}\n"
        f"  missing_title:         {s['missing_title']:>5}\n"
        f"  missing_creator_slug:  {s['missing_creator_slug']:>5}\n"
        f"  missing_singer:        {s['missing_singer']:>5}\n"
        f"  missing_date:          {s['missing_date']:>5}\n"
        f"  missing_platform:      {s['missing_platform']:>5}\n"
        f"  missing_engine:        {s['missing_engine']:>5}\n"
        f"  missing_style:         {s['missing_style']:>5}\n"
        f"  missing_tags:          {s['missing_tags']:>5}\n"
        f"  missing_videoid:       {s['missing_videoid']:>5}\n"
        f"  missing_plays:         {s['missing_plays']:>5}\n"
        f"  has_placeholder:       {s['has_placeholder']:>5}\n"
        f"  has_bare_bilibili_url: {s['has_bare_bilibili_url']:>5}\n"
        f"  has_wrong_heading:     {s['has_wrong_heading']:>5}\n"
        f"  missing_source_section:{s['missing_source_section']:>5}\n"
        f"  with_videoid:          {s['with_videoid']:>5}\n"
        f"  without_videoid:       {s['without_videoid']:>5}\n",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
