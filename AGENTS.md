# AGENTS.md

## What this repo is

Preservation archive of **فواز الغسلان** audio recovered from the mirror channel
`@alraawy_2`. Git tracks only the manifests, scripts, and docs. All media and
yt-dlp sidecars are gitignored, so a fresh clone legitimately has no audio.

## Verify state

- `python3 verify.py` is the only check; it uses the standard library only and
  needs no venv or installed packages.
- Expected output for the complete local archive:
  `downloaded: 207/207`, `size: 1.94 GB`, `runtime covered: 33.3 hours`,
  `supplements: 4/4 (36 MB)`.
- `verify.py` writes `catalog/download_report.csv` (gitignored).
- `python3 podcast/validate_feed.py` checks the generated podcast feeds: required
  iTunes tags, enclosure byte lengths against the local files, GUID and title
  uniqueness, 3000x3000 covers, and ordering.
- There is no test suite, linter, typecheck, build, CI, or package manifest.

## Commands

- `./download.sh` — downloads the 207 main uploads; `WORKERS` defaults to 8.
  Skips IDs already present anywhere under `audios/` and IDs in
  `catalog/supplements.csv`. Runs `organize.py` and `verify.py` when finished.
- `./download_supplements.sh` — downloads the 4 gap-fillers into
  `audios/مكملات/`.
- `./download_sequential.sh` — single-queue fallback using
  `state/downloads_audio.txt` when parallel workers hit rate limits.
- `python3 organize.py` — idempotently moves audio into `audios/<series>/`
  based on the catalog and sidecars into `metadata/`.
- `python3 make_zips.py` — builds `dist/release/<series>.zip` for every folder
  under `audios/`, plus `SHA256SUMS.txt` and `summary.tsv`. Archives are stored
  (no deflate) and rebuilt only when a source file is newer (use `--force`).
- `./release.sh` — builds the zips, creates the draft GitHub release
  `archive-2026-11-15` if needed, uploads missing assets smallest-first, and
  verifies remote sizes. `./release.sh --publish` flips the draft to public.
  Needs an authenticated `gh`; re-running is safe and resumable.
- `python3 podcast/build_feed.py` — regenerates `docs/feed.xml`,
  `docs/kasayet/feed.xml` and `docs/index.html` from the manifests, the audio
  files, and the committed covers. Deterministic; safe to re-run.
- `python3 podcast/publish_podcast.py` — creates one `audio-<slug>` release per
  series and uploads each episode as `<video-id>.m4a`. Skips assets already
  present with the right size, so it resumes after failures. `--dry-run` first.
- `swift podcast/make_covers.swift` — redraws both 3000x3000 JPEG covers. Uses
  CoreText because macOS fonts have no Arabic presentation-form glyphs; Pillow
  alone renders tofu.
- `yt-dlp` is always run via `uvx --from yt-dlp yt-dlp`; `ffmpeg`/`ffprobe` are
  only needed by `convert_to_audio.py`.
- Downloads transfer ~2 GB and depend on YouTube. Do not run them unless asked;
  both downloaders are resumable.

## Invariants and gotchas

- The `[<11-char video id>].m4a` filename suffix is load-bearing:
  `download*.sh`, `organize.py`, and `verify.py` all parse it. Do not rename
  media files.
- `catalog/ghasslan_mirrors.csv` is the source of truth for series placement;
  the `series` column selects `audios/<series>/`, and a blank value maps to
  `أخرى`. Adding or removing rows changes the expected coverage counts and the
  README tables.
- Supplements are identified by the `audios/مكملات/` path. `organize.py`
  deliberately never moves them, and the main downloader excludes their IDs.
  The two manifests must not overlap.
- `audios/كاسيت/` is a collection, not a series: the 12 full-cassette uploads
  live there and their catalog `series` is `كاسيت`, even though each title
  names its original series. `نوادر شعرية` and `مفاخر العرب` consequently hold
  only `.gitkeep`, so `make_zips.py` skips them and no `nawader-sheriya.zip` or
  `mafakher-alarab.zip` is produced; their slugs stay in `SLUGS` as reserved.
- The manifests are a frozen 2026-11-15 snapshot, not a live mirror; do not add
  newer source uploads unless explicitly asked.
- Podcast feeds are live API. `docs/feed.xml` is served at
  `https://itzfaisal.github.io/alrawie/feed.xml`; episode GUIDs are video IDs and
  enclosures point at `releases/download/audio-<slug>/<video-id>.m4a`. Renaming
  the repo, the slug, or an asset, or deleting and re-uploading one, silently
  breaks every subscriber. Add new episodes at the end of a season instead of
  renumbering. The Apple Podcasts IDs (`6835240326` main, `6835240746`
  cassettes) are bound to these feed URLs and would have to be resubmitted if
  the URL changed.
- `docs/` is generated: edit `podcast/build_feed.py`, not the XML or HTML.
  `BASE_DATE` is fixed on purpose so a rebuild produces an empty diff; changing
  it republishes every episode with a new date.
- The cassette show is deliberately separate from the main show. Putting
  `audios/كاسيت/` into the main feed would duplicate the 14.5 h that the 195
  individual episodes were cut from.
- Feeds skip the 4 supplements from the main series seasons and file them as
  `مكملات` season 10; they are unique content (`replaces_original` IDs are not in
  the mirror manifest).
- `verify.py` indexes main files recursively under `audios/` but counts
  supplements only from `audios/مكملات/`.
- `convert_to_audio.py` scans only top-level `audios/*.mp4`, not series
  subfolders. `--delete-video` removes source MP4s after a duration check.
- Trailing silence is by design, not a defect: short uploads are padded to a
  3-minute minimum, and the channel owner confirmed it. 62 files end with 30 s
  or more of silence (16 of them are more than half silent), and 18 of those
  also break off early with a ~1.3 s fragment near 1:46. `k7g61lkLMUw` is one
  of them; do not re-download or "repair" these files.
- Paths contain Arabic text and the fullwidth `｜` character; quote paths in
  shell commands.
- Release asset names are Latin slugs defined in `SLUGS` in `make_zips.py`.
  GitHub strips non-ASCII characters from uploaded filenames, so Arabic cannot
  be used on the asset itself; the zip's top-level folder keeps the real Arabic
  name. Adding a series folder requires adding a slug or the build fails.
  `RELEASE_NOTES.md` and the README release section must be updated when the
  tag, asset set, or counts change.
- `README.md` is the published documentation. Reconcile its counts and expected
  output when catalog rows, scripts, or archive contents change.
