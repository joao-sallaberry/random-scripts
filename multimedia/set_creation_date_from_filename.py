#!/usr/bin/env python3

"""
Set creation dates for photos and videos from filenames.
Extracts date/time from specially formatted filenames and writes it as metadata.
Handles timezone conversion from Brazil time to UTC with automatic DST support.
Uses exiftool for metadata manipulation.

Supported filename formats:
    - Standard: [tag] 2018-04-07 17.50.41-1.mp4
    - Standard: 2016-12-19 19.10.47-1.m4v
    - With "at": Any prefix 2025-12-31 at 11.08.35 PM
"""

import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil

# Supported file extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.MP4', '.MOV', '.MKV', '.AVI', '.M4V'}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.JPG', '.JPEG', '.PNG', '.HEIC'}

# Brazil timezone (automatically handles DST)
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

def extract_date_from_filename(filename):
    """
    Extract date from filename. Tries multiple formats:
        - Format 1: 2018-04-07 17.50.41 (24-hour, optional prefix)
        - Format 2: 2025-12-31 at 11.08.35 PM (12-hour with AM/PM)
    
    Returns datetime object or None if no match
    """
    # Pattern 1: YYYY-MM-DD HH.MM.SS (24-hour format)
    # Examples: "[tag] 2018-04-07 17.50.41-1.mp4" or "2016-12-19 19.10.47-1.m4v"
    pattern1 = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})'
    
    match = re.search(pattern1, filename)
    if match:
        year, month, day, hour, minute, second = match.groups()
        # Check if this is the 12-hour format (has AM/PM after)
        # If so, skip this match and let pattern2 handle it
        pos_after_match = match.end()
        if pos_after_match < len(filename):
            remaining = filename[pos_after_match:]
            if re.search(r'\s+(AM|PM)', remaining, re.IGNORECASE):
                # This is 12-hour format, skip to pattern2
                pass
            else:
                # This is 24-hour format
                return datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second)
                )
        else:
            # End of filename, treat as 24-hour format
            return datetime(
                int(year), int(month), int(day),
                int(hour), int(minute), int(second)
            )
    
    # Pattern 2: YYYY-MM-DD at HH.MM.SS AM/PM (12-hour format)
    # Example: "WhatsApp Video 2025-12-31 at 11.08.35 PM" or "2025-12-31 at 11.08.35 PM"
    pattern2 = r'(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d{1,2})\.(\d{2})\.(\d{2})\s+(AM|PM)'
    
    match = re.search(pattern2, filename, re.IGNORECASE)
    if match:
        year, month, day, hour, minute, second, ampm = match.groups()
        hour = int(hour)
        
        # Convert 12-hour to 24-hour format
        if ampm.upper() == 'PM' and hour != 12:
            hour += 12
        elif ampm.upper() == 'AM' and hour == 12:
            hour = 0
        
        return datetime(
            int(year), int(month), int(day),
            hour, int(minute), int(second)
        )
    
    return None

