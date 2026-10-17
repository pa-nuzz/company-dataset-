from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# The 7 business-required fields (per the project spec). `country` is additional
# metadata, not a required field, and must never be counted toward this list.
REQUIRED_FIELDS = ("name", "description", "linkedin_url", "website_url", "careersite_url", "ats_system", "ats_code")


@dataclass
class SourceMeta:
    name: str
    description: str
    download_url: str
    filename: str
    license: str
    license_url: str = ""
    license_note: str = ""
    attribution: str = ""


@dataclass
class SourceRecord:
    source: str
    ats: str
    code: str
    region: str | None = None
    name: str | None = None
    careersite_url: str | None = None
    row_ref: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Reject:
    source: str
    reason: str
    detail: str = ""
    row_ref: str = ""
    ats: str = ""
    code: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Candidate:
    ats: str
    codes: list[str] = field(default_factory=list)
    region: str | None = None
    name: str | None = None
    name_source: str = ""
    careersite_urls: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    row_count: int = 1

    @property
    def code(self) -> str:
        return self.codes[0]

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.code.casefold()}"


@dataclass
class BoardValidation:
    ats: str
    code: str
    status: str
    http_status: int | None = None
    jobs_count: int | None = None
    company_name: str | None = None
    description: str | None = None
    website_url: str | None = None
    country: str | None = None
    country_basis: str | None = None
    region_answered: str | None = None
    code_validated: str | None = None
    error: str | None = None
    checked_at: str = ""

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.code.casefold()}"

    def to_dict(self) -> dict:
        return {
            "ats": self.ats,
            "code": self.code,
            "status": self.status,
            "http_status": self.http_status,
            "jobs_count": self.jobs_count,
            "company_name": self.company_name,
            "description": self.description,
            "website_url": self.website_url,
            "country": self.country,
            "country_basis": self.country_basis,
            "region_answered": self.region_answered,
            "code_validated": self.code_validated,
            "error": self.error,
            "checked_at": self.checked_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoardValidation":
        return cls(**d)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
