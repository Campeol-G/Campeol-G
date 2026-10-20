#!/usr/bin/env python3
"""
Renderiza o README de perfil do GitHub (SVG) a partir de um data.json.

Estilos (--style):
  cli     -> prompt de shell, secoes com barra, barra de status no rodape
  box     -> moldura fechada, colunas key/value (estilo fastfetch classico)
  dots    -> sem moldura, leaders de pontos e reguas de secao
  accent  -> sem moldura, barrinha de acento nas secoes
  panel   -> faixa de cabecalho + modulos em duas colunas

Temas: --theme dark|light|both

Uso:
    python3 tools/render.py --data data.json --style cli --theme both --outdir .
"""

import argparse
import calendar
import datetime
import json
import os
import re
import xml.sax.saxutils as sax

# ---------------------------------------------------------------- metricas
FONT_SIZE = 16.0
CHAR_W = 9.6          # largura de um caractere na fonte monoespacada de 16px
CHAR_H = 18.0         # altura de uma linha
PAD = 26.0            # padding interno
LOGO_GAP = 30.0       # espaco entre logo e coluna de texto
TITLE_LINES = 3.0     # altura do cabecalho em linhas

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
        "green_strong": "#56d364",
        "green_mid": "#2ea043",
        "green_dim": "#1a7f37",
        "yellow": "#d29922",
        "magenta": "#bc8cff",
        "red": "#f85149",
        "cyan": "#39c5cf",
        "logo": "#39c5cf",
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
        "green_strong": "#0f5322",
        "green_mid": "#2ea043",
        "green_dim": "#a7d3b0",
        "yellow": "#9a6700",
        "magenta": "#8250df",
        "red": "#cf222e",
        "cyan": "#0a7d8a",
        "logo": "#1f2328",
    },
}


def esc(text):
    return sax.escape(str(text))


def font_family():
    return "'Mono','DejaVu Sans Mono','Menlo','Liberation Mono',monospace"


def svg_header(width, height, extra_css=""):
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


def ascii_block(lines, x, y, color, char_w=CHAR_W, char_h=CHAR_H, scale=1.0):
    """Cada linha recebe textLength fixo -> a grade nunca quebra, independente
    da fonte que o navegador resolver usar."""
    out = [f'<g>']
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


# ---------------------------------------------------------------- conteudo
def age_string(birthday, today=None):
    """'17 years, 4 months, 4 days' no formato do uptime do fastfetch."""
    if not birthday:
        return ""
    try:
        born = datetime.date.fromisoformat(birthday)
    except ValueError:
        return ""
    today = today or datetime.date.today()

    # Meses completos entre a data de nascimento e hoje.
    months_total = (today.year - born.year) * 12 + (today.month - born.month)
    if today.day < born.day:
        months_total -= 1
    if months_total < 0:
        return "0 years, 0 months, 0 days"

    # Ultimo aniversario mensal (com o dia limitado ao tamanho do mes).
    ay = born.year + months_total // 12
    am = born.month + months_total % 12
    if am > 12:
        am -= 12
        ay += 1
    last = datetime.date(ay, am, min(born.day, calendar.monthrange(ay, am)[1]))
    days = (today - last).days

    years = months_total // 12
    months = months_total % 12
    cake = " 🎂" if (today.month, today.day) == (born.month, born.day) else ""
    return (
        f"{years} year{'' if years == 1 else 's'}, "
        f"{months} month{'' if months == 1 else 's'}, "
        f"{days} day{'' if days == 1 else 's'}{cake}"
    )


def stats_rows(data):
    """Linhas do modulo de stats, montadas a partir dos dados automaticos."""
    activity = data.get("activity") or {}
    rows = []

    def num(v):
        return f"{v:,}"

    if "streak" in activity:
        rows.append(["Streak", f"{activity['streak']} days"])
    if "longest_streak" in activity:
        rows.append(["Longest", f"{activity['longest_streak']} days"])
    if "commits" in activity:
        rows.append(["Commits (1y)", num(activity["commits"])])
    if "lines_added" in activity:
        added = num(activity["lines_added"])
        deleted = num(activity.get("lines_deleted", 0))
        total = num(activity["lines_added"] - activity.get("lines_deleted", 0))
        rows.append(["Lines of Code", f"{total} ( +{added}, -{deleted} )"])
    if "repos" in activity:
        rows.append(["Repos", num(activity["repos"])])
    if "open_prs" in activity or "open_issues" in activity:
        rows.append([
            "Open PRs/Issues",
            f"{activity.get('open_prs', 0)} / {activity.get('open_issues', 0)}",
        ])
    return rows


