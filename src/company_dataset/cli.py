from __future__ import annotations

import argparse

from company_dataset.build import run_build
from company_dataset.config import resolve_dirs
from company_dataset.download import run_download
from company_dataset.enrichment import run_enrich
from company_dataset.export import run_export
from company_dataset.report import run_report
from company_dataset.validate import run_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="company-dataset",
        description="Build a verified dataset of companies using Greenhouse, Lever, or Ashby public job boards",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["download", "build", "validate", "enrich", "export", "report", "all"],
        help="pipeline stage to run (default: all)",
    )
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--workers", type=int, default=10, help="max concurrent validation requests")
    parser.add_argument("--per-host-delay", type=float, default=0.15, help="min seconds between requests per host")
    parser.add_argument("--timeout", type=float, default=20.0, help="per-request timeout in seconds")
    parser.add_argument("--limit", type=int, default=None, help="validate at most N boards per ATS (smoke runs)")
    parser.add_argument("--revalidate", action="store_true", help="ignore cached validation results")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    dirs = resolve_dirs(args.data_dir)
    command = args.command
    if command in ("download", "all"):
        run_download(dirs)
    if command in ("build", "all"):
        run_build(dirs)
    if command in ("validate", "all"):
        run_validate(
            dirs,
            max_workers=args.workers,
            per_host_interval=args.per_host_delay,
            timeout=args.timeout,
            limit=args.limit,
            revalidate=args.revalidate,
        )
    if command in ("enrich", "all"):
        run_enrich(
            dirs,
            max_workers=args.workers,
            timeout=args.timeout,
        )
    if command in ("export", "all"):
        run_export(dirs)
    if command in ("report", "all"):
        run_report(dirs)
    return 0
