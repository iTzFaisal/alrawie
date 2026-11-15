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
OWNER_EMAIL = "iTzFaisal@users.noreply.github.com"

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
# landing page

PAGE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --ink: #1b1712; --muted: #6d6254; --line: #e4dbcb;
    --sand: #f7f2e8; --gold: #a8791f; --card: #fffdf8;
  }}
  * {{ box-sizing: border-box; }}
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
  .shows {{ display: grid; gap: 22px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
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
  }}
  button.secondary, .button.secondary {{ background: transparent; color: var(--gold); }}
  .meta {{ font-size: 13px; color: var(--muted); }}
  ol {{ padding-inline-start: 20px; color: var(--muted); font-size: 15px; }}
  ol li {{ margin: 6px 0; }}
  footer {{ margin-top: 40px; text-align: center; color: var(--muted); font-size: 13px; }}
  a {{ color: var(--gold); }}
</style>
</head>
<body>
<main>
  <header>
    <div class="kicker">أرشيف صوتي · ٢٠٢٦</div>
    <h1>الراوي فواز الغسلان</h1>
    <p>{tagline}</p>
  </header>

  <div class="shows">
{cards}
  </div>

  <h2 style="margin:44px 0 10px;font-size:20px">كيف تشترك؟</h2>
  <ol>
    <li>انسخ رابط الاشتراك (Feed URL) من البطاقة أعلاه.</li>
    <li>في تطبيق البودكاست اختر «إضافة بودكاست عبر رابط» أو «Add by URL» والصق الرابط: Overcast، Pocket Casts، AntennaPod، Castro، Podverse…</li>
    <li>للاستظهار في دليل Apple Podcasts أو غيره، أرسل نفس الرابط مرة واحدة إلى <a href="https://podcastsconnect.apple.com/">Podcasts Connect</a>.</li>
    <li>تحميل الملفات كاملةً (بدون بودكاست): <a href="https://github.com/{repo}/releases/latest">صفحة الإصدارات</a>.</li>
  </ol>

  <footer>
    الحقوق تعود للراوي فواز الغسلان وللقنوات الناشرة. هذا الأرشيف للحفظ والاستماع الشخصي غير التجاري.<br>
    <a href="https://github.com/{repo}">github.com/{repo}</a> · {english}
  </footer>
</main>
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
      <div class="feed">
        <code id="feed-{show.key}">{esc(show.feed_url)}</code>
        <button type="button" onclick="copyFeed('{show.key}', this)">انسخ الرابط</button>
      </div>
      <div class="feed">
        <a class="button secondary" href="overcast://x-callback-url/add?url={quote(show.feed_url, safe="")}">Overcast</a>
        <a class="button secondary" href="pocketcasts://subscribe/{show.feed_url}">Pocket Casts</a>
        <a class="button secondary" href="{esc(show.feed_url)}">RSS</a>
      </div>
    </section>"""


def landing(shows: list[Show]) -> str:
    cards = "\n".join(show_card(show) for show in shows)
    return PAGE.format(
        title="الراوي فواز الغسلان — بودكاست",
        tagline="قصص وقصائد وأمثال من التراث العربي، بصوت الراوي فواز الغسلان.",
        cards=cards,
        repo=REPO,
        english="Arabic poetry and folk tales podcast",
    ).replace(
        "</body>",
        """<script>
function copyFeed(key, button) {
  const text = document.getElementById('feed-' + key).textContent;
  navigator.clipboard.writeText(text).then(function () {
    const old = button.textContent;
    button.textContent = 'تم النسخ';
    setTimeout(function () { button.textContent = old; }, 1500);
  });
}
</script>
</body>""",
    )


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
