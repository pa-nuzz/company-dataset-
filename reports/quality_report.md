# Quality Report: Companies on Greenhouse, Lever and Ashby

Generated: 2026-10-17T15:02:19Z

## Executive summary

| Metric | Value |
|---|---|
| Source rows read | 114243 |
| In-scope source records (greenhouse/lever/ashby) | 66057 |
| Source rows rejected at parse | 48186 |
| Duplicate source rows merged | 36334 |
| Unique candidate boards (ats + casefolded code) | 29723 |
| Boards checked live | 29723 |
| Validated live boards | 15016 |
| Invalid boards (404) | 14707 |
| Unresolved boards (kept for review) | 0 |
| **Exported companies** | **15016** |
| **Records complete across all 7 required fields** | **1631 (10.86%)** |

## Source audit

| Source | License | Rows read | In-scope | Rejected | Contributed candidates |
|---|---|---|---|---|---|
| latmay | CC-BY-4.0 | 69638 | 28162 | 41476 | 28155 |
| lastroundai | CC-BY-4.0 | 9935 | 9935 | 0 | 9935 |
| kaleb | No formal license | 12237 | 6225 | 6012 | 6225 |
| moonie | CC0-1.0 | 1804 | 1106 | 698 | 1106 |
| feashliaa | MIT | 15862 | 15862 | 0 | 15862 |
| commoncrawl | CC ToU (factual URL data) | 4767 | 4767 | 0 | 4628 |

- **License flag (kaleb):** No formal license file in repository; publisher site states 'free to pull as data... no attribution required'. Incorporated with attribution; FLAGGED for review.
- **License flag (feashliaa):** MIT covers the repository including its data files. Board slugs are factual identifiers; each is live-verified against the vendor API before export.
- **License flag (commoncrawl):** Only URL path segments (factual board identifiers) are extracted; every token is independently live-verified against the vendor's public API before export. No page content is used.

## Board validation by ATS

| ATS | Candidates | Valid | Invalid | Unresolved | Exported |
|---|---|---|---|---|---|
| ashby | 5776 | 4109 | 1667 | 0 | 4109 |
| greenhouse | 15217 | 8031 | 7186 | 0 | 8031 |
| lever | 8730 | 2876 | 5854 | 0 | 2876 |

## Metadata completeness (exported rows)

| Field | Non-null | Total | Coverage |
|---|---|---|---|
| name | 13491 | 15016 | 89.84% |
| description | 5933 | 15016 | 39.51% |
| linkedin_url | 2007 | 15016 | 13.37% |
| website_url | 2912 | 15016 | 19.39% |
| careersite_url | 15016 | 15016 | 100.0% |
| ats_system | 15016 | 15016 | 100.0% |
| ats_code | 15016 | 15016 | 100.0% |

Records with ALL 7 required fields populated simultaneously: 1631 / 15016 (10.86%). This is not the average of the per-field percentages above — a row only counts here if every required field is non-empty at once. `country` is additional metadata, not one of the 7 required fields, and is reported separately below.

Rows where name equals the board slug: 5720.

## Country coverage

- Exported rows with country: 3629 (24.17%)
- US: 2889
- GB: 139
- CA: 120
- All other countries combined: 481

Country is set only when every job posting on the board reports the same country (Lever ISO `country` field; Ashby `addressCountry`), or when a source dataset explicitly provides it. It is never guessed.

## Duplicates

- Source rows merged into an existing board: 36334
- Exported rows flagged as sharing a website URL with another exported row (cross-board duplicate signal): 91

## Policy and limitations

- `linkedin_url` is intentionally empty for all rows: no licensed source provides verified LinkedIn URLs and this pipeline never guesses them.
- `description` comes only from the Greenhouse board `content` field (company-authored, served by Greenhouse's public Job Board API); Lever and Ashby public APIs expose no company description.
- `website_url` comes only from the origin of Greenhouse `absolute_url` job links that point at a company's own (non-Greenhouse) domain; it is never derived from company names.
- Boards with zero open jobs are valid; emptiness never marks a board invalid.
- Boards that failed validation with 404 are excluded from companies.csv and written to rejected_records.csv; network-level failures are marked `validation_unresolved` and kept for review and re-runs.
- Lever slugs are case-sensitive; this pipeline preserves casing, dedupes case-insensitively, and records the exact casing that validated.
- Lever boards are probed on the global instance first, then the EU instance (`api.eu.lever.co`).
- Raw source files are cached unmodified under `data/raw/`; cleaned outputs live under `data/output/`.
- The kalebconfer-sys job-board-directory publishes no formal license; its site states the data is free to use with no attribution required. It is incorporated with attribution and flagged in `source_manifest.csv` for review.
- Validation hits only the three vendors' documented public job board endpoints with bounded concurrency, per-host rate limiting, timeouts, retries, and a resumable cache (`data/cache/validation.json`).
- Deduplication folds case for the merge key (`ats + casefolded code`), but Lever board slugs are documented case-sensitive. A handful of candidates (observed: 4) have multiple raw casings merged into one board; only the casing that validates first is kept. If two of these were ever genuinely distinct live companies rather than inconsistent scraping of the same one, the second would be silently dropped. This is a known, unmitigated edge case, not something this run can rule out.
- This run recorded zero `unresolved` boards across every candidate checked live. That is a clean result but an unusually clean one for ~29.5k calls against rate-limited third-party APIs; treat it as this run's measured result, not a guarantee that a future run (or `--revalidate`) will also see zero transient failures.

## Reproduction

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
company-dataset all
```
