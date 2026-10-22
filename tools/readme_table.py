#!/usr/bin/env python3
"""
Mantem a tabela de projetos do README, se ela existir.

O card (arte + campos) e' um SVG: o GitHub renderiza a imagem do jeito que
ela foi desenhada, e nao da pra clicar em nada dentro dela. O markdown
entra so com o que a imagem nao faz: link clicavel e a descricao inteira
dos projetos (no card, a curta, que cabe na largura).

A tabela e' opt-in: enquanto o README nao tiver os marcadores, o tool
nao cria o bloco.

Uso:
    python3 tools/readme_table.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import load_data  # noqa: E402

README = "README.md"

PROJ_START = "<!-- projects:start -->"
PROJ_END = "<!-- projects:end -->"


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
    """Substitui o conteudo entre dois marcadores.

    O bloco so e' substituido se ja existir no README: a tabela e' opt-in.
    """
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.S,
    )
    if not pattern.search(text):
        return text
    block = f"{start_marker}\n{content}\n{end_marker}"
    return pattern.sub(lambda _: block, text)


def main():
    data = load_data("data.json")

    with open(README, encoding="utf-8") as f:
        text = f.read()

    text = replace_block(text, PROJ_START, PROJ_END, projects_table(data))

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"-> {README} atualizado.")


if __name__ == "__main__":
    main()
