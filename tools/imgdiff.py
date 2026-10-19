#!/usr/bin/env python3
"""Visual diff between a target screenshot and the clone's own screenshot.

Scores how far apart two renders are and writes a heatmap so the gap is
visible rather than argued about. Needs Pillow; degrades to a clear message
when it is missing instead of pretending to have measured something.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover - environment-dependent
    Image = None


def _histogram_stats(gray, tolerance):
    """(pixels above tolerance, rms delta, pixel count) for a greyscale image."""
    hist = gray.histogram()
    n = sum(hist) or 1
    over = sum(hist[tolerance + 1:]) if tolerance + 1 < len(hist) else 0
    rms = (sum(v * v * c for v, c in enumerate(hist)) / n) ** 0.5
    return over, rms, n


def load_pair(a_path: str, b_path: str, width: int):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    # Compare at one width; a clone that reflows differently should show up as
    # height difference, not be hidden by rescaling both axes independently.
    def scale(img):
        if img.width == width:
            return img
        h = max(1, round(img.height * width / img.width))
        return img.resize((width, h), Image.LANCZOS)
    a, b = scale(a), scale(b)
    h = min(a.height, b.height)
    return a.crop((0, 0, width, h)), b.crop((0, 0, width, h)), a.height, b.height


def compare(a_path: str, b_path: str, width=1200, tolerance=12, blocks=8):
    a, b, ah, bh = load_pair(a_path, b_path, width)
    diff = ImageChops.difference(a, b).convert("L")
    # A histogram answers both questions in one pass and keeps the whole
    # bitmap out of Python memory.
    over, rms, n = _histogram_stats(diff, tolerance)

    # Per-band scores so the report says *where* it diverges.
    bands = []
    band_h = max(1, diff.height // blocks)
    for i in range(blocks):
        top = i * band_h
        if top >= diff.height:
            break
        box = (0, top, diff.width, min(diff.height, top + band_h))
        b_over, _, b_n = _histogram_stats(diff.crop(box), tolerance)
        b_hist = diff.crop(box).histogram()
        bands.append({
            "band": i,
            "y_range": [box[1], box[3]],
            "pixels_over_tolerance_pct": round(100 * b_over / b_n, 2),
            "mean_delta": round(sum(v * c for v, c in enumerate(b_hist)) / b_n, 2),
        })

    height_ratio = min(ah, bh) / max(ah, bh) if max(ah, bh) else 1.0
    pixel_score = 100 * (1 - over / n)
    score = round(pixel_score * (0.85 + 0.15 * height_ratio), 2)
    return {
        "target": a_path,
        "clone": b_path,
        "compare_width": width,
        "tolerance": tolerance,
        "target_height": ah,
        "clone_height": bh,
        "height_ratio": round(height_ratio, 3),
        "pixels_over_tolerance_pct": round(100 * over / n, 2),
        "rms_delta": round(rms, 2),
        "score": score,
        "bands": bands,
    }, diff


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Visual diff between target and clone screenshots")
    ap.add_argument("target")
    ap.add_argument("clone")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--tolerance", type=int, default=12, help="per-channel delta to ignore (anti-aliasing)")
    ap.add_argument("--heatmap", default="", help="write the difference image here")
    ap.add_argument("--out", default="", help="write the report as JSON here")
    ap.add_argument("--gate", type=float, default=None, help="exit 1 if score is below this")
    args = ap.parse_args(argv)

    if Image is None:
        print("imgdiff needs Pillow: pip install Pillow", file=sys.stderr)
        return 2
    for p in (args.target, args.clone):
        if not os.path.isfile(p):
            print(f"missing image: {p}", file=sys.stderr)
            return 2

    report, diff = compare(args.target, args.clone, args.width, args.tolerance)
    print(f"visual score   {report['score']:.2f}/100")
    print(f"  pixels over tolerance : {report['pixels_over_tolerance_pct']}%")
    print(f"  rms delta             : {report['rms_delta']}")
    print(f"  height target/clone   : {report['target_height']} / {report['clone_height']} "
          f"(ratio {report['height_ratio']})")
    worst = sorted(report["bands"], key=lambda b: -b["pixels_over_tolerance_pct"])[:3]
    for b in worst:
        print(f"  worst band y{b['y_range'][0]}-{b['y_range'][1]}: "
              f"{b['pixels_over_tolerance_pct']}% differ")

    if args.heatmap:
        os.makedirs(os.path.dirname(os.path.abspath(args.heatmap)) or ".", exist_ok=True)
        diff.save(args.heatmap)
        print(f"wrote {args.heatmap}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
            fh.write("\n")
        print(f"wrote {args.out}")

    if args.gate is not None and report["score"] < args.gate:
        print(f"\nGATE FAIL — visual score {report['score']} < {args.gate}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
