---
name: historico-fii-youtube
description: Atualiza (ou cria) o histórico de um FII a partir dos vídeos de canais de YouTube sobre FIIs (FIIcaEsperto, Liberdade é Logo Ali), com resumo, números e sentimento/opinião do autor por vídeo. Use quando o usuário pedir para atualizar o histórico de um fundo (ex. "atualiza o JSRE", "tem vídeo novo do FIIcaEsperto sobre TEPP11?", "faz o histórico do JSRE11 no canal do Eric Leonardo") ou criar o histórico de um fundo novo.
argument-hint: "[TICKER ...] [--canal SLUG]  (vazio = atualizar todos os históricos existentes)"
---

# Histórico de FIIs pelos vídeos de canais do YouTube

Os históricos ficam fora do repositório, em `<HISTORICO_DIR>/<canal>/<BASE>.md`:
- `HISTORICO_DIR` vem do `.env` ao lado deste arquivo;
- `<canal>` é o slug do canal;
- `<BASE>` é o ticker sem o sufixo numérico (`JSRE11` → `JSRE.md`).

O H1 de cada arquivo começa com o ticker completo (`# JSRE11: ...`). Use-o para descobrir o ticker quando nenhum for passado.

Os canais conhecidos estão em `CANAIS`, no `buscar_videos.py`, e `python3 ${CLAUDE_SKILL_DIR}/buscar_videos.py --canais` os lista. Para acrescentar um canal, inclua o slug, o nome e a URL `youtube.com/channel/<id>` nesse dicionário e na lista do `README.md`.

Se o script reclamar que falta `HISTORICO_DIR`, peça ao usuário para criar o `.env` a partir do `.env.example`.

## Passos

1. **Escolher fundos e canais.**
   - Tickers e `--canal` vêm de `$ARGUMENTS`. Se o usuário citar o canal pelo nome ou pelo apresentador, mapeie para o slug.
   - Sem `--canal`, use todos os canais.
   - Sem ticker, atualize todos os `.md` existentes em `<HISTORICO_DIR>/<canal>/`, lendo o ticker do H1 de cada um.
   - Ao criar o histórico de um fundo num canal onde ele ainda não existe, confirme antes com o usuário se o canal tiver muitos vídeos do fundo (mais de ~15).
2. **Buscar vídeos novos.** Para cada par fundo × canal, rode o script, com a saída numa pasta nova dentro do scratchpad:
   ```sh
   python3 ${CLAUDE_SKILL_DIR}/buscar_videos.py JSRE11 --canal fiicaesperto --out <scratchpad>/videos-fiicaesperto-JSRE11
   ```
   O script:
   - lista vídeos, lives e shorts do canal com o ticker no título;
   - descarta os IDs que já aparecem no histórico (os links nos títulos das seções);
   - salva a transcrição de cada vídeo novo em `<data>_<id>.txt`;
   - imprime um JSON com o canal, o caminho do histórico, se ele existe e os vídeos novos, do mais antigo para o mais novo.

   Listar um canal leva alguns minutos, então use timeout de 600000 ms. Quando houver vários pares, rode-os em paralelo, em background. Se não houver vídeos novos, diga isso e não mexa no arquivo.
3. **Ler cada transcrição por inteiro.** São legendas automáticas, e nomes próprios vêm truncados.
   - Antes de ler, carregue `${CLAUDE_SKILL_DIR}/glossario.md`, que vale para todos os canais, e aplique as correções conhecidas.
   - Liste os trechos relevantes que continuarem duvidosos: tickers, nomes de imóveis, gestoras, regiões, números ou frases cujo sentido muda a análise.
   - **Pergunte ao usuário antes de escrever o histórico.**
     - Para cada dúvida, ache o horário do trecho no `.vtt` do vídeo (campo `legenda` do JSON), por exemplo com `grep -i -B3 '<termo>' <legenda> | grep -oE '^[0-9:.]+ -->' | head -1`.
     - Primeiro mostre, em texto, a lista de dúvidas. Cada item leva o trecho original entre aspas, o canal, a data do vídeo e o link já no horário, `https://www.youtube.com/watch?v=<id>&t=<segundos>s`, recuado ~5 s, para o usuário poder ouvir.
     - Depois pergunte com AskUserQuestion, com até 4 perguntas por chamada e suas melhores hipóteses como opções. Repita os links na pergunta.
   - Termos irrelevantes para a análise não precisam de pergunta: omita-os.
   - Toda correção confirmada vai para o glossário, marcada como (confirmado).
   - Nunca invente ticker. Se o usuário não souber, mantenha o texto vago.
   - Se o vídeo não tiver legenda (`tem_legenda: false`), registre-o na seção só com o título e "sem legenda disponível".
