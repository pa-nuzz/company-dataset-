import json

from conftest import FakeResponse, FakeSession

from company_dataset.http import HttpClient
from company_dataset.models import Candidate
from company_dataset.validate import BoardValidator

GH_JOBS_URL = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
GH_INFO_URL = "https://boards-api.greenhouse.io/v1/boards/acme"
LEVER_URL = "https://api.lever.co/v0/postings/acme?mode=json"
LEVER_EU_URL = "https://api.eu.lever.co/v0/postings/acme?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/acme"


def make_client(script, sleeps=None):
    session = FakeSession(script)
    sleep = sleeps.append if sleeps is not None else (lambda s: None)
    client = HttpClient(session=session, sleep=sleep, per_host_interval=0.0, max_attempts=3)
    return client, session


def cand(ats, code, region=None):
    return Candidate(ats=ats, codes=[code], region=region, sources=["test"])


def test_greenhouse_valid_with_jobs_and_website():
    payload = {
        "jobs": [
            {"company_name": "Acme", "absolute_url": "https://acme.com/careers?gh_jid=1"},
            {"company_name": "Acme", "absolute_url": "https://acme.com/jobs?gh_jid=2"},
            {"company_name": "Acme", "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/3"},
        ],
        "meta": {"total": 3},
    }
    client, _ = make_client({
        GH_JOBS_URL: FakeResponse(200, json.dumps(payload), GH_JOBS_URL),
        GH_INFO_URL: FakeResponse(200, json.dumps({"name": "Acme", "content": ""}), GH_INFO_URL),
    })
    result = BoardValidator(client).validate_one(cand("greenhouse", "acme"))
    assert result.status == "valid"
    assert result.jobs_count == 3
    assert result.company_name == "Acme"
    assert result.website_url == "https://acme.com"
    assert result.description is None


def test_greenhouse_empty_jobs_still_valid_with_board_info_name():
    client, _ = make_client({
        GH_JOBS_URL: FakeResponse(200, json.dumps({"jobs": [], "meta": {"total": 0}})),
        GH_INFO_URL: FakeResponse(200, json.dumps({"name": "Acme", "content": "<p>We build things.</p>"})),
    })
    result = BoardValidator(client).validate_one(cand("greenhouse", "acme"))
    assert result.status == "valid"
    assert result.jobs_count == 0
    assert result.company_name == "Acme"
    assert result.description == "We build things."


def test_greenhouse_404_is_invalid():
    client, _ = make_client({GH_JOBS_URL: FakeResponse(404, "nope")})
    result = BoardValidator(client).validate_one(cand("greenhouse", "acme"))
    assert result.status == "invalid"
    assert result.http_status == 404


def test_greenhouse_board_info_failure_does_not_invalidate():
    client, _ = make_client({
        GH_JOBS_URL: FakeResponse(200, json.dumps({"jobs": [], "meta": {"total": 0}})),
        GH_INFO_URL: FakeResponse(404, "gone"),
    })
    result = BoardValidator(client).validate_one(cand("greenhouse", "acme"))
    assert result.status == "valid"
    assert result.company_name is None


def test_lever_country_unanimous():
    payload = [{"country": "US"}, {"country": "US"}, {"country": None}]
    client, _ = make_client({LEVER_URL: FakeResponse(200, json.dumps(payload))})
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "valid"
    assert result.country == "US"
    assert result.country_basis == "lever_postings_unanimous"


def test_lever_mixed_countries_yields_no_country():
    payload = [{"country": "US"}, {"country": "GB"}]
    client, _ = make_client({LEVER_URL: FakeResponse(200, json.dumps(payload))})
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "valid"
    assert result.country is None


def test_lever_empty_postings_is_valid():
    client, _ = make_client({LEVER_URL: FakeResponse(200, "[]")})
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "valid"
    assert result.jobs_count == 0


def test_lever_falls_back_to_eu():
    client, session = make_client({
        LEVER_URL: FakeResponse(404, '{"ok":false,"error":"Document not found"}'),
        LEVER_EU_URL: FakeResponse(200, "[]"),
    })
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "valid"
    assert result.region_answered == "eu"
    assert session.calls == [LEVER_URL, LEVER_EU_URL]


def test_lever_eu_candidate_tries_eu_first():
    client, session = make_client({
        LEVER_EU_URL: FakeResponse(200, "[]"),
        LEVER_URL: FakeResponse(404, ""),
    })
    result = BoardValidator(client).validate_one(cand("lever", "acme", region="eu"))
    assert result.status == "valid"
    assert result.region_answered == "eu"
    assert session.calls == [LEVER_EU_URL]


def test_lever_both_hosts_404_is_invalid():
    client, session = make_client({})
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "invalid"
    assert session.calls == [LEVER_URL, LEVER_EU_URL]


