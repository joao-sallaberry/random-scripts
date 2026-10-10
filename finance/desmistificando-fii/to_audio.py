#!/usr/bin/env python3
"""Gera o áudio do relatório de FIIs (.md do to_md.py): uma faixa MP3 por seção + um .m4b com capítulos.

Uso: python3 to_audio.py "Relatorio FII 41 - 2026-10-03.md" [--voz pt-BR-AntonioNeural] [--velocidade +10%]
     python3 to_audio.py relatorio.md --so 1,3,5      # só essas seções (números do .md)
     python3 to_audio.py relatorio.md --com-disclaimer --sem-m4b

Saída: pasta "<nome do md> - audio/" com "NN - <título>.mp3" por seção, "Relatorio FII NN.m4b"
(com capítulos) e roteiro.txt (o texto exatamente como foi falado). Abertura, Carteira Recomendada e
Retornos ficam só no .md. Requer edge-tts (uv tool install edge-tts) e ffmpeg/ffprobe.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from speech import falar

VOZ = "pt-BR-AntonioNeural"
TENTATIVAS = 3
PARALELO = 4
# seções que ficam só no .md (tabelas); o disclaimer entra só com --com-disclaimer
SEM_AUDIO = ("Carteira Recomendada", "Retornos Nominais")


class Erro(Exception):
    pass


def ler_md(texto):
    """Retorna (cabeçalho, [(número, título, corpo)])."""
    partes = re.split(r"^## (\d+)\. (.+)$", texto, flags=re.M)
    cab = partes[0]
    secoes = [(int(partes[i]), partes[i + 1].strip(), partes[i + 2].strip()) for i in range(1, len(partes), 3)]
    if not secoes:
        raise Erro("nenhuma seção '## NN. Título' no arquivo: ele foi gerado pelo to_md.py?")
    return cab, secoes


def frases(corpo):
    """Corpo Markdown → texto corrido para fala."""
    out = []
    for linha in corpo.splitlines():
        l = linha.strip()
        if not l or l.startswith("|"):
            continue
        if l.startswith("Fonte:"):
            continue
        if l.startswith("[Imagem"):
            out.append("Neste ponto, o relatório traz uma imagem.")
            continue
        l = re.sub(r"^#+\s*", "", l)
        l = re.sub(r"^-\s+", "", l)
        if not re.search(r"[.!?:;]$", l):
            l += "."
        out.append(l)
    return "\n".join(out)


def fundos_falados(linha_fundos):
    """'Fundos: RBRX11 (Multiestratégia, R$ 7,36) · ...' → 'RBRX11, multiestratégia.' (sem a cotação)."""
    out = []
    for m in re.finditer(r"([A-Z]{4}\d{2}) \(([^)]*)\)", linha_fundos):
        seg = m.group(2).split("R$")[0].strip(" ,")
        out.append(f"{m.group(1)}, {seg.lower()}." if seg else f"{m.group(1)}.")
    return " ".join(out)


def roteiro_secao(titulo, corpo):
    linhas = corpo.splitlines()
    if linhas and linhas[0].startswith("Fundos:"):
        return fundos_falados(linhas[0]) + "\n\n" + frases("\n".join(linhas[1:]))
    return f"{titulo}.\n\n" + frases(corpo)


def metadados(cab):
    """Edição e data de divulgação, do cabeçalho do .md."""
    m = re.search(r"nº (\d+) — divulgação (\S+)", cab)
    return (m.group(1), m.group(2)) if m else ("?", "")


def nome_arquivo(n, titulo):
    t = re.sub(r'[\\/:*?"<>|]', "-", titulo)
    return f"{n:02d} - {t[:80]}.mp3"


def rodar(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise Erro(f"{Path(cmd[0]).name} falhou: {r.stderr.strip()[-500:]}")
    return r.stdout


def tts(texto, destino, voz, velocidade, tmp):
    entrada = Path(tmp) / (destino.stem + ".txt")
    entrada.write_text(texto, encoding="utf-8")
    ultimo = None
    for _ in range(TENTATIVAS):
        try:
            rodar(["edge-tts", "--voice", voz, f"--rate={velocidade}", "-f", str(entrada), "--write-media", str(destino)])
            return
        except Erro as e:
            ultimo = e
    raise ultimo


def duracao(arq):
    return float(rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)]))


def gerar_faixa(faixa, album, total, voz, velocidade, tmp, pasta):
    n, titulo, texto = faixa
    bruto = Path(tmp) / f"{n:02d}.mp3"
    tts(texto, bruto, voz, velocidade, tmp)
    final = pasta / nome_arquivo(n, titulo)
    rodar(["ffmpeg", "-y", "-v", "error", "-i", str(bruto), "-c", "copy", "-id3v2_version", "3",
           "-metadata", f"title={titulo}", "-metadata", f"album={album}", "-metadata", "artist=Relatório Semanal FII",
           "-metadata", f"track={n + 1}/{total}", str(final)])
    return final


def escape_meta(s):
    return re.sub(r"([=;#\\\n])", r"\\\1", s)


def gerar_m4b(faixas, arquivos, album, destino, tmp):
    lista = Path(tmp) / "lista.txt"
    lista.write_text("".join(f"file '{str(a).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n" for a in arquivos))
    meta = [";FFMETADATA1", f"title={escape_meta(album)}", f"album={escape_meta(album)}", "artist=Relatório Semanal FII"]
    ini = 0
    for (n, titulo, _), arq in zip(faixas, arquivos):
        fim = ini + int(duracao(arq) * 1000)
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={ini}", f"END={fim}", f"title={escape_meta(titulo)}"]
        ini = fim
    meta_arq = Path(tmp) / "meta.txt"
    meta_arq.write_text("\n".join(meta) + "\n", encoding="utf-8")
    rodar(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-i", str(meta_arq),
           "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1", "-c:a", "aac", "-b:a", "64k",
           "-f", "mp4", str(destino)])
    return ini / 1000


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("md", type=Path)
    ap.add_argument("--out", type=Path, help="pasta de saída (padrão: '<md> - audio' ao lado do .md)")
    ap.add_argument("--voz", default=VOZ, help=f"voz do edge-tts (padrão {VOZ}; ex.: pt-BR-FranciscaNeural)")
    ap.add_argument("--velocidade", default="+0%", help="ex.: +10%%, -5%%")
    ap.add_argument("--com-disclaimer", action="store_true", help="inclui o disclaimer no áudio")
    ap.add_argument("--so", help="só estas seções, ex.: 1,3 (números do .md)")
    ap.add_argument("--sem-m4b", action="store_true", help="não gera o .m4b com capítulos")
    ap.add_argument("--force", action="store_true", help="sobrescreve a pasta de saída")
    args = ap.parse_args()

    for exe in ("edge-tts", "ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            dica = " (instale com: uv tool install edge-tts)" if exe == "edge-tts" else ""
            print(f"erro: {exe} não encontrado{dica}", file=sys.stderr)
            sys.exit(1)

    try:
        cab, secoes = ler_md(args.md.read_text(encoding="utf-8"))
        edicao, data = metadados(cab)
        faixas = []
        for n, titulo, corpo in secoes:
            if titulo.startswith(SEM_AUDIO) or (titulo == "Disclaimer" and not args.com_disclaimer):
                continue
            faixas.append((n, titulo, roteiro_secao(titulo, corpo)))
        if args.so:
            quero = {int(x) for x in args.so.split(",")}
            faixas = [f for f in faixas if f[0] in quero]
        faixas = [(n, t, falar_bloco(txt)) for n, t, txt in faixas]

        pasta = (args.out or args.md.with_name(f"{args.md.stem} - audio")).resolve()
        if pasta.exists() and any(pasta.iterdir()) and not args.force:
            raise Erro(f"{pasta} já existe e não está vazia (use --force)")
        if pasta.exists() and args.force:
            for f in list(pasta.glob("*.mp3")) + list(pasta.glob("*.m4b")):
                f.unlink()
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "roteiro.txt").write_text(
            "\n\n".join(f"=== {n:02d}. {t} ===\n{txt}" for n, t, txt in faixas) + "\n", encoding="utf-8")

        album = f"Relatório FII nº {edicao} ({data})"
        with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(PARALELO) as pool:
            futuros = [pool.submit(gerar_faixa, f, album, len(faixas), args.voz, args.velocidade, tmp, pasta)
                       for f in faixas]
            arquivos = []
            for f, fut in zip(faixas, futuros):
                arquivos.append(fut.result())
                print(f"  ok {arquivos[-1].name}", flush=True)
            if not args.sem_m4b:
                m4b = pasta / f"Relatorio FII {edicao}.m4b"
                total = gerar_m4b(faixas, arquivos, album, m4b, tmp)
            else:
                total = sum(duracao(a) for a in arquivos)
    except (Erro, OSError) as e:
        print(f"erro: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{len(arquivos)} faixas, {int(total // 60)} min {int(total % 60)} s → {pasta}")


def falar_bloco(texto):
    return "\n".join(falar(l) for l in texto.splitlines())


if __name__ == "__main__":
    main()
