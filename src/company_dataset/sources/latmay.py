from __future__ import annotations

import csv
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, LEVER, parse_board_url

META = SourceMeta(
    name="latmay",
    description="Latmay ATS Career Page URLs (69,638 canonical career page URLs across 40 ATS platforms)",
    download_url="https://huggingface.co/datasets/latmay/ats-career-page-urls/resolve/main/ats_career_page_urls.csv",
    filename="ats_career_page_urls.csv",
    license="CC-BY-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    license_note="",
    attribution="Latmay (latmay.com), dataset snapshot August 2026",
)

PLATFORM_MAP = {"Greenhouse": GREENHOUSE, "Lever": LEVER, "Ashby": ASHBY}


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            platform = (row.get("ats_platform") or "").strip()
            ats = PLATFORM_MAP.get(platform)
            url = (row.get("canonical_url") or "").strip()
            ref = f"line {i}"
            if ats is None:
                rejects.append(Reject(source=META.name, reason="unsupported_ats", detail=platform or "(empty)", row_ref=ref, raw=dict(row)))
                continue
            parsed = parse_board_url(url)
            if parsed is None:
                rejects.append(Reject(source=META.name, reason="unparseable_url", detail=url, row_ref=ref, ats=ats, raw=dict(row)))
                continue
            if parsed.ats != ats:
                rejects.append(Reject(source=META.name, reason="platform_url_mismatch", detail=f"label={platform} url_host_ats={parsed.ats}", row_ref=ref, ats=ats, raw=dict(row)))
                continue
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=parsed.ats,
                    code=parsed.code,
                    region=parsed.region,
                    careersite_url=url,
                    row_ref=ref,
                    raw=dict(row),
                )
            )
    return records, rejects
