#!/usr/bin/env python3
import datetime as dt
import html
import json
import math
import pathlib
import subprocess
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TEMPLATE = ROOT / "README.template.md"
DATA = ROOT / "data" / "profile-data.json"
WIDGETS = ROOT / "widgets"
LOGIN = "caml07"
PROFILE_REPO = f"{LOGIN}/{LOGIN}"

PALETTE = {
    "background": "#151412",
    "surface": "#1c1a17",
    "raised": "#27231e",
    "text": "#d8c7a3",
    "accent": "#e1a33b",
    "success": "#91b36b",
    "danger": "#d96b5f",
    "border": "#493e31",
    "muted": "#817463",
    "dim": "#4e473d",
    "blue": "#7aa2f7",
    "violet": "#8d76ad",
}

CURATED_DESCRIPTIONS = {
    "OSF-Atlas": "An evidence-first archive of Obsidian Soundfields: transcripts, entities, locations and human-reviewed connections.",
}


def run_gh(*args):
    proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return proc.stdout


def xml(value):
    return html.escape(str(value or ""), quote=True)


def weekly_totals(days):
    by_week = defaultdict(int)
    for day in days:
        date = dt.date.fromisoformat(day["date"])
        year, week, _ = date.isocalendar()
        by_week[(year, week)] += int(day.get("contributionCount", 0))
    return [by_week[key] for key in sorted(by_week)]


def weekly_days(days):
    by_week = defaultdict(list)
    for day in sorted(days, key=lambda item: item["date"]):
        date = dt.date.fromisoformat(day["date"])
        year, week, _ = date.isocalendar()
        by_week[(year, week)].append(day)
    return [by_week[key] for key in sorted(by_week)][-53:]


def language_percentages(languages, limit=5):
    rows = [(name, int(size)) for name, size in languages.items() if int(size) > 0]
    rows.sort(key=lambda item: (-item[1], item[0].lower()))
    if len(rows) > limit:
        kept = rows[: limit - 1]
        kept.append(("Other", sum(size for _, size in rows[limit - 1 :])))
        rows = kept
    total = sum(size for _, size in rows)
    if total <= 0:
        return []
    exact = [(name, size, size * 100 / total) for name, size in rows]
    floors = [math.floor(percent) for _, _, percent in exact]
    remainder = 100 - sum(floors)
    order = sorted(
        range(len(exact)),
        key=lambda idx: (exact[idx][2] - floors[idx], exact[idx][1]),
        reverse=True,
    )
    for idx in order[:remainder]:
        floors[idx] += 1
    return [(exact[idx][0], exact[idx][1], floors[idx]) for idx in range(len(exact))]


def fmt_date(value):
    if not value:
        return "—"
    return value[:10].replace("-", ".")


def fmt_time(value):
    if not value or "T" not in value:
        return "--:--"
    return value.split("T", 1)[1][:5]


