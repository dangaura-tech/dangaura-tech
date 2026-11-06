#!/usr/bin/env python3
"""Generate self-hosted profile cards (stats, languages, achievements) as SVG files.

Runs in GitHub Actions with the built-in GITHUB_TOKEN (public data only) and has no
third-party dependencies, so the profile never depends on rate-limited public services.

    python scripts/generate_cards.py --user dangaura-tech --out dist
    python scripts/generate_cards.py --mock --out dist          # offline preview
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svgart import Orbit, fibonacci_sphere, orbit_cloud  # noqa: E402

API = "https://api.github.com"

THEME = {
    "bg": "#0f1326",
    "border": "#262b4d",
    "title": "#e6e8ff",
    "text": "#c9cdf0",
    "muted": "#7a81ab",
    "accent": "#8b7cff",
    "icon": "#22d3ee",
}

# GitHub linguist colours for the languages we are likely to show.
LANG_COLORS = {
    "Python": "#3572A5", "Go": "#00ADD8", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Solidity": "#AA6746", "Shell": "#89e051", "C++": "#f34b7d", "C": "#555555", "Rust": "#dea584",
    "Jupyter Notebook": "#DA5B0B", "Dockerfile": "#384d54", "Makefile": "#427819", "HTML": "#e34c26",
    "CSS": "#563d7c", "Cuda": "#3A4E3A", "TeX": "#3D6117",
}  # fmt: skip

# Markup / bibliography files from paper write-ups are not "languages" in a meaningful sense.
IGNORED_LANGUAGES = {"BibTeX Style", "TeX", "HTML", "CSS", "Makefile", "Dockerfile"}

ACHIEVEMENT_NAMES = {
    "pull-shark": "Pull Shark", "yolo": "YOLO", "quickdraw": "Quickdraw", "starstruck": "Starstruck",
    "pair-extraordinaire": "Pair Extraordinaire", "galaxy-brain": "Galaxy Brain", "public-sponsor": "Public Sponsor",
    "arctic-code-vault-contributor": "Arctic Code Vault", "heart-on-your-sleeve": "Heart On Your Sleeve",
    "open-sourcerer": "Open Sourcerer",
}  # fmt: skip


# --------------------------------------------------------------------------- data fetching
class GitHub:
    def __init__(self, token: str | None) -> None:
        self.token = token

    def _request(self, url: str, data: bytes | None = None, accept: str = "application/vnd.github+json"):
        headers = {"Accept": accept, "User-Agent": "profile-cards"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())

    def get(self, path: str):
        return self._request(f"{API}{path}")

    def paginate(self, path: str):
        page, out = 1, []
        sep = "&" if "?" in path else "?"
        while True:
            items = self.get(f"{path}{sep}per_page=100&page={page}")
            out.extend(items)
            if len(items) < 100:
                return out
            page += 1

    def graphql(self, query: str, variables: dict):
        body = json.dumps({"query": query, "variables": variables}).encode()
        return self._request(f"{API}/graphql", data=body)


CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def streaks(days: list[tuple[str, int]]) -> tuple[int, int]:
    """Return (current streak, longest streak) from (date, count) pairs sorted by date."""
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    rev = list(reversed(days))
    if rev and rev[0][1] == 0:  # today without contributions does not break the streak yet
        rev = rev[1:]
    for _, c in rev:
        if c == 0:
            break
        current += 1
    return current, longest


ACHIEVEMENT_IMG = re.compile(
    r"(https://github\.githubassets\.com/[^\"'\s]*?/([a-z0-9]+(?:-[a-z0-9]+)*?)-default(?:-[0-9a-f]{6,})?\.png)"
)


def scrape_achievements(user: str) -> list[dict]:
    """GitHub has no API for achievements, so read the public achievements tab.

    Returns ``[{"slug": ..., "image": url}]`` in page order, de-duplicated. Badge images are
    served either as ``.../achievements/<slug>-default.png`` or as hashed asset names
    ``.../assets/<slug>-default-<hash>.png``; both forms are recognised.
    """
    try:
        req = urllib.request.Request(f"https://github.com/{user}?tab=achievements", headers={"User-Agent": "Mozilla/5.0"})
        page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: achievements page unavailable: {exc}", file=sys.stderr)
        return []
    found: dict[str, str] = {}
    for url, slug in ACHIEVEMENT_IMG.findall(page):
        found.setdefault(slug, url)
    return [{"slug": k, "image": v} for k, v in found.items()]


def fetch(user: str, token: str | None) -> dict:
    gh = GitHub(token)
    repos = [r for r in gh.paginate(f"/users/{user}/repos?type=owner") if not r["fork"]]
    langs: Counter = Counter()
    for r in repos:
        if r["name"] == user:  # the profile repo itself is not a project
            continue
        for lang, size in gh.get(f"/repos/{user}/{r['name']}/languages").items():
            if lang not in IGNORED_LANGUAGES:
                langs[lang] += size
    def search_count(path: str, accept: str = "application/vnd.github+json") -> int | None:
        """Search API totals; ``None`` when GitHub refuses the query (e.g. 422 for private profiles)."""
        try:
            return int(gh._request(f"{API}{path}", accept=accept)["total_count"])
        except urllib.error.HTTPError as exc:
            print(f"warning: {path} -> HTTP {exc.code}", file=sys.stderr)
            return None

    commits = search_count(f"/search/commits?q=author:{user}&per_page=1", "application/vnd.github.cloak-preview+json")
    prs = search_count(f"/search/issues?q=author:{user}+type:pr&per_page=1")
    merged = search_count(f"/search/issues?q=author:{user}+type:pr+is:merged&per_page=1")
    issues = search_count(f"/search/issues?q=author:{user}+type:issue&per_page=1")
    total_contrib, current, longest = None, 0, 0
    try:
        cal = gh.graphql(CALENDAR_QUERY, {"login": user})["data"]["user"]["contributionsCollection"]
        cal = cal["contributionCalendar"]
        days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
        total_contrib = cal["totalContributions"]
        current, longest = streaks(days)
    except Exception as exc:  # noqa: BLE001 - the card still renders without the calendar
        print(f"warning: contribution calendar unavailable: {exc}", file=sys.stderr)
    return {
        "user": user,
        "stars": sum(r["stargazers_count"] for r in repos),
        "forks": sum(r["forks_count"] for r in repos),
        "repos": len([r for r in repos if r["name"] != user]),
        "commits": commits,
        "prs": prs,
        "merged_prs": merged,
        "issues": issues,
        "contributions": total_contrib,
        "current_streak": current,
        "longest_streak": longest,
        "languages": dict(langs.most_common()),
        "achievements": scrape_achievements(user),
    }


MOCK = {
    "user": "dangaura-tech", "stars": 3, "forks": 1, "repos": 6, "commits": 87, "prs": 4, "merged_prs": 3,
    "issues": 2, "contributions": 112, "current_streak": 5, "longest_streak": 9,
    "languages": {"Python": 410000, "Go": 95000, "TypeScript": 30000, "Solidity": 21000, "Shell": 4000},
    "achievements": [{"slug": s, "image": ""} for s in ("pull-shark", "yolo", "quickdraw")],
}  # fmt: skip


# ------------------------------------------------------------------------------ rendering
def _frame(width: int, height: int, title: str, body: str) -> str:
    t = THEME
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
<style>
.title {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: {t["title"]}; }}
.label {{ font: 400 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: {t["text"]}; }}
.value {{ font: 700 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: {t["text"]}; }}
.muted {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: {t["muted"]}; }}
.big {{ font: 700 26px 'Segoe UI', Ubuntu, Sans-Serif; fill: {t["accent"]}; }}
.fade {{ opacity: 0; animation: fadein .6s ease-in-out forwards; }}
@keyframes fadein {{ to {{ opacity: 1; }} }}
</style>
<rect x="0.5" y="0.5" rx="10" width="{width - 1}" height="{height - 1}" fill="{t["bg"]}" stroke="{t["border"]}"/>
<text x="25" y="35" class="title">{html.escape(title)}</text>
{body}
</svg>
"""


