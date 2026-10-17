from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from company_dataset.models import Candidate, utc_now
from company_dataset.sources import SOURCES

NAME_PRIORITY = ("lastroundai", "moonie", "kaleb", "latmay")


@dataclass
class MergeStats:
    duplicate_rows: int = 0
    unique_candidates: int = 0


def _pick_name(names_by_source: dict[str, str]) -> tuple[str | None, str]:
    for source in NAME_PRIORITY:
        if names_by_source.get(source):
            return names_by_source[source], source
    for source in sorted(names_by_source):
        if names_by_source[source]:
            return names_by_source[source], source
    return None, ""


def merge_records(records) -> tuple[list[Candidate], MergeStats]:
    by_key: dict[tuple[str, str], Candidate] = {}
    names_by_key: dict[tuple[str, str], dict[str, str]] = {}
    stats = MergeStats()
    for rec in records:
        key = (rec.ats, rec.code.casefold())
        names = names_by_key.setdefault(key, {})
        if rec.name and rec.source not in names:
            names[rec.source] = rec.name
        cand = by_key.get(key)
        if cand is None:
            by_key[key] = Candidate(
                ats=rec.ats,
                codes=[rec.code],
                region=rec.region,
                careersite_urls=[rec.careersite_url] if rec.careersite_url else [],
                sources=[rec.source],
                row_count=1,
            )
            continue
        stats.duplicate_rows += 1
        cand.row_count += 1
        if rec.code not in cand.codes:
            cand.codes.append(rec.code)
        if rec.region == "eu":
            cand.region = "eu"
        if rec.source not in cand.sources:
            cand.sources.append(rec.source)
        if rec.careersite_url and rec.careersite_url not in cand.careersite_urls:
            cand.careersite_urls.append(rec.careersite_url)
    candidates = sorted(by_key.values(), key=lambda c: (c.ats, c.codes[0].casefold()))
    for cand in candidates:
        names = names_by_key[(cand.ats, cand.codes[0].casefold())]
        cand.name, cand.name_source = _pick_name(names)
    stats.unique_candidates = len(candidates)
    return candidates, stats


def run_build(dirs: dict) -> dict:
    all_records = []
    all_rejects = []
    per_source: dict[str, dict] = {}
    for mod in SOURCES:
        path = dirs["raw"] / mod.META.name / mod.META.filename
        records, rejects = mod.parse(path)
        all_records.extend(records)
        all_rejects.extend(rejects)
        per_source[mod.META.name] = {
            "file_present": path.exists(),
            "records": len(records),
            "rejects": len(rejects),
            "rows_read": len(records) + len(rejects),
            "reject_reasons": dict(Counter(r.reason for r in rejects)),
        }
    candidates, merge_stats = merge_records(all_records)

    candidates_path = dirs["intermediate"] / "candidates.csv"
    with open(candidates_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ats", "code", "alt_codes", "region", "name", "name_source", "careersite_urls", "sources", "row_count"])
        for cand in candidates:
            writer.writerow([
                cand.ats,
                cand.codes[0],
                ";".join(cand.codes[1:]),
                cand.region or "",
                cand.name or "",
                cand.name_source,
                "; ".join(cand.careersite_urls),
                "; ".join(cand.sources),
                cand.row_count,
            ])

    rejects_path = dirs["intermediate"] / "source_rejects.csv"
    with open(rejects_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["source", "reason", "detail", "row_ref", "ats", "code", "raw_json"])
        for reject in all_rejects:
            writer.writerow([
                reject.source,
                reject.reason,
                reject.detail,
                reject.row_ref,
                reject.ats,
                reject.code,
                json.dumps(reject.raw, ensure_ascii=False),
            ])

    stats = {
        "generated_at": utc_now(),
        "per_source": per_source,
        "total_source_rows": sum(v["rows_read"] for v in per_source.values()),
        "in_scope_records": len(all_records),
        "rejected_source_rows": len(all_rejects),
        "unique_candidates": merge_stats.unique_candidates,
        "duplicate_rows": merge_stats.duplicate_rows,
    }
    stats_path = dirs["intermediate"] / "build_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2))
    print(
        f"[build] source rows={stats['total_source_rows']} in_scope={stats['in_scope_records']} "
        f"rejected={stats['rejected_source_rows']} unique_candidates={stats['unique_candidates']} "
        f"duplicate_rows_merged={stats['duplicate_rows']}"
    )
    return stats


def load_candidates(dirs: dict) -> list[Candidate]:
    path = Path(dirs["intermediate"]) / "candidates.csv"
    candidates: list[Candidate] = []
    if not path.exists():
        return candidates
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            alt = [c for c in (row.get("alt_codes") or "").split(";") if c]
            candidates.append(
                Candidate(
                    ats=row["ats"],
                    codes=[row["code"]] + alt,
                    region=row.get("region") or None,
                    name=row.get("name") or None,
                    name_source=row.get("name_source") or "",
                    careersite_urls=[u for u in (row.get("careersite_urls") or "").split("; ") if u],
                    sources=[s for s in (row.get("sources") or "").split("; ") if s],
                    row_count=int(row.get("row_count") or 1),
                )
            )
    return candidates
