#!/usr/bin/env python3
"""Build one release zip per series folder under audios/.

Every folder in audios/ becomes ``dist/release/<folder>.zip`` with the folder
itself as the archive's top level, so extracting yields the same layout as a
clone. M4A is already compressed, so entries are stored instead of deflated:
the build stays I/O bound and the archives are reproducible byte for byte.

Also writes ``dist/release/SHA256SUMS.txt`` for integrity checks and
``dist/release/summary.tsv`` for the release notes.

    python3 make_zips.py             # rebuild only stale archives
    python3 make_zips.py --force     # rebuild everything
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUDIOS = ROOT / "audios"
OUT = ROOT / "dist" / "release"
IGNORED = {".DS_Store", ".gitkeep", "Thumbs.db", "desktop.ini"}
IGNORED_SUFFIXES = {".part"}
CHUNK = 1024 * 1024

# GitHub renames release assets: it transliterates Unicode and replaces every
# other character with a dot, which erases Arabic entirely. Asset names are
# therefore fixed Latin slugs; the Arabic folder name survives inside the zip.
SLUGS = {
    "أخرى": "okhra",
    "القصائد المتداخلة": "qasaid-mutadakhila",
    "الموسوعة الشعرية": "mawsuat-sheriya",
    "جواهر الأمثال الشعبية": "jawaher-amthal-shaabiya",
    "ضحايا العشق": "dahaya-aleshq",
    "عاشق ومعشوق": "asheq-wamaashuq",
    "فنجال الكيف": "finjal-alkayf",
    "مفاخر العرب": "mafakher-alarab",
    "مكملات": "mukammilat",
    "موسوعة التاريخ والأدب": "mawsuat-tarikh-wa-adab",
    "نوادر شعرية": "nawader-sheriya",
    "نوادر من التراث": "nawader-min-alturath",
}


def asset_name(folder: Path) -> str:
    """Release asset filename: Latin slug, because GitHub drops Arabic."""
    try:
        slug = SLUGS[folder.name]
    except KeyError:
        raise SystemExit(
            f"no release slug for {folder.name!r}; add one to SLUGS in make_zips.py"
        ) from None
    return f"{slug}.zip"


def source_files(folder: Path) -> list[Path]:
    files = [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.name not in IGNORED
        and path.suffix not in IGNORED_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.relative_to(folder).as_posix())


def needs_rebuild(zip_path: Path, files: list[Path], force: bool) -> bool:
    if force or not zip_path.exists():
        return True
    built = zip_path.stat().st_mtime
    return any(path.stat().st_mtime > built for path in files)


def build(folder: Path, zip_path: Path, files: list[Path]) -> None:
    tmp_path = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            arcname = f"{folder.name}/{path.relative_to(folder).as_posix()}"
            archive.write(path, arcname)
    tmp_path.replace(zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    expected = [f"{folder.name}/{p.relative_to(folder).as_posix()}" for p in files]
    if names != expected:
        raise SystemExit(f"self-check failed for {zip_path.name}: entry mismatch")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild every archive")
    args = parser.parse_args()

    if not AUDIOS.is_dir():
        raise SystemExit(f"missing audio directory: {AUDIOS}")

    folders = sorted(path for path in AUDIOS.iterdir() if path.is_dir() and not path.name.startswith("."))
    if not folders:
        raise SystemExit(f"no series folders under {AUDIOS}")

    OUT.mkdir(parents=True, exist_ok=True)
    summary: list[tuple[str, str, int, int]] = []

    for folder in folders:
        files = source_files(folder)
        if not files:
            print(f"skip {folder.name}: no files", file=sys.stderr)
            continue

        zip_path = OUT / asset_name(folder)
        action = "rebuilt" if needs_rebuild(zip_path, files, args.force) else "kept"
        if action == "rebuilt":
            build(folder, zip_path, files)

        summary.append((folder.name, zip_path.name, len(files), zip_path.stat().st_size))
        print(f"{action:8} {zip_path.name:40} {len(files):>3} files  {zip_path.stat().st_size / 1024 / 1024:7.1f} MB")

    if not summary:
        raise SystemExit("nothing to package")

    sums_path = OUT / "SHA256SUMS.txt"
    lines = []
    for _, name, _, _ in sorted(summary, key=lambda row: row[1]):
        lines.append(f"{sha256(OUT / name)}  {name}")
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    table = OUT / "summary.tsv"
    table.write_text(
        "folder\tasset\tfiles\tbytes\n"
        + "\n".join(f"{folder}\t{name}\t{count}\t{size}" for folder, name, count, size in summary)
        + "\n",
        encoding="utf-8",
    )

    total_files = sum(row[2] for row in summary)
    total_bytes = sum(row[3] for row in summary)
    print(f"\n{len(summary)} archives, {total_files} files, {total_bytes / 1024 / 1024 / 1024:.2f} GiB")
    print(f"checksums: {sums_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
