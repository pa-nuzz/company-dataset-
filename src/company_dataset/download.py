from __future__ import annotations

import hashlib
import json
from pathlib import Path

from company_dataset.http import HttpClient
from company_dataset.models import utc_now
from company_dataset.sources import SOURCES


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_download(dirs: dict, client: HttpClient | None = None) -> list[dict]:
    client = client or HttpClient(timeout=60.0)
    raw_dir = dirs["raw"]
    entries = []
    for mod in SOURCES:
        meta = mod.META
        dest = raw_dir / meta.name / meta.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "source": meta.name,
            "description": meta.description,
            "download_url": meta.download_url,
            "license": meta.license,
            "license_url": meta.license_url,
            "license_note": meta.license_note,
            "attribution": meta.attribution,
            "path": str(dest),
        }
        if hasattr(mod, "run_download"):
            mod.run_download(raw_dir / meta.name, client)
            if not dest.exists():
                entries.append(entry)
                print(f"[download] FAILED {meta.name}: custom download produced no file")
                continue
            entry["downloaded_at"] = utc_now()
            entry["cached"] = False
            print(f"[download] {meta.name}: {dest.stat().st_size} bytes")
        elif dest.exists() and dest.stat().st_size > 0:
            entry["downloaded_at"] = None
            entry["cached"] = True
        else:
            resp = client.get(meta.download_url)
            if resp.status != 200:
                entry["downloaded_at"] = None
                entry["cached"] = False
                entry["error"] = f"download failed with HTTP {resp.status}"
                entries.append(entry)
                print(f"[download] FAILED {meta.name}: HTTP {resp.status}")
                continue
            dest.write_bytes(resp.text.encode("utf-8"))
            entry["downloaded_at"] = utc_now()
            entry["cached"] = False
            print(f"[download] {meta.name}: {dest.stat().st_size} bytes")
        entry["sha256"] = _sha256(dest)
        entry["size_bytes"] = dest.stat().st_size
        entries.append(entry)
    manifest_path = dirs["intermediate"] / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2)
    return entries
