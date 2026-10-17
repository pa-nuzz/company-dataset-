from __future__ import annotations

import csv
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, is_valid_slug

META = SourceMeta(
    name="reapxdev_ashby",
    description="reapxdev Ashby Jobs Scraper (3,194 postings with org slugs and company names)",
    download_url="https://huggingface.co/datasets/reapxdev/ashby-jobs-scraper/resolve/main/ashby-jobs-scraper.csv",
    filename="ashby-jobs-scraper.csv",
    license="CC-BY-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    license_note="",
    attribution="reapxdev/ashby-jobs-scraper (Hugging Face), scraped August 2026",
)

def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects

    seen_tokens = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            token = (row.get("orgSlug") or "").strip()
            company = (row.get("companyName") or "").strip()
            ref = f"line {i}"

            if not token:
                rejects.append(Reject(source=META.name, reason="empty_token", detail="empty orgSlug", row_ref=ref, ats=ASHBY, raw=dict(row)))
                continue

            if not is_valid_slug(token):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=token, row_ref=ref, ats=ASHBY, raw=dict(row)))
                continue

            if token in seen_tokens:
                continue
            seen_tokens.add(token)

            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ASHBY,
                    code=token,
                    name=company or None,
                    row_ref=ref,
                    raw=dict(row),
                )
            )
    return records, rejects