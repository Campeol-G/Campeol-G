#!/usr/bin/env python3
"""
Converte uma imagem em ASCII art para usar como logo do README de perfil.

Ideia: o logo precisa ser uma grade de caracteres monoespacados, entao a
imagem e' reduzida para N colunas e a altura e' derivada da proporcao da
imagem (caracteres de terminal sao ~2x mais altos que largos).

Uso:
    python3 tools/ascii_art.py entrada.png --cols 44 --out logo.txt
    python3 tools/ascii_art.py entrada.png --cols 44 --mode duo --out logo.txt
"""

import argparse
import sys

import numpy as np
from PIL import Image

# Ramp de brightness -> caractere. Do mais claro (fundo) ao mais escuro.
RAMP = " .:-=+*#%@"
# Ramp "bloco": do espaco (fundo) ao bloco cheio.
BLOCKS = " ░▒▓█"
# Ramp "blocos de meio": 8 blocos + cheio -> mais tons, melhor legibilidade.
BLOCKS8 = " ▘▝▗▖▌▐▞▚█"
# Ramp "blocos forte": menos niveis -> mais tinta, melhor leitura em fundo claro.
BLOCKS_STRONG = " ▒▓█"
# Ramp "blocos 6": seis niveis usando meios-blocos.
BLOCKS6 = " ▖▌▐▞▚█"
# Ramp "blocos medio": 3 niveis, sem o mais leve.
BLOCKS_MED = " ░▓█"
# Ramp "pesada": sem espaco no topo, todo pixel desenhado (boa leitura em claro).
HEAVY = ".:-=+*#%@"
# Ramp classica de 70 niveis (a dos ASCII arts antigos): cobertura de tinta
# crescente, feita para foto. Densidade alta onde a imagem e' escura.
PHOTO = (" `^\",:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$")
# Rampas ASCII densas: poucos niveis, mas cada caractere cobre bastante
# celula. Sao as que funcionam em foto, porque caractere fino = ruido.
ASCII5 = " .:oO@"
ASCII4 = " .oO@"
ASCII6 = " .:coO@"
ASCII3 = " .O@"
# Rampas densas com mais niveis: cada caractere ainda preenche bem a celula,
# mas com mais tons para a imagem ficar mais fiel.
ASCII8 = " .:coO@#"
ASCII10 = " .:coO@#%M"
ASCII7 = " .coO@#"
# Ramp para imagens coloridas/flat (identicon do GitHub, por exemplo).
DUO = " #"

RAMPS = {
    "gray": RAMP,
    "blocks": BLOCKS,
    "blocks8": BLOCKS8,
    "blocks_strong": BLOCKS_STRONG,
    "blocks6": BLOCKS6,
    "blocks_med": BLOCKS_MED,
    "heavy": HEAVY,
    "photo": PHOTO,
    "ascii5": ASCII5,
    "ascii4": ASCII4,
    "ascii6": ASCII6,
    "ascii3": ASCII3,
    "ascii8": ASCII8,
    "ascii10": ASCII10,
    "ascii7": ASCII7,
    "duo": DUO,
}


