#!/usr/bin/env python3

"""
Adjust creation dates of videos and photos in a directory.
Supports two modes: offset mode (adjust by time delta) or exact date mode (set specific date).
Uses ffmpeg for videos and exiftool for photos.

Usage Examples:
    Offset mode (adjust dates by time delta):
        python change_shot_date.py /path/to/media --days 2 --hours 3 --minutes 30
        python change_shot_date.py /path/to/media --days -5 --hours -2
    
    Exact date mode (set all files to specific date):
        python change_shot_date.py /path/to/media --set-date 2024-03-15T14:30:00
        python change_shot_date.py /path/to/media --set-date "2024-03-15 14:30:00"
"""

import subprocess
from datetime import datetime, timedelta
import sys
import re
from pathlib import Path
import shutil
import argparse

# Supported extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.MP4', '.MOV', '.AVI', '.MKV', '.M4V'}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}


def setup_argument_parser():
    """
    Set up and return the argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Adjust creation dates of videos and photos by offset or set to exact date',
        epilog='Examples:\n'
               '  Offset mode:  %(prog)s /path/to/media --days 2 --hours 3\n'
               '  Exact mode:   %(prog)s /path/to/media --set-date 2024-03-15T14:30:00\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'directory',
        type=str,
        help='Directory containing the media files'
    )
    
    # Create mutually exclusive group for modes
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--set-date',
        type=str,
        metavar='ISO_DATE',
        help='Set all files to exact date (ISO format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS)'
    )
    
    # Offset parameters
    parser.add_argument(
        '--days',
        type=int,
        default=0,
        help='Number of days to offset (negative to go back in time, default: 0). Requires offset mode.'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=0,
        help='Number of hours to offset (negative to go back in time, default: 0). Requires offset mode.'
    )
    parser.add_argument(
        '--minutes',
        type=int,
        default=0,
        help='Number of minutes to offset (negative to go back in time, default: 0). Requires offset mode.'
    )
    
    return parser


def parse_iso_date(date_string):
    """
    Parse an ISO format date string.
    
    Args:
        date_string: Date string in ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS)
        
    Returns:
        datetime: Parsed datetime object
        
    Raises:
        ValueError: If date format is invalid
    """
    try:
        # Try parsing with 'T' separator first
        return datetime.fromisoformat(date_string)
    except ValueError:
        try:
            # Try with space separator
            return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(
                f"Invalid date format '{date_string}'. "
                "Expected format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS. "
                "Examples: 2024-03-15T14:30:00 or 2024-03-15 14:30:00"
            )


def validate_arguments(args):
    """
    Validate parsed arguments and return configuration.
    
    Args:
        args: Parsed arguments from argparse
        
    Returns:
        tuple: (use_exact_date: bool, exact_date: datetime or None, input_dir: Path)
        
    Raises:
        SystemExit: If validation fails
    """
    # Check if using exact date or offset mode
    use_exact_date = args.set_date is not None
    use_offset = args.days != 0 or args.hours != 0 or args.minutes != 0
    
    # Validate that modes are mutually exclusive
    if use_exact_date and use_offset:
        print("Error: Cannot use both --set-date and offset parameters (--days, --hours, --minutes)")
        sys.exit(1)
    
    # Validate that at least one mode is specified
    if not use_exact_date and not use_offset:
        print("Error: Must specify either --set-date or at least one offset (--days, --hours, --minutes)")
        sys.exit(1)
    
    # Parse exact date if provided
    exact_date = None
    if use_exact_date:
        try:
            exact_date = parse_iso_date(args.set_date)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Validate directory
    input_dir = Path(args.directory)
    
    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"Error: The provided path is not a directory: {input_dir}")
        sys.exit(1)
    
    return use_exact_date, exact_date, input_dir


def process_video(input_video, output_video, use_exact_date, exact_date, args):
    """
    Process a video file using ffmpeg.
    
    Args:
        input_video: Path to input video file
        output_video: Path to output video file
        use_exact_date: Whether to use exact date mode
        exact_date: The exact date to set (if in exact date mode)
        args: Parsed command-line arguments
        
    Returns:
        tuple: (original_time_str, new_time_str)
    """
    # 1️⃣ Read creation_time via ffmpeg (only needed for offset mode)
    original_time_str = None
    
    if not use_exact_date:
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
        
        original_time_str = match.group(1).strip()
        
        # 2️⃣ Parse the date (UTC)
        creation_time = datetime.strptime(
            original_time_str,
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        
        # 3️⃣ Apply the time offset
        new_time = creation_time + timedelta(days=args.days, hours=args.hours, minutes=args.minutes)
    else:
        # Use exact date
        new_time = exact_date
        original_time_str = "(original date)"
    
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
    
    return original_time_str, new_time_str


def process_photo(input_photo, output_photo, use_exact_date, exact_date, args):
    """
    Process a photo file using exiftool.
    
    Args:
        input_photo: Path to input photo file
        output_photo: Path to output photo file
        use_exact_date: Whether to use exact date mode
        exact_date: The exact date to set (if in exact date mode)
        args: Parsed command-line arguments
        
    Returns:
        tuple: (original_date_str, new_time_str)
    """
    # 1️⃣ Read original date via exiftool (only needed for offset mode)
    original_date_str = None
    
    if not use_exact_date:
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
        
        original_date_str = result.stdout.strip()
        
        if not original_date_str:
            raise ValueError("DateTimeOriginal not found in EXIF")
        
        # 2️⃣ Parse the date
        # Expected format: "2022:03:10 08:15:00"
        creation_time = datetime.strptime(original_date_str, "%Y:%m:%d %H:%M:%S")
        
        # 3️⃣ Apply the time offset
        new_time = creation_time + timedelta(days=args.days, hours=args.hours, minutes=args.minutes)
    else:
        # Use exact date
        new_time = exact_date
        original_date_str = "(original date)"
    
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
    
    return original_date_str, new_time_str


def main():
    """Main entry point for the script."""
    # Parse and validate arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    use_exact_date, exact_date, input_dir = validate_arguments(args)
    
    # Check if exiftool is available
    exiftool_available = shutil.which("exiftool") is not None
    if not exiftool_available:
        print("⚠️  exiftool not found. Photos will not be processed.")
        print("   Install with: brew install exiftool")
    
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
    
    # Display mode information
    if use_exact_date:
        print(f"📅 Mode: Set to exact date")
        print(f"⏰ Target date: {exact_date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        offset_parts = []
        if args.days != 0:
            offset_parts.append(f"{args.days:+d} day(s)")
        if args.hours != 0:
            offset_parts.append(f"{args.hours:+d} hour(s)")
        if args.minutes != 0:
            offset_parts.append(f"{args.minutes:+d} minute(s)")
        offset_str = ", ".join(offset_parts)
        print(f"📅 Mode: Offset by time delta")
        print(f"⏰ Time offset: {offset_str}")
    
    print(f"📹 Found {video_count} video(s)")
    print(f"📷 Found {photo_count} photo(s)")
    print()
    
    # Create output directory
    output_dir = input_dir / "updated"
    output_dir.mkdir(exist_ok=True)
    
    success_count = 0
    error_count = 0
    
    # Process all media files
    for media_type, input_file in media_files:
        icon = "🎬" if media_type == "video" else "📷"
        print(f"{icon} Processing: {input_file.name}")
        
        try:
            output_file = output_dir / input_file.name
            
            if media_type == "video":
                original, new = process_video(input_file, output_file, use_exact_date, exact_date, args)
            else:  # photo
                original, new = process_photo(input_file, output_file, use_exact_date, exact_date, args)
            
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


if __name__ == "__main__":
    main()
