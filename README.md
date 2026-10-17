# company-dataset

Builds a dataset of companies using Greenhouse, Lever, or Ashby job boards. Every company in the output has been checked against the ATS vendor's public API — nothing is guessed or made up.

## Output

`data/output/companies.csv` — one row per live job board:

| Field | Where it comes from |
|---|---|
| `name` | Board API or source datasets |
| `description` | Greenhouse board content, or the company's own homepage |
| `linkedin_url` | Parsed from company homepages — never constructed from names |
| `website_url` | Greenhouse job link origins, or Lever board footers |
| `careersite_url` | The live job board itself |
| `ats_system` | greenhouse / lever / ashby |
| `ats_code` | Board slug on the ATS |

Also includes `country`, `jobs_count`, and a few provenance columns so you can trace where each value came from.

Rejected rows (unsupported ATS, bad URLs, dead boards) land in `rejected_records.csv` with a reason for each one.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
company-dataset all
```

Stages can run individually: `company-dataset download | build | validate | enrich | export | report`

The full run takes a while (live API checks for ~30k boards plus homepage fetches), so results are cached at each stage. Re-runs pick up where the last one left off.

## Pipeline

1. **download** — fetch source datasets, cache under `data/raw/`
2. **build** — parse sources, extract (ATS, slug) pairs, deduplicate
3. **validate** — check each board against the vendor's public API (200 = live, 404 = dead, anything else = retry later)
4. **enrich** — pull company websites from Lever board footers, then fetch homepages for LinkedIn links and descriptions
5. **export** — merge everything into `companies.csv`
6. **report** — write `reports/quality_report.md`

A board with zero open jobs is still valid — it exists, it's just not hiring right now. Only a hard 404 marks a board dead. Rate limits and timeouts leave the board unresolved so the next run can retry it.

## Sources

All checked for license terms before use:

| Source | License | Contribution |
|---|---|---|
| [latmay/ats-career-page-urls](https://huggingface.co/datasets/latmay/ats-career-page-urls) | CC-BY-4.0 | ~28k career page URLs |
| [lastroundai-hiring-data](https://github.com/fyrosofttech/lastroundai-hiring-data) | CC-BY-4.0 | ~10k company/slug mappings |
| [kalebconfer job-board-directory](https://kalebconfer-sys.github.io/job-board-directory/) | free to use, no attribution needed | ~6k confirmed boards |
| [moonie0201/ats-directory](https://github.com/moonie0201/ats-directory) | CC0 | ~1k probed (provider, slug) pairs |
| [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator) | MIT | ~16k active board slugs |
| Common Crawl index | [CC terms](https://commoncrawl.org/terms-of-use/) | board tokens from crawled URLs |

The Common Crawl harvest only extracts URL paths — factual identifiers. Every token gets independently verified against the vendor's API before it ends up in the output. No page content is used.

Raw downloads are kept unmodified with SHA-256 checksums in `data/raw/`. License details per source are in `source_manifest.csv`.

## Results

Latest run (October 2026):

- 15,016 live companies — 8,031 on Greenhouse, 4,109 on Ashby, 2,876 on Lever
- 1,631 have all seven fields filled in (10.9%)
- 2,007 verified LinkedIn URLs
- 2,912 verified website URLs
- 5,933 descriptions
- 3,629 with country data

The seven-field coverage is limited by `linkedin_url` and `website_url`. These can only come from a company's own pages, which means we need to know the website first. Greenhouse and Ashby boards rarely expose the company website through their APIs, so most of those boards don't get one. Lever boards have the site in the footer, which is why Lever rows have the best completion rate.

Full stats: [`reports/quality_report.md`](reports/quality_report.md)

## Dependencies

Just `requests` and the standard library. Python 3.11+.

## License

The code is original. Output data inherits each source's license — CC-BY for latmay and lastroundai, CC0 for moonie0201, MIT for the feashliaa lists. If you redistribute the output, include `source_manifest.csv` to preserve attribution.
