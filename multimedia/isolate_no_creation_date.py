#!/usr/bin/env python3

"""
Isolate images that lack EXIF date metadata.
Scans a directory for photos and moves those without creation date information
to a separate subfolder.
"""

import subprocess
import sys
from pathlib import Path
import shutil

if len(sys.argv) != 2:
    print("Usage: python move_no_exif_date.py <directory>")
    sys.exit(1)

base_dir = Path(sys.argv[1])

if not base_dir.is_dir():
    print("Not a directory")
    sys.exit(1)

# Subfolder for files without EXIF date
target_dir = base_dir / "no_exif_date"
target_dir.mkdir(exist_ok=True)

# Image extensions to check
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif"}

moved_files = []

for file in sorted(base_dir.iterdir()):
    if not file.is_file():
        continue

    if file.suffix.lower() not in IMAGE_EXTS:
        continue

    cmd = [
        "exiftool",
        "-s", "-s", "-s",
        "-DateTimeOriginal",
        "-CreateDate",
        "-DateTimeDigitized",
        str(file)
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # If no EXIF date fields exist
    if not result.stdout.strip():
        dest = target_dir / file.name
        shutil.move(str(file), str(dest))
        moved_files.append(file.name)

# Summary
print(f"\nMoved {len(moved_files)} file(s) to '{target_dir.name}/':\n")
for name in moved_files:
    print(name)