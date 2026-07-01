#!/usr/bin/env python3
"""Online verification job generator for music knowledge base.

Generates structured verification task files that are *consumed* by a
downstream agent (the orchestrator) that performs the actual web searches.
This script is a JOB GENERATOR + RESULT PROCESSOR, not a web searcher itself.

Usage:
    python bin/verify-online.py --plan <file.md>                         # Show verification plan
    python bin/verify-online.py --verify <file> <result_dir>             # Single verification job
    python bin/verify-online.py --batch <music_dir> --output <results_dir>  # Batch jobs
    python bin/verify-online.py --batch <music_dir> --output <results_dir> --only-with-bv
    python bin/verify-online.py --batch <music_dir> --output <results_dir> --only-without-bv

Output:
    qa/verify-batches/batch-NNN.json        — batch manifests
    qa/verify-batches/batch-NNN_results.json — result files (written by orchestrator)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ── Configuration ──────────────────────────────────────────────────────────

INVENTORY_PATH = Path("qa/inventory.json")
VERIFY_BATCHES_DIR = Path("qa/verify-batches")

BATCH_SIZES: dict[int, int] = {
    1: 50,  # has BV number
    2: 30,  # no BV, but has title + creator
    3: 20,  # no BV, no creator (hardest)
}

HEADING_BASIC_INFO = "### 基本信息"
HEADING_SOURCE = "### 来源"
HEADING_BACKGROUND = "### 歌曲背景"

# Fields from the markdown table that we include in claims
CLAIM_FIELDS = [
    "曲名",
    "P主",
    "演唱",
    "发行日期",
    "首发平台",
    "引擎",
    "视频ID",
    "播放量",
]

# Map of markdown field names to inventory key hints (for type inference)
FIELD_TYPE_MAP: dict[str, str] = {
    "曲名": "string",
    "P主": "slug",
    "演唱": "slug",
    "发行日期": "date",
    "首发平台": "string",
    "引擎": "string",
    "视频ID": "id",
    "播放量": "play_count",
}


# ── File / Inventory helpers ───────────────────────────────────────────────


def load_inventory() -> list[dict[str, Any]]:
    """Load the pre-computed inventory from qa/inventory.json."""
    if not INVENTORY_PATH.is_file():
        print(
            f"[ERROR] Inventory not found at {INVENTORY_PATH}. "
            f"Run `python bin/inventory.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(INVENTORY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def parse_table_fields(content: str) -> dict[str, str]:
    """Extract key-value pairs from the ``### 基本信息`` markdown table.

    Returns a dict mapping field name -> value (stripped). Fields with an
    empty value get an empty string. Missing fields are omitted.
    """
    fields: dict[str, str] = {}
    in_basic_info = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == HEADING_BASIC_INFO:
            in_basic_info = True
            continue

        # A new heading of the same or higher level ends the section
        if in_basic_info and stripped.startswith("##"):
            in_basic_info = False
            continue

        if in_basic_info and stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            if len(parts) >= 3:
                key = parts[1]
                if key and key != "---":
                    value = parts[2] if len(parts) > 2 else ""
                    fields[key] = value

    return fields


def read_music_file(filepath: Path) -> str | None:
    """Read a music markdown file, returning its content or None on error."""
    try:
        return filepath.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"  [WARN] Cannot read {filepath}: {exc}", file=sys.stderr)
        return None


def extract_slug(filepath: Path) -> str:
    """Extract slug from first line ``# music:<slug>``, fallback to stem."""
    try:
        with open(filepath, encoding="utf-8-sig") as fh:
            first_line = fh.readline().strip()
        if first_line.startswith("# music:"):
            return first_line[len("# music:"):].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return filepath.stem


# ── Priority / Classification ──────────────────────────────────────────────


def get_priority_class(entry: dict[str, Any]) -> int:
    """Determine verification priority for an inventory entry.

    Returns:
        1: Has BV number (easiest — bilibili direct)
        2: No BV but has title + creator slug (can search by name)
        3: No BV and no creator slug (hardest)
    """
    if entry.get("has_videoid"):
        return 1
    if entry.get("has_title") and entry.get("has_creator_slug"):
        return 2
    return 3


def priority_label(cls: int) -> str:
    return {1: "has BV", 2: "no BV + title+creator", 3: "no BV + no creator"}.get(cls, "unknown")


# ── Claim generation ───────────────────────────────────────────────────────


