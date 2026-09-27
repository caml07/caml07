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

    def test_vine_is_deterministic_and_stays_inside_band(self):
        points, leaves = mod.build_vine([0, 2, 8, 1, 12], width=500, y=220, amplitude=18)
        self.assertEqual(points, mod.build_vine([0, 2, 8, 1, 12], width=500, y=220, amplitude=18)[0])
        self.assertTrue(all(202 <= p[1] <= 238 for p in points))
        self.assertGreaterEqual(len(leaves), 2)

    def test_escape_xml(self):
        self.assertEqual(mod.escape_xml('a & <b> "c"'), 'a &amp; &lt;b&gt; &quot;c&quot;')

    def test_disk_snapshot_does_not_publish_raw_daily_activity(self):
        snapshot = {
            "login": "caml07",
            "public_repos": 5,
            "stars": 1,
            "contributions": 303,
            "contribution_days": [{"date": "2026-09-21", "contributionCount": 2}],
            "active_repo": "OSF-Atlas",
            "active_repo_url": "https://github.com/caml07/OSF-Atlas",
            "latest_commit_sha": "abcdef0",
            "latest_commit_date": "2026-09-26T00:00:00Z",
            "latest_commit_message": "test",
            "generated_at": "2026-09-27",
        }
        public = mod.snapshot_for_disk(snapshot)
        self.assertNotIn("contribution_days", public)
        self.assertEqual(public["moss_weeks"], [2])

    def test_render_contains_verifiable_fields(self):
        snapshot = {
            "login": "caml07",
            "public_repos": 5,
            "stars": 1,
            "contributions": 289,
            "contribution_days": [
                {"date": "2026-09-20", "contributionCount": 1},
                {"date": "2026-09-21", "contributionCount": 2},
            ],
            "active_repo": "OSF-Atlas",
            "active_repo_url": "https://github.com/caml07/OSF-Atlas",
            "latest_commit_sha": "f002764",
            "latest_commit_date": "2026-09-27T05:11:09Z",
            "latest_commit_message": "Initial commit",
            "generated_at": "2026-09-27T06:00:00Z",
        }
        svg = mod.render_svg(snapshot)
        for value in ("CAM / 07", "OSF-ATLAS", "289", "f002764", "THINGS GROW HERE"):
            self.assertIn(value, svg)
        self.assertNotIn("PROFILE VIEWS", svg)


if __name__ == "__main__":
    unittest.main()
