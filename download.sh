#!/usr/bin/env bash
# Download the remaining Ghasslan mirrors as M4A.
# Audio files are small, so we run several videos in parallel instead of
# relying on fragment concurrency inside one video (YouTube throttles each
# connection; many connections aggregate to full link speed).
set -u
cd "$(dirname "$0")"

mkdir -p audios metadata logs
trap 'python3 organize.py >/dev/null 2>&1' EXIT
WORKERS="${WORKERS:-8}"

# Build the list of videos that still have no .m4a, then split it into
# balanced chunks (largest first, round-robin).
python3 - <<'PY'
import csv
import re
from pathlib import Path

done = set()
for path in Path("audios").rglob("*.m4a"):
    m = re.search(r"\[([A-Za-z0-9_-]{11})\]\.m4a$", path.name)
    if m:
        done.add(m.group(1))

# Supplements are downloaded by download_supplements.sh. Skip their IDs here
# so a future overlap with the main manifest cannot create a duplicate.
supplements = set()
if Path("catalog/supplements.csv").exists():
    supplements = {
        r["video_id"]
        for r in csv.DictReader(open("catalog/supplements.csv", encoding="utf-8"))
    }

rows = [
    r for r in csv.DictReader(open("catalog/ghasslan_mirrors.csv", encoding="utf-8"))
    if r["video_id"] not in done and r["video_id"] not in supplements
]
rows.sort(key=lambda r: -int(r["duration_seconds"] or 0))

workers = int(__import__("os").environ.get("WORKERS", "8"))
chunks = [[] for _ in range(workers)]
for i, row in enumerate(rows):
    chunks[i % workers].append(row["url"])

for i, chunk in enumerate(chunks):
    Path(f"catalog/chunk_{i}.txt").write_text("\n".join(chunk) + ("\n" if chunk else ""))
Path("catalog/remaining_audio.txt").write_text("\n".join(r["url"] for r in rows) + ("\n" if rows else ""))
print(f"{len(rows)} remaining across {sum(1 for c in chunks if c)} workers")
PY

pids=()
for i in $(seq 0 $((WORKERS - 1))); do
  [ -s "catalog/chunk_$i.txt" ] || continue
  echo "worker $i: $(wc -l < "catalog/chunk_$i.txt") videos"
  uvx --from yt-dlp yt-dlp \
    --batch-file "catalog/chunk_$i.txt" \
    --extractor-args "youtube:lang=ar" \
    --format "bestaudio[ext=m4a]/bestaudio" \
    --output "audios/%(title).140B [%(id)s].%(ext)s" \
    --write-info-json \
    --no-overwrites \
    --retries 10 \
    --fragment-retries 10 \
    --socket-timeout 30 \
    --concurrent-fragments 2 \
    --no-warnings \
    > "logs/worker_$i.log" 2>&1 &
  pids+=($!)
done

for pid in ${pids[@]+"${pids[@]}"}; do
  wait "$pid" || true
done

echo "workers finished"
python3 organize.py
python3 verify.py
