#!/usr/bin/env python3
"""WCAG contrast check over derived tokens.

A clone that copies a palette inherits its accessibility bugs. This walks every
text colour against every surface colour that was actually observed together
often enough to matter, and reports the pairs that fail WCAG 2.1 AA.

Stdlib only. Exits non-zero when --gate is set and any pair in use fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tokens import parse_color  # noqa: E402

AA_NORMAL, AA_LARGE, AAA_NORMAL = 4.5, 3.0, 7.0


def relative_luminance(rgb) -> float:
    def channel(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg) -> float:
    """fg/bg as (r,g,b,a). An alpha < 1 on fg is composited over bg first."""
    if len(fg) > 3 and fg[3] < 0.999:
        a = fg[3]
        fg = tuple(round(fg[i] * a + bg[i] * (1 - a)) for i in range(3)) + (1.0,)
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def grade(ratio: float) -> str:
    if ratio >= AAA_NORMAL:
        return "AAA"
    if ratio >= AA_NORMAL:
        return "AA"
    if ratio >= AA_LARGE:
        return "AA-large-only"
    return "fail"


def opaque_surfaces(tokens):
    """Surfaces to test against, with a white fallback when every observed
    background is transparent (common on simple pages)."""
    out = []
    for row in tokens.get("colors", {}).get("surface", []):
        rgba = parse_color(row["value"].split("@")[0])
        if rgba is None:
            continue
        alpha = 1.0
        if "@" in row["value"]:
            try:
                alpha = float(row["value"].split("@")[1])
            except ValueError:
                alpha = 1.0
        if alpha < 0.5:
            continue
        out.append((row["token"], rgba, row["usage"], row["evidence"]))
    if not out:
        out.append(("--surface-default(assumed-white)", (255, 255, 255, 1.0), 0, []))
    return out


def check(tokens, min_usage=1):
    rows = []
    surfaces = opaque_surfaces(tokens)
    for text in tokens.get("colors", {}).get("text", []):
        if text["usage"] < min_usage:
            continue
        fg = parse_color(text["value"].split("@")[0])
        if fg is None:
            continue
        if "@" in text["value"]:
            try:
                fg = fg[:3] + (float(text["value"].split("@")[1]),)
            except ValueError:
                pass
        for s_token, s_rgba, s_usage, s_ev in surfaces:
            ratio = round(contrast_ratio(fg, s_rgba), 2)
            rows.append({
                "text_token": text["token"],
                "text_value": text["value"],
                "surface_token": s_token,
                "surface_value": "#%02x%02x%02x" % s_rgba[:3],
                "ratio": ratio,
                "grade": grade(ratio),
                "text_usage": text["usage"],
                "surface_usage": s_usage,
                "assumed_surface": s_token.endswith("(assumed-white)"),
                "evidence": sorted(set(text["evidence"]) | set(s_ev)),
            })
    rows.sort(key=lambda r: r["ratio"])
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="WCAG contrast check over derived tokens")
    ap.add_argument("--tokens", default="blueprint/tokens.json")
    ap.add_argument("--out", default="", help="write the full report as JSON here")
    ap.add_argument("--min-usage", type=int, default=1,
                    help="ignore text colours seen fewer than this many times")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any pair fails AA for normal text")
    args = ap.parse_args(argv)

    with open(args.tokens, encoding="utf-8") as fh:
        tokens = json.load(fh)
    rows = check(tokens, args.min_usage)
    if not rows:
        print("no text/surface colour pairs to check")
        return 0

    fails = [r for r in rows if r["grade"] in ("fail", "AA-large-only")]
    for r in rows:
        flag = "assumed surface" if r["assumed_surface"] else ""
        print(f"{r['ratio']:>6.2f}  {r['grade']:<14} {r['text_value']:<12} on {r['surface_value']:<9} "
              f"(x{r['text_usage']}) {flag}")
    print(f"\n{len(rows)} pair(s); {len(fails)} below AA for normal text")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"pairs": rows, "failing": len(fails)}, fh, indent=2)
            fh.write("\n")
        print(f"wrote {args.out}")

    if args.gate and fails:
        print("\nGATE FAIL — fix these in your own palette rather than inheriting them.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
