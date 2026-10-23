"""Encontra os vídeos de um canal sobre um fundo que ainda não estão no histórico e salva as transcrições.

Uso:
    python3 buscar_videos.py --canais
    python3 buscar_videos.py JSRE11 --canal fiicaesperto --out /tmp/transcricoes
    python3 buscar_videos.py JSRE11 --canal liberdade-e-logo-ali --historico /caminho/JSRE.md --out /tmp/transcricoes

Lista vídeos, lives e shorts do canal com o yt-dlp, fica com os que têm o ticker no título,
descarta os que já aparecem no histórico (pelo ID nos links) e grava um <data>_<id>.txt por
vídeo novo em --out (cabeçalho com canal, título, data, duração e URL, depois o texto da legenda).
O histórico padrão é <HISTORICO_DIR>/<canal>/<BASE>.md, com HISTORICO_DIR do .env ao lado deste
script e BASE o ticker sem o sufixo numérico (JSRE11 → JSRE.md). Imprime um JSON com os vídeos
novos, do mais antigo para o mais novo. --canais lista os canais conhecidos.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import HISTORICO_DIR  # noqa: E402

CANAIS = {
    "fiicaesperto": ("FIIcaEsperto", "https://www.youtube.com/channel/UCOe1sCwSXRf-clKYdmgO1Kw"),
    "liberdade-e-logo-ali": ("Liberdade é Logo Ali (Eric Leonardo)", "https://www.youtube.com/channel/UCOn6-uNuXeXJqmbywtfBgdQ"),
}
ABAS = ("videos", "streams", "shorts")
VIDEO_ID = re.compile(r"(?:watch\?v=|youtu\.be/|shorts/)([\w-]{11})")


def listar_canal(url_canal, ticker):
    achados = {}
    for aba in ABAS:
        r = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s", f"{url_canal}/{aba}"],
            capture_output=True, text=True,
        )
        for linha in r.stdout.splitlines():
            video_id, _, titulo = linha.partition("\t")
            if ticker.lower() in titulo.lower():
                achados[video_id] = titulo
    return achados


def vtt_para_texto(vtt):
    linhas, vistas = [], set()
    for linha in vtt.splitlines():
        if not linha.strip() or linha.startswith(("WEBVTT", "Kind:", "Language:")) or "-->" in linha:
            continue
        linha = re.sub(r"<[^>]*>", "", linha).strip()
        if linha and linha not in vistas:
            vistas.add(linha)
            linhas.append(linha)
    return " ".join(linhas)


def baixar_transcricao(video_id, pasta):
    url = f"https://www.youtube.com/watch?v={video_id}"
    r = subprocess.run(
        ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
         "--sub-langs", "pt-orig,pt", "--sub-format", "vtt", "--no-simulate",
         "--print", "%(upload_date)s\t%(duration_string)s\t%(title)s",
         "-o", str(pasta / f"{video_id}.%(ext)s"), url],
        capture_output=True, text=True,
    )
    data, duracao, titulo = (r.stdout.strip().splitlines() or ["\t\t"])[-1].split("\t", 2)
    legendas = sorted(pasta.glob(f"{video_id}.pt-orig.vtt")) or sorted(pasta.glob(f"{video_id}.pt*.vtt"))
    texto = vtt_para_texto(legendas[0].read_text(encoding="utf-8")) if legendas else ""
    return {"id": video_id, "url": url, "titulo": titulo, "data": data,
            "duracao": duracao, "tem_legenda": bool(texto), "texto": texto}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ticker", nargs="?", help="ticker como aparece nos títulos, ex. JSRE11")
    ap.add_argument("--canal", choices=CANAIS, help="slug do canal (veja --canais)")
    ap.add_argument("--canais", action="store_true", help="lista os canais conhecidos e sai")
    ap.add_argument("--historico", type=Path, help="padrão: <HISTORICO_DIR>/<canal>/<BASE>.md")
    ap.add_argument("--out", type=Path, help="pasta onde gravar as transcrições")
    args = ap.parse_args()

    if args.canais:
        print(json.dumps({slug: {"nome": nome, "url": url} for slug, (nome, url) in CANAIS.items()},
                         ensure_ascii=False, indent=2))
        return
    if not (args.ticker and args.canal and args.out):
        ap.error("informe TICKER, --canal e --out")
    if not shutil.which("yt-dlp"):
        sys.exit("yt-dlp não encontrado")
    historico = args.historico
    if historico is None:
        if HISTORICO_DIR is None:
            ap.error("defina HISTORICO_DIR no .env da skill (veja .env.example) ou passe --historico")
        base = re.sub(r"\d+$", "", args.ticker.upper())
        historico = HISTORICO_DIR / args.canal / f"{base}.md"
    historico = historico.expanduser()

    nome_canal, url_canal = CANAIS[args.canal]
    conhecidos = set(VIDEO_ID.findall(historico.read_text(encoding="utf-8"))) if historico.exists() else set()
    novos_ids = [v for v in listar_canal(url_canal, args.ticker) if v not in conhecidos]
    args.out.mkdir(parents=True, exist_ok=True)
    novos = []
    with tempfile.TemporaryDirectory() as tmp:
        for video_id in novos_ids:
            v = baixar_transcricao(video_id, Path(tmp))
            arquivo = args.out / f"{v['data']}_{video_id}.txt"
            arquivo.write_text(
                f"Canal: {nome_canal}\nTítulo: {v['titulo']}\nData: {v['data']}\n"
                f"Duração: {v['duracao']}\nURL: {v['url']}\n\n{v['texto']}\n",
                encoding="utf-8",
            )
            novos.append({k: x for k, x in v.items() if k != "texto"} | {"arquivo": str(arquivo)})

    novos.sort(key=lambda v: v["data"])
    print(json.dumps({"canal": nome_canal, "historico": str(historico), "existe": historico.exists(),
                      "conhecidos": len(conhecidos), "novos": novos}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
