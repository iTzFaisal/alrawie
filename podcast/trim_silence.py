#!/usr/bin/env python3
"""Trim trailing digital silence from the files recorded in the report.

The report (``catalog/trailing_silence.csv``) is produced by the silence scan
and carries the recommended cut point for every file. This script applies those
cuts in place with a stream copy (no re-encode), keeping a local backup under
``dist/audio-originals/`` first, and records the applied duration, new size and
SHA-256 back into the report.

    python3 podcast/trim_silence.py              # dry run
    python3 podcast/trim_silence.py --apply      # crop, with backups
    python3 podcast/trim_silence.py --apply --only OtWUnyGiR58,k7g61lkLMUw
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audios"
REPORT = ROOT / "catalog" / "trailing_silence.csv"
BACKUP = ROOT / "dist" / "audio-originals"
START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")
TOLERANCE = 0.4


class TrimError(Exception):
    pass


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def ffprobe_streams(path: Path) -> list[dict[str, str]]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return [
        {"codec": stream.get("codec_name", ""), "type": stream.get("codec_type", "")}
        for stream in json.loads(out).get("streams", [])
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def last_silence(path: Path, duration: float) -> tuple[float, float] | None:
    """Return the last silence interval, if it reaches the end of the file."""
    log = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostdin", "-i", str(path),
         "-af", "silencedetect=noise=-45dB:d=2", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    starts = [float(x) for x in START_RE.findall(log)]
    ends = [float(x) for x in END_RE.findall(log)]
    pairs = []
    for start in starts:
        later = [end for end in ends if end > start]
        pairs.append((start, min(later) if later else duration))
    if pairs and pairs[-1][1] >= duration - 0.4:
        return pairs[-1]
    return None


def verify(trimmed: Path, target: float, original_size: int) -> None:
    duration = ffprobe_duration(trimmed)
    if abs(duration - target) > TOLERANCE:
        raise TrimError(f"{trimmed.name}: duration {duration:.2f}s != target {target:.2f}s")
    streams = ffprobe_streams(trimmed)
    if streams != [{"codec": "aac", "type": "audio"}]:
        raise TrimError(f"{trimmed.name}: unexpected streams {streams}")
    size = trimmed.stat().st_size
    if size == 0 or size >= original_size:
        raise TrimError(f"{trimmed.name}: size {size} not smaller than {original_size}")
    trailing = last_silence(trimmed, duration)
    if trailing is not None:
        raise TrimError(
            f"{trimmed.name}: still {trailing[1] - trailing[0]:.1f}s of silence at the end"
        )


def write_report(rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    tmp = REPORT.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(REPORT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="crop the files (default: dry run)")
    parser.add_argument("--only", help="comma-separated video IDs to process")
    args = parser.parse_args()

    if not REPORT.exists():
        raise SystemExit(f"missing report: {REPORT}")
    with REPORT.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fieldnames = list(rows[0])
    for name in ("applied_duration_s", "new_size_bytes", "new_sha256"):
        if name not in fieldnames:
            fieldnames.append(name)
    for row in rows:
        for name in ("applied_duration_s", "new_size_bytes", "new_sha256"):
            row.setdefault(name, "")

    only = set(args.only.split(",")) if args.only else None
    targets = [row for row in rows if row["trim"] == "yes"]
    if only:
        targets = [row for row in targets if row["video_id"] in only]
    if not targets:
        raise SystemExit("nothing to do")

    total_before = total_after = 0
    planned = applied = skipped = 0
    for position, row in enumerate(targets, 1):
        source = AUDIO / row["series"] / row["filename"]
        if not source.exists():
            raise SystemExit(f"missing audio file: {source}")
        original = float(row["duration_s"])
        target = float(row["recommended_duration_s"])
        current = ffprobe_duration(source)
        before = source.stat().st_size
        total_before += before

        if row["applied_duration_s"] and abs(current - float(row["applied_duration_s"])) <= TOLERANCE:
            print(f"[{position:2}/{len(targets)}] skip  {row['video_id']}  already applied")
            total_after += before
            skipped += 1
            continue
        if abs(current - target) <= TOLERANCE:
            row["applied_duration_s"] = f"{current:.3f}"
            row["new_size_bytes"] = str(before)
            row["new_sha256"] = sha256(source)
            print(f"[{position:2}/{len(targets)}] record {row['video_id']}  already at {current:.1f}s")
            total_after += before
            skipped += 1
            continue
        if abs(current - original) > TOLERANCE:
            raise SystemExit(
                f"{source.name}: duration {current:.2f}s matches neither "
                f"source {original:.2f}s nor target {target:.2f}s"
            )

        print(
            f"[{position:2}/{len(targets)}] {'trim' if args.apply else 'plan'}  "
            f"{row['video_id']}  {current:7.1f}s -> {target:7.1f}s  "
            f"({current - target:6.1f}s removed)"
        )
        planned += 1
        if not args.apply:
            total_after += int(before * target / current)
            continue

        backup = BACKUP / row["series"] / row["filename"]
        if backup.exists():
            if backup.stat().st_size != before:
                raise SystemExit(f"backup mismatch, refusing to overwrite: {backup}")
        else:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)

        tmp = source.with_name(source.stem + ".trim.m4a")
        subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-i", str(source), "-t", f"{target:.3f}", "-c", "copy",
             "-movflags", "+faststart", str(tmp)],
            check=True,
        )
        try:
            verify(tmp, target, before)
        except TrimError:
            tmp.unlink(missing_ok=True)
            raise

        after = tmp.stat().st_size
        tmp.replace(source)
        row["applied_duration_s"] = f"{ffprobe_duration(source):.3f}"
        row["new_size_bytes"] = str(after)
        row["new_sha256"] = sha256(source)
        write_report(rows, fieldnames)
        total_after += after
        applied += 1

    verb = "applied" if args.apply else "planned"
    print(
        f"\n{verb}: {applied if args.apply else planned}, skipped: {skipped}; "
        f"{total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB"
    )
    if not args.apply:
        print("dry run only; re-run with --apply to crop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