def load_square(path, size=512, sharpen=0.0):
    """Abre a imagem, corta no quadrado central e devolve em tons de cinza."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).convert("L")
    if sharpen:
        from PIL import ImageFilter
        img = img.filter(ImageFilter.UnsharpMask(
            radius=2.0, percent=int(sharpen * 100), threshold=2))
    return img.resize((size, size), Image.LANCZOS)


def local_autocontrast(arr, win):
    """Estica o contraste localmente: cada janela usa o proprio min/max.

    E' o que salva foto de animal escuro/embaçado: o focinho ganha contraste
    mesmo estando numa regiao globalmente escura.
    """
    h, w = arr.shape
    out = np.zeros_like(arr, dtype=np.float32)
    step = max(1, win // 2)
    for y in range(h):
        y0, y1 = max(0, y - step), min(h, y + step + 1)
        for x in range(w):
            x0, x1 = max(0, x - step), min(w, x + step + 1)
            patch = arr[y0:y1, x0:x1]
            lo, hi = float(patch.min()), float(patch.max())
            if hi - lo < 1e-6:
                out[y, x] = 0.0
            else:
                out[y, x] = (arr[y, x] - lo) * 255.0 / (hi - lo)
    return out


# Matriz de Bayer 8x8: dithering ordenado. Distribui o erro de quantizacao
# em padrao regular, o que da muito mais aparencia de detalhe do que um
# degrade suave -- essencial pra foto de animal escuro.
BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32)


def dither(arr, levels):
    """Dithering ordenado de Bayer: devolve indices de 0..levels-1."""
    h, w = arr.shape
    bayer = np.tile(BAYER8, (h // 8 + 1, w // 8 + 1))[:h, :w]
    threshold = (bayer / 64.0 + 0.5 / levels) * (255.0 / levels)
    scaled = arr / 255.0 * levels + (threshold - 127.5) / 255.0
    return np.clip(np.floor(scaled), 0, levels - 1).astype(np.int32)


def to_gray_matrix(path, cols, gamma=1.0, levels=False, local=0, dither_levels=0, sharpen=0.0):
    src = load_square(path, 512, sharpen)
    arr = np.asarray(src, dtype=np.float32)

    if local:
        arr = local_autocontrast(arr, local)

    if levels:
        lo, hi = np.percentile(arr, 2), np.percentile(arr, 98)
        if hi - lo < 1e-6:
            lo, hi = 0.0, 255.0
        arr = np.clip((arr - lo) * 255.0 / (hi - lo), 0, 255)

    if gamma != 1.0:
        arr = 255.0 * np.power(arr / 255.0, gamma)

    # Altura em linhas: o caractere de terminal e' ~2x mais alto que largo.
    lines = max(1, round(cols / 2))
    img = Image.fromarray(arr.astype(np.uint8)).resize((cols, lines), Image.LANCZOS)
    if dither_levels:
        idx = dither(np.asarray(img, dtype=np.float32), dither_levels)
        # dither_levels niveis, mapeados para 0..255 (o render usa o ramp)
        mat = [int(v) for v in (idx * 255 // max(1, dither_levels - 1)).flatten()]
        return mat, cols, lines
    return list(img.getdata()), img.size[0], img.size[1]


def to_dual_matrix(path, cols):
    """Matriz binaria: 1 onde a corzao 'saturada' (a forma), 0 no fundo."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    px = list(img.resize((cols, max(1, round(cols / 2))), Image.LANCZOS).getdata())
    mat = []
    for r, g, b in px:
        v = 1.0 - (r / 255.0)
        mat.append(1 if v > 0.12 else 0)
    return mat, cols, max(1, round(cols / 2))


def to_stencil_matrix(path, cols, threshold=0.55, local=0):
    """Posteriza em 2 niveis (estencil): escuro vira bloco, claro vira fundo."""
    src = load_square(path, 512)
    arr = np.asarray(src, dtype=np.float32)
    if local:
        arr = local_autocontrast(arr, local)
    lines = max(1, round(cols / 2))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((cols, lines), Image.LANCZOS)
    cut = threshold * 255.0
    mat = [0 if v >= cut else 255 for v in img.getdata()]
    return mat, cols, lines


def render(path, cols, mode, gamma=1.0, levels=False, invert=False, local=0,
           threshold=0.55, dither_levels=0, sharpen=0.0):
    if mode == "duo":
        mat, w, h = to_dual_matrix(path, cols)
        ramp = DUO
    elif mode == "stencil":
        mat, w, h = to_stencil_matrix(path, cols, threshold, local)
        ramp = " █"
    else:
        mat, w, h = to_gray_matrix(path, cols, gamma, levels, local, dither_levels, sharpen)
        ramp = RAMPS[mode]
    if invert:
        mat = [255 - v for v in mat]
    lines = []
    for y in range(h):
        row = "".join(ramp[min(len(ramp) - 1, mat[y * w + x] * len(ramp) // 256)] for x in range(w))
        lines.append(row)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=44)
    ap.add_argument("--mode", choices=list(RAMPS) + ["stencil"], default="gray")
    ap.add_argument("--threshold", type=float, default=0.55, help="corte do stencil (0-1)")
    ap.add_argument("--dither", type=int, default=0, help="niveis com dithering de Bayer")
    ap.add_argument("--sharpen", type=float, default=0.0, help="unsharp mask (0-300)")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--levels", action="store_true", help="estica o contraste automaticamente")
    ap.add_argument("--invert", action="store_true", help="inverte o brilho")
    ap.add_argument("--local", type=int, default=0,
                    help="auto-contraste local (janela em px da imagem maior)")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    lines = render(args.image, args.cols, args.mode, args.gamma, args.levels,
                   args.invert, args.local, args.threshold, args.dither, args.sharpen)
    # Todas as linhas com o mesmo numero de caracteres (espacos a direita),
    # para o SVG poder forcar a largura via textLength sem quebrar a grade.
    width = max(len(l) for l in lines)
    lines = [l.ljust(width) for l in lines]

    text = "\n".join(lines) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{len(lines)} linhas x {width} colunas -> {args.out}")


if __name__ == "__main__":
    main()
