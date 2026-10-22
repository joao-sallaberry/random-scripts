# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A collection of standalone personal Python CLI scripts, grouped by domain:

- `multimedia/` — batch operations over a directory of photos/videos (compress, fix shot dates, set GPS, extract RAW previews, isolate files without EXIF dates). They shell out to external tools rather than using Python libraries: `ffmpeg`/`ffprobe` for videos, `exiftool` for metadata, `dcraw` for RAW files, and `notify-send` for desktop notifications.
- `finance/` — B3 (Brazilian stock exchange) data processing with pandas/openpyxl (`transactions_from_b3.py`) and an exploratory Jupyter notebook (`dfev.ipynb`).
  - `desmistificando-fii/` — `arquivar.py` + `to_audio.py` (+ `verificar.py`): the DesmistificandoFII weekly REIT report, browser-saved HTML → archived Markdown with images and an index → audio. See `finance/desmistificando-fii/CLAUDE.md`.

There is no build system, test suite, or linter configured.

## Setup and running

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python <script>.py <args>
```

Multimedia scripts import `from util import ...`, so run them from inside `multimedia/` (or with `multimedia/` on `PYTHONPATH`) — e.g. `cd multimedia && python compress_video.py /path/to/videos`.

## Conventions

- Each script is self-contained: module docstring with usage examples at the top, `argparse` (or a simple `sys.argv` check in older scripts), a `main()` (except `isolate_no_creation_date.py`, which runs at module level) that iterates over the files in the given directory (non-recursive), and per-file success/error counts printed at the end.
- `compress_video.py` records the equivalent ffmpeg command in each output's `compress_settings` metadata tag (via `-movflags use_metadata_tags`). `compare_videos.py` imports `read_command_metadata` from it and uses the recorded `-ss` and `bwdif` filter to line the original up with the compressed video — keep both in sync when changing the recorded command format.
- Shared media extension sets live in `multimedia/util.py` (`VIDEO_EXTENSIONS`, `PHOTO_EXTENSIONS`, lowercase); compare against `f.suffix.lower()`. Some older scripts (`set_creation_date_from_filename.py`, `extract_raw_previews.py`, `isolate_no_creation_date.py`) still define their own extension sets — prefer `util.py` for new code.
- Scripts check external tool availability with `shutil.which(...)` before processing.
- Metadata scripts modify files in place (`exiftool -overwrite_original`); there are no backups.
- Timezone handling uses `zoneinfo`; Brazil time (`America/Sao_Paulo`) is the common default.
- When a script's CLI changes, update its module docstring usage block to match.
