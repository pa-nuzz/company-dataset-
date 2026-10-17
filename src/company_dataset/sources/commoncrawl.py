from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from company_dataset.models import Reject, SourceMeta, SourceRecord
from company_dataset.normalize import ASHBY, GREENHOUSE, is_valid_slug

META = SourceMeta(
    name="commoncrawl",
    description="Common Crawl index harvest (board tokens extracted from publicly crawled job-board URLs across recent crawls)",
    download_url="https://index.commoncrawl.org/",
    filename="tokens.csv",
    license="CC ToU (factual URL data)",
    license_url="https://commoncrawl.org/terms-of-use/",
    license_note="Only URL path segments (factual board identifiers) are extracted; every token is independently live-verified against the vendor's public API before export. No page content is used.",
    attribution="Common Crawl Foundation, crawls CC-MAIN-2026-34 and CC-MAIN-2026-39",
)

CRAWLS = ["CC-MAIN-2026-34", "CC-MAIN-2026-39"]
HOSTS = {
    "job-boards.greenhouse.io": GREENHOUSE,
    "jobs.ashbyhq.com": ASHBY,
}
CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_EXCLUDE_TOKENS = {"embed", "docs", "jobs", "api", "assets", "static", "favicon", "robots"}

_TOKEN_RE = re.compile(r"https?://[^/]+/([^/?#]+)")


def _query_bucket(client, host: str, char: str, crawl: str, timeout: float = 90.0) -> list[str]:
    """Query one letter bucket and extract first path segment from each URL."""
    q = quote(f"{host}/{char}", safe="") + "*"
    url = f"https://index.commoncrawl.org/{crawl}-index?url={q}&output=json"
    for attempt in range(3):
        try:
            resp = client.get(url)
            if resp.status == 200:
                tokens: set[str] = set()
                for line in resp.text.splitlines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except ValueError:
                        continue
                    m = _TOKEN_RE.match(data.get("url", ""))
                    if m:
                        tok = m.group(1)
                        if tok not in _EXCLUDE_TOKENS:
                            tokens.add(tok)
                return sorted(tokens)
            if resp.status in (400, 404):
                return []
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return []


def run_download(dest_dir: Path, client) -> None:
    """Harvest board tokens from CC index server, letter by letter, with resumable cache."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    cache_path = dest_dir / "harvest_cache.json"
    cache: dict[str, list[str]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    all_tokens: dict[str, set[str]] = {GREENHOUSE: set(), ASHBY: set()}
    total_new = 0
    for host, ats in HOSTS.items():
        for crawl in CRAWLS:
            for ch in CHARS:
                key = f"{host}/{ch}"
                if key in cache:
                    tokens = cache[key]
                else:
                    tokens = _query_bucket(client, host, ch, crawl)
                    cache[key] = tokens
                    cache_path.write_text(json.dumps(cache), encoding="utf-8")
                    total_new += len(tokens)
                    print(f"[commoncrawl] {key}: {len(tokens)} tokens")
                for tok in tokens:
                    all_tokens[ats].add(tok)

    rows: list[tuple[str, str]] = []
    for ats, tokens in all_tokens.items():
        for tok in sorted(tokens):
            rows.append((ats, tok))
    with open(dest_dir / META.filename, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ats", "code"])
        writer.writerows(rows)
    print(f"[commoncrawl] harvested {len(rows)} unique tokens (gh={len(all_tokens[GREENHOUSE])}, ashby={len(all_tokens[ASHBY])})")


def parse(path: Path):
    records: list[SourceRecord] = []
    rejects: list[Reject] = []
    if not Path(path).exists():
        return records, rejects
    with open(path, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            ats = (row.get("ats") or "").strip()
            code = (row.get("code") or "").strip()
            ref = f"line {i}"
            if ats not in (GREENHOUSE, ASHBY):
                rejects.append(Reject(source=META.name, reason="unsupported_ats", detail=ats, row_ref=ref))
                continue
            if not is_valid_slug(code):
                rejects.append(Reject(source=META.name, reason="invalid_slug", detail=code, row_ref=ref, ats=ats))
                continue
            records.append(
                SourceRecord(
                    source=META.name,
                    ats=ats,
                    code=code,
                    row_ref=ref,
                )
            )
    return records, rejects
