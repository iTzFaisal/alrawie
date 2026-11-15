#!/usr/bin/env python3
"""Check docs/feed.xml and docs/kasayet/feed.xml before publishing.

    python3 podcast/validate_feed.py

Only the standard library is used, so this runs on a bare checkout.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_feed as bf  # noqa: E402

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "atom": "http://www.w3.org/2005/Atom",
}
REQUIRED_CHANNEL = [
    "title",
    "link",
    "description",
    "language",
    "itunes:image",
    "itunes:author",
    "itunes:summary",
    "itunes:owner/itunes:email",
    "itunes:category",
    "itunes:explicit",
    "itunes:type",
]
REQUIRED_ITEM = [
    "title",
    "description",
    "guid",
    "pubDate",
    "enclosure",
    "itunes:duration",
    "itunes:season",
    "itunes:episode",
]


def fail(message: str) -> None:
    print(f"FAIL {message}")
    raise SystemExit(1)


def jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    index = 2
    while index < len(data) - 9:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        index += 2 + int.from_bytes(data[index + 2 : index + 4], "big")
    raise ValueError("no SOF marker")


def check_cover(show: bf.Show) -> None:
    path = bf.DOCS / show.cover
    if not path.exists():
        fail(f"{show.key}: missing cover {path}")
    width, height = jpeg_size(path)
    if (width, height) != (3000, 3000):
        fail(f"{show.key}: cover is {width}x{height}, expected 3000x3000")
    if path.stat().st_size > 10 * 1024 * 1024:
        fail(f"{show.key}: cover is larger than 10 MB")


def check_show(show: bf.Show) -> None:
    path = bf.DOCS / show.feed_rel
    if not path.exists():
        fail(f"{show.key}: missing feed {path}")
    tree = ET.parse(path)
    channel = tree.getroot().find("channel")
    if tree.getroot().tag != "rss" or channel is None:
        fail(f"{show.key}: not an RSS channel")

    for tag in REQUIRED_CHANNEL:
        if channel.find(tag, NS) is None:
            fail(f"{show.key}: channel is missing <{tag}>")
    if channel.find("itunes:owner/itunes:email", NS).text.strip() == "":
        fail(f"{show.key}: owner e-mail is empty")
    if channel.find("itunes:image", NS).get("href") != show.cover_url:
        fail(f"{show.key}: channel artwork URL mismatch")

    items = channel.findall("item")
    if len(items) != len(show.episodes):
        fail(f"{show.key}: {len(items)} items, expected {len(show.episodes)}")

    guids: set[str] = set()
    titles: set[str] = set()
    previous: str | None = None
    for item, episode in zip(items, show.episodes):
        for tag in REQUIRED_ITEM:
            if item.find(tag, NS) is None:
                fail(f"{show.key}: item {episode.video_id} is missing <{tag}>")
        guid = item.findtext("guid")
        if guid in guids:
            fail(f"{show.key}: duplicate guid {guid}")
        guids.add(guid)
        title = item.findtext("title")
        if title in titles:
            fail(f"{show.key}: duplicate title {title!r}")
        titles.add(title)

        enclosure = item.find("enclosure")
        if enclosure.get("type") != "audio/x-m4a":
            fail(f"{show.key}: {guid} has enclosure type {enclosure.get('type')}")
        if int(enclosure.get("length")) != episode.size:
            fail(f"{show.key}: {guid} enclosure length does not match the file size")
        tag = dict(show.seasons)[episode.series]
        if enclosure.get("url") != episode.url(f"audio-{tag}"):
            fail(f"{show.key}: {guid} points at the wrong asset URL")

        published = item.findtext("pubDate")
        if previous is not None and published >= previous:
            fail(f"{show.key}: {guid} is not older than the previous item")
        previous = published

    print(
        f"ok {show.key}: {len(items)} items, {len(show.seasons)} seasons, "
        f"{sum(e.duration for e in show.episodes) / 3600:.1f} h, "
        f"{path.stat().st_size / 1024:.0f} KiB feed"
    )


def main() -> int:
    shows = bf.build_shows()
    for show in shows:
        check_cover(show)
        check_show(show)
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
