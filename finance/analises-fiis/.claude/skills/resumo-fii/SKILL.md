---
name: resumo-fii
description: Resume as análises recentes de um FII (ticker como GGRC11, BTLG11) nos relatórios arquivados do DesmistificandoFII, a fonte principal, complementados pelos históricos dos canais do YouTube, incluindo rendimento recorrente, lucro por cota, a recomendação e a opinião dos canais. Use quando o usuário pedir o resumo, a análise recente, o recorrente ou a recomendação de um fundo.
argument-hint: TICKER [--ultimas N | --desde AAAA-MM-DD] [--sem-youtube]
---

# Resumo das análises de um FII

Responda em pt-BR e use **só** o que o `buscar.py` imprime, nunca os `original.html` ou a internet:
- **Relatórios do DesmistificandoFII** (`.md` arquivados em `RELATORIOS_DIR`, do `.env` de `desmistificando-fii/`): a fonte principal. A recomendação, os números e a estrutura do resumo vêm deles.
- **Históricos dos canais do YouTube** (`<HISTORICO_DIR>/<canal>/<BASE>.md`, mantidos pela skill `historico-fii-youtube`): um complemento. Servem para confirmar, contrastar ou trazer fatos que os relatórios não cobrem, sempre identificados pelo canal e pela data do vídeo. Os números deles vêm de legendas automáticas e não foram conferidos; quando divergirem dos relatórios, vale o relatório, e aponte a divergência.

O uso é local, então pode citar trechos à vontade, mas não grave o resumo dentro do repositório (é conteúdo de assinante).

## 1. Buscar o material

```sh
python3 ${CLAUDE_SKILL_DIR}/buscar.py TICKER                      # últimas 8 edições com seção do fundo + menções + YouTube
python3 ${CLAUDE_SKILL_DIR}/buscar.py TICKER --ultimas 20
python3 ${CLAUDE_SKILL_DIR}/buscar.py TICKER --desde 2025-01-01
```

- Imprime as seções dedicadas ao fundo (pelo "Por fundo" do `indice.md`), da mais recente para a mais antiga, e os parágrafos de outras seções que citam o ticker (cartas aos leitores, seções de outros fundos).
- Depois, em `# YouTube`, imprime o histórico do fundo em cada canal que o tem: a tabela e as seções de vídeo a partir da edição mais antiga impressa (ou da `--desde`), mais a evolução do sentimento e a tese do autor, que cobrem o histórico todo. Se nenhum canal tiver histórico do fundo, siga só com os relatórios e diga isso no fim; o histórico pode ser criado com `/historico-fii-youtube TICKER`.
- Repasse os argumentos do usuário (`$ARGUMENTS`). Sem período definido, comece pelo padrão e amplie com `--ultimas` se o material for pouco ou se for preciso histórico para comparar.
- Se o ticker não estiver no índice, o `buscar.py` sai com erro e sugere tickers parecidos; repasse isso ao usuário.
- Se reclamar que falta `RELATORIOS_DIR` (ou avisar que falta `HISTORICO_DIR`), peça ao usuário para criar o `.env` correspondente a partir do `.env.example`.
- Para rendimento recorrente, quase sempre vale buscar também mais para trás (`--desde` um ano antes) com `| grep -n -i -E 'recorrent|lucro|distribu|dividendo|rendimento|R\$ 0,'`, porque o número nem sempre aparece na edição mais recente.
- Para a alavancagem, procure no mesmo material do resumo (mesmo período) com `| grep -n -i -E 'alavanc|compromissad|endivid|dívida|obrigaç|LTV|% do PL|% do patrim'`. Em fundos de recebíveis ela costuma aparecer como operações compromissadas; em tijolo, como CRIs emitidos para comprar imóveis ou obrigações por aquisição a pagar.

## 2. Montar a resposta

1. **Resposta direta primeiro:** a recomendação atual (comprar, neutro, vender, ou se está na Carteira Recomendada), o número de recorrente mais recente e a alavancagem, com a edição e a data de onde saiu.
2. **Rendimento e resultado:** uma tabela com período, edição e dado (recorrente, lucro/cota, distribuição). Separe:
   - o que o analista **afirma** (com o número exato do relatório);
   - o que é **dedução sua** (marque como "leitura minha");
   - o que os relatórios **não informam** (diga explicitamente, em vez de inventar).
   Explique as variações (emissão de cotas, vacância, venda de imóveis com lucro não recorrente, inadimplência).
3. **Alavancagem:** o percentual mais recente sobre o patrimônio (ou o valor em R$, se só houver esse), com a edição, o indexador e o custo da dívida e os vencimentos ou carências, quando o analista informar. Mostre a evolução se houver mais de um dado. Se as edições do período não falarem em alavancagem do fundo, diga isso explicitamente (não deduza que é zero).
4. **Outros pontos da análise:** aquisições, vendas, emissões, recompras, inquilinos, governança. Bullets curtos, com datas e números.
5. **Correções:** se uma edição posterior corrige uma anterior, diga o que mudou.
6. **Conclusão do analista:** a recomendação e o motivo, citando as palavras dele quando ajudar.
7. **O que dizem os canais do YouTube:** por canal, o sentimento mais recente (com a data do vídeo e o emoji da escala do histórico), a tendência no período e os fatos ou números que acrescentam algo aos relatórios. Termine com uma frase sobre se os canais concordam ou divergem do DesmistificandoFII e entre si. Esta seção é curta e não muda a resposta direta, que segue o relatório.

Cite sempre as edições como "nº 39 (20/09/2026)" e os vídeos como "FIIcaEsperto, 22/10/2026". Valores em formato brasileiro (R$ 0,10/cota).
