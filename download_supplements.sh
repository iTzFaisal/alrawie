#!/usr/bin/env bash
# Download the four gap-filling supplements as M4A.
# Skips files already present in audios/ or audios/مكملات/.
set -u
cd "$(dirname "$0")"

mkdir -p audios/مكملات metadata/مكملات logs
trap 'python3 organize.py >/dev/null 2>&1' EXIT

python3 - <<'PY'
import csv
import re
from pathlib import Path

rows = list(csv.DictReader(open("catalog/supplements.csv", encoding="utf-8")))
existing = set()
# Check the whole tree so a supplement is not downloaded twice if it is
# already present in a series folder from an older run.
for path in Path("audios").rglob("*.m4a"):
    m = re.search(r"\[([A-Za-z0-9_-]{11})\]\.m4a$", path.name)
    if m:
        existing.add(m.group(1))

missing = [r["video_id"] for r in rows if r["video_id"] not in existing]
Path("catalog/supplement_ids.txt").write_text(
    "\n".join(missing) + ("\n" if missing else "")
)
print(f"{len(missing)} supplement(s) to download")
PY

pids=()
while IFS= read -r id; do
  [ -n "$id" ] || continue
  echo "downloading $id"
  uvx --from yt-dlp yt-dlp \
    --extractor-args "youtube:lang=ar" \
    --format "bestaudio[ext=m4a]/bestaudio" \
    --output "audios/مكملات/%(title).140B [%(id)s].%(ext)s" \
    --write-info-json \
    --no-overwrites \
    --retries 10 \
    --fragment-retries 10 \
    --socket-timeout 30 \
    --concurrent-fragments 2 \
    --no-warnings \
    "https://www.youtube.com/watch?v=$id" \
    > "logs/supplement_$id.log" 2>&1 &
  pids+=($!)
done < catalog/supplement_ids.txt

for pid in ${pids[@]+"${pids[@]}"}; do
  wait "$pid" || true
done

python3 organize.py
python3 verify.py
