#!/usr/bin/env python3
"""Organize downloaded files.

* Move .m4a files into audios/<series>/ using catalog/ghasslan_mirrors.csv.
* Move yt-dlp .info.json sidecars from audios/ into metadata/.
* Leave audios/مكملات/ untouched.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).parent
VIDEOS = ROOT / "audios"
METADATA = ROOT / "metadata"
CATALOG = ROOT / "catalog" / "ghasslan_mirrors.csv"
NAME_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.m4a$")
FALLBACK_SERIES = "أخرى"
SUPPLEMENTS_DIR = "مكملات"
LEGACY_SUPPLEMENTS_DIRS = {"supplements"}


def is_supplement(path: Path) -> bool:
    return SUPPLEMENTS_DIR in path.parts or any(
        part in LEGACY_SUPPLEMENTS_DIRS for part in path.parts
    )


def load_series() -> dict[str, str]:
    if not CATALOG.exists():
        return {}
    with CATALOG.open(encoding="utf-8") as fh:
        return {
            row["video_id"]: row.get("series") or FALLBACK_SERIES
            for row in csv.DictReader(fh)
        }


def main() -> None:
    series = load_series()
    moved_audio = 0
    moved_meta = 0

    for src in sorted(VIDEOS.rglob("*.m4a")):
        if is_supplement(src):
            continue
        match = NAME_RE.search(src.name)
        if not match:
            continue
        target_dir = VIDEOS / series.get(match.group(1), FALLBACK_SERIES)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        if target == src:
            continue
        if target.exists():
            src.unlink()
        else:
            src.replace(target)
        moved_audio += 1

    for src in sorted(VIDEOS.rglob("*.info.json")):
        target_dir = METADATA / SUPPLEMENTS_DIR if is_supplement(src) else METADATA
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        if target.exists():
            target.unlink()
        src.replace(target)
        moved_meta += 1

    print(f"audio files organized: {moved_audio}")
    print(f"metadata files moved: {moved_meta}")


if __name__ == "__main__":
    main()
