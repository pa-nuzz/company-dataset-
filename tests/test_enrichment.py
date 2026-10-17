"""Tests for the enrichment module (website, linkedin, description extraction)."""
from __future__ import annotations

from company_dataset.enrichment import (
    extract_description,
    extract_lever_website,
    extract_linkedin,
)


class TestExtractLeverWebsite:
    def test_finds_company_link(self):
        html = '<html><body><a href="https://lever.co/job1">Job</a><div class="main-footer"><a href="https://www.15five.com">15Five Home Page</a></div></body></html>'
        assert extract_lever_website(html) == "https://www.15five.com"

    def test_finds_first_external_link(self):
        html = '<a href="https://jobs.lever.co/x">Internal</a><a href="https://fonts.googleapis.com/css">Font</a><a href="https://www.acme.com/careers">Acme</a>'
        assert extract_lever_website(html) == "https://www.acme.com"

    def test_excludes_social_media(self):
        html = '<a href="https://www.linkedin.com/company/acme">LinkedIn</a><a href="https://twitter.com/acme">Twitter</a><a href="https://www.acme.com">Acme</a>'
        assert extract_lever_website(html) == "https://www.acme.com"

    def test_returns_none_when_no_external(self):
        html = '<a href="https://jobs.lever.co/x">Internal</a><a href="https://fonts.googleapis.com/css">Font</a>'
        assert extract_lever_website(html) is None

    def test_returns_none_for_empty_html(self):
        assert extract_lever_website("") is None

    def test_strips_path_from_careers_url(self):
        html = '<a href="https://www.turvo.com/careers/jobs">Careers</a>'
        assert extract_lever_website(html) == "https://www.turvo.com"

    def test_handles_http(self):
        html = '<a href="http://www.canimmunize.ca/page">Site</a>'
        assert extract_lever_website(html) == "http://www.canimmunize.ca"


class TestExtractLinkedin:
    def test_standard_url(self):
        html = '<a href="https://www.linkedin.com/company/acme">LinkedIn</a>'
        assert extract_linkedin(html) == "https://www.linkedin.com/company/acme"

    def test_no_www(self):
        html = '<a href="https://linkedin.com/company/acme">LinkedIn</a>'
        assert extract_linkedin(html) == "https://www.linkedin.com/company/acme"

    def test_trailing_slash(self):
        html = '<a href="https://www.linkedin.com/company/acme/">LinkedIn</a>'
        assert extract_linkedin(html) == "https://www.linkedin.com/company/acme"

    def test_with_utm_params(self):
        html = '<a href="https://www.linkedin.com/company/acme?trk=footer">LinkedIn</a>'
        # The regex matches the slug before ? so we get the clean URL
        assert extract_linkedin(html) == "https://www.linkedin.com/company/acme"

    def test_none_when_missing(self):
        html = '<a href="https://www.acme.com">Acme</a>'
        assert extract_linkedin(html) is None

    def test_ignores_personal_profiles(self):
        html = '<a href="https://www.linkedin.com/in/johndoe">John</a>'
        assert extract_linkedin(html) is None


class TestExtractDescription:
    def test_meta_description(self):
        html = '<meta name="description" content="Acme builds software that helps teams collaborate faster and ship better products.">'
        result = extract_description(html)
        assert result is not None
        assert "Acme builds software" in result

    def test_og_description(self):
        html = '<meta property="og:description" content="Acme is a leading provider of cloud solutions for modern enterprises.">'
        result = extract_description(html)
        assert result is not None
        assert "cloud solutions" in result

    def test_reversed_attribute_order(self):
        html = '<meta content="Acme provides tools for developers worldwide." name="description">'
        result = extract_description(html)
        assert result is not None

    def test_too_short_rejected(self):
        html = '<meta name="description" content="Short">'
        assert extract_description(html) is None

    def test_none_when_missing(self):
        html = "<html><body>Hello</body></html>"
        assert extract_description(html) is None

    def test_strips_tags_and_whitespace(self):
        html = '<meta name="description" content="Acme & Co builds <b>great</b> products for teams.">'
        result = extract_description(html)
        assert result is not None
        assert "<b>" not in result
