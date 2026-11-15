# الراوي فواز الغسلان — audio archive

[![GitHub](https://img.shields.io/badge/GitHub-iTzFaisal%2Falrawie-181717?logo=github)](https://github.com/iTzFaisal/alrawie)
[![Download](https://img.shields.io/badge/Download-GitHub%20Releases-2ea44f?logo=github)](https://github.com/iTzFaisal/alrawie/releases/latest)

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
size: 1.94 GB
runtime covered: 33.3 hours
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
12 archives with 211 files (1.98 GB) plus `SHA256SUMS.txt`.

```bash
gh release download archive-2026-11-15 --repo iTzFaisal/alrawie
shasum -a 256 -c SHA256SUMS.txt
for z in *.zip; do unzip -q "$z" -d audios; done
```

Asset names are Latin slugs because GitHub strips non-ASCII characters from
release filenames. Each zip keeps the original Arabic folder as its top level,
so extracting under `audios/` reproduces this repository's layout exactly; the
[folder table](#series-folders) maps every slug to its series.

## What you get

| Item                   |   Count |        Size |                 Runtime |
| ---------------------- | ------: | ----------: | ----------------------: |
| Main channel uploads   |     207 |     1.94 GB |                  33.3 h |
| Gap-filler supplements |       4 |       36 MB |                   0.6 h |
| **Total**              | **211** | **1.98 GB** | **33.9 h actual audio** |

- **207/207** mirror-channel uploads whose titles name فواز الغسلان.
- 195 individual episodes and 12 full-cassette uploads.
- Organized into one folder per series under `audios/<series>/`.
- Audio format: **M4A / AAC**, ~128 kbps, stream-copied from the source with no
  re-encode.
- No video is downloaded — every file is audio-only.
- The snapshot was completed on **2026-11-15**.

## Series folders

Each audio file is placed in the folder for its series:

| Folder                  | Files | Release asset                 |
| ----------------------- | ----: | ----------------------------- |
| `الموسوعة الشعرية`      |    57 | `mawsuat-sheriya.zip`         |
| `نوادر من التراث`       |    49 | `nawader-min-alturath.zip`    |
| `جواهر الأمثال الشعبية` |    38 | `jawaher-amthal-shaabiya.zip` |
| `عاشق ومعشوق`           |    23 | `asheq-wamaashuq.zip`         |
| `ضحايا العشق`           |    17 | `dahaya-aleshq.zip`           |
| `القصائد المتداخلة`     |    10 | `qasaid-mutadakhila.zip`      |
| `فنجال الكيف`           |     7 | `finjal-alkayf.zip`           |
| `مفاخر العرب`           |     1 | `mafakher-alarab.zip`         |
| `موسوعة التاريخ والأدب` |     1 | `mawsuat-tarikh-wa-adab.zip`  |
| `نوادر شعرية`           |     1 | `nawader-sheriya.zip`         |
| `أخرى`                  |     3 | `okhra.zip`                   |
| `مكملات`                |     4 | `mukammilat.zip`              |

`أخرى` is the catch-all for the few uploads whose titles do not name a series.
The `series` value is stored in `catalog/ghasslan_mirrors.csv`, so the
downloader and organizer use the same mapping.

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
│   ├── القصائد المتداخلة/
│   ├── فنجال الكيف/
│   ├── مفاخر العرب/
│   ├── موسوعة التاريخ والأدب/
│   ├── نوادر شعرية/
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
in `audios/<series>/`. It uses 8 parallel workers by default because YouTube
throttles each connection individually:

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
whose sources changed (`--force` rebuilds all). Uploads are resumable: assets
whose size already matches are skipped, and `release.sh` refuses to publish if
any local archive is missing or differs in size. Requires an authenticated
[`gh`](https://cli.github.com) CLI.

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

## Known source defect

One source upload has a defective audio track:

- `k7g61lkLMUw` — _أمكن تراها ما تفيد الحسايف | جواهر الامثال الشعبيه_
  (3:02). The source audio is silent from about **1:13** onward, with only a
  brief sound around **1:46**, then silence to the end.

This is **not** a corrupted local download. A fresh download from YouTube
reproduces the same silence. The file is kept as-is for completeness; if a
complete alternative copy is found, replace it and update the manifest.

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
