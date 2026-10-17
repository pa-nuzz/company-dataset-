from __future__ import annotations

import csv
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, LEVER, is_valid_slug, parse_board_url

META = SourceMeta(
    name="kaleb",
    description="Kaleb Confer Job Board Directory (12,237 board addresses across eight ATS platforms, live-confirmed)",
    download_url="https://kalebconfer-sys.github.io/job-board-directory/job-board-directory.csv",
    filename="job-board-directory.csv",
    license="No formal license",
    license_url="",
    license_note="No formal license file in repository; publisher site states 'free to pull as data... no attribution required'. Incorporated with attribution; FLAGGED for review.",
    attribution="kalebconfer-sys/job-board-directory (revivacatch.com), built 2026-10-15",
)

PLATFORM_MAP = {"greenhouse": GREENHOUSE, "lever": LEVER, "ashby": ASHBY}


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, start=2):
            platform = (row.get("platform") or "").strip().lower()
            ref = f"line {i}"
            ats = PLATFORM_MAP.get(platform)
            if ats is None:
                rejects.append(Reject(source=META.name, reason="unsupported_ats", detail=platform or "(empty)", row_ref=ref, raw=dict(row)))
                continue
            token = (row.get("token") or "").strip()
            if not is_valid_slug(token):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=token, row_ref=ref, ats=ats, raw=dict(row)))
                continue
            region = "eu" if (row.get("region") or "").strip().upper() == "EU" else None
            board_url = (row.get("board_url") or "").strip() or None
            code = token
            parsed = parse_board_url(board_url) if board_url else None
            if parsed is not None and parsed.ats != ats:
                rejects.append(Reject(source=META.name, reason="platform_url_mismatch", detail=f"label={platform} url_host_ats={parsed.ats}", row_ref=ref, ats=ats, code=token, raw=dict(row)))
                continue
            if parsed is not None and parsed.code.casefold() == token.casefold():
                code = parsed.code
                region = parsed.region or region
            name = (row.get("company") or "").strip() or None
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ats,
                    code=code,
                    region=region,
                    name=name,
                    careersite_url=board_url,
                    row_ref=ref,
                    raw=dict(row),
                )
            )
    return records, rejects
