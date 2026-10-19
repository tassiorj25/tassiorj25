import os
import tempfile
import unittest

from fixtures import TOOLS  # noqa: F401  (puts tools/ on sys.path)

import imgdiff

HAS_PIL = imgdiff.Image is not None
if HAS_PIL:
    from PIL import Image


@unittest.skipUnless(HAS_PIL, "Pillow not installed")
class TestImgDiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def solid(self, name, color, size=(400, 400)):
        path = os.path.join(self.tmp.name, name)
        Image.new("RGB", size, color).save(path)
        return path

    def half(self, name, top, bottom, size=(400, 400)):
        path = os.path.join(self.tmp.name, name)
        img = Image.new("RGB", size, top)
        for y in range(size[1] // 2, size[1]):
            for x in range(size[0]):
                img.putpixel((x, y), bottom)
        img.save(path)
        return path

    def test_identical_images_score_100(self):
        a = self.solid("a.png", (255, 255, 255))
        b = self.solid("b.png", (255, 255, 255))
        report, _ = imgdiff.compare(a, b, width=400)
        self.assertEqual(report["score"], 100.0)
        self.assertEqual(report["pixels_over_tolerance_pct"], 0.0)
        self.assertEqual(report["rms_delta"], 0.0)

    def test_half_the_canvas_differing_scores_50(self):
        a = self.solid("a.png", (255, 255, 255))
        c = self.half("c.png", (255, 255, 255), (0, 0, 0))
        report, _ = imgdiff.compare(a, c, width=400)
        self.assertEqual(report["pixels_over_tolerance_pct"], 50.0)
        self.assertEqual(report["score"], 50.0)
        # rms over half-black vs white is sqrt(0.5 * 255^2)
        self.assertAlmostEqual(report["rms_delta"], 180.31, places=1)

    def test_tolerance_absorbs_anti_aliasing(self):
        a = self.solid("a.png", (255, 255, 255))
        b = self.solid("b.png", (250, 250, 250))
        self.assertEqual(imgdiff.compare(a, b, width=400, tolerance=12)[0]["score"], 100.0)
        self.assertLess(imgdiff.compare(a, b, width=400, tolerance=2)[0]["score"], 100.0)

    def test_bands_locate_the_divergence(self):
        a = self.solid("a.png", (255, 255, 255))
        c = self.half("c.png", (255, 255, 255), (0, 0, 0))
        report, _ = imgdiff.compare(a, c, width=400, blocks=8)
        self.assertEqual(len(report["bands"]), 8)
        self.assertEqual(report["bands"][0]["pixels_over_tolerance_pct"], 0.0)
        self.assertEqual(report["bands"][7]["pixels_over_tolerance_pct"], 100.0)

    def test_a_shorter_clone_is_penalised_not_hidden(self):
        a = self.solid("a.png", (255, 255, 255), size=(400, 800))
        b = self.solid("b.png", (255, 255, 255), size=(400, 400))
        report, _ = imgdiff.compare(a, b, width=400)
        self.assertEqual(report["height_ratio"], 0.5)
        self.assertLess(report["score"], 100.0)
        self.assertGreater(report["score"], 90.0)

    def test_differing_widths_are_scaled_to_one_comparison_width(self):
        a = self.solid("a.png", (255, 255, 255), size=(800, 600))
        b = self.solid("b.png", (255, 255, 255), size=(400, 300))
        report, _ = imgdiff.compare(a, b, width=400)
        self.assertEqual(report["compare_width"], 400)
        self.assertEqual(report["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
