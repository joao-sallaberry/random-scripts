#!/usr/bin/env python3

"""
Compare a compressed video against its original, visually (with ffplay) or with SSIM.
If the compressed video has the compress_settings tag written by compress_video.py,
its cut (-ss) and deinterlace filter are applied to the original too, so both line up.

Modes:
    side   Both videos side by side, scaled down to fit the screen (default)
    split  Left half from the original, right half from the compressed, at full resolution
    diff   Amplified difference between both (black = identical, bright = lost detail)
    ssim   SSIM score (1.0 = identical) and the worst frame, without playback

usage: compare_videos.py [-h] [--mode {side,split,diff,ssim}] [--start START]
                         [--duration DURATION] [--height HEIGHT]
                         original compressed

example: compare_videos.py IMG_1234.MOV "ff23-slow/[ff23] IMG_1234.mp4" --mode split --start 01:30

ffplay keys: space = pause, s = next frame, f = fullscreen, ←/→ = seek 10s, q = quit
"""

import subprocess
import sys
import argparse
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from compress_video import read_command_metadata

MODES = ["side", "split", "diff", "ssim"]
DEFAULT_MODE = "side"
DEFAULT_SIDE_HEIGHT = 720
DIFF_AMPLIFICATION = 8


def setup_argument_parser():
    """
    Set up and return the argument parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Compare a compressed video against its original',
        epilog='Examples:\n'
               '  %(prog)s IMG_1234.MOV "ff23-slow/[ff23] IMG_1234.mp4"\n'
               '  %(prog)s IMG_1234.MOV "ff23-slow/[ff23] IMG_1234.mp4" --mode diff --start 01:30\n'
               '  %(prog)s IMG_1234.MOV "ff23-slow/[ff23] IMG_1234.mp4" --mode ssim\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'original',
        type=str,
        help='Original video'
    )
    parser.add_argument(
        'compressed',
        type=str,
        help='Compressed video'
    )
    parser.add_argument(
        '--mode',
        choices=MODES,
        default=DEFAULT_MODE,
        help=f'Comparison mode (default: {DEFAULT_MODE})'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start time in the compressed video (e.g. 01:30 or 90)'
    )
    parser.add_argument(
        '--duration',
        type=str,
        help='Duration to compare (e.g. 10 or 00:30)'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=DEFAULT_SIDE_HEIGHT,
        help=f'Height of each video in side mode (default: {DEFAULT_SIDE_HEIGHT})'
    )

    return parser


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


def get_recorded_options(compressed_file):
    """
    Get the cut start and deinterlace filter from the compress_settings tag.

    Returns:
        tuple: (start seconds, deinterlace filter or None)
    """
    recorded = read_command_metadata(compressed_file)
    if not recorded:
        return 0.0, None

    args = shlex.split(recorded)
    options = dict(zip(args, args[1:]))

    start = parse_time(options["-ss"]) if "-ss" in options else 0.0
    # Keep only the deinterlace part, the pixel format conversion doesn't matter here
    filters = options.get("-vf", "").split(",")
    deinterlace = next((f for f in filters if f.startswith("bwdif")), None)
    return start, deinterlace


def build_filter_graph(mode, deinterlace, height):
    """
    Build the ffmpeg filter graph for the comparison.

    Input 0 is the original, input 1 the compressed. The compressed video is scaled
    to the original's size so both can be compared pixel by pixel.

    Returns:
        str: Filter graph
    """
    ref_filters = f"{deinterlace}," if deinterlace else ""
    graph = (
        f"[0:v]{ref_filters}format=yuv420p,split[a][aref];"
        f"[1:v][aref]scale=rw:rh,format=yuv420p[b];"
    )

    if mode == "split":
        graph += (
            "[a]crop=iw/2:ih:0:0[l];[b]crop=iw/2:ih:iw/2:0[r];"
            "[l][r]hstack=shortest=1,"
            "drawbox=x=iw/2-1:y=0:w=2:h=ih:color=white@0.5:t=fill"
        )
    elif mode == "side":
        graph += (
            f"[a]scale=-2:{height}[a2];[b]scale=-2:{height}[b2];"
            "[a2][b2]hstack=shortest=1"
        )
    elif mode == "diff":
        graph += (
            "[a]format=gray[ag];[b]format=gray[bg];"
            f"[ag][bg]blend=all_mode=difference:shortest=1,lutyuv=y=val*{DIFF_AMPLIFICATION}"
        )
    return graph


def build_input_args(original_file, compressed_file, start, recorded_start, duration):
    """
    Build the ffmpeg input arguments, seeking both videos to the same moment.

    Returns:
        list: ffmpeg arguments for both inputs
    """
    args = []
    original_start = start + recorded_start
    if original_start:
        args.extend(["-ss", str(original_start)])
    if duration:
        args.extend(["-t", duration])
    args.extend(["-i", str(original_file)])

    if start:
        args.extend(["-ss", str(start)])
    if duration:
        args.extend(["-t", duration])
    args.extend(["-i", str(compressed_file)])
    return args


def play(input_args, graph, title):
    """
    Render the comparison with ffmpeg and play it with ffplay.
    """
    ffmpeg_cmd = [
        "ffmpeg", "-v", "error",
        *input_args,
        "-filter_complex", graph,
        "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-f", "matroska", "-"
    ]
    ffplay_cmd = ["ffplay", "-v", "error", "-autoexit", "-window_title", title, "-"]

    ffmpeg = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)
    try:
        subprocess.run(ffplay_cmd, stdin=ffmpeg.stdout)
    except KeyboardInterrupt:
        pass
    finally:
        # Closing ffplay early leaves ffmpeg writing to a broken pipe
        ffmpeg.stdout.close()
        ffmpeg.terminate()
        ffmpeg.wait()


def get_frame_rate(video_file):
    """
    Get the average frame rate of a video with ffprobe.

    Returns:
        float: Frames per second, or None if unknown
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    num, _, den = result.stdout.strip().partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return None


