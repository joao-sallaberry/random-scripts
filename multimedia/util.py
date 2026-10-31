"""
Shared constants and utilities for multimedia scripts.
"""

VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.vob', '.mod'}
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.dng', '.raw'}


def parse_time(value):
    """
    Parse an ffmpeg-style time ("90", "01:30", "1:02:03.5") into seconds.

    Raises:
        ValueError: If the value is not a valid time
    """
    seconds = 0.0
    for part in value.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds
