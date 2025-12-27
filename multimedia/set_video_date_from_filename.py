#!/usr/bin/env python3

"""
Set video creation dates from filenames.
Extracts date/time from specially formatted filenames and writes it as metadata.
Handles timezone conversion from Brazil time to UTC with automatic DST support.

Supported filename formats:
    - With prefix: [tag] 2018-04-07 17.50.41-1.mp4
    - Without prefix: 2016-12-19 19.10.47-1.m4v
"""

import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Supported video extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.MP4', '.MOV', '.MKV', '.AVI', '.M4V'}

# Brazil timezone (automatically handles DST)
BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")

def extract_date_from_filename(filename):
    """
    Extract date from filename formats:
        - With prefix: [tag] 2018-04-07 17.50.41-1.mp4
        - Without prefix: 2016-12-19 19.10.47-1.m4v
    
    Returns datetime object or None if no match
    """
    # Pattern to match: (optional [anything]) YYYY-MM-DD HH.MM.SS (optional suffix)
    pattern = r'(?:\[.*?\]\s+)?(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})'
    
    match = re.search(pattern, filename)
    
    if not match:
        return None
    
    year, month, day, hour, minute, second = match.groups()
    
    # Convert to datetime object
    date_obj = datetime(
        int(year),
        int(month),
        int(day),
        int(hour),
        int(minute),
        int(second)
    )
    
    return date_obj

def set_video_creation_date(video_path, output_dir, creation_date):
    """
    Set the creation date metadata of a video file using ffmpeg
    
    Args:
        video_path: Path to the input video file
        output_dir: Path to the output directory
        creation_date: datetime object with the desired creation date (in Brazil time, naive)
    
    Returns:
        Path to the output file
    """
    input_path = Path(video_path)
    
    # Create output filename in the output directory
    output_path = output_dir / input_path.name
    
    # Localize the naive datetime to Brazil timezone (handles DST automatically)
    creation_date_br = creation_date.replace(tzinfo=BRAZIL_TZ)
    
    # Convert to UTC
    creation_date_utc = creation_date_br.astimezone(ZoneInfo("UTC"))
    
    # Get the offset for display purposes
    offset = creation_date_br.strftime('%z')
    offset_hours = f"UTC{offset[:3]}:{offset[3:]}"
    
    # Format date for ffmpeg (ISO 8601 format in UTC)
    date_str = creation_date_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Build ffmpeg command
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c", "copy",  # Copy without re-encoding
        "-map_metadata", "0",  # Copy existing metadata
        "-metadata", f"creation_time={date_str}",
        "-y",  # Overwrite if exists
        str(output_path)
    ]
    
    print(f"   📅 Brazil: {creation_date.strftime('%Y-%m-%d %H:%M:%S')} ({offset_hours})")
    print(f"   🌍 UTC:    {creation_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"   ✅ Success!")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error running ffmpeg: {e}")
        if e.stderr:
            print(f"      stderr: {e.stderr.decode()}")
        raise

def main():
    if len(sys.argv) != 2:
        print("Usage: python set_video_date_from_filename.py <directory>")
        print()
        print("Example:")
        print('  python set_video_date_from_filename.py /path/to/videos/')
        print()
        print("Expected filename formats (date in Brazil time):")
        print('  - With prefix:    [tag] 2018-04-07 17.50.41-1.mp4')
        print('  - Without prefix: 2016-12-19 19.10.47-1.m4v')
        print()
        print('Note: DST (Daylight Saving Time) is automatically handled based on the date.')
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
    
    print(f"📁 Processing videos in: {input_dir}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🌍 Timezone: America/Sao_Paulo (BRT/BRST with DST support)")
    print()
    
    # Find all video files
    video_files = [f for f in input_dir.iterdir() 
                   if f.is_file() and f.suffix in VIDEO_EXTENSIONS]
    
    if not video_files:
        print("❌ No video files found in the directory")
        sys.exit(0)
    
    print(f"Found {len(video_files)} video file(s)")
    print()
    
    # Process each video
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    for video_file in video_files:
        print(f"→ Processing: {video_file.name}")
        
        # Extract date from filename
        creation_date = extract_date_from_filename(video_file.name)
        
        if creation_date is None:
            print(f"   ⚠️  Skipped: Could not extract date from filename")
            print(f"      Expected format: YYYY-MM-DD HH.MM.SS (optional [prefix])")
            skipped_count += 1
            print()
            continue
        
        print(f"   📅 Extracted date: {creation_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Set the creation date
        try:
            output_path = set_video_creation_date(video_file, output_dir, creation_date)
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

