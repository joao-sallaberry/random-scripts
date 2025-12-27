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
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v', '.MP4', '.MOV', '.MKV', '.AVI', '.M4V'}

def main():
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
        output_file = output_dir / f"[ff{args.crf}-{args.preset}] {video_file.name}"
        
        print(f"→ Converting: {video_file.name} → {output_file.name}")
        
        try:
            cmd = [
                "ffmpeg",
                "-i", str(video_file),
                "-map_metadata", "0",
                "-c:v", "libx264",
                "-preset", args.preset,
                "-crf", str(args.crf),
                "-vf", "scale='if(gt(iw,ih),-2,1080)':'if(gt(ih,iw),-2,1080)',fps=30",
                "-c:a", "aac",
                "-b:a", "160k",
                "-movflags", "+faststart",
                "-y",  # Overwrite if exists
                str(output_file)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"  ✅ Success")
            success_count += 1
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Error: {e}")
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

