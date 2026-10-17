from __future__ import annotations

import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

from company_dataset.build import load_candidates
from company_dataset.http import HttpClient, RequestError
from company_dataset.models import utc_now

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

COUNTRY_NAMES = {
    "usa": "US", "united states": "US", "united states of america": "US", "us": "US",
    "u.s.a.": "US", "u.s": "US", "america": "US", "estados unidos": "US",
    "united kingdom": "GB", "uk": "GB", "u.k.": "GB", "great britain": "GB",
    "britain": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB",
    "canada": "CA",
    "australia": "AU", "new zealand": "NZ", "ireland": "IE", "germany": "DE",
    "deutschland": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "netherlands": "NL", "the netherlands": "NL", "belgium": "BE", "austria": "AT",
    "switzerland": "CH", "sweden": "SE", "norway": "NO", "denmark": "DK",
    "finland": "FI", "iceland": "IS", "poland": "PL", "portugal": "PT",
    "greece": "GR", "czech republic": "CZ", "czechia": "CZ", "hungary": "HU",
    "romania": "RO", "bulgaria": "BG", "croatia": "HR", "serbia": "RS",
    "slovakia": "SK", "slovenia": "SI", "ukraine": "UA", "lithuania": "LT",
    "latvia": "LV", "estonia": "EE", "turkey": "TR", "türkiye": "TR",
    "israel": "IL", "united arab emirates": "AE", "saudi arabia": "SA",
    "qatar": "QA", "india": "IN", "singapore": "SG", "japan": "JP",
    "south korea": "KR", "china": "CN", "hong kong": "HK", "taiwan": "TW",
    "philippines": "PH", "malaysia": "MY", "indonesia": "ID", "vietnam": "VN",
    "thailand": "TH", "brazil": "BR", "mexico": "MX", "argentina": "AR",
    "chile": "CL", "colombia": "CO", "peru": "PE", "uruguay": "UY",
    "costa rica": "CR", "panama": "PA", "guatemala": "GT", "jamaica": "JM",
    "trinidad and tobago": "TT", "south africa": "ZA", "kenya": "KE",
    "nigeria": "NG", "egypt": "EG", "morocco": "MA",
}


def strip_html(text) -> str:
    if not text:
        return ""
    s = _TAG_RE.sub(" ", str(text))
    s = unescape(s)
    return _WS_RE.sub(" ", s).strip()


def normalize_country_name(name) -> str | None:
    if not isinstance(name, str):
        return None
    key = name.strip().lower().rstrip(".")
    if not key:
        return None
    return COUNTRY_NAMES.get(key)


def greenhouse_facts(payload: dict) -> dict:
    jobs = payload.get("jobs") or []
    meta = payload.get("meta") or {}
    jobs_count = meta.get("total", len(jobs))
    company_name = None
    for job in jobs:
        if isinstance(job, dict) and job.get("company_name"):
            company_name = str(job["company_name"]).strip()
            break
    origins: Counter[str] = Counter()
    for job in jobs:
        if not isinstance(job, dict):
            continue
        url = job.get("absolute_url") or ""
        try:
            host = urlsplit(url).hostname or ""
        except ValueError:
            continue
        if host and not host.endswith(".greenhouse.io"):
            scheme = urlsplit(url).scheme or "https"
            origins[f"{scheme}://{host}"] += 1
    website_url = origins.most_common(1)[0][0] if origins else None
    return {
        "jobs_count": jobs_count,
        "company_name": company_name,
        "website_url": website_url,
    }


def lever_facts(payload) -> dict:
    postings = payload if isinstance(payload, list) else []
    countries = {
        str(p.get("country")).strip()
        for p in postings
        if isinstance(p, dict) and p.get("country")
    }
    country = countries.pop() if len(countries) == 1 else None
    return {"jobs_count": len(postings), "country": country}


def ashby_facts(payload: dict) -> dict:
    jobs = payload.get("jobs") or []
    jobs_count = len(jobs)
    raw_countries = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        address = (job.get("address") or {}).get("postalAddress") or {}
        name = address.get("addressCountry")
        if isinstance(name, str) and name.strip():
            raw_countries.append(name.strip())
    country = None
    if raw_countries:
        mapped = {normalize_country_name(c) for c in raw_countries}
        if len(mapped) == 1 and None not in mapped:
            country = mapped.pop()
    return {"jobs_count": jobs_count, "country": country}


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
