from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from company_dataset.build import load_candidates
from company_dataset.enrichment import ashby_facts, greenhouse_facts, lever_facts, strip_html
from company_dataset.http import HttpClient, RequestError
from company_dataset.models import BoardValidation, Candidate, utc_now
from company_dataset.normalize import (
    ASHBY,
    GREENHOUSE,
    LEVER,
    canonical_api_url,
    greenhouse_board_info_url,
)

VALID = "valid"
INVALID = "invalid"
UNRESOLVED = "unresolved"


class BoardValidator:
    def __init__(self, client: HttpClient, cache_path: str | Path | None = None, max_workers: int = 10, progress_every: int = 250, logger=None):
        self.client = client
        self.cache_path = Path(cache_path) if cache_path else None
        self.max_workers = max_workers
        self.progress_every = progress_every
        self.logger = logger
        self.cache: dict[str, dict] = {}
        if self.cache_path and self.cache_path.exists():
            try:
                self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except ValueError:
                self.cache = {}

    def flush(self):
        if not self.cache_path:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache), encoding="utf-8")
        tmp.replace(self.cache_path)

    def _get_json(self, url: str):
        try:
            resp = self.client.get(url)
        except RequestError:
            return None
        if resp.status != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    def validate_one(self, cand: Candidate) -> BoardValidation:
        if cand.ats == GREENHOUSE:
            return self._validate_greenhouse(cand)
        if cand.ats == LEVER:
            return self._validate_lever(cand)
        if cand.ats == ASHBY:
            return self._validate_ashby(cand)
        return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, error="unknown ats", checked_at=utc_now())

    def _validate_greenhouse(self, cand: Candidate) -> BoardValidation:
        now = utc_now()
        codes = list(dict.fromkeys(cand.codes))
        for code in codes:
            url = canonical_api_url(GREENHOUSE, code)
            try:
                resp = self.client.get(url)
            except RequestError as exc:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, error=f"request_error: {exc}", checked_at=now)
            if resp.status == 404:
                continue
            if resp.status != 200:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=resp.status, error=f"http_{resp.status}", checked_at=now)
            try:
                payload = resp.json()
            except ValueError:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="invalid_json", checked_at=now)
            if not isinstance(payload, dict) or "jobs" not in payload:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="unexpected_schema", checked_at=now)
            facts = greenhouse_facts(payload)
            company_name = facts["company_name"]
            description = None
            info = self._get_json(greenhouse_board_info_url(code))
            if info is not None:
                info_name = info.get("name") or None
                company_name = company_name or (str(info_name).strip() if info_name else None)
                content = strip_html(info.get("content") or "")
                if content:
                    description = content
            return BoardValidation(
                ats=cand.ats,
                code=cand.code,
                status=VALID,
                http_status=200,
                jobs_count=facts["jobs_count"],
                company_name=company_name,
                description=description,
                website_url=facts["website_url"],
                code_validated=code,
                checked_at=now,
            )
        return BoardValidation(ats=cand.ats, code=cand.code, status=INVALID, http_status=404, error="board_not_found", checked_at=now)

    def _validate_lever(self, cand: Candidate) -> BoardValidation:
        now = utc_now()
        codes = list(dict.fromkeys(cand.codes))
        hosts = ["eu", None] if cand.region == "eu" else [None, "eu"]
        for region in hosts:
            for code in codes:
                url = canonical_api_url(LEVER, code, region)
                try:
                    resp = self.client.get(url)
                except RequestError as exc:
                    return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, error=f"request_error: {exc}", checked_at=now)
                if resp.status == 404:
                    continue
                if resp.status != 200:
                    return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=resp.status, error=f"http_{resp.status}", checked_at=now)
                try:
                    payload = resp.json()
                except ValueError:
                    return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="invalid_json", checked_at=now)
                if not isinstance(payload, list):
                    return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="unexpected_schema", checked_at=now)
                facts = lever_facts(payload)
                return BoardValidation(
                    ats=cand.ats,
                    code=cand.code,
                    status=VALID,
                    http_status=200,
                    jobs_count=facts["jobs_count"],
                    country=facts["country"],
                    country_basis="lever_postings_unanimous" if facts["country"] else None,
                    region_answered="eu" if region == "eu" else None,
                    code_validated=code,
                    checked_at=now,
                )
        return BoardValidation(ats=cand.ats, code=cand.code, status=INVALID, http_status=404, error="board_not_found", checked_at=now)

    def _validate_ashby(self, cand: Candidate) -> BoardValidation:
        now = utc_now()
        codes = list(dict.fromkeys(cand.codes))
        for code in codes:
            url = canonical_api_url(ASHBY, code)
            try:
                resp = self.client.get(url)
            except RequestError as exc:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, error=f"request_error: {exc}", checked_at=now)
            if resp.status == 404:
                continue
            if resp.status != 200:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=resp.status, error=f"http_{resp.status}", checked_at=now)
            try:
                payload = resp.json()
            except ValueError:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="invalid_json", checked_at=now)
            if not isinstance(payload, dict) or "jobs" not in payload:
                return BoardValidation(ats=cand.ats, code=cand.code, status=UNRESOLVED, http_status=200, error="unexpected_schema", checked_at=now)
            facts = ashby_facts(payload)
            return BoardValidation(
                ats=cand.ats,
                code=cand.code,
                status=VALID,
                http_status=200,
                jobs_count=facts["jobs_count"],
                country=facts["country"],
                country_basis="ashby_postings_unanimous" if facts["country"] else None,
                code_validated=code,
                checked_at=now,
            )
        return BoardValidation(ats=cand.ats, code=cand.code, status=INVALID, http_status=404, error="board_not_found", checked_at=now)

    def validate_many(self, candidates, limit: int | None = None, revalidate: bool = False) -> dict[str, BoardValidation]:
        results: dict[str, BoardValidation] = {}
        todo: list[Candidate] = []
        for cand in candidates:
            cached = self.cache.get(cand.key)
            if cached and not revalidate and cached.get("status") in (VALID, INVALID):
                results[cand.key] = BoardValidation.from_dict(cached)
            else:
                todo.append(cand)
        if limit is not None:
            per_ats: Counter = Counter()
            selected = []
            for cand in todo:
                if per_ats[cand.ats] < limit:
                    selected.append(cand)
                    per_ats[cand.ats] += 1
            todo = selected
        if not todo:
            return results
        done = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.validate_one, cand) for cand in todo]
            for future in as_completed(futures):
                outcome = future.result()
                results[outcome.key] = outcome
                self.cache[outcome.key] = outcome.to_dict()
                done += 1
                if self.progress_every and done % self.progress_every == 0:
                    self.flush()
                    if self.logger:
                        statuses = Counter(v.status for v in results.values())
                        self.logger(f"[validate] {done}/{len(todo)} checked (valid={statuses.get(VALID, 0)} invalid={statuses.get(INVALID, 0)} unresolved={statuses.get(UNRESOLVED, 0)})")
        self.flush()
        return results


