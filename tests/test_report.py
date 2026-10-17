import csv
import json

from company_dataset.report import run_report


def _write_json(path, payload):
    path.write_text(json.dumps(payload))


def test_report_renders_contributed_candidates(tmp_path):
    dirs = {
        "data": tmp_path,
        "raw": tmp_path / "raw",
        "cache": tmp_path / "cache",
        "intermediate": tmp_path / "intermediate",
        "output": tmp_path / "output",
        "reports": tmp_path / "reports",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    intermediate = dirs["intermediate"]
    _write_json(intermediate / "build_stats.json", {
        "total_source_rows": 10,
        "in_scope_records": 6,
        "rejected_source_rows": 4,
        "duplicate_rows_merged": 2,
        "unique_candidates": 4,
        "per_source": {
            "latmay": {"rows_read": 10, "records": 6, "rejects": 4, "reject_reasons": {}, "file_present": True},
            "moonie": {"rows_read": 3, "records": 3, "rejects": 0, "reject_reasons": {}, "file_present": True},
        },
    })
    _write_json(intermediate / "validation_stats.json", {
        "checked": 4,
        "by_status": {"valid": 3, "invalid": 1, "unresolved": 0},
        "by_ats": {"lever": {"valid": 3, "invalid": 1}},
    })
    _write_json(intermediate / "export_stats.json", {
        "exported_companies": 3,
        "by_ats": {"lever": 3},
        "completeness": {
            f: {"non_null": 0 if f == "linkedin_url" else 3, "total": 3, "pct": 0.0 if f == "linkedin_url" else 100.0}
            for f in ("name", "description", "linkedin_url", "website_url", "careersite_url", "ats_system", "ats_code")
        },
        "complete_all_required_fields": {"count": 0, "total": 3, "pct": 0.0},
        "country_coverage": {"rows_with_country": 2, "pct": 66.6, "breakdown": {"US": 2}},
        "name_is_slug_count": 0,
        "website_duplicate_flags": 0,
    })
    _write_json(intermediate / "manifest.json", [
        {"source": "latmay", "license": "CC-BY-4.0", "license_note": ""},
        {"source": "moonie", "license": "CC0-1.0", "license_note": ""},
    ])
    out_manifest = dirs["output"] / "source_manifest.csv"
    columns = ["source", "description", "download_url", "license", "license_url", "license_note", "attribution", "downloaded_at", "sha256", "size_bytes", "rows_read", "in_scope_records", "rejected_rows", "contributed_candidates"]
    with open(out_manifest, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        writer.writerow(["latmay", "x", "y", "CC-BY-4.0", "", "", "", "", "abc", 1, 10, 6, 4, 7])
        writer.writerow(["moonie", "x", "y", "CC0-1.0", "", "", "", "", "def", 1, 3, 3, 0, 4])

    run_report(dirs)
    text = (dirs["reports"] / "quality_report.md").read_text(encoding="utf-8")
    assert "| latmay | CC-BY-4.0 | 10 | 6 | 4 | 7 |" in text
    assert "| moonie | CC0-1.0 | 3 | 3 | 0 | 4 |" in text
    assert "**Exported companies** | **3**" in text
    assert "**Records complete across all 7 required fields** | **0 (0.0%)**" in text
    assert "| ats_system | 3 | 3 | 100.0% |" in text
    # The "Metadata completeness" table must list the 7 required fields only;
    # `country` belongs in its own "Country coverage" section, not here.
    assert "| country | 2 | 3 | 66.6% |" not in text
