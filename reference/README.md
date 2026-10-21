# Referências

Material de origem da arte do card.

## `logo_blocks_96.txt`

A arte do cachorro em **96 colunas usando caracteres de bloco** (`░▒▓█`), com dithering de
Bayer. É a **fonte** da arte do card: `tools/resample_art.py` reduz essa grade para 72 colunas
e escreve o `logo.txt`, que é o que o card desenha.

Por que 72 colunas: a coluna do README de perfil no GitHub tem até ~940px (o container de
1280px menos a sidebar de 296px). Com 96 colunas o card ficaria com 1880px e o GitHub
encolheria tudo para 35% — a fonte de 16px viraria 5,5px e a arte viraria um borrão. Com 72
colunas o card cabe em 1268px, a fonte chega a 11,9px numa janela grande, e a arte continua
com a cara legível.

## `logo_ascii_96.txt`

A mesma imagem em ASCII de 10 níveis (`` ` .:coO@#%M ``). Fica mais "ASCII" e mais suave, mas
perde o detalhe do bloco quando a grade é reduzida. Está aqui como referência.

### Como regenerar

```bash
# arte do card: 72 colunas, a partir da arte de blocos em 96
python3 tools/resample_art.py reference/logo_blocks_96.txt logo.txt --cols 72

# renderizar o card
python3 tools/render.py --data data.json --style cli --theme both --assign light --outdir .
```

### Se a foto voltar a aparecer

A foto que originou as artes não está mais no repo. Se ela aparecer de novo:

```bash
# arte em blocos (96 colunas, dithering de Bayer + auto-contraste local)
python3 tools/ascii_art.py FOTO.png --cols 96 --mode blocks --dither 4 --local 24 \
    --out reference/logo_blocks_96.txt

# arte em ASCII de 10 niveis
python3 tools/ascii_art.py FOTO.png --cols 96 --mode ascii10 --local 128 \
    --out reference/logo_ascii_96.txt
```

### Rampas disponíveis

| modo | caracteres | uso |
|---|---|---|
| `blocks` | `░▒▓█` | **o que está em uso** — sólido, o dithering funciona melhor |
| `ascii10` | `` ` .:coO@#%M `` | 10 níveis, densa, boa em foto |
| `ascii8` | ` .:coO@#` | 8 níveis, um pouco mais limpo |
| `ascii5` | ` .:oO@` | 5 níveis, quase stencil, o mais legível |
| `blocks8` | `▘▝▗▖▌▐▞▚█` | meios-blocos — vira ruído em foto |
| `gray` | ` .:-=+*#%@` | ASCII clássico, fino demais em alta resolução |
| `photo` | 70 níveis | rampa clássica de foto, só funciona sem dithering |

**Dica:** caractere ASCII tem tinta fininha, então rampa com poucos níveis e caracteres densos
(`o`, `O`, `@`, `#`) funciona muito melhor que rampa com 10+ caracteres finos. E a janela do
auto-contraste local precisa ser grande (≥ 96) em alta resolução — janela pequena amplifica
cada grão da foto e vira estática.

`logo_scale` no `data.json` reduz o tamanho físico da arte sem perder colunas de detalhe: o
`textLength` fixa a largura de cada linha, então a grade nunca quebra.