def generate_claims(
    fields: dict[str, str], entry: dict[str, Any]
) -> list[dict[str, str]]:
    """Build the ``claims_to_verify`` list for a single music file.

    Iterates over the predefined CLAIM_FIELDS and emits a structured claim
    for each one that is either present or meaningful to check even when
    empty (e.g. empty ``演唱`` or ``发行日期`` signals a gap to fill).
    """
    claims: list[dict[str, str]] = []

    for field_name in CLAIM_FIELDS:
        field_type = FIELD_TYPE_MAP.get(field_name, "string")

        # Get the value from the parsed table first, fallback to inventory
        value = fields.get(field_name, "")

        # For fields missing in table but available in inventory, reconstruct
        if not value:
            if field_name == "P主" and entry.get("creator_slug"):
                value = f"creator:{entry['creator_slug']}"
            elif field_name == "演唱" and entry.get("singer_field"):
                value = entry["singer_field"]
            elif field_name == "发行日期" and entry.get("date"):
                value = entry["date"]
            elif field_name == "视频ID" and entry.get("videoid"):
                value = entry["videoid"]
            elif field_name == "播放量" and entry.get("plays_raw"):
                value = entry["plays_raw"]

        # Normalise: P主 slug type always uses the ``creator:xxx`` form
        if field_name == "P主" and value and not value.startswith("creator:"):
            value = f"creator:{value}"

        # Determine if this claim is actionable
        # - Always include: 曲名, P主, 演唱, 发行日期, 视频ID
        # - Include 播放量 only if present
        # - Include 首发平台, 引擎 only if present (optional fields)
        if field_name in ("首发平台", "引擎", "播放量"):
            if not value:
                continue

        claim = {
            "field": field_name,
            "value": value,
            "type": field_type,
        }
        claims.append(claim)

    return claims


# ── Search query generation ────────────────────────────────────────────────


def generate_search_queries(
    entry: dict[str, Any], fields: dict[str, str]
) -> list[str]:
    """Build a list of web search queries suitable for finding this song.

    The strategy depends on whether we have a BV number:
      - With BV: single targeted query for the bilibili page.
      - Without BV + title+creator: name-based search.
      - Without BV + no creator: broad search by title + VOCALOID.
    """
    queries: list[str] = []

    videoid = entry.get("videoid") or fields.get("视频ID", "")
    if videoid:
        queries.append(f"bilibili video {videoid}")
        return queries

    # Get readable title and creator name
    title = fields.get("曲名", "")
    if not title:
        title = entry.get("slug", "")

    creator_slug = entry.get("creator_slug", "")
    creator_name = creator_slug.replace("-", " ") if creator_slug else ""

    # Build queries based on available data
    if title and creator_slug:
        queries.append(f"VOCALOID {title} {creator_slug}")
        queries.append(f"bilibili {title} VOCALOID 洛天依")
    elif title and not creator_slug:
        queries.append(f"VOCALOID {title} 洛天依")
        queries.append(f"bilibili {title} VOCALOID")
    else:
        # Last resort: use slug
        slug = entry.get("slug", "")
        queries.append(f"VOCALOID {slug} 洛天依 bilibili")

    return queries


# ── Job generation ──────────────────────────────────────────────────────────


def generate_verify_job(
    slug: str, fields: dict[str, str], entry: dict[str, Any]
) -> dict[str, Any]:
    """Create a single verification job dict from an inventory entry."""
    claims = generate_claims(fields, entry)
    search_queries = generate_search_queries(entry, fields)
    videoid = entry.get("videoid") or fields.get("视频ID", "")

    job: dict[str, Any] = {
        "job_id": f"verify-{slug}",
        "file": entry.get("file", f"music/{slug}.md"),
        "method": "bilibili_direct" if videoid else "web_search",
        "bv_number": videoid if videoid else None,
        "claims_to_verify": claims,
        "search_queries": search_queries,
    }

    priority = get_priority_class(entry)
    if priority == 3:
        job["priority"] = "missing_critical_fields"

    return job


def generate_batch_manifest(
    jobs: list[dict[str, Any]], batch_num: int
) -> dict[str, Any]:
    """Wrap a list of verification jobs in a batch manifest."""
    return {
        "batch_id": f"batch-{batch_num:03d}",
        "batch_number": batch_num,
        "job_count": len(jobs),
        "priority_classes": list(
            sorted(
                set(
                    1 if j.get("method") == "bilibili_direct" else (
                        3 if j.get("priority") == "missing_critical_fields" else 2
                    )
                    for j in jobs
                )
            )
        ),
        "jobs": jobs,
    }


# ── Output helpers ─────────────────────────────────────────────────────────


