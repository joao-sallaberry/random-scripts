#!/usr/bin/env python3

"""
Android share target (via Termux) that sets the shot date of a shared video or photo.

When a file is shared to Termux, Termux copies it to ~/downloads and runs
~/bin/termux-file-editor with its path. This script is meant to be that program:
it opens Android's date and time pickers (termux-dialog), sets the date with
change_shot_date.py (in the phone's timezone), and reopens the share menu with
the updated file (termux-share), so it can be sent on to Google Photos.

Requires the Termux:API app and, inside Termux:
    pkg install python ffmpeg exiftool termux-api
    pip install tzdata   # Termux has no system timezone database for zoneinfo

Setup (in Termux, after cloning the repository to ~/random-scripts):
    mkdir -p ~/bin
    rm -f ~/bin/termux-file-editor
    printf '#!/data/data/com.termux/files/usr/bin/sh\nexec python3 "$HOME/random-scripts/multimedia/termux_share_date.py" "$@"\n' > ~/bin/termux-file-editor
    chmod +x ~/bin/termux-file-editor

    A wrapper rather than a symlink to this file: when Termux runs termux-file-editor
    from the share menu, it doesn't resolve this file's "#!/usr/bin/env python3" shebang
    (fails with "env: ...: No such file or directory").

Usage:
    Share a video or photo from any app → Termux → pick the date and time.
    It can also be run by hand:
        python3 termux_share_date.py ~/downloads/video.mp4
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHANGE_SHOT_DATE = Path(__file__).resolve().parent / "change_shot_date.py"


def fail(message):
    """Print an error and wait for Enter, so the Termux session doesn't close before it's read."""
    print(f"❌ {message}")
    input("Press Enter to close...")
    sys.exit(1)


def dialog(widget, *extra):
    """
    Open a termux-dialog widget and return the text the user chose.

    Returns:
        str or None: The chosen value, or None if the dialog was cancelled
    """
    result = subprocess.run(
        ["termux-dialog", widget, *extra],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(f"termux-dialog failed (is the Termux:API app installed?)\n{result.stderr}")
    # code -2 is the "Cancel" button; an empty text is a dismissed dialog
    if data.get("code") == -2 or not data.get("text"):
        return None
    return data["text"].strip()


def phone_timezone():
    """Return the phone's IANA timezone (e.g. America/Sao_Paulo), defaulting to Brazil time."""
    result = subprocess.run(
        ["getprop", "persist.sys.timezone"],
        capture_output=True, text=True
    )
    return result.stdout.strip() or "America/Sao_Paulo"


def main():
    """Main entry point for the script."""
    # Keep our messages in order with change_shot_date.py's output
    sys.stdout.reconfigure(line_buffering=True)

    if len(sys.argv) != 2:
        fail("Usage: termux_share_date.py <file>")

    input_file = Path(sys.argv[1])
    if not input_file.is_file():
        fail(f"File not found: {input_file}")

    if shutil.which("termux-dialog") is None:
        fail("termux-dialog not found. Run: pkg install termux-api")

    print(f"🎬 {input_file.name}")

    date = dialog("date", "-d", "yyyy-MM-dd")
    if date is None:
        fail("Cancelled")
    time = dialog("time")
    if time is None:
        fail("Cancelled")

    match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", time)
    if not match:
        fail(f"Unexpected time from the picker: {time}")
    hours, minutes = (int(g) for g in match.groups())
    timezone = phone_timezone()
    new_date = f"{date}T{hours:02d}:{minutes:02d}:00"

    # --timezone is given, so change_shot_date.py doesn't need prompt_toolkit
    # and runs with plain python, without uv
    result = subprocess.run([
        sys.executable, str(CHANGE_SHOT_DATE), str(input_file),
        "--set-date", new_date, "--timezone", timezone
    ])
    output_file = input_file.parent / "updated" / input_file.name
    if result.returncode != 0 or not output_file.is_file():
        fail("change_shot_date.py failed")

    print(f"📤 Sharing {output_file.name} ({new_date}, {timezone})")
    subprocess.run(["termux-share", "-a", "send", str(output_file)], check=True)

    # The share copy in ~/downloads is no longer needed. The updated file is kept:
    # the app it's shared to may still be reading it.
    input_file.unlink()


if __name__ == "__main__":
    main()
