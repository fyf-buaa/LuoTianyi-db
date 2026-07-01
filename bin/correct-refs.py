"""Reference correction engine for music knowledge base.

Normalizes cross-references in music .md files using reference maps.

Operations:
  1. migrate_creator_slug  — Apply slug migrations from creator-id-migration.json
  2. fill_creator_name     — Replace slug-form display names with human-readable names
  3. normalize_singer_prefix — Ensure consistent prefix format in the 演唱 field
  4. report_anomalies      — Detect and report data quality issues (no modifications)

Usage:
    python bin/correct-refs.py --dry-run <file.md>
    python bin/correct-refs.py <file.md>
    python bin/correct-refs.py --batch music/
    python bin/correct-refs.py --batch music/ --dry-run
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO


# ── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUSIC_DIR = PROJECT_ROOT / "music"
QA_BACKUP_DIR = PROJECT_ROOT / "qa" / "backups"

CREATOR_ID_MIGRATION_PATH = PROJECT_ROOT / "creator-id-migration.json"
CREATOR_NAME_MAP_PATH = PROJECT_ROOT / "creator-name-map.json"
CREATOR_SLUG_MAP_PATH = PROJECT_ROOT / "creator-slug-map.json"
MEMBER_NAME_MAP_PATH = PROJECT_ROOT / "member-name-map.json"

# ── Heading constants (must match exactly) ───────────────────────────────
HEADING_BASIC_INFO = "### 基本信息"
HEADING_CREW = "### 创作团队"


# ══════════════════════════════════════════════════════════════════════════
#  Map loaders
# ══════════════════════════════════════════════════════════════════════════

def load_json(path: Path, label: str) -> dict[str, str]:
    """Load a JSON object and return it.  Exits on read / decode errors."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"[FATAL] {label} not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[FATAL] {label} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def load_all_maps() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    """Load all four reference maps and return them as a tuple."""
    creator_id_migration = load_json(CREATOR_ID_MIGRATION_PATH, "creator-id-migration.json")
    creator_name_map = load_json(CREATOR_NAME_MAP_PATH, "creator-name-map.json")
    creator_slug_map = load_json(CREATOR_SLUG_MAP_PATH, "creator-slug-map.json")
    member_name_map = load_json(MEMBER_NAME_MAP_PATH, "member-name-map.json")
    return creator_id_migration, creator_name_map, creator_slug_map, member_name_map


# ══════════════════════════════════════════════════════════════════════════
#  Table-parsing helpers
# ══════════════════════════════════════════════════════════════════════════

def parse_basic_info_table(text: str) -> dict[str, str]:
    """Extract key → value from the ``### 基本信息`` markdown table."""
    fields: dict[str, str] = {}
    in_table = False

    for line in text.splitlines():
        stripped = line.strip()

        if stripped == HEADING_BASIC_INFO:
            in_table = True
            continue

        if in_table and stripped.startswith("##"):
            in_table = False
            continue

        if in_table and stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 3:
                key = parts[1]
                if key and key != "---":
                    value = parts[2] if len(parts) > 2 else ""
                    fields[key] = value

    return fields


def extract_creator_full(fields: dict[str, str]) -> str | None:
    """Return the raw ``P主`` value (e.g. ``creator:xxx``) or *None*."""
    val = fields.get("P主")
    if val and val.startswith("creator:"):
        return val
    return None


def extract_singer_raw(fields: dict[str, str]) -> str | None:
    """Return the raw 演唱 value, or *None* if absent / empty."""
    val = fields.get("演唱", "").strip()
    return val if val else None


# ══════════════════════════════════════════════════════════════════════════
#  Text helpers
# ══════════════════════════════════════════════════════════════════════════

def _has_cjk(s: str) -> bool:
    """Return *True* if *s* contains any CJK Unified Ideograph."""
    for ch in s:
        if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
            return True
    return False


def _is_slug_like(s: str) -> bool:
    """Return *True* if *s* looks like a bare slug (Latin / digits / hyphens / underscores / dots)."""
    return bool(re.fullmatch(r"[a-zA-Z0-9_.-]+", s))