def write_json(path: Path, data: Any) -> None:
    """Write JSON data to a file with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def resolve_inventory_entry(
    file_arg: str, inventory: list[dict[str, Any]]
) -> tuple[Path, dict[str, Any], str] | None:
    """Resolve a file argument to (path, inventory_entry, slug).

    Accepts:
      - ``music/<slug>.md``
      - ``<slug>.md``
      - ``<slug>``
      - absolute path
    """
    file_path = Path(file_arg)

    # If it doesn't exist yet, try different forms
    if not file_path.exists():
        # Try relative to cwd
        candidates = [
            Path.cwd() / file_path,
            Path.cwd() / "music" / file_path,
            Path.cwd() / "music" / f"{file_path.stem if file_path.suffix == '.md' else file_path}.md",
        ]
        for cand in candidates:
            if cand.exists():
                file_path = cand
                break
        else:
            print(f"[ERROR] File not found: {file_arg}", file=sys.stderr)
            return None

    slug = extract_slug(file_path)
    # Find in inventory
    for entry in inventory:
        if entry.get("slug") == slug:
            return file_path, entry, slug

    print(f"[ERROR] Slug '{slug}' not found in inventory.", file=sys.stderr)
    return None


# ── Mode: --plan ────────────────────────────────────────────────────────────


def mode_plan(file_arg: str) -> None:
    """Display a structured verification plan for a single file."""
    inventory = load_inventory()
    resolved = resolve_inventory_entry(file_arg, inventory)
    if resolved is None:
        sys.exit(1)

    file_path, entry, slug = resolved
    content = read_music_file(file_path)
    if content is None:
        sys.exit(1)

    fields = parse_table_fields(content)
    job = generate_verify_job(slug, fields, entry)
    priority = get_priority_class(entry)

    # ── Pretty-print plan ──────────────────────────────────────────────
    sep = "=" * 60
    print(sep)
    print(f"  Verification Plan:  {slug}")
    print(f"  File:               {entry.get('file', file_path.name)}")
    print(f"  Priority Class:     {priority} ({priority_label(priority)})")
    print(f"  Method:             {job['method']}")
    if job["bv_number"]:
        print(f"  BV Number:          {job['bv_number']}")
    print(sep)
    print()

    print("  Claims to verify:")
    for claim in job["claims_to_verify"]:
        val = claim["value"] if claim["value"] else "(empty)"
        print(f"    [{claim['type']:>10}] {claim['field']}: {val}")
    print()

    print("  Search queries:")
    for q in job["search_queries"]:
        print(f"    • {q}")
    print()

    # Summary stats from inventory
    missing = []
    if not entry.get("has_singer"):
        missing.append("演唱")
    if not entry.get("has_date"):
        missing.append("发行日期")
    if not entry.get("has_plays"):
        missing.append("播放量")
    if not entry.get("has_videoid"):
        missing.append("视频ID")
    if missing:
        print(f"  Missing fields: {', '.join(missing)}")
        print()

    print(sep)


# ── Mode: --verify ──────────────────────────────────────────────────────────


def mode_verify(file_arg: str, result_dir: str) -> None:
    """Generate a single verification job JSON file."""
    inventory = load_inventory()
    resolved = resolve_inventory_entry(file_arg, inventory)
    if resolved is None:
        sys.exit(1)

    file_path, entry, slug = resolved
    content = read_music_file(file_path)
    if content is None:
        sys.exit(1)

    fields = parse_table_fields(content)
    job = generate_verify_job(slug, fields, entry)

    out_dir = Path(result_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"verify-{slug}.json"
    write_json(out_path, job)
    print(f"Written: {out_path}", file=sys.stderr)


# ── Mode: --batch ───────────────────────────────────────────────────────────


def mode_batch(
    music_dir: str,
    output_dir: str,
    only_with_bv: bool | None,
    only_without_bv: bool | None,
) -> None:
    """Generate batch verification jobs for all (or filtered) music files.

    Steps:
      1. Load inventory.
      2. Group files by priority class.
      3. Within each priority, process entries in order.
      4. Write batch manifests respecting per-priority batch sizes.
      5. Optionally filter by BV presence.
    """
    inventory = load_inventory()

    # Apply BV filters
    if only_with_bv:
        inventory = [e for e in inventory if e.get("has_videoid")]
        print(f"[INFO] Filtered to {len(inventory)} files WITH BV number.", file=sys.stderr)
    elif only_without_bv:
        inventory = [e for e in inventory if not e.get("has_videoid")]
        print(f"[INFO] Filtered to {len(inventory)} files WITHOUT BV number.", file=sys.stderr)

    if not inventory:
        print("[ERROR] No files to process after filtering.", file=sys.stderr)
        sys.exit(1)

    # Sort inventory by priority class, then by slug for determinism
    inventory_sorted = sorted(inventory, key=lambda e: (
        get_priority_class(e),
        e.get("slug", ""),
    ))

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    # Verify music_dir exists
    music_path = Path(music_dir)
    if not music_path.is_dir():
        print(f"[ERROR] Music directory not found: {music_path}", file=sys.stderr)
        sys.exit(1)

    # ── Build jobs grouped by priority ─────────────────────────────────
    # Within each priority, we parse the file and build a job.
    priority_jobs: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    stats = {"total": 0, "parsed": 0, "skipped": 0, "errors": 0}

    for entry in inventory_sorted:
        stats["total"] += 1
        priority = get_priority_class(entry)
        slug = entry.get("slug", "")

        # Determine the file path
        file_rel = entry.get("file", f"music/{slug}.md")
        file_path = music_path / Path(file_rel).name
        if not file_path.exists():
            file_path = music_path / f"{slug}.md"
        if not file_path.exists():
            stats["skipped"] += 1
            continue

        content = read_music_file(file_path)
        if content is None:
            stats["skipped"] += 1
            continue

        fields = parse_table_fields(content)
        job = generate_verify_job(slug, fields, entry)
        priority_jobs[priority].append(job)
        stats["parsed"] += 1

    if stats["parsed"] == 0:
        print("[ERROR] No files could be parsed.", file=sys.stderr)
        sys.exit(1)

    # ── Generate batch manifests ───────────────────────────────────────
    batch_num = 0
    total_jobs_written = 0

    for priority in (1, 2, 3):
        jobs = priority_jobs[priority]
        batch_size = BATCH_SIZES[priority]

        for i in range(0, len(jobs), batch_size):
            batch_num += 1
            chunk = jobs[i:i + batch_size]
            manifest = generate_batch_manifest(chunk, batch_num)

            # Record which priority this batch is dominated by
            manifest["primary_priority"] = priority

            out_path = out_root / f"batch-{batch_num:03d}.json"
            write_json(out_path, manifest)
            total_jobs_written += len(chunk)

            # Also create an empty results companion file
            results_path = out_root / f"batch-{batch_num:03d}_results.json"
            if not results_path.exists():
                write_json(results_path, {
                    "batch_id": f"batch-{batch_num:03d}",
                    "status": "pending",
                    "results": [],
                })

    # ── Summary ────────────────────────────────────────────────────────
    print(f"[INFO] Verification job generation complete.", file=sys.stderr)
    print(f"  Files processed:  {stats['parsed']} / {stats['total']}", file=sys.stderr)
    print(f"  Skipped (read err): {stats['skipped']}", file=sys.stderr)
    print(f"  Batches created:  {batch_num}", file=sys.stderr)
    print(f"  Jobs written:     {total_jobs_written}", file=sys.stderr)
    print(f"  Output directory: {out_root.resolve()}", file=sys.stderr)

    # Per-priority breakdown
    for p in (1, 2, 3):
        print(
            f"    Priority {p} ({priority_label(p)}): "
            f"{len(priority_jobs[p])} jobs, "
            f"batch size {BATCH_SIZES[p]}",
            file=sys.stderr,
        )


# ── CLI entry point ─────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Online verification job generator for music knowledge base.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --plan music/10from-bottom-to-the-top.md\n"
            "  %(prog)s --verify music/1282.md qa/verify-jobs/\n"
            "  %(prog)s --batch music/ --output qa/verify-batches/\n"
            "  %(prog)s --batch music/ --output qa/verify-batches/ --only-with-bv\n"
            "  %(prog)s --batch music/ --output qa/verify-batches/ --only-without-bv\n"
        ),
    )

    # Mutually exclusive main actions
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--plan",
        metavar="<file.md>",
        help="Show a structured verification plan for a single file.",
    )
    action.add_argument(
        "--verify",
        nargs=2,
        metavar=("<file>", "<result_dir>"),
        help="Generate a single verification job JSON file.",
    )
    action.add_argument(
        "--batch",
        metavar="<music_dir>",
        help="Generate batch verification jobs for all files in the music directory.",
    )

    # Filter flags (only meaningful with --batch)
    parser.add_argument(
        "--only-with-bv",
        action="store_true",
        help="Only process files that HAVE a video ID in inventory.",
    )
    parser.add_argument(
        "--only-without-bv",
        action="store_true",
        help="Only process files that are WITHOUT a video ID.",
    )

    # --output (required with --batch)
    parser.add_argument(
        "--output",
        metavar="<results_dir>",
        help="Output directory for batch manifests (required with --batch).",
    )

    args = parser.parse_args(argv)

    # Validate
    if args.batch and not args.output:
        parser.error("--output is required when using --batch")

    if (args.only_with_bv or args.only_without_bv) and not args.batch:
        parser.error(
            "--only-with-bv / --only-without-bv are only meaningful with --batch"
        )

    if args.only_with_bv and args.only_without_bv:
        parser.error("--only-with-bv and --only-without-bv are mutually exclusive")

    return args


def main() -> None:
    args = parse_args()

    if args.plan:
        mode_plan(args.plan)
    elif args.verify:
        mode_verify(args.verify[0], args.verify[1])
    elif args.batch:
        mode_batch(
            music_dir=args.batch,
            output_dir=args.output,
            only_with_bv=args.only_with_bv if args.only_with_bv else None,
            only_without_bv=args.only_without_bv if args.only_without_bv else None,
        )


if __name__ == "__main__":
    main()
