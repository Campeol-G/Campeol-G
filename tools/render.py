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

# Duas paletas de verdade, com as cores exatas de um terminal.
PALETTES = {
    # ---- modo escuro
    "forest": {
        "label": "Forest (escuro)",
        "bg": "#2D3533",        # Forest Night
        "frame": "#46564A",     # Sage Forest
        "rule": "#343F3A",      # Moss Shadow
        "key": "#A3B8B0",       # Eucalyptus
        "value": "#D8C7A5",     # Oat Milk
        "dim": "#A7B69B",       # Soft Sage
        "title": "#D6A85E",     # Honey Glow
        "logo": "#D6A85E",      # Honey Glow
        "accent": "#D6A85E",    # Honey Glow
        "text": "#D8C7A5",      # Oat Milk
        "surface": "#343F3A",   # Moss Shadow
        "neutral": "#B8A08A",   # Mushroom
        "strip": ["#D6A85E", "#A3B8B0", "#D8C7A5", "#A7B69B", "#46564A", "#B8A08A"],
    },
    # ---- modo claro
    "linen": {
        "label": "Linen (claro)",
        "bg": "#F2EFE5",        # Background
        "frame": "#D0D5C9",     # Border
        "rule": "#D0D5C9",      # Border
        "key": "#506653",       # Primary
        "value": "#3D5143",     # Text
        "dim": "#7D8778",       # Text Secondary
        "title": "#3D5143",     # Primary Dark
        "logo": "#506653",      # Primary
        "accent": "#86A79B",    # Accent
        "text": "#3D5143",      # Text
        "surface": "#E8E4D8",   # Surface
        "neutral": "#A18F7B",   # Muted
        "strip": ["#506653", "#86A79B", "#3D5143", "#7D8778", "#D8DFD0", "#A18F7B"],
    },
}


def theme_from(palette_name):
    """Monta o dicionario de cores de uma paleta, ja com as cores derivadas."""
    p = dict(PALETTES[palette_name])
    p["rule"] = p["frame"]
    p["band"] = p["frame"]
    p["cursor"] = p["title"]
    p["highlight"] = p["title"]
    p.setdefault("logo", p["title"])
    return p


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

/* Cursor piscando, como um terminal esperando comando.
   CSS dentro de um SVG referenciado como imagem roda no GitHub (mesmo
   mecanismo dos badges animados). O prefers-reduced-motion desliga
   pra quem pediu. */
