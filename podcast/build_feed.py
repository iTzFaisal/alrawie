#!/usr/bin/env python3
"""Generate the podcast RSS feeds and landing page under docs/.

The audio itself lives in GitHub Releases, one asset per episode, so every
episode has a stable URL that podcast apps can subscribe to. This script only
writes text: docs/feed.xml, docs/kasayet/feed.xml and docs/index.html.

Run it from anywhere:  python3 podcast/build_feed.py
"""

from __future__ import annotations

import csv
import html
import re
from urllib.parse import quote
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audios"
CATALOG = ROOT / "catalog"
DOCS = ROOT / "docs"

SITE = "https://itzfaisal.github.io/alrawie"
REPO = "iTzFaisal/alrawie"
DOWNLOAD = f"https://github.com/{REPO}/releases/download"
OWNER_EMAIL = "faisalalkheraiji@gmail.com"

# Every episode gets a distinct publication timestamp so the feed order is the
# curated order (podcast apps list newest first). Fixed, not "now", so rebuilds
# are byte-identical and land as empty git diffs.
BASE_DATE = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)
STEP = timedelta(minutes=6)

SUPPLEMENT_SERIES = "مكملات"
CASSETTES = "كاسيت"

# Curated season order; must stay in sync with SLUGS in make_zips.py.
SEASONS = [
    ("الموسوعة الشعرية", "mawsuat-sheriya"),
    ("نوادر من التراث", "nawader-min-alturath"),
    ("جواهر الأمثال الشعبية", "jawaher-amthal-shaabiya"),
    ("عاشق ومعشوق", "asheq-wamaashuq"),
    ("ضحايا العشق", "dahaya-aleshq"),
    ("القصائد المتداخلة", "qasaid-mutadakhila"),
    ("فنجال الكيف", "finjal-alkayf"),
    ("أخرى", "okhra"),
    ("موسوعة التاريخ والأدب", "mawsuat-tarikh-wa-adab"),
    (SUPPLEMENT_SERIES, "mukammilat"),
]
CASSETTE_SLUG = "kasayet"

MAIN_COVER = "cover.jpg"
CASSETTE_COVER = "kasayet/cover.jpg"

LICENCE_AR = (
    "الحقوق تعود للراوي فواز الغسلان وللقنوات الناشرة. "
    "هذا الأرشيف للحفظ والاستماع الشخصي غير التجاري."
)

ID_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.m4a$")
DIACRITICS_RE = re.compile(r"[\u064B-\u0652\u0670\u0640]")
SPACE_RE = re.compile(r"\s+")
SPLIT_RE = re.compile(r"[|｜]")

NARRATOR = "فواز الغسلان"
NARRATOR_MARKERS = (NARRATOR, "الراوي فواز", "الراوية فواز", "صدى نجد")


class FeedError(Exception):
    pass


@dataclass
class Episode:
    video_id: str
    title: str
    raw_title: str
    series: str
    season: int
    number: int
    duration: int
    size: int
    path: Path
    published: datetime

    @property
    def asset(self) -> str:
        return f"{self.video_id}.m4a"

    def url(self, tag: str) -> str:
        return f"{DOWNLOAD}/{tag}/{self.asset}"

    @property
    def source(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class Show:
    key: str
    title: str
    short_title: str
    subtitle: str
    description: str
    summary: str
    keywords: str
    cover: str
    feed_rel: str
    apple: str
    seasons: list[tuple[str, str]] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)

    @property
    def feed_url(self) -> str:
        return f"{SITE}/{self.feed_rel}"

    @property
    def cover_url(self) -> str:
        return f"{SITE}/{self.cover}"


# --------------------------------------------------------------------------
# catalog parsing