def _fmt(n) -> str:
    if n is None:
        return "-"
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render_stats(d: dict) -> str:
    rows = [
        ("★", "Total stars", d["stars"]),
        ("⎇", "Commits", d["commits"]),
        ("⇄", "Pull requests (merged)", f"{_fmt(d['prs'])} ({_fmt(d['merged_prs'])})"),
        ("!", "Issues", d["issues"]),
        ("▣", "Public repositories", d["repos"]),
    ]
    if not d["stars"]:
        rows = rows[1:]
    body = []
    for i, (icon, label, value) in enumerate(rows):
        y = 78 + i * 30 + (15 if len(rows) < 5 else 0)
        body.append(
            f'<g class="fade" style="animation-delay:{150 + i * 120}ms">'
            f'<text x="25" y="{y}" class="label" fill="{THEME["icon"]}" style="fill:{THEME["icon"]}">{icon}</text>'
            f'<text x="48" y="{y}" class="label">{html.escape(label)}:</text>'
            f'<text x="240" y="{y}" class="value">{html.escape(value if isinstance(value, str) else _fmt(value))}</text></g>'
        )
    orbit = Orbit(cx=385, cy=128, scale=52, period=16)
    body.append(orbit_cloud(orbit, fibonacci_sphere(140), radius=1.7))
    return _frame(470, 240, f"{d['user']}'s GitHub stats", "\n".join(body))


