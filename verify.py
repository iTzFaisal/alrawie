#!/usr/bin/env python3
"""Verify the Ghasslan archive against the catalog and write a download report."""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).parent
VIDEOS = ROOT / "audios"
SUPPLEMENTS_DIR = VIDEOS / "مكملات"
CATALOG = ROOT / "catalog"
NAME_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.(m4a|mp4)$")


def load_catalog() -> list[dict]:
    with (CATALOG / "ghasslan_mirrors.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def index_files(directory: Path, recursive: bool = False) -> dict[str, Path]:
    """Map video ID -> media file, preferring M4A over MP4."""
    index: dict[str, Path] = {}
    if not directory.exists():
        return index
    paths = directory.rglob("*") if recursive else directory.iterdir()
    for path in sorted(paths):
        m = NAME_RE.search(path.name)
        if not m:
            continue
        vid, ext = m.group(1), m.group(2)
        if vid not in index or ext == "m4a":
            index[vid] = path
    return index


def main() -> None:
    rows = load_catalog()
    files = index_files(VIDEOS, recursive=True)
    # Some catalog entries may be supplied as supplements from other uploads.
    for vid, path in index_files(SUPPLEMENTS_DIR, recursive=True).items():
        files.setdefault(vid, path)
    report = []
    missing = []
    total_bytes = 0
    total_seconds = 0

    for row in rows:
        vid = row["video_id"]
        path = files.get(vid)
        if not path:
            missing.append((vid, row["title"]))
            continue
        size = path.stat().st_size
        total_bytes += size
        total_seconds += int(row["duration_seconds"] or 0)
        report.append({
            "video_id": vid,
            "title": row["title"],
            "duration_seconds": int(row["duration_seconds"] or 0),
            "file": path.name,
            "format": path.suffix.lstrip("."),
            "size_bytes": size,
            "url": row["url"],
        })

    with (CATALOG / "download_report.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()) if report else ["video_id"])
        w.writeheader()
        w.writerows(report)

    print(f"downloaded: {len(report)}/{len(rows)}")
    print(f"size: {total_bytes / 1e9:.2f} GB")
    print(f"runtime covered: {total_seconds / 3600:.1f} hours")
    if missing:
        print(f"\nmissing: {len(missing)}")
        for vid, title in missing[:10]:
            print(f"  {vid}  {title}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    sup_path = CATALOG / "supplements.csv"
    if sup_path.exists():
        sup_rows = list(csv.DictReader(sup_path.open(encoding="utf-8")))
        sup_files = index_files(SUPPLEMENTS_DIR, recursive=True)
        sup_size = sum(p.stat().st_size for p in sup_files.values())
        print(f"supplements: {len(sup_files)}/{len(sup_rows)} ({sup_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