# ══════════════════════════════════════════════════════════════════════════
#  Operation 1 — migrate_creator_slug
# ══════════════════════════════════════════════════════════════════════════

def migrate_creator_slug(text: str, migration_map: dict[str, str]) -> tuple[str, list[str]]:
    """Apply slug migrations from *migration_map* to the ``P主`` table cell."""
    changes: list[str] = []
    lines = text.splitlines()
    in_basic = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == HEADING_BASIC_INFO:
            in_basic = True
            continue

        if in_basic and stripped.startswith("##"):
            in_basic = False
            continue

        if in_basic and stripped.startswith("| P主 |"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 3:
                current = parts[2]
                if current in migration_map:
                    new_val = migration_map[current]
                    lines[i] = line.replace(
                        f"| P主 | {current} |",
                        f"| P主 | {new_val} |",
                        1,
                    )
                    changes.append(f"migrate_creator_slug — {current} → {new_val}")
            break

    return _join_lines(text, lines), changes


# ══════════════════════════════════════════════════════════════════════════
#  Operation 2 — fill_creator_name
# ══════════════════════════════════════════════════════════════════════════

def fill_creator_name(text: str, name_map: dict[str, str]) -> tuple[str, list[str]]:
    """Replace slug-form display names in the ``P主/作者`` line with human-readable names."""
    changes: list[str] = []

    # Get the (possibly migrated) creator slug from the table
    fields = parse_basic_info_table(text)
    creator_full = extract_creator_full(fields)
    if creator_full is None:
        return text, changes

    slug = creator_full[len("creator:"):]
    display_name = name_map.get(slug)

    if display_name is None:
        return text, changes  # nothing to fill

    # Locate the P主/作者 line inside ### 创作团队
    lines = text.splitlines()
    in_crew = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == HEADING_CREW:
            in_crew = True
            continue
        if in_crew and stripped.startswith("##"):
            break
        if not in_crew or "**P主/作者**" not in stripped:
            continue

        # ── Split the value after "**: " into name_part and suffix ──
        # The value has one of these forms:
        #   slug（display） - description        (with space before dash)
        #   slug（display）- description         (no space before dash)
        #   slug - description
        #   slug
        #   暂无资料
        full_value = stripped.split("**: ", 1)[1] if "**: " in stripped else ""

        paren_open = full_value.find("（")
        paren_close = full_value.find("）")

        if paren_open >= 0 and paren_close > paren_open:
            # Has parens format: slug（display）<suffix>
            slug_part = full_value[:paren_open].strip()
            paren_content = full_value[paren_open + 1 : paren_close].strip()
            name_part = full_value[: paren_close + 1]  # "slug（display）"
            suffix = full_value[paren_close + 1 :]

            # Build the corrected name portion
            if slug_part == slug and paren_content != display_name and display_name:
                new_name_part = f"{slug_part}（{display_name}）"
                new_full_value = new_name_part + suffix

                if new_full_value == full_value:
                    break  # no effective change

                # Replace in the raw (unstripped) line
                old_line = lines[i]
                prefix = stripped.replace(full_value, "", 1)
                new_line = old_line.replace(prefix + full_value, prefix + new_full_value, 1)
                if new_line != old_line:
                    lines[i] = new_line
                    changes.append(
                        f"fill_creator_name — paren-content \"{paren_content}\" → "
                        f"\"{display_name}\" for slug \"{slug}\"",
                    )
            break

        # No parens → split at first " - " to separate name from description
        if " - " in full_value:
            name_part, suffix = full_value.split(" - ", 1)
            name_part = name_part.strip()
            suffix = " - " + suffix
        else:
            name_part = full_value.strip()
            suffix = ""

        # Determine if replacement is needed
        needs_replace = False

        if name_part == "暂无资料":
            needs_replace = True
        elif _is_slug_like(name_part) and not _has_cjk(name_part):
            needs_replace = True

        if needs_replace and display_name:
            if name_part == display_name:
                break  # no effective change

            old_line = lines[i]
            prefix = stripped.replace(full_value, "", 1)
            new_line = old_line.replace(
                prefix + full_value,
                prefix + display_name + suffix,
                1,
            )
            if new_line != old_line:
                lines[i] = new_line
                changes.append(
                    f"fill_creator_name — \"{name_part}\" → \"{display_name}\" "
                    f"for slug \"{slug}\"",
                )
        break

    return _join_lines(text, lines), changes


# ══════════════════════════════════════════════════════════════════════════
#  Operation 3 — normalize_singer_prefix
# ══════════════════════════════════════════════════════════════════════════

def _normalize_singer_tokens(raw: str) -> tuple[str, list[str]]:
    """Prepend ``core:`` to any 演唱 token that is missing a prefix."""
    changes: list[str] = []
    tokens = [t.strip() for t in raw.split(",")]
    out: list[str] = []

    for t in tokens:
        if not t:
            continue
        if t.startswith("core:") or t.startswith("member:"):
            out.append(t)
        else:
            normalized = f"core:{t}"
            out.append(normalized)
            changes.append(f"normalize_singer_prefix — \"{t}\" → \"{normalized}\"")

    return ", ".join(out), changes


def normalize_singer_prefix(text: str) -> tuple[str, list[str]]:
    """Ensure consistent prefix on every 演唱 token (bare slug → ``core:``)."""
    changes: list[str] = []
    lines = text.splitlines()
    in_basic = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == HEADING_BASIC_INFO:
            in_basic = True
            continue

        if in_basic and stripped.startswith("##"):
            in_basic = False
            continue

        if in_basic and stripped.startswith("| 演唱 |"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 3:
                current = parts[2]
                if current:
                    normalized, token_changes = _normalize_singer_tokens(current)
                    if token_changes:
                        lines[i] = line.replace(
                            f"| 演唱 | {current} |",
                            f"| 演唱 | {normalized} |",
                            1,
                        )
                        changes.extend(token_changes)
            break

    return _join_lines(text, lines), changes


# ══════════════════════════════════════════════════════════════════════════
#  Operation 4 — report_anomalies
# ══════════════════════════════════════════════════════════════════════════

def report_anomalies(
    text: str,
    filename: str,
    creator_name_map: dict[str, str],
    creator_slug_map: dict[str, str],
    creator_id_migration: dict[str, str],
    member_name_map: dict[str, str],
) -> list[str]:
    """Inspect the file and return a list of anomaly descriptions."""
    anomalies: list[str] = []
    fields = parse_basic_info_table(text)
    creator_full = extract_creator_full(fields)

    if creator_full is not None:
        slug = creator_full[len("creator:"):]

        # Check that the slug (or its ``creator:`` form) appears somewhere
        in_name = slug in creator_name_map
        in_slug = slug in creator_slug_map
        # Check both old-key and new-value side of the migration map
        in_migration_key = creator_full in creator_id_migration
        in_migration_val = creator_full in creator_id_migration.values()

        if not in_name and not in_slug and not in_migration_key and not in_migration_val:
            anomalies.append(
                f"[ANOMALY] {filename}: P主 slug \"{slug}\" not found in any reference map",
            )

    # Check 演唱 field
    singer_raw = extract_singer_raw(fields)
    if not singer_raw:
        anomalies.append(
            f"[ANOMALY] {filename}: 演唱 field is empty — needs human input",
        )
    else:
        for token in (t.strip() for t in singer_raw.split(",")):
            if not token:
                continue
            if token.startswith("core:") or token.startswith("member:"):
                if token not in member_name_map:
                    anomalies.append(
                        f"[ANOMALY] {filename}: 演唱 value \"{token}\" "
                        f"references non-existent member",
                    )

    return anomalies


# ══════════════════════════════════════════════════════════════════════════
#  Joining helper (preserve trailing newline)
# ══════════════════════════════════════════════════════════════════════════

def _join_lines(original: str, lines: list[str]) -> str:
    """Rejoin *lines* (from ``splitlines()`` without *keepends*) and
    preserve a trailing newline if the original had one."""
    result = "\n".join(lines)
    if original.endswith("\n"):
        result += "\n"
    return result


# ══════════════════════════════════════════════════════════════════════════
#  File-level processing
# ══════════════════════════════════════════════════════════════════════════

def process_file(
    filepath: Path,
    maps: tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]],
    dry_run: bool = False,
    out: TextIO = sys.stdout,
) -> int:
    """Run all operations on *filepath*.

    Returns the number of changes applied (zero means no-op).
    In dry-run mode the file is never touched but changes are still counted.
    """
    (
        creator_id_migration,
        creator_name_map,
        creator_slug_map,
        member_name_map,
    ) = maps

    filename = filepath.name
    tag = "[WOULD CHANGE]" if dry_run else "[CHANGE]"

    # Read file (UTF-8 with or without BOM)
    try:
        original = filepath.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"  [WARN] Cannot read {filename}: {exc}", file=sys.stderr)
        return 0

    text = original
    all_changes: list[str] = []

    # ── Operation 1 ──────────────────────────────────────────────────────
    text, changes = migrate_creator_slug(text, creator_id_migration)
    all_changes.extend(changes)

    # ── Operation 2 ──────────────────────────────────────────────────────
    text, changes = fill_creator_name(text, creator_name_map)
    all_changes.extend(changes)

    # ── Operation 3 ──────────────────────────────────────────────────────
    text, changes = normalize_singer_prefix(text)
    all_changes.extend(changes)

    # ── Operation 4 ──────────────────────────────────────────────────────
    anomalies = report_anomalies(
        text,
        filename,
        creator_name_map,
        creator_slug_map,
        creator_id_migration,
        member_name_map,
    )

    # ── Output ───────────────────────────────────────────────────────────
    for change in all_changes:
        print(f"  {tag} {filename}: {change}", file=out)

    for anomaly in anomalies:
        print(f"  {anomaly}", file=out)

    if not all_changes:
        return 0

    if dry_run:
        return len(all_changes)

    # ── Backup ───────────────────────────────────────────────────────────
    QA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = QA_BACKUP_DIR / f"{filepath.stem}_{timestamp}.md"
    backup_path.write_bytes(original.encode("utf-8"))
    print(f"  [BACKUP] {backup_path}", file=out)

    # ── Write modified file ─────────────────────────────────────────────
    filepath.write_bytes(text.encode("utf-8"))
    print(
        f"  [APPLIED] {filename}: {len(all_changes)} change(s)",
        file=out,
    )

    return len(all_changes)


