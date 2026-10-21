#!/usr/bin/env python3
"""
Reamostra a arte ASCII/blocos para outra grade de colunas.

A foto que originou a arte nao esta mais no repo, entao a arte de 96 colunas
virou a fonte: reduzir a grade e o que permite o card caber na coluna do
GitHub sem virar borrao.

Cada caractere vale um nivel de densidade; a celula destino e a media
ponderada da area que ela cobre, e o resultado volta pra rampa.

Uso:
    python3 tools/resample_art.py reference/logo_blocks_96.txt logo.txt --cols 72
"""

import argparse

# Rampas conhecidas, do mais claro (fundo) pro mais escuro.
RAMPS = {
    "ascii": " .:coO@#%M",
    "blocks": " ░▒▓█",
}


def load(path):
    """Le a arte e devolve as linhas com o mesmo tamanho (pra grade nao quebrar)."""
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    width = max((len(l) for l in lines), default=0)
    return [l.ljust(width) for l in lines]


def detect_ramp(lines):
    """Descobre a rampa pelo caractere mais escuro que aparece na arte."""
    chars = {c for line in lines for c in line}
    for name, ramp in RAMPS.items():
        if chars <= set(ramp):
            return ramp
    return RAMPS["ascii"]


def resample(lines, cols, ramp):
    """Reamostra a arte para `cols` colunas, mantendo a proporcao da imagem."""
    idx = {c: i for i, c in enumerate(ramp)}
    top = len(ramp) - 1
    src_h = len(lines)
    src_w = len(lines[0]) if lines else 0
    # Caractere de terminal e' ~2x mais alto que largo.
    rows = max(1, round(cols / 2))
    out = []
    for r in range(rows):
        y0 = r * src_h / rows
        y1 = (r + 1) * src_h / rows
        row = []
        for c in range(cols):
            x0 = c * src_w / cols
            x1 = (c + 1) * src_w / cols
            total = 0.0
            area = 0.0
            for y in range(int(y0), max(int(y0) + 1, int(y1 + 0.999))):
                for x in range(int(x0), max(int(x0) + 1, int(x1 + 0.999))):
                    wy = min(y1, y + 1) - max(y0, y)
                    wx = min(x1, x + 1) - max(x0, x)
                    a = wy * wx
                    if a <= 0:
                        continue
                    ch = lines[y][x] if x < src_w else " "
                    total += idx.get(ch, 0) * a
                    area += a
            value = total / area if area else 0
            row.append(ramp[min(top, int(round(value)))])
        out.append("".join(row).rstrip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--cols", type=int, required=True)
    args = ap.parse_args()

    lines = load(args.entrada)
    if not lines:
        raise SystemExit(f"arte vazia: {args.entrada}")

    ramp = detect_ramp(lines)
    art = resample(lines, args.cols, ramp)
    with open(args.saida, "w", encoding="utf-8") as f:
        f.write("\n".join(art) + "\n")
    print(f"{len(art)} linhas x {args.cols} colunas -> {args.saida}")


if __name__ == "__main__":
    main()
