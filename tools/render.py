#!/usr/bin/env python3
"""
Renderiza o README de perfil do GitHub (SVG) a partir de um data.json.

Estilos disponiveis (--style):
  box    -> moldura fechada estilo fastfetch, logo a esquerda, colunas key/value
  dots   -> sem moldura, leaders de pontos (estilo Andrew6rant) e reguas de secao
  panel  -> moldura com barra de cabecalho e modulos em duas colunas

Temas: --theme dark|light|both

Uso:
    python3 tools/render.py --data data.json --style box --theme both --outdir .
"""

import argparse
import json
import os
import xml.sax.saxutils as sax

# ---------------------------------------------------------------- metricas
FONT_SIZE = 16.0
CHAR_W = 9.6          # largura de um caractere na fonte monoespacada de 16px
CHAR_H = 18.0         # altura de uma linha
PAD = 26.0            # padding interno
LOGO_GAP = 30.0       # espaco entre logo e coluna de texto

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "frame": "#30363d",
        "frame_soft": "#21262d",
        "header_bg": "#161b22",
        "title": "#e6edf3",
        "handle": "#58a6ff",
        "subtitle": "#8b949e",
        "key": "#39c5cf",
        "value": "#c9d1d9",
        "dim": "#6e7681",
        "rule": "#30363d",
        "green": "#3fb950",
        "yellow": "#d29922",
        "magenta": "#bc8cff",
        "red": "#f85149",
        "cyan": "#39c5cf",
    },
    "light": {
        "bg": "#ffffff",
        "frame": "#d0d7de",
        "frame_soft": "#eaeef2",
        "header_bg": "#f6f8fa",
        "title": "#1f2328",
        "handle": "#0969da",
        "subtitle": "#59636e",
        "key": "#0a7d8a",
        "value": "#1f2328",
        "dim": "#818b98",
        "rule": "#d8dee4",
        "green": "#1a7f37",
        "yellow": "#9a6700",
        "magenta": "#8250df",
        "red": "#cf222e",
        "cyan": "#0a7d8a",
    },
}

# Altura do cabecalho (handle + subtitulo) em unidades de linha.
TITLE_LINES = 3.0


def esc(text):
    return sax.escape(str(text))


def font_family():
    return "'Mono','DejaVu Sans Mono','Menlo','Liberation Mono',monospace"


def svg_header(width, height, theme, extra_css=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}px" height="{height:.0f}px"
     viewBox="0 0 {width:.0f} {height:.0f}" font-family="{font_family()}" font-size="{FONT_SIZE:.0f}px">
