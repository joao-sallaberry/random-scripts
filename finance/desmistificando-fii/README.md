# desmistificando-fii

Scripts para arquivar e ouvir o Relatório Semanal de FIIs do DesmistificandoFII:

1. Você salva a página do relatório pelo navegador.
2. O `arquivar.py` transforma a página num Markdown com as imagens e mantém um índice de todas as edições.
3. O `to_audio.py` gera o áudio, em `.m4b` com capítulos ou um MP3 por seção.
4. A skill `resumo-fii` do Claude Code resume o que os relatórios dizem de um fundo.

Os scripts usam só a biblioteca padrão do Python. Os relatórios são conteúdo de assinante e ficam fora do repositório.

## Requisitos

- Python 3.
- Para o áudio:
  - [edge-tts](https://github.com/rany2/edge-tts), com `uv tool install edge-tts`. Se der erro 403, rode `uv tool upgrade edge-tts`.
  - `ffmpeg` e `ffprobe`.
  - Opcional, para TTS local sem internet: [Piper](https://github.com/OHF-Voice/piper1-gpl), com `uv tool install piper-tts`, mais as vozes em `~/.local/share/piper-voices`:
    ```sh
    ~/.local/share/uv/tools/piper-tts/bin/python -m piper.download_voices \
        --data-dir ~/.local/share/piper-voices pt_BR-faber-medium
    ```

## Configuração

Copie o `.env.example` para `.env` e defina `RELATORIOS_DIR`, a pasta onde os relatórios ficam arquivados. O `.env` não vai para o git.

```sh
cp .env.example .env
```

## 1. Salvar o relatório

Abra o relatório no site e salve com **Salvar como → Página da Web, completa**. O navegador grava o `.html` e uma pasta `<nome>_files/` com as imagens. Os dois precisam ficar juntos.

## 2. Arquivar

```sh
python3 arquivar.py relatorio-FIIS-43-17-10-2026.html
python3 arquivar.py pasta-com-relatorios/         # todos os .html de uma pasta
python3 arquivar.py                                # só refaz o indice.md
python3 arquivar.py relatorio.html --destino ~/outra/pasta --force
```

Cada edição vai para a pasta `RELATORIOS_DIR` do `.env` (ou para a de `--destino`):

```
2026-10-17 - Relatorio FII 43/
    Relatorio FII 43 - 2026-10-17.md    metadados (front matter) + uma seção "## NN. Título" por tópico
    imagens/01.webp, 02.png, ...        figuras do texto
    original.html                       a página sem scripts, apontando para imagens/
indice.md                               todas as edições e, por fundo, as seções que tratam dele
```

- **Edições já arquivadas:** são puladas. O `--force` regera a edição, e o `original.html` arquivado serve de entrada para isso: `python3 arquivar.py ".../original.html" --force`.
- **Página baixada de novo:** traz as cotações do dia em que foi salva. Para manter os preços da época, não use `--force` só porque baixou de novo.
- **`indice.md`:** é refeito a cada execução.
  - **Edições:** uma tabela da mais recente para a mais antiga.
  - **Por fundo:** cada ticker com links para as seções que falam dele e a cotação de cada relatório.

## 3. Conferir

```sh
python3 verificar.py                       # confere o arquivo inteiro
python3 verificar.py /tmp/teste --curtas 150
```

- **O que ele aponta:**
  - links de imagem quebrados;
  - restos de HTML no Markdown;
  - títulos de seção estranhos;
  - arquivos que o `to_audio.py` não consegue ler.
- **Casos normais:** alguns apontamentos são do próprio relatório, como um ticker sozinho numa linha usado de subtítulo pelo autor.

## 4. Ouvir

```sh
python3 to_audio.py "Relatorio FII 43 - 2026-10-17.md"
python3 to_audio.py relatorio.md --so 1,3,5 --formato mp3
python3 to_audio.py relatorio.md --voz pt-BR-FranciscaNeural --velocidade +10%
python3 to_audio.py relatorio.md --motor piper --voz pt_BR-cadu-medium
```

- **Saída:** fica na pasta `<nome do md> - audio/`, ao lado do `.md`. Ela contém o `Relatorio FII NN.m4b`, com um capítulo por seção, ou `NN - <título>.mp3` com `--formato mp3`. Também tem o `roteiro.txt`, com o texto exatamente como foi falado.
- **Seções que ficam fora do áudio:** a abertura, a Carteira Recomendada e os Retornos ficam só no `.md`. O Disclaimer só entra com `--com-disclaimer`.

## 5. Resumir as análises de um fundo

Com o Claude Code aberto nesta pasta:

```
/resumo-fii GGRC11
/resumo-fii LVBI11 --ultimas 20
/resumo-fii BTLG11 --desde 2025-01-01
```

Também funciona pedindo em texto, como "qual a análise recente do RBHG11?". O resumo usa só os relatórios arquivados e traz:
- a recomendação atual e se o fundo está na Carteira Recomendada;
- o rendimento recorrente, o lucro e a distribuição por cota, com a edição de onde saiu cada número;
- a alavancagem;
- aquisições, vendas, emissões e outros eventos, as mudanças de recomendação e a conclusão do analista.

Por padrão, olha as 8 edições mais recentes com seção sobre o fundo, mais as menções a ele em outras seções.

Para ver o material bruto sem o Claude:

```sh
python3 .claude/skills/resumo-fii/buscar.py GGRC11 --ultimas 3
python3 .claude/skills/resumo-fii/buscar.py GGRC11 --desde 2026-01-01 --sem-mencoes
```
