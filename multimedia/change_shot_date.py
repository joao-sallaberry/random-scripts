#!/usr/bin/env python3

"""
Adjust creation dates of videos and photos in a directory.
Adds a fixed offset (728 days + 23 hours) to the creation time metadata.
Uses ffmpeg for videos and exiftool for photos.
"""

import subprocess
from datetime import datetime, timedelta
import sys
import re
from pathlib import Path
import shutil

if len(sys.argv) != 2:
    print("Usage: python adjust_date.py <directory>")
    sys.exit(1)

input_dir = Path(sys.argv[1])

if not input_dir.exists():
    print("Directory not found")
    sys.exit(1)

if not input_dir.is_dir():
    print("The provided path is not a directory")
    sys.exit(1)

# Check if exiftool is available
exiftool_available = shutil.which("exiftool") is not None
if not exiftool_available:
    print("⚠️  exiftool not found. Photos will not be processed.")
    print("   Install with: brew install exiftool")

# Supported extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.MP4', '.MOV', '.AVI', '.MKV', '.M4V'}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}

# Find all files in the directory
media_files = []
for f in input_dir.iterdir():
    if f.is_file():
        if f.suffix in VIDEO_EXTENSIONS:
            media_files.append(('video', f))
        elif f.suffix in PHOTO_EXTENSIONS and exiftool_available:
            media_files.append(('photo', f))

if not media_files:
    print("No media files found in the directory")
    sys.exit(1)

video_count = sum(1 for t, _ in media_files if t == 'video')
photo_count = sum(1 for t, _ in media_files if t == 'photo')

print(f"📹 Found {video_count} video(s)")
print(f"📷 Found {photo_count} photo(s)")
print()

# Create output directory
output_dir = input_dir / "updated"
output_dir.mkdir(exist_ok=True)

success_count = 0
error_count = 0

def process_video(input_video, output_video):
    """Process a video file using ffmpeg"""
    # 1️⃣ Read creation_time via ffmpeg
    cmd_probe = [
        "ffmpeg",
        "-i", str(input_video)
    ]
    
    result = subprocess.run(
        cmd_probe,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )
    
    match = re.search(r"creation_time\s*:\s*(.+)", result.stderr)
    
    if not match:
        raise ValueError("creation_time not found in metadata")
    
    creation_time_str = match.group(1).strip()
    
    # 2️⃣ Parse the date (UTC)
    creation_time = datetime.strptime(
        creation_time_str,
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    
    # 3️⃣ Add 728 days and 23 hours
    new_time = creation_time + timedelta(days=728, hours=23)
    
    new_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 4️⃣ Write new metadata (without re-encoding)
    cmd_write = [
        "ffmpeg",
        "-i", str(input_video),
        "-c", "copy",
        "-map_metadata", "0",
        "-metadata", f"creation_time={new_time_str}",
        "-y",  # Overwrite if exists
        str(output_video)
    ]
    
    subprocess.run(cmd_write, check=True, capture_output=True)
    
    return creation_time_str, new_time_str

def process_photo(input_photo, output_photo):
    """Process a photo file using exiftool"""
    # 1️⃣ Read original date via exiftool
    cmd_probe = [
        "exiftool",
        "-DateTimeOriginal",
        "-s3",  # Simple format
        str(input_photo)
    ]
    
    result = subprocess.run(
        cmd_probe,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    date_str = result.stdout.strip()
    
    if not date_str:
        raise ValueError("DateTimeOriginal not found in EXIF")
    
    # 2️⃣ Parse the date
    # Expected format: "2022:03:10 08:15:00"
    creation_time = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    
    # 3️⃣ Add 728 days and 23 hours
    new_time = creation_time + timedelta(days=728, hours=23)
    
    new_time_str = new_time.strftime("%Y:%m:%d %H:%M:%S")
    
    # 4️⃣ Copy file and update metadata
    shutil.copy2(input_photo, output_photo)
    
    cmd_write = [
        "exiftool",
        "-overwrite_original",
        f"-DateTimeOriginal={new_time_str}",
        f"-CreateDate={new_time_str}",
        f"-ModifyDate={new_time_str}",
        str(output_photo)
    ]
    
    subprocess.run(cmd_write, check=True, capture_output=True)
    
    return date_str, new_time_str

for media_type, input_file in media_files:
    icon = "🎬" if media_type == "video" else "📷"
    print(f"{icon} Processing: {input_file.name}")
    
    try:
        output_file = output_dir / input_file.name
        
        if media_type == "video":
            original, new = process_video(input_file, output_file)
        else:  # photo
            original, new = process_photo(input_file, output_file)
        
        print(f"  ✅ Success")
        print(f"     📅 Original : {original}")
        print(f"     📅 New      : {new}")
        success_count += 1
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        error_count += 1
    
    print()

print("="*50)
print(f"✅ Successfully processed: {success_count}")
print(f"❌ Errors: {error_count}")
print(f"📁 Files saved in: {output_dir}")