def set_media_creation_date(file_path, output_dir, creation_date, is_video=True):
    """
    Set the creation date metadata of a photo or video file using exiftool
    
    Args:
        file_path: Path to the input file
        output_dir: Path to the output directory
        creation_date: datetime object with the desired creation date (in Brazil time, naive)
        is_video: True for videos, False for photos
    
    Returns:
        Path to the output file
    """
    input_path = Path(file_path)
    
    # Read existing creation time from metadata using exiftool
    probe_field = "CreateDate" if is_video else "DateTimeOriginal"
    probe_cmd = [
        "exiftool",
        f"-{probe_field}",
        "-s3",  # Simple format (value only)
        str(input_path)
    ]
    
    probe_result = subprocess.run(
        probe_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    existing_time_str = probe_result.stdout.strip()
    if existing_time_str:
        print(f"   🕐 Previous: {existing_time_str}")
    else:
        print(f"   🕐 Previous: (no {probe_field} metadata found)")
    
    # Create output filename in the output directory
    output_path = output_dir / input_path.name
    
    # Copy file first
    shutil.copy2(input_path, output_path)
    
    # Localize the naive datetime to Brazil timezone (handles DST automatically)
    creation_date_br = creation_date.replace(tzinfo=BRAZIL_TZ)
    
    # Convert to UTC
    creation_date_utc = creation_date_br.astimezone(ZoneInfo("UTC"))
    
    # Get the offset for display purposes
    offset = creation_date_br.strftime('%z')
    offset_hours = f"UTC{offset[:3]}:{offset[3:]}"
    
    # Format date for exiftool (YYYY:MM:DD HH:MM:SS format)
    date_str = creation_date_utc.strftime("%Y:%m:%d %H:%M:%S")
    
    # Build exiftool command based on file type
    if is_video:
        # Video: Set CreateDate, ModifyDate, TrackCreateDate, MediaCreateDate
        cmd = [
            "exiftool",
            "-overwrite_original",
            f"-CreateDate={date_str}",
            f"-ModifyDate={date_str}",
            f"-TrackCreateDate={date_str}",
            f"-MediaCreateDate={date_str}",
            str(output_path)
        ]
    else:
        # Photo: Set DateTimeOriginal, CreateDate, ModifyDate
        cmd = [
            "exiftool",
            "-overwrite_original",
            f"-DateTimeOriginal={date_str}",
            f"-CreateDate={date_str}",
            f"-ModifyDate={date_str}",
            str(output_path)
        ]
    
    print(f"   📅 New (BRT): {creation_date.strftime('%Y-%m-%d %H:%M:%S')} ({offset_hours})")
    print(f"   🌍 New (UTC): {creation_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"   ✅ Success!")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error running exiftool: {e}")
        if e.stderr:
            print(f"      stderr: {e.stderr}")
        raise

def main():
    if len(sys.argv) != 2:
        print("Usage: python set_video_date_from_filename.py <directory>")
        print()
        print("Example:")
        print('  python set_video_date_from_filename.py /path/to/media/')
        print()
        print("Expected filename formats (date in Brazil time):")
        print('  - 24-hour: [tag] 2018-04-07 17.50.41-1.mp4')
        print('  - 24-hour: 2016-12-19 19.10.47-1.m4v')
        print('  - 12-hour: 2025-12-31 at 11.08.35 PM')
        print('  - 12-hour: WhatsApp Video 2025-12-31 at 11.08.35 PM')
        print()
        print('Supports: Videos (mp4, mov, mkv, avi, m4v) and Photos (jpg, jpeg, png, heic)')
        print('Note: DST (Daylight Saving Time) is automatically handled based on the date.')
        print('Requires: exiftool')
        sys.exit(1)
    
    # Check if exiftool is available
    if not shutil.which("exiftool"):
        print("❌ Error: exiftool is not installed")
        print()
        print("Install exiftool:")
        print("  macOS:  brew install exiftool")
        print("  Ubuntu: sudo apt install libimage-exiftool-perl")
        print("  Fedora: sudo dnf install perl-Image-ExifTool")
        sys.exit(1)
    
    input_dir = Path(sys.argv[1])
    
    # Validate directory exists
    if not input_dir.exists():
        print(f"❌ Error: Directory not found: {input_dir}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"❌ Error: Not a directory: {input_dir}")
        sys.exit(1)
    
    # Create output directory
    output_dir = input_dir / "dated"
    output_dir.mkdir(exist_ok=True)
    
    print(f"📁 Processing media in: {input_dir}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🌍 Timezone: America/Sao_Paulo (BRT/BRST with DST support)")
    print()
    
    # Find all media files (videos and photos)
    media_files = []
    for f in input_dir.iterdir():
        if f.is_file():
            if f.suffix in VIDEO_EXTENSIONS:
                media_files.append(('video', f))
            elif f.suffix in PHOTO_EXTENSIONS:
                media_files.append(('photo', f))
    
    if not media_files:
        print("❌ No media files found in the directory")
        sys.exit(0)
    
    video_count = sum(1 for t, _ in media_files if t == 'video')
    photo_count = sum(1 for t, _ in media_files if t == 'photo')
    
    print(f"Found {video_count} video(s) and {photo_count} photo(s)")
    print()
    
    # Process each media file
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for media_type, media_file in media_files:
        icon = "🎬" if media_type == "video" else "📷"
        print(f"{icon} Processing: {media_file.name}")
        
        # Extract date from filename
        creation_date = extract_date_from_filename(media_file.name)
        
        if creation_date is None:
            print(f"   ⚠️  Skipped: Could not extract date from filename")
            print(f"      Supported formats:")
            print(f"      - 24-hour: YYYY-MM-DD HH.MM.SS")
            print(f"      - 12-hour: YYYY-MM-DD at HH.MM.SS AM/PM")
            skipped_count += 1
            print()
            continue
        
        print(f"   📅 Extracted date: {creation_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Set the creation date
        try:
            is_video = (media_type == 'video')
            output_path = set_media_creation_date(media_file, output_dir, creation_date, is_video)
            success_count += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1
        
        print()
    
    print("="*50)
    print(f"✅ Successfully processed: {success_count}")
    print(f"⚠️  Skipped (no date found): {skipped_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📁 Files saved in: {output_dir}")


if __name__ == "__main__":
    main()