4. **Atualizar o histórico** no formato abaixo:
   - acrescente uma seção por vídeo novo no fim de "Vídeo a vídeo", em ordem cronológica;
   - acrescente uma linha por vídeo na tabela;
   - revise "Evolução do sentimento", "O que mudou" e a tese final para refletir os vídeos novos;
   - atualize a contagem de vídeos e o intervalo de datas no parágrafo de abertura.

   Edite com Edit e preserve o que já está escrito. Só corrija conteúdo antigo se um vídeo novo o contradisser explicitamente, e nesse caso registre isso no texto ("corrigido no vídeo de dd/mm/aaaa").
5. **Fundo sem histórico no canal:** crie `<HISTORICO_DIR>/<canal>/<BASE>.md` do zero com todos os vídeos encontrados. Cada canal tem o próprio histórico: não misture canais num mesmo arquivo.
6. **Responder ao usuário** com um resumo curto, por canal: vídeos novos (data e título), sentimento de cada um, o que mudou de relevante e o caminho do arquivo. Quando houver históricos do mesmo fundo em mais de um canal, aponte numa frase se os autores concordam ou divergem.

## Formato do arquivo

```markdown
# <TICKER>: histórico pelos vídeos do <nome do canal>

Resumo dos N vídeos do canal <nome do canal> com "<ticker>" no título, de <mês/ano> a <mês/ano>, com as atualizações relevantes e a opinião do autor em ordem cronológica.

> Baseado nas transcrições automáticas dos vídeos. Os números são os citados pelo autor e não foram conferidos nos relatórios. Vídeos de vários fundos que só mencionam o <TICKER>, sem o ticker no título, ficaram de fora. Nada aqui é recomendação.

## Linha do tempo resumida

| Data do vídeo | Sentimento | Rendimento/cota | Resultado/cota | Desconto sobre o VP | Fato marcante |
|---|---|---|---|---|---|
| dd/mm/aaaa | 🟡 Neutro | R$ 0,48 | R$ 0,52 | 36% | ... |

Escala de sentimento: 🔴 negativo, 🟠 neutro-negativo, 🟡 neutro, 🟢 neutro-positivo, 🔵 positivo.

## Evolução do sentimento
<O que é constante na visão do autor, o que oscila e por quê, com as viradas de tom por período.>

## Vídeo a vídeo

### dd/mm/aaaa: [<título sem o "#ticker - ">](https://www.youtube.com/watch?v=<id>)
**Sentimento: 🟡 Neutro.** <1 a 3 frases com a opinião do autor sobre o fundo, citando expressões dele entre aspas.>
- **<Tema>:** fatos e números do vídeo...

## O que mudou ao longo de <período>
**Melhorou**
- ...

**Piorou ou continua pendente**
- ...

**A tese do autor, estável nos N vídeos:** ...
```

## Regras

- **Link obrigatório no título de cada seção.** É por ele que o script sabe quais vídeos já foram incluídos.
- **Títulos dos vídeos:** use o título do cabeçalho da transcrição, que vem da página do vídeo. A listagem do canal pode trazer o título traduzido automaticamente para o inglês.
- **Canais com vídeos muito frequentes** (ex. atualização mensal do mesmo fundo): mantenha cada seção curta e concentre os detalhes nos vídeos com fatos novos.
- **Sentimento = opinião do autor sobre o fundo como investimento,** não sobre o mercado em geral.
  - Baseie a nota nas conclusões e no tom do vídeo e justifique com citações curtas.
  - Vídeos comparativos (`#a x #b`, `#a | #b`) avaliam o fundo deste histórico. Inclua o placar ou o veredito.
- **Na tabela, use "—"** quando o vídeo não citar o número. Dado histórico citado num vídeo posterior, como um pico de desconto, pode virar uma linha própria com sentimento "—".
- **Números só do vídeo.** Contas suas, como o yield anual a partir do mensal, podem entrar desde que indicadas.
- **Pt-br com acentuação correta.**
- **Nunca grave os históricos nem as transcrições dentro do repositório.** O glossário, por outro lado, faz parte da skill e é commitado.
