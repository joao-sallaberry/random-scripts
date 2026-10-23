# historico-fii-youtube

A skill `historico-fii-youtube` do Claude Code mantém um histórico por fundo imobiliário e por canal a partir de vídeos do YouTube.

Ela procura os vídeos com o ticker no título que ainda não estão no histórico e lê as legendas automáticas. Depois acrescenta ao histórico:
- o resumo de cada vídeo, com os números citados;
- o sentimento do autor sobre o fundo;
- a evolução da opinião dele ao longo do tempo.

Os históricos ficam fora do repositório.

Canais suportados:

| Slug | Canal |
|---|---|
| `fiicaesperto` | [FIIcaEsperto](https://www.youtube.com/channel/UCOe1sCwSXRf-clKYdmgO1Kw) |
| `liberdade-e-logo-ali` | [Liberdade é Logo Ali (Eric Leonardo)](https://www.youtube.com/channel/UCOn6-uNuXeXJqmbywtfBgdQ) |

## Requisitos

- Python 3.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Configuração

Nesta pasta, copie o `.env.example` para `.env` e defina `HISTORICO_DIR`, a pasta raiz dos históricos. O `.env` não vai para o git.

```sh
cp .env.example .env
```

## Uso

Abra o Claude Code na pasta `finance/analises-fiis/` e peça:

```
/historico-fii-youtube JSRE11                         # atualiza o JSRE11 em todos os canais
/historico-fii-youtube JSRE11 --canal fiicaesperto    # só num canal
/historico-fii-youtube                                # atualiza todos os históricos existentes
```

O histórico do `JSRE11` no FIIcaEsperto fica em `<HISTORICO_DIR>/fiicaesperto/JSRE.md`.

Quando um termo relevante da legenda automática estiver duvidoso, como um ticker ou o nome de um imóvel, a skill pergunta antes de escrever. As respostas vão para o `glossario.md` e são aplicadas sozinhas nas próximas vezes.

Para só ver quais vídeos novos existem, rode o script direto:

```sh
python3 .claude/skills/historico-fii-youtube/buscar_videos.py --canais
python3 .claude/skills/historico-fii-youtube/buscar_videos.py JSRE11 --canal fiicaesperto --out /tmp/transcricoes
```
