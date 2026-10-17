from __future__ import annotations

import json
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, LEVER, is_valid_slug

META = SourceMeta(
    name="moonie",
    description="moonie0201 ATS Directory ((provider, slug) pairs probed live against provider public APIs)",
    download_url="https://raw.githubusercontent.com/moonie0201/ats-directory/main/companies.jsonl",
    filename="companies.jsonl",
    license="CC0-1.0",
    license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    license_note="",
    attribution="moonie0201/ats-directory",
)

PROVIDER_MAP = {"greenhouse": GREENHOUSE, "lever": LEVER, "ashby": ASHBY}


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            text = line.strip()
            ref = f"line {i}"
            if not text:
                rejects.append(Reject(source=META.name, reason="blank_line", detail="", row_ref=ref))
                continue
            try:
                row = json.loads(text)
            except ValueError:
                rejects.append(Reject(source=META.name, reason="unparseable_row", detail=text[:100], row_ref=ref))
                continue
            provider = (row.get("provider") or "").strip()
            ats = PROVIDER_MAP.get(provider.lower())
            if ats is None:
                rejects.append(Reject(source=META.name, reason="unsupported_ats", detail=provider or "(empty)", row_ref=ref, raw=row))
                continue
            slug = (row.get("slug") or "").strip()
            if not is_valid_slug(slug):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=slug, row_ref=ref, ats=ats, raw=row))
                continue
            status = (row.get("status") or "").strip()
            if status == "dead":
                rejects.append(Reject(source=META.name, reason="source_marked_dead", detail="404/307 at source probe time", row_ref=ref, ats=ats, code=slug, raw=row))
                continue
            region = "eu" if (row.get("region") or "").strip() == "eu" else None
            name = (row.get("name") or "").strip() or None
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ats,
                    code=slug,
                    region=region,
                    name=name,
                    row_ref=ref,
                    raw=row,
                )
            )
    return records, rejects
