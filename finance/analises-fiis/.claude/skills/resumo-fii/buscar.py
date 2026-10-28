#!/usr/bin/env python3
"""Imprime o que os relatórios arquivados dizem de um fundo, da edição mais recente para a mais antiga,
e depois os históricos do fundo nos canais do YouTube.

Uso: python3 buscar.py GGRC11                  # seções dedicadas ao fundo nas últimas 8 edições + menções + YouTube
     python3 buscar.py GGRC11 --ultimas 20
     python3 buscar.py GGRC11 --desde 2025-01-01 --sem-mencoes --sem-youtube

Seções dedicadas vêm do "Por fundo" do indice.md. Menções são parágrafos de outras seções que citam o ticker
(fora da carteira, dos retornos e das linhas "Fundos:"), nas edições do mesmo período.
Os históricos do YouTube (<HISTORICO_DIR>/<canal>/<BASE>.md, da skill historico-fii-youtube) saem inteiros,
menos as linhas da tabela e as seções de vídeo anteriores à edição mais antiga impressa (ou a --desde).
"""
import argparse
import difflib
import importlib.util
import re
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]


def config(caminho):
    """Carrega um config.py pelo caminho (os dois .env do projeto têm módulos de mesmo nome)."""
    spec = importlib.util.spec_from_file_location(f"config_{caminho.parent.name}", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


RELATORIOS_DIR = config(SKILLS.parents[1] / "desmistificando-fii" / "config.py").RELATORIOS_DIR
HISTORICO_DIR = config(SKILLS / "historico-fii-youtube" / "config.py").HISTORICO_DIR

SECAO = re.compile(r"^## (\d+)\. (.*)$", re.M)
ENTRADA = re.compile(r"^- (\d{4}-\d{2}-\d{2}) · nº (\d+) · \[(\d+)\. [^\]]*\]\(([^)]+)\)(?: · (.*))?$")
FORA = ("Carteira Recomendada", "Retornos", "Disclaimer")
DATA_BR = re.compile(r"^(?:### |\| )(\d{2})/(\d{2})/(\d{4})")


def youtube(historico, ticker, inicio):
    """Os históricos do fundo por canal, sem as linhas e seções de vídeo anteriores a `inicio` (AAAA-MM-DD)."""
    if historico is None:
        print("# YouTube\n\n(HISTORICO_DIR não definido no .env da skill historico-fii-youtube)\n")
        return
    base = re.sub(r"\d+$", "", ticker)
    arquivos = sorted(historico.glob(f"*/{base}.md"))
    print(f"# YouTube · {len(arquivos)} canais com histórico do {ticker}\n")
    for md in arquivos:
        print(f"<!-- {md} -->")
        pular = False
        for linha in md.read_text(encoding="utf-8").splitlines():
            if linha.startswith("#"):
                pular = False
            if m := DATA_BR.match(linha):
                antiga = inicio and f"{m[3]}-{m[2]}-{m[1]}" < inicio
                if linha.startswith("#"):
                    pular = antiga
                elif antiga:
                    continue
            if not pular:
                print(linha)
        print()


def secoes(md):
    partes = SECAO.split(md.read_text(encoding="utf-8"))
    return {n: (titulo, corpo.strip()) for n, titulo, corpo in zip(partes[1::3], partes[2::3], partes[3::3])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker", type=str.upper)
    ap.add_argument("--ultimas", type=int, default=8, metavar="N", help="edições com seção do fundo (padrão: 8)")
    ap.add_argument("--desde", metavar="AAAA-MM-DD", help="em vez de --ultimas, tudo a partir desta data")
    ap.add_argument("--sem-mencoes", action="store_true", help="só as seções dedicadas")
    ap.add_argument("--sem-youtube", action="store_true", help="sem os históricos dos canais do YouTube")
    ap.add_argument("--arquivo", type=Path, default=RELATORIOS_DIR, help="padrão: RELATORIOS_DIR do .env")
    ap.add_argument("--historico", type=Path, default=HISTORICO_DIR, help="padrão: HISTORICO_DIR do .env")
    args = ap.parse_args()
    if args.arquivo is None:
        ap.error("defina RELATORIOS_DIR no .env da pasta desmistificando-fii (veja .env.example)")

    indice = (args.arquivo / "indice.md").read_text(encoding="utf-8")
    bloco = re.search(rf"^### {re.escape(args.ticker)}(?: — ([^\n]*))?\n(.*?)(?=^### |\Z)", indice, re.M | re.S)
    if not bloco:
        tickers = re.findall(r"^### (\S+)", indice, re.M)
        parecidos = difflib.get_close_matches(args.ticker, tickers, n=5, cutoff=0.6)
        sys.exit(f"erro: {args.ticker} não aparece no índice" + (f" (parecidos: {', '.join(parecidos)})" if parecidos else ""))
    entradas = [m.groups() for m in map(ENTRADA.match, bloco[2].splitlines()) if m]
    entradas = [e for e in entradas if e[0] >= args.desde] if args.desde else entradas[: args.ultimas]
    if not entradas:
        sys.exit("erro: nenhuma edição no período")
    print(f"# {args.ticker} — {bloco[1] or 'sem segmento'} · {len(entradas)} edições com seção própria\n")

    inicio = min(e[0] for e in entradas)
    dedicadas = {}
    for data, edicao, n, link, cotacao in entradas:
        dedicadas.setdefault(link.replace("%20", " "), set()).add(n)
    for md in sorted(args.arquivo.glob("*/*.md"), reverse=True):
        data, edicao = md.parent.name[:10], md.parent.name.rsplit(" ", 1)[-1]
        if data < inicio:
            break
        proprias = dedicadas.get(str(md.relative_to(args.arquivo)), set())
        for n, (titulo, corpo) in secoes(md).items():
            if n in proprias:
                print(f"## {data} · nº {edicao} · seção {n}. {titulo}\n\n{corpo}\n")
            elif not args.sem_mencoes and not titulo.startswith(FORA):
                trechos = [p for p in corpo.split("\n\n") if args.ticker in p and not p.startswith("Fundos:")]
                if trechos:
                    print(f"## Menção: {data} · nº {edicao} · seção {n}. {titulo}\n\n" + "\n\n".join(trechos) + "\n")
    if not args.sem_youtube:
        youtube(args.historico, args.ticker, args.desde or inicio)


if __name__ == "__main__":
    main()
