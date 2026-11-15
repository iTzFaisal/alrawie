#!/usr/bin/env python3
"""Convert downloaded MP4s to M4A by copying the AAC stream (no re-encode).

Verifies audio duration against the video before deleting anything.
Usage:
    python3 convert_to_audio.py            # convert + verify, keep MP4s
    python3 convert_to_audio.py --delete-video
"""
import re
import subprocess
import sys
from pathlib import Path

VIDEOS = Path(__file__).parent / "audios"
NAME_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.mp4$")


def duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ])
    return float(out.strip())


def main() -> None:
    delete_video = "--delete-video" in sys.argv
    converted, skipped, failed = 0, 0, []

    for mp4 in sorted(VIDEOS.glob("*.mp4")):
        if not NAME_RE.search(mp4.name):
            continue  # skip .f136.mp4 intermediates
        m4a = mp4.with_suffix(".m4a")

        if not m4a.exists():
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(mp4), "-vn", "-map", "0:a:0", "-c:a", "copy",
                "-movflags", "+faststart", str(m4a),
            ], check=True)

        video_dur = duration(mp4)
        audio_dur = duration(m4a)
        if abs(video_dur - audio_dur) > 2:
            failed.append((mp4.name, video_dur, audio_dur))
            continue

        converted += 1
        if delete_video:
            mp4.unlink()
        else:
            skipped += 1

    print(f"verified audio: {converted}")
    print(f"kept videos: {skipped}")
    if failed:
        print("duration mismatches (videos kept):")
        for name, vd, ad in failed:
            print(f"  {name}: video {vd:.1f}s vs audio {ad:.1f}s")

    if delete_video:
        # remove leftover download fragments
        for pattern in ("*.part", "*.f*.mp4", "*.f*.m4a"):
            for f in VIDEOS.glob(pattern):
                f.unlink()
                print("removed partial:", f.name)


if __name__ == "__main__":
    main()