.cursor {{ animation: blink 1.15s steps(1, end) infinite; }}
@keyframes blink {{
  0%, 49% {{ opacity: 1; }}
  50%, 100% {{ opacity: 0; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .cursor {{ animation: none; opacity: 1; }}
}}
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
        # "uptime" e "working in" com valor vazio sao preenchidos automaticamente.
        if key == "uptime" and not value:
            value = age_string(data.get("birthday", ""))
        if key.lower() == "working in" and not value:
            value = (data.get("activity") or {}).get("working_on", "")
        rows.append((key, value))
    return rows


def prompt_height(data):
    """Altura do cabecalho (prompt): uma linha."""
    return CHAR_H


def content_top(data):
    """Y onde comeca o conteudo (mesma fonte de verdade do render)."""
    return PAD + prompt_height(data) + 18


STATUS_H = 40   # altura reservada para a barra de status


def header_width(data):
    """Largura necessaria do cabecalho (tudo numa linha so)."""
    handle = data.get("handle", "")
    host = data.get("host", "")
    subtitle = data.get("subtitle", "")
    w = 16 + text_width(handle, 20)
    if host:
        w += text_width(" · ", 17) + text_width(f"@{host}", 17)
    if subtitle:
        w += text_width("  ·  ", 17) + text_width(subtitle, 17)
    return w


def project_lines(data, mod):
    """Linhas do bloco de projetos: nome + descricao, vindos do activity."""
    projects = (data.get("activity") or {}).get("projects") or []
    lines = []
    for p in projects:
        name = p.get("name", "")
        desc = p.get("description", "")
        if not name:
            continue
        lines.append((name, desc))
    return lines


def project_width(name, desc):
    """Largura real de uma linha de projeto (nome em 16px, resto em 14px)."""
    return (
        len(name) * CHAR_W
        + 8
        + 3 * CHAR_W * (14.0 / FONT_SIZE)
        + len(desc) * CHAR_W * (14.0 / FONT_SIZE)
    )


def measure(data, style):
    """Geometria do layout."""
    logo = data.get("logo_lines", [])
    logo_scale = 13.0 / CHAR_H if style == "panel" else 1.0
    logo_w = max((len(l) for l in logo), default=0) * CHAR_W
    logo_h = len(logo) * CHAR_H * logo_scale

    key_w = val_w = 0
    proj_w = 0
    for mod in data.get("modules", []):
        if mod.get("type") == "projects":
            for name, desc in project_lines(data, mod):
                proj_w = max(proj_w, project_width(name, desc))
            continue
        for k, v in module_rows(data, mod):
            key_w = max(key_w, len(k))
            val_w = max(val_w, len(v))
    # +34 px deixa espaco para pelo menos tres pontinhos de leader
    key_w = key_w * CHAR_W + 34
    val_w = val_w * CHAR_W
    proj_w = proj_w + 8

    mods = data.get("modules", [])

    def block_height(group):
        h = 0
        for i, mod in enumerate(group):
            if i:
                h += 16
            if mod.get("title"):
                h += CHAR_H + 4
            if mod.get("type") == "projects":
                h += len(project_lines(data, mod)) * CHAR_H
            else:
                h += len(module_rows(data, mod)) * CHAR_H
        return h

    if style == "panel":
        head_h = 74.0
        half = (len(mods) + 1) // 2
        cols = [mods[:half], mods[half:]]
        content_h = max(block_height(c) for c in cols) if cols else 0
        col_w = key_w + val_w
        w = PAD * 2 + logo_w + LOGO_GAP + col_w * 2 + 44
        w = max(w, PAD * 2 + header_width(data) + logo_w * 0.62 + LOGO_GAP)
        h = head_h + PAD + max(content_h + CHAR_H, logo_h) + PAD + STATUS_H
        return w, h, logo_w, logo_h, key_w, val_w, content_h

    right_h = TITLE_LINES * CHAR_H + 14 + block_height(mods)
    content_w = max(key_w + val_w, proj_w)
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
    """Titulo e subtitulo na mesma linha, no estilo prompt de shell."""
    handle = data.get("handle", "")
    host = data.get("host", "")
    out.append(
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{t["accent"]}" font-size="18px" '
        f'font-weight="700">❯</text>'
    )
    out.append(
        f'<text x="{x + 16:.1f}" y="{y:.1f}" fill="{t["title"]}" font-size="20px" '
        f'font-weight="700">{esc(handle)}</text>'
    )
    cx = x + 20 + text_width(handle, 20)
    if host:
        out.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="17px">·</text>'
        )
        cx += text_width("·", 17) + 6
        out.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="17px">'
            f'@{esc(host)}</text>'
        )
        cx += text_width(f"@{host}", 17)
    if data.get("subtitle"):
        out.append(
            f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="17px">'
            f'  ·  {esc(data["subtitle"])}</text>'
        )
    return y


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
                    f'fill="{t["title"]}"/>'
                )
            out.append(
                f'<text x="{x + 10:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                f'font-weight="700" letter-spacing="0.8">{esc(mod["title"])}</text>'
            )
            y += CHAR_H + 4
        if mod.get("type") == "projects":
            y = render_projects(t, data, out, x, y)
            continue
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
                        f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["highlight"]}" '
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


def render_projects(t, data, out, x, y):
    """Bloco de projetos: nome em destaque + descricao, na mesma linha."""
    for name, desc in project_lines(data, {}):
        out.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{t["key"]}" font-weight="700">'
            f'{esc(name)}</text>'
        )
        cx = x + text_width(name, FONT_SIZE) + 8
        if desc:
            out.append(
                f'<text x="{cx:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="14px">'
                f'— {esc(desc)}</text>'
            )
        y += CHAR_H
    return y


def render_strip(t, out, right_x, y, size=15.0, gap=3.0):
    """Quadradinhos com as cores da paleta, no canto inferior direito
    (como a faixa de cores do fastfetch)."""
    colors = t.get("strip", [])
    total = len(colors) * size + (len(colors) - 1) * gap
    x = right_x - total
    out.append(f'<g>')
    for i, c in enumerate(colors):
        out.append(
            f'<rect x="{x + i * (size + gap):.1f}" y="{y:.1f}" width="{size:.1f}" '
            f'height="{size:.1f}" fill="{c}"/>'
        )
    out.append("</g>")
    return total


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
            (f"{name.lower()} ", t["dim"]),
            ("█" * filled, t["key"]),
            ("░" * (cells - filled), t["dim"]),
            (f" {pct}%", t["dim"]),
        ])

    up = age_string(data.get("birthday", ""))
    if up:
        segs.append([(f"up {up.split(' years')[0]}y", t["dim"])])
    if "streak" in activity:
        segs.append([(f"streak {activity['streak']}d", t["dim"])])
    if "repos" in activity:
        segs.append([(f"repos {activity['repos']}", t["dim"])])

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
    # cursor piscando no fim da linha (parece terminal esperando comando)
    out.append(
        f'<text class="cursor" x="{cx + 9:.1f}" y="{y:.1f}" fill="{t["cursor"]}" '
        f'font-size="13px">█</text>'
    )
    return y + 14


