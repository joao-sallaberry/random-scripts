#!/usr/bin/env python3
"""Arquiva o Relatório Semanal de FIIs (DesmistificandoFII) salvo pelo navegador: HTML → Markdown, uma seção por tópico.

Uso: python3 arquivar.py relatorio-FIIS-43-17-10-2026/relatorio-FIIS-43-17-10-2026.html
     python3 arquivar.py relatorio-FIIS-*/          # vários de uma vez (pastas ou .html)
     python3 arquivar.py                                         # só regera o indice.md
     python3 arquivar.py relatorio.html --destino ~/outra/pasta --force

Cada relatório vai para "<destino>/AAAA-MM-DD - Relatorio FII NN/" (destino padrão: <RELATORIOS_DIR>):
  Relatorio FII NN - AAAA-MM-DD.md  metadados (front matter YAML) + uma seção "## NN. Título" por tópico
  imagens/                          figuras do texto, copiadas da pasta "<nome>_files/" salva junto com a página
  original.html                     o HTML sem scripts e apontando para imagens/; serve de entrada para regerar o .md
Edições já arquivadas são puladas (use --force para regerar). Ao final, "<destino>/indice.md" é refeito a partir
de todos os .md arquivados: lista de edições e, por fundo, as seções que tratam dele com a cotação da época.
"""
import argparse
import base64
import binascii
import json
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

IGNORAR = {"script", "style", "svg", "button", "noscript", "canvas"}
BLOCOS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "header", "section", "table", "br", "ul", "ol"}
TICKER = re.compile(r"^[A-Z]{4}1[1-3][A-Z]?$")  # FIIP11B: classe de cotas
PRECO = re.compile(r"^R\$\s?[\d.]+,\d{2}$")
# alt automático do Office ("Interface gráfica do usuário, Texto, Aplicativo ... gerado por IA"): descartado
ALT_IA = re.compile(r"O conteúdo gerado por IA pode estar incorreto")
FINAIS = ("Carteira Recomendada", "Carteira FIIs")
DATA_URI = re.compile(r"data:image/([\w.+-]+)?(;base64)?,(.*)", re.S)
EXTENSOES = {"jpeg": ".jpg", "svg+xml": ".svg"}
# assinatura dos formatos, para arquivos salvos sem extensão
ASSINATURAS = {b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"GIF8": ".gif", b"RIFF": ".webp", b"<svg": ".svg"}
DESTINO = Path.home() / "relatorios"
INDICE = "indice.md"


class Erro(Exception):
    pass


def limpar(texto):
    # ﻿ e afins: caracteres invisíveis que às vezes vêm no texto colado pelo autor
    texto = re.sub("[﻿​-‍⁠]", "", texto.replace("\xa0", " "))
    return re.sub(r"\s+", " ", texto).strip()


