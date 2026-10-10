"""Normaliza texto do relatório para leitura em voz alta (pt-BR).

Números, valores em R$ e porcentagens simples ficam para o motor de voz, que já os lê bem.
Aqui tratamos o que ele costuma errar: tickers, siglas, datas, abreviações e símbolos.
"""
import math
import re
from decimal import ROUND_HALF_UP, Decimal

# Siglas e abreviações → forma falada. A busca é por palavra inteira.
SIGLAS = {
    "FIIs": "fi is",
    "FII": "fi i",
    "FoFs": "fófis",
    "FoF": "fófi",
    "P/VP": "PVP",
    "DY": "dividend yield",
    "IMAB5": "ima B5",
    "IPCADP": "IPCA",
    "EUA": "Estados Unidos",
    "nº": "número",
}

# Palavras em inglês → grafia que a voz pt-BR lê com som de inglês. A busca ignora maiúsculas.
INGLES = {
    "asset": "ásset",
    "cap rate": "kép rêit",
    "mall": "mól",
    "Shopee": "xopí",
}

# Pronúncia das 4 letras do ticker (vale para 11, 12, 13...). Sem entrada aqui, o ticker é soletrado.
TICKERS = {
    "BCIA": "B cia",
    "BCRI": "B cri",
    "BROF": "brófi",
    "CLIN": "clin",
    "DEVA": "deva",
    "FATN": "fáti N",
    "FIIB": "fiib",
    "HABT": "habitá",
    "HREC": "H réqui",
    "HSAF": "H sáfi",
    "ICRI": "I cri",
    "IRIM": "irim",
    "ITIT": "I tite",
    "ITRI": "I tri",
    "JSAF": "J sáfi",
    "KFOF": "K fófi",
    "KNIP": "canipe",
    "KISU": "kizú",
    "KIVO": "kivo",
    "KORE": "córe",
    "PCIP": "P cipe",
    "PSEC": "P séqui",
    "RZAT": "R záti",
    "SAPI": "sápi",
    "TEPP": "tépi",
    "TOPP": "tópi",
    "TORD": "tórdi",
    "VCRI": "V cri",
    "VILG": "vílgui",
    "VISC": "vísqui",
}

LETRAS = {
    "A": "á", "B": "bê", "C": "cê", "D": "dê", "E": "é", "F": "éfe", "G": "gê", "H": "agá",
    "I": "i", "J": "jota", "K": "cá", "L": "éle", "M": "ême", "N": "ene", "O": "ó", "P": "pê",
    "Q": "quê", "R": "érre", "S": "ésse", "T": "tê", "U": "u", "V": "vê", "W": "dáblio",
    "X": "xis", "Y": "ípsilon", "Z": "zê",
}
NUMEROS_TICKER = {"3": "três", "4": "quatro", "5": "cinco", "6": "seis", "11": "onze", "12": "doze", "13": "treze"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

TICKER = re.compile(r"\b([A-Z]{4})(11|12|13|3|4|5|6)\b")
DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
URL = re.compile(r"https?://\S+")
# Milhões e bilhões com casas decimais são arredondados para 2 algarismos significativos:
# 1,66 MM → 1,7 milhões; 3,16 bilhões → 3,2 bilhões; 71,52 MM → 72 milhões. A partir de 10, sem decimais.
PORCENTAGEM = re.compile(r"(?<![\d,])(\d+,\d+)\s?%")
GRANDEZA = re.compile(r"(\d[\d.]*,\d+)\s?(MM|mi|milhões|milhão|bi|bilhões|bilhão)(?!\w)")
REAIS_POR_EXTENSO = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3}){2,})(?:,\d+)?(?!\d|[.,]\d)")
CENTAVOS = re.compile(r"R\$\s?0,(\d+)(?!\d|[.,]\d)")
VALOR_GRANDE = re.compile(r"R\$\s?([\d.,]+)\s?(MM|mi|milhões|milhão|bi|bilhões|bilhão|mil)\b")


