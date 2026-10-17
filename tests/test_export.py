import csv
import json

from company_dataset.export import run_export
from company_dataset.models import REQUIRED_FIELDS


def _dirs(tmp_path):
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
    return dirs


def _write_candidates(dirs, rows):
    path = dirs["intermediate"] / "candidates.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ats", "code", "alt_codes", "region", "name", "name_source", "careersite_urls", "sources", "row_count"])
        for row in rows:
            writer.writerow(row)


def test_required_fields_is_the_real_seven_business_fields():
    assert tuple(REQUIRED_FIELDS) == (
        "name", "description", "linkedin_url", "website_url", "careersite_url", "ats_system", "ats_code",
    )
    assert "country" not in REQUIRED_FIELDS


def test_completeness_uses_ats_system_not_country(tmp_path):
    dirs = _dirs(tmp_path)
    _write_candidates(dirs, [["greenhouse", "acme", "", "", "Acme Inc", "latmay", "https://job-boards.greenhouse.io/acme", "latmay", 1]])
    cache = {
        "greenhouse:acme": {
            "ats": "greenhouse", "code": "acme", "status": "valid", "http_status": 200,
            "jobs_count": 5, "company_name": "Acme Inc", "description": "We build things",
            "website_url": "https://acme.com", "country": "US", "country_basis": "greenhouse_absolute_url",
            "region_answered": None, "code_validated": "acme", "error": None, "checked_at": "2026-01-01T00:00:00Z",
        }
    }
    (dirs["cache"] / "validation.json").write_text(json.dumps(cache))

    stats = run_export(dirs)

    # ats_system must be one of the completeness fields (it is always 100% for
    # exported rows), and country must NOT be treated as a required field.
    assert "ats_system" in stats["completeness"]
    assert "country" not in stats["completeness"]
    assert stats["completeness"]["ats_system"]["pct"] == 100.0
    assert stats["completeness"]["name"]["pct"] == 100.0
    assert stats["completeness"]["description"]["pct"] == 100.0
    assert stats["completeness"]["website_url"]["pct"] == 100.0
    assert stats["completeness"]["careersite_url"]["pct"] == 100.0
    assert stats["completeness"]["ats_code"]["pct"] == 100.0
    # linkedin_url is never populated by this pipeline (no licensed source, never guessed).
    assert stats["completeness"]["linkedin_url"]["pct"] == 0.0


def test_complete_all_required_fields_is_honest_about_linkedin_gap(tmp_path):
    # Even with every OTHER field fully populated, the all-7 count must be 0
    # because linkedin_url is structurally always empty. This is the single
    # most important honesty check in the whole report: per-field percentages
    # must never be mistaken for "records complete across all 7 fields".
    dirs = _dirs(tmp_path)
    _write_candidates(dirs, [["greenhouse", "acme", "", "", "Acme Inc", "latmay", "https://job-boards.greenhouse.io/acme", "latmay", 1]])
    cache = {
        "greenhouse:acme": {
            "ats": "greenhouse", "code": "acme", "status": "valid", "http_status": 200,
            "jobs_count": 5, "company_name": "Acme Inc", "description": "We build things",
            "website_url": "https://acme.com", "country": "US", "country_basis": "greenhouse_absolute_url",
            "region_answered": None, "code_validated": "acme", "error": None, "checked_at": "2026-01-01T00:00:00Z",
        }
    }
    (dirs["cache"] / "validation.json").write_text(json.dumps(cache))

    stats = run_export(dirs)

    assert stats["exported_companies"] == 1
    assert stats["complete_all_required_fields"]["count"] == 0
    assert stats["complete_all_required_fields"]["total"] == 1
    assert stats["complete_all_required_fields"]["pct"] == 0.0


def test_invalid_and_not_validated_candidates_go_to_rejects(tmp_path):
    dirs = _dirs(tmp_path)
    _write_candidates(dirs, [
        ["greenhouse", "acme", "", "", "Acme Inc", "latmay", "https://job-boards.greenhouse.io/acme", "latmay", 1],
        ["lever", "deadco", "", "", "", "", "https://jobs.lever.co/deadco", "latmay", 1],
        ["ashby", "notyet", "", "", "", "", "https://jobs.ashbyhq.com/notyet", "latmay", 1],
    ])
    cache = {
        "greenhouse:acme": {
            "ats": "greenhouse", "code": "acme", "status": "valid", "http_status": 200,
            "jobs_count": 5, "company_name": "Acme Inc", "description": "We build things",
            "website_url": "https://acme.com", "country": "US", "country_basis": "greenhouse_absolute_url",
            "region_answered": None, "code_validated": "acme", "error": None, "checked_at": "2026-01-01T00:00:00Z",
        },
        "lever:deadco": {
            "ats": "lever", "code": "deadco", "status": "invalid", "http_status": 404,
            "jobs_count": None, "company_name": None, "description": None, "website_url": None,
            "country": None, "country_basis": None, "region_answered": None, "code_validated": None,
            "error": "board_not_found", "checked_at": "2026-01-01T00:00:00Z",
        },
        # "ashby:notyet" intentionally absent from the cache -> not_validated
    }
    (dirs["cache"] / "validation.json").write_text(json.dumps(cache))

    stats = run_export(dirs)

    assert stats["exported_companies"] == 1
    rejected_path = dirs["output"] / "rejected_records.csv"
    with open(rejected_path, newline="", encoding="utf-8") as fh:
        rejected = list(csv.DictReader(fh))
    reasons = sorted(r["reason"] for r in rejected)
    assert reasons == ["not_validated", "validation_failed"]
