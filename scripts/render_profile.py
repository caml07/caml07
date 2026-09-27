#!/usr/bin/env python3
import datetime as dt
import json
import math
import pathlib
import subprocess
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TEMPLATE = ROOT / "README.template.md"
SNAPSHOT = ROOT / "data" / "profile-data.json"
LOGIN = "caml07"
PROFILE_REPO = f"{LOGIN}/{LOGIN}"

CURATED_DESCRIPTIONS = {
    "OSF-Atlas": "An evidence-first archive of Obsidian Soundfields: transcripts, entities, locations and human-verified connections.",
}


def run_gh(*args):
    proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return proc.stdout


def weekly_totals(days):
    by_week = defaultdict(int)
    for day in days:
        date = dt.date.fromisoformat(day["date"])
        year, week, _ = date.isocalendar()
        by_week[(year, week)] += int(day.get("contributionCount", 0))
    return [by_week[key] for key in sorted(by_week)]


def pair_weeks(weeks):
    values = list(weeks)
    return [sum(values[i:i + 2]) for i in range(0, len(values), 2)]


def render_growth_ascii(weeks):
    bins = pair_weeks(list(weeks)[-53:])
    if not bins:
        bins = [0]
    max_value = max(bins) or 1
    levels = []
    for value in bins:
        if value <= 0:
            levels.append(0)
            continue
        ratio = math.sqrt(value / max_value)
        levels.append(max(1, min(4, math.ceil(ratio * 4))))

    height = 4
    width = len(levels) * 3 + 1
    canvas = [[" " for _ in range(width)] for _ in range(height)]
    base = ["─" for _ in range(width)]

    for index, level in enumerate(levels):
        center = 2 + index * 3
        if level == 0:
            continue
        top = height - level
        if center - 1 >= 0:
            canvas[top][center - 1] = "╱"
        if center + 1 < width:
            canvas[top][center + 1] = "╲"
        for row in range(top + 1, height):
            canvas[row][center] = "│"
        base[center] = "┴"

    lines = ["".join(row).rstrip() for row in canvas]
    lines.append("".join(base).rstrip())
    return "\n".join(lines)


def fmt_date(value):
    if not value:
        return "—"
    return value[:10].replace("-", ".")


def fmt_time(value):
    if not value or "T" not in value:
        return "--:--"
    return value.split("T", 1)[1][:5]


def clamp(value, limit=84):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def safe_inline(value):
    return str(value or "").replace("`", "'").replace("\n", " ").strip()


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
    for repo in sorted(raw_repos, key=lambda item: item.get("pushed_at") or "", reverse=True):
        repos.append({
            "name": repo.get("name", "—"),
            "url": repo.get("html_url", ""),
            "description": repo.get("description") or CURATED_DESCRIPTIONS.get(repo.get("name", ""), ""),
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
        "sha": "—",
        "date": "",
        "message": "no public commit found",
        "repo": "—",
        "url": f"https://github.com/{LOGIN}?tab=repositories",
    }

    repo_lookup = {repo["name"]: repo for repo in repos}
    active_repo = dict(repo_lookup.get(latest["repo"], {}))
    if not active_repo:
        active_repo = {
            "name": latest["repo"],
            "url": f"https://github.com/{LOGIN}?tab=repositories",
            "description": "",
            "language": "",
            "stars": 0,
            "fork": False,
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
        "recent_commits": recent_commits,
        "generated_at": dt.datetime.now(dt.timezone.utc).date().isoformat(),
    }


def render_now(snapshot):
    repo = snapshot["active_repo"]
    commit = snapshot["latest_commit"]
    kind = "FORK" if repo.get("fork") else "ORIGINAL"
    language = (repo.get("language") or "NO PRIMARY LANGUAGE").upper()
    description = repo.get("description") or "latest public work, selected from the newest authored commit."
    return f'''## NOW / 001

### [{repo["name"]}]({repo["url"]})

`PUBLIC / {kind}` · `{language}` · `★ {repo.get("stars", 0)}`

{description}

**latest public commit**<br>
[`{commit["sha"]}`]({commit["url"]}) / `{fmt_date(commit["date"])}` / `{fmt_time(commit["date"])}`<br>
{safe_inline(commit["message"])}'''


def render_growth(snapshot):
    weeks = weekly_totals(snapshot.get("contribution_days", []))
    plant = render_growth_ascii(weeks)
    return f'''## GROWTH / 365D

```text
{plant}
```

`{snapshot["contributions"]:03d} / CONTRIBUTIONS`<br>
`{snapshot["public_repos"]:02d} / PUBLIC REPOS`<br>
`{snapshot["stars"]:02d} / PUBLIC STARS`

<sub>MOSS / 53 WEEKS / GENERATED FROM GITHUB CONTRIBUTION COUNTS</sub>'''


def render_work(snapshot):
    blocks = ["## WORK / PUBLIC"]
    for index, repo in enumerate(snapshot.get("repos", []), start=1):
        kind = "FORK" if repo.get("fork") else "ORIGINAL"
        language = (repo.get("language") or "NO PRIMARY LANGUAGE").upper()
        description = repo.get("description") or "public repository."
        blocks.append(
            f'''### PUBLIC / {index:02d} — [{repo["name"]}]({repo["url"]})

`{language}` · `{kind}` · `★ {repo.get("stars", 0)}` · `PUSH {fmt_date(repo.get("pushed_at", ""))}`

{description}'''
        )
    return "\n\n".join(blocks)


def render_log(snapshot):
    lines = []
    for commit in snapshot.get("recent_commits", []):
        lines.append(f'{fmt_date(commit["date"])} {fmt_time(commit["date"])}  {commit["sha"]:<7}  {commit["repo"]}')
        lines.append(f'  {clamp(commit["message"], 78)}')
        lines.append("")
    if not lines:
        lines = ["no public authored commits found"]
    return "## LOG / RECENT\n\n```text\n" + "\n".join(lines).rstrip() + "\n```"


def render_footer(snapshot):
    return (
        f'<sub>SOURCE / GITHUB GRAPHQL + REST · REFRESH / 6H · '
        f'UPDATED / {fmt_date(snapshot["generated_at"])} · CAM / 07</sub>'
    )


def render_readme(snapshot):
    template = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "{{NOW}}": render_now(snapshot),
        "{{GROWTH}}": render_growth(snapshot),
        "{{WORK}}": render_work(snapshot),
        "{{LOG}}": render_log(snapshot),
        "{{FOOTER}}": render_footer(snapshot),
    }
    for marker, value in replacements.items():
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
        "recent_commits": snapshot.get("recent_commits", []),
        "generated_at": snapshot.get("generated_at"),
        "moss_weeks": weekly_totals(snapshot.get("contribution_days", []))[-53:],
    }


def main():
    snapshot = fetch_snapshot()
    README.write_text(render_readme(snapshot), encoding="utf-8")
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot_for_disk(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {README.relative_to(ROOT)} and {SNAPSHOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
