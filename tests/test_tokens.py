import os
import tempfile
import unittest

from fixtures import make_evidence, style_frequency
from tokens import (build_tokens, cluster_colors, color_distance,
                    detect_base_unit, parse_color, to_css, to_hex)


class TestColorParsing(unittest.TestCase):
    def test_parses_every_form_the_browser_emits(self):
        self.assertEqual(parse_color("rgb(1, 2, 3)"), (1, 2, 3, 1.0))
        self.assertEqual(parse_color("rgba(1, 2, 3, 0.5)"), (1, 2, 3, 0.5))
        self.assertEqual(parse_color("rgb(1 2 3 / 50%)"), (1, 2, 3, 0.5))
        self.assertEqual(parse_color("#0a0b0c"), (10, 11, 12, 1.0))
        self.assertEqual(parse_color("#abc"), (170, 187, 204, 1.0))
        self.assertEqual(parse_color("#0a0b0cff"), (10, 11, 12, 1.0))

    def test_rounds_fractional_channels(self):
        self.assertEqual(parse_color("rgb(0.6, 1.4, 2.5)"), (1, 1, 2, 1.0))

    def test_returns_none_for_non_colors(self):
        for v in ("transparent", "currentColor", "", "var(--x)", "linear-gradient(red, blue)"):
            self.assertIsNone(parse_color(v), v)

    def test_hex_round_trip_keeps_alpha_visible(self):
        self.assertEqual(to_hex((255, 0, 0, 1.0)), "#ff0000")
        self.assertEqual(to_hex((255, 0, 0, 0.5)), "#ff0000@0.5")


class TestClustering(unittest.TestCase):
    def test_distance_is_zero_for_identical_and_large_across_alpha(self):
        self.assertEqual(color_distance((1, 2, 3, 1.0), (1, 2, 3, 1.0)), 0.0)
        self.assertEqual(color_distance((1, 2, 3, 1.0), (1, 2, 3, 0.2)), 999.0)

    def test_merges_near_duplicates_and_keeps_distinct_colors_apart(self):
        obs = [
            ((17, 17, 17, 1.0), 40, {"EV-0001"}),
            ((18, 18, 18, 1.0), 5, {"EV-0002"}),   # anti-aliasing twin
            ((230, 20, 20, 1.0), 12, {"EV-0001"}),  # genuinely different
        ]
        clusters = cluster_colors(obs, threshold=12.0)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0]["count"], 45)
        self.assertEqual(clusters[0]["evidence"], {"EV-0001", "EV-0002"})
        self.assertEqual(clusters[1]["count"], 12)

    def test_clustering_is_deterministic(self):
        obs = [((i * 40 % 255, 10, 10, 1.0), 7, {"EV-0001"}) for i in range(6)]
        a = [to_hex(c["rgba"]) for c in cluster_colors(list(obs))]
        b = [to_hex(c["rgba"]) for c in cluster_colors(list(reversed(obs)))]
        self.assertEqual(a, b)


class TestScales(unittest.TestCase):
    def test_finds_the_largest_unit_that_explains_the_spacing(self):
        self.assertEqual(detect_base_unit([(8, 10), (16, 20), (24, 5)]), (8, 1.0))
        self.assertEqual(detect_base_unit([(4, 10), (12, 20), (20, 5)]), (4, 1.0))

    def test_tolerates_a_minority_of_off_grid_values(self):
        unit, coverage = detect_base_unit([(4, 100), (12, 100), (7, 5)])
        self.assertEqual(unit, 4)
        self.assertGreater(coverage, 0.8)

    def test_reports_a_poor_fit_rather_than_claiming_a_grid(self):
        unit, coverage = detect_base_unit([(3, 5), (7, 5), (11, 5), (13, 5)])
        self.assertEqual(unit, 1)
        self.assertEqual(detect_base_unit([]), (1, 0.0))


class TestBuildTokens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "evidence")

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_token_cites_the_evidence_it_came_from(self):
        make_evidence(self.root)
        t = build_tokens(self.root)
        rows = t["colors"]["text"] + t["spacing"]["scale"] + t["typography"]["scale"]
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(row["evidence"], f"{row['token']} cites nothing")
            for ev in row["evidence"]:
                self.assertRegex(ev, r"^EV-\d{4}$")

    def test_derives_the_scales_present_in_the_evidence(self):
        make_evidence(self.root)
        t = build_tokens(self.root)
        self.assertEqual(t["spacing"]["base_unit_px"], 8)
        self.assertEqual([r["value"] for r in t["typography"]["scale"]], ["16px", "24px", "32px"])
        self.assertEqual(t["typography"]["median_step_ratio"], 1.417)
        self.assertEqual(t["summary"]["type_steps"], 3)

    def test_orders_colors_by_observed_usage(self):
        make_evidence(self.root, frequency=style_frequency(
            colors={"rgb(10, 10, 10)": 3, "rgb(200, 0, 0)": 50}))
        t = build_tokens(self.root)
        self.assertEqual(t["colors"]["text"][0]["value"], "#c80000")
        self.assertEqual(t["colors"]["text"][0]["usage"], 50)

    def test_refuses_when_there_is_no_style_evidence(self):
        from ledger import Ledger
        Ledger(self.root).init("https://target.test/")
        with self.assertRaises(SystemExit):
            build_tokens(self.root)

    def test_css_output_declares_every_colour_token(self):
        make_evidence(self.root)
        css = to_css(build_tokens(self.root))
        self.assertIn(":root {", css)
        self.assertIn("--text-1:", css)
        self.assertIn("--space-8:", css)
        self.assertNotIn("@", css.split("--text-1:")[1].split(";")[0])


if __name__ == "__main__":
    unittest.main()