def format_time(seconds):
    """Format seconds as MM:SS.s"""
    mins, secs = divmod(seconds, 60)
    return f"{int(mins):02d}:{secs:04.1f}"


def compute_ssim(input_args, graph, compressed_file, start):
    """
    Compute the SSIM between both videos and report the overall and worst frame scores.
    """
    with tempfile.NamedTemporaryFile(suffix=".log") as stats:
        graph += f"[b][a]ssim=shortest=1:stats_file={stats.name}"
        cmd = ["ffmpeg", "-hide_banner", *input_args, "-filter_complex", graph, "-f", "null", "-"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: ffmpeg failed with exit code {result.returncode}")
            print(result.stderr.strip())
            sys.exit(1)

        # Per-frame lines look like "n:12 Y:0.98 U:0.99 V:0.99 All:0.985 (18.2)"
        frames = re.findall(r"n:(\d+) .*?All:([\d.]+)", Path(stats.name).read_text())

    summary = re.search(r"All:([\d.]+) \(([\d.]+|inf)\)", result.stderr)
    if not summary or not frames:
        print("Error: could not read SSIM from ffmpeg output")
        sys.exit(1)

    print(f"SSIM: {float(summary.group(1)):.4f} ({summary.group(2)} dB)")

    worst_frame, worst_ssim = min(((int(n), float(s)) for n, s in frames), key=lambda f: f[1])
    fps = get_frame_rate(compressed_file)
    worst_at = f" at {format_time(start + (worst_frame - 1) / fps)}" if fps else ""
    print(f"Worst frame: {worst_ssim:.4f} (frame {worst_frame}{worst_at})")


def main():
    parser = setup_argument_parser()
    args = parser.parse_args()

    original_file = Path(args.original)
    compressed_file = Path(args.compressed)
    for video_file in (original_file, compressed_file):
        if not video_file.is_file():
            print(f"Error: File not found: {video_file}")
            sys.exit(1)

    required_tools = ["ffmpeg", "ffprobe"] + ([] if args.mode == "ssim" else ["ffplay"])
    for tool in required_tools:
        if not shutil.which(tool):
            print(f"Error: {tool} is not installed")
            sys.exit(1)

    try:
        start = parse_time(args.start) if args.start else 0.0
    except ValueError:
        print(f"Error: Invalid start time: {args.start}")
        sys.exit(1)

    recorded_start, deinterlace = get_recorded_options(compressed_file)
    if recorded_start:
        print(f"ℹ️  Compressed video was cut at {format_time(recorded_start)}, seeking original to match")
    if deinterlace:
        print("ℹ️  Compressed video was deinterlaced, applying the same filter to the original")

    input_args = build_input_args(original_file, compressed_file, start, recorded_start, args.duration)
    graph = build_filter_graph(args.mode, deinterlace, args.height)

    if args.mode == "ssim":
        print("Computing SSIM...")
        compute_ssim(input_args, graph, compressed_file, start)
    else:
        print(f"Playing {args.mode} comparison: {original_file.name} | {compressed_file.name}")
        play(input_args, graph, f"{args.mode}: {original_file.name} | {compressed_file.name}")


if __name__ == "__main__":
    main()
