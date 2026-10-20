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

from PIL import Image

# Ramp de brightness -> caractere. Do mais claro (fundo) ao mais escuro.
RAMP = " .:-=+*#%@"
# Ramp "bloco": daspace (fundo) ao bloco cheio.
BLOCKS = " ░▒▓█"
# Ramp para imagens coloridas/flat (identicon do GitHub, por exemplo).
DUO = " #"

RAMPS = {"gray": RAMP, "blocks": BLOCKS, "duo": DUO}


def load_gray(path, cols):
    """Abre a imagem, corta num quadrado e devolve (matriz de brilho, w, h)."""
    img = Image.open(path).convert("RGB")

    # Recorta no quadrado central para nao distorcer a arte.
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Cada caractere ocupa ~2x a altura da largura, entao a altura em linhas
    # e' metade da altura em pixels.
    lines = max(1, round(cols * (side / side) / 2))
    px_w = cols
    px_h = lines
    return img.resize((px_w, px_h), Image.LANCZOS)


def to_gray_matrix(path, cols, gamma=1.0, levels=False):
    img = load_gray(path, cols).convert("L")
    if levels:
        # Normaliza o contraste: usa o percentil 2..98 para esticar a faixa.
        hist = img.histogram()
        total = sum(hist)
        lo, hi = 0, 255
        acc = 0
        for i, c in enumerate(hist):
            acc += c
            if acc >= total * 0.02:
                lo = i
                break
        acc = 0
        for i, c in enumerate(hist):
            acc += c
            if acc >= total * 0.98:
                hi = i
                break
        if hi <= lo:
            lo, hi = 0, 255
        img = img.point(lambda v: max(0, min(255, int((v - lo) * 255 / (hi - lo)))))
    if gamma != 1.0:
        img = img.point(lambda v: int(255 * ((v / 255.0) ** gamma)))
    return list(img.getdata()), img.size[0], img.size[1]


def to_dual_matrix(path, cols):
    """Matriz binaria: 1 onde a corzao 'saturada' (a forma), 0 no fundo."""
    img = load_gray(path, cols)
    px = list(img.getdata())
    # Usa o canal R como proxy de "quanto tem de cor" (fundo branco = 0).
    mat = []
    for r, g, b in px:
        # branco -> 0, rosa saturado -> 1
        v = 1.0 - (r / 255.0)
        mat.append(1 if v > 0.12 else 0)
    return mat, img.size[0], img.size[1]


def render(path, cols, mode, gamma=1.0, levels=False):
    if mode == "duo":
        mat, w, h = to_dual_matrix(path, cols)
        ramp = DUO
    else:
        mat, w, h = to_gray_matrix(path, cols, gamma, levels)
        ramp = RAMPS[mode]
    lines = []
    for y in range(h):
        row = "".join(ramp[min(len(ramp) - 1, mat[y * w + x] * len(ramp) // 256)] for x in range(w))
        lines.append(row)
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=44)
    ap.add_argument("--mode", choices=["gray", "blocks", "duo"], default="gray")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--levels", action="store_true", help="estica o contraste automaticamente")
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    lines = render(args.image, args.cols, args.mode, args.gamma, args.levels)
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