class Blocos(HTMLParser):
    """Transforma o <main> numa lista linear de blocos (tipo, conteúdo).

    Tipos: p, li, h2, strong (parágrafo todo em negrito), img ((alt, src)), tr (lista de células).
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
            alt = a.get("alt") or ""
            self.blocos.append(("img", ("" if ALT_IA.search(alt) else limpar(alt), a.get("src") or "")))
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
    return bloco[1] if bloco[0] not in ("tr", "img") else ""


def ler_card(blocos, j):
    """Tenta ler um card de fundo (FII / TICKER / segmento? / R$ preço?) terminando no índice j.

    Retorna (início, card) ou None. Alguns cards vêm sem cotação (ex.: VLOL11 no relatório 41 de 2022).
    """
    k, preco, segmento = j, None, None
    if PRECO.match(texto_de(blocos[k])):
        preco, k = texto_de(blocos[k]), k - 1
    if k >= 0 and not TICKER.match(texto_de(blocos[k])):
        segmento, k = texto_de(blocos[k]), k - 1
    if k < 1 or not TICKER.match(texto_de(blocos[k])) or texto_de(blocos[k - 1]) != "FII":
        return None
    return k - 1, {"ticker": texto_de(blocos[k]), "segmento": segmento, "preco": preco}


def cards_em(blocos, ini, fim):
    """Lê, em ordem, todos os cards de fundo no intervalo [ini, fim)."""
    cards = []
    for j in range(ini, fim):
        lido = ler_card(blocos, j)
        # o mesmo card também casa terminando no segmento: fica só a leitura mais longa
        seguinte = ler_card(blocos, j + 1) if j + 1 < fim else None
        if lido and not (seguinte and seguinte[0] == lido[0]):
            cards.append(lido[1])
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
            alt, link = cont
            linhas += ["", f"![{alt or 'Imagem'}]({link.replace(' ', '%20')})", ""]
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
        if textos and texto_de(textos[-1]).isdigit() and b[0] == "p":
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
        notas = [b for b in blocos[i_ret + 1:fim] if b[0] != "tr" and not texto_de(b).isdigit()]
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

    # figuras locais (da pasta _files) e embutidas (data:, nos relatórios antigos) viram imagens/01.webp,
    # 02.png...; as remotas ficam com a URL. Sem extensão conhecida, o arquivar() descobre pelo conteúdo.
    imagens = []
    for i, (tipo, cont) in enumerate(blocos):
        if tipo != "img" or re.match(r"https?:", cont[1]):
            continue
        dados = DATA_URI.match(cont[1])
        if dados:
            tipo_mime = dados.group(1)
            ext = EXTENSOES.get(tipo_mime, f".{tipo_mime}") if tipo_mime else ""
        else:
            ext = Path(unquote(cont[1])).suffix.lower()
        link = f"imagens/{len(imagens) + 1:02d}{ext}"
        imagens.append((cont[1], link))
        blocos[i] = ("img", (cont[0], link))

    meta = metadados(blocos)
    marcas = [i for i, b in enumerate(blocos) if texto_de(b) == "Ouvir"]
    if not marcas:
        raise Erro("nenhum marcador 'Ouvir' encontrado: o layout do site pode ter mudado")

    # cabeçalho de cada seção: cards de fundo (um ou mais) ou um título de texto antes do 'Ouvir'
    cabecalhos = []
    for m in marcas:
        cards, j = [], m - 1
        while (lido := ler_card(blocos, j)):
            # ticker repetido: já é a lista "Fundos abordados", colada aos cards em relatórios de uma seção só
            if any(c["ticker"] == lido[1]["ticker"] for c in cards):
                break
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
    return meta, abordados, secoes, imagens


def montar_md(meta, abordados, secoes):
    d, m, a = meta["divulgacao"].split("/")
    fundos = list(dict.fromkeys([c["ticker"] for c in abordados] + [c["ticker"] for s in secoes for c in s["fundos"]]))
    frente = {"edicao": int(meta["edicao"]), "divulgacao": f"{a}-{m}-{d}", "periodo": meta["periodo"],
              "analista": meta["analista"], "fundos": fundos}
    partes = ["---", *(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in frente.items()), "---", ""]
    partes += [
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


def ler_html(arq):
    raw = arq.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def arquivar(arq_html, destino, force):
    """Arquiva um relatório. Retorna False se ele já estava arquivado (e não há --force)."""
    html = ler_html(arq_html)
    meta, abordados, secoes, imagens = extrair(html)
    d, m, a = meta["divulgacao"].split("/")
    nome = f"Relatorio FII {meta['edicao']} - {a}-{m}-{d}"
    pasta = destino / f"{a}-{m}-{d} - Relatorio FII {meta['edicao']}"
    out = pasta / f"{nome}.md"
    if out.exists() and not force:
        print(f"já arquivado: {pasta.name} (use --force para regerar)")
        return False

    md = montar_md(meta, abordados, secoes)
    (pasta / "imagens").mkdir(parents=True, exist_ok=True)
    copiadas = set()
    for src, link in imagens:
        if f"]({link})" not in md:  # figura fora das seções (cabeçalho da página)
            continue
        dados = imagem(src, arq_html.parent)
        if dados is None:
            # o navegador às vezes não salva uma figura: fica a menção no texto, sem link quebrado
            print(f"aviso: imagem não salva com a página: {src[:100]}", file=sys.stderr)
            md = re.sub(rf"!\[([^\]]*)\]\({re.escape(link)}\)",
                        lambda m: "[Imagem não salva com a página" + (f": {m.group(1)}]" if m.group(1) != "Imagem" else "]"), md)
            continue
        if not Path(link).suffix:
            novo = link + next((e for a, e in ASSINATURAS.items() if dados.startswith(a)), ".bin")
            md, link = md.replace(f"]({link})", f"]({novo})"), novo
        alvo = pasta / link
        if not (alvo.exists() and alvo.read_bytes() == dados):  # regerando a partir do original.html arquivado
            alvo.write_bytes(dados)
        copiadas.add(alvo.name)
        html = html.replace(f'src="{src}"', f'src="{link}"')
    for velha in (pasta / "imagens").iterdir():
        if velha.name not in copiadas:
            velha.unlink()
    out.write_text(md, encoding="utf-8")
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    (pasta / "original.html").write_text(html, encoding="utf-8")

    print(f"Edição {meta['edicao']} ({meta['divulgacao']}): {len(secoes)} seções, {len(copiadas)} imagens → {out}")
    tickers_secoes = {c["ticker"] for s in secoes for c in s["fundos"]}
    faltando = [c["ticker"] for c in abordados if c["ticker"] not in tickers_secoes]
    if faltando:
        print(f"aviso: fundos abordados sem seção própria: {', '.join(faltando)}", file=sys.stderr)
    return True


def imagem(src, base):
    """Bytes de uma figura: decodificada de um data: URI ou lida da pasta do HTML. None se não existir."""
    dados = DATA_URI.match(src)
    if dados:
        try:
            return base64.b64decode(dados.group(3)) if dados.group(2) else unquote(dados.group(3)).encode()
        except binascii.Error:
            return None
    arq = base / unquote(src).removeprefix("./")
    return arq.read_bytes() if arq.is_file() else None


def ler_arquivado(arq):
    """Front matter e seções de um .md arquivado: (meta, [(número, título, [(ticker, segmento, preço)])])."""
    md = arq.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", md, flags=re.S)
    if not m:
        raise Erro("sem front matter (arquivado por uma versão antiga? rode de novo com --force no original.html)")
    meta = {k: json.loads(v) for k, v in (l.split(": ", 1) for l in m.group(1).splitlines())}
    secoes = []
    for s in re.finditer(r"^## (\d+)\. (.+)\n\n(?:Fundos: (.+))?", md, flags=re.M):
        fundos = []
        for f in re.finditer(r"([A-Z]{4}\d{2}[A-Z]?) \(([^)]*)\)", s.group(3) or ""):
            seg, _, preco = f.group(2).partition("R$")
            fundos.append((f.group(1), seg.strip(" ,"), f"R$ {preco.strip()}" if preco else ""))
        secoes.append((int(s.group(1)), s.group(2), fundos))
    return meta, secoes


def gerar_indice(destino):
    edicoes = []
    for arq in destino.glob("*/Relatorio FII *.md"):
        try:
            edicoes.append((arq, *ler_arquivado(arq)))
        except (Erro, ValueError, OSError) as e:
            print(f"aviso: {arq.relative_to(destino)} fora do índice: {e}", file=sys.stderr)
    if not edicoes:
        return None
    edicoes.sort(key=lambda e: e[1]["divulgacao"], reverse=True)

    def link(arq):
        return quote(str(arq.relative_to(destino)))

    linhas = ["# Relatórios DesmistificandoFII", "",
              f"{len(edicoes)} edições, de {edicoes[-1][1]['divulgacao']} a {edicoes[0][1]['divulgacao']}. "
              "Gerado pelo arquivar.py: não edite à mão.", "",
              "## Edições", "", "| Divulgação | Edição | Período | Fundos |", "|---|---|---|---|"]
    por_fundo = {}
    for arq, meta, secoes in edicoes:
        linhas.append(f"| {meta['divulgacao']} | [nº {meta['edicao']}]({link(arq)}) | {meta['periodo'] or ''} | "
                      f"{', '.join(meta['fundos'])} |")
        for n, titulo, fundos in secoes:
            for ticker, seg, preco in fundos:
                por_fundo.setdefault(ticker, []).append((meta, arq, n, titulo, seg, preco))
    linhas += ["", "## Por fundo"]
    for ticker in sorted(por_fundo):
        itens = por_fundo[ticker]
        seg = next((i[4] for i in itens if i[4]), "")  # o mais recente
        linhas += ["", f"### {ticker} — {seg}" if seg else f"### {ticker}", ""]
        linhas += [f"- {meta['divulgacao']} · nº {meta['edicao']} · [{n:02d}. {titulo}]({link(arq)})"
                   + (f" · {preco}" if preco else "") for meta, arq, n, titulo, _, preco in itens]
    (destino / INDICE).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino / INDICE


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("entradas", nargs="*", type=Path, help="HTMLs salvos, ou pastas com eles")
    ap.add_argument("--destino", type=Path, default=DESTINO, help=f"pasta do arquivo (padrão: {DESTINO})")
    ap.add_argument("--force", action="store_true", help="regera edições já arquivadas")
    args = ap.parse_args()

    htmls = []
    for e in args.entradas:
        if not e.is_dir():
            htmls.append(e)
            continue
        # numa pasta, outros HTMLs (ex.: versões antigas para TTS) não são erro
        for arq in sorted(e.glob("*.html")):
            if "<main" in ler_html(arq):
                htmls.append(arq)
            else:
                print(f"ignorado (não é a página do relatório): {arq}")
    if args.entradas and not htmls:
        print("erro: nenhum .html nas entradas", file=sys.stderr)
        sys.exit(1)

    ok = pulados = erros = 0
    for arq in htmls:
        try:
            if arquivar(arq, args.destino.expanduser(), args.force):
                ok += 1
            else:
                pulados += 1
        except (Erro, OSError) as e:
            print(f"erro: {arq}: {e}", file=sys.stderr)
            erros += 1
    if htmls:
        print(f"{ok} arquivados, {pulados} já estavam no arquivo, {erros} erros")

    indice = gerar_indice(args.destino.expanduser())
    print(f"índice: {indice}" if indice else f"nada arquivado em {args.destino} ainda")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