def run_validate(
    dirs: dict,
    client: HttpClient | None = None,
    max_workers: int = 10,
    per_host_interval: float = 0.15,
    timeout: float = 20.0,
    limit: int | None = None,
    revalidate: bool = False,
) -> dict:
    candidates = load_candidates(dirs)
    if not candidates:
        print("[validate] no candidates found; run build stage first")
        return {}
    client = client or HttpClient(timeout=timeout, per_host_interval=per_host_interval)
    validator = BoardValidator(
        client,
        cache_path=dirs["cache"] / "validation.json",
        max_workers=max_workers,
        progress_every=250,
        logger=print,
    )
    results = validator.validate_many(candidates, limit=limit, revalidate=revalidate)
    by_status = Counter(v.status for v in results.values())
    by_ats: dict[str, Counter] = {}
    for v in results.values():
        by_ats.setdefault(v.ats, Counter())[v.status] += 1
    stats = {
        "generated_at": utc_now(),
        "candidates_total": len(candidates),
        "checked": len(results),
        "by_status": dict(by_status),
        "by_ats": {ats: dict(counter) for ats, counter in by_ats.items()},
    }
    stats_path = dirs["intermediate"] / "validation_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2))
    print(
        f"[validate] checked={len(results)} valid={by_status.get(VALID, 0)} "
        f"invalid={by_status.get(INVALID, 0)} unresolved={by_status.get(UNRESOLVED, 0)}"
    )
    return stats