def render(data, style, palette_name):
    t = theme_from(palette_name)
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
        y = render_sections(t, data, out, text_x, content_top(data), key_w, val_w, bar=True)
        bar_y = y + 16
        render_statusbar(t, data, out, PAD, bar_y, w - PAD * 2 - 190)
        render_strip(t, out, w - PAD, bar_y + 6)
    elif style == "box":
        if logo:
            logo_top = PAD + max(0, (right_h - logo_h) / 2)
            out.append(ascii_block(logo, PAD, logo_top + CHAR_H - 4, t["logo"]))
        y = PAD + CHAR_H
        out.append(
            f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["title"]}" font-size="22px" '
            f'font-weight="700">{esc(data.get("handle", ""))}</text>'
        )
        if data.get("subtitle"):
            out.append(
                f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["dim"]}" '
                f'font-size="14px">{esc(data["subtitle"])}</text>'
            )
        y = render_sections(t, data, out, text_x, PAD + TITLE_LINES * CHAR_H + 14,
                            key_w, val_w, bar=False)
    elif style == "accent":
        if logo:
            out.append(ascii_block(logo, PAD, PAD + CHAR_H - 4, t["logo"]))
        y = PAD + CHAR_H
        out.append(
            f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["title"]}" font-size="22px" '
            f'font-weight="700">{esc(data.get("handle", ""))}</text>'
        )
        if data.get("subtitle"):
            out.append(
                f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["dim"]}" '
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
            f'<text x="{text_x:.1f}" y="{y:.1f}" fill="{t["title"]}" font-size="22px" '
            f'font-weight="700">{esc(data.get("handle", ""))}</text>'
        )
        if data.get("subtitle"):
            out.append(
                f'<text x="{text_x:.1f}" y="{y + CHAR_H:.1f}" fill="{t["dim"]}" '
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
        head_h = 74.0
        out.append(
            f'<path d="M 0 14 A 14 14 0 0 1 14 0 L {w-14:.0f} 0 A 14 14 0 0 1 {w:.0f} 14 '
            f'L {w:.0f} {head_h:.0f} L 0 {head_h:.0f} Z" fill="{t["band"]}"/>'
        )
        out.append(
            f'<line x1="0" y1="{head_h:.0f}" x2="{w:.0f}" y2="{head_h:.0f}" '
            f'stroke="{t["frame"]}" stroke-width="1"/>'
        )
        # cabecalho na faixa
        hx = PAD + logo_w * 0.62 + LOGO_GAP
        out.append(
            f'<text x="{hx:.1f}" y="{head_h / 2 + 6:.1f}" fill="{t["title"]}" font-size="18px" '
            f'font-weight="700">❯</text>'
        )
        out.append(
            f'<text x="{hx + 16:.1f}" y="{head_h / 2 + 6:.1f}" fill="{t["title"]}" '
            f'font-size="20px" font-weight="700">{esc(data.get("handle", ""))}</text>'
        )
        cx = hx + 20 + text_width(data.get("handle", ""), 20)
        if data.get("host"):
            out.append(
                f'<text x="{cx:.1f}" y="{head_h / 2 + 6:.1f}" fill="{t["dim"]}" font-size="17px">'
                f'@{esc(data["host"])}</text>'
            )
            cx += text_width(f"@{data['host']}", 17)
        if data.get("subtitle"):
            out.append(
                f'<text x="{cx:.1f}" y="{head_h / 2 + 6:.1f}" fill="{t["dim"]}" font-size="17px">'
                f'  ·  {esc(data["subtitle"])}</text>'
            )

        if logo:
            out.append(ascii_block(logo, PAD, head_h + PAD + CHAR_H - 4, t["logo"],
                                   char_h=13.0, scale=0.78))

        # modulos em duas colunas, divididas por altura
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
                        f'<rect x="{cx:.1f}" y="{y - 11:.1f}" width="3" height="14" '
                        f'fill="{t["title"]}"/>'
                    )
                    out.append(
                        f'<text x="{cx + 10:.1f}" y="{y:.1f}" fill="{t["dim"]}" font-size="13px" '
                        f'font-weight="700" letter-spacing="0.8">{esc(mod["title"])}</text>'
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
        bar_y = h - PAD - 12
        render_statusbar(t, data, out, PAD, bar_y, w - PAD * 2 - 190)
        render_strip(t, out, w - PAD, bar_y + 6)

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
    ap.add_argument("--theme", default="both", choices=list(PALETTES) + ["both"],
                    help="paleta a renderizar (ou 'both')")
    ap.add_argument("--assign", default="light", choices=["light", "dark"],
                    help="qual paleta vai para o SVG de tema claro")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--name", default="")
    args = ap.parse_args()

    data = load_data(args.data)
    palettes = list(PALETTES) if args.theme == "both" else [args.theme]

    # '--assign' diz qual paleta ocupa o SVG de tema claro.
    # Padrao: Gruvbox no claro, Everforest no escuro.
    pairs = {"light": ("linen", "forest"), "dark": ("forest", "linen")}
    light_palette, dark_palette = pairs[args.assign]

    for palette in palettes:
        svg = render(data, args.style, palette)
        if len(palettes) == 1 and args.name:
            name = args.name
        else:
            name = "light_mode" if palette == light_palette else "dark_mode"
        out = os.path.join(args.outdir, f"{name}.svg")
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"-> {out}  ({len(svg)} bytes, {PALETTES[palette]['label']})")


if __name__ == "__main__":
    main()
