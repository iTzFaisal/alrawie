# الراوي فواز الغسلان — audio archive

[![GitHub](https://img.shields.io/badge/GitHub-iTzFaisal%2Falrawie-181717?logo=github)](https://github.com/iTzFaisal/alrawie)
[![Download](https://img.shields.io/badge/Download-GitHub%20Releases-2ea44f?logo=github)](https://github.com/iTzFaisal/alrawie/releases/latest)
[![Podcast](https://img.shields.io/badge/Podcast-RSS%20feed-a8791f?logo=rss)](https://itzfaisal.github.io/alrawie/feed.xml)

A preservation archive of **فواز الغسلان** recordings recovered from the
surviving mirror channel **صدى نجد دوت كوم** (`@alraawy_2`).

The original channel **@alrawie8** (`UCw5-fa9GQo2bml9VVPKOM6Q`) is deleted and
all of its original video IDs return HTTP 404. This project reconstructs the
Ghasslan part of that catalog from third-party reuploads and keeps it as
**audio-only M4A files**.

> **The audio is not stored in this Git repository.** The archive is about
> 2 GB, so the audio ships as GitHub Release assets: grab the per-series zips
> below, or clone the repo and run the downloader.

## Quick start

```bash
git clone https://github.com/iTzFaisal/alrawie.git
cd alrawie

./download.sh                # 207 main audio files
./download_supplements.sh    # 4 gap-filler audio files
python3 verify.py            # check coverage
```

Expected verification output:

```text
downloaded: 207/207
size: 1.86 GB
source runtime covered: 33.3 hours
supplements: 4/4 (36 MB)
```

The order of the two download commands does not matter. Re-running either
script skips files that already exist, so downloads are resumable.

If you only want the audio, skip all of this and go to
**[Download](#download)**.

## Download

All audio is published on the
**[Releases page](https://github.com/iTzFaisal/alrawie/releases/latest)** — no
scripts needed, each series is a ready-to-extract zip. The current snapshot is
[`archive-2026-11-15`](https://github.com/iTzFaisal/alrawie/releases/tag/archive-2026-11-15):
11 archives with 211 files (1.89 GB) plus `SHA256SUMS.txt`.

```bash
gh release download archive-2026-11-15 --repo iTzFaisal/alrawie
shasum -a 256 -c SHA256SUMS.txt
for z in *.zip; do unzip -q "$z" -d audios; done
```

Asset names are Latin slugs because GitHub strips non-ASCII characters from
release filenames. Each zip keeps the original Arabic folder as its top level,
so extracting under `audios/` reproduces this repository's layout exactly; the
[folder table](#series-folders) maps every slug to its series.

## Podcast

The archive is also published as two podcast feeds, served from GitHub Pages.
Every episode is its own release asset, because podcast apps need one stable
URL per episode and cannot open a zip.

| Show | Episodes | Runtime | Subscribe |
| --- | ---: | ---: | --- |
| أرشيف الراوي فواز الغسلان | 199 | 18.1 h | <https://itzfaisal.github.io/alrawie/feed.xml> |
| الكاسيتات الكاملة | 12 | 14.5 h | <https://itzfaisal.github.io/alrawie/kasayet/feed.xml> |

- **Main show** — the 195 individual episodes plus the 4 gap-fillers, grouped
  into 10 seasons (`itunes:season`) that follow the series folders.
- **Cassettes** — the 12 full-cassette uploads in a separate show, so the main
  feed does not duplicate the material the episodes were cut from.
- Both feeds use the original YouTube upload date only inside the description.
  Publication dates are assigned in curated order (`BASE_DATE` in
  `podcast/build_feed.py`) so the list reads like a table of contents instead of
  a jumble of mirror-upload timestamps.
- 7 uploads in `القصائد المتداخلة` have no title of their own in the source and
  are numbered `القصائد المتداخلة — القسم 1…7`; two `مساجله شعريه` uploads get
  the same suffix. Renaming the catalog row and rebuilding renames the episode.

Both shows are listed in Apple Podcasts:

- أرشيف الراوي فواز الغسلان — <https://podcasts.apple.com/us/podcast/id6835240326>
- الكاسيتات الكاملة — <https://podcasts.apple.com/us/podcast/id6835240746>

The landing page also links Podcast Addict, Overcast and Pocket Casts. The
Podcast Addict button uses `podcastaddict.com/feed/<encoded feed>`, which starts
working once the feed is indexed there — submit it once at
<https://podcastaddict.com/submit> (indexing can take up to 24 hours).

The landing page has an on-page player as well: browse either show by season,
search the Arabic titles, and listen in the sticky player without subscribing.
It streams from the same per-series release assets, so no audio is stored in
the repository or on GitHub Pages. Playback position and speed are remembered
in the browser, and the playing episode is mirrored in the URL as
`#ep-<video-id>` so a link can be shared.

To listen without a directory, paste a feed URL into any app that supports
"Add by URL".

```bash
python3 podcast/build_feed.py        # regenerate both feeds and the player page
python3 podcast/validate_feed.py     # tags, sizes, GUIDs, titles, player rows; --urls checks links
python3 podcast/publish_podcast.py --dry-run   # what still needs uploading
python3 podcast/publish_podcast.py   # resumable: skips assets already present
swift podcast/make_covers.swift      # redraw both 3000x3000 covers
```

`publish_podcast.py` creates one release per series (`audio-<slug>`, matching
the zip slug) and uploads `<video-id>.m4a` files into it. Re-running is safe.
The feed URLs, asset URLs and GUIDs are permanent API: renaming the repository,
retagging a release, or deleting and re-uploading an asset breaks every
subscriber, so treat those names as frozen.

## What you get

| Item                   |   Count |        Size |                 Runtime |
| ---------------------- | ------: | ----------: | ----------------------: |
| Main channel uploads   |     207 |     1.86 GB |                  31.9 h |
| Gap-filler supplements |       4 |       36 MB |                   0.6 h |
| **Total**              | **211** | **1.89 GB** | **32.5 h actual audio** |

The catalog still records the source durations (33.9 h); the difference is the
1.4 h of trailing silence removed on 2026-11-21.

- **207/207** mirror-channel uploads whose titles name فواز الغسلان.
- 195 individual episodes and 12 full-cassette uploads.
- Organized into one folder per series under `audios/<series>/`. The 12 full
  cassettes are collected separately in `audios/كاسيت/`.
- Audio format: **M4A / AAC**, ~128 kbps, stream-copied from the source with no
  re-encode.
- No video is downloaded — every file is audio-only.
- The snapshot was completed on **2026-11-15**.

## Series folders

Each audio file is placed in the folder for its series:

| Folder                  | Files | Release asset                 |
| ----------------------- | ----: | ----------------------------- |
| `الموسوعة الشعرية`      |    54 | `mawsuat-sheriya.zip`         |
| `نوادر من التراث`       |    47 | `nawader-min-alturath.zip`    |
| `جواهر الأمثال الشعبية` |    37 | `jawaher-amthal-shaabiya.zip` |
| `عاشق ومعشوق`           |    22 | `asheq-wamaashuq.zip`         |
| `ضحايا العشق`           |    16 | `dahaya-aleshq.zip`           |
| `كاسيت`                 |    12 | `kasayet.zip`                 |
| `القصائد المتداخلة`     |     9 | `qasaid-mutadakhila.zip`      |
| `فنجال الكيف`           |     6 | `finjal-alkayf.zip`           |
| `مكملات`                |     4 | `mukammilat.zip`              |
| `أخرى`                  |     3 | `okhra.zip`                   |
| `موسوعة التاريخ والأدب` |     1 | `mawsuat-tarikh-wa-adab.zip`  |

`أخرى` is the catch-all for the few uploads whose titles do not name a series.
`كاسيت` holds the 12 full-cassette uploads, which are the complete tapes the
individual episodes were cut from; their catalog `series` is `كاسيت` even
though each cassette's title names its original series. The `series` value is
stored in `catalog/ghasslan_mirrors.csv`, so the downloader and organizer use
the same mapping.

Two series exist only as cassettes, so after the tapes were collected into
`كاسيت` their folders hold no separate episodes: **مفاخر العرب** and
**نوادر شعرية**. Their recordings are inside `kasayet.zip`.

## Requirements

- `python3` 3.10 or newer
- [`uv`](https://docs.astral.sh/uv/)
- `ffmpeg` on `PATH`
- Internet access to YouTube
- About **2.1 GB** of free disk space

`yt-dlp` does not need to be installed globally: the scripts run the latest
version through `uvx --from yt-dlp yt-dlp`.

## Repository layout

```text
.
├── audios/                     # 207 M4A files, grouped by series (gitignored)
│   ├── الموسوعة الشعرية/
│   ├── نوادر من التراث/
│   ├── جواهر الأمثال الشعبية/
│   ├── عاشق ومعشوق/
│   ├── ضحايا العشق/
│   ├── كاسيت/                  # 12 full-cassette uploads
│   ├── القصائد المتداخلة/
│   ├── فنجال الكيف/
│   ├── مفاخر العرب/            # empty: its only upload is a cassette
│   ├── موسوعة التاريخ والأدب/
│   ├── نوادر شعرية/            # empty: its only upload is a cassette
│   ├── أخرى/
│   └── مكملات/                 # 4 extra M4A files (gitignored)
├── metadata/                   # yt-dlp .info.json sidecars (gitignored)
│   └── مكملات/
├── catalog/
│   ├── ghasslan_mirrors.csv    # main 207-upload manifest
│   └── supplements.csv         # 4 gap-filler manifest
├── state/                      # yt-dlp bookkeeping (gitignored)
├── logs/                       # download logs (gitignored)
├── dist/release/               # generated release zips (gitignored)
├── download.sh                 # parallel audio downloader
├── download_supplements.sh     # downloads the 4 gap-fillers
├── download_sequential.sh      # single-queue fallback
├── organize.py                 # moves new audio into series folders + sidecars
├── verify.py                   # coverage/size report
├── make_zips.py                # one zip per series folder + SHA256SUMS.txt
├── release.sh                  # uploads the zips to a GitHub release
├── RELEASE_NOTES.md            # release page text
├── convert_to_audio.py         # optional MP4 -> M4A converter
├── README.md
└── .gitignore
```

After a fresh clone, the `audios/` series folders and `metadata/` contain only
`.gitkeep` files. The audio and metadata are intentionally excluded from Git.

## Downloading with the scripts

### Main archive

```bash
./download.sh
```

Downloads the 207 main uploads and runs `organize.py`, which places each file
in `audios/<series>/` — or `audios/كاسيت/` for the 12 full cassettes. It uses 8
parallel workers by default because YouTube throttles each connection
individually:

```bash
WORKERS=12 ./download.sh     # more concurrency
WORKERS=4 ./download.sh      # gentler on the connection
```

You can also run the single-queue fallback:

```bash
./download_sequential.sh
```

The fallback uses `state/downloads_audio.txt` and is useful when parallel
workers trigger rate limits.

### Supplements

```bash
./download_supplements.sh
```

Downloads the 4 gap-filler recordings to `audios/مكملات/`. They come from
other channels: two cover original alrawie8 videos that have no direct mirror on
`@alraawy_2`, and two are alternate copies of the coffee episode.

### Verify

```bash
python3 verify.py
```

This checks every manifest row against the files on disk (including series
folders), prints coverage, total size, and runtime, and writes
`catalog/download_report.csv` (gitignored).

## Rebuilding the release zips

```bash
./release.sh              # build, upload to a draft release, verify sizes
./release.sh --publish    # flip the verified draft to public
```

`make_zips.py` stores files uncompressed (M4A does not shrink), writes UTF-8
filenames so Arabic extracts correctly everywhere, and only rebuilds archives
whose sources or entry list changed (`--force` rebuilds all). Uploads are
resumable: assets whose size already matches are skipped, and `release.sh`
refuses to publish if any local archive is missing or differs in size. Requires
an authenticated [`gh`](https://cli.github.com) CLI.

## Catalog files

Only two files are needed to rebuild the archive:

| File                           | Used by                                   | Contents                                                            |
| ------------------------------ | ----------------------------------------- | ------------------------------------------------------------------- |
| `catalog/ghasslan_mirrors.csv` | `download.sh`, `organize.py`, `verify.py` | 207 rows: `video_id,title,series,duration_seconds,channel,url`      |
| `catalog/supplements.csv`      | `download_supplements.sh`, `verify.py`    | 4 rows: `video_id,title,replaces_original,duration_seconds,channel` |

There is **no overlap** between the two manifests. All 207 channel uploads,
including `hR-LkMcljDk`, live in `audios/`; the 4 supplements are separate
files from other channels.

The manifests are frozen snapshots. New uploads made on the source channel
after the snapshot date are not included.

## What is in the archive

The mirror titles follow the same series naming as alrawie8's uploads:

- **نوادر من التراث**
- **الموسوعة الشعرية**
- **جواهر الأمثال الشعبية**
- **عاشق ومعشوق**
- **ضحايا العشق**
- **فنجال الكيف / قوانين القهوة**
- **القصائد المتداخلة**
- **مفاخر العرب**

The original channel also hosted other narrators (محمد الشرهان,
منيف الشويب, عبدالرحمن المرشدي, …). This archive covers **فواز الغسلان only**.

## Background

The original blog `alrawie8.com` and channel `@alrawie8` are gone. Research
using Wayback Machine captures recovered 13 original video IDs and titles, but
every original YouTube ID returns 404. The surviving recordings are reuploads
on **صدى نجد دوت كوم** (`@alraawy_2`,
`UCmiS1tzQ7melN6GHhUbCgcQ`), which is the source for this archive.

The mirror channel had 661 public uploads at snapshot time; **207** of them
name فواز الغسلان. All 207 are included here, plus 4 supplement recordings
from other channels.

## Trailing silence

Short recordings were padded with digital silence to a **3-minute minimum**
before upload. The channel owner confirmed this is by design, not a fault, so
a clip could run 3:02 while only half of it carried sound. Sixteen of these
files also broke off early: a brief (~1.2 s) fragment near **1:46**, then
silence to the end.

On **2026-11-21** the 76 files with at least 10 seconds of trailing silence
were trimmed with a stream copy (no re-encode), keeping one second of tail and
removing the orphan fragment from the 16 affected files. That removed about
1.4 hours in total and rebuilt the six affected zips. The catalog keeps the
source durations; `catalog/trailing_silence.csv` records the original silence,
the cut point and the applied duration for every file.

`k7g61lkLMUw` is one of them: its sound stopped at about **1:13**, and the
file is now 1:14 instead of 3:02.

This is **not** a corrupted local download. Re-downloading the affected IDs
from YouTube still produces the padded originals, so do not re-download or
"repair" them: that would restore the silence. The podcast feeds and the
archive zips now serve the trimmed files.

## Important limits

- **The original uploads are not recoverable.** YouTube does not serve deleted
  videos, and no web archive stores the original media streams. Everything here
  is a reupload of the same content, not the original file.
- Coverage is based on title matching. Some episodes may also exist inside the
  full-cassette uploads, so the number of files is larger than the number of
  unique recordings.
- The source channel can remove or change uploads at any time. The manifests
  are a snapshot, not a live mirror.
- Rights remain with the narrator and creators. This is a personal preservation
  archive; do not redistribute it commercially.

## Troubleshooting

**A download fails with HTTP 403 or “Sign in to confirm you’re not a bot”**

YouTube changes its checks frequently. Refresh yt-dlp and retry:

```bash
uvx --refresh --from yt-dlp yt-dlp --version
./download.sh
```

**A download is slow or stalls**

Reduce concurrency:

```bash
WORKERS=4 ./download.sh
```

or use the single-queue fallback:

```bash
./download_sequential.sh
```

**A download was interrupted**

Just run the same command again. Existing `.m4a` files are skipped, and
`.part` files are resumed or replaced.

**A file downloaded as `.webm` or `.opus` instead of `.m4a`**

The scripts prefer M4A but fall back to the best audio-only stream. Convert it
to M4A (this re-encodes the audio):

```bash
ffmpeg -i "input.webm" -vn -c:a aac -b:a 128k "output.m4a"
```

`verify.py` currently expects `.m4a` filenames, so convert before verifying.

**I want the files without running scripts**

Use the [release zips](#download) — every series is published as a
ready-to-extract archive with checksums.

## Safe to delete

These are regenerable or disposable:

- `logs/` — download logs
- `dist/` — generated release zips, rebuilt by `make_zips.py`
- `catalog/download_report.csv` — regenerated by `verify.py`
- `catalog/urls.txt`, `catalog/chunk_*.txt`, `catalog/remaining_audio.txt` —
  generated by the downloaders
- `state/` — yt-dlp bookkeeping; safe once the archive is complete
- `__pycache__/`, `*.pyc`, `.DS_Store` — OS/Python noise
- `download_sequential.sh` and `convert_to_audio.py` — optional fallbacks

**Do not delete:** `audios/`, `metadata/`, `catalog/ghasslan_mirrors.csv`,
`catalog/supplements.csv`, `README.md`, or the main download scripts.

## Credits

Narration and original recordings: **فواز الغسلان**. Mirror uploads:
**صدى نجد دوت كوم** (`@alraawy_2`). This repository only documents and
preserves the recovered audio for personal, non-commercial use.
