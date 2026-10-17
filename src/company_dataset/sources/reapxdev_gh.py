from __future__ import annotations

import csv
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import GREENHOUSE, is_valid_slug

META = SourceMeta(
    name="reapxdev_greenhouse",
    description="reapxdev Greenhouse Jobs Scraper (14,091 postings with board tokens, company names, board URLs)",
    download_url="https://huggingface.co/datasets/reapxdev/greenhouse-jobs-scraper/resolve/main/greenhouse-jobs-scraper.csv",
    filename="greenhouse-jobs-scraper.csv",
    license="CC-BY-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    license_note="",
    attribution="reapxdev/greenhouse-jobs-scraper (Hugging Face), scraped August 2026",
)

def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects

    # Deduplicate by boardToken - we want one record per board
    seen_tokens = set()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            token = (row.get("boardToken") or "").strip()
            company = (row.get("company") or "").strip()
            board_url = (row.get("boardUrl") or "").strip()
            ref = f"line {i}"

            if not token:
                rejects.append(Reject(source=META.name, reason="empty_token", detail="empty boardToken", row_ref=ref, ats=GREENHOUSE, raw=dict(row)))
                continue

            if not is_valid_slug(token):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=token, row_ref=ref, ats=GREENHOUSE, raw=dict(row)))
                continue

            if token in seen_tokens:
                continue
            seen_tokens.add(token)

            records.append(
                SourceRecord(
                    source=META.name,
                    ats=GREENHOUSE,
                    code=token,
                    name=company or None,
                    careersite_url=board_url or None,
                    row_ref=ref,
                    raw=dict(row),
                )
            )
    return records, rejects