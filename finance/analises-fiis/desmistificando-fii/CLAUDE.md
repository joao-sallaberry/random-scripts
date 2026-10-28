# CLAUDE.md

Pipeline for the DesmistificandoFII weekly REIT report: browser-saved HTML → archived Markdown (`arquivar.py`) → audio (`to_audio.py`). Stdlib only, except for the TTS tools `to_audio.py` shells out to. The code and its messages are in Portuguese.

## Scripts

- Machine-specific settings live in the untracked `.env` (template: `.env.example`), read by `config.py`; an environment variable of the same name wins. `RELATORIOS_DIR` is the archive folder, the default for `arquivar.py --destino`, `verificar.py` and `buscar.py`. Never commit local paths or other details of the user's environment: put them in `.env` and refer to them by variable name.
- `arquivar.py [html|dir ...] [--destino DIR] [--force]` archives into `<RELATORIOS_DIR>/AAAA-MM-DD - Relatorio FII NN/`:
  - `Relatorio FII NN - AAAA-MM-DD.md`, with JSON-valued YAML front matter (`edicao`, `divulgacao`, `periodo`, `analista`, `fundos`) and one `## NN. Title` section per topic or fund.
  - `imagens/NN.ext`, copied from the browser's `<name>_files/` or decoded from `data:` URIs (2022), and linked as `![alt](imagens/NN.ext)`.
  - `original.html`, without scripts and pointing at `imagens/`. It is valid input to regenerate with `--force`.
  - Every run rebuilds `indice.md` (an editions table plus per-fund section links) from the archived `.md` files. With no args, it only rebuilds the index.
  - An edition that is already archived is skipped unless `--force` is given.
- `to_audio.py` writes one MP3 per section or a chaptered `.m4b`. It shells out to `edge-tts` (default), or to the local `piper` with `--motor piper`, plus `ffmpeg`/`ffprobe`. It imports `from speech import falar`, so run it from this directory or by path.
- `speech.py` handles pronunciation:
  - `TICKERS` maps tickers to spoken forms, and unknown tickers are spelled out via `LETRAS`, including a class suffix like `FIIP11B`.
  - `SIGLAS` covers acronyms and abbreviations; `INGLES` respells English words.
  - Test with `python3 speech.py "frase"`.
- The `resumo-fii` skill lives in the parent folder (`analises-fiis/.claude/skills/resumo-fii/`, run Claude from `analises-fiis/`). It summarizes a fund's recent analyses from the archived `.md` files, the main source, plus the `historico-fii-youtube` histories. Its `buscar.py` reads the index's "Por fundo" entries and the `## NN. Title` sections, so keep it in sync with that format. It loads this folder's `config.py` by path.
- If `edge-tts` fails with 403, upgrade it with `uv tool upgrade edge-tts`.

- `README.md` (pt-BR) introduces the folder's tools and teaches how to use them. When a user-facing feature or option changes, update it too. Keep internal decisions and maintenance details (parsing rules, pronunciation dictionaries, regression checks) here, not there.

## Parsing

- Sections are found by the `Ouvir`/`Order` marker text preceding each topic. The title is right before the marker:
  - fund cards `FII / TICKER / segment? / R$ price?` (segment and price may be missing; one section can have several cards), or
  - a text heading, or
  - only an image (2025 nº 29), which goes into the body and gets the title "Sem título".
- "Fundos abordados" lists cards before the first section. In single-section reports it is glued to the section's cards, and the backward card chain stops at a repeated ticker. A text title right after a price-less card is not taken as its segment (`TITULOS`).
- Final sections are Carteira Recomendada, Retornos Nominais and Disclaimer. Extraordinary reports may have no carteira; they end at the Disclaimer.
- If it fails with "nenhum marcador 'Ouvir'" or "HTML sem <main>", the site layout changed, or the saved file isn't the report page.
- Keep the generated Markdown format stable, because `to_audio.py` and the index builder (`ler_arquivado`) parse it:
  - the `# … nº NN — divulgação DD/MM/AAAA` header;
  - `## NN. Title` sections;
  - the `Fundos: TICKER (segmento, R$ x) · …` lines, including an empty `()`;
  - `![` image lines and `[Imagem não salva com a página]` placeholders;
  - the front matter.

## Sources and archiving workflow

- The user saves the pages with the browser into a downloads folder, one subfolder per year. Files are named `relatorio-semanal-N-*.html` or `relatorio-FIIS-N-DD-MM-AAAA.html`, each with its `_files/` folder. Edition numbers restart every year, and the number in the file name may be wrong (2022 `-79.html` is edition 49).
- The reports are paid content. They stay outside the git repo; never commit them.
- Before archiving a new batch:
  1. Check the sources:
     - nothing modified in the last minute (`find -mmin -1`), since the browser may still be saving;
     - every `.html` has its `_files/` and contains `</main>`;
     - there are no gaps in the edition numbers.
  2. Do a trial run with `--destino` in the scratchpad.
  3. Run `python3 verificar.py <trial dir> --curtas 150` on the trial output. It checks:
     - broken image links and leftover `data:` URIs;
     - stray `FII`, `##` or `###` lines and invisible characters;
     - empty, `R$…`, numeric or overlong section titles;
     - that every `.md` parses with `to_audio.py`.

     It exits 1 on findings. On the real archive, the known leftovers are the 2022 nº 40 image placeholder and lone tickers that are author subheadings.
  4. After any parser change, regenerate the whole archive from its `original.html` files into the scratchpad (`python3 arquivar.py <RELATORIOS_DIR>/*/original.html --destino <tmp>`), then run `python3 verificar.py <tmp> --comparar <RELATORIOS_DIR>`. The `.md` files must be identical except for the intended fix.
  5. Only then archive into the real destination.
- Don't `--force` editions that are already archived just because they were downloaded again. A re-saved page carries that day's fund quotes and may lose chart labels, so the archived copy, saved near publication, is the better one.

## Known content quirks (not parser bugs)

- Recurring columns: "1 ano no Tibet", "Destaques da Semana", "Fundos Passivos". Some reports have a section 02 titled "Carteira Recomendada", which is the analyst's weekly note; the table is still at the end.
- Authors write tickers as plain-text subheadings inside a section (e.g. 2022 nº 43 RECT11, 2026 nº 12, nº 25).
- Extraordinary editions have only a few sections, odd periods ("09/02 a 09/02") or shared dates (2025 nº 46 and 47 are both 26/10). Disclaimers may read "Acesso restrito à assinantes" or "null". Some fund sections are just one sentence.
- 2022 nº 40 has one image hosted on Evernote that returns 403, so it is archived as a placeholder.
- In reports that reuse the same embedded image (2022 nº 45, 52), regenerating may point `original.html` at a different copy. The `.md` is unaffected.
