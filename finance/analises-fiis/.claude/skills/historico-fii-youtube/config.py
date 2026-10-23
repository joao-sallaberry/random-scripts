"""Configuração local da skill, lida do .env ao lado deste arquivo (fora do git; modelo em .env.example).

Uma variável de ambiente de mesmo nome tem precedência sobre o .env.
"""
import os
from pathlib import Path

ENV = Path(__file__).with_name(".env")


def caminho(nome):
    """Valor de `nome` como Path (com ~ expandido), ou None se não estiver definido."""
    valor = os.environ.get(nome)
    if valor is None and ENV.exists():
        for linha in ENV.read_text(encoding="utf-8").splitlines():
            chave, sep, v = linha.partition("=")
            if sep and chave.strip() == nome and not chave.lstrip().startswith("#"):
                valor = v.strip().strip("\"'")
    return Path(valor).expanduser() if valor else None


HISTORICO_DIR = caminho("HISTORICO_DIR")
