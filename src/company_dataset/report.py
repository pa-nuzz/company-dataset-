from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from company_dataset.models import REQUIRED_FIELDS, utc_now


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def run_report(dirs: dict) -> dict:
    build_stats = _read_json(dirs["intermediate"] / "build_stats.json", {}) or {}
    validation_stats = _read_json(dirs["intermediate"] / "validation_stats.json", {}) or {}
    export_stats = _read_json(dirs["intermediate"] / "export_stats.json", {}) or {}
    manifest = _read_json(dirs["intermediate"] / "manifest.json", []) or []

    by_status = validation_stats.get("by_status", {})
    by_ats_status = validation_stats.get("by_ats", {})
    exported_by_ats = export_stats.get("by_ats", {})
    completeness = export_stats.get("completeness", {})
    country = export_stats.get("country_coverage", {})
    breakdown = country.get("breakdown", {})

    lines: list[str] = []
    lines.append("# Quality Report: Companies on Greenhouse, Lever and Ashby")
    lines.append("")
    lines.append(f"Generated: {utc_now()}")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Source rows read | {build_stats.get('total_source_rows', 0)} |")
    lines.append(f"| In-scope source records (greenhouse/lever/ashby) | {build_stats.get('in_scope_records', 0)} |")
    lines.append(f"| Source rows rejected at parse | {build_stats.get('rejected_source_rows', 0)} |")
    lines.append(f"| Duplicate source rows merged | {build_stats.get('duplicate_rows', 0)} |")
    lines.append(f"| Unique candidate boards (ats + casefolded code) | {build_stats.get('unique_candidates', 0)} |")
    lines.append(f"| Boards checked live | {validation_stats.get('checked', 0)} |")
    lines.append(f"| Validated live boards | {by_status.get('valid', 0)} |")
    lines.append(f"| Invalid boards (404) | {by_status.get('invalid', 0)} |")
    lines.append(f"| Unresolved boards (kept for review) | {by_status.get('unresolved', 0)} |")
    lines.append(f"| **Exported companies** | **{export_stats.get('exported_companies', 0)}** |")
    complete_all = export_stats.get("complete_all_required_fields", {})
    lines.append(
        f"| **Records complete across all 7 required fields** | "
        f"**{complete_all.get('count', 0)} ({complete_all.get('pct', 0)}%)** |"
    )
    lines.append("")

    lines.append("## Source audit")
    lines.append("")
    lines.append("| Source | License | Rows read | In-scope | Rejected | Contributed candidates |")
    lines.append("|---|---|---|---|---|---|")
    per_source = build_stats.get("per_source", {})
    contributed = Counter()
    manifest_csv = dirs["output"] / "source_manifest.csv"
    if manifest_csv.exists():
        with open(manifest_csv, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    contributed[row["source"]] = int(row["contributed_candidates"] or 0)
                except (KeyError, ValueError):
                    continue
    manifest_by_name = {entry.get("source"): entry for entry in manifest}
    for name in per_source:
        entry = manifest_by_name.get(name, {})
        stats = per_source[name]
        lines.append(
            f"| {name} | {entry.get('license', '?')} | {stats.get('rows_read', 0)} | "
            f"{stats.get('records', 0)} | {stats.get('rejects', 0)} | {contributed.get(name, 0)} |"
        )
    lines.append("")
    for entry in manifest:
        note = entry.get("license_note")
        if note:
            lines.append(f"- **License flag ({entry.get('source')}):** {note}")
    lines.append("")

    lines.append("## Board validation by ATS")
    lines.append("")
    lines.append("| ATS | Candidates | Valid | Invalid | Unresolved | Exported |")
    lines.append("|---|---|---|---|---|---|")
    for ats in ("ashby", "greenhouse", "lever"):
        row = by_ats_status.get(ats, {})
        lines.append(
            f"| {ats} | {sum(row.values())} | {row.get('valid', 0)} | {row.get('invalid', 0)} | "
            f"{row.get('unresolved', 0)} | {exported_by_ats.get(ats, 0)} |"
        )
    lines.append("")

    lines.append("## Metadata completeness (exported rows)")
    lines.append("")
    lines.append("| Field | Non-null | Total | Coverage |")
    lines.append("|---|---|---|---|")
    for field in REQUIRED_FIELDS:
        comp = completeness.get(field, {})
        lines.append(f"| {field} | {comp.get('non_null', 0)} | {comp.get('total', 0)} | {comp.get('pct', 0)}% |")
    lines.append("")
    lines.append(
        f"Records with ALL 7 required fields populated simultaneously: "
        f"{complete_all.get('count', 0)} / {complete_all.get('total', 0)} ({complete_all.get('pct', 0)}%). "
        f"This is not the average of the per-field percentages above — a row only counts here if every "
        f"required field is non-empty at once. `country` is additional metadata, not one of the 7 required "
        f"fields, and is reported separately below."
    )
    lines.append("")
    lines.append(f"Rows where name equals the board slug: {export_stats.get('name_is_slug_count', 0)}.")
    lines.append("")

    lines.append("## Country coverage")
    lines.append("")
    lines.append(f"- Exported rows with country: {country.get('rows_with_country', 0)} ({country.get('pct', 0)}%)")
    for code in ("US", "GB", "CA"):
        lines.append(f"- {code}: {breakdown.get(code, 0)}")
    lines.append(f"- All other countries combined: {sum(v for k, v in breakdown.items() if k not in ('US', 'GB', 'CA'))}")
    lines.append("")
    lines.append("Country is set only when every job posting on the board reports the same country (Lever ISO `country` field; Ashby `addressCountry`), or when a source dataset explicitly provides it. It is never guessed.")
    lines.append("")

    lines.append("## Duplicates")
    lines.append("")
    lines.append(f"- Source rows merged into an existing board: {build_stats.get('duplicate_rows', 0)}")
    lines.append(f"- Exported rows flagged as sharing a website URL with another exported row (cross-board duplicate signal): {export_stats.get('website_duplicate_flags', 0)}")
    lines.append("")

    lines.append("## Policy and limitations")
    lines.append("")
    lines.append("- `linkedin_url` is intentionally empty for all rows: no licensed source provides verified LinkedIn URLs and this pipeline never guesses them.")
    lines.append("- `description` comes only from the Greenhouse board `content` field (company-authored, served by Greenhouse's public Job Board API); Lever and Ashby public APIs expose no company description.")
    lines.append("- `website_url` comes only from the origin of Greenhouse `absolute_url` job links that point at a company's own (non-Greenhouse) domain; it is never derived from company names.")
    lines.append("- Boards with zero open jobs are valid; emptiness never marks a board invalid.")
    lines.append("- Boards that failed validation with 404 are excluded from companies.csv and written to rejected_records.csv; network-level failures are marked `validation_unresolved` and kept for review and re-runs.")
    lines.append("- Lever slugs are case-sensitive; this pipeline preserves casing, dedupes case-insensitively, and records the exact casing that validated.")
    lines.append("- Lever boards are probed on the global instance first, then the EU instance (`api.eu.lever.co`).")
    lines.append("- Raw source files are cached unmodified under `data/raw/`; cleaned outputs live under `data/output/`.")
    lines.append("- The kalebconfer-sys job-board-directory publishes no formal license; its site states the data is free to use with no attribution required. It is incorporated with attribution and flagged in `source_manifest.csv` for review.")
    lines.append("- Validation hits only the three vendors' documented public job board endpoints with bounded concurrency, per-host rate limiting, timeouts, retries, and a resumable cache (`data/cache/validation.json`).")
    lines.append("- Deduplication folds case for the merge key (`ats + casefolded code`), but Lever board slugs are documented case-sensitive. A handful of candidates (observed: 4) have multiple raw casings merged into one board; only the casing that validates first is kept. If two of these were ever genuinely distinct live companies rather than inconsistent scraping of the same one, the second would be silently dropped. This is a known, unmitigated edge case, not something this run can rule out.")
    lines.append("- This run recorded zero `unresolved` boards across every candidate checked live. That is a clean result but an unusually clean one for ~29.5k calls against rate-limited third-party APIs; treat it as this run's measured result, not a guarantee that a future run (or `--revalidate`) will also see zero transient failures.")
    lines.append("")

    lines.append("## Reproduction")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 -m venv .venv")
    lines.append("source .venv/bin/activate")
    lines.append('pip install -e ".[dev]"')
    lines.append("pytest")
    lines.append("company-dataset all")
    lines.append("```")
    lines.append("")

    reports_dir = dirs["reports"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("=== FINAL COUNTS ===")
    print(f"source_records: {build_stats.get('total_source_rows', 0)}")
    print(f"in_scope_records: {build_stats.get('in_scope_records', 0)}")
    print(f"rejected_source_rows: {build_stats.get('rejected_source_rows', 0)}")
    print(f"duplicate_rows_merged: {build_stats.get('duplicate_rows', 0)}")
    print(f"unique_candidate_boards: {build_stats.get('unique_candidates', 0)}")
    print(f"validated_boards: {by_status.get('valid', 0)}")
    print(f"invalid_boards: {by_status.get('invalid', 0)}")
    print(f"unresolved_boards: {by_status.get('unresolved', 0)}")
    print(f"exported_companies: {export_stats.get('exported_companies', 0)}")
    for field in REQUIRED_FIELDS:
        comp = completeness.get(field, {})
        print(f"completeness.{field}: {comp.get('non_null', 0)}/{comp.get('total', 0)} ({comp.get('pct', 0)}%)")
    print(
        f"complete_all_required_fields: {complete_all.get('count', 0)}/{complete_all.get('total', 0)} "
        f"({complete_all.get('pct', 0)}%)"
    )
    print(f"country_coverage: {country.get('rows_with_country', 0)}/{export_stats.get('exported_companies', 0)} ({country.get('pct', 0)}%)")
    summary = {
        "source_records": build_stats.get("total_source_rows", 0),
        "exported_companies": export_stats.get("exported_companies", 0),
        "validated_boards": by_status.get("valid", 0),
        "complete_all_required_fields": complete_all.get("count", 0),
    }
    return summary