def normalize(text: str) -> str:
    """Fold Arabic spelling variants so titles and series names can be compared."""
    text = unicodedata.normalize("NFKC", text)
    text = DIACRITICS_RE.sub("", text)
    text = re.sub(r"[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return SPACE_RE.sub(" ", text).strip()


def clean_title(raw: str, series: str) -> str:
    """Drop the channel/series/narrator boilerplate and keep the subject.

    Titles look like "قصة الجربوع | الراوي فواز الغسلان | الموسوعة الشعرية";
    everything after the first pipe is usually boilerplate.
    """
    keep: list[str] = []
    for part in SPLIT_RE.split(raw):
        part = SPACE_RE.sub(" ", part).strip(" -–—")
        if not part:
            continue
        part = re.sub(r"^(?:الراوي|الراوية)\s+", "", part)
        part = re.sub(r"\s+(?:الراوي|الراوية)$", "", part)
        folded = normalize(part)
        if not folded or folded == normalize(series):
            continue
        if any(marker in folded for marker in NARRATOR_MARKERS):
            continue
        keep.append(part)
    return " — ".join(keep)


def index_audio() -> dict[str, Path]:
    if not AUDIO.is_dir():
        raise FeedError(f"missing audio directory: {AUDIO}")
    found: dict[str, Path] = {}
    for path in AUDIO.rglob("*.m4a"):
        match = ID_RE.search(path.name)
        if match:
            found[match.group(1)] = path
    return found


def read_rows() -> list[tuple[str, str]]:
    """Return (video_id, series) for the main catalog plus the supplements."""
    rows: list[tuple[str, str]] = []
    with (CATALOG / "ghasslan_mirrors.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["video_id"], row["series"].strip() or "أخرى"))
    if (CATALOG / "supplements.csv").exists():
        with (CATALOG / "supplements.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append((row["video_id"], SUPPLEMENT_SERIES))
    return rows


def read_titles() -> dict[str, tuple[str, str]]:
    """video_id -> (raw title, duration seconds)."""
    titles: dict[str, tuple[str, str]] = {}
    for name, id_column in (
        ("ghasslan_mirrors.csv", "video_id"),
        ("supplements.csv", "video_id"),
    ):
        path = CATALOG / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                titles[row[id_column]] = (row["title"], row["duration_seconds"])
    return titles


# --------------------------------------------------------------------------
# assembling the shows


def collect(rows, titles, files, series, season) -> list[Episode]:
    episodes: list[Episode] = []
    for video_id, row_series in rows:
        if row_series != series:
            continue
        path = files.get(video_id)
        if path is None:
            raise FeedError(f"{video_id} ({series}) has no M4A file under audios/")
        raw, duration = titles[video_id]
        episodes.append(
            Episode(
                video_id=video_id,
                title=clean_title(raw, series),
                raw_title=raw.strip(),
                series=series,
                season=season,
                number=len(episodes) + 1,
                duration=int(duration),
                size=path.stat().st_size,
                path=path,
                published=BASE_DATE,
            )
        )

    # Titles that the source left blank become "series — القسم n", and repeated
    # titles get a section suffix so no two episodes look identical.
    blanks = [ep for ep in episodes if not ep.title]
    for position, ep in enumerate(blanks, start=1):
        ep.title = f"{series} — القسم {position}"
    counts: dict[str, int] = {}
    for ep in episodes:
        counts[ep.title] = counts.get(ep.title, 0) + 1
    seen: dict[str, int] = {}
    for ep in episodes:
        if counts[ep.title] == 1:
            continue
        seen[ep.title] = seen.get(ep.title, 0) + 1
        ep.title = f"{ep.title} — القسم {seen[ep.title]}"
    return episodes


def build_shows() -> list[Show]:
    files = index_audio()
    titles = read_titles()
    rows = read_rows()

    main = Show(
        key="main",
        title="أرشيف الراوي فواز الغسلان",
        short_title="فواز الغسلان",
        subtitle="الشعر النبطي · القصص · الأمثال",
        description=(
            "أرشيف صوتي كامل لتسجيلات الراوي فواز الغسلان: قصص وقصائد من "
            "الشعر النبطي، وأمثال وحكايات من التراث العربي، مروية بصوته. "
            "جُمعت من قناة المرآة «صدى نجد دوت كوم» بعد حذف القناة الأصلية، "
            "وأُتيحت هنا حلقةً حلقة لتصلك في تطبيق البودكاست الذي تحب."
        ),
        summary=(
            "قصص وقصائد وأمثال من التراث العربي بصوت الراوي فواز الغسلان، "
            "مجموعة في عشر سلاسل مرتّبة."
        ),
        keywords="فواز الغسلان,شعر نبطي,تراث,قصص,أمثال,نجد,العرب",
        cover=MAIN_COVER,
        feed_rel="feed.xml",
        apple="https://podcasts.apple.com/us/podcast/أرشيف-الراوي-فواز-الغسلان/id6835240326",
        seasons=SEASONS,
    )
    cassette_show = Show(
        key="kasayet",
        title="فواز الغسلان — الكاسيتات الكاملة",
        short_title="الكاسيتات الكاملة",
        subtitle="الأشرطة الأصلية كاملة",
        description=(
            "الأشرطة الأصلية الكاملة التي اقتُطعت منها حلقات أرشيف الراوي "
            "فواز الغسلان: اثنا عشر كاسيتًا، نحو أربع عشرة ساعة ونصف. "
            "لمن يفضّل الاستماع على ترتيب الشريط كما صدر."
        ),
        summary=(
            "اثنا عشر كاسيتًا كاملًا لتسجيلات الراوي فواز الغسلان، "
            "دون تقطيع، على ترتيب الشريط الأصلي."
        ),
        keywords="فواز الغسلان,كاسيت,أشرطة,شعر نبطي,تراث",
        cover=CASSETTE_COVER,
        feed_rel="kasayet/feed.xml",
        apple="https://podcasts.apple.com/us/podcast/فواز-الغسلان-—-الكاسيتات-الكاملة/id6835240746",
        seasons=[(CASSETTES, CASSETTE_SLUG)],
    )

    for show in (main, cassette_show):
        for index, (series, slug) in enumerate(show.seasons, start=1):
            show.episodes.extend(collect(rows, titles, files, series, index))

    for show in (main, cassette_show):
        if not show.episodes:
            raise FeedError(f"show {show.key!r} has no episodes")

    main.episodes.sort(key=lambda ep: (ep.season, ep.number))
    cassette_show.episodes.sort(key=lambda ep: (ep.season, ep.number))
    for show in (main, cassette_show):
        for index, ep in enumerate(show.episodes):
            ep.published = BASE_DATE - STEP * index
    return [main, cassette_show]


# --------------------------------------------------------------------------
# RSS


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def clock(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def arabic_number(value: int) -> str:
    return str(value).translate(AR_DIGITS)


def human(seconds: int) -> str:
    hours = seconds // 3600
    minutes = round((seconds % 3600) / 60)
    if minutes == 60:
        hours, minutes = hours + 1, 0
    if hours and minutes:
        return f"{arabic_number(hours)} س {arabic_number(minutes)} د"
    if hours:
        return f"{arabic_number(hours)} ساعة"
    return f"{arabic_number(minutes)} دقيقة"


def arabic_clock(seconds: int) -> str:
    return clock(seconds).translate(AR_DIGITS)


def episode_xml(ep: Episode, show: Show, tag: str) -> str:
    lines = [
        f"من سلسلة «{ep.series}» — {show.subtitle}.",
        f"المدة: {clock(ep.duration)}",
    ]
    if normalize(ep.raw_title) != normalize(ep.title):
        lines.append(f"العنوان الأصلي: {ep.raw_title}")
    lines += [f"المصدر: {ep.source}", LICENCE_AR]
    description = "\n".join(lines)
    return "\n".join(
        [
            "    <item>",
            f"      <title>{esc(ep.title)}</title>",
            f"      <description>{esc(description)}</description>",
            f"      <link>{esc(ep.source)}</link>",
            f'      <guid isPermaLink="false">{ep.video_id}</guid>',
            f"      <pubDate>{format_datetime(ep.published)}</pubDate>",
            f'      <enclosure url="{esc(ep.url(tag))}" length="{ep.size}" type="audio/x-m4a"/>',
            f"      <itunes:duration>{clock(ep.duration)}</itunes:duration>",
            f"      <itunes:season>{ep.season}</itunes:season>",
            f"      <itunes:episode>{ep.number}</itunes:episode>",
            "      <itunes:episodeType>full</itunes:episodeType>",
            "      <itunes:explicit>false</itunes:explicit>",
            f"      <itunes:author>{esc(show.title)}</itunes:author>",
            "    </item>",
        ]
    )


def feed_xml(show: Show) -> str:
    episodes = show.episodes
    tags = {series: f"audio-{slug}" for series, slug in show.seasons}
    items = "\n".join(episode_xml(ep, show, tags[ep.series]) for ep in episodes)
    last_build = format_datetime(max(ep.published for ep in episodes))
    category = (
        '<itunes:category text="Arts"><itunes:category text="Books"/></itunes:category>\n'
        '    <itunes:category text="Society &amp; Culture"/>'
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(show.title)}</title>
    <link>{SITE}/</link>
    <atom:link href="{esc(show.feed_url)}" rel="self" type="application/rss+xml"/>
    <description>{esc(show.description)}</description>
    <language>ar</language>
    <copyright>{esc(LICENCE_AR)}</copyright>
    <lastBuildDate>{last_build}</lastBuildDate>
    <generator>podcast/build_feed.py</generator>
    <itunes:author>{esc(show.title)}</itunes:author>
    <itunes:summary>{esc(show.summary)}</itunes:summary>
    <itunes:subtitle>{esc(show.subtitle)}</itunes:subtitle>
    <itunes:keywords>{esc(show.keywords)}</itunes:keywords>
    <itunes:owner>
      <itunes:name>أرشيف فواز الغسلان</itunes:name>
      <itunes:email>{OWNER_EMAIL}</itunes:email>
    </itunes:owner>
    <itunes:image href="{esc(show.cover_url)}"/>
    <image>
      <url>{esc(show.cover_url)}</url>
      <title>{esc(show.title)}</title>
      <link>{SITE}/</link>
    </image>
    {category}
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
{items}
  </channel>
</rss>
"""


# --------------------------------------------------------------------------
# landing page: episode browser and player


def episode_row(ep: Episode, url: str) -> str:
    title = esc(ep.title)
    return (
        f'<li><a class="ep" href="{esc(url)}" data-id="{ep.video_id}" '
        f'data-title="{title}" data-series="{esc(ep.series)}" '
        f'data-number="{ep.number}" data-duration="{ep.duration}">'
        f'<span class="ep-num">{arabic_number(ep.number)}</span>'
        f'<span class="ep-name">{title}</span>'
        f'<span class="ep-time">{arabic_clock(ep.duration)}</span>'
        '<span class="ep-icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24"><use href="#i-play"/></svg></span>'
        "</a></li>"
    )


def season_block(show: Show, series: str, episodes: list[Episode], tag: str) -> str:
    rows = "\n".join(
        "          " + episode_row(ep, ep.url(tag)) for ep in episodes
    )
    unit = "كاسيت" if show.key == "kasayet" else "حلقة"
    meta = (
        f"{arabic_number(len(episodes))} {unit} · "
        f"{human(sum(ep.duration for ep in episodes))}"
    )
    return (
        '      <details class="season">\n'
        f'        <summary><span class="season-name">{esc(series)}</span>'
        f'<span class="season-meta">{meta}</span>'
        '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M7.4 9.6 12 14.2l4.6-4.6L18 11l-6 6-6-6z"/></svg>'
        "</summary>\n"
        f'        <ol class="episodes">\n{rows}\n        </ol>\n'
        "      </details>"
    )


def listen_panel(show: Show) -> str:
    blocks = []
    for season_index, (series, slug) in enumerate(show.seasons, start=1):
        episodes = [ep for ep in show.episodes if ep.season == season_index]
        if episodes:
            blocks.append(season_block(show, series, episodes, f"audio-{slug}"))
    return (
        f'    <div class="panel" id="panel-{show.key}" role="tabpanel" '
        f'aria-labelledby="tab-{show.key}" data-key="{show.key}" '
        f'data-title="{esc(show.title)}" data-cover="{show.cover}">\n'
        '      <label class="search">\n'
        '        <span class="sr-only">ابحث في العناوين</span>\n'
        '        <input type="search" placeholder="ابحث في عناوين الحلقات…" autocomplete="off">\n'
        "      </label>\n"
        '      <p class="no-results" hidden>لا توجد حلقات مطابقة.</p>\n'
        + "\n".join(blocks)
        + "\n    </div>"
    )


def listen_section(shows: list[Show]) -> str:
    labels = {"main": "الحلقات المفردة", "kasayet": "الكاسيتات الكاملة"}
    tabs = "\n".join(
        f'      <button type="button" role="tab" id="tab-{show.key}" '
        f'aria-controls="panel-{show.key}" '
        f'aria-selected="{"true" if index == 0 else "false"}" '
        f'tabindex="{0 if index == 0 else -1}" data-key="{show.key}">'
        f"{labels.get(show.key, show.short_title)}</button>"
        for index, show in enumerate(shows)
    )
    panels = "\n".join(listen_panel(show) for show in shows)
    return f"""  <section class="listen" id="listen">
    <h2>استمع الآن</h2>
    <p class="hint">اختر سلسلة ثم حلقة ليبدأ التشغيل فورًا في المشغّل أسفل الصفحة، دون تطبيق بودكاست. يمكنك البحث في العناوين والتنقّل بين الحلقات.</p>
    <div class="tabs" role="tablist" aria-label="اختر البرنامج">
{tabs}
    </div>
{panels}
  </section>"""


PLAYER_HTML = """<div class="player" id="player" role="region" aria-label="مشغل الحلقات" hidden>
  <div class="player-inner">
    <img class="p-cover" id="p-cover" src="cover.jpg" alt="">
    <div class="p-info">
      <div class="p-title" id="p-title"></div>
      <div class="p-sub" id="p-sub"></div>
    </div>
    <div class="p-controls">
      <button class="pbtn" id="p-prev" type="button" aria-label="الحلقة السابقة"><svg viewBox="0 0 24 24"><use href="#i-prev"/></svg></button>
      <button class="pbtn" id="p-back" type="button" aria-label="إرجاع ١٥ ثانية"><svg viewBox="0 0 24 24"><use href="#i-back"/></svg></button>
      <button class="pbtn" id="p-toggle" type="button" aria-label="تشغيل"><svg viewBox="0 0 24 24"><use href="#i-play"/></svg></button>
      <button class="pbtn" id="p-fwd" type="button" aria-label="تقديم ٣٠ ثانية"><svg viewBox="0 0 24 24"><use href="#i-fwd"/></svg></button>
      <button class="pbtn" id="p-next" type="button" aria-label="الحلقة التالية"><svg viewBox="0 0 24 24"><use href="#i-next"/></svg></button>
      <select class="p-rate" id="p-rate" aria-label="سرعة التشغيل">
        <option value="1">١×</option>
        <option value="1.25">١٫٢٥×</option>
        <option value="1.5">١٫٥×</option>
        <option value="1.75">١٫٧٥×</option>
        <option value="2">٢×</option>
      </select>
    </div>
    <div class="p-actions">
      <a class="pbtn" id="p-download" href="#" aria-label="تحميل الحلقة" title="تحميل"><svg viewBox="0 0 24 24"><use href="#i-download"/></svg></a>
      <button class="pbtn" id="p-close" type="button" aria-label="إغلاق المشغل" title="إغلاق"><svg viewBox="0 0 24 24"><use href="#i-close"/></svg></button>
    </div>
    <div class="p-seek">
      <span class="p-time" id="p-cur">٠:٠٠</span>
      <input type="range" id="p-range" min="0" max="1000" value="0" step="1" aria-label="موضع التشغيل">
      <span class="p-time" id="p-dur">٠:٠٠</span>
    </div>
  </div>
  <audio id="p-audio" preload="metadata"></audio>
</div>"""


PAGE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f7f2e8">
<title>{title}</title>
<link rel="alternate" type="application/rss+xml" title="أرشيف الراوي فواز الغسلان" href="feed.xml">
<link rel="alternate" type="application/rss+xml" title="الكاسيتات الكاملة" href="kasayet/feed.xml">
<style>
  :root {{
    --ink: #1b1712; --muted: #6d6254; --line: #e4dbcb;
    --sand: #f7f2e8; --gold: #a8791f; --card: #fffdf8;
  }}
  * {{ box-sizing: border-box; }}
  [hidden] {{ display: none !important; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0; padding: 48px 20px 72px; background: var(--sand); color: var(--ink);
    font-family: "Al Nile", "Geeza Pro", "Noto Naskh Arabic", "Segoe UI", Tahoma, sans-serif;
    line-height: 1.8;
  }}
  main {{ max-width: 860px; margin: 0 auto; }}
  header {{ text-align: center; margin-bottom: 40px; }}
  header .kicker {{ color: var(--gold); letter-spacing: .12em; font-size: 14px; }}
  h1 {{ font-size: clamp(30px, 5vw, 44px); margin: 10px 0 8px; }}
  header p {{ color: var(--muted); margin: 0 auto; max-width: 620px; }}
  .shows {{ display: grid; gap: 22px; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); }}
  .show {{
    background: var(--card); border: 1px solid var(--line); border-radius: 18px;
    padding: 22px; display: flex; flex-direction: column; gap: 14px;
  }}
  .show img {{ width: 100%; max-width: 240px; border-radius: 12px; align-self: center; }}
  .show h2 {{ margin: 0; font-size: 22px; }}
  .show p {{ margin: 0; color: var(--muted); font-size: 15px; }}
  .feed {{
    display: flex; gap: 8px; align-items: stretch; flex-wrap: wrap;
  }}
  .feed code {{
    flex: 1 1 220px; direction: ltr; text-align: left; background: var(--sand);
    border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
    font-size: 12px; overflow-wrap: anywhere; font-family: ui-monospace, Menlo, monospace;
  }}
  button, .button {{
    font: inherit; font-size: 14px; cursor: pointer; border-radius: 10px;
    border: 1px solid var(--gold); background: var(--gold); color: #fff;
    padding: 9px 14px; text-decoration: none; white-space: nowrap;
    display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  }}
  button.secondary, .button.secondary {{ background: transparent; color: var(--gold); }}
  .button.apple {{ background: #111; border-color: #111; color: #fff; display: inline-flex; align-items: center; gap: 8px; }}
  .button.apple::before {{
    content: ""; width: 13px; height: 15px; background: currentColor;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 384 512'%3E%3Cpath d='M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z'/%3E%3C/svg%3E") no-repeat center / contain;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 384 512'%3E%3Cpath d='M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z'/%3E%3C/svg%3E") no-repeat center / contain;
  }}
  .meta {{ font-size: 13px; color: var(--muted); }}
  .listen {{ margin-top: 46px; scroll-margin-top: 24px; }}
  .listen > h2 {{ margin: 0 0 6px; font-size: 20px; }}
  .listen .hint {{ margin: 0 0 16px; color: var(--muted); font-size: 14px; }}
  .tabs {{
    display: flex; gap: 4px; padding: 4px; border: 1px solid var(--line);
    background: #efe7d8; border-radius: 12px;
  }}
  .tabs button {{
    flex: 1; padding: 9px 10px; border: 0; border-radius: 9px;
    background: transparent; color: var(--muted); font-size: 14px;
  }}
  .tabs button[aria-selected="true"] {{
    background: var(--card); color: var(--ink);
    box-shadow: 0 1px 3px rgba(27, 23, 18, .1);
  }}
  .search {{ display: block; margin: 16px 0 4px; }}
  .search input {{
    width: 100%; padding: 11px 14px; border: 1px solid var(--line);
    border-radius: 10px; background: var(--card); color: var(--ink);
    font: inherit; font-size: 14px;
  }}
  .search input:focus {{ outline: 2px solid rgba(168, 121, 31, .35); outline-offset: 1px; }}
  .no-results {{ color: var(--muted); font-size: 14px; padding: 10px 4px; }}
  .season {{
    margin: 10px 0; border: 1px solid var(--line); border-radius: 14px;
    background: var(--card); overflow: hidden;
  }}
  .season summary {{
    display: flex; align-items: center; gap: 10px; padding: 13px 15px;
    cursor: pointer; list-style: none; font-weight: 600;
  }}
  .season summary::-webkit-details-marker {{ display: none; }}
  .season summary:hover {{ background: #faf5ea; }}
  .season-name {{ flex: 1; min-width: 0; font-size: 15px; }}
  .season-meta {{ color: var(--muted); font-size: 12px; font-weight: 400; white-space: nowrap; }}
  .chev {{ flex: none; width: 18px; height: 18px; fill: var(--muted); transition: transform .2s; }}
  .season[open] .chev {{ transform: rotate(180deg); }}
  .episodes {{ margin: 0; padding: 0 6px 8px; list-style: none; }}
  .ep {{
    display: grid; grid-template-columns: 26px minmax(0, 1fr) auto 22px;
    align-items: center; gap: 10px; padding: 8px 10px; border-radius: 9px;
    color: var(--ink); text-decoration: none; font-size: 14px; line-height: 1.55;
  }}
  .ep:hover {{ background: #f6efdf; }}
  .ep.playing {{ background: #f2e5c9; }}
  .ep-num {{ color: var(--muted); font-size: 11px; text-align: center; }}
  .ep-name {{ min-width: 0; }}
  .ep-time {{ color: var(--muted); font-size: 11.5px; white-space: nowrap; }}
  .ep-icon {{ display: flex; justify-content: center; }}
  .ep-icon svg {{ width: 15px; height: 15px; fill: var(--gold); opacity: .5; }}
  .ep:hover .ep-icon svg, .ep.playing .ep-icon svg {{ opacity: 1; }}
  .ep.playing .ep-icon svg {{ fill: var(--ink); }}
  .listen-jump {{ width: 100%; }}
  .btn-icon {{ width: 14px; height: 14px; fill: currentColor; flex: none; }}
  .sr-only {{
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
  }}
  .icons {{ display: none; }}
  .player {{
    position: fixed; inset-inline: 0; bottom: 0; z-index: 40;
    background: #1b1712; color: #f7f2e8;
    box-shadow: 0 -10px 30px rgba(27, 23, 18, .25);
  }}
  .player-inner {{
    max-width: 860px; margin: 0 auto; padding: 9px 16px 11px;
    display: grid; align-items: center; gap: 6px 12px;
    grid-template-columns: 44px minmax(0, 1fr) auto;
    grid-template-areas: "cover info actions" "controls controls controls" "seek seek seek";
  }}
  .p-cover {{ grid-area: cover; width: 44px; height: 44px; border-radius: 8px; object-fit: cover; }}
  .p-info {{ grid-area: info; min-width: 0; line-height: 1.45; }}
  .p-title {{ font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .p-sub {{ font-size: 11.5px; color: #bdb19d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .p-controls {{ grid-area: controls; display: flex; align-items: center; justify-content: center; gap: 2px; }}
  .p-actions {{ grid-area: actions; display: flex; align-items: center; gap: 2px; }}
  .pbtn {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 38px; height: 38px; padding: 0; border: 0; border-radius: 999px;
    background: transparent; color: inherit; cursor: pointer;
  }}
  .pbtn:hover {{ background: rgba(247, 242, 232, .1); }}
  .pbtn svg {{ width: 20px; height: 20px; fill: currentColor; }}
  #p-toggle {{ width: 44px; height: 44px; background: var(--gold); color: #fff; }}
  #p-toggle:hover {{ background: #b9842a; }}
  #p-toggle svg {{ width: 22px; height: 22px; }}
  .p-rate {{
    height: 30px; margin-inline-start: 6px; padding: 0 6px; border-radius: 7px;
    border: 1px solid rgba(247, 242, 232, .3); background: transparent;
    color: inherit; font: inherit; font-size: 12px;
  }}
  .p-rate option {{ color: var(--ink); }}
  .p-seek {{ grid-area: seek; display: flex; align-items: center; gap: 10px; }}
  #p-range {{ flex: 1; min-width: 0; height: 18px; accent-color: var(--gold); cursor: pointer; }}
  .p-time {{
    min-width: 40px; text-align: center; font-size: 11px;
    color: #cfc4b0; font-variant-numeric: tabular-nums;
  }}
  body.has-player {{ padding-bottom: 214px; }}
  @media (min-width: 700px) {{
    .player-inner {{
      grid-template-columns: 46px minmax(0, 1fr) auto auto;
      grid-template-areas: "cover info controls actions" "seek seek seek seek";
      padding: 10px 18px 12px;
    }}
    .p-controls {{ justify-content: flex-start; }}
    body.has-player {{ padding-bottom: 136px; }}
  }}
  ol {{ padding-inline-start: 20px; color: var(--muted); font-size: 15px; }}
  ol li {{ margin: 6px 0; }}
  footer {{ margin-top: 40px; text-align: center; color: var(--muted); font-size: 13px; }}
  a {{ color: var(--gold); }}
</style>
</head>
<body>
<svg class="icons" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
  <symbol id="i-play" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></symbol>
  <symbol id="i-pause" viewBox="0 0 24 24"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></symbol>
  <symbol id="i-prev" viewBox="0 0 24 24"><path d="M18 5h-2v14h2zM6 5v14l9-7z"/></symbol>
  <symbol id="i-next" viewBox="0 0 24 24"><path d="M6 5h2v14H6zm12 0v14l-9-7z"/></symbol>
  <symbol id="i-back" viewBox="0 0 24 24"><path d="M11.5 8c2.65 0 5.05.99 6.9 2.6L22 7v9h-9l3.62-3.62c-1.39-1.16-3.16-1.88-5.12-1.88-3.54 0-6.55 2.31-7.6 5.5l-2.37-.78C2.92 11.03 6.85 8 11.5 8z"/></symbol>
  <symbol id="i-fwd" viewBox="0 0 24 24"><path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/></symbol>
  <symbol id="i-download" viewBox="0 0 24 24"><path d="M11 4h2v9.2l3.1-3.1 1.4 1.4L12 17l-5.5-5.5 1.4-1.4L11 13.2z"/><path d="M5 19h14v2H5z"/></symbol>
  <symbol id="i-close" viewBox="0 0 24 24"><path d="M6.4 5 12 10.6 17.6 5 19 6.4 13.4 12 19 17.6 17.6 19 12 13.4 6.4 19 5 17.6 10.6 12 5 6.4z"/></symbol>
</svg>
<main>
  <header>
    <div class="kicker">أرشيف صوتي · ٢٠٢٦</div>
    <h1>الراوي فواز الغسلان</h1>
    <p>{tagline}</p>
  </header>

  <div class="shows">
{cards}
  </div>

{listen}

  <h2 style="margin:44px 0 10px;font-size:20px">كيف تستمع؟</h2>
  <ol>
    <li>من هذه الصفحة: اختر سلسلة ثم حلقة من قسم <a href="#listen">استمع الآن</a>، وسيعمل المشغّل مباشرة. يمكنك البحث في العناوين والتنقل بين الحلقات ومتابعة الاستماع من حيث توقفت.</li>
    <li>للاشتراك في تطبيق بودكاست: انسخ رابط الاشتراك (Feed URL) من البطاقة أعلاه.</li>
    <li>في تطبيق البودكاست اختر «إضافة بودكاست عبر رابط» أو «Add by URL» والصق الرابط: Podcast Addict، Overcast، Pocket Casts، AntennaPod، Castro، Podverse…</li>
    <li>على iPhone افتح <a href="{apple}">Apple Podcasts</a> مباشرة، أو ابحث في التطبيق عن «أرشيف الراوي فواز الغسلان».</li>
    <li>تحميل الملفات كاملةً (بدون بودكاست): <a href="https://github.com/{repo}/releases/latest">صفحة الإصدارات</a>.</li>
  </ol>

  <footer>
    الحقوق تعود للراوي فواز الغسلان وللقنوات الناشرة. هذا الأرشيف للحفظ والاستماع الشخصي غير التجاري.<br>
    <a href="https://github.com/{repo}">github.com/{repo}</a> · {english}
  </footer>
</main>
{player}
</body>
</html>
"""


def show_card(show: Show) -> str:
    total = sum(ep.duration for ep in show.episodes)
    count = f"{arabic_number(len(show.episodes))} حلقة"
    if show.key == "kasayet":
        count = f"{arabic_number(len(show.episodes))} كاسيت"
    seasons = (
        "سلسلة واحدة"
        if len(show.seasons) == 1
        else f"{arabic_number(len(show.seasons))} سلاسل"
    )
    return f"""    <section class="show">
      <img src="{show.cover}" alt="{esc(show.title)}">
      <h2>{esc(show.title)}</h2>
      <p>{esc(show.summary)}</p>
      <div class="meta">{count} · {human(total)} · {seasons}</div>
      <a class="button listen-jump" href="#listen" data-listen="{show.key}"><svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#i-play"/></svg>استمع على الموقع</a>
      <div class="feed">
        <code id="feed-{show.key}">{esc(show.feed_url)}</code>
        <button type="button" onclick="copyFeed('{show.key}', this)">انسخ الرابط</button>
      </div>
      <div class="feed">
        <a class="button apple" href="{quote(show.apple, safe=":/")}">Apple Podcasts</a>
        <a class="button secondary" href="https://podcastaddict.com/feed/{quote(show.feed_url, safe="")}">Podcast Addict</a>
        <a class="button secondary" href="overcast://x-callback-url/add?url={quote(show.feed_url, safe="")}">Overcast</a>
        <a class="button secondary" href="pocketcasts://subscribe/{show.feed_url}">Pocket Casts</a>
        <a class="button secondary" href="{esc(show.feed_url)}">RSS</a>
      </div>
    </section>"""


COPY_JS = """<script>
function copyFeed(key, button) {
  const text = document.getElementById('feed-' + key).textContent;
  navigator.clipboard.writeText(text).then(function () {
    const old = button.textContent;
    button.textContent = 'تم النسخ';
    setTimeout(function () { button.textContent = old; }, 1500);
  });
}
</script>"""


PLAYER_JS = r"""<script>
(function () {
  'use strict';

  var audio = document.getElementById('p-audio');
  if (!audio) return;

  var player = document.getElementById('player');
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tabs [role="tab"]'));
  var links = Array.prototype.slice.call(document.querySelectorAll('a.ep'));
  var titleEl = document.getElementById('p-title');
  var subEl = document.getElementById('p-sub');
  var coverEl = document.getElementById('p-cover');
  var toggleBtn = document.getElementById('p-toggle');
  var toggleUse = toggleBtn.querySelector('use');
  var range = document.getElementById('p-range');
  var curEl = document.getElementById('p-cur');
  var durEl = document.getElementById('p-dur');
  var rateEl = document.getElementById('p-rate');
  var downloadEl = document.getElementById('p-download');
  var closeBtn = document.getElementById('p-close');

  var AR = '٠١٢٣٤٥٦٧٨٩';
  var POS_KEY = 'alrawie:positions';
  var RATE_KEY = 'alrawie:rate';
  var RATES = [1, 1.25, 1.5, 1.75, 2];

  var currentLink = null;
  var currentInfo = null;
  var resumeAt = 0;
  var dragging = false;
  var lastSave = 0;
  var rate = 1;

  function arabic(value) {
    return String(value).replace(/[0-9]/g, function (digit) {
      return AR.charAt(Number(digit));
    });
  }

  function clock(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0;
    seconds = Math.floor(seconds);
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var secs = seconds % 60;
    var text = hours
      ? hours + ':' + ('0' + minutes).slice(-2) + ':' + ('0' + secs).slice(-2)
      : minutes + ':' + ('0' + secs).slice(-2);
    return arabic(text);
  }

  function readPositions() {
    try {
      return JSON.parse(localStorage.getItem(POS_KEY)) || {};
    } catch (error) {
      return {};
    }
  }

  function writePositions(value) {
    try {
      localStorage.setItem(POS_KEY, JSON.stringify(value));
    } catch (error) {}
  }

  function savePosition() {
    if (!currentInfo || !audio.duration) return;
    var store = readPositions();
    if (audio.currentTime > 3 && audio.duration - audio.currentTime > 5) {
      store[currentInfo.id] = Math.round(audio.currentTime);
    } else {
      delete store[currentInfo.id];
    }
    writePositions(store);
  }

  function setToggle(playing) {
    toggleUse.setAttribute('href', playing ? '#i-pause' : '#i-play');
    toggleBtn.setAttribute('aria-label', playing ? 'إيقاف مؤقت' : 'تشغيل');
  }

  function markPlaying(link) {
    links.forEach(function (item) {
      item.classList.remove('playing');
      item.removeAttribute('aria-current');
    });
    if (link) {
      link.classList.add('playing');
      link.setAttribute('aria-current', 'true');
    }
  }

  function panelFor(link) {
    return link.closest('.panel');
  }

  function infoFor(link) {
    var panel = panelFor(link);
    return {
      id: link.dataset.id,
      title: link.dataset.title,
      series: link.dataset.series,
      number: Number(link.dataset.number),
      duration: Number(link.dataset.duration),
      url: link.href,
      cover: panel.dataset.cover,
      showTitle: panel.dataset.title,
      cassette: panel.dataset.key === 'kasayet'
    };
  }

  function subtitle(info) {
    if (info.cassette) return info.series + ' ' + arabic(info.number);
    return info.series + ' · الحلقة ' + arabic(info.number);
  }

  function setMediaSession(info) {
    if (!('mediaSession' in navigator)) return;
    try {
      if (typeof MediaMetadata === 'function') {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: info.title,
          artist: info.showTitle,
          album: info.series,
          artwork: [{
            src: new URL(info.cover, location.href).href,
            sizes: '3000x3000',
            type: 'image/jpeg'
          }]
        });
      }
    } catch (error) {}
  }

  function updatePositionState() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState) return;
    if (!isFinite(audio.duration) || audio.duration <= 0) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: audio.duration,
        playbackRate: audio.playbackRate,
        position: Math.min(audio.currentTime, audio.duration)
      });
    } catch (error) {}
  }

  function load(link, autoplay) {
    if (currentLink === link && currentInfo) {
      if (audio.paused) {
        audio.play().catch(function () {});
      } else {
        audio.pause();
      }
      return;
    }

    savePosition();
    var info = infoFor(link);
    var saved = readPositions()[info.id] || 0;

    currentLink = link;
    currentInfo = info;
    resumeAt = saved > 4 ? saved : 0;

    audio.src = info.url;
    audio.playbackRate = rate;
    titleEl.textContent = info.title;
    subEl.textContent = subtitle(info);
    coverEl.src = info.cover;
    coverEl.alt = info.showTitle;
    downloadEl.href = info.url;
    durEl.textContent = clock(info.duration);
    curEl.textContent = clock(0);
    range.value = '0';
    player.hidden = false;
    document.body.classList.add('has-player');
    markPlaying(link);
    setMediaSession(info);

    try {
      history.replaceState(null, '', '#ep-' + info.id);
    } catch (error) {}

    if (autoplay) {
      audio.play().catch(function () { setToggle(false); });
    }
  }

  function playlist(link) {
    return Array.prototype.slice.call(
      panelFor(link).querySelectorAll('a.ep')
    ).filter(function (item) {
      return !item.parentNode.hidden;
    });
  }

  function step(delta, reveal) {
    if (!currentLink) return;
    var list = playlist(currentLink);
    var next = list[list.indexOf(currentLink) + delta];
    if (!next) return;
    var season = next.closest('details');
    if (season) season.open = true;
    load(next, true);
    if (reveal) next.scrollIntoView({ block: 'nearest' });
  }

  function seekBy(delta) {
    if (!currentInfo) return;
    var duration = audio.duration || currentInfo.duration;
    var target = Math.max(0, Math.min(duration - 0.25, audio.currentTime + delta));
    audio.currentTime = target;
    range.value = String(Math.round((target / duration) * 1000));
    curEl.textContent = clock(target);
  }

  audio.addEventListener('loadedmetadata', function () {
    audio.playbackRate = rate;
    durEl.textContent = clock(audio.duration);
    if (resumeAt && resumeAt < audio.duration - 8) {
      audio.currentTime = resumeAt;
    }
    resumeAt = 0;
    updatePositionState();
  });

  audio.addEventListener('timeupdate', function () {
    if (!dragging && audio.duration) {
      range.value = String(Math.round((audio.currentTime / audio.duration) * 1000));
      curEl.textContent = clock(audio.currentTime);
    }
    if (Date.now() - lastSave > 5000) {
      lastSave = Date.now();
      savePosition();
    }
    updatePositionState();
  });

  audio.addEventListener('play', function () { setToggle(true); });

  audio.addEventListener('playing', function () {
    if (currentInfo) subEl.textContent = subtitle(currentInfo);
    setToggle(true);
  });

  audio.addEventListener('pause', function () {
    setToggle(false);
    savePosition();
    updatePositionState();
  });

  audio.addEventListener('seeked', updatePositionState);

  audio.addEventListener('waiting', function () {
    subEl.textContent = 'جارٍ التحميل…';
  });

  audio.addEventListener('error', function () {
    if (!currentInfo || !audio.error || audio.error.code === 1) return;
    subEl.textContent = 'تعذّر تشغيل الملف — استخدم زر التحميل.';
    setToggle(false);
  });

  audio.addEventListener('ended', function () {
    savePosition();
    var list = currentLink ? playlist(currentLink) : [];
    var next = currentLink ? list[list.indexOf(currentLink) + 1] : null;
    if (next) {
      load(next, true);
    } else {
      setToggle(false);
    }
  });

  range.addEventListener('input', function () {
    dragging = true;
    if (audio.duration) {
      curEl.textContent = clock((Number(range.value) / 1000) * audio.duration);
    }
  });

  range.addEventListener('change', function () {
    if (audio.duration) {
      audio.currentTime = (Number(range.value) / 1000) * audio.duration;
    }
    dragging = false;
  });

  toggleBtn.addEventListener('click', function () {
    if (!currentLink) return;
    if (audio.paused) {
      audio.play().catch(function () {});
    } else {
      audio.pause();
    }
  });

  document.getElementById('p-prev').addEventListener('click', function () { step(-1, true); });
  document.getElementById('p-next').addEventListener('click', function () { step(1, true); });
  document.getElementById('p-back').addEventListener('click', function () { seekBy(-15); });
  document.getElementById('p-fwd').addEventListener('click', function () { seekBy(30); });

  rateEl.addEventListener('change', function () {
    rate = Number(rateEl.value) || 1;
    audio.playbackRate = rate;
    updatePositionState();
    try {
      localStorage.setItem(RATE_KEY, String(rate));
    } catch (error) {}
  });

  closeBtn.addEventListener('click', function () {
    savePosition();
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    currentLink = null;
    currentInfo = null;
    player.hidden = true;
    document.body.classList.remove('has-player');
    markPlaying(null);
    try {
      history.replaceState(null, '', location.pathname + location.search);
    } catch (error) {}
  });

  function activate(key) {
    tabs.forEach(function (tab) {
      var active = tab.dataset.key === key;
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.key !== key;
    });
  }

  tabs.forEach(function (tab, index) {
    tab.addEventListener('click', function () { activate(tab.dataset.key); });
    tab.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      var delta = event.key === 'ArrowLeft' ? 1 : -1;
      var nextTab = tabs[(index + delta + tabs.length) % tabs.length];
      activate(nextTab.dataset.key);
      nextTab.focus();
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-listen]'), function (link) {
    link.addEventListener('click', function () { activate(link.dataset.listen); });
  });

  function fold(text) {
    return String(text)
      .normalize('NFKC')
      .replace(/[\u064B-\u0652\u0670\u0640]/g, '')
      .replace(/[إأآٱ]/g, 'ا')
      .replace(/ى/g, 'ي')
      .replace(/ة/g, 'ه')
      .replace(/ؤ/g, 'و')
      .replace(/ئ/g, 'ي')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function filterPanel(panel, query) {
    var needle = fold(query);
    var any = false;
    var seasons = Array.prototype.slice.call(panel.querySelectorAll('details.season'));

    seasons.forEach(function (season) {
      var matches = 0;
      Array.prototype.forEach.call(season.querySelectorAll('a.ep'), function (link) {
        var hit = !needle || fold(link.dataset.title).indexOf(needle) !== -1;
        link.parentNode.hidden = !hit;
        if (hit) matches += 1;
      });

      if (needle) {
        if (!('userOpen' in season.dataset)) {
          season.dataset.userOpen = season.open ? '1' : '0';
        }
        season.hidden = matches === 0;
        season.open = matches > 0;
        if (matches) any = true;
      } else {
        season.hidden = false;
        if ('userOpen' in season.dataset) {
          season.open = season.dataset.userOpen === '1';
          delete season.dataset.userOpen;
        }
      }
    });

    var empty = panel.querySelector('.no-results');
    if (empty) empty.hidden = !needle || any;
  }

  panels.forEach(function (panel) {
    var input = panel.querySelector('.search input');
    if (!input) return;
    input.addEventListener('input', function () {
      filterPanel(panel, input.value);
    });
  });

  links.forEach(function (link) {
    link.addEventListener('click', function (event) {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      load(link, true);
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.code !== 'Space' || event.metaKey || event.ctrlKey || event.altKey) return;
    var tag = (event.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'select' || tag === 'textarea' ||
        tag === 'button' || tag === 'a' || event.target.isContentEditable) return;
    if (!currentLink) return;
    event.preventDefault();
    if (audio.paused) {
      audio.play().catch(function () {});
    } else {
      audio.pause();
    }
  });

  if ('mediaSession' in navigator && navigator.mediaSession.setActionHandler) {
    var actions = {
      play: function () { audio.play().catch(function () {}); },
      pause: function () { audio.pause(); },
      seekbackward: function (details) {
        seekBy(-(details && details.seekOffset ? details.seekOffset : 15));
      },
      seekforward: function (details) {
        seekBy(details && details.seekOffset ? details.seekOffset : 30);
      },
      previoustrack: function () { step(-1, false); },
      nexttrack: function () { step(1, false); },
      seekto: function (details) {
        if (details && typeof details.seekTime === 'number') {
          audio.currentTime = details.seekTime;
        }
      }
    };
    Object.keys(actions).forEach(function (name) {
      try {
        navigator.mediaSession.setActionHandler(name, actions[name]);
      } catch (error) {}
    });
  }

  window.addEventListener('pagehide', function () { savePosition(); });

  try {
    var storedRate = Number(localStorage.getItem(RATE_KEY));
    if (RATES.indexOf(storedRate) !== -1) rate = storedRate;
  } catch (error) {}
  rateEl.value = String(rate);

  function loadFromHash() {
    var hash = /^#ep-([A-Za-z0-9_-]{11})$/.exec(location.hash);
    if (!hash) return;
    var linked = document.querySelector('a.ep[data-id="' + hash[1] + '"]');
    if (!linked) return;
    activate(panelFor(linked).dataset.key);
    var season = linked.closest('details');
    if (season) season.open = true;
    if (currentLink !== linked) load(linked, false);
    linked.scrollIntoView({ block: 'center' });
  }

  window.addEventListener('hashchange', loadFromHash);
  activate('main');
  loadFromHash();
})();
</script>"""


def landing(shows: list[Show]) -> str:
    cards = "\n".join(show_card(show) for show in shows)
    return PAGE.format(
        title="الراوي فواز الغسلان — بودكاست",
        tagline="قصص وقصائد وأمثال من التراث العربي، بصوت الراوي فواز الغسلان.",
        cards=cards,
        listen=listen_section(shows),
        player=PLAYER_HTML,
        repo=REPO,
        apple=quote(shows[0].apple, safe=":/"),
        english="Arabic poetry and folk tales podcast",
    ).replace("</body>", COPY_JS + "\n" + PLAYER_JS + "\n</body>")


# --------------------------------------------------------------------------


def main() -> int:
    shows = build_shows()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "kasayet").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    for show in shows:
        path = DOCS / show.feed_rel
        path.write_text(feed_xml(show), encoding="utf-8")
        hours = sum(ep.duration for ep in show.episodes) / 3600
        print(
            f"{path.relative_to(ROOT)}: {len(show.episodes)} episodes, "
            f"{hours:.1f} h, {path.stat().st_size / 1024:.0f} KiB"
        )

    (DOCS / "index.html").write_text(landing(shows), encoding="utf-8")
    print(f"{(DOCS / 'index.html').relative_to(ROOT)}: landing page")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FeedError as error:
        raise SystemExit(f"error: {error}") from None
