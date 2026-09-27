#!/usr/bin/env python3
import datetime as dt
import html
import json
import math
import pathlib
import subprocess
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "profile.svg"
OUT_MOBILE = ROOT / "assets" / "profile-mobile.svg"
SNAPSHOT = ROOT / "assets" / "profile-data.json"
LOGIN = "caml07"
PROFILE_REPO = f"{LOGIN}/{LOGIN}"


def run_gh(*args):
    proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return proc.stdout


def escape_xml(value):
    return html.escape(str(value), quote=True)


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
        "api", "--paginate", "--slurp", f"users/{LOGIN}/repos?per_page=100&type=owner"
    ))
    repos = [
        repo for page in repo_pages for repo in page
        if not repo.get("private") and repo.get("full_name") != PROFILE_REPO
    ]

    commit_search = json.loads(run_gh(
        "api", "--method", "GET", "search/commits",
        "-f", f"q=author:{LOGIN}", "-f", "sort=committer-date", "-f", "order=desc", "-f", "per_page=50"
    ))
    latest = None
    for item in commit_search.get("items", []):
        repo = item.get("repository", {})
        if repo.get("private"):
            continue
        if repo.get("full_name") == PROFILE_REPO:
            continue
        latest = item
        break

    weeks = profile["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [day for week in weeks for day in week.get("contributionDays", [])]
    total = profile["contributionsCollection"]["contributionCalendar"]["totalContributions"]

    if latest:
        commit = latest["commit"]
        repo = latest["repository"]
        date = (commit.get("committer") or commit.get("author") or {}).get("date", "")
        message = (commit.get("message") or "").splitlines()[0].strip()
        active_repo = repo.get("name") or repo.get("full_name", "").split("/")[-1]
        active_url = repo.get("html_url") or f"https://github.com/{repo.get('full_name', '')}"
        sha = latest.get("sha", "")[:7]
    else:
        date = ""
        message = "no public commit found"
        active_repo = "—"
        active_url = f"https://github.com/{LOGIN}?tab=repositories"
        sha = "—"

    return {
        "login": LOGIN,
        "public_repos": len(repos),
        "stars": sum(int(repo.get("stargazers_count", 0)) for repo in repos),
        "contributions": int(total),
        "contribution_days": days,
        "active_repo": active_repo,
        "active_repo_url": active_url,
        "latest_commit_sha": sha,
        "latest_commit_date": date,
        "latest_commit_message": message,
        "generated_at": dt.datetime.now(dt.timezone.utc).date().isoformat(),
    }


def weekly_totals(days):
    by_week = defaultdict(int)
    for day in days:
        date = dt.date.fromisoformat(day["date"])
        year, week, _ = date.isocalendar()
        by_week[(year, week)] += int(day.get("contributionCount", 0))
    return [by_week[key] for key in sorted(by_week)]


def build_vine(weeks, width=820, y=226, amplitude=18):
    if not weeks:
        return [(40.0, float(y)), (40.0 + width, float(y))], []
    max_value = max(max(weeks), 1)
    step = width / max(len(weeks) - 1, 1)
    points = []
    leaves = []
    for idx, value in enumerate(weeks):
        x = 40 + idx * step
        strength = math.sqrt(value / max_value)
        # Quiet weeks stay near the seam; active weeks push the vine upward.
        variation = math.sin(idx * 1.73) * amplitude * 0.16
        yy = y - (strength * amplitude * 0.82) + variation
        yy = max(y - amplitude, min(y + amplitude, yy))
        points.append((round(x, 2), round(yy, 2)))
        if value >= max(2, math.ceil(max_value * 0.24)):
            side = -1 if idx % 2 else 1
            leaves.append((round(x, 2), round(yy, 2), side, strength))
    return points, leaves


def smooth_path(points):
    if len(points) < 2:
        return ""
    d = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for idx in range(1, len(points)):
        x0, y0 = points[idx - 1]
        x1, y1 = points[idx]
        mx = (x0 + x1) / 2
        d.append(f"Q {mx:.2f} {y0:.2f} {x1:.2f} {y1:.2f}")
    return " ".join(d)


def fmt_date(value):
    if not value:
        return "—"
    return value[:10].replace("-", ".")


def clamp_text(value, limit):
    value = str(value).strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def render_svg(snapshot):
    weeks = weekly_totals(snapshot.get("contribution_days", []))[-53:]
    points, leaves = build_vine(weeks)
    vine = smooth_path(points)
    max_week = max(weeks or [1])

    leaf_nodes = []
    for x, yy, side, strength in leaves:
        ry = 2.1 + strength * 2.4
        rx = 4.2 + strength * 3.0
        cy = yy + side * (5.5 + strength * 3.5)
        rotate = -28 if side < 0 else 28
        leaf_nodes.append(
            f'<ellipse cx="{x:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'transform="rotate({rotate} {x:.2f} {cy:.2f})" fill="#6f8669" opacity="{0.28 + strength * 0.34:.2f}" />'
        )

    # Moss thickens locally according to contribution density without becoming a chart.
    moss_nodes = []
    for idx, (x, yy) in enumerate(points):
        if idx >= len(weeks):
            break
        value = weeks[idx]
        if not value:
            continue
        density = math.sqrt(value / max_week)
        radius = 1.3 + 2.8 * density
        moss_nodes.append(
            f'<circle cx="{x:.2f}" cy="{yy:.2f}" r="{radius:.2f}" fill="#536b54" opacity="{0.18 + density * 0.28:.2f}" />'
        )

    active_repo = escape_xml(snapshot.get("active_repo", "—").upper())
    sha = escape_xml(snapshot.get("latest_commit_sha", "—"))
    message = escape_xml(clamp_text(snapshot.get("latest_commit_message", ""), 46))
    commit_date = escape_xml(fmt_date(snapshot.get("latest_commit_date", "")))
    generated_date = escape_xml(fmt_date(snapshot.get("generated_at", "")))
    repos = int(snapshot.get("public_repos", 0))
    stars = int(snapshot.get("stars", 0))
    contributions = int(snapshot.get("contributions", 0))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300" role="img" aria-labelledby="title desc">
  <title id="title">CAM / 07 — GitHub profile telemetry</title>
  <desc id="desc">Compact profile plate showing public repositories, stars, contributions, active repository, and latest public commit for caml07.</desc>
  <defs>
    <pattern id="grain" width="74" height="74" patternUnits="userSpaceOnUse">
      <circle cx="8" cy="14" r="0.7" fill="#d6dad4" opacity="0.035"/>
      <circle cx="39" cy="31" r="0.55" fill="#d6dad4" opacity="0.025"/>
      <circle cx="66" cy="58" r="0.8" fill="#d6dad4" opacity="0.025"/>
      <path d="M18 62h5 M52 9h3" stroke="#d6dad4" stroke-width="0.5" opacity="0.018"/>
    </pattern>
    <style>
      .sans {{ font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .mono {{ font-family: ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace; }}
      .caps {{ letter-spacing: 0.12em; }}
      .tabular {{ font-variant-numeric: tabular-nums; }}
    </style>
  </defs>

  <rect width="900" height="300" fill="#0e110f"/>
  <rect x="0.5" y="0.5" width="899" height="299" fill="none" stroke="#2a302b"/>
  <rect width="900" height="300" fill="url(#grain)"/>

  <g class="sans">
    <text x="38" y="65" fill="#d6dad4" font-size="40" font-weight="640" letter-spacing="-1.2">CAM <tspan fill="#6f8669">/</tspan> 07</text>
    <text x="40" y="92" fill="#899188" font-size="10" font-weight="600" class="caps">LITTLE ENGINEER</text>
    <text x="40" y="113" fill="#637064" font-size="12">THINGS GROW HERE.</text>
  </g>

  <line x1="556" y1="36" x2="556" y2="184" stroke="#252b26" stroke-width="1"/>

  <g class="mono tabular">
    <text x="594" y="47" fill="#657066" font-size="9" class="caps">ACTIVE / 001</text>
    <text x="594" y="78" fill="#d6dad4" font-size="20" font-weight="700">{active_repo}</text>
    <text x="594" y="103" fill="#8b938b" font-size="10">{sha}  /  {commit_date}</text>
    <text x="594" y="126" fill="#667067" font-size="10">{message}</text>
  </g>

  <g class="mono tabular">
    <text x="40" y="179" fill="#d6dad4" font-size="18" font-weight="700">{repos:02d}</text>
    <text x="40" y="195" fill="#707970" font-size="8" class="caps">PUBLIC REPOS</text>

    <text x="184" y="179" fill="#d6dad4" font-size="18" font-weight="700">{stars:02d}</text>
    <text x="184" y="195" fill="#707970" font-size="8" class="caps">STARS</text>

    <text x="303" y="179" fill="#d6dad4" font-size="18" font-weight="700">{contributions:03d}</text>
    <text x="303" y="195" fill="#707970" font-size="8" class="caps">CONTRIB. / 365D</text>
  </g>

  <line x1="40" y1="226" x2="860" y2="226" stroke="#232924" stroke-width="1"/>
  <path d="{vine}" fill="none" stroke="#526653" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" opacity="0.78"/>
  {''.join(moss_nodes)}
  {''.join(leaf_nodes)}

  <g class="mono tabular" font-size="7.5" fill="#5f685f">
    <text x="40" y="275" class="caps">SOURCE / GITHUB GRAPHQL + REST</text>
    <text x="860" y="275" text-anchor="end" class="caps">UPDATED / {generated_date}Z</text>
  </g>
</svg>'''


def render_svg_mobile(snapshot):
    weeks = weekly_totals(snapshot.get("contribution_days", []))[-53:]
    points, leaves = build_vine(weeks, width=440, y=340, amplitude=15)
    vine = smooth_path(points)
    max_week = max(weeks or [1])

    leaf_nodes = []
    for x, yy, side, strength in leaves:
        ry = 2.0 + strength * 2.0
        rx = 3.8 + strength * 2.7
        cy = yy + side * (5.0 + strength * 3.0)
        rotate = -28 if side < 0 else 28
        leaf_nodes.append(
            f'<ellipse cx="{x:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'transform="rotate({rotate} {x:.2f} {cy:.2f})" fill="#6f8669" opacity="{0.28 + strength * 0.34:.2f}" />'
        )

    moss_nodes = []
    for idx, (x, yy) in enumerate(points):
        if idx >= len(weeks):
            break
        value = weeks[idx]
        if not value:
            continue
        density = math.sqrt(value / max_week)
        radius = 1.2 + 2.4 * density
        moss_nodes.append(
            f'<circle cx="{x:.2f}" cy="{yy:.2f}" r="{radius:.2f}" fill="#536b54" opacity="{0.18 + density * 0.28:.2f}" />'
        )

    active_repo = escape_xml(snapshot.get("active_repo", "—").upper())
    sha = escape_xml(snapshot.get("latest_commit_sha", "—"))
    message = escape_xml(clamp_text(snapshot.get("latest_commit_message", ""), 42))
    commit_date = escape_xml(fmt_date(snapshot.get("latest_commit_date", "")))
    generated_date = escape_xml(fmt_date(snapshot.get("generated_at", "")))
    repos = int(snapshot.get("public_repos", 0))
    stars = int(snapshot.get("stars", 0))
    contributions = int(snapshot.get("contributions", 0))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="410" viewBox="0 0 520 410" role="img" aria-labelledby="title desc">
  <title id="title">CAM / 07 — GitHub profile telemetry</title>
  <desc id="desc">Compact mobile profile plate showing public repositories, stars, contributions, active repository, and latest public commit for caml07.</desc>
  <defs>
    <pattern id="grain" width="66" height="66" patternUnits="userSpaceOnUse">
      <circle cx="8" cy="14" r="0.7" fill="#d6dad4" opacity="0.035"/>
      <circle cx="35" cy="29" r="0.55" fill="#d6dad4" opacity="0.025"/>
      <circle cx="58" cy="52" r="0.8" fill="#d6dad4" opacity="0.025"/>
    </pattern>
    <style>
      .sans {{ font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
      .mono {{ font-family: ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", monospace; }}
      .caps {{ letter-spacing: 0.12em; }}
      .tabular {{ font-variant-numeric: tabular-nums; }}
    </style>
  </defs>
  <rect width="520" height="410" fill="#0e110f"/>
  <rect x="0.5" y="0.5" width="519" height="409" fill="none" stroke="#2a302b"/>
  <rect width="520" height="410" fill="url(#grain)"/>

  <g class="sans">
    <text x="28" y="57" fill="#d6dad4" font-size="34" font-weight="640" letter-spacing="-1">CAM <tspan fill="#6f8669">/</tspan> 07</text>
    <text x="30" y="82" fill="#899188" font-size="10" font-weight="600" class="caps">LITTLE ENGINEER</text>
    <text x="30" y="104" fill="#637064" font-size="11">THINGS GROW HERE.</text>
  </g>

  <g class="mono tabular">
    <text x="30" y="151" fill="#d6dad4" font-size="18" font-weight="700">{repos:02d}</text>
    <text x="30" y="168" fill="#707970" font-size="9" class="caps">PUBLIC</text>
    <text x="146" y="151" fill="#d6dad4" font-size="18" font-weight="700">{stars:02d}</text>
    <text x="146" y="168" fill="#707970" font-size="9" class="caps">STARS</text>
    <text x="247" y="151" fill="#d6dad4" font-size="18" font-weight="700">{contributions:03d}</text>
    <text x="247" y="168" fill="#707970" font-size="9" class="caps">CONTRIB. / 365D</text>
  </g>

  <line x1="30" y1="193" x2="490" y2="193" stroke="#252b26"/>

  <g class="mono tabular">
    <text x="30" y="224" fill="#657066" font-size="9" class="caps">ACTIVE / 001</text>
    <text x="30" y="258" fill="#d6dad4" font-size="22" font-weight="700">{active_repo}</text>
    <text x="30" y="284" fill="#8b938b" font-size="10">{sha}  /  {commit_date}</text>
    <text x="30" y="308" fill="#667067" font-size="10">{message}</text>
  </g>

  <line x1="40" y1="340" x2="480" y2="340" stroke="#232924"/>
  <path d="{vine}" fill="none" stroke="#526653" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" opacity="0.78"/>
  {''.join(moss_nodes)}
  {''.join(leaf_nodes)}

  <g class="mono tabular" font-size="8" fill="#5f685f">
    <text x="30" y="389" class="caps">SOURCE / GITHUB</text>
    <text x="490" y="389" text-anchor="end" class="caps">UPDATED / {generated_date}Z</text>
  </g>
</svg>'''

def snapshot_for_disk(snapshot):
    keys = (
        "login", "public_repos", "stars", "contributions", "active_repo",
        "active_repo_url", "latest_commit_sha", "latest_commit_date",
        "latest_commit_message", "generated_at",
    )
    data = {key: snapshot.get(key) for key in keys}
    data["moss_weeks"] = weekly_totals(snapshot.get("contribution_days", []))[-53:]
    return data


def main():
    snapshot = fetch_snapshot()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_svg(snapshot), encoding="utf-8")
    OUT_MOBILE.write_text(render_svg_mobile(snapshot), encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(snapshot_for_disk(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}, {OUT_MOBILE.relative_to(ROOT)}, and {SNAPSHOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