def text_width(s, size):
    """Largura estimada de um texto monoespacado (0.6em de avanco)."""
    return len(str(s)) * size * 0.6


def module_rows(data, mod):
    """Linhas de um modulo: fixas ou geradas automaticamente."""
    if mod.get("auto") == "stats":
        return stats_rows(data)
    if mod.get("auto") == "uptime":
        value = age_string(data.get("birthday", ""))
        return [["Uptime", value]] if value else []
    rows = []
    for key, value in mod.get("rows", []):
        # "uptime" com valor vazio e' preenchido com a idade real.
        if key == "uptime" and not value:
            value = age_string(data.get("birthday", ""))
        rows.append((key, value))
    return rows


def prompt_height(data):
    """Altura do cabecalho (prompt): 1 ou 2 linhas + regua."""
    return CHAR_H + (CHAR_H if data.get("subtitle") else 0) + 6


def content_top(data):
    """Y onde comeca o conteudo (mesma fonte de verdade do render)."""
    return PAD + CHAR_H + prompt_height(data) + 12


STATUS_H = 40   # altura reservada para a barra de status


def header_width(data):
    """Largura necessaria do cabecalho em pixels."""
    handle = data.get("handle", "")
    host = data.get("host", "")
    prompt_w = 16 + text_width(handle, 20) + text_width(f"@{host}", 18)
    sub_w = text_width(data.get("subtitle", ""), 15) + 18
    return max(prompt_w, sub_w)


def measure(data, style):
    """Geometria do layout."""
    logo = data.get("logo_lines", [])
    logo_scale = 13.0 / CHAR_H if style == "panel" else 1.0
    logo_w = max((len(l) for l in logo), default=0) * CHAR_W
    logo_h = len(logo) * CHAR_H * logo_scale

    key_w = val_w = 0
    for mod in data.get("modules", []):
        for k, v in module_rows(data, mod):
            key_w = max(key_w, len(k))
            val_w = max(val_w, len(v))
    key_w = key_w * CHAR_W + 18
    val_w = val_w * CHAR_W

    mods = data.get("modules", [])

    def block_height(group):
        h = 0
        for i, mod in enumerate(group):
            if i:
                h += 16
            if mod.get("title"):
                h += CHAR_H + 4
            h += len(module_rows(data, mod)) * CHAR_H
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
    text_x = PAD + logo_w + LOGO_GAP
    w = text_x + max(content_w, header_width(data)) + PAD
    if style == "cli":
        top = content_top(data)
        h = top + block_height(mods) + 16 + STATUS_H + PAD
    else:
        h = PAD + max(logo_h, right_h) + PAD
    return w, h, logo_w, logo_h, key_w, val_w, right_h


# ------------------------------------------------------------- renderizacao
def render_prompt(t, data, out, x, y, w):
    """Cabecalho no estilo prompt de shell: '❯ nome@host' + subtitulo."""
    handle = data.get("handle", "")
    host = data.get("host", "")
    out.append(
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{t["green"]}" font-size="18px" '
        f'font-weight="700">❯</text>'
    )
    out.append(
        f'<text x="{x + 16:.1f}" y="{y:.1f}" fill="{t["handle"]}" font-size="20px" '
        f'font-weight="700">{esc(handle)}</text>'
    )
    px = x + 20 + text_width(handle, 20)
    if host:
        out.append(
            f'<text x="{px:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="18px">'
            f'@{esc(host)}</text>'
        )
    if data.get("subtitle"):
        out.append(
            f'<text x="{x + 18:.1f}" y="{y + CHAR_H:.1f}" fill="{t["subtitle"]}" '
            f'font-size="15px">{esc(data["subtitle"])}</text>'
        )
    y += CHAR_H + (CHAR_H if data.get("subtitle") else 0)
    out.append(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + w:.1f}" y2="{y:.1f}" '
        f'stroke="{t["rule"]}" stroke-width="1"/>'
    )
    return y + 6


