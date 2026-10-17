from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

from company_dataset.build import load_candidates
from company_dataset.http import HttpClient, RequestError
from company_dataset.models import utc_now

_EXCLUDE_DOMAINS = (
    "lever.co", "leverpatch.com", "greenhouse.io", "ashbyhq.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "gstatic.com",
    "linkedin.com", "lnkd.in", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "youtube.com", "tiktok.com", "apple.com", "google.com",
    "googletagmanager.com", "googleapis.com", "w3.org", "schema.org",
    "cloudflare.com", "jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
)

_LINKEDIN_RE = re.compile(
    r'href="(?:https?://(?:[a-z]+\.)?)?linkedin\.com/company/([A-Za-z0-9\-_.%]+)["/?]'
)

_DESC_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']{20,2000})["\']',
    re.I,
)
_DESC_RE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']{20,2000})["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
    re.I,
)


def extract_lever_website(html: str) -> str | None:
    """Extract the company website URL from a Lever board page footer.

    Lever board pages often include a "Home Page" link in the footer pointing
    at the company's own website. Returns the scheme + host (no path).
    """
    links = re.findall(r'href="(https?://[^"]+)"', html)
    for link in links:
        try:
            parts = urlsplit(link)
        except ValueError:
            continue
        host = (parts.hostname or "").lower()
        if not host:
            continue
        if any(host == d or host.endswith("." + d) or d in link for d in _EXCLUDE_DOMAINS):
            continue
        # Strip path — return just scheme + host as the company website
        return f"{parts.scheme}://{parts.netloc}"
    return None


def extract_linkedin(html: str) -> str | None:
    """Extract a LinkedIn company URL from a company's own homepage HTML."""
    m = _LINKEDIN_RE.search(html)
    if not m:
        return None
    slug = m.group(1).rstrip("/")
    if not slug:
        return None
    return f"https://www.linkedin.com/company/{slug}"


def extract_description(html: str) -> str | None:
    """Extract a company-level description from homepage meta tags."""
    m = _DESC_RE.search(html) or _DESC_RE_REV.search(html)
    if not m:
        return None
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 20:
        return None
    return text[:1000]


def _fetch_html(client: HttpClient, url: str, max_bytes: int = 2_000_000) -> str:
    try:
        resp = client.get(url)
        if resp.status == 200:
            return resp.text[:max_bytes]
    except RequestError:
        pass
    return ""


def run_enrich(
    dirs: dict,
    client: HttpClient | None = None,
    max_workers: int = 10,
    timeout: float = 20.0,
) -> dict:
    """Enrich valid boards with website_url (Lever footer), linkedin_url and description (homepage).

    Reads the validation cache for valid boards, fetches company pages politely,
    and stores results in data/cache/enrichment.json keyed by board key.
    """
    client = client or HttpClient(timeout=timeout, per_host_interval=0.1)
    cache_path = Path(dirs["cache"]) / "enrichment.json"
    cache: dict[str, dict] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}

    candidates = load_candidates(dirs)
    validation_path = Path(dirs["cache"]) / "validation.json"
    if not validation_path.exists():
        print("[enrich] no validation cache found; run validate stage first")
        return {}
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    valid_boards = []
    for cand in candidates:
        key = cand.key
        outcome = validation.get(key)
        if outcome and outcome.get("status") == "valid":
            valid_boards.append({
                "key": key,
                "ats": cand.ats,
                "code": cand.code,
                "careersite_url": f"https://jobs.lever.co/{cand.code}" if cand.ats == "lever" else "",
                "website_url": outcome.get("website_url") or "",
                "description": outcome.get("description") or "",
            })

    print(f"[enrich] {len(valid_boards)} valid boards to enrich")

    # Phase 1: discover websites for Lever boards (fetch board page, extract footer link)
    lever_todo = [
        b for b in valid_boards
        if b["ats"] == "lever"
        and not b["website_url"]
        and not cache.get(b["key"], {}).get("website_url")
        and not cache.get(b["key"], {}).get("website_checked")
    ]
    print(f"[enrich] phase 1: {len(lever_todo)} Lever boards to fetch for website discovery")

    def _lever_fetch(board):
        html = _fetch_html(client, board["careersite_url"])
        website = extract_lever_website(html) if html else None
        entry = cache.setdefault(board["key"], {})
        entry["website_checked"] = True
        if website:
            entry["website_url"] = website
        return website

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_lever_fetch, b): b for b in lever_todo}
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % 250 == 0:
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
                print(f"[enrich] lever phase: {done}/{len(lever_todo)}")

    # Phase 2: fetch homepages for boards with a known website
    homepage_todo = []
    for board in valid_boards:
        entry = cache.get(board["key"], {})
        website = board["website_url"] or entry.get("website_url") or ""
        if website and not entry.get("homepage_checked"):
            homepage_todo.append({**board, "website_url": website})

    print(f"[enrich] phase 2: {len(homepage_todo)} homepages to fetch for linkedin/description")

    def _homepage_fetch(board):
        html = _fetch_html(client, board["website_url"])
        entry = cache.setdefault(board["key"], {})
        entry["homepage_checked"] = True
        if html:
            linkedin = extract_linkedin(html)
            description = extract_description(html)
            if linkedin:
                entry["linkedin_url"] = linkedin
            if description and not board["description"]:
                entry["description"] = description
        return bool(html)

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_homepage_fetch, b): b for b in homepage_todo}
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % 250 == 0:
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
                print(f"[enrich] homepage phase: {done}/{len(homepage_todo)}")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")

    stats = {
        "generated_at": utc_now(),
        "boards_enriched": len(cache),
        "lever_websites_found": sum(1 for v in cache.values() if v.get("website_url")),
        "linkedin_urls_found": sum(1 for v in cache.values() if v.get("linkedin_url")),
        "descriptions_found": sum(1 for v in cache.values() if v.get("description")),
    }
    (Path(dirs["intermediate"]) / "enrichment_stats.json").write_text(json.dumps(stats, indent=2))
    print(
        f"[enrich] done: {stats['lever_websites_found']} websites, "
        f"{stats['linkedin_urls_found']} linkedin_urls, {stats['descriptions_found']} descriptions"
    )
    return stats
