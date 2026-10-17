"""Tests for the feashliaa and commoncrawl source adapters."""
from __future__ import annotations

import json
from pathlib import Path

from company_dataset.sources import commoncrawl, feashliaa


class TestFeashliaa:
    def test_parse_valid_file(self, tmp_path: Path):
        data = {
            "greenhouse": ["stripe", "vercel"],
            "lever": ["airtable"],
            "ashby": ["0g", "0x"],
        }
        path = tmp_path / "companies.json"
        path.write_text(json.dumps(data))
        records, rejects = feashliaa.parse(path)
        assert len(records) == 5
        assert len(rejects) == 0
        by_ats = {}
        for r in records:
            by_ats.setdefault(r.ats, []).append(r.code)
        assert set(by_ats) == {"greenhouse", "lever", "ashby"}
        assert by_ats["greenhouse"] == ["stripe", "vercel"]

    def test_parse_empty_file(self, tmp_path: Path):
        path = tmp_path / "companies.json"
        path.write_text("{}")
        records, rejects = feashliaa.parse(path)
        assert records == []
        assert rejects == []

    def test_parse_missing_file(self, tmp_path: Path):
        records, rejects = feashliaa.parse(tmp_path / "nonexistent.json")
        assert records == []
        assert rejects == []

    def test_invalid_slugs_rejected(self, tmp_path: Path):
        data = {"greenhouse": ["ok", "with/slash", "trailing;", ""]}
        path = tmp_path / "companies.json"
        path.write_text(json.dumps(data))
        records, rejects = feashliaa.parse(path)
        assert len(records) == 1
        assert records[0].code == "ok"
        assert len(rejects) == 3
        reasons = {r.reason for r in rejects}
        assert reasons == {"invalid_slug"}

    def test_meta_has_license(self):
        assert feashliaa.META.license == "MIT"
        assert "feashliaa" in feashliaa.META.name


class TestCommonCrawl:
    def test_parse_valid_csv(self, tmp_path: Path):
        path = tmp_path / "tokens.csv"
        path.write_text("ats,code\ngreenhouse,stripe\ngreenhouse,vercel\nashby,0g\n")
        records, rejects = commoncrawl.parse(path)
        assert len(records) == 3
        assert len(rejects) == 0
        assert records[0].ats == "greenhouse"
        assert records[0].code == "stripe"

    def test_parse_rejects_invalid_ats(self, tmp_path: Path):
        path = tmp_path / "tokens.csv"
        path.write_text("ats,code\nworkday,acme\ngreenhouse,stripe\n")
        records, rejects = commoncrawl.parse(path)
        assert len(records) == 1
        assert len(rejects) == 1
        assert rejects[0].reason == "unsupported_ats"

    def test_parse_rejects_invalid_slug(self, tmp_path: Path):
        path = tmp_path / "tokens.csv"
        path.write_text("ats,code\ngreenhouse,trailing;\nashby,ok\n")
        records, rejects = commoncrawl.parse(path)
        assert len(records) == 1
        assert len(rejects) == 1
        assert rejects[0].reason == "invalid_slug"

    def test_parse_missing_file(self, tmp_path: Path):
        records, rejects = commoncrawl.parse(tmp_path / "nonexistent.csv")
        assert records == []
        assert rejects == []

    def test_meta_license_note_mentions_factual(self):
        assert "factual" in commoncrawl.META.license_note.lower()
