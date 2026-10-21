# Referências

Material que não é usado pelo card, mas vale guardar para consultar depois.

## `logo_blocks_96.txt`

A versão do logo do cachorro em **96 colunas usando caracteres de bloco** (`░▒▓█`), com
dithering de Bayer. É a variante "sólida", mais fácil de ler de longe e com mais textura — uma
alternativa ao ASCII de 10 níveis que está no `logo.txt` da raiz.

**Não está em uso no card.** Está aqui como referência para trocar a qualquer momento.

### Como regenerar

```bash
# arte em blocos (96 colunas, dithering de Bayer + auto-contraste local)
python3 tools/ascii_art.py FOTO.png --cols 96 --mode blocks --dither 4 --local 24 \
    --out reference/logo_blocks_96.txt

# arte em ASCII de 10 niveis (o que esta no card)
python3 tools/ascii_art.py FOTO.png --cols 96 --mode ascii10 --local 128 --out logo.txt

# renderizar o card
python3 tools/render.py --data data.json --style cli --theme both --assign light --outdir .
```

### Rampas disponíveis

| modo | caracteres | uso |
|---|---|---|
| `ascii10` | `` ` .:coO@#%M `` | **o que está em uso** — 10 níveis, densa, boa em foto |
| `ascii8` | ` .:coO@#` | 8 níveis, um pouco mais limpo |
| `ascii5` | ` .:oO@` | 5 níveis, quase stencil, o mais legível |
| `blocks` | `░▒▓█` | em blocos, mais sólido, dithering funciona melhor |
| `blocks8` | `▘▝▗▖▌▐▞▚█` | meios-blocos — vira ruído em foto |
| `gray` | ` .:-=+*#%@` | ASCII clássico, fino demais em alta resolução |
| `photo` | 70 níveis | rampa clássica de foto, só funciona sem dithering |

**Dica:** caractere ASCII tem tinta fininha, então rampa com poucos níveis e caracteres densos
(`o`, `O`, `@`, `#`) funciona muito melhor que rampa com 10+ caracteres finos. E a janela do
auto-contraste local precisa ser grande (≥ 96) em alta resolução — janela pequena amplifica
cada grão da foto e vira estática.

`logo_scale` no `data.json` (0.78) reduz o tamanho físico do logo sem perder colunas de detalhe:
o `textLength` fixa a largura de cada linha, então a grade nunca quebra.
