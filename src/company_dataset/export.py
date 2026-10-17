from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from company_dataset.models import REQUIRED_FIELDS, utc_now
from company_dataset.normalize import canonical_board_url

COMPANY_COLUMNS = [
    "name",
    "description",
    "linkedin_url",
    "website_url",
    "careersite_url",
    "ats_system",
    "ats_code",
    "country",
    "jobs_count",
    "country_basis",
    "region",
    "name_source",
    "name_is_slug",
    "validated_at",
    "sources",
    "source_row_count",
    "source_careersite_urls",
    "potential_duplicate_website",
]

REJECT_COLUMNS = [
    "source",
    "reason",
    "detail",
    "row_ref",
    "ats_system",
    "ats_code",
    "name",
    "careersite_url",
    "raw_json",
]


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def _load_candidates(dirs: dict) -> list[dict]:
    path = dirs["intermediate"] / "candidates.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_source_rejects(dirs: dict) -> list[list]:
    path = dirs["intermediate"] / "source_rejects.csv"
    rows: list[list] = []
    if not path.exists():
        return rows
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append([
                row["source"],
                row["reason"],
                row["detail"],
                row["row_ref"],
                row.get("ats") or "",
                row.get("code") or "",
                "",
                "",
                row.get("raw_json") or "",
            ])
    return rows


def run_export(dirs: dict) -> dict:
    candidates = _load_candidates(dirs)
    cache = _read_json(dirs["cache"] / "validation.json", {}) or {}
    enrichment = _read_json(dirs["cache"] / "enrichment.json", {}) or {}
    build_stats = _read_json(dirs["intermediate"] / "build_stats.json", {}) or {}
    manifest = _read_json(dirs["intermediate"] / "manifest.json", []) or []

    companies: list[dict] = []
    validation_rejects: list[list] = []
    for cand in candidates:
        ats = cand["ats"]
        code = cand["code"]
        key = f"{ats}:{code.casefold()}"
        outcome = cache.get(key)
        if outcome is None:
            validation_rejects.append([cand.get("sources", ""), "not_validated", "no validation result; run validate stage", "", ats, code, cand.get("name") or "", cand.get("careersite_urls") or "", ""])
            continue
        if outcome.get("status") != "valid":
            reason = "validation_failed" if outcome.get("status") == "invalid" else "validation_unresolved"
            detail = f'http={outcome.get("http_status")} error={outcome.get("error") or ""}'
            validation_rejects.append([cand.get("sources", ""), reason, detail, "", ats, code, cand.get("name") or "", cand.get("careersite_urls") or "", ""])
            continue
        code_validated = outcome.get("code_validated") or code
        region = outcome.get("region_answered") or cand.get("region") or None
        company_name = outcome.get("company_name") or cand.get("name") or ""
        if outcome.get("company_name"):
            name_source = "vendor_api"
        else:
            name_source = cand.get("name_source") or ""
        enr = enrichment.get(key, {})
        companies.append({
            "name": company_name,
            "description": outcome.get("description") or enr.get("description") or "",
            "linkedin_url": enr.get("linkedin_url") or "",
            "website_url": outcome.get("website_url") or enr.get("website_url") or "",
            "careersite_url": canonical_board_url(ats, code_validated, region),
            "ats_system": ats,
            "ats_code": code_validated,
            "country": outcome.get("country") or "",
            "jobs_count": outcome.get("jobs_count") if outcome.get("jobs_count") is not None else "",
            "country_basis": outcome.get("country_basis") or "",
            "region": "eu" if region == "eu" else "",
            "name_source": name_source,
            "name_is_slug": "",
            "validated_at": outcome.get("checked_at") or "",
            "sources": cand.get("sources") or "",
            "source_row_count": cand.get("row_count") or "",
            "source_careersite_urls": cand.get("careersite_urls") or "",
            "potential_duplicate_website": "",
        })

    websites = Counter(row["website_url"] for row in companies if row["website_url"])
    for row in companies:
        row["name_is_slug"] = "yes" if row["name"] and row["name"].casefold() == row["ats_code"].casefold() else ""
        if row["website_url"] and websites[row["website_url"]] > 1:
            row["potential_duplicate_website"] = "yes"

    companies.sort(key=lambda r: (r["ats_system"], r["ats_code"].casefold()))
    output_path = dirs["output"] / "companies.csv"
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COMPANY_COLUMNS)
        writer.writeheader()
        writer.writerows(companies)

    rejected_path = dirs["output"] / "rejected_records.csv"
    rejects = _load_source_rejects(dirs) + validation_rejects
    with open(rejected_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(REJECT_COLUMNS)
        writer.writerows(rejects)

    per_source = build_stats.get("per_source", {})
    source_rows: list[dict] = []
    contributed = Counter()
    for cand in candidates:
        for source in (cand.get("sources") or "").split("; "):
            if source:
                contributed[source] += 1
    for entry in manifest:
        name = entry.get("source", "")
        src_stats = per_source.get(name, {})
        source_rows.append({
            "source": name,
            "description": entry.get("description", ""),
            "download_url": entry.get("download_url", ""),
            "license": entry.get("license", ""),
            "license_url": entry.get("license_url", ""),
            "license_note": entry.get("license_note", ""),
            "attribution": entry.get("attribution", ""),
            "downloaded_at": entry.get("downloaded_at") or "",
            "sha256": entry.get("sha256", ""),
            "size_bytes": entry.get("size_bytes", ""),
            "rows_read": src_stats.get("rows_read", ""),
            "in_scope_records": src_stats.get("records", ""),
            "rejected_rows": src_stats.get("rejects", ""),
            "contributed_candidates": contributed.get(name, ""),
        })
    manifest_path = dirs["output"] / "source_manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "source", "description", "download_url", "license", "license_url", "license_note",
            "attribution", "downloaded_at", "sha256", "size_bytes", "rows_read",
            "in_scope_records", "rejected_rows", "contributed_candidates",
        ])
        writer.writeheader()
        writer.writerows(source_rows)

    total = len(companies)
    completeness = {}
    for field in REQUIRED_FIELDS:
        non_null = sum(1 for row in companies if row[field])
        completeness[field] = {"non_null": non_null, "total": total, "pct": round(100 * non_null / total, 2) if total else 0.0}
    complete_all_required = sum(1 for row in companies if all(row[field] for field in REQUIRED_FIELDS))
    countries = Counter(row["country"] for row in companies if row["country"])
    export_stats = {
        "generated_at": utc_now(),
        "exported_companies": total,
        "by_ats": dict(Counter(row["ats_system"] for row in companies)),
        "completeness": completeness,
        "complete_all_required_fields": {
            "count": complete_all_required,
            "total": total,
            "pct": round(100 * complete_all_required / total, 2) if total else 0.0,
        },
        "country_coverage": {
            "rows_with_country": sum(countries.values()),
            "pct": round(100 * sum(countries.values()) / total, 2) if total else 0.0,
            "breakdown": dict(countries.most_common()),
        },
        "name_is_slug_count": sum(1 for row in companies if row["name_is_slug"]),
        "website_duplicate_flags": sum(1 for row in companies if row["potential_duplicate_website"]),
        "validation_rejects": len(validation_rejects),
        "rejected_rows_total": len(rejects),
    }
    (dirs["intermediate"] / "export_stats.json").write_text(json.dumps(export_stats, indent=2))
    print(
        f"[export] companies={total} rejected={len(rejects)} "
        f"country_coverage={export_stats['country_coverage']['pct']}% "
        f"complete_all_required_fields={complete_all_required}/{total} "
        f"({export_stats['complete_all_required_fields']['pct']}%)"
    )
    return export_stats
