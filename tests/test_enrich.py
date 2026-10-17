from company_dataset.enrich import (
    ashby_facts,
    greenhouse_facts,
    lever_facts,
    normalize_country_name,
    strip_html,
)


def test_strip_html():
    assert strip_html("<p>Hello  <b>world</b></p>") == "Hello world"
    assert strip_html("<p>We are & build things.</p>") == "We are & build things."
    assert strip_html("") == ""
    assert strip_html(None) == ""


def test_greenhouse_facts():
    payload = {
        "jobs": [
            {"company_name": "Acme", "absolute_url": "https://acme.com/jobs?gh_jid=1"},
            {"company_name": "Acme", "absolute_url": "https://acme.com/careers?gh_jid=2"},
            {"company_name": "Acme", "absolute_url": "https://careers.acme.com/jobs?gh_jid=3"},
            {"company_name": "Acme", "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/4"},
        ],
        "meta": {"total": 4},
    }
    facts = greenhouse_facts(payload)
    assert facts["jobs_count"] == 4
    assert facts["company_name"] == "Acme"
    assert facts["website_url"] == "https://acme.com"


def test_greenhouse_facts_no_name_no_website():
    payload = {"jobs": [{"absolute_url": "https://job-boards.greenhouse.io/x/jobs/1"}], "meta": {"total": 1}}
    facts = greenhouse_facts(payload)
    assert facts["jobs_count"] == 1
    assert facts["company_name"] is None
    assert facts["website_url"] is None


def test_greenhouse_facts_empty_jobs():
    facts = greenhouse_facts({"jobs": [], "meta": {"total": 0}})
    assert facts["jobs_count"] == 0
    assert facts["company_name"] is None


def test_lever_facts_country():
    assert lever_facts([{"country": "US"}, {"country": None}])["country"] == "US"
    assert lever_facts([{"country": "US"}, {"country": "GB"}])["country"] is None
    facts = lever_facts([])
    assert facts == {"jobs_count": 0, "country": None}


def test_ashby_facts_strict_unanimity():
    canada = {"jobs": [
        {"address": {"postalAddress": {"addressCountry": "Canada"}}},
        {"address": {"postalAddress": {"addressCountry": "Canada"}}},
    ]}
    assert ashby_facts(canada)["country"] == "CA"

    mixed = {"jobs": [
        {"address": {"postalAddress": {"addressCountry": "Canada"}}},
        {"address": {"postalAddress": {"addressCountry": "Germany"}}},
    ]}
    assert ashby_facts(mixed)["country"] is None

    unmapped = {"jobs": [{"address": {"postalAddress": {"addressCountry": "Ruritania"}}}]}
    assert ashby_facts(unmapped)["country"] is None

    no_address = {"jobs": [{"address": None}, {}]}
    assert ashby_facts(no_address)["country"] is None


def test_normalize_country_name():
    assert normalize_country_name("USA") == "US"
    assert normalize_country_name("United States") == "US"
    assert normalize_country_name("United Kingdom") == "GB"
    assert normalize_country_name("UK") == "GB"
    assert normalize_country_name("CANADA") == "CA"
    assert normalize_country_name("") is None
    assert normalize_country_name("Atlantis") is None
    assert normalize_country_name(None) is None
