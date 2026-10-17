from company_dataset.sources import kaleb, lastround, latmay, moonie

LATMAY_CSV = "\ufeffcanonical_url,ats_platform\n" + (
    "https://job-boards.greenhouse.io/acme,Greenhouse\n"
    "https://jobs.lever.co/leverco,Lever\n"
    "https://jobs.ashbyhq.com/ashbyco,Ashby\n"
    "https://3m.wd1.myworkdayjobs.com/Search,Workday\n"
    "https://jobs.lever.co/,Lever\n"
    "https://job-boards.greenhouse.io/.well-known,Greenhouse\n"
    "https://jobs.lever.co/leverco,Lever\n"
)

LASTROUND_CSV = (
    "ats_vendor,company_name,board_slug,last_crawled\n"
    "greenhouse,10a Labs,10alabs,2026-07-17\n"
    'ashby,"0g Labs",0g,2026-07-12\n'
    "lever,100MS,100ms,2026-08-01\n"
)

KALEB_CSV = (
    "platform,token,company,board_url,api_url,open_roles,count_basis,region\n"
    "greenhouse,10alabs,10alabs,https://job-boards.greenhouse.io/10alabs,https://boards-api.greenhouse.io/v1/boards/10alabs/jobs,16,vendor,\n"
    "lever,aavelabs,aavelabs,https://jobs.eu.lever.co/aavelabs,https://api.eu.lever.co/v0/postings/aavelabs?mode=json,14,observed,EU\n"
    "ashby,0g,0g,https://jobs.ashbyhq.com/0g,https://api.ashbyhq.com/posting-api/job-board/0g,8,observed,\n"
    "workable,hf,hf,https://apply.workable.com/hf,https://apply.workable.com/api/v1/widget?id=1,2,vendor,\n"
)

MOONIE_JSONL = (
    '{"provider": "greenhouse", "slug": "anthropic", "site": null, "region": null, "name": "Anthropic", "status": "ok"}\n'
    '{"provider": "lever", "slug": "bunq", "site": null, "region": "eu", "name": null, "status": "ok"}\n'
    '{"provider": "lever", "slug": "oldco", "site": null, "region": null, "name": null, "status": "dead"}\n'
    '{"provider": "recruitee", "slug": "x", "site": null, "region": null, "name": null, "status": "ok"}\n'
    '{"provider": "lever", "slug": "maybe", "site": null, "region": null, "name": "Maybe", "status": "unconfirmed"}\n'
    "\n"
)


def test_latmay_parses_and_rejects(tmp_path):
    path = tmp_path / "latmay.csv"
    path.write_text(LATMAY_CSV, encoding="utf-8")
    records, rejects = latmay.parse(path)
    assert [(r.ats, r.code) for r in records] == [
        ("greenhouse", "acme"),
        ("lever", "leverco"),
        ("ashby", "ashbyco"),
        ("lever", "leverco"),
    ]
    assert records[0].source == latmay.META.name
    assert records[0].careersite_url == "https://job-boards.greenhouse.io/acme"
    reasons = sorted(r.reason for r in rejects)
    assert reasons == ["unparseable_url", "unparseable_url", "unsupported_ats"]


def test_lastround_parses(tmp_path):
    path = tmp_path / "lastround.csv"
    path.write_text(LASTROUND_CSV, encoding="utf-8")
    records, rejects = lastround.parse(path)
    assert len(records) == 3 and rejects == []
    by_ats = {r.ats: r for r in records}
    assert by_ats["greenhouse"].name == "10a Labs"
    assert by_ats["greenhouse"].code == "10alabs"
    assert by_ats["ashby"].name == "0g Labs"
    assert by_ats["ashby"].code == "0g"
    assert by_ats["lever"].name == "100MS"


def test_kaleb_parses_with_eu_region(tmp_path):
    path = tmp_path / "kaleb.csv"
    path.write_text(KALEB_CSV, encoding="utf-8")
    records, rejects = kaleb.parse(path)
    assert len(records) == 3
    assert [r.reason for r in rejects] == ["unsupported_ats"]
    lever = next(r for r in records if r.ats == "lever")
    assert lever.code == "aavelabs"
    assert lever.region == "eu"
    assert lever.careersite_url == "https://jobs.eu.lever.co/aavelabs"
    ashby = next(r for r in records if r.ats == "ashby")
    assert ashby.name == "0g"
    assert ashby.region is None


def test_moonie_parses_statuses(tmp_path):
    path = tmp_path / "moonie.jsonl"
    path.write_text(MOONIE_JSONL, encoding="utf-8")
    records, rejects = moonie.parse(path)
    assert [(r.ats, r.code) for r in records] == [
        ("greenhouse", "anthropic"),
        ("lever", "bunq"),
        ("lever", "maybe"),
    ]
    bunq = next(r for r in records if r.code == "bunq")
    assert bunq.region == "eu"
    anthropic = next(r for r in records if r.code == "anthropic")
    assert anthropic.name == "Anthropic"
    reasons = sorted(r.reason for r in rejects)
    assert reasons == ["blank_line", "source_marked_dead", "unsupported_ats"]
    assert all(r.source == moonie.META.name for r in rejects)


def test_moonie_accepts_mixed_case_provider(tmp_path):
    path = tmp_path / "moonie.jsonl"
    path.write_text(
        '{"provider": "Greenhouse", "slug": "acme", "site": null, "region": null, "name": "Acme", "status": "ok"}\n',
        encoding="utf-8",
    )
    records, rejects = moonie.parse(path)
    assert rejects == []
    assert len(records) == 1
    assert records[0].ats == "greenhouse"
    assert records[0].code == "acme"


def test_moonie_counts_blank_lines_as_rejects(tmp_path):
    path = tmp_path / "moonie.jsonl"
    path.write_text(
        '{"provider": "greenhouse", "slug": "acme", "site": null, "region": null, "name": "Acme", "status": "ok"}\n\n\n',
        encoding="utf-8",
    )
    records, rejects = moonie.parse(path)
    assert len(records) == 1
    assert [r.reason for r in rejects] == ["blank_line", "blank_line"]


KALEB_MISMATCH_CSV = (
    "platform,token,company,board_url,api_url,open_roles,count_basis,region\n"
    "greenhouse,acme,Acme,https://jobs.lever.co/acme,,5,vendor,\n"
)


def test_kaleb_rejects_platform_url_mismatch(tmp_path):
    path = tmp_path / "kaleb.csv"
    path.write_text(KALEB_MISMATCH_CSV, encoding="utf-8")
    records, rejects = kaleb.parse(path)
    assert records == []
    assert [r.reason for r in rejects] == ["platform_url_mismatch"]
    assert rejects[0].detail == "label=greenhouse url_host_ats=lever"


def test_adapters_skip_missing_file(tmp_path):
    for mod in (latmay, lastround, kaleb, moonie):
        records, rejects = mod.parse(tmp_path / "does-not-exist.csv")
        assert records == []
        assert rejects == []


def test_source_meta_has_licenses():
    for mod in (latmay, lastround, kaleb, moonie):
        assert mod.META.name
        assert mod.META.download_url
        assert mod.META.license
    assert latmay.META.license.startswith("CC-BY")
    assert lastround.META.license.startswith("CC-BY")
    assert moonie.META.license.startswith("CC0")
    assert "no formal license" in kaleb.META.license_note.lower()
