#!/usr/bin/env python3

"""

Compress videos in a directory using ffmpeg with H.265 encoding.
Downscales videos to 1080p, 30fps, and applies customizable CRF quality.
Preserves metadata while reducing file size.

usage: compress_video.py [-h] [--crf CRF] [--preset PRESET] [--start START] [--end END]
                         directory

Compress videos in a directory using ffmpeg

positional arguments:
  directory        Directory containing the videos

options:
  -h, --help       show this help message and exit
  --crf CRF        CRF quality factor (default: 23)
  --preset PRESET  ffmpeg compression preset (default: medium)
  --start START    Start time to cut from (e.g. 01:30 or 90)
  --end END        End time to cut to (e.g. 02:45 or 165)

example: compress_video.py --crf 18 --preset medium /path/to/videos
"""

import subprocess
import sys
import argparse
import time
from pathlib import Path

# Default values
DEFAULT_CRF = 23
DEFAULT_PRESET = "medium"

# Supported video extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.vob', '.mod'}


def setup_argument_parser():
    """
    Set up and return the argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Compress videos in a directory using ffmpeg'
    )
    parser.add_argument(
        '--crf',
        type=int,
        default=DEFAULT_CRF,
        help=f'CRF quality factor (default: {DEFAULT_CRF})'
    )
    parser.add_argument(
        '--preset',
        type=str,
        default=DEFAULT_PRESET,
        help=f'ffmpeg compression preset (default: {DEFAULT_PRESET})'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start time to cut from (e.g. 01:30 or 90)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End time to cut to (e.g. 02:45 or 165)'
    )
    parser.add_argument(
        'directory',
        type=str,
        help='Directory containing the videos'
    )
    
    return parser


class ProcessingTimer:
    """Utility class to measure and format processing time."""
    def __init__(self):
        self.start_time = None
        
    def start(self):
        self.start_time = time.time()
        
    def get_elapsed_str(self):
        if self.start_time is None:
            return "0.0s"
            
        elapsed = time.time() - self.start_time
        
        if elapsed >= 3600:
            hours, remainder = divmod(elapsed, 3600)
            mins, secs = divmod(remainder, 60)
            return f"{int(hours)}h {int(mins)}m {secs:.1f}s"
        elif elapsed >= 60:
            mins, secs = divmod(elapsed, 60)
            return f"{int(mins)}m {secs:.1f}s"
        else:
            return f"{elapsed:.1f}s"


def is_video_interlaced(input_file):
    """
    Check if a video is interlaced using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=field_order",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_file)
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        output = result.stdout.strip().lower()
        
        # 'tt', 'bb', 'tb', 'bt' indicate interlaced. 'progressive' or unknown indicate not.
        return output in ['tt', 'bb', 'tb', 'bt']
    except subprocess.CalledProcessError:
        return False


def build_ffmpeg_command(input_file, output_file, crf, preset, is_interlaced=False, start_time=None, end_time=None):
    """
    Build the ffmpeg command for video conversion.
    
    Args:
        input_file: Path to input video file
        output_file: Path to output video file
        crf: CRF quality value
        preset: ffmpeg preset
        is_interlaced: Whether the video is interlaced
        start_time: Optional start time to cut from
        end_time: Optional end time to cut to
        
    Returns:
        list: Command as list of strings for subprocess
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-map", "0", "-map", "-0:d",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-c:v", "libx265",
        "-pix_fmt", "yuv420p",
        "-color_range", "tv",
        "-preset", preset,
        "-crf", str(crf)
    ]
    
    vf_opt = "scale=in_range=pc:out_range=tv,format=yuv420p"
    if is_interlaced:
        vf_opt = "bwdif=mode=1:parity=auto:deint=interlaced," + vf_opt
    cmd.extend(["-vf", vf_opt])

    if start_time:
        cmd.extend(["-ss", str(start_time)])
    if end_time:
        cmd.extend(["-to", str(end_time)])
    
    cmd.extend([
        "-movflags", "+faststart",
        "-y", # overwrite if exists
        str(output_file)
    ])
    return cmd


def notify_done(success_count, error_count):
    """Send a desktop notification and play a sound when done."""
    message = f"Successfully converted: {success_count}\nErrors: {error_count}"
    
    # Try notify-send for desktop notification
    try:
        subprocess.run(["notify-send", "-a", "Video Compressor", "Compression Complete", message], check=False)
    except Exception:
        pass
        
    # Try to play a sound
    try:
        sound_file = "/usr/share/sounds/freedesktop/stereo/complete.oga"
        if Path(sound_file).exists():
            subprocess.run(["paplay", sound_file], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Fallback to terminal bell
            print('\a', end='', flush=True)
    except Exception:
        print('\a', end='', flush=True)


def main():
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Validate directory
    input_dir = Path(args.directory)
    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {input_dir}")
        sys.exit(1)
    
    # Create output directory with dynamic name
    output_dir = input_dir / f"ff{args.crf}-{args.preset}"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Converting videos from: {input_dir}")
    print(f"CRF: {args.crf}")
    print(f"Preset: {args.preset}")
    if args.start:
        print(f"Start time: {args.start}")
    if args.end:
        print(f"End time: {args.end}")
    print(f"Output to: {output_dir}")
    print()
    
    # Find all video files
    video_files = [f for f in input_dir.iterdir() 
                   if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    
    if not video_files:
        print("No video files found in the directory")
        sys.exit(0)
    
    print(f"Found {len(video_files)} video file(s)")
    print()
    
    # Process each video
    success_count = 0
    error_count = 0
    
    for video_file in video_files:
        # Always output as .mp4, replace original extension
        output_name = f"[ff{args.crf}-{args.preset}] {video_file.stem}.mp4"
        output_file = output_dir / output_name
        
        print(f"→ Converting: {video_file.name} → {output_file.name}")
        
        try:
            is_interlaced = is_video_interlaced(video_file)
            if is_interlaced:
                print("  ℹ️  Detected interlaced video, applying deinterlace filter")
                
            cmd = build_ffmpeg_command(
                video_file, output_file, args.crf, args.preset, 
                is_interlaced, args.start, args.end
            )
            print(f"  Running: {' '.join(cmd)}")
            
            timer = ProcessingTimer()
            timer.start()
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            print(f"  ✅ Success (took {timer.get_elapsed_str()})")
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Error: ffmpeg failed with exit code {e.returncode}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")
            error_count += 1
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            error_count += 1
        
        print()
    
    print("="*50)
    print(f"✅ Successfully converted: {success_count}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    print(f"📁 Files saved in: {output_dir}")
    
    notify_done(success_count, error_count)

if __name__ == "__main__":
    main()

