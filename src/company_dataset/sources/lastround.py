from __future__ import annotations

import csv
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, LEVER, is_valid_slug

META = SourceMeta(
    name="lastroundai",
    description="LastRound AI ATS Company Directory (9,935 companies mapped to ATS vendor and job-board slug)",
    download_url="https://raw.githubusercontent.com/fyrosofttech/lastroundai-hiring-data/main/ats-directory/lastroundai-ats-company-directory-2026-08.csv",
    filename="lastroundai-ats-company-directory-2026-08.csv",
    license="CC-BY-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    license_note="",
    attribution="LastRound AI (lastroundai.com), crawled July-August 2026",
)

VENDOR_MAP = {"greenhouse": GREENHOUSE, "lever": LEVER, "ashby": ASHBY}


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            vendor = (row.get("ats_vendor") or "").strip().lower()
            ref = f"line {i}"
            ats = VENDOR_MAP.get(vendor)
            if ats is None:
                rejects.append(Reject(source=META.name, reason="unsupported_ats", detail=vendor or "(empty)", row_ref=ref, raw=dict(row)))
                continue
            slug = (row.get("board_slug") or "").strip()
            if not is_valid_slug(slug):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=slug, row_ref=ref, ats=ats, raw=dict(row)))
                continue
            name = (row.get("company_name") or "").strip() or None
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ats,
                    code=slug,
                    name=name,
                    row_ref=ref,
                    raw=dict(row),
                )
            )
    return records, rejects
