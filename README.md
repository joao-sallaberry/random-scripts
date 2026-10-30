# random-scripts

Personal Python CLI scripts, grouped by domain:

- `multimedia/` — batch operations over photos/videos: compress, compare, fix shot dates, set GPS, extract RAW previews, isolate files without EXIF dates.
- `finance/` — B3 transaction export to CSV (`transactions_from_b3.py`).
  - `analises-fiis/` — REIT analyses: the DesmistificandoFII report archiver/audio (`desmistificando-fii/`) and Claude skills in `.claude/skills/`.

Each script has a docstring at the top with usage examples, and `--help`.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — only for the scripts with Python dependencies (see below)
- External tools, depending on the script:

| Tool | Used by |
|---|---|
| `ffmpeg`, `ffprobe` | video scripts in `multimedia/`, `to_audio.py` |
| `ffplay` | `compare_videos.py` (visual modes) |
| `exiftool` | photo/metadata scripts in `multimedia/` |
| `dcraw` | `extract_raw_previews.py` |
| `notify-send` | `compress_video.py` (desktop notification when done) |
| `yt-dlp` | `historico-fii-youtube` skill |
| `edge-tts` or `piper` | `to_audio.py` |

## Usage

Most scripts only use the standard library:

```sh
python3 multimedia/compress_video.py /path/to/videos
```

Scripts with Python dependencies declare them inline ([PEP 723](https://peps.python.org/pep-0723/)) and are run with `uv run`, which creates a cached environment for them automatically — no virtualenv to set up:

```sh
uv run finance/transactions_from_b3.py negociacao.xlsx
```

They are also executable directly (`./finance/transactions_from_b3.py ...`).

## Local configuration

Scripts that need local paths read them from an untracked `.env` next to the code. Copy the `.env.example` and fill it in:

- `finance/analises-fiis/desmistificando-fii/.env` — `RELATORIOS_DIR`
- `finance/analises-fiis/.claude/skills/historico-fii-youtube/.env` — `HISTORICO_DIR`
