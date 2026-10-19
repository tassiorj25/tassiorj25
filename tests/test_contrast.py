import unittest

from fixtures import TOOLS  # noqa: F401  (puts tools/ on sys.path)

from contrast import check, contrast_ratio, grade, relative_luminance


class TestContrastMath(unittest.TestCase):
    def test_matches_the_wcag_reference_values(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0, 1), (255, 255, 255, 1)), 21.0, places=2)
        self.assertAlmostEqual(contrast_ratio((255, 255, 255, 1), (255, 255, 255, 1)), 1.0, places=2)
        # #767676 on white is the canonical "just passes AA" value: 4.54
        self.assertAlmostEqual(contrast_ratio((118, 118, 118, 1), (255, 255, 255, 1)), 4.54, places=2)

    def test_is_symmetric(self):
        a = contrast_ratio((20, 40, 60, 1), (240, 240, 240, 1))
        b = contrast_ratio((240, 240, 240, 1), (20, 40, 60, 1))
        self.assertAlmostEqual(a, b, places=6)

    def test_luminance_endpoints(self):
        self.assertAlmostEqual(relative_luminance((0, 0, 0)), 0.0, places=6)
        self.assertAlmostEqual(relative_luminance((255, 255, 255)), 1.0, places=6)

    def test_composites_a_translucent_foreground_before_measuring(self):
        solid = contrast_ratio((0, 0, 0, 1), (255, 255, 255, 1))
        half = contrast_ratio((0, 0, 0, 0.5), (255, 255, 255, 1))
        self.assertLess(half, solid)
        self.assertAlmostEqual(half, 3.95, places=2)

    def test_grades_at_the_spec_boundaries(self):
        self.assertEqual(grade(21.0), "AAA")
        self.assertEqual(grade(7.0), "AAA")
        self.assertEqual(grade(4.5), "AA")
        self.assertEqual(grade(4.49), "AA-large-only")
        self.assertEqual(grade(3.0), "AA-large-only")
        self.assertEqual(grade(2.99), "fail")


class TestCheck(unittest.TestCase):
    def _tokens(self, text, surface):
        return {"colors": {
            "text": [{"token": "--text-1", "value": text, "usage": 10, "evidence": ["EV-0001"]}],
            "surface": [{"token": "--surface-1", "value": surface, "usage": 5, "evidence": ["EV-0001"]}],
        }}

    def test_reports_a_failing_pair_with_its_evidence(self):
        rows = check(self._tokens("#aaaaaa", "#ffffff"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["grade"], "fail")
        self.assertEqual(rows[0]["evidence"], ["EV-0001"])
        self.assertFalse(rows[0]["assumed_surface"])

    def test_falls_back_to_white_and_labels_the_assumption(self):
        tokens = {"colors": {
            "text": [{"token": "--text-1", "value": "#000000", "usage": 3, "evidence": ["EV-0001"]}],
            "surface": [{"token": "--surface-1", "value": "#ffffff@0.1", "usage": 9, "evidence": ["EV-0001"]}],
        }}
        rows = check(tokens)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["assumed_surface"])
        self.assertAlmostEqual(rows[0]["ratio"], 21.0, places=1)

    def test_min_usage_filters_out_incidental_colours(self):
        tokens = self._tokens("#aaaaaa", "#ffffff")
        tokens["colors"]["text"][0]["usage"] = 2
        self.assertEqual(check(tokens, min_usage=5), [])

    def test_sorts_worst_first(self):
        tokens = {"colors": {
            "text": [
                {"token": "--text-1", "value": "#000000", "usage": 1, "evidence": []},
                {"token": "--text-2", "value": "#eeeeee", "usage": 1, "evidence": []},
            ],
            "surface": [{"token": "--surface-1", "value": "#ffffff", "usage": 1, "evidence": []}],
        }}
        rows = check(tokens)
        self.assertEqual(rows[0]["text_value"], "#eeeeee")
        self.assertLess(rows[0]["ratio"], rows[1]["ratio"])


if __name__ == "__main__":
    unittest.main()
