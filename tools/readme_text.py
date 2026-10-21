#!/usr/bin/env python3
"""
Gera o README.md em markdown de verdade.

Por que texto e nao SVG: o GitHub renderiza o README do perfil numa coluna
de ~700px. Uma imagem de 1537px e' encolhida pra 46%, e uma fonte de 16px
vira 7,3px — ilegivel. Texto em markdown renderiza no tamanho nativo do
GitHub, sempre legivel, selecionavel e com link clicavel.

A imagem SVG fica so com o desenho do logo (que encolhe bem, por ser
desenho e nao texto).

Uso:
    python3 tools/readme_text.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import age_string, load_data, stats_rows  # noqa: E402

README = "README.md"

START = "<!-- readme:start -->"
END = "<!-- readme:end -->"

PROJ_START = "<!-- projects:start -->"
PROJ_END = "<!-- projects:end -->"


def status_bar(data):
    """Barra de status no texto: ─[java 86%]─[up 17y]─[streak 12d]─"""
    activity = data.get("activity") or {}
    segs = []

    langs = activity.get("languages") or {}
    if langs:
        name, share = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[0]
        pct = int(round(share * 100))
        cells = 10
        filled = max(1, round(pct / 100 * cells))
        segs.append(f"{name.lower()} {'█' * filled}{'░' * (cells - filled)} {pct}%")

    up = age_string(data.get("birthday", ""))
    if up:
        segs.append(f"up {up.split(' years')[0]}y")
    if "streak" in activity:
        segs.append(f"streak {activity['streak']}d")
    if "repos" in activity:
        segs.append(f"repos {activity['repos']}")

    return "  " + "─".join(f"[{s}]" for s in segs) if segs else ""


def terminal_block(data):
    """Monta o card de terminal em texto puro (mesmo formato do SVG)."""
    activity = data.get("activity") or {}

    def fill(key, value):
        if value:
            return value
        if key.lower() == "uptime":
            return age_string(data.get("birthday", ""))
        if key.lower() == "working in":
            return activity.get("working_on", "")
        return ""

    # Largura da coluna de chaves: a maior entre chaves e nomes de projeto.
    key_w = 0
    for mod in data.get("modules", []):
        if mod.get("type") == "projects":
            for p in activity.get("projects") or []:
                key_w = max(key_w, len(p.get("name", "")))
            continue
        rows = mod.get("rows", [])
        if mod.get("auto") == "stats":
            rows = stats_rows(data)
        for k, v in rows:
            key_w = max(key_w, len(k))
    key_w = max(key_w, 12)

    def row(key, value):
        dots = "." * max(2, key_w - len(key) + 2)
        return f"    {key} {dots} {value}".rstrip()

    lines = []

    # A arte ASCII entra como texto: no tamanho nativo do GitHub ela fica
    # nitida (numa imagem, 96 colunas virariam chuvisco ao encolher).
    art = data.get("logo_lines") or []
    if art:
        lines.extend(art)
        lines.append("")

    lines.append(f"  ❯ {data.get('handle', '')} @{data.get('host', '')}")
    if data.get("subtitle"):
        lines.append(f"    {data['subtitle']}")
    lines.append("  " + "─" * (key_w + 46))

    for mod in data.get("modules", []):
        title = mod.get("title")
        if not title:
            continue

        if mod.get("type") == "projects":
            projects = activity.get("projects") or []
            if not projects:
                continue
            lines.append("")
            lines.append(f"  {title}")
            for p in projects:
                lines.append(f"    {p.get('name', '')}")
            continue

        rows = mod.get("rows", [])
        if mod.get("auto") == "stats":
            rows = stats_rows(data)
        rendered = []
        for key, value in rows:
            value = fill(key, value)
            if value:
                rendered.append(row(key, value))
        if not rendered:
            continue

        lines.append("")
        lines.append(f"  {title}")
        lines.extend(rendered)

    bar = status_bar(data)
    if bar:
        lines.append("")
        lines.append(bar)

    return "\n".join(lines)


def projects_table(data):
    """Tabela de projetos com link (o SVG nao aceita link, o markdown aceita)."""
    activity = data.get("activity") or {}
    projects = activity.get("projects") or []
    if not projects:
        return "_Sem projetos listados._"
    rows = ["| Project | What it is |", "|---|---|"]
    for p in projects:
        name = p.get("name", "")
        desc = p.get("description", "")
        url = p.get("url") or f"https://github.com/{data.get('host', '')}/{name}"
        rows.append(f"| **[{name}]({url})** | {desc} |")
    return "\n".join(rows)


def replace_block(text, start_marker, end_marker, content):
    """Substitui o conteudo entre dois marcadores, criando o bloco se preciso."""
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.S,
    )
    block = f"{start_marker}\n{content}\n{end_marker}"
    if pattern.search(text):
        return pattern.sub(lambda _: block, text)
    return text.rstrip() + "\n\n" + block + "\n"


def main():
    data = load_data("data.json")

    block = "```text\n" + terminal_block(data) + "\n```"
    table = projects_table(data)

    with open(README, encoding="utf-8") as f:
        text = f.read()

    text = replace_block(text, START, END, block)
    text = replace_block(text, PROJ_START, PROJ_END, table)

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"-> {README} atualizado.")


if __name__ == "__main__":
    main()