def split_highlight(value, terms):
    """Quebra o valor em (trecho, destacado) — 'Java, Python' com 'Java'."""
    if not terms:
        return [(value, False)]
    pattern = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True) if t)
    if not pattern:
        return [(value, False)]
    parts = []
    for chunk in re.split(f"({pattern})", str(value)):
        if not chunk:
            continue
        parts.append((chunk, chunk in terms))
    return parts or [(value, False)]


def render_sections(t, data, out, x, y, key_w, val_w, bar=True):
    """Modulos no formato CLI: titulo com barra, linhas chave -> valor."""
    terms = set()
    for mod in data.get("modules", []):
        for h in mod.get("highlight", []):
            terms.add(h)

    for i, mod in enumerate(data.get("modules", [])):
        if i:
            y += 16
        if mod.get("title"):
            if bar:
                out.append(
                    f'<rect x="{x:.1f}" y="{y - 11:.1f}" width="3" height="14" '
                    f'fill="{t["handle"]}"/>'
                )
            out.append(
                f'<text x="{x + 10:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                f'font-weight="700" letter-spacing="0.8">{esc(mod["title"])}</text>'
            )
            y += CHAR_H + 4
        for key, value in module_rows(data, mod):
            out.append(
                f'<text x="{x:.1f}" y="{y:.1f}" fill="{t["key"]}" font-weight="700">'
                f'{esc(key)}</text>'
            )
            dots = max(2, int((key_w - len(key) * CHAR_W - 18) / CHAR_W))
            out.append(
                f'<text x="{x + len(key) * CHAR_W + 10:.1f}" y="{y:.1f}" '
                f'fill="{t["dim"]}">{"." * dots}</text>'
            )
            # Valor: trechos em destaque sao pintados de verde.
            cx = x + key_w
            for chunk, hot in split_highlight(value, terms):
                if hot:
                    out.append(
                        f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["green"]}" '
                        f'font-weight="700">{esc(chunk)}</text>'
                    )
                else:
                    out.append(
                        f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                        f'{esc(chunk)}</text>'
                    )
                cx += text_width(chunk, FONT_SIZE)
            y += CHAR_H
    return y


