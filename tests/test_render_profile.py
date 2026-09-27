import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_profile", ROOT / "scripts" / "render_profile.py")
mod = importlib.util.module_from_spec(SPEC)


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

    def test_growth_ascii_is_data_driven(self):
        quiet = mod.render_growth_ascii([0] * 53)
        active = mod.render_growth_ascii([0] * 48 + [1, 4, 9, 16, 25])
        self.assertNotEqual(quiet, active)
        self.assertIn("╱", active)
        self.assertIn("╲", active)
        self.assertIn("─", active)
        self.assertNotIn("<svg", active)

    def test_pair_weeks_compresses_year_without_losing_total(self):
        weeks = list(range(1, 54))
        bins = mod.pair_weeks(weeks)
        self.assertEqual(len(bins), 27)
        self.assertEqual(sum(bins), sum(weeks))

    def test_render_readme_is_long_modular_and_not_svg_based(self):
        snapshot = {
            "login": "caml07",
            "public_repos": 5,
            "stars": 1,
            "contributions": 305,
            "contribution_days": [
                {"date": "2026-09-20", "contributionCount": 1},
                {"date": "2026-09-21", "contributionCount": 2},
            ],
            "active_repo": {
                "name": "OSF-Atlas",
                "url": "https://github.com/caml07/OSF-Atlas",
                "description": "Evidence-first archive",
                "language": None,
                "stars": 0,
                "fork": False,
            },
            "latest_commit": {
                "sha": "6d971f7",
                "date": "2026-09-26T23:50:26-06:00",
                "message": "docs: pause corpus for semantic review",
                "repo": "OSF-Atlas",
                "url": "https://github.com/caml07/OSF-Atlas/commit/6d971f7",
            },
            "repos": [
                {
                    "name": "wayvibes-tui",
                    "url": "https://github.com/caml07/wayvibes-tui",
                    "description": "A native Linux terminal interface for WayVibes.",
                    "language": "Rust",
                    "stars": 1,
                    "fork": False,
                    "pushed_at": "2026-08-26T06:03:02Z",
                }
            ],
            "recent_commits": [
                {
                    "sha": "6d971f7",
                    "date": "2026-09-26T23:50:26-06:00",
                    "message": "docs: pause corpus for semantic review",
                    "repo": "OSF-Atlas",
                    "url": "https://github.com/caml07/OSF-Atlas/commit/6d971f7",
                }
            ],
            "generated_at": "2026-09-27",
        }
        readme = mod.render_readme(snapshot)
        for heading in ("CAM / 07", "NOW / 001", "GROWTH / 365D", "WORK / PUBLIC", "LOG / RECENT", "OFF—REPO"):
            self.assertIn(heading, readme)
        self.assertIn("THINGS GROW HERE.", readme)
        self.assertIn("6d971f7", readme)
        self.assertIn("wayvibes-tui", readme)
        self.assertNotIn("profile.svg", readme)
        self.assertNotIn("<picture>", readme)

    def test_disk_snapshot_does_not_publish_raw_daily_activity(self):
        snapshot = {
            "login": "caml07",
            "public_repos": 5,
            "stars": 1,
            "contributions": 305,
            "contribution_days": [{"date": "2026-09-21", "contributionCount": 2}],
            "active_repo": {"name": "OSF-Atlas"},
            "latest_commit": {"sha": "abcdef0"},
            "repos": [],
            "recent_commits": [],
            "generated_at": "2026-09-27",
        }
        public = mod.snapshot_for_disk(snapshot)
        self.assertNotIn("contribution_days", public)
        self.assertEqual(public["moss_weeks"], [2])


if __name__ == "__main__":
    unittest.main()