def test_lever_case_variant_validates():
    client, _ = make_client({
        "https://api.lever.co/v0/postings/Palantir?mode=json": FakeResponse(404, ""),
        "https://api.eu.lever.co/v0/postings/Palantir?mode=json": FakeResponse(404, ""),
        "https://api.lever.co/v0/postings/palantir?mode=json": FakeResponse(200, "[]"),
    })
    c = Candidate(ats="lever", codes=["Palantir", "palantir"], sources=["test"])
    result = BoardValidator(client).validate_one(c)
    assert result.status == "valid"
    assert result.code_validated == "palantir"


def test_ashby_valid_with_mapped_country():
    payload = {"jobs": [
        {"address": {"postalAddress": {"addressCountry": "USA"}}},
        {"address": {"postalAddress": {"addressCountry": "United States"}}},
    ]}
    client, _ = make_client({ASHBY_URL: FakeResponse(200, json.dumps(payload))})
    result = BoardValidator(client).validate_one(cand("ashby", "acme"))
    assert result.status == "valid"
    assert result.country == "US"
    assert result.country_basis == "ashby_postings_unanimous"


def test_ashby_unmapped_country_vetoes():
    payload = {"jobs": [
        {"address": {"postalAddress": {"addressCountry": "USA"}}},
        {"address": {"postalAddress": {"addressCountry": "Ruritania"}}},
    ]}
    client, _ = make_client({ASHBY_URL: FakeResponse(200, json.dumps(payload))})
    result = BoardValidator(client).validate_one(cand("ashby", "acme"))
    assert result.status == "valid"
    assert result.country is None


def test_retries_on_429_then_valid():
    sleeps = []
    client, _ = make_client({LEVER_URL: [FakeResponse(429, "slow down"), FakeResponse(200, "[]")]}, sleeps)
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "valid"
    assert len(sleeps) == 1


def test_connection_errors_exhausted_is_unresolved():
    client, _ = make_client({LEVER_URL: [RuntimeError("boom")] * 3})
    result = BoardValidator(client).validate_one(cand("lever", "acme"))
    assert result.status == "unresolved"
    assert result.error


def test_403_after_retries_is_unresolved_not_invalid():
    client, _ = make_client({ASHBY_URL: [FakeResponse(403, "blocked")] * 3})
    result = BoardValidator(client).validate_one(cand("ashby", "acme"))
    assert result.status == "unresolved"
    assert result.http_status == 403


def test_200_invalid_json_is_unresolved():
    client, _ = make_client({GH_JOBS_URL: FakeResponse(200, "<html>login</html>")})
    result = BoardValidator(client).validate_one(cand("greenhouse", "acme"))
    assert result.status == "unresolved"


def test_cache_skips_valid_and_invalid_but_retries_unresolved(tmp_path):
    cache_path = tmp_path / "validation.json"

    client1, session1 = make_client({LEVER_URL: FakeResponse(404, "")})
    v1 = BoardValidator(client1, cache_path=cache_path)
    r1 = v1.validate_many([cand("lever", "acme")])
    assert r1["lever:acme"].status == "invalid"
    v1.flush()

    client2, session2 = make_client({})
    v2 = BoardValidator(client2, cache_path=cache_path)
    r2 = v2.validate_many([cand("lever", "acme")])
    assert len(session2.calls) == 0
    assert r2["lever:acme"].status == "invalid"

    client3, _ = make_client({ASHBY_URL: [RuntimeError("x")] * 3})
    v3 = BoardValidator(client3, cache_path=cache_path)
    v3.validate_many([cand("ashby", "acme")])
    v3.flush()

    client4, session4 = make_client({ASHBY_URL: FakeResponse(200, '{"jobs": []}')})
    v4 = BoardValidator(client4, cache_path=cache_path)
    r4 = v4.validate_many([cand("ashby", "acme")])
    assert len(session4.calls) > 0
    assert r4["ashby:acme"].status == "valid"


def test_validate_many_concurrent_correctness():
    script = {
        GH_JOBS_URL: FakeResponse(404, ""),
        GH_INFO_URL: FakeResponse(404, ""),
        LEVER_URL: FakeResponse(200, "[]"),
        ASHBY_URL: FakeResponse(200, '{"jobs": []}'),
    }
    client, _ = make_client(script)
    validator = BoardValidator(client, max_workers=3)
    results = validator.validate_many([
        cand("greenhouse", "acme"),
        cand("lever", "acme"),
        cand("ashby", "acme"),
    ])
    assert set(results) == {"greenhouse:acme", "lever:acme", "ashby:acme"}
    assert results["greenhouse:acme"].status == "invalid"
    assert results["lever:acme"].status == "valid"
    assert results["ashby:acme"].status == "valid"