<style>
@font-face {{
  src: local('Consolas');
  font-family: 'Mono';
  size-adjust: 94.6%;
  font-display: swap;
}}
@font-face {{
  src: local('JetBrains Mono'), local('Fira Code'), local('Menlo'),
       local('DejaVu Sans Mono'), local('Liberation Mono'), local('Courier New');
  font-family: 'Mono';
  font-display: swap;
}}
text, tspan {{ white-space: pre; }}
{extra_css}
</style>
"""


def ascii_block(lines, x, y, color, char_w=CHAR_W, char_h=CHAR_H, opacity=1.0, scale=1.0):
    """Cada linha recebe textLength fixo -> a grade nunca quebra, independente
    da fonte que o navegador resolver usar."""
    out = [f'<g opacity="{opacity}">']
    font_size = FONT_SIZE * scale
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        w = len(line) * char_w
        out.append(
            f'<text x="{x:.1f}" y="{y + i * char_h:.1f}" fill="{color}" '
            f'font-size="{font_size:.1f}px" textLength="{w:.1f}" '
            f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">{esc(line)}</text>'
        )
    out.append("</g>")
    return "\n".join(out)


def measure(data, style):
    """Calcula a geometria do layout e devolve (w, h, logo_w, logo_h, key_w, val_w, right_h)."""
    logo = data.get("logo_lines", [])
    logo_scale = 13.0 / CHAR_H if style == "panel" else 1.0
    logo_w = max((len(l) for l in logo), default=0) * CHAR_W
    logo_h = len(logo) * CHAR_H * logo_scale

    key_w = 0
    val_w = 0
    for mod in data.get("modules", []):
        for k, v in mod.get("rows", []):
            key_w = max(key_w, len(k))
            val_w = max(val_w, len(v))
    key_w = key_w * CHAR_W + 18
    val_w = val_w * CHAR_W

    mods = data.get("modules", [])

    def block_height(group):
        h = 0
        for i, mod in enumerate(group):
            if i:
                h += 14
            if mod.get("title"):
                h += CHAR_H
            h += len(mod.get("rows", [])) * CHAR_H
        return h

    if style == "panel":
        head_h = 78.0
        half = (len(mods) + 1) // 2
        cols = [mods[:half], mods[half:]]
        content_h = max(block_height(c) for c in cols) if cols else 0
        col_w = key_w + val_w
        w = PAD * 2 + logo_w + LOGO_GAP + col_w * 2 + 44
        h = head_h + PAD + max(content_h + CHAR_H, logo_h) + PAD
        return w, h, logo_w, logo_h, key_w, val_w, content_h

    right_h = TITLE_LINES * CHAR_H + 14 + block_height(mods)
    content_w = key_w + val_w
    w = PAD + logo_w + LOGO_GAP + content_w + PAD
    h = PAD + max(logo_h, right_h) + PAD
    return w, h, logo_w, logo_h, key_w, val_w, right_h


def render_box(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x):
    """Fastfetch classico: moldura fechada, logo a esquerda, colunas key/value."""
    out.append(
        f'<rect x="0.5" y="0.5" width="{w-1:.0f}" height="{h-1:.0f}" rx="14" '
        f'fill="none" stroke="{t["frame"]}" stroke-width="1"/>'
    )
    if logo:
        logo_top = PAD + max(0, (right_h - logo_h) / 2)
        out.append(ascii_block(logo, PAD, logo_top + CHAR_H - 4, t["cyan"]))

    y = PAD + CHAR_H
    out.append(
        f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["handle"]}" font-size="22px" '
        f'font-weight="700">{esc(data.get("handle", ""))}</text>'
    )
    if data.get("subtitle"):
        out.append(
            f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["subtitle"]}" '
            f'font-size="14px">{esc(data["subtitle"])}</text>'
        )

    y = PAD + TITLE_LINES * CHAR_H + 14
    for i, mod in enumerate(data.get("modules", [])):
        if i:
            y += 14
        if mod.get("title"):
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="12px" '
                f'font-weight="700" letter-spacing="1.4">{esc(mod["title"].upper())}</text>'
            )
            y += CHAR_H
        for key, value in mod.get("rows", []):
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["key"]}" '
                f'font-weight="700">{esc(key)}</text>'
            )
            out.append(
                f'<text x="{text_x + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                f'{esc(value)}</text>'
            )
            y += CHAR_H


def render_dots(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x):
    """Sem moldura: leaders de pontos e reguas de secao (estilo Andrew6rant)."""
    if logo:
        out.append(ascii_block(logo, PAD, PAD + CHAR_H - 4, t["cyan"]))

    y = PAD + CHAR_H
    out.append(
        f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["handle"]}" font-size="22px" '
        f'font-weight="700">{esc(data.get("handle", ""))}</text>'
    )
    if data.get("subtitle"):
        out.append(
            f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["subtitle"]}" '
            f'font-size="14px">{esc(data["subtitle"])}</text>'
        )

    y = PAD + TITLE_LINES * CHAR_H + 14
    for i, mod in enumerate(data.get("modules", [])):
        if i:
            y += 16
        if mod.get("title"):
            title = mod["title"]
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                f'font-weight="700">{esc(title)}</text>'
            )
            rule_x = text_x + (len(title) + 2) * CHAR_W
            rule_end = text_x + key_w + val_w
            out.append(
                f'<line x1="{rule_x:.1f}" y1="{y - 4:.1f}" x2="{rule_end:.1f}" y2="{y - 4:.1f}" '
                f'stroke="{t["rule"]}" stroke-width="1"/>'
            )
            y += CHAR_H
        for key, value in mod.get("rows", []):
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["key"]}" '
                f'font-weight="700">{esc(key)}</text>'
            )
            dots = max(2, int((key_w - len(key) * CHAR_W - 18) / CHAR_W))
            out.append(
                f'<text x="{text_x + len(key) * CHAR_W + 10:.1f}" y="{y:.1f}" '
                f'fill="{t["dim"]}">{"." * dots}</text>'
            )
            out.append(
                f'<text x="{text_x + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                f'{esc(value)}</text>'
            )
            y += CHAR_H


def render_panel(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x):
    """Faixa de cabecalho + logo a esquerda + modulos em duas colunas."""
    head_h = 78.0
    out.append(
        f'<rect x="0.5" y="0.5" width="{w-1:.0f}" height="{h-1:.0f}" rx="14" '
        f'fill="none" stroke="{t["frame"]}" stroke-width="1"/>'
    )
    out.append(
        f'<path d="M 0 14 A 14 14 0 0 1 14 0 L {w-14:.0f} 0 A 14 14 0 0 1 {w:.0f} 14 '
        f'L {w:.0f} {head_h:.0f} L 0 {head_h:.0f} Z" fill="{t["header_bg"]}"/>'
    )
    out.append(
        f'<line x1="0" y1="{head_h:.0f}" x2="{w:.0f}" y2="{head_h:.0f}" '
        f'stroke="{t["frame"]}" stroke-width="1"/>'
    )

    handle = data.get("handle", "")
    out.append(
        f'<text x="{PAD:.1f}" y="{head_h / 2 + 8:.1f}" fill="{t["handle"]}" font-size="24px" '
        f'font-weight="700">{esc(handle)}</text>'
    )
    if data.get("subtitle"):
        hx = PAD + (len(handle) + 2) * 13.0
        out.append(
            f'<text x="{hx:.1f}" y="{head_h / 2 + 7:.1f}" fill="{t["subtitle"]}" '
            f'font-size="14px">{esc(data["subtitle"])}</text>'
        )

    if logo:
        out.append(ascii_block(logo, PAD, head_h + PAD + CHAR_H - 4, t["cyan"]))

    mods = data.get("modules", [])
    half = (len(mods) + 1) // 2
    cols = [mods[:half], mods[half:]]
    col_w = key_w + val_w
    body_x = PAD + logo_w + LOGO_GAP

    for ci, group in enumerate(cols):
        cx = body_x + ci * (col_w + 44)
        y = head_h + PAD + CHAR_H
        for i, mod in enumerate(group):
            if i:
                y += 16
            if mod.get("title"):
                out.append(
                    f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="12px" '
                    f'font-weight="700" letter-spacing="1.4">{esc(mod["title"].upper())}</text>'
                )
                out.append(
                    f'<line x1="{cx:.1f}" y1="{y + 6:.1f}" x2="{cx + col_w:.1f}" y2="{y + 6:.1f}" '
                    f'stroke="{t["rule"]}" stroke-width="1"/>'
                )
                y += CHAR_H + 4
            for key, value in mod.get("rows", []):
                out.append(
                    f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["key"]}" font-weight="700">'
                    f'{esc(key)}</text>'
                )
                out.append(
                    f'<text x="{cx + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                    f'{esc(value)}</text>'
                )
                y += CHAR_H


def render_hybrid(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x):
    """A + B: moldura do fastfetch por fora, leaders de pontos e reguas por dentro."""
    out.append(
        f'<rect x="0.5" y="0.5" width="{w-1:.0f}" height="{h-1:.0f}" rx="14" '
        f'fill="none" stroke="{t["frame"]}" stroke-width="1"/>'
    )
    if logo:
        logo_top = PAD + max(0, (right_h - logo_h) / 2)
        out.append(ascii_block(logo, PAD, logo_top + CHAR_H - 4, t["cyan"]))

    y = PAD + CHAR_H
    out.append(
        f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["handle"]}" font-size="22px" '
        f'font-weight="700">{esc(data.get("handle", ""))}</text>'
    )
    if data.get("subtitle"):
        out.append(
            f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["subtitle"]}" '
            f'font-size="14px">{esc(data["subtitle"])}</text>'
        )

    y = PAD + TITLE_LINES * CHAR_H + 14
    for i, mod in enumerate(data.get("modules", [])):
        if i:
            y += 16
        if mod.get("title"):
            title = mod["title"]
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                f'font-weight="700">{esc(title)}</text>'
            )
            rule_x = text_x + (len(title) + 2) * CHAR_W
            rule_end = text_x + key_w + val_w
            out.append(
                f'<line x1="{rule_x:.1f}" y1="{y - 4:.1f}" x2="{rule_end:.1f}" y2="{y - 4:.1f}" '
                f'stroke="{t["rule"]}" stroke-width="1"/>'
            )
            y += CHAR_H
        for key, value in mod.get("rows", []):
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["key"]}" '
                f'font-weight="700">{esc(key)}</text>'
            )
            dots = max(2, int((key_w - len(key) * CHAR_W - 18) / CHAR_W))
            out.append(
                f'<text x="{text_x + len(key) * CHAR_W + 10:.1f}" y="{y:.1f}" '
                f'fill="{t["dim"]}">{"." * dots}</text>'
            )
            out.append(
                f'<text x="{text_x + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                f'{esc(value)}</text>'
            )
            y += CHAR_H


def render_accent(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x):
    """A + B, versao leve: sem moldura, mas com barra de acento e reguas."""
    if logo:
        out.append(ascii_block(logo, PAD, PAD + CHAR_H - 4, t["cyan"]))

    y = PAD + CHAR_H
    out.append(
        f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["handle"]}" font-size="22px" '
        f'font-weight="700">{esc(data.get("handle", ""))}</text>'
    )
    if data.get("subtitle"):
        out.append(
            f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["subtitle"]}" '
            f'font-size="14px">{esc(data["subtitle"])}</text>'
        )
    out.append(
        f'<line x1="{text_x:.1f}" y1="{y + CHAR_H + 12:.1f}" '
        f'x2="{text_x + key_w + val_w:.1f}" y2="{y + CHAR_H + 12:.1f}" '
        f'stroke="{t["rule"]}" stroke-width="1"/>'
    )

    y = PAD + TITLE_LINES * CHAR_H + 22
    for i, mod in enumerate(data.get("modules", [])):
        if i:
            y += 16
        if mod.get("title"):
            title = mod["title"]
            out.append(
                f'<rect x="{text_x:.1f}" y="{y - 11:.1f}" width="3" height="14" '
                f'fill="{t["handle"]}"/>'
            )
            out.append(
                f'<text x="{text_x + 10:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                f'font-weight="700">{esc(title)}</text>'
            )
            rule_x = text_x + 10 + (len(title) + 2) * CHAR_W
            rule_end = text_x + key_w + val_w
            out.append(
                f'<line x1="{rule_x:.1f}" y1="{y - 4:.1f}" x2="{rule_end:.1f}" y2="{y - 4:.1f}" '
                f'stroke="{t["rule"]}" stroke-width="1"/>'
            )
            y += CHAR_H
        for key, value in mod.get("rows", []):
            out.append(
                f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["key"]}" '
                f'font-weight="700">{esc(key)}</text>'
            )
            dots = max(2, int((key_w - len(key) * CHAR_W - 18) / CHAR_W))
            out.append(
                f'<text x="{text_x + len(key) * CHAR_W + 10:.1f}" y="{y:.1f}" '
                f'fill="{t["dim"]}">{"." * dots}</text>'
            )
            out.append(
                f'<text x="{text_x + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                f'{esc(value)}</text>'
            )
            y += CHAR_H


def render(data, style, theme_name):
    t = THEMES[theme_name]
    logo = data.get("logo_lines", [])
    w, h, logo_w, logo_h, key_w, val_w, right_h = measure(data, style)

    out = [svg_header(w, h, theme_name)]
    out.append(f'<rect width="{w:.0f}" height="{h:.0f}" fill="{t["bg"]}" rx="14"/>')

    text_x = PAD + logo_w + LOGO_GAP
    if style == "dots":
        render_dots(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x)
    elif style == "panel":
        render_panel(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x)
    elif style == "hybrid":
        render_hybrid(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x)
    elif style == "accent":
        render_accent(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x)
    else:
        render_box(t, data, out, w, h, logo, logo_w, logo_h, key_w, val_w, right_h, text_x)

    out.append("</svg>")
    return "\n".join(out)


def load_data(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    logo_path = data.get("logo")
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        width = max(len(l) for l in lines) if lines else 0
        data["logo_lines"] = [l.ljust(width) for l in lines]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--style", default="box", choices=["box", "dots", "panel", "hybrid", "accent"])
    ap.add_argument("--theme", default="both", choices=["dark", "light", "both"])
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--name", default="")
    args = ap.parse_args()

    data = load_data(args.data)
    themes = ["dark", "light"] if args.theme == "both" else [args.theme]
    for theme in themes:
        svg = render(data, args.style, theme)
        name = args.name or ("dark_mode" if theme == "dark" else "light_mode")
        out = os.path.join(args.outdir, f"{name}.svg")
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"-> {out}  ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
