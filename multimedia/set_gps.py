#!/usr/bin/env python3

"""
Set GPS coordinates on media files in a directory using exiftool.
Accepts decimal degree coordinates and applies them to all supported files.

usage: set_gps.py [-h] coordinates directory

positional arguments:
  coordinates  GPS coordinates in decimal degrees: "LAT, LON" (e.g. "48.819126, 2.342003")
  directory    Directory containing the media files

example: set_gps.py "48.819126, 2.342003" /path/to/media
"""

import subprocess
import sys
import argparse
import shutil
from pathlib import Path
from util import VIDEO_EXTENSIONS, PHOTO_EXTENSIONS

MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | PHOTO_EXTENSIONS


def setup_argument_parser():
    """
    Set up and return the argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Set GPS coordinates on media files using exiftool',
        epilog='Examples:\n'
               '  %(prog)s "48.819126, 2.342003" /path/to/media\n'
               '  %(prog)s "-22.9068, -43.1729" /path/to/media\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'coordinates',
        type=str,
        help='GPS coordinates in decimal degrees: "LAT, LON" (e.g. "48.819126, 2.342003")'
    )
    parser.add_argument(
        'directory',
        type=str,
        help='Directory containing the media files'
    )

    return parser


def parse_coordinates(coordinates_str):
    """
    Parse a "LAT, LON" decimal degree string into (latitude, longitude) floats.

    Args:
        coordinates_str: String like "48.819126, 2.342003" or "-22.9068, -43.1729"

    Returns:
        tuple: (latitude: float, longitude: float)

    Raises:
        ValueError: If the string cannot be parsed
    """
    parts = coordinates_str.split(',')
    if len(parts) != 2:
        raise ValueError(
            f"Invalid coordinates format: '{coordinates_str}'. "
            "Expected: \"LAT, LON\" (e.g. \"48.819126, 2.342003\")"
        )
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except ValueError:
        raise ValueError(
            f"Could not parse numeric values from '{coordinates_str}'. "
            "Both latitude and longitude must be decimal numbers."
        )

    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude {lat} is out of range (-90 to 90).")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude {lon} is out of range (-180 to 180).")

    return lat, lon


def set_gps_on_file(file_path, lat, lon):
    """
    Apply GPS coordinates to a single media file using exiftool.

    For videos, writes to the QuickTime ©xyz UserData atom and Apple Keys
    metadata, which is what Google Photos and most video players read.
    For photos, writes standard EXIF GPS tags.

    Args:
        file_path: Path to the media file
        lat: Latitude in decimal degrees (negative for South)
        lon: Longitude in decimal degrees (negative for West)
    """
    lat_ref = 'N' if lat >= 0 else 'S'
    lon_ref = 'E' if lon >= 0 else 'W'
    is_video = file_path.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv', '.m4v'}

    cmd = ['exiftool', '-overwrite_original']

    if is_video:
        # Google Photos reads from the LocationInformation (loci) atom.
        # This is also the format ffmpeg uses when copying GPS during re-encoding.
        # GPSCoordinates (©xyz) is kept for Apple/QuickTime compatibility.
        cmd += [
            f'-QuickTime:LocationInformation=(none) Role=shooting Lat={lat} Lon={lon} Alt=0.00 Body=earth Notes=',
            f'-QuickTime:GPSCoordinates={lat}, {lon}',
            f'-Keys:GPSCoordinates={lat}, {lon}',
        ]
    else:
        # Standard EXIF GPS tags for photos (JPEG, PNG, HEIC, RAW, etc.)
        cmd += [
            f'-GPSLatitude={abs(lat)}',
            f'-GPSLatitudeRef={lat_ref}',
            f'-GPSLongitude={abs(lon)}',
            f'-GPSLongitudeRef={lon_ref}',
        ]

    cmd.append(str(file_path))
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    """Main entry point for the script."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Check exiftool availability
    if shutil.which('exiftool') is None:
        print('❌ exiftool is not installed or not in PATH.')
        print('   Install with: "sudo apt install exiftool" or "brew install exiftool"')
        sys.exit(1)

    # Parse and validate coordinates
    try:
        lat, lon = parse_coordinates(args.coordinates)
    except ValueError as e:
        print(f'Error: {e}')
        sys.exit(1)

    # Validate directory
    input_dir = Path(args.directory)
    if not input_dir.exists():
        print(f'Error: Directory not found: {input_dir}')
        sys.exit(1)
    if not input_dir.is_dir():
        print(f'Error: Not a directory: {input_dir}')
        sys.exit(1)

    # Find all supported media files
    media_files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS
    ]

    if not media_files:
        print('No supported media files found in the directory.')
        sys.exit(0)

    lat_label = f"{abs(lat)}° {'N' if lat >= 0 else 'S'}"
    lon_label = f"{abs(lon)}° {'E' if lon >= 0 else 'W'}"

    print(f'📍 Coordinates: {lat_label}, {lon_label}')
    print(f'📁 Directory:   {input_dir}')
    print(f'🗂️  Found {len(media_files)} file(s)')
    print()

    success_count = 0
    error_count = 0

    for media_file in sorted(media_files):
        print(f'→ {media_file.name}')
        try:
            set_gps_on_file(media_file, lat, lon)
            print('  ✅ Done')
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f'  ❌ Error: exiftool failed (exit code {e.returncode})')
            if e.stderr:
                print(f'     {e.stderr.decode().strip()}')
            error_count += 1
        except Exception as e:
            print(f'  ❌ Unexpected error: {e}')
            error_count += 1
        print()

    print('=' * 50)
    print(f'✅ Successfully updated: {success_count}')
    if error_count > 0:
        print(f'❌ Errors: {error_count}')


if __name__ == '__main__':
    main()
