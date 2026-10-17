from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

GREENHOUSE = "greenhouse"
LEVER = "lever"
ASHBY = "ashby"
SUPPORTED_ATS = (ASHBY, GREENHOUSE, LEVER)

_HOSTS = {
    "job-boards.greenhouse.io": GREENHOUSE,
    "boards.greenhouse.io": GREENHOUSE,
    "boards-api.greenhouse.io": GREENHOUSE,
    "jobs.lever.co": LEVER,
    "jobs.eu.lever.co": LEVER,
    "api.lever.co": LEVER,
    "api.eu.lever.co": LEVER,
    "jobs.ashbyhq.com": ASHBY,
    "api.ashbyhq.com": ASHBY,
}


@dataclass(frozen=True)
class ParsedBoard:
    ats: str
    code: str
    region: str | None = None


def _query_param(query: str, name: str) -> str | None:
    for part in query.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        if unquote(key) == name:
            return unquote(value)
    return None


def is_valid_slug(code: str) -> bool:
    if not code or len(code) > 128:
        return False
    if code.startswith("."):
        return False
    if "/" in code:
        return False
    if not all(32 < ord(ch) < 127 for ch in code):
        return False
    # A trailing ";" or "\" never occurs in a real board slug; it is the signature
    # of a scraped CSS/JS fragment leaking into a source dataset's URL column
    # (e.g. "100vw;", "Abridge\\") rather than a company-chosen identifier.
    if code.endswith(";") or code.endswith("\\"):
        return False
    return any(ch.isascii() and ch.isalnum() for ch in code)


def parse_board_url(raw) -> ParsedBoard | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    ats = _HOSTS.get(host)
    if ats is None:
        return None
    segs = [unquote(seg) for seg in parts.path.split("/") if seg != ""]
    code = None
    region = None
    if ats == GREENHOUSE:
        if segs and segs[0] == "embed":
            code = _query_param(parts.query, "for")
        elif len(segs) >= 3 and segs[0] == "v1" and segs[1] == "boards":
            code = segs[2]
        elif segs:
            code = segs[0]
    elif ats == LEVER:
        if host in ("api.lever.co", "api.eu.lever.co"):
            region = "eu" if host == "api.eu.lever.co" else None
            if len(segs) >= 3 and segs[0] == "v0" and segs[1] == "postings":
                code = segs[2]
        else:
            region = "eu" if host == "jobs.eu.lever.co" else None
            if segs:
                code = segs[0]
    else:
        if host == "api.ashbyhq.com":
            if len(segs) >= 3 and segs[0] == "posting-api" and segs[1] == "job-board":
                code = segs[2]
        elif segs:
            code = segs[0]
    if code is None:
        return None
    code = code.strip()
    if not is_valid_slug(code):
        return None
    return ParsedBoard(ats=ats, code=code, region=region)


def canonical_board_url(ats: str, code: str, region: str | None = None) -> str:
    q = quote(code, safe="")
    if ats == GREENHOUSE:
        return f"https://job-boards.greenhouse.io/{q}"
    if ats == LEVER:
        host = "jobs.eu.lever.co" if region == "eu" else "jobs.lever.co"
        return f"https://{host}/{q}"
    if ats == ASHBY:
        return f"https://jobs.ashbyhq.com/{q}"
    raise ValueError(f"unsupported ats: {ats}")


def canonical_api_url(ats: str, code: str, region: str | None = None) -> str:
    q = quote(code, safe="")
    if ats == GREENHOUSE:
        return f"https://boards-api.greenhouse.io/v1/boards/{q}/jobs"
    if ats == LEVER:
        host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
        return f"https://{host}/v0/postings/{q}?mode=json"
    if ats == ASHBY:
        return f"https://api.ashbyhq.com/posting-api/job-board/{q}"
    raise ValueError(f"unsupported ats: {ats}")


def greenhouse_board_info_url(code: str) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{quote(code, safe='')}"
