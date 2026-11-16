#!/usr/bin/env python3
"""Check both feeds and the landing page player before publishing.

    python3 podcast/validate_feed.py

Only the standard library is used, so this runs on a bare checkout.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.error
import urllib.request
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


EPISODE_LINK_RE = re.compile(
    r'<a class="ep" href="([^"]+)" data-id="([A-Za-z0-9_-]{11})" '
    r'data-title="([^"]*)" data-series="[^"]*" data-number="\d+" '
    r'data-duration="(\d+)"'
)


def check_landing(shows: list[bf.Show]) -> None:
    """Every feed episode must be playable exactly once from the landing page."""
    path = bf.DOCS / "index.html"
    if not path.exists():
        fail(f"missing landing page {path}")
    text = path.read_text(encoding="utf-8")
    for marker in ('id="player"', 'id="p-audio"', 'id="p-toggle"'):
        if marker not in text:
            fail(f"landing page is missing {marker}")

    found = EPISODE_LINK_RE.findall(text)
    expected: list[tuple[str, str, str, str]] = []
    for show in shows:
        if f'id="panel-{show.key}"' not in text:
            fail(f"landing page is missing the {show.key} panel")
        for episode in show.episodes:
            tag = dict(show.seasons)[episode.series]
            expected.append(
                (
                    episode.url(f"audio-{tag}"),
                    episode.video_id,
                    episode.title,
                    str(episode.duration),
                )
            )

    if len(found) != len(expected):
        fail(f"landing page lists {len(found)} episodes, expected {len(expected)}")

    ids = [row[1] for row in found]
    if len(ids) != len(set(ids)):
        fail("landing page lists an episode twice")

    for actual, wanted in zip(found, expected):
        url, video_id, title, duration = actual
        if (url, video_id, html.unescape(title), duration) != wanted:
            fail(f"landing page episode {video_id} does not match the feed")

    print(f"ok landing: {len(found)} playable episodes, player present")


def check_urls(shows: list[bf.Show]) -> int:
    """HEAD every enclosure: catches releases that were not uploaded or renamed."""
    problems = 0
    for show in shows:
        for episode in show.episodes:
            tag = dict(show.seasons)[episode.series]
            request = urllib.request.Request(
                episode.url(f"audio-{tag}"), method="HEAD",
                headers={"User-Agent": "alrawie-feed-check"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    length = response.headers.get("Content-Length")
                if length is not None and int(length) != episode.size:
                    print(f"  size mismatch {episode.asset}: {length} != {episode.size}")
                    problems += 1
                    continue
            except urllib.error.HTTPError as error:
                status = error.code
            except Exception as error:  # noqa: BLE001 - report and keep going
                print(f"  error {episode.asset}: {error}")
                problems += 1
                continue
            if status != 200:
                print(f"  HTTP {status} {episode.asset}")
                problems += 1
        print(f"checked {show.key}: {len(show.episodes)} enclosure URLs")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", action="store_true", help="also HEAD every enclosure URL")
    args = parser.parse_args()

    shows = bf.build_shows()
    for show in shows:
        check_cover(show)
        check_show(show)
    check_landing(shows)
    if args.urls:
        problems = check_urls(shows)
        if problems:
            print(f"{problems} enclosure problems")
            return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
