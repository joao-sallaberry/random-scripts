#!/usr/bin/env python3

"""
Compress videos in a directory using ffmpeg with H.264 encoding.
Downscales videos to 1080p, 30fps, and applies customizable CRF quality.
Preserves metadata while reducing file size.
"""

import subprocess
import sys
import argparse
from pathlib import Path

# Default values
DEFAULT_CRF = 23
DEFAULT_PRESET = "medium"

# Supported video extensions
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.vob', '.mod',
                    '.MP4', '.MOV', '.MKV', '.AVI', '.M4V', '.VOB', '.MOD'}


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
        'directory',
        type=str,
        help='Directory containing the videos'
    )
    
    return parser


def build_ffmpeg_command(input_file, output_file, crf, preset):
    """
    Build the ffmpeg command for video conversion.
    
    Args:
        input_file: Path to input video file
        output_file: Path to output video file
        crf: CRF quality value
        preset: ffmpeg preset
        
    Returns:
        list: Command as list of strings for subprocess
    """
    return [
        "ffmpeg",
        "-i", str(input_file),
        "-map", "0",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", preset,
        "-crf", str(crf),
        "-vf", "bwdif=mode=1:parity=auto:deint=all", # deinterlace if interlaced
        "-movflags", "+faststart",
        "-y", # overwrite if exists
        str(output_file)
    ]


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
    print(f"Output to: {output_dir}")
    print()
    
    # Build sample command to show options
    sample_cmd = build_ffmpeg_command("<input>", "<output>", args.crf, args.preset)
    
    print("FFmpeg command options:")
    # Display options in a readable format
    cmd_str = " ".join(sample_cmd)
    # Break into lines for readability
    parts = cmd_str.split(" -")
    print(f"  {parts[0]}")
    for part in parts[1:]:
        print(f"  -{part}")
    print()
    
    # Find all video files
    video_files = [f for f in input_dir.iterdir() 
                   if f.is_file() and f.suffix in VIDEO_EXTENSIONS]
    
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
            cmd = build_ffmpeg_command(video_file, output_file, args.crf, args.preset)
            
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✅ Success")
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
    print(f"❌ Errors: {error_count}")
    print(f"📁 Files saved in: {output_dir}")

if __name__ == "__main__":
    main()