def render_languages(d: dict, top: int = 6) -> str:
    langs = list(d["languages"].items())[:top]
    total = sum(v for _, v in langs) or 1
    x, bar = 25, []
    for name, v in langs:
        w = 420 * v / total
        bar.append(f'<rect x="{x:.1f}" y="60" width="{w:.1f}" height="10" fill="{LANG_COLORS.get(name, "#8b949e")}"/>')
        x += w
    items = []
    for i, (name, v) in enumerate(langs):
        col, row = i % 2, i // 2
        px, py = 25 + col * 215, 112 + row * 40
        items.append(
            f'<g class="fade" style="animation-delay:{200 + i * 120}ms">'
            f'<circle cx="{px + 6}" cy="{py - 5}" r="6" fill="{LANG_COLORS.get(name, "#8b949e")}"/>'
            f'<text x="{px + 20}" y="{py}" class="label">{html.escape(name)}</text>'
            f'<text x="{px + 190}" y="{py}" text-anchor="end" class="muted">{100 * v / total:.1f}%</text></g>'
        )
    clip = '<clipPath id="r"><rect x="25" y="60" width="420" height="10" rx="5"/></clipPath>'
    body = f'{clip}<g clip-path="url(#r)">{"".join(bar)}</g>' + "\n".join(items)
    return _frame(470, 240, "Most used languages", body)


def _badge_image(url: str) -> str | None:
    if not url:
        return None
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
    except (urllib.error.URLError, TimeoutError):
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode()


def render_achievements(d: dict, embed: bool = True) -> str:
    badges = d["achievements"]
    if not badges:
        body = '<text x="25" y="80" class="muted">Achievements will appear here as they are unlocked.</text>'
        return _frame(470, 110, "GitHub achievements", body)
    items = []
    shown = badges[:6]
    start = (470 - 72 * len(shown) + 12) / 2
    for i, badge in enumerate(shown):
        slug = badge["slug"]
        x = round(start + i * 72)
        img = _badge_image(badge["image"]) if embed else None
        if img:
            pic = f'<image x="{x}" y="52" width="60" height="60" xlink:href="{img}" href="{img}"/>'
        else:
            pic = (
                f'<circle cx="{x + 30}" cy="82" r="28" fill="{THEME["border"]}"/>'
                f'<text x="{x + 30}" y="90" text-anchor="middle" class="big">★</text>'
            )
        name = ACHIEVEMENT_NAMES.get(slug, slug.replace("-", " ").title())
        items.append(
            f'<g class="fade" style="animation-delay:{150 + i * 150}ms">{pic}'
            f'<text x="{x + 30}" y="130" text-anchor="middle" class="muted">{html.escape(name)}</text></g>'
        )
    return _frame(470, 150, "GitHub achievements", "\n".join(items))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "dangaura-tech"))
    p.add_argument("--out", default="dist")
    p.add_argument("--mock", action="store_true", help="render with sample data, no network")
    args = p.parse_args()

    data = MOCK if args.mock else fetch(args.user, os.environ.get("GITHUB_TOKEN"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.svg").write_text(render_stats(data))
    (out / "languages.svg").write_text(render_languages(data))
    (out / "achievements.svg").write_text(render_achievements(data, embed=not args.mock))
    (out / "data.json").write_text(json.dumps({**data, "generated_at": dt.datetime.now(dt.UTC).isoformat()}, indent=2))
    print(json.dumps({k: v for k, v in data.items() if k != "languages"}, indent=2))


if __name__ == "__main__":
    main()
