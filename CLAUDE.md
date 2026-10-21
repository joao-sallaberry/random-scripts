# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A collection of standalone personal Python CLI scripts, grouped by domain:

- `multimedia/` — batch operations over a directory of photos/videos (compress, fix shot dates, set GPS, extract RAW previews, isolate files without EXIF dates). They shell out to external tools rather than using Python libraries: `ffmpeg`/`ffprobe` for videos, `exiftool` for metadata, `dcraw` for RAW files, and `notify-send` for desktop notifications.
- `finance/` — B3 (Brazilian stock exchange) data processing with pandas/openpyxl (`transactions_from_b3.py`) and an exploratory Jupyter notebook (`dfev.ipynb`).
  - `desmistificando-fii/` — `arquivar.py` + `to_audio.py`, a pipeline for the DesmistificandoFII weekly REIT report: browser-saved HTML → Markdown (one `## NN. Title` section per topic/fund, stdlib only), archived in `<RELATORIOS_DIR>/AAAA-MM-DD - Relatorio FII NN/` (`.md` with JSON-valued YAML front matter, figures copied from the browser's `<name>_files/` (or decoded from `data:` URIs, as in the 2022 reports) into `imagens/NN.ext` and linked as `![alt](imagens/NN.ext)`, and `original.html` without scripts, pointing at `imagens/`, which is valid input to regenerate with `--force`); every run rebuilds `indice.md` (editions + per-fund section links) from the archived `.md` files → one MP3 per section plus a chaptered `.m4b` (shells out to `edge-tts`, or the local `piper` with `--motor piper`, and `ffmpeg`/`ffprobe`). The code and its messages are in Portuguese.

There is no build system, test suite, or linter configured.

## Setup and running

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python <script>.py <args>
```

Multimedia scripts import `from util import ...`, so run them from inside `multimedia/` (or with `multimedia/` on `PYTHONPATH`) — e.g. `cd multimedia && python compress_video.py /path/to/videos`.

FII audio: `to_audio.py` imports `from speech import falar`, so run it from inside `finance/desmistificando-fii/` or by path (the script's own directory is on `sys.path`).

## Conventions

- Each script is self-contained: module docstring with usage examples at the top, `argparse` (or a simple `sys.argv` check in older scripts), a `main()` (except `isolate_no_creation_date.py`, which runs at module level) that iterates over the files in the given directory (non-recursive), and per-file success/error counts printed at the end.
- `compress_video.py` records the equivalent ffmpeg command in each output's `compress_settings` metadata tag (via `-movflags use_metadata_tags`). `compare_videos.py` imports `read_command_metadata` from it and uses the recorded `-ss` and `bwdif` filter to line the original up with the compressed video — keep both in sync when changing the recorded command format.
- Shared media extension sets live in `multimedia/util.py` (`VIDEO_EXTENSIONS`, `PHOTO_EXTENSIONS`, lowercase); compare against `f.suffix.lower()`. Some older scripts (`set_creation_date_from_filename.py`, `extract_raw_previews.py`, `isolate_no_creation_date.py`) still define their own extension sets — prefer `util.py` for new code.
- Scripts check external tool availability with `shutil.which(...)` before processing.
- Metadata scripts modify files in place (`exiftool -overwrite_original`); there are no backups.
- Timezone handling uses `zoneinfo`; Brazil time (`America/Sao_Paulo`) is the common default.
- When a script's CLI changes, update its module docstring usage block to match.
- `desmistificando-fii/arquivar.py` finds sections by the `Ouvir`/`Order` marker text preceding each topic; the title is right before it (`FII / TICKER / segment? / R$?` cards, where segment and price may be missing, or a text heading). If it fails with "nenhum marcador 'Ouvir'" or "HTML sem <main>", the site layout changed (or the saved file isn't the report page).
- Pronunciation lives in `finance/desmistificando-fii/speech.py`: `TICKERS` maps tickers to spoken forms (e.g. `"TEPP": "tépi"`), unknown tickers are spelled out via `LETRAS`, `SIGLAS` covers acronyms/abbreviations, and `INGLES` respells English words. Test with `python3 speech.py "frase"`. Keep the generated Markdown format stable (`# … nº NN — divulgação DD/MM/AAAA` header, `## NN. Title` sections, `Fundos:` line, `![` image lines, front matter): `to_audio.py` and the `indice.md` builder (`ler_arquivado`) parse it.