def render_statusbar(t, data, out, x, y, w):
    """Barra de status no estilo tmux: ─[ java ██░░ 86% ]─[ up 17y ]─[ 12d ]─"""
    activity = data.get("activity") or {}
    # cada segmento e' uma lista de (texto, cor)
    segs = []

    langs = activity.get("languages") or {}
    if langs:
        top = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
        name, share = top[0]
        pct = int(round(share * 100))
        cells = 10
        filled = max(1, round(pct / 100 * cells))
        segs.append([
            (f"{name.lower()} ", t["subtitle"]),
            ("█" * filled, t["green"]),
            ("░" * (cells - filled), t["dim"]),
            (f" {pct}%", t["subtitle"]),
        ])

    up = age_string(data.get("birthday", ""))
    if up:
        segs.append([(f"up {up.split(' years')[0]}y", t["subtitle"])])
    if "streak" in activity:
        segs.append([(f"streak {activity['streak']}d", t["subtitle"])])
    if "repos" in activity:
        segs.append([(f"repos {activity['repos']}", t["subtitle"])])

    if not segs:
        return y

    out.append(
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + w:.1f}" y2="{y:.1f}" '
        f'stroke="{t["rule"]}" stroke-width="1"/>'
    )
    y += 22
    cx = x
    for pieces in segs:
        out.append(f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px">─</text>')
        cx += 9
        out.append(f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px">[</text>')
        cx += 8
        for text, color in pieces:
            out.append(
                f'<text x="{cx:.1f}" y="{y:.1f}" fill="{color}" font-size="13px">'
                f'{esc(text)}</text>'
            )
            cx += text_width(text, 13)
        out.append(f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px">]</text>')
        cx += 16
    # cursor piscando no fim da linha
    out.append(f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px">─</text>')
    out.append(
        f'<text x="{cx + 9:.1f}" y="{y:.1f}" fill="{t["green"]}" font-size="13px">█</text>'
    )
    return y + 14


def render(data, style, theme_name):
    t = THEMES[theme_name]
    logo = data.get("logo_lines", [])
    w, h, logo_w, logo_h, key_w, val_w, right_h = measure(data, style)

    out = [svg_header(w, h)]
    out.append(f'<rect width="{w:.0f}" height="{h:.0f}" fill="{t["bg"]}" rx="14"/>')

    if style in ("cli", "box", "panel"):
        out.append(
            f'<rect x="0.5" y="0.5" width="{w-1:.0f}" height="{h-1:.0f}" rx="14" '
            f'fill="none" stroke="{t["frame"]}" stroke-width="1"/>'
        )

    text_x = PAD + logo_w + LOGO_GAP

    if style == "cli":
        top = content_top(data)
        body_h = h - top - 16 - STATUS_H - PAD
        if logo:
            logo_top = top + max(0, (body_h - logo_h) / 2)
            out.append(ascii_block(logo, PAD, logo_top + CHAR_H - 4, t["logo"]))
        y = render_prompt(t, data, out, text_x, PAD + CHAR_H, key_w + val_w)
        y = render_sections(t, data, out, text_x, y + 12, key_w, val_w, bar=True)
        render_statusbar(t, data, out, PAD, y + 16, w - PAD * 2)
    elif style == "box":
        if logo:
            logo_top = PAD + max(0, (right_h - logo_h) / 2)
            out.append(ascii_block(logo, PAD, logo_top + CHAR_H - 4, t["logo"]))
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
        y = render_sections(t, data, out, text_x, PAD + TITLE_LINES * CHAR_H + 14,
                            key_w, val_w, bar=False)
    elif style == "accent":
        if logo:
            out.append(ascii_block(logo, PAD, PAD + CHAR_H - 4, t["logo"]))
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
        render_sections(t, data, out, text_x, PAD + TITLE_LINES * CHAR_H + 22,
                        key_w, val_w, bar=True)
    elif style == "dots":
        if logo:
            out.append(ascii_block(logo, PAD, PAD + CHAR_H - 4, t["logo"]))
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
                    f'<line x1="{rule_x:.1f}" y1="{y - 4:.1f}" x2="{rule_end:.1f}" '
                    f'y2="{y - 4:.1f}" stroke="{t["rule"]}" stroke-width="1"/>'
                )
                y += CHAR_H
            for key, value in module_rows(data, mod):
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
    elif style == "panel":
        head_h = 78.0
        out.append(
            f'<path d="M 0 14 A 14 14 0 0 1 14 0 L {w-14:.0f} 0 A 14 14 0 0 1 {w:.0f} 14 '
            f'L {w:.0f} {head_h:.0f} L 0 {head_h:.0f} Z" fill="{t["header_bg"]}"/>'
        )
        out.append(
            f'<line x1="0" y1="{head_h:.0f}" x2="{w:.0f}" y2="{head_h:.0f}" '
            f'stroke="{t["frame"]}" stroke-width="1"/>'
        )
        if logo:
            out.append(ascii_block(logo, PAD, head_h + PAD + CHAR_H - 4, t["logo"]))
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
                        f'font-weight="700" letter-spacing="1.4">'
                        f'{esc(mod["title"].upper())}</text>'
                    )
                    y += CHAR_H + 4
                for key, value in module_rows(data, mod):
                    out.append(
                        f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["key"]}" font-weight="700">'
                        f'{esc(key)}</text>'
                    )
                    out.append(
                        f'<text x="{cx + key_w:.1f}" y="{y:.1f}" fill="{t["value"]}">'
                        f'{esc(value)}</text>'
                    )
                    y += CHAR_H

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
        width = max((len(l) for l in lines), default=0)
        data["logo_lines"] = [l.ljust(width) for l in lines]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--style", default="cli",
                    choices=["cli", "box", "dots", "panel", "accent"])
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
