#!/usr/bin/env python3

"""

Compress a video, or all videos in a directory, using ffmpeg with H.265 (10-bit) encoding.
Keeps original resolution and frame rate, deinterlaces when needed, and applies
customizable CRF quality. Preserves metadata (dates, GPS, camera make/model) and
file modification time while reducing file size. The equivalent ffmpeg command is
recorded in the output's "compress_settings" metadata tag.

With --crf-test, encodes only 10s (from --start) at CRF 25, 30 and 35 and stacks them
with the original in a 2x2 mosaic (original top left; a single row for vertical videos),
labeled with each CRF and its estimated size relative to the original, to pick a CRF
before compressing everything.

usage: compress_video.py [-h] [--crf CRF] [--preset PRESET] [--start START] [--end END]
                         [--overwrite] [--show-settings] [--crf-test]
                         path

Compress videos in a directory using ffmpeg

positional arguments:
  path             Video file, or directory containing the videos

options:
  -h, --help       show this help message and exit
  --crf CRF        CRF quality factor (default: 23)
  --preset PRESET  ffmpeg compression preset (default: slow)
  --start START    Start time to cut from (e.g. 01:30 or 90)
  --end END        End time to cut to (e.g. 02:45 or 165)
  --overwrite      Re-encode videos whose output already exists
  --show-settings  Only print the compress_settings tag of already compressed videos
  --crf-test       Encode 10s (from --start) at CRF 25, 30, 35 and stack them with the
                   original in a 2x2 mosaic (a row for vertical videos)

examples:
  compress_video.py --crf 20 --preset slow /path/to/videos
  compress_video.py --crf 20 /path/to/videos/IMG_1234.MOV
  compress_video.py --show-settings /path/to/videos/ff20-slow
  compress_video.py --crf-test --start 01:30 /path/to/videos/IMG_1234.MOV
"""

import subprocess
import sys
import argparse
import os
import shlex
import shutil
import tempfile
import time
from pathlib import Path
from util import VIDEO_EXTENSIONS, parse_time

# Default values
DEFAULT_CRF = 23
DEFAULT_PRESET = "slow"
AUDIO_BITRATE_PER_CHANNEL_K = 80  # 160k for stereo
COMMAND_METADATA_KEY = "compress_settings"

# --crf-test: one tile for the original and one for each CRF
CRF_TEST_VALUES = [25, 30, 35]
CRF_TEST_DURATION = 10
# Each tile keeps the original resolution up to this size on its short side, so
# 4K sources don't produce an 8K mosaic
CRF_TEST_MAX_TILE_SIZE = 1080

