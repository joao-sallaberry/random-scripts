#!/usr/bin/env python3
"""Extrai o Relatório Semanal de FIIs (DesmistificandoFII) de um HTML salvo para Markdown, uma seção por tópico.

Uso: python3 to_md.py relatorio.html [--out arquivo.md] [--force]
"""
import argparse
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

IGNORAR = {"script", "style", "svg", "button", "noscript", "canvas"}
BLOCOS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "header", "section", "table", "br", "ul", "ol"}
TICKER = re.compile(r"^[A-Z]{4}1[1-3]$")
PRECO = re.compile(r"^R\$\s?[\d.]+,\d{2}$")
LIXO_ALT = re.compile(r"\s*O conteúdo gerado por IA pode estar incorreto\.?\s*")
FINAIS = ("Carteira Recomendada", "Carteira FIIs")


class Erro(Exception):
    pass


def limpar(texto):
    return re.sub(r"\s+", " ", texto.replace("\xa0", " ")).strip()


class Blocos(HTMLParser):
    """Transforma o <main> numa lista linear de blocos (tipo, conteúdo).

    Tipos: p, li, h2, strong (parágrafo todo em negrito), img, tr (lista de células).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocos = []
        self.pular = 0
        self.texto = []      # pedaços (texto, em_negrito) do bloco atual
        self.negrito = 0
        self.pilha = []      # tags de bloco abertas, para saber se é li/h2
        self.linha = None    # células do <tr> atual
        self.celula = None

    def _tipo(self):
        for t in reversed(self.pilha):
            if t in ("li", "h2", "h1", "h3", "h4"):
                return "h2" if t.startswith("h") else t
        return "p"

    def _fechar_bloco(self):
        if self.linha is not None:
            return
        texto = limpar("".join(t for t, _ in self.texto))
        if texto:
            tudo_negrito = all(b or not t.strip() for t, b in self.texto)
            tipo = self._tipo()
            if tipo == "p" and tudo_negrito and len(texto) <= 80 and not texto.endswith("."):
                tipo = "strong"
            self.blocos.append((tipo, texto))
        self.texto = []

    def handle_starttag(self, tag, attrs):
        if tag in IGNORAR:
            self.pular += 1
            return
        if self.pular:
            return
        a = dict(attrs)
        if tag == "tr":
            self._fechar_bloco()
            self.linha = []
        elif tag in ("td", "th") and self.linha is not None:
            self.celula = []
        elif tag in ("strong", "b"):
            self.negrito += 1
        elif tag == "img" and "chakra-image" not in (a.get("class") or ""):
            # logos de fundos e do site têm class chakra-image; figuras do texto, não
            self._fechar_bloco()
            alt = LIXO_ALT.sub(" ", a.get("alt") or "")
            self.blocos.append(("img", limpar(alt)))
        elif tag in BLOCOS:
            self._fechar_bloco()
            if tag != "br":
                self.pilha.append(tag)

    def handle_endtag(self, tag):
        if tag in IGNORAR:
            self.pular = max(0, self.pular - 1)
            return
        if self.pular:
            return
        if tag in ("td", "th") and self.celula is not None:
            self.linha.append(limpar("".join(self.celula)))
            self.celula = None
        elif tag == "tr" and self.linha is not None:
            if any(self.linha):
                self.blocos.append(("tr", self.linha))
            self.linha = None
        elif tag in ("strong", "b"):
            self.negrito = max(0, self.negrito - 1)
        elif tag in BLOCOS:
            if self.linha is not None and self.celula is not None:
                self.celula.append(" ")
            self._fechar_bloco()
            if tag in self.pilha:
                del self.pilha[len(self.pilha) - 1 - self.pilha[::-1].index(tag):]

    def handle_data(self, data):
        if self.pular:
            return
        if self.celula is not None:
            self.celula.append(data)
        elif self.linha is None:
            self.texto.append((data, self.negrito > 0))


def texto_de(bloco):
    return bloco[1] if bloco[0] != "tr" else ""


def ler_card(blocos, j):
    """Tenta ler um card de fundo terminando no índice j (o preço). Retorna (início, card) ou None."""
    if j < 2 or not PRECO.match(texto_de(blocos[j])):
        return None
    preco = texto_de(blocos[j])
    k = j - 1
    segmento = None
    if not TICKER.match(texto_de(blocos[k])):
        segmento, k = texto_de(blocos[k]), k - 1
    if k < 1 or not TICKER.match(texto_de(blocos[k])) or texto_de(blocos[k - 1]) != "FII":
        return None
    return k - 1, {"ticker": texto_de(blocos[k]), "segmento": segmento, "preco": preco}


def cards_em(blocos, ini, fim):
    """Lê, em ordem, todos os cards de fundo no intervalo [ini, fim)."""
    cards, j = [], ini
    while j < fim:
        lido = ler_card(blocos, j)
        if lido:
            cards.append(lido[1])
        j += 1
    return cards


def descrever(card):
    extra = ", ".join(x for x in (card["segmento"], card["preco"]) if x)
    return f"{card['ticker']} ({extra})"


def indice(blocos, pred, ini=0):
    for i in range(ini, len(blocos)):
        if pred(blocos[i]):
            return i
    return None


def metadados(blocos):
    h2s = [t for tipo, t in blocos if tipo == "h2"]
    edicao = next((t for t in h2s if t.isdigit()), None)
    if not edicao:
        raise Erro("não achei o número da edição (primeiro título numérico)")

    def depois(rotulo):
        i = indice(blocos, lambda b: texto_de(b) == rotulo)
        return texto_de(blocos[i + 1]) if i is not None else None

    i = indice(blocos, lambda b: texto_de(b).startswith("Analista de Valores"))
    analista = texto_de(blocos[i - 1]) if i else None
    divulgacao = depois("Divulgação")
    if not divulgacao or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", divulgacao):
        raise Erro(f"data de divulgação não encontrada ou inválida: {divulgacao!r}")
    return {"edicao": edicao, "periodo": depois("Período"), "divulgacao": divulgacao, "analista": analista}


def corpo_md(blocos):
    """Renderiza os blocos do corpo de uma seção em Markdown."""
    linhas, tabela = [], False
    for tipo, cont in blocos:
        if tipo == "tr":
            if not tabela:
                linhas.append("")
            linhas.append("| " + " | ".join(c.replace("|", "/") for c in cont) + " |")
            tabela = True
            continue
        if tabela:
            linhas.append("")
            tabela = False
        if tipo == "strong":
            linhas += ["", f"### {cont.strip('* ')}", ""]
        elif tipo == "h2":
            linhas += ["", f"### {cont}", ""]
        elif tipo == "li":
            linhas.append(cont if cont.startswith("- ") else f"- {cont}")
        elif tipo == "img":
            linhas += ["", f"[Imagem: {cont}]" if cont else "[Imagem]", ""]
        else:
            linhas += ["", cont, ""] if not cont.startswith("- ") else [cont]
    md = "\n".join(linhas)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def tabela_md(linhas, cabecalho=None):
    if not linhas:
        return ""
    cab = cabecalho or linhas[0]
    resto = linhas if cabecalho else linhas[1:]
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(r) + " |" for r in resto]
    return "\n".join(out)


def secoes_finais(blocos, ini):
    """Carteira Recomendada, Retornos e Disclaimer, a partir do índice ini."""
    secoes = []
    i_ret = indice(blocos, lambda b: b[0] == "h2" and b[1].startswith("Retornos Nominais"), ini)
    i_disc = indice(blocos, lambda b: texto_de(b).lower() == "disclaimer", ini)
    fim_cart = i_ret if i_ret is not None else (i_disc if i_disc is not None else len(blocos))

    cart = [b for b in blocos[ini:fim_cart] if b[1] not in FINAIS and b[1] not in ("Gráficos",)
            and not (b[0] == "h2" and b[1].startswith("Retorno da Carteira"))]
    linhas = [b[1] for b in cart if b[0] == "tr"]
    textos = []
    for b in cart:
        if b[0] == "tr":
            continue
        if textos and textos[-1][1].isdigit() and b[0] == "p":
            textos[-1] = ("p", f"{textos[-1][1]} {b[1]}")  # "25" + "ativos nesta carteira"
        else:
            textos.append(b)
    md = "\n\n".join(filter(None, [corpo_md(textos), tabela_md(linhas)]))
    secoes.append({"titulo": "Carteira Recomendada", "fundos": [], "md": md, "tipo": "carteira"})

    if i_ret is not None:
        fim = i_disc if i_disc is not None else len(blocos)
        rows = [b[1] for b in blocos[i_ret + 1:fim] if b[0] == "tr"]
        cab, ano, tabela = None, None, []
        for r in rows:
            if cab is None:
                cab = ["Ano"] + r[1:] if not r[0] else r
                continue
            if len(r) == len(cab):
                ano = r[0]
                tabela.append(r)
            elif len(r) == len(cab) - 1:
                tabela.append([ano] + r)
        # texto após a tabela (nota sobre a carteira); números soltos são paginação
        notas = [b for b in blocos[i_ret + 1:fim] if b[0] != "tr" and not b[1].isdigit()]
        md = "\n\n".join(filter(None, [tabela_md(tabela, cab), corpo_md(notas)]))
        secoes.append({"titulo": "Retornos Nominais da Carteira x Benchmark", "fundos": [], "md": md, "tipo": "retornos"})

    if i_disc is not None:
        resto = [b for b in blocos[i_disc + 1:] if b[1] != "DISCLAIMER"]
        secoes.append({"titulo": "Disclaimer", "fundos": [], "md": corpo_md(resto), "tipo": "disclaimer"})
    return secoes


def extrair(html):
    ini, fim = html.find("<main"), html.find("</main>")
    if ini < 0 or fim < 0:
        raise Erro("HTML sem <main>: é a página do relatório salva pelo navegador?")
    p = Blocos()
    p.feed(html[ini:fim])
    blocos = p.blocos

    meta = metadados(blocos)
    marcas = [i for i, b in enumerate(blocos) if texto_de(b) == "Ouvir"]
    if not marcas:
        raise Erro("nenhum marcador 'Ouvir' encontrado: o layout do site pode ter mudado")

    # cabeçalho de cada seção: cards de fundo (um ou mais) ou um título de texto antes do 'Ouvir'
    cabecalhos = []
    for m in marcas:
        cards, j = [], m - 1
        while (lido := ler_card(blocos, j)):
            cards.insert(0, lido[1])
            j = lido[0] - 1
        if cards:
            cabecalhos.append((j + 1, m, None, cards))
        else:
            cabecalhos.append((m - 1, m, texto_de(blocos[m - 1]), []))

    i_final = indice(blocos, lambda b: b[1] in FINAIS, marcas[-1])
    if i_final is None:
        i_final = len(blocos)

    i_abord = indice(blocos, lambda b: texto_de(b).startswith("Fundos abordados"))
    abordados = cards_em(blocos, i_abord + 1, cabecalhos[0][0]) if i_abord is not None else []

    secoes = []
    for n, (cab_ini, m, titulo, cards) in enumerate(cabecalhos):
        corpo_ini = m + 1
        if corpo_ini < len(blocos) and texto_de(blocos[corpo_ini]) == "Order":
            corpo_ini += 1
        corpo_fim = cabecalhos[n + 1][0] if n + 1 < len(cabecalhos) else i_final
        secoes.append({
            "titulo": titulo or ", ".join(c["ticker"] for c in cards),
            "fundos": cards,
            "md": corpo_md(blocos[corpo_ini:corpo_fim]),
            "tipo": "fundos" if cards else "texto",
        })
    secoes += secoes_finais(blocos, i_final)
    return meta, abordados, secoes


def montar_md(meta, abordados, secoes):
    partes = [
        f"# Relatório Semanal FII nº {meta['edicao']} — divulgação {meta['divulgacao']}",
        "",
        " · ".join(x for x in (
            f"Período: {meta['periodo']}" if meta["periodo"] else None,
            f"Analista: {meta['analista']}" if meta["analista"] else None,
        ) if x),
    ]
    if abordados:
        partes += ["", "Fundos abordados: " + ", ".join(descrever(c) for c in abordados)]
    for n, s in enumerate(secoes, 1):
        partes += ["", f"## {n:02d}. {s['titulo']}", ""]
        if s["fundos"]:
            partes += ["Fundos: " + " · ".join(descrever(c) for c in s["fundos"]), ""]
        partes.append(s["md"])
    return "\n".join(partes).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("html", type=Path)
    ap.add_argument("--out", type=Path, help="arquivo .md de saída (padrão: na pasta do HTML)")
    ap.add_argument("--force", action="store_true", help="sobrescreve o .md se já existir")
    args = ap.parse_args()
    try:
        raw = args.html.read_bytes()
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1")
        meta, abordados, secoes = extrair(html)
    except (Erro, OSError) as e:
        print(f"erro: {e}", file=sys.stderr)
        sys.exit(1)

    d, m, a = meta["divulgacao"].split("/")
    out = args.out or args.html.parent / f"Relatorio FII {meta['edicao']} - {a}-{m}-{d}.md"
    if out.exists() and not args.force:
        print(f"erro: {out} já existe (use --force para sobrescrever)", file=sys.stderr)
        sys.exit(1)
    out.write_text(montar_md(meta, abordados, secoes), encoding="utf-8")

    print(f"Edição {meta['edicao']} ({meta['divulgacao']}) → {out}")
    for n, s in enumerate(secoes, 1):
        print(f"  {n:02d}. {s['titulo']}")
    tickers_secoes = {c["ticker"] for s in secoes for c in s["fundos"]}
    faltando = [c["ticker"] for c in abordados if c["ticker"] not in tickers_secoes]
    if faltando:
        print(f"aviso: fundos abordados sem seção própria: {', '.join(faltando)}", file=sys.stderr)


if __name__ == "__main__":
    main()
