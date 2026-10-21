#!/usr/bin/env python3
"""
Busca os dados do GitHub e grava em data.json (secao "activity").

So usa a biblioteca padrao (urllib) pra nao depender de pip no Action.

Variaveis de ambiente:
    GITHUB_TOKEN  -> Personal Access Token (fine-grained, somente leitura)
    GITHUB_USER   -> login do dono do perfil (ex.: Campeol-G)

Uso:
    python3 tools/update.py
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com/graphql"
DATA_FILE = "data.json"
CACHE_FILE = "cache/loc.json"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER = os.environ.get("GITHUB_USER", "")


# ----------------------------------------------------------------- graphql
def graphql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-updater",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:500]
            if e.code in (502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"GraphQL falhou ({e.code}): {detail}")
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise SystemExit(f"Erro de rede: {e}")
        if "errors" in body:
            raise SystemExit("GraphQL retornou erro: " + json.dumps(body["errors"])[:600])
        return body["data"]
    raise SystemExit("GraphQL falhou apos varias tentativas.")


# ------------------------------------------------------------- consultas
Q_CALENDAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    id
    createdAt
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""

Q_PROFILE = """
query($login: String!) {
  user(login: $login) {
    id
    name
    repositories(ownerAffiliations: OWNER) { totalCount }
    pullRequests(states: OPEN) { totalCount }
    issues(states: OPEN) { totalCount }
  }
}
"""

Q_REPOS = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER) {
      totalCount
      pageInfo { endCursor hasNextPage }
      nodes {
        nameWithOwner
        name
        description
        isFork
        pushedAt
        defaultBranchRef {
          target { ... on Commit { history(first: 1) { totalCount } } }
        }
      }
    }
  }
}
"""