# ══════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize cross-references in music .md files",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Single file to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show proposed changes without modifying files",
    )
    parser.add_argument(
        "--batch",
        metavar="DIR",
        help="Process all *.md files in the given directory",
    )
    args = parser.parse_args()

    maps = load_all_maps()

    # ── Batch mode ───────────────────────────────────────────────────────
    if args.batch:
        target_dir = Path(args.batch)
        if not target_dir.is_dir():
            print(f"[ERROR] Directory not found: {target_dir}", file=sys.stderr)
            sys.exit(1)

        md_files = sorted(target_dir.glob("*.md"))
        if not md_files:
            print(f"[WARN] No .md files found in {target_dir}", file=sys.stderr)
            return

        print(
            f"Processing {len(md_files)} file(s) in {target_dir} ...",
            file=sys.stderr,
        )

        total_changes = 0
        for fpath in md_files:
            total_changes += process_file(fpath, maps, dry_run=args.dry_run, out=sys.stdout)

        summary = f"\nDone. {total_changes} change(s) across {len(md_files)} file(s)."
        print(summary, file=sys.stderr)
        return

    # ── Single-file mode ─────────────────────────────────────────────────
    if args.target:
        fpath = Path(args.target)
        if not fpath.exists():
            print(f"[ERROR] File not found: {fpath}", file=sys.stderr)
            sys.exit(1)
        process_file(fpath, maps, dry_run=args.dry_run, out=sys.stdout)
        return

    # No argument → show help
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
