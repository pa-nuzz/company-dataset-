from company_dataset.build import merge_records
from company_dataset.models import SourceRecord


def rec(source, ats, code, name=None, region=None, careersite=None):
    return SourceRecord(
        source=source,
        ats=ats,
        code=code,
        region=region,
        name=name,
        careersite_url=careersite,
        row_ref="line 1",
    )


def test_same_key_merges():
    recs = [
        rec("lastroundai", "greenhouse", "acme", name="Acme Inc"),
        rec("kaleb", "greenhouse", "acme", name="acme", careersite="https://job-boards.greenhouse.io/acme"),
    ]
    candidates, stats = merge_records(recs)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.row_count == 2
    assert stats.duplicate_rows == 1
    assert set(cand.sources) == {"lastroundai", "kaleb"}
    assert cand.name == "Acme Inc"
    assert cand.name_source == "lastroundai"
    assert cand.careersite_urls == ["https://job-boards.greenhouse.io/acme"]


def test_case_insensitive_dedupe_keeps_alt_casings():
    recs = [
        rec("moonie", "lever", "Palantir"),
        rec("latmay", "lever", "palantir", careersite="https://jobs.lever.co/palantir"),
    ]
    candidates, stats = merge_records(recs)
    assert len(candidates) == 1
    assert candidates[0].codes == ["Palantir", "palantir"]
    assert stats.duplicate_rows == 1


def test_different_ats_same_slug_not_merged():
    recs = [rec("lastroundai", "greenhouse", "acme"), rec("lastroundai", "lever", "acme")]
    candidates, _ = merge_records(recs)
    assert len(candidates) == 2


def test_eu_region_wins_over_global():
    recs = [
        rec("latmay", "lever", "aavelabs", region=None),
        rec("kaleb", "lever", "aavelabs", region="eu"),
    ]
    candidates, _ = merge_records(recs)
    assert candidates[0].region == "eu"


def test_name_priority_prefers_lastroundai():
    recs = [
        rec("kaleb", "ashby", "0g", name="0g"),
        rec("lastroundai", "ashby", "0g", name="0g Labs"),
        rec("moonie", "ashby", "0g", name="0g"),
    ]
    candidates, _ = merge_records(recs)
    assert candidates[0].name == "0g Labs"
    assert candidates[0].name_source == "lastroundai"


def test_name_falls_back_to_any_available_source():
    candidates, _ = merge_records([rec("kaleb", "ashby", "0g", name="0g")])
    assert candidates[0].name == "0g"
    assert candidates[0].name_source == "kaleb"


def test_candidates_sorted_deterministically():
    recs = [
        rec("latmay", "lever", "b"),
        rec("latmay", "greenhouse", "a"),
        rec("latmay", "ashby", "c"),
    ]
    candidates, stats = merge_records(recs)
    assert [c.ats for c in candidates] == ["ashby", "greenhouse", "lever"]
    assert stats.unique_candidates == 3
    assert stats.duplicate_rows == 0
