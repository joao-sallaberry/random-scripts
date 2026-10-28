#!/usr/bin/env python3
"""Confere os relatórios arquivados pelo arquivar.py: links de imagem, sobras de parsing e leitura pelo to_audio.py.

Uso: python3 verificar.py                                   # o arquivo padrão (RELATORIOS_DIR do .env)
     python3 verificar.py /tmp/teste --curtas 150           # também lista seções com menos de 150 caracteres
     python3 verificar.py /tmp/regerado --comparar ~/relatorios

Para cada pasta "AAAA-MM-DD - Relatorio FII NN/", aponta:
  - link ![...](imagens/...) sem o arquivo, data: URI que sobrou no .md e imagens não salvas com a página;
  - linhas soltas (FII, ##, ###), caracteres invisíveis e tickers sozinhos numa linha (às vezes é só um
    subtítulo do autor, como RECT11 em 2022 nº 43);
  - títulos de seção vazios, que começam com R$, só com número ou longos demais;
  - .md que o to_audio.py não consegue ler.
--comparar REF diz quais .md diferem dos de mesmo nome em REF: depois de mudar o arquivar.py, regere o arquivo a
partir dos original.html numa pasta temporária e compare com o arquivo de verdade.
Sai com código 1 se encontrar problemas.
"""
import argparse
import re
import sys
from pathlib import Path

from config import RELATORIOS_DIR
from to_audio import Erro, ler_md

LINK = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
INVISIVEIS = re.compile(r"[﻿​-‍⁠]")
TICKER_SOLTO = re.compile(r"[A-Z]{4}1[1-3][A-Z]?")
SECAO = re.compile(r"^## (\d+)\. (.*)$", re.M)


def problemas(md, curtas):
    texto = md.read_text(encoding="utf-8")
    achados = []
    for link in LINK.findall(texto):
        if link.startswith("data:"):
            achados.append("imagem em data: URI no .md")
        elif not re.match(r"https?:", link) and not (md.parent / link).exists():
            achados.append(f"link quebrado: {link}")
    if "[Imagem não salva com a página" in texto:
        achados.append("imagem não salva com a página")
    for linha in texto.splitlines():
        l = linha.strip()
        if l in ("FII", "##", "###"):
            achados.append(f"linha solta: {l}")
        if INVISIVEIS.search(linha):
            achados.append("caractere invisível")
        if TICKER_SOLTO.fullmatch(l):
            achados.append(f"ticker solto: {l}")
    titulos = SECAO.findall(texto)
    corpos = SECAO.split(texto)[3::3]
    for (n, titulo), corpo in zip(titulos, corpos):
        if len(titulo.strip()) < 3 or re.match(r"R\$|[\d.,% ]+$", titulo) or len(titulo) > 120:
            achados.append(f"título estranho na seção {n}: {titulo[:80]!r}")
        if curtas and len(corpo.strip()) < curtas:
            achados.append(f"seção {n} curta ({len(corpo.strip())} caracteres): {titulo[:50]}")
    try:
        ler_md(texto)
    except Erro as e:
        achados.append(f"to_audio: {e}")
    return achados


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", nargs="?", type=Path, default=RELATORIOS_DIR,
                    help="arquivo a conferir (padrão: RELATORIOS_DIR do .env)")
    ap.add_argument("--curtas", type=int, metavar="N", help="listar seções com menos de N caracteres")
    ap.add_argument("--comparar", type=Path, metavar="REF", help="arquivo de referência para comparar os .md")
    args = ap.parse_args()
    if args.pasta is None:
        ap.error("defina RELATORIOS_DIR no .env (veja .env.example) ou passe a pasta")

    mds = sorted(args.pasta.glob("*/*.md"))
    if not mds:
        sys.exit(f"erro: nenhum relatório arquivado em {args.pasta}")

    com_problema = diferentes = 0
    for md in mds:
        achados = problemas(md, args.curtas)
        if args.comparar:
            ref = args.comparar / md.relative_to(args.pasta)
            if not ref.exists():
                achados.append(f"ausente em {args.comparar}")
            elif ref.read_bytes() != md.read_bytes():
                achados.append(f"difere de {ref}")
                diferentes += 1
        if achados:
            com_problema += 1
            print(f"{md.parent.name}:")
            for a in dict.fromkeys(achados):
                print(f"  {a}")

    resumo = f"{len(mds)} relatórios conferidos, {com_problema} com apontamentos"
    if args.comparar:
        resumo += f", {diferentes} diferentes da referência"
    print(resumo)
    sys.exit(1 if com_problema else 0)


if __name__ == "__main__":
    main()
