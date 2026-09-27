import importlib.util
import pathlib
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_profile", ROOT / "scripts" / "render_profile.py")
mod = importlib.util.module_from_spec(SPEC)


def sample_snapshot():
    days = []
    for index in range(70):
        days.append({
            "date": f"2026-{7 + (index // 28):02d}-{1 + (index % 28):02d}",
            "contributionCount": (index * 3) % 8,
        })
    return {
        "login": "caml07",
        "public_repos": 5,
        "stars": 1,
        "contributions": 308,
        "contribution_days": days,
        "active_repo": {
            "name": "OSF-Atlas",
            "url": "https://github.com/caml07/OSF-Atlas",
            "description": "An evidence-first archive of Obsidian Soundfields.",
            "language": "Python",
            "stars": 0,
            "fork": False,
        },
        "latest_commit": {
            "sha": "45c453b",
            "date": "2026-09-27T00:19:00-06:00",
            "message": "docs: expand human discovery guide",
            "repo": "OSF-Atlas",
            "url": "https://github.com/caml07/OSF-Atlas/commit/45c453b",
        },
        "repos": [
            {
                "name": "OSF-Atlas",
                "url": "https://github.com/caml07/OSF-Atlas",
                "description": "An evidence-first archive of Obsidian Soundfields.",
                "language": "Python",
                "stars": 0,
                "fork": False,
                "pushed_at": "2026-09-27T00:19:00Z",
            },
            {
                "name": "wayvibes-tui",
                "url": "https://github.com/caml07/wayvibes-tui",
                "description": "A native Linux terminal interface for WayVibes.",
                "language": "Rust",
                "stars": 1,
                "fork": False,
                "pushed_at": "2026-08-26T06:03:02Z",
            },
        ],
        "languages": {"QML": 4200, "Python": 2900, "Rust": 1800, "TypeScript": 1100},
        "recent_commits": [
            {
                "sha": "45c453b",
                "date": "2026-09-27T00:19:00-06:00",
                "message": "docs: expand human discovery guide",
                "repo": "OSF-Atlas",
                "url": "https://github.com/caml07/OSF-Atlas/commit/45c453b",
            }
        ],
        "generated_at": "2026-09-27",
    }


class ProfileRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SPEC.loader.exec_module(mod)

    def test_weekly_totals_group_contributions_by_week(self):
        days = [
            {"date": "2026-09-20", "contributionCount": 1},
            {"date": "2026-09-21", "contributionCount": 2},
            {"date": "2026-09-27", "contributionCount": 3},
        ]
        self.assertEqual(mod.weekly_totals(days), [1, 5])

    def test_language_percentages_sum_to_100(self):
        rows = mod.language_percentages({"QML": 4200, "Python": 2900, "Rust": 1800, "TypeScript": 1100})
        self.assertEqual(sum(row[2] for row in rows), 100)
        self.assertEqual(rows[0][0], "QML")

    def test_garden_svg_is_valid_and_data_driven(self):
        snapshot = sample_snapshot()
        active = mod.render_garden_svg(snapshot)
        quiet_snapshot = sample_snapshot()
        quiet_snapshot["contribution_days"] = [
            {"date": day["date"], "contributionCount": 0}
            for day in quiet_snapshot["contribution_days"]
        ]
        quiet = mod.render_garden_svg(quiet_snapshot)
        ET.fromstring(active)
        self.assertNotEqual(active, quiet)
        self.assertIn("GARDEN / 365D", active)
        self.assertIn("#91b36b", active.lower())
        self.assertIn("data-week=", active)
        self.assertNotIn("gradient", active.lower())

    def test_mixer_svg_is_valid_and_has_language_channels(self):
        svg = mod.render_mixer_svg(sample_snapshot())
        ET.fromstring(svg)
        for language in ("QML", "PYTHON", "RUST", "TYPESCRIPT"):
            self.assertIn(language, svg.upper())
        self.assertIn("MIXER / LANGUAGES", svg)
        self.assertIn("#e1a33b", svg.lower())

    def test_telemetry_svg_is_valid_and_contains_real_metrics(self):
        svg = mod.render_telemetry_svg(sample_snapshot())
        ET.fromstring(svg)
        for value in ("308", "05", "01", "45c453b", "OSF-ATLAS"):
            self.assertIn(value, svg)
        self.assertIn("TELEMETRY", svg)

    def test_readme_is_tui_document_with_small_widgets_not_one_big_svg(self):
        readme = mod.render_readme(sample_snapshot())
        for heading in ("CAM / 07", "DECK / NOW", "BANK / PUBLIC", "LOG / RECENT", "LOCAL / OFF—REPO"):
            self.assertIn(heading, readme)
        for widget in ("widgets/telemetry.svg", "widgets/garden.svg", "widgets/mixer.svg"):
            self.assertIn(widget, readme)
        self.assertNotIn("profile.svg", readme)
        self.assertNotIn("GROWTH / 365D", readme)
        self.assertIn("▌ ● 01", readme)

    def test_disk_snapshot_keeps_aggregate_growth_and_languages_not_raw_days(self):
        public = mod.snapshot_for_disk(sample_snapshot())
        self.assertNotIn("contribution_days", public)
        self.assertIn("moss_weeks", public)
        self.assertEqual(public["languages"]["QML"], 4200)


if __name__ == "__main__":
    unittest.main()
