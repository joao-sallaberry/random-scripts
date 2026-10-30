# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A collection of standalone personal Python CLI scripts, grouped by domain:

- `multimedia/` — batch operations over a directory of photos/videos (compress, fix shot dates, set GPS, extract RAW previews, isolate files without EXIF dates). They shell out to external tools rather than using Python libraries: `ffmpeg`/`ffprobe` for videos, `exiftool` for metadata, `dcraw` for RAW files, and `notify-send` for desktop notifications.
- `finance/` — B3 (Brazilian stock exchange) data processing with pandas/openpyxl (`transactions_from_b3.py`).
  - `analises-fiis/` — REIT analyses. Run Claude from `finance/analises-fiis/` so its skills (`.claude/skills/`) load.
    - `desmistificando-fii/` — `arquivar.py` + `to_audio.py` (+ `verificar.py`): the DesmistificandoFII weekly REIT report, browser-saved HTML → archived Markdown with images and an index → audio. See `finance/analises-fiis/desmistificando-fii/CLAUDE.md`.
    - `resumo-fii` skill: summarizes a fund from the archived reports (the main source) plus the YouTube histories below. Its `buscar.py` loads both `config.py` files by path (`desmistificando-fii/config.py` and the `historico-fii-youtube` one) and parses the history format (`### dd/mm/aaaa:` headings, `| dd/mm/aaaa |` table rows) to cut by period.
    - `historico-fii-youtube` skill: per-fund, per-channel history (summary + sentiment) of REIT YouTube videos, from auto-captions via `yt-dlp`. Channels live in `CANAIS` in `buscar_videos.py` (keep the skill's `README.md` table in sync). Histories go to `<HISTORICO_DIR>/<channel slug>/<BASE>.md`, outside the repo; the script finds already-covered videos by the `watch?v=<id>` links in the `### dd/mm/aaaa: [title](url)` headings, so keep that format in sync with `SKILL.md`. `glossario.md` maps auto-caption misspellings to correct names ("(confirmado)" = user-confirmed).

There is no build system, test suite, or linter configured.

## Setup and running

There is no shared virtualenv or `requirements.txt`. Most scripts use only the standard library and run with `python3 <dir>/<script>.py <args>`. Scripts that need third-party packages (`transactions_from_b3.py`) declare them in a PEP 723 `# /// script` block under a `#!/usr/bin/env -S uv run --script` shebang, and run with `uv run <dir>/<script>.py <args>`. A new third-party dependency goes in that script's block, never in a global file.

Multimedia scripts import `from util import ...`; this works from any directory, since Python puts the script's own directory on `sys.path`.

## Conventions

- Each script is self-contained: module docstring with usage examples at the top, `argparse` (or a simple `sys.argv` check in older scripts), a `main()` (except `isolate_no_creation_date.py`, which runs at module level) that iterates over the files in the given directory (non-recursive), and per-file success/error counts printed at the end.
- `compress_video.py` records the equivalent ffmpeg command in each output's `compress_settings` metadata tag (via `-movflags use_metadata_tags`). `compare_videos.py` imports `read_command_metadata` from it and uses the recorded `-ss` and `bwdif` filter to line the original up with the compressed video — keep both in sync when changing the recorded command format.
- Shared media extension sets live in `multimedia/util.py` (`VIDEO_EXTENSIONS`, `PHOTO_EXTENSIONS`, lowercase); compare against `f.suffix.lower()`. Some older scripts (`set_creation_date_from_filename.py`, `extract_raw_previews.py`, `isolate_no_creation_date.py`) still define their own extension sets — prefer `util.py` for new code.
- Scripts check external tool availability with `shutil.which(...)` before processing.
- Metadata scripts modify files in place (`exiftool -overwrite_original`); there are no backups.
- Timezone handling uses `zoneinfo`; Brazil time (`America/Sao_Paulo`) is the common default.
- When a script's CLI changes, update its module docstring usage block to match.
- Never commit local paths or other details of the user's environment (home directory, download folders). Put them in an untracked `.env` next to the code that reads it, with a committed `.env.example`, and use generic paths in usage examples. `finance/analises-fiis/desmistificando-fii/.env` has `RELATORIOS_DIR`; `finance/analises-fiis/.claude/skills/historico-fii-youtube/.env` has `HISTORICO_DIR`.