Q_HISTORY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            nodes {
              author { user { id } }
              additions
              deletions
            }
            pageInfo { endCursor hasNextPage }
          }
        }
      }
    }
  }
}
"""


# ------------------------------------------------------------- utilidades
def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def level_for(count, thresholds):
    """0 = sem atividade. 1..4 = os niveis do heatmap do GitHub."""
    if count <= 0:
        return 0
    for i, t in enumerate(thresholds):
        if count <= t:
            return i + 1
    return 4


def compute_streaks(days):
    """days: lista de (date, count) ordenada. Devolve (atual, maior)."""
    current = 0
    best = 0
    run = 0
    for _, count in days:
        run = run + 1 if count > 0 else 0
        best = max(best, run)
    # Streak atual: conta de tras pra frente a partir de hoje.
    for _, count in reversed(days):
        if count > 0:
            current += 1
        else:
            break
    # Se hoje ainda nao teve commit, o streak de ontem continua valendo.
    if current == 0 and len(days) > 1:
        for _, count in reversed(days[:-1]):
            if count > 0:
                current += 1
            else:
                break
    return current, best


def build_heatmap(weeks):
    """Converte as semanas do GraphQL no grid [semana][dia] com niveis 0..4."""
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    if not days:
        return [], 0, 0, 0
    counts = sorted(c for _, c in days if c > 0)
    if not counts:
        thresholds = [0, 0, 0]
    else:
        def q(p):
            return counts[min(len(counts) - 1, int(len(counts) * p))]
        thresholds = [q(0.25), q(0.5), q(0.75)]

    grid = []
    for week in weeks:
        row = [level_for(day["contributionCount"], thresholds) for day in week["contributionDays"]]
        # A primeira semana comeca no meio da semana: preenche com None.
        first = week.get("firstDay")
        if first and len(grid) == 0:
            offset = datetime.date.fromisoformat(first).weekday()
            row = [None] * offset + row
        grid.append(row)

    total = sum(c for _, c in days)
    current, best = compute_streaks(days)
    return grid, total, current, best


def count_loc(owner, repo, my_id):
    """Soma additions/deletions dos commits escritos por mim no repo."""
    additions = deletions = commits = 0
    cursor = None
    while True:
        data = graphql(
            Q_HISTORY,
            {"owner": owner, "name": repo, "cursor": cursor},
        )
        ref = (data.get("repository") or {}).get("defaultBranchRef")
        if not ref:
            break
        target = ref.get("target") or {}
        history = target.get("history") or {}
        for node in history.get("nodes") or []:
            author = (node.get("author") or {}).get("user")
            if author and author.get("id") == my_id:
                additions += node.get("additions") or 0
                deletions += node.get("deletions") or 0
                commits += 1
        page = history.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return additions, deletions, commits


def dump_json(path, data):
    """Escreve JSON mantendo os pares [chave, valor] em uma linha só."""
    def fmt(obj, indent=0):
        pad = "  " * indent
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            items = []
            for k, v in obj.items():
                if k == "weeks":
                    items.append(f'{pad}  "weeks": {json.dumps(v)}')
                else:
                    items.append(f'{pad}  "{k}": {fmt(v, indent + 1)}')
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        if isinstance(obj, list):
            if not obj:
                return "[]"
            if all(isinstance(x, list) and len(x) == 2 for x in obj):
                rows = ", ".join(json.dumps(x, ensure_ascii=False) for x in obj)
                return "[" + rows + "]"
            items = [f"{pad}  {fmt(v, indent + 1)}" for v in obj]
            return "[\n" + ",\n".join(items) + f"\n{pad}]"
        return json.dumps(obj, ensure_ascii=False)

    with open(path, "w", encoding="utf-8") as f:
        f.write(fmt(data) + "\n")


def read_handle():
    """O login do GitHub vem do data.json.

    Cuidado: 'handle' e' o nome de exibicao ("Gustavo Campeol") e NAO serve
    pra API. O login e' o campo 'login' (fallback: 'host', depois a env).
    """
    if USER:
        return USER
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    for key in ("login", "host", "handle"):
        value = data.get(key)
        if value and " " not in value:
            return value
    return ""


def main():
    handle = read_handle()
    if not handle:
        sys.exit("Informe o login em data.json (campo 'login') ou em GITHUB_USER.")
    now = datetime.datetime.now(datetime.timezone.utc)
    since = now - datetime.timedelta(days=371)

    print(f"-> Buscando dados de {handle}...")
    cal = graphql(
        Q_CALENDAR,
        {
            "login": handle,
            "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    user = cal["user"]
    my_id = user["id"]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    grid, total_commits, streak, longest = build_heatmap(weeks)
    print(f"   commits no periodo: {total_commits} | streak: {streak} | maior: {longest}")

    profile = graphql(Q_PROFILE, {"login": handle})["user"]
    repo_count = profile["repositories"]["totalCount"]
    open_prs = profile["pullRequests"]["totalCount"]
    open_issues = profile["issues"]["totalCount"]
    print(f"   repos: {repo_count} | PRs abertos: {open_prs} | issues abertas: {open_issues}")

    # Repos + linhas de codigo (com cache por repositorio)
    repos = []
    cursor = None
    while True:
        data = graphql(Q_REPOS, {"login": handle, "cursor": cursor})["user"]["repositories"]
        repos.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    # Projeto mais recente (para a linha "working in")
    working_on = ""
    pushed = [
        (node.get("pushedAt") or "", node["nameWithOwner"].split("/", 1)[1])
        for node in repos
    ]
    pushed.sort(reverse=True)
    for _, name in pushed:
        if name.lower() != handle.lower():
            working_on = name
            break
    if working_on:
        print(f"   working in: {working_on}")

    # Bytes por linguagem (para a barra de status)
    lang_bytes = {}
    for node in repos:
        full = node["nameWithOwner"]
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{full}/languages",
                headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "profile-readme-updater"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:  # rede pode falhar; nao impede o resto
            print(f"   aviso: linguagens de {full} indisponiveis ({e})")
            continue
        for lang, size in (data or {}).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + size
    total_bytes = sum(lang_bytes.values()) or 1
    languages = {k: round(v / total_bytes, 4) for k, v in sorted(lang_bytes.items(), key=lambda kv: -kv[1])}
    print("   linguagens: " + ", ".join(f"{k} {v:.0%}" for k, v in list(languages.items())[:4]))

    cache = load_cache()
    loc_add = loc_del = my_commits = 0
    for node in repos:
        full = node["nameWithOwner"]
        owner, name = full.split("/", 1)
        ref = node.get("defaultBranchRef")
        if not ref:
            continue
        total = ((ref.get("target") or {}).get("history") or {}).get("totalCount") or 0
        entry = cache.get(full)
        if entry and entry.get("commits_total") == total:
            loc_add += entry["additions"]
            loc_del += entry["deletions"]
            my_commits += entry["my_commits"]
            continue
        a, d, c = count_loc(owner, name, my_id)
        cache[full] = {
            "commits_total": total,
            "additions": a,
            "deletions": d,
            "my_commits": c,
        }
        loc_add += a
        loc_del += d
        my_commits += c
        print(f"   {full}: +{a}/-{d} em {c} commits")
    save_cache(cache)

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Bloco de projetos: os que tem mais trabalho seu (commits proprios).
    fallback = data.get("project_descriptions", {})
    excluded = set(data.get("exclude_projects", []))
    limit = int(data.get("projects_limit", 4))
    ranked = []
    for node in repos:
        full = node["nameWithOwner"]
        name = node.get("name") or full.split("/", 1)[1]
        if name in excluded or full in excluded:
            continue
        entry = cache.get(full) or {}
        mine = entry.get("my_commits", 0)
        desc = node.get("description") or fallback.get(name, "")
        if not desc:
            continue
        label = name + (" (fork)" if node.get("isFork") else "")
        ranked.append((mine, node.get("pushedAt") or "", label, desc))
    ranked.sort(key=lambda r: (r[0], r[1]), reverse=True)
    projects = [{"name": r[2], "description": r[3]} for r in ranked[:limit]]
    if projects:
        print("   projetos: " + ", ".join(p["name"] for p in projects))

    data["activity"] = {
        "streak": streak,
        "longest_streak": longest,
        "commits": total_commits,
        "lines_added": loc_add,
        "lines_deleted": loc_del,
        "repos": repo_count,
        "open_prs": open_prs,
        "open_issues": open_issues,
        "languages": languages,
        "working_on": working_on,
        "projects": projects,
    }
    dump_json(DATA_FILE, data)
    print(f"-> {DATA_FILE} atualizado.")


if __name__ == "__main__":
    main()
