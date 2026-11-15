#!/usr/bin/env bash
# Download every surviving mirror of the Ghasslan videos uploaded by @alrawie8.
# Audio-only: copies YouTube's AAC stream to .m4a (no re-encode).
# Resumable: re-running skips anything already in state/downloads_audio.txt.
set -u
cd "$(dirname "$0")"

mkdir -p audios metadata state logs

if [ ! -f catalog/urls.txt ]; then
  python3 - <<'PY'
import csv
with open('catalog/ghasslan_mirrors.csv', encoding='utf-8') as fh, \
     open('catalog/urls.txt', 'w', encoding='utf-8') as out:
    for row in csv.DictReader(fh):
        out.write(row['url'] + '\n')
PY
fi

# Record files already present anywhere under audios/ (including series
# folders) so the single-queue run does not download them again.
python3 - <<'PY'
import re
from pathlib import Path

archive = Path('state/downloads_audio.txt')
seen = set()
if archive.exists():
    seen = {line.strip() for line in archive.read_text().splitlines() if line.strip()}
for path in Path('audios').rglob('*.m4a'):
    m = re.search(r'\[([A-Za-z0-9_-]{11})\]\.m4a$', path.name)
    if m:
        seen.add(m.group(1))
archive.write_text('\n'.join(sorted(seen)) + ('\n' if seen else ''))
print(f'{len(seen)} existing audio IDs recorded')
PY

uvx --from yt-dlp yt-dlp \
  --batch-file catalog/urls.txt \
  --download-archive state/downloads_audio.txt \
  --extractor-args "youtube:lang=ar" \
  --format "bestaudio[ext=m4a]/bestaudio" \
  --output "audios/%(title).140B [%(id)s].%(ext)s" \
  --write-info-json \
  --retries 10 \
  --fragment-retries 10 \
  --socket-timeout 30 \
  --concurrent-fragments 8 \
  --no-overwrites \
  --no-warnings \
  2>&1 | tee -a logs/download.log
python3 organize.py
python3 verify.py