def soletrar_ticker(m):
    raiz = TICKERS.get(m.group(1)) or " ".join(LETRAS[c] for c in m.group(1))
    return f"{raiz} {NUMEROS_TICKER[m.group(2)]}"


def data_falada(m):
    dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        return m.group(0)
    s = f"{dia} de {MESES[mes - 1]}"
    return f"{s} de {ano}" if ano else s


def valor_grande(m):
    unidade = {"MM": "milhões", "mi": "milhões", "bi": "bilhões"}.get(m.group(2), m.group(2))
    if m.group(1) == "1" and unidade in ("milhões", "bilhões"):
        unidade = unidade.replace("ões", "ão")
    return f"{m.group(1)} {unidade} {'reais' if unidade == 'mil' else 'de reais'}"


def arredondar(valor):
    """Arredonda (meio para cima) mantendo 2 algarismos significativos, sem zerar a parte inteira."""
    if valor == 0:
        return "0"
    casas = max(0, 1 - math.floor(math.log10(valor)))  # 24,87 → 0 casas; 7,31 → 1; 0,163 → 2
    v = f"{Decimal(str(valor)).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP):f}"
    if "." in v:
        v = v.rstrip("0").rstrip(".")
    return v.replace(".", ",")


def simplificar_grandeza(m):
    valor = float(m.group(1).replace(".", "").replace(",", "."))
    return f"{arredondar(valor)} {m.group(2)}"


def reais_em_milhoes(m):
    reais = int(m.group(1).replace(".", ""))
    return f"R$ {arredondar(reais / 1_000_000)} MM"


def centavos(m):
    """R$ 0,71 → 71 centavos; R$ 0,107 → 10,7 centavos."""
    dec = m.group(1).ljust(2, "0")
    inteiro, resto = int(dec[:2]), dec[2:].rstrip("0")
    valor = f"{inteiro},{resto}" if resto else str(inteiro)
    return f"{valor} {'centavo' if valor == '1' else 'centavos'}"


def falar(texto):
    t = URL.sub("", texto)
    t = REAIS_POR_EXTENSO.sub(reais_em_milhoes, t)
    t = GRANDEZA.sub(simplificar_grandeza, t)
    t = PORCENTAGEM.sub(lambda m: f"{arredondar(float(m.group(1).replace(',', '.')))}%", t)
    t = VALOR_GRANDE.sub(valor_grande, t)
    t = CENTAVOS.sub(centavos, t)
    t = re.sub(r"(?<=\d)\s?MM(?!\w)|\bMM\b", " milhões", t)
    t = DATA.sub(data_falada, t)
    for sigla, fala in sorted(SIGLAS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"(?<![\w/]){re.escape(sigla)}(?![\w/])", fala, t)
    for palavra, fala in sorted(INGLES.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"(?<![\w/]){re.escape(palavra)}(?![\w/])", fala, t, flags=re.IGNORECASE)
    t = TICKER.sub(soletrar_ticker, t)
    t = re.sub(r"\bp\.p\.", "pontos percentuais", t)
    t = re.sub(r"%\s?a\.?a\.?(?=\W|$)", "% ao ano", t)
    t = re.sub(r"%\s?a\.?m\.?(?=\W|$)", "% ao mês", t)
    t = re.sub(r"/cota\b", " por cota", t)
    t = re.sub(r"/m²", " por metro quadrado", t)
    t = re.sub(r"\s*\+\s*", " mais ", t)
    t = re.sub(r"\s[xX]\s", " versus ", t)
    t = re.sub(r"[*_#|`]", "", t)
    t = t.replace("–", ",").replace("—", ",")
    return re.sub(r"[ \t]+", " ", t).strip()


if __name__ == "__main__":
    import sys
    for linha in sys.argv[1:] or sys.stdin:
        print(falar(linha.rstrip("\n")))