# Metadata copied from the original with exiftool. Track header tags (e.g. Rotation)
# are deliberately left out: ffmpeg already applies the rotation when re-encoding,
# so copying it would rotate the video twice.
EXIFTOOL_TAGS = [
    "-Keys:all",        # Apple: location, make, model, creationdate
    "-UserData:all",    # Android/others: GPS (©xyz), make, model
    "-ItemList:all",
    "-QuickTime:CreateDate",
    "-QuickTime:ModifyDate",
    "-QuickTime:TrackCreateDate",
    "-QuickTime:TrackModifyDate",
    "-QuickTime:MediaCreateDate",
    "-QuickTime:MediaModifyDate",
]


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
        '--overwrite',
        action='store_true',
        help='Re-encode videos whose output already exists'
    )
    parser.add_argument(
        '--show-settings',
        action='store_true',
        help=f'Only print the {COMMAND_METADATA_KEY} tag of already compressed videos'
    )
    parser.add_argument(
        '--crf-test',
        action='store_true',
        help=f'Encode {CRF_TEST_DURATION}s (from --start) at CRF '
             f'{", ".join(map(str, CRF_TEST_VALUES))} and stack them with the original in a 2x2 mosaic (a row for vertical videos)'
    )
    parser.add_argument(
        'path',
        type=str,
        help='Video file, or directory containing the videos'
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


def format_size(size_bytes):
    """Format a size in bytes as a human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def probe_stream(input_file, stream, entries):
    """
    Read stream entries with ffprobe.

    Args:
        input_file: Path to the video file
        stream: Stream selector (e.g. "v:0", "a:0")
        entries: Comma-separated stream entries (e.g. "codec_name,channels")

    Returns:
        dict: Entry name to value, or empty dict if the stream doesn't exist
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", stream,
        "-show_entries", f"stream={entries}",
        "-of", "default=noprint_wrappers=1",
        str(input_file)
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return {}

    info = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        info.setdefault(key, value.strip().lower())
    return info


def is_video_interlaced(input_file):
    """
    Check if a video is interlaced using ffprobe.
    """
    field_order = probe_stream(input_file, "v:0", "field_order").get("field_order")
    # 'tt', 'bb', 'tb', 'bt' indicate interlaced. 'progressive' or unknown indicate not.
    return field_order in ['tt', 'bb', 'tb', 'bt']


def build_audio_options(input_file):
    """
    Copy AAC audio as is; re-encode anything else to AAC.
    """
    audio = probe_stream(input_file, "a:0", "codec_name,channels")
    if not audio:
        return []
    if audio.get("codec_name") == "aac":
        return ["-c:a", "copy"]

    try:
        channels = int(audio.get("channels", 2))
    except ValueError:
        channels = 2
    bitrate = AUDIO_BITRATE_PER_CHANNEL_K * max(channels, 2)
    return ["-c:a", "aac", "-b:a", f"{bitrate}k"]


def build_ffmpeg_command(input_file, output_file, crf, preset, is_interlaced=False,
                         start_time=None, end_time=None, audio_options=None):
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
        audio_options: ffmpeg audio codec options

    Returns:
        list: Command as list of strings for subprocess
    """
    cmd = ["ffmpeg"]

    # Seeking before -i is fast, and still frame-accurate since we re-encode
    if start_time:
        cmd.extend(["-ss", str(start_time)])
    if end_time:
        cmd.extend(["-to", str(end_time)])

    cmd.extend([
        "-i", str(input_file),
        "-map", "0:v:0", "-map", "0:a?",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-c:v", "libx265",
        "-preset", preset,
        "-crf", str(crf),
        "-tag:v", "hvc1",  # required for playback on Apple devices
    ])

    # 10-bit avoids banding, keeps HDR (HLG) phone footage, and compresses
    # better than 8-bit even for 8-bit sources
    vf_opt = "format=yuv420p10le"
    if is_interlaced:
        vf_opt = "bwdif=mode=1:parity=auto:deint=interlaced," + vf_opt
    cmd.extend(["-vf", vf_opt])

    cmd.extend(audio_options or [])

    cmd.extend([
        "-movflags", "+faststart+use_metadata_tags",
        "-y", # overwrite if exists
        str(output_file)
    ])
    return cmd


def add_command_metadata(cmd, input_file, temp_file, output_file):
    """
    Record the equivalent ffmpeg call in the output's metadata, as if ffmpeg had
    been run directly on the original file (file names only, no directories).

    Args:
        cmd: ffmpeg command built by build_ffmpeg_command, writing to temp_file
        input_file: Path to input video file
        temp_file: Path the command actually writes to
        output_file: Final output path

    Returns:
        list: Command with the metadata option added before the output path
    """
    paths = {str(input_file): input_file.name, str(temp_file): output_file.name}
    recorded = shlex.join(paths.get(arg, arg) for arg in cmd)
    return [*cmd[:-1], "-metadata", f"{COMMAND_METADATA_KEY}={recorded}", cmd[-1]]


def copy_metadata(input_file, output_file):
    """
    Copy dates, GPS and camera metadata from the original with exiftool,
    then copy the original file modification time.

    Returns:
        bool: True if exiftool succeeded
    """
    success = True
    if shutil.which("exiftool"):
        cmd = [
            "exiftool",
            "-overwrite_original",
            "-tagsFromFile", str(input_file),
            *EXIFTOOL_TAGS,
            str(output_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠️  exiftool failed: {result.stderr.strip()}")
            success = False

    stat = input_file.stat()
    os.utime(output_file, (stat.st_atime, stat.st_mtime))
    return success


def read_command_metadata(video_file):
    """
    Read the ffmpeg command recorded by add_command_metadata.

    Returns:
        str: Recorded command, or None if the tag is missing
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", f"format_tags={COMMAND_METADATA_KEY}",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip() or None


def find_videos(path):
    """
    Get the videos to process: every video in a directory, or a single video file.

    Returns:
        tuple: (sorted list of video paths, directory the output directory goes in)
    """
    if path.is_dir():
        video_files = sorted(f for f in path.iterdir()
                             if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
        return video_files, path
    return [path], path.parent


def show_settings(path):
    """
    Print the recorded compress settings of a video, or of every video in a directory.
    """
    video_files, _ = find_videos(path)

    if not video_files:
        print("No video files found in the directory")
        return

    for video_file in video_files:
        print(f"→ {video_file.name}")
        settings = read_command_metadata(video_file)
        print(f"  {settings}" if settings else f"  (no {COMMAND_METADATA_KEY} tag)")
        print()


def probe_duration(video_file):
    """
    Get the duration of a video in seconds with ffprobe.

    Returns:
        float: Duration, or None if unknown
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def build_mosaic_command(original_file, clips, start, deinterlace, vertical, output_file):
    """
    Build the ffmpeg command that stacks the original and the test clips: original
    first, then the clips left to right, top to bottom. Horizontal videos go in a
    2x2 grid, vertical ones side by side in a single row.

    Args:
        original_file: Path to the original video
        clips: List of (label, path) for the encoded clips, in order
        start: Start time of the clips in the original, in seconds
        deinterlace: Deinterlace filter applied to the clips, also applied to the original
        vertical: Whether the video is taller than wide (after rotation)
        output_file: Path to the mosaic

    Returns:
        list: Command as list of strings for subprocess
    """
    cmd = ["ffmpeg", "-ss", str(start), "-t", str(CRF_TEST_DURATION), "-i", str(original_file)]
    for _, clip in clips:
        cmd.extend(["-i", str(clip)])

    labels = ["Original"] + [label for label, _ in clips]
    if vertical:
        scale = f"scale='min(iw,{CRF_TEST_MAX_TILE_SIZE})':-2"
        layout = "0_0|w0_0|w0+w1_0|w0+w1+w2_0"
    else:
        scale = f"scale=-2:'min(ih,{CRF_TEST_MAX_TILE_SIZE})'"
        layout = "0_0|w0_0|0_h0|w0_h0"

    graph = ""
    for i, label in enumerate(labels):
        pre = f"{deinterlace}," if i == 0 and deinterlace else ""
        graph += (
            f"[{i}:v]{pre}{scale},format=yuv420p,"
            f"drawtext=text='{label}':expansion=none:x='min(w,h)/40':y='min(w,h)/40':"
            f"fontsize='min(w,h)/20':fontcolor=white:box=1:boxcolor=black@0.6:"
            f"boxborderw='min(w,h)/80'[t{i}];"
        )
    graph += "".join(f"[t{i}]" for i in range(len(labels)))
    graph += f"xstack=inputs={len(labels)}:layout={layout}:shortest=1"

    cmd.extend([
        "-filter_complex", graph,
        "-an",
        # Near-lossless, so the mosaic's own encoding doesn't hide the differences
        "-c:v", "libx264", "-preset", "fast", "-crf", "10",
        "-movflags", "+faststart",
        "-y",
        str(output_file)
    ])
    return cmd


def crf_test(video_file, output_file, preset, start):
    """
    Encode a short clip of a video at each CRF in CRF_TEST_VALUES, and stack them
    with the original in a mosaic for visual comparison.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails
    """
    is_interlaced = is_video_interlaced(video_file)
    if is_interlaced:
        print("  ℹ️  Detected interlaced video, applying deinterlace filter")
    deinterlace = "bwdif=mode=1:parity=auto:deint=interlaced" if is_interlaced else None

    # Bitrate of the original, to estimate the size of each CRF on the whole video
    original_duration = probe_duration(video_file)
    original_rate = video_file.stat().st_size / original_duration if original_duration else None

    with tempfile.TemporaryDirectory() as temp_dir:
        clips = []
        for crf in CRF_TEST_VALUES:
            clip = Path(temp_dir) / f"crf{crf}.mp4"
            cmd = build_ffmpeg_command(
                video_file, clip, crf, preset, is_interlaced,
                start, start + CRF_TEST_DURATION, build_audio_options(video_file)
            )
            timer = ProcessingTimer()
            timer.start()
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            label = f"CRF {crf}"
            clip_duration = probe_duration(clip)
            if original_rate and clip_duration:
                ratio = clip.stat().st_size / clip_duration / original_rate * 100
                label += f" ~{ratio:.0f}%"
                estimate = f", ~{ratio:.0f}% of the original's size"
            else:
                estimate = ""
            print(f"  CRF {crf} (took {timer.get_elapsed_str()}): "
                  f"{format_size(clip.stat().st_size)}{estimate}")
            clips.append((label, clip))

        # The clips are already rotated, unlike the original, which may only have a rotation tag
        size = probe_stream(clips[0][1], "v:0", "width,height")
        vertical = int(size.get("height", 0)) > int(size.get("width", 0))

        # Write to a temporary file so an interrupted run never leaves a partial mosaic
        temp_file = Path(temp_dir) / "mosaic.mp4"
        subprocess.run(build_mosaic_command(video_file, clips, start, deinterlace, vertical, temp_file),
                       check=True, capture_output=True, text=True)
        shutil.move(temp_file, output_file)


def run_crf_test(path, args):
    """
    Run crf_test on a single video, or on every video in a directory.
    """
    video_files, base_dir = find_videos(path)
    output_dir = base_dir / f"crf-test-{args.preset}"

    if not video_files:
        print("No video files found in the directory")
        sys.exit(0)

    try:
        start = parse_time(args.start) if args.start else 0.0
    except ValueError:
        print(f"Error: Invalid start time: {args.start}")
        sys.exit(1)

    output_dir.mkdir(exist_ok=True)
    print(f"Testing CRF {', '.join(map(str, CRF_TEST_VALUES))} on {CRF_TEST_DURATION}s "
          f"from {start:g}s, preset {args.preset}")
    print(f"Output to: {output_dir}")
    print()

    success_count = 0
    skipped_count = 0
    error_count = 0

    for video_file in video_files:
        output_file = output_dir / f"{video_file.stem} [crf-test].mp4"
        if output_file.exists() and not args.overwrite:
            print(f"→ Skipping (already exists): {output_file.name}")
            print()
            skipped_count += 1
            continue

        print(f"→ Testing: {video_file.name}")
        try:
            crf_test(video_file, output_file, args.preset, start)
            print(f"  ✅ Mosaic: {output_file.name}")
            success_count += 1
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Error: ffmpeg failed with exit code {e.returncode}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")
            error_count += 1
        print()

    print("="*50)
    print(f"✅ Mosaics created: {success_count}")
    if skipped_count > 0:
        print(f"⏭️  Skipped (already exist): {skipped_count}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    print(f"📁 Files saved in: {output_dir}")

    notify_done(success_count, error_count)


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

    input_dir = Path(args.path)
    if not input_dir.exists():
        print(f"Error: Path not found: {input_dir}")
        sys.exit(1)

    if args.show_settings:
        show_settings(input_dir)
        return

    if args.crf_test:
        if args.end:
            print(f"Error: --end can't be used with --crf-test, which always encodes {CRF_TEST_DURATION}s")
            sys.exit(1)
        run_crf_test(input_dir, args)
        return

    if not shutil.which("exiftool"):
        print("Warning: exiftool not found, GPS and camera metadata may be lost")
        print()

    # Find the videos: every video in a directory, or a single file
    video_files, base_dir = find_videos(input_dir)

    if not video_files:
        print("No video files found in the directory")
        sys.exit(0)

    # Create output directory with dynamic name
    output_dir = base_dir / f"ff{args.crf}-{args.preset}"
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

    print(f"Found {len(video_files)} video file(s)")
    print()

    # Process each video
    success_count = 0
    skipped_count = 0
    error_count = 0
    larger_files = []

    for video_file in video_files:
        # Always output as .mp4, replace original extension. The preset is only in the
        # directory name, and is recorded in the compress_settings tag.
        output_name = f"[ff{args.crf}] {video_file.stem}.mp4"
        output_file = output_dir / output_name
        # Outputs from older versions of this script also had the preset in the file name
        legacy_file = output_dir / f"[ff{args.crf}-{args.preset}] {video_file.stem}.mp4"

        existing_file = next((f for f in (output_file, legacy_file) if f.exists()), None)
        if existing_file and not args.overwrite:
            print(f"→ Skipping (already exists): {existing_file.name}")
            print()
            skipped_count += 1
            continue

        # Encode to a temporary file so an interrupted run never leaves a
        # partial output that would be skipped next time
        temp_file = output_file.with_name(f"{output_file.stem}.part.mp4")

        print(f"→ Converting: {video_file.name} → {output_file.name}")

        try:
            is_interlaced = is_video_interlaced(video_file)
            if is_interlaced:
                print("  ℹ️  Detected interlaced video, applying deinterlace filter")

            cmd = build_ffmpeg_command(
                video_file, temp_file, args.crf, args.preset,
                is_interlaced, args.start, args.end,
                build_audio_options(video_file)
            )
            cmd = add_command_metadata(cmd, video_file, temp_file, output_file)
            print(f"  Running: {' '.join(cmd)}")

            timer = ProcessingTimer()
            timer.start()
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            copy_metadata(video_file, temp_file)
            temp_file.replace(output_file)

            input_size = video_file.stat().st_size
            output_size = output_file.stat().st_size
            ratio = output_size / input_size * 100
            print(f"  ✅ Success (took {timer.get_elapsed_str()}): "
                  f"{format_size(input_size)} → {format_size(output_size)} ({ratio:.0f}%)")
            if output_size >= input_size and not (args.start or args.end):
                print("  ⚠️  Output is not smaller than the original")
                larger_files.append(video_file.name)
            success_count += 1

        except subprocess.CalledProcessError as e:
            print(f"  ❌ Error: ffmpeg failed with exit code {e.returncode}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")
            temp_file.unlink(missing_ok=True)
            error_count += 1
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            temp_file.unlink(missing_ok=True)
            error_count += 1

        print()

    print("="*50)
    print(f"✅ Successfully converted: {success_count}")
    if skipped_count > 0:
        print(f"⏭️  Skipped (already exist): {skipped_count}")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    if larger_files:
        print(f"⚠️  Not smaller than the original: {', '.join(larger_files)}")
    print(f"📁 Files saved in: {output_dir}")

    notify_done(success_count, error_count)

if __name__ == "__main__":
    main()
