from company_dataset.normalize import (
    ASHBY,
    GREENHOUSE,
    LEVER,
    ParsedBoard,
    canonical_api_url,
    canonical_board_url,
    is_valid_slug,
    parse_board_url,
)


def test_greenhouse_job_boards_host():
    assert parse_board_url("https://job-boards.greenhouse.io/acme") == ParsedBoard(GREENHOUSE, "acme", None)


def test_greenhouse_trailing_slash_jobs_suffix_legacy_host():
    assert parse_board_url("https://job-boards.greenhouse.io/acme/") == ParsedBoard(GREENHOUSE, "acme", None)
    assert parse_board_url("https://job-boards.greenhouse.io/acme/jobs") == ParsedBoard(GREENHOUSE, "acme", None)
    assert parse_board_url("http://boards.greenhouse.io/acme") == ParsedBoard(GREENHOUSE, "acme", None)


def test_greenhouse_job_detail_path():
    assert parse_board_url("https://job-boards.greenhouse.io/acme/jobs/4266196009") == ParsedBoard(GREENHOUSE, "acme", None)


def test_greenhouse_embed_for_param():
    assert parse_board_url("https://boards.greenhouse.io/embed/job_board?for=acme&codes=") == ParsedBoard(GREENHOUSE, "acme", None)
    assert parse_board_url("https://job-boards.greenhouse.io/embed/job_board/list?for=AcmeInc") == ParsedBoard(GREENHOUSE, "AcmeInc", None)


def test_greenhouse_api_url():
    assert parse_board_url("https://boards-api.greenhouse.io/v1/boards/acme/jobs") == ParsedBoard(GREENHOUSE, "acme", None)


def test_greenhouse_schemeless():
    assert parse_board_url("job-boards.greenhouse.io/acme") == ParsedBoard(GREENHOUSE, "acme", None)


def test_greenhouse_rejects_whitespace_slug():
    assert parse_board_url("https://job-boards.greenhouse.io/very%20awesome") is None


def test_greenhouse_rejects_empty_token():
    assert parse_board_url("https://job-boards.greenhouse.io/") is None


def test_greenhouse_rejects_well_known():
    assert parse_board_url("https://job-boards.greenhouse.io/.well-known") is None


def test_lever_basic():
    assert parse_board_url("https://jobs.lever.co/acme") == ParsedBoard(LEVER, "acme", None)


def test_lever_trailing_slash_and_posting_path():
    assert parse_board_url("https://jobs.lever.co/acme/") == ParsedBoard(LEVER, "acme", None)
    assert parse_board_url("https://jobs.lever.co/acme/5ac21346-8e0c-4494-8e7a-3eb92ff77902") == ParsedBoard(LEVER, "acme", None)


def test_lever_eu_region():
    assert parse_board_url("https://jobs.eu.lever.co/aavelabs/") == ParsedBoard(LEVER, "aavelabs", "eu")


def test_lever_api_urls():
    assert parse_board_url("https://api.lever.co/v0/postings/aavelabs?mode=json") == ParsedBoard(LEVER, "aavelabs", None)
    assert parse_board_url("https://api.eu.lever.co/v0/postings/aavelabs") == ParsedBoard(LEVER, "aavelabs", "eu")


def test_lever_percent_encoded_slug():
    assert parse_board_url("https://jobs.lever.co/11%3A11Media") == ParsedBoard(LEVER, "11:11Media", None)


def test_ashby_basic_and_job_path():
    assert parse_board_url("https://jobs.ashbyhq.com/acme") == ParsedBoard(ASHBY, "acme", None)
    assert parse_board_url("https://jobs.ashbyhq.com/acme/9638e78d-ada8-4111-832b-6d75eace719b") == ParsedBoard(ASHBY, "acme", None)


def test_ashby_api_url():
    assert parse_board_url("https://api.ashbyhq.com/posting-api/job-board/acme") == ParsedBoard(ASHBY, "acme", None)


def test_ashby_percent_encoded_slug():
    assert parse_board_url("https://jobs.ashbyhq.com/%2410.2K") == ParsedBoard(ASHBY, "$10.2K", None)


def test_non_ats_urls_return_none():
    assert parse_board_url("https://example.com/careers") is None
    assert parse_board_url("https://www.greenhouse.io/") is None
    assert parse_board_url("https://apply.workable.com/huggingface") is None
    assert parse_board_url("https://jobs.eu.lever.co") is None


def test_malformed_inputs_return_none():
    for bad in (None, "", "   ", "not a url", "https://", "https://jobs.lever.co", "/careers", 123, "https://jobs.lever.co/ "):
        assert parse_board_url(bad) is None


def test_case_preserved():
    assert parse_board_url("https://jobs.lever.co/Palantir").code == "Palantir"


def test_is_valid_slug():
    assert is_valid_slug("acme")
    assert is_valid_slug("very_awesome_inc")
    assert is_valid_slug("$10.2K")
    assert not is_valid_slug("")
    assert not is_valid_slug(".well-known")
    assert not is_valid_slug("has space")
    assert not is_valid_slug("a" * 200)


def test_is_valid_slug_rejects_css_js_fragments():
    # Real-world garbage found in the latmay source: CSS/JS tokens that leaked
    # into the URL column, not company-chosen board slugs.
    assert not is_valid_slug("100vw;")
    assert not is_valid_slug("0;")
    assert not is_valid_slug("750ms;")
    assert not is_valid_slug("Abridge\\")
    assert not is_valid_slug("airgarage\\")


def test_is_valid_slug_still_accepts_special_char_company_names():
    # These are real, live-validated board slugs; the garbage filter above
    # must not catch legitimate company names that contain punctuation.
    assert is_valid_slug("frey&muller")
    assert is_valid_slug("1840&Company")
    assert is_valid_slug("ep+co")
    assert is_valid_slug("survoy's")


def test_ashby_rejects_css_fragment_urls():
    assert parse_board_url("https://jobs.ashbyhq.com/100vw%3B") is None
    assert parse_board_url("https://jobs.ashbyhq.com/Abridge%5C") is None


def test_canonical_board_urls():
    assert canonical_board_url(GREENHOUSE, "acme") == "https://job-boards.greenhouse.io/acme"
    assert canonical_board_url(LEVER, "acme") == "https://jobs.lever.co/acme"
    assert canonical_board_url(LEVER, "acme", "eu") == "https://jobs.eu.lever.co/acme"
    assert canonical_board_url(ASHBY, "acme") == "https://jobs.ashbyhq.com/acme"


def test_canonical_api_urls():
    assert canonical_api_url(GREENHOUSE, "acme") == "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    assert canonical_api_url(LEVER, "acme") == "https://api.lever.co/v0/postings/acme?mode=json"
    assert canonical_api_url(LEVER, "acme", "eu") == "https://api.eu.lever.co/v0/postings/acme?mode=json"
    assert canonical_api_url(ASHBY, "acme") == "https://api.ashbyhq.com/posting-api/job-board/acme"


def test_canonical_quotes_special_codes():
    assert canonical_board_url(LEVER, "11:11Media") == "https://jobs.lever.co/11%3A11Media"
    assert canonical_api_url(ASHBY, "$10.2K") == "https://api.ashbyhq.com/posting-api/job-board/%2410.2K"
