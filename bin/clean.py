#!/usr/bin/env python3
"""
bin/clean.py — Format cleanup engine for music .md files.

Each operation is a pure function: fn(text: str) -> str.
Operations are applied in sequence. Operation 4 (fix_bare_url) is
detection-only — it reports findings without modifying text.

Usage:
    python bin/clean.py --dry-run <file.md>
    python bin/clean.py <file.md>
    python bin/clean.py --batch music/
    python bin/clean.py --batch music/ --dry-run
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ── Constants ──────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

STANDARD_FIELDS = [
    "曲名",
    "P主",
    "演唱",
    "发行日期",
    "首发平台",
    "引擎",
    "风格",
    "标签",
    "作词",
    "作曲",
    "编曲",
    "调教",
    "视频ID",
    "播放量",
]

BARE_BILIBILI_URLS = frozenset({
    "https://www.bilibili.com/",
    "https://www.bilibili.com",
    "http://www.bilibili.com/",
    "http://www.bilibili.com",
})

INVENTORY_PATH = PROJECT_DIR / "qa" / "inventory.json"

# ── Operation 1: fix_heading ───────────────────────────────────────────────


def fix_heading(text: str) -> str:
    """Replace ``### 描述`` heading with ``### 歌曲背景``."""
    return text.replace("### 描述", "### 歌曲背景")


# ── Operation 2: strip_placeholders ────────────────────────────────────────


def strip_placeholders(text: str) -> str:
    """Replace ``暂无资料`` in table value cells with an empty value.

    Only affects pipe-delimited table rows:

        | 作词 | 暂无资料 |  →  | 作词 |  |

    Non-table occurrences (e.g. in prose or list items) are left untouched.
    """
    return re.sub(
        r'\|([^|\n]*)\|\s*暂无资料\s*\|',
        r'|\1|  |',
        text,
    )


# ── Operation 3: normalize_table_rows ──────────────────────────────────────


def normalize_table_rows(text: str) -> str:
    """Ensure all standard table rows exist in the ``### 基本信息`` section.

    Standard rows (in order): 曲名, P主, 演唱, 发行日期, 首发平台, 引擎,
    风格, 标签, 作词, 作曲, 编曲, 调教, 视频ID, 播放量.

    Missing rows are inserted at their correct position with empty values.
    Non-standard rows (custom fields, blank lines, etc.) are preserved in
    their original relative order after the standard rows.
    """
    lines = text.split("\n")

    # Locate section boundaries
    basic_info_idx: int | None = None
    section_end_idx = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == "### 基本信息":
            basic_info_idx = i
        elif basic_info_idx is not None and line.strip().startswith("## ") and i > basic_info_idx:
            section_end_idx = i
            break

    if basic_info_idx is None:
        return text  # nothing to do

    # Collect existing rows and any non-standard content
    existing_rows: dict[str, str] = {}
    other_lines: list[str] = []

    for j in range(basic_info_idx + 1, section_end_idx):
        line = lines[j]
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 4 and parts[1] and parts[1] not in ("---", "字段"):
                field = parts[1]
                value = parts[2] if len(parts) > 2 else ""
                if field in STANDARD_FIELDS:
                    existing_rows[field] = value
                else:
                    other_lines.append(line)
                continue  # skip table data rows (will be rebuilt)
        # Keep non-table lines intact
        other_lines.append(line)

    # Short-circuit if nothing is missing
    missing = [f for f in STANDARD_FIELDS if f not in existing_rows]
    if not missing:
        return text

    # Rebuild the section
    new_lines = lines[: basic_info_idx + 1]
    new_lines.append("| 字段 | 值 |")
    new_lines.append("|------|----|")

    for field in STANDARD_FIELDS:
        value = existing_rows.get(field, "")
        new_lines.append(f"| {field} | {value} |")

    new_lines.extend(other_lines)
    new_lines.extend(lines[section_end_idx:])

    return "\n".join(new_lines)


# ── Operation 4: fix_bare_url (detection only) ─────────────────────────────


def detect_bare_urls(text: str) -> list[str]:
    """Detect bare bilibili URLs in the ``### 来源`` section.

    Returns a list of bare URLs found (e.g. ``https://www.bilibili.com/``
    without a video path).  This is detection-only — the text is NOT modified.
    """
    findings: list[str] = []
    in_source = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "### 来源":
            in_source = True
            continue
        if not in_source:
            continue
        if stripped.startswith("#"):
            in_source = False
            continue

        # Match any URL (markdown link target or bare)
        for match in re.finditer(r"https?://[^\s)]+", stripped):
            url = match.group(0)
            normalized = url.rstrip("/")
            if normalized in BARE_BILIBILI_URLS or url in BARE_BILIBILI_URLS:
                findings.append(url)

    return findings


