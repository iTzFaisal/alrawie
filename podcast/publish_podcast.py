#!/usr/bin/env python3
"""Upload every episode as its own GitHub Release asset.

Podcast apps need one stable URL per episode, which the zips in the archive
release cannot provide. Each series becomes an `audio-<slug>` release whose
asset names are `<video-id>.m4a`; the feed points straight at them.

    python3 podcast/publish_podcast.py --dry-run    # show the plan
    python3 podcast/publish_podcast.py              # upload what is missing

Re-running is safe: assets already present with the right size are skipped, so
an interrupted run resumes where it stopped. Requires an authenticated `gh`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_feed as bf  # noqa: E402


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SystemExit(f"gh {' '.join(args)} failed: {detail[-1] if detail else ''}")
    return result


def existing_assets(tag: str) -> dict[str, int] | None:
    result = gh("release", "view", tag, "--repo", bf.REPO, "--json", "assets", check=False)
    if result.returncode != 0:
        if "not found" in (result.stderr or "").lower():
            return None
        raise SystemExit(f"cannot inspect release {tag}: {result.stderr.strip()}")
    return {asset["name"]: asset["size"] for asset in json.loads(result.stdout)["assets"]}


def ensure_release(show: bf.Show, series: str, tag: str) -> dict[str, int]:
    assets = existing_assets(tag)
    if assets is not None:
        return assets
    notes = "\n".join(
        [
            f"حلقات سلسلة «{series}» من أرشيف الراوي فواز الغسلان، ملفًا ملفًا.",
            "",
            f"الاشتراك في البودكاست: {show.feed_url}",
            f"بقية الأرشيف: https://github.com/{bf.REPO}/releases",
        ]
    )
    gh(
        "release",
        "create",
        tag,
        "--repo",
        bf.REPO,
        "--title",
        f"{show.short_title} — {series}",
        "--notes",
        notes,
        "--latest=false",
    )
    print(f"created release {tag}")
    return {}


STAGE = bf.ROOT / "dist" / "podcast-stage"


def staged(episode: bf.Episode) -> Path:
    """Hardlink the episode under a clean name.

    The media files contain Arabic and a `[video-id]` suffix, and `gh release
    upload` expands its arguments as glob patterns, so `[...]` is read as a
    character class and never matches. A hardlink costs no extra space and
    makes the asset name exactly what the feed expects.
    """
    STAGE.mkdir(parents=True, exist_ok=True)
    link = STAGE / episode.asset
    if link.exists() and link.stat().st_size == episode.size:
        return link
    if link.exists():
        link.unlink()
    try:
        os.link(episode.path, link)
    except OSError:
        shutil.copy2(episode.path, link)
    return link


def upload(tag: str, episodes: list[bf.Episode]) -> None:
    gh("release", "upload", tag, *[str(staged(episode)) for episode in episodes],
       "--repo", bf.REPO)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    parser.add_argument("--only", help="limit to one tag or slug, e.g. mawsuat-sheriya")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="delete and re-upload assets whose size does not match the local file",
    )
    parser.add_argument("--batch", type=int, default=6, help="files per gh call (default 6)")
    parser.add_argument("--limit", type=int, help="stop after this many uploads")
    args = parser.parse_args()

    shows = bf.build_shows()
    plan: list[tuple[bf.Show, str, str, bf.Episode]] = []
    for show in shows:
        for series, slug in show.seasons:
            tag = f"audio-{slug}"
            for episode in show.episodes:
                if episode.series == series:
                    plan.append((show, series, tag, episode))

    if args.only:
        wanted = args.only.removeprefix("audio-")
        plan = [row for row in plan if wanted in (row[2].removeprefix("audio-"), row[1])]
        if not plan:
            raise SystemExit(f"no episodes matched {args.only!r}")

    total_bytes = sum(row[3].size for row in plan)
    print(f"{len(plan)} episodes, {total_bytes / 1024 / 1024 / 1024:.2f} GiB")

    if args.dry_run:
        for show, series, tag, episode in plan:
            print(f"  {tag:32} {episode.asset:16} {episode.size / 1e6:7.1f} MB  {episode.title[:40]}")
        return 0

    gh("auth", "status")

    uploaded = skipped = replaced = 0
    sent_bytes = 0
    started = time.monotonic()
    by_tag: dict[str, list[bf.Episode]] = {}
    for _, _, tag, episode in plan:
        by_tag.setdefault(tag, []).append(episode)

    for show in shows:
        for series, slug in show.seasons:
            tag = f"audio-{slug}"
            episodes = by_tag.get(tag)
            if not episodes:
                continue
            assets = ensure_release(show, series, tag)
            missing: list[bf.Episode] = []
            for episode in episodes:
                size = assets.get(episode.asset)
                if size == episode.size:
                    skipped += 1
                    continue
                if size is not None:
                    if not args.replace:
                        print(f"  size mismatch, skipping {episode.asset} ({size} != {episode.size})")
                        continue
                    gh("release", "delete-asset", tag, episode.asset, "--repo", bf.REPO, "--yes")
                    replaced += 1
                missing.append(episode)

            print(f"{tag}: {len(episodes) - len(missing)} present, {len(missing)} to upload")
            for start in range(0, len(missing), args.batch):
                if args.limit is not None and uploaded >= args.limit:
                    break
                chunk = missing[start : start + args.batch]
                if args.limit is not None:
                    chunk = chunk[: args.limit - uploaded]
                try:
                    upload(tag, chunk)
                except SystemExit as error:
                    print(f"  batch failed ({error}); retrying one by one")
                    for episode in chunk:
                        try:
                            upload(tag, [episode])
                        except SystemExit as inner:
                            raise SystemExit(f"upload failed for {episode.asset}: {inner}") from None
                uploaded += len(chunk)
                sent_bytes += sum(episode.size for episode in chunk)
                elapsed = time.monotonic() - started
                rate = sent_bytes / elapsed / 1e6 if elapsed else 0
                print(
                    f"  [{uploaded}/{len(plan)}] {chunk[-1].asset} "
                    f"({sent_bytes / 1e6:.0f} MB, {rate:.1f} MB/s)"
                )

    # Confirm the sizes GitHub recorded match the files on disk.
    if args.limit is not None:
        print(f"uploaded {uploaded}, skipped {skipped}, partial run — skipping completeness check")
        return 0
    problems = 0
    for tag in dict.fromkeys(row[2] for row in plan):
        assets = existing_assets(tag) or {}
        for episode in by_tag[tag]:
            if assets.get(episode.asset) != episode.size:
                print(f"  MISSING or wrong size: {tag}/{episode.asset}")
                problems += 1

    print(
        f"uploaded {uploaded}, skipped {skipped}, replaced {replaced}, "
        f"{sent_bytes / 1024 / 1024 / 1024:.2f} GiB sent"
    )
    if problems:
        print(f"{problems} assets still missing; re-run to finish")
        return 1
    print("all episode assets are present")
    print(f"feeds: {[show.feed_url for show in shows]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