def clamp(value, limit=88):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fetch_snapshot():
    graphql = r'''query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }'''
    profile = json.loads(run_gh(
        "api", "graphql", "-f", f"query={graphql}", "-F", f"login={LOGIN}"
    ))["data"]["user"]

    repo_pages = json.loads(run_gh(
        "api", "--paginate", "--slurp", f"users/{LOGIN}/repos?per_page=100&type=owner&sort=pushed"
    ))
    raw_repos = [repo for page in repo_pages for repo in page]
    raw_repos = [
        repo for repo in raw_repos
        if not repo.get("private") and repo.get("full_name") != PROFILE_REPO
    ]

    repos = []
    language_totals = defaultdict(int)
    for repo in sorted(raw_repos, key=lambda item: item.get("pushed_at") or "", reverse=True):
        name = repo.get("name", "—")
        languages = json.loads(run_gh("api", f"repos/{LOGIN}/{name}/languages"))
        for language, size in languages.items():
            language_totals[language] += int(size)
        repos.append({
            "name": name,
            "url": repo.get("html_url", ""),
            "description": CURATED_DESCRIPTIONS.get(name) or repo.get("description") or "public repository.",
            "language": repo.get("language") or "",
            "stars": int(repo.get("stargazers_count", 0)),
            "fork": bool(repo.get("fork")),
            "pushed_at": repo.get("pushed_at") or "",
        })

    search = json.loads(run_gh(
        "api", "--method", "GET", "search/commits",
        "-f", f"q=author:{LOGIN}", "-f", "sort=committer-date", "-f", "order=desc", "-f", "per_page=50"
    ))
    recent_commits = []
    for item in search.get("items", []):
        repo = item.get("repository") or {}
        if repo.get("private") or repo.get("full_name") == PROFILE_REPO:
            continue
        commit = item.get("commit") or {}
        when = (commit.get("committer") or commit.get("author") or {}).get("date", "")
        recent_commits.append({
            "sha": (item.get("sha") or "")[:7],
            "date": when,
            "message": clamp((commit.get("message") or "").splitlines()[0], 96),
            "repo": repo.get("name") or (repo.get("full_name") or "—").split("/")[-1],
            "url": item.get("html_url") or "",
        })
        if len(recent_commits) >= 7:
            break

    latest = recent_commits[0] if recent_commits else {
        "sha": "—", "date": "", "message": "no public commit found", "repo": "—",
        "url": f"https://github.com/{LOGIN}?tab=repositories",
    }
    repo_lookup = {repo["name"]: repo for repo in repos}
    active_repo = dict(repo_lookup.get(latest["repo"], {})) or {
        "name": latest["repo"], "url": f"https://github.com/{LOGIN}?tab=repositories",
        "description": "latest public work.", "language": "", "stars": 0, "fork": False,
        "pushed_at": latest["date"],
    }

    weeks = profile["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [day for week in weeks for day in week.get("contributionDays", [])]
    total = int(profile["contributionsCollection"]["contributionCalendar"]["totalContributions"])

    return {
        "login": LOGIN,
        "public_repos": len(repos),
        "stars": sum(repo["stars"] for repo in repos),
        "contributions": total,
        "contribution_days": days,
        "active_repo": active_repo,
        "latest_commit": latest,
        "repos": repos,
        "languages": dict(language_totals),
        "recent_commits": recent_commits,
        "generated_at": dt.datetime.now(dt.timezone.utc).date().isoformat(),
    }


def svg_header(width, height, title, right=""):
    p = PALETTE
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
  <style>
    .mono {{ font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace; }}
    .caps {{ letter-spacing: .12em; }}
  </style>
  <rect width="{width}" height="{height}" fill="{p['background']}"/>
  <rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" fill="none" stroke="{p['border']}"/>
  <text x="22" y="28" class="mono caps" fill="{p['accent']}" font-size="11" font-weight="700">{xml(title)}</text>
  <text x="{width-22}" y="28" text-anchor="end" class="mono caps" fill="{p['success']}" font-size="10">{xml(right)}</text>
  <line x1="22" y1="42" x2="{width-22}" y2="42" stroke="{p['border']}" opacity=".72"/>'''


def render_telemetry_svg(snapshot):
    p = PALETTE
    repo = snapshot["active_repo"]
    commit = snapshot["latest_commit"]
    columns = [
        ("CONTRIB / 365D", f'{int(snapshot["contributions"]):03d}', p["success"]),
        ("PUBLIC REPOS", f'{int(snapshot["public_repos"]):02d}', p["blue"]),
        ("PUBLIC STARS", f'{int(snapshot["stars"]):02d}', p["violet"]),
        ("LAST SIGNAL", xml(commit.get("sha", "—")), p["accent"]),
    ]
    out = [svg_header(900, 126, "TELEMETRY", "● LIVE")]
    x0, usable = 22, 856
    cell = usable / 4
    for idx, (label, value, color) in enumerate(columns):
        x = x0 + idx * cell
        if idx:
            out.append(f'<line x1="{x:.1f}" y1="56" x2="{x:.1f}" y2="105" stroke="{p["border"]}" opacity=".6"/>')
        out.append(f'<text x="{x+14:.1f}" y="75" class="mono caps" fill="{p["muted"]}" font-size="8.5">{label}</text>')
        out.append(f'<text x="{x+14:.1f}" y="101" class="mono" fill="{color}" font-size="20" font-weight="700">{value}</text>')
    out.append(f'<text x="878" y="117" text-anchor="end" class="mono" fill="{p["dim"]}" font-size="8">{xml(str(repo.get("name", "—")).upper())} / {xml(fmt_date(commit.get("date", "")))}</text>')
    out.append('</svg>')
    return "\n".join(out)


def render_garden_svg(snapshot):
    p = PALETTE
    weeks = weekly_days(snapshot.get("contribution_days", []))
    if not weeks:
        weeks = [[]]
    totals = [sum(int(day.get("contributionCount", 0)) for day in week) for week in weeks]
    max_total = max(max(totals), 1)
    width, height = 900, 228
    left, right, baseline = 28, 872, 184
    span = right - left
    step = span / max(len(weeks) - 1, 1)
    out = [svg_header(width, height, "GARDEN / 365D", "● LIVE")]
    out.append(f'<line x1="{left}" y1="{baseline}" x2="{right}" y2="{baseline}" stroke="{p["border"]}"/>')

    for index, week in enumerate(weeks):
        total = totals[index]
        x = left + index * step
        age = index / max(len(weeks) - 1, 1)
        stem_color = p["success"] if age > .72 else "#66725e" if age > .35 else "#535d4d"
        if total <= 0:
            out.append(f'<circle data-week="{index}" cx="{x:.2f}" cy="{baseline}" r="1.25" fill="{p["dim"]}" opacity=".5"/>')
            continue
        strength = math.sqrt(total / max_total)
        stem_h = 14 + strength * 78
        top = baseline - stem_h
        bend = math.sin(index * 1.61) * (2.0 + strength * 4.0)
        top_x = x + bend
        out.append(f'<g data-week="{index}" data-total="{total}">')
        out.append(f'<path d="M {x:.2f} {baseline:.2f} Q {x-bend:.2f} {(baseline+top)/2:.2f} {top_x:.2f} {top:.2f}" fill="none" stroke="{stem_color}" stroke-width="{0.8 + strength*0.75:.2f}" stroke-linecap="round"/>')
        active_days = [day for day in week if int(day.get("contributionCount", 0)) > 0]
        for leaf_index, day in enumerate(active_days):
            count = int(day.get("contributionCount", 0))
            fraction = (leaf_index + 1) / (len(active_days) + 1)
            cy = baseline - stem_h * fraction
            cx = x + bend * fraction
            side = -1 if (index + leaf_index) % 2 == 0 else 1
            leaf_len = 3.8 + min(count, 10) * 0.42
            leaf_w = 1.8 + min(count, 10) * 0.16
            leaf_color = p["success"] if age > .72 else "#75826a" if age > .35 else "#60695a"
            opacity = .52 + min(count, 10) * .035
            lx = cx + side * (4.2 + leaf_len * .25)
            rotate = -28 if side < 0 else 28
            out.append(f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{lx:.2f}" y2="{cy-1.2:.2f}" stroke="{leaf_color}" stroke-width=".7" opacity="{opacity:.2f}"/>')
            out.append(f'<ellipse cx="{lx + side*leaf_len/2:.2f}" cy="{cy-2.1:.2f}" rx="{leaf_len:.2f}" ry="{leaf_w:.2f}" transform="rotate({rotate} {lx + side*leaf_len/2:.2f} {cy-2.1:.2f})" fill="{leaf_color}" opacity="{opacity:.2f}"/>')
        if index == len(weeks) - 1:
            out.append(f'<circle cx="{top_x:.2f}" cy="{top:.2f}" r="3.4" fill="{p["accent"]}"/>')
            out.append(f'<circle cx="{top_x:.2f}" cy="{top:.2f}" r="6.8" fill="none" stroke="{p["accent"]}" opacity=".24"/>')
        out.append('</g>')

    out.append(f'<text x="28" y="212" class="mono caps" fill="{p["dim"]}" font-size="8">OLD GROWTH</text>')
    out.append(f'<text x="872" y="212" text-anchor="end" class="mono caps" fill="{p["muted"]}" font-size="8">NOW / {int(snapshot.get("contributions", 0))} CONTRIBUTIONS</text>')
    out.append('</svg>')
    return "\n".join(out)


def render_mixer_svg(snapshot):
    p = PALETTE
    rows = language_percentages(snapshot.get("languages", {}))
    colors = [p["accent"], p["success"], p["blue"], p["danger"], p["violet"]]
    height = 72 + max(1, len(rows)) * 30
    out = [svg_header(900, height, "MIXER / LANGUAGES", "BYTES / PUBLIC REPOS")]
    if not rows:
        out.append(f'<text x="22" y="72" class="mono" fill="{p["muted"]}" font-size="11">NO LANGUAGE DATA</text>')
    for idx, (name, _size, percent) in enumerate(rows):
        y = 69 + idx * 30
        color = colors[idx % len(colors)]
        track_x, track_w = 178, 610
        fill_w = track_w * percent / 100
        out.append(f'<text x="24" y="{y+5}" class="mono caps" fill="{p["text"]}" font-size="10">{xml(name.upper())}</text>')
        out.append(f'<rect x="{track_x}" y="{y-6}" width="{track_w}" height="11" fill="{p["raised"]}"/>')
        out.append(f'<rect x="{track_x}" y="{y-6}" width="{fill_w:.2f}" height="11" fill="{color}"/>')
        out.append(f'<line x1="{track_x + fill_w:.2f}" y1="{y-10}" x2="{track_x + fill_w:.2f}" y2="{y+9}" stroke="{p["text"]}" stroke-width="1"/>')
        out.append(f'<text x="858" y="{y+5}" text-anchor="end" class="mono" fill="{color}" font-size="11" font-weight="700">{percent:02d}%</text>')
    out.append('</svg>')
    return "\n".join(out)


def render_now(snapshot):
    repo = snapshot["active_repo"]
    commit = snapshot["latest_commit"]
    kind = "FORK" if repo.get("fork") else "ORIGINAL"
    language = (repo.get("language") or "NO PRIMARY LANGUAGE").upper()
    return f'''## DECK / NOW

### [{repo["name"]}]({repo["url"]})

{repo.get("description") or "latest public work."}

`{language}` · `{kind}` · `★ {repo.get("stars", 0)}`

**LAST SIGNAL**<br>
[`{commit["sha"]}`]({commit["url"]}) · `{fmt_date(commit["date"])}` · `{fmt_time(commit["date"])}`<br>
{commit["message"]}'''


def render_bank(snapshot):
    lines = ["## BANK / PUBLIC", ""]
    active_name = snapshot.get("active_repo", {}).get("name")
    for index, repo in enumerate(snapshot.get("repos", []), start=1):
        active = repo["name"] == active_name
        marker = f"▌ ● {index:02d}" if active else f"  ○ {index:02d}"
        status = "NOW" if active else "FORK" if repo.get("fork") else "PUBLIC"
        language = (repo.get("language") or "—").upper()
        lines.append(f'`{marker}` **[{repo["name"]}]({repo["url"]})** `{language} / {status}`')
        lines.append(f'<sub>{repo.get("description") or "public repository."}</sub>')
        lines.append("")
    return "\n".join(lines).rstrip()


def render_log(snapshot):
    rows = []
    for commit in snapshot.get("recent_commits", []):
        rows.append(f'{fmt_date(commit["date"])} {fmt_time(commit["date"])}  {commit["sha"]:<7}  {commit["repo"]}')
        rows.append(f'  {clamp(commit["message"], 78)}')
        rows.append("")
    if not rows:
        rows = ["no public authored commits found"]
    return "## LOG / RECENT\n\n```text\n" + "\n".join(rows).rstrip() + "\n```"


def render_readme(snapshot):
    template = TEMPLATE.read_text(encoding="utf-8")
    widgets = {
        "{{TELEMETRY}}": '<img src="./widgets/telemetry.svg" width="100%" alt="CAM / 07 GitHub telemetry">',
        "{{NOW}}": render_now(snapshot),
        "{{GARDEN}}": '## GARDEN / 365D\n\n<img src="./widgets/garden.svg" width="100%" alt="A living garden generated from the last 365 days of GitHub contributions">\n\n<sub>365 contribution days → weekly stems → daily leaves. Same activity, same garden.</sub>',
        "{{BANK}}": render_bank(snapshot),
        "{{MIXER}}": '## MIXER / LANGUAGES\n\n<img src="./widgets/mixer.svg" width="100%" alt="Language mix across public repositories">',
        "{{LOG}}": render_log(snapshot),
        "{{FOOTER}}": f'<sub>SOURCE / GITHUB GRAPHQL + REST · REFRESH / 6H · UPDATED / {fmt_date(snapshot["generated_at"])} · CAM / 07</sub>',
    }
    for marker, value in widgets.items():
        template = template.replace(marker, value)
    return template.rstrip() + "\n"


def snapshot_for_disk(snapshot):
    return {
        "login": snapshot.get("login"),
        "public_repos": snapshot.get("public_repos"),
        "stars": snapshot.get("stars"),
        "contributions": snapshot.get("contributions"),
        "active_repo": snapshot.get("active_repo"),
        "latest_commit": snapshot.get("latest_commit"),
        "repos": snapshot.get("repos", []),
        "languages": snapshot.get("languages", {}),
        "recent_commits": snapshot.get("recent_commits", []),
        "generated_at": snapshot.get("generated_at"),
        "moss_weeks": weekly_totals(snapshot.get("contribution_days", []))[-53:],
    }


def main():
    snapshot = fetch_snapshot()
    WIDGETS.mkdir(parents=True, exist_ok=True)
    README.write_text(render_readme(snapshot), encoding="utf-8")
    (WIDGETS / "telemetry.svg").write_text(render_telemetry_svg(snapshot), encoding="utf-8")
    (WIDGETS / "garden.svg").write_text(render_garden_svg(snapshot), encoding="utf-8")
    (WIDGETS / "mixer.svg").write_text(render_mixer_svg(snapshot), encoding="utf-8")
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(snapshot_for_disk(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote README.md, widgets/*.svg and data/profile-data.json")


if __name__ == "__main__":
    main()