# ── Operation 5: strip_trailing_whitespace ─────────────────────────────────


def strip_trailing_whitespace(text: str) -> str:
    """Remove trailing whitespace from all lines; normalise line endings to \\n."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    lines = [line.rstrip() for line in lines]
    return "\n".join(lines)


# ── Composite apply ────────────────────────────────────────────────────────

ChangeReport = dict[str, Any]


def apply_all(text: str) -> tuple[str, ChangeReport]:
    """Apply all operations in sequence.

    Returns (cleaned_text, report) where *report* is a dict summarising
    what changed (suitable for both dry-run display and change logging).
    """
    original = text
    report: ChangeReport = {}

    # ── Op 1 ──────────────────────────────────────────────────────────
    t = fix_heading(text)
    report["heading_fixed"] = "### 描述" in original

    # ── Op 2 ──────────────────────────────────────────────────────────
    t = strip_placeholders(t)
    placeholder_count = len(
        re.findall(r"\|[^|\n]*\|\s*暂无资料\s*\|", original)
    )
    report["placeholders_stripped"] = placeholder_count

    # ── Op 3 ──────────────────────────────────────────────────────────
    t = normalize_table_rows(t)
    # Detect missing rows from original (before modification)
    existing_set: set[str] = _compute_existing_fields(original)
    missing = [f for f in STANDARD_FIELDS if f not in existing_set]
    report["rows_added"] = len(missing)
    report["missing_rows"] = missing

    # ── Op 4 (detection only, no modification) ────────────────────────
    bare_urls = detect_bare_urls(original)
    report["bare_urls_found"] = bare_urls

    # ── Op 5 ──────────────────────────────────────────────────────────
    has_trailing = any(
        line != line.rstrip() for line in original.split("\n")
    ) or "\r" in original
    t = strip_trailing_whitespace(t)
    report["trailing_whitespace_fixed"] = has_trailing

    return t, report


def _compute_existing_fields(text: str) -> set[str]:
    """Return the set of field names present in the ``### 基本信息`` table."""
    fields: set[str] = set()
    in_basic = False
    for line in text.splitlines():
        s = line.strip()
        if s == "### 基本信息":
            in_basic = True
        elif in_basic:
            if s.startswith("## "):
                break
            if s.startswith("|") and s.endswith("|"):
                parts = [p.strip() for p in s.split("|")]
                if len(parts) >= 4 and parts[1] and parts[1] not in ("---", "字段"):
                    fields.add(parts[1])
    return fields


# ── I/O helpers ────────────────────────────────────────────────────────────


def read_file(path: Path) -> str:
    """Read a file with UTF-8 BOM handling (``utf-8-sig``)."""
    return path.read_text(encoding="utf-8-sig")


def write_file(path: Path, text: str) -> None:
    """Write a file as plain UTF-8 (no BOM)."""
    path.write_text(text, encoding="utf-8")


# ── Reporting ──────────────────────────────────────────────────────────────


def format_dry_run_report(file: str, report: ChangeReport) -> str:
    """Format a human-readable dry-run report for a single file."""
    lines: list[str] = [f"File: {file}"]

    heading = report.get("heading_fixed", False)
    lines.append(f"  Will fix heading: {'yes' if heading else 'no'}")

    ph_count = report.get("placeholders_stripped", 0)
    if isinstance(ph_count, int) and ph_count > 0:
        lines.append(f"  Will strip placeholders: {ph_count} found")
    else:
        lines.append("  Will strip placeholders: 0 found")

    rows = report.get("rows_added", 0)
    if isinstance(rows, int) and rows > 0:
        missing = report.get("missing_rows", [])
        lines.append(
            f"  Will add {rows} missing rows: {', '.join(missing)}"
        )
    else:
        lines.append("  Will add 0 missing rows")

    bare = report.get("bare_urls_found", [])
    if bare:
        lines.append(f"  Bare URL found: yes — {bare[0]}")
    else:
        lines.append("  Bare URL found: no")

    ws = report.get("trailing_whitespace_fixed", False)
    lines.append(
        f"  Will strip trailing whitespace: {'yes' if ws else 'no'}"
    )

    return "\n".join(lines)


def format_change_summary(report: ChangeReport) -> str:
    """Format a compact one-line summary of changes actually made."""
    parts: list[str] = []
    if report.get("heading_fixed"):
        parts.append("heading")
    ph = report.get("placeholders_stripped", 0)
    if isinstance(ph, int) and ph > 0:
        parts.append(f"placeholders({ph})")
    rows = report.get("rows_added", 0)
    if isinstance(rows, int) and rows > 0:
        parts.append(f"rows({rows})")
    if report.get("trailing_whitespace_fixed"):
        parts.append("trailing_ws")
    return ", ".join(parts) if parts else "no changes"


