import os
import tempfile
import unittest

from fixtures import make_evidence, style_frequency
from parity import WEIGHTS, run


class TestParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = os.path.join(self.tmp.name, "target")
        self.c = os.path.join(self.tmp.name, "clone")

    def tearDown(self):
        self.tmp.cleanup()

    def test_weights_sum_to_100(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)

    def test_identical_evidence_scores_100(self):
        make_evidence(self.t)
        make_evidence(self.c)
        report = run(self.t, self.c)
        self.assertEqual(report["overall"], 100.0)
        for dim in WEIGHTS:
            self.assertEqual(report["scores"][dim], 100.0, dim)

    def test_a_wrong_palette_lowers_only_the_palette_score(self):
        make_evidence(self.t)
        make_evidence(self.c, frequency=style_frequency(
            colors={"rgb(200, 0, 0)": 40, "rgb(0, 200, 0)": 10}))
        report = run(self.t, self.c)
        self.assertEqual(report["details"]["palette"]["per_role"]["text"], 0.0)
        self.assertLess(report["scores"]["palette"], 100.0)
        self.assertEqual(report["scores"]["spacing"], 100.0)
        self.assertLess(report["overall"], 100.0)

    def test_near_identical_colours_still_count_as_matched(self):
        make_evidence(self.t)
        make_evidence(self.c, frequency=style_frequency(
            colors={"rgb(18, 18, 18)": 40, "rgb(101, 101, 101)": 10}))
        self.assertEqual(run(self.t, self.c)["scores"]["palette"], 100.0)

    def test_a_missing_spacing_step_is_named_in_the_report(self):
        make_evidence(self.t)
        make_evidence(self.c, frequency=style_frequency(
            spaces={"padding-top": {"8px": 12}, "gap": {"8px": 4}}))
        report = run(self.t, self.c)
        missing = [m["value"] for m in report["details"]["spacing"]["unmatched_target_steps"]]
        self.assertIn("16px", missing)
        self.assertIn("24px", missing)
        self.assertLess(report["scores"]["spacing"], 100.0)

    def test_a_different_base_unit_is_reported(self):
        make_evidence(self.t)
        make_evidence(self.c, frequency=style_frequency(
            spaces={"padding-top": {"5px": 12, "10px": 9}, "gap": {"15px": 4}}))
        detail = run(self.t, self.c)["details"]["spacing"]
        self.assertEqual(detail["target_base_unit_px"], 8)
        self.assertEqual(detail["clone_base_unit_px"], 5)
        self.assertFalse(detail["base_unit_match"])

    def test_different_structure_lowers_the_structure_score(self):
        make_evidence(self.t)
        make_evidence(self.c, landmarks=[{"tag": "div", "role": None, "label": None}])
        report = run(self.t, self.c)
        self.assertLess(report["scores"]["structure"], 100.0)

    def test_mismatched_viewports_are_reported_not_scored_as_perfect(self):
        make_evidence(self.t, viewport="1440")
        make_evidence(self.c, viewport="390")
        report = run(self.t, self.c)
        self.assertEqual(report["scores"]["structure"], 0.0)
        self.assertIn("no shared viewport", report["details"]["structure"]["error"])

    def test_refuses_an_unsound_ledger(self):
        make_evidence(self.t)
        make_evidence(self.c)
        with open(os.path.join(self.t, "raw", "styles-1440.json"), "w", encoding="utf-8") as fh:
            fh.write("{}")
        with self.assertRaises(SystemExit):
            run(self.t, self.c)


if __name__ == "__main__":
    unittest.main()
