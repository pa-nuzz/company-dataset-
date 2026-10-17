from __future__ import annotations

import json
from pathlib import Path

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, LEVER, is_valid_slug

META = SourceMeta(
    name="feashliaa",
    description="Job Board Aggregator active company lists (per-ATS board slugs harvested from Common Crawl CDX, refreshed daily)",
    download_url="https://github.com/Feashliaa/job-board-aggregator",
    filename="companies.json",
    license="MIT",
    license_url="https://opensource.org/licenses/MIT",
    license_note="MIT covers the repository including its data files. Board slugs are factual identifiers; each is live-verified against the vendor API before export.",
    attribution="Feashliaa/job-board-aggregator (feashliaa.github.io/job-board-aggregator), snapshot October 2026",
)

_FILES = {
    "greenhouse": "greenhouse_companies.json",
    "lever": "lever_companies.json",
    "ashby": "ashby_companies.json",
}
_BASE = "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/"


def run_download(dest_dir: Path, client) -> None:
    """Download per-ATS company lists and combine into one JSON file."""
    combined: dict[str, list[str]] = {}
    for ats, filename in _FILES.items():
        try:
            resp = client.get(_BASE + filename)
            if resp.status == 200:
                combined[ats] = json.loads(resp.text)
            else:
                combined[ats] = []
        except Exception:
            combined[ats] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / META.filename).write_text(json.dumps(combined), encoding="utf-8")


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for ats, slugs in data.items():
        for i, slug in enumerate(slugs):
            ref = f"{ats}[{i}]"
            if not isinstance(slug, str):
                continue
            slug = slug.strip()
            if not is_valid_slug(slug):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=slug, row_ref=ref, ats=ats))
                continue
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ats,
                    code=slug,
                    row_ref=ref,
                )
            )
    return records, rejects