# ── Process file ───────────────────────────────────────────────────────────


def process_file(filepath: Path, dry_run: bool = False) -> bool:
    """Process a single music ``.md`` file.

    In *dry_run* mode only the report is printed; the file is never modified.
    Returns ``True`` if at least one change would be made.
    """
    # Guard: missing file
    if not filepath.is_file():
        print(f"  [ERROR] File not found: {filepath}", file=sys.stderr)
        return False

    # Guard: missing 基本信息 section
    raw = read_file(filepath)
    if "### 基本信息" not in raw:
        print(
            f"  [WARN] {filepath.name}: missing '### 基本信息' section, skipping",
            file=sys.stderr,
        )
        return False

    cleaned, report = apply_all(raw)

    if dry_run:
        print(format_dry_run_report(str(filepath), report))
        return _report_has_changes(report)

    # Live mode — write back if changed
    if cleaned != raw:
        write_file(filepath, cleaned)
        print(f"  \u2713 {filepath.name}: {format_change_summary(report)}")
        return True
    else:
        print(f"  \u2013 {filepath.name}: no changes")
        return False


def _report_has_changes(report: ChangeReport) -> bool:
    """Return ``True`` if the report indicates any change would be made."""
    return bool(
        report.get("heading_fixed")
        or report.get("placeholders_stripped", 0)
        or report.get("rows_added", 0)
        or report.get("trailing_whitespace_fixed")
        or report.get("bare_urls_found", [])
    )


# ── Inventory integration ──────────────────────────────────────────────────


def load_inventory() -> list[dict[str, Any]]:
    """Load ``qa/inventory.json`` and return the list of per-file entries."""
    try:
        return json.loads(
            INVENTORY_PATH.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(
            f"  [WARN] Cannot load inventory at {INVENTORY_PATH}: {exc}",
            file=sys.stderr,
        )
        return []


def find_files_needing_op(
    inventory: list[dict[str, Any]], op_key: str
) -> list[str]:
    """Return file paths (relative to project root) that need a given op.

    *op_key* matches the boolean keys in inventory entries, e.g.
    ``"has_wrong_heading"``, ``"has_placeholder"``, ``"has_bare_bilibili_url"``.
    """
    return [e["file"] for e in inventory if e.get(op_key)]


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Format cleanup engine for music .md files",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="File path or directory path (when used with --batch)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying any file",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all ``.md`` files in the given directory",
    )
    parser.add_argument(
        "--inventory",
        action="store_true",
        help="Report inventory-derived counts of files needing each operation",
    )

    args = parser.parse_args()

    # ── --inventory flag ───────────────────────────────────────────────
    if args.inventory:
        inv = load_inventory()
        if not inv:
            print("[ERROR] No inventory data available.", file=sys.stderr)
            sys.exit(1)
        # (Re)use the same detection the scanner uses
        wrong_hdg = sum(1 for e in inv if e.get("has_wrong_heading"))
        has_ph = sum(1 for e in inv if e.get("has_placeholder"))
        bare_url = sum(1 for e in inv if e.get("has_bare_bilibili_url"))
        print(f"Inventory-based estimates ({len(inv)} files):")
        print(f"  Wrong heading (### 描述):           {wrong_hdg}")
        print(f"  Has placeholder (暂无资料):          {has_ph}")
        print(f"  Has bare bilibili URL:              {bare_url}")
        return

    # ── --batch mode ───────────────────────────────────────────────────
    if args.batch:
        if not args.target:
            print("[ERROR] --batch requires a directory path", file=sys.stderr)
            sys.exit(1)

        target_dir = Path(args.target)
        if not target_dir.is_dir():
            print(f"[ERROR] Not a directory: {target_dir}", file=sys.stderr)
            sys.exit(1)

        md_files = sorted(target_dir.glob("*.md"))
        if not md_files:
            print(f"[WARN] No .md files found in {target_dir}", file=sys.stderr)
            return

        print(f"Processing {len(md_files)} files in {target_dir} ...")
        changed = 0
        for fpath in md_files:
            if process_file(fpath, dry_run=args.dry_run):
                changed += 1

        mode = "dry-run" if args.dry_run else "cleaned"
        print(
            f"\nDone. {changed}/{len(md_files)} files would be modified ({mode})."
        )
        return

    # ── Single file mode ───────────────────────────────────────────────
    if args.target:
        filepath = Path(args.target)
        if not filepath.is_file():
            print(f"[ERROR] File not found: {filepath}", file=sys.stderr)
            sys.exit(1)

        process_file(filepath, dry_run=args.dry_run)
        return

    # ── No arguments — show help ───────────────────────────────────────
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
