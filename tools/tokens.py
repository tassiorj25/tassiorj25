#!/usr/bin/env python3
"""Derive a design system from measured styles.

Reads every `computed-style` entry in the evidence ledger and clusters the
values that were actually observed in the browser into tokens: colours,
spacing scale, radii, type scale, shadows. Each token carries its usage count
and the Evidence IDs it came from, so a reviewer can trace any token back to
the bytes that produced it.

This is deliberately deterministic. The same evidence always yields the same
tokens, which is what makes the output reviewable instead of plausible.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import Ledger  # noqa: E402

COLOR_PROPS = ("color", "background-color", "border-top-color")
SPACE_PROPS = (
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-bottom", "gap",
)
PX = re.compile(r"^(-?\d+(?:\.\d+)?)px$")


# ---- colour ---------------------------------------------------------------
def parse_color(value: str):
    """Return (r, g, b, a) or None. Handles rgb(), rgba(), #rgb, #rrggbb."""
    v = value.strip().lower()
    m = re.match(r"^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.%]+))?\s*\)$", v)
    if m:
        r, g, b = (int(round(float(m.group(i)))) for i in (1, 2, 3))
        a_raw = m.group(4)
        if a_raw is None:
            a = 1.0
        elif a_raw.endswith("%"):
            a = float(a_raw[:-1]) / 100.0
        else:
            a = float(a_raw)
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), round(a, 3))
    m = re.match(r"^#([0-9a-f]{3,8})$", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
        if len(h) == 8:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(int(h[6:8], 16) / 255, 3))
    return None


def to_hex(rgba) -> str:
    r, g, b, a = rgba
    base = "#%02x%02x%02x" % (r, g, b)
    return base if a >= 0.999 else f"{base}@{a:g}"


def color_distance(c1, c2) -> float:
    """Weighted RGB distance. Approximates perceived difference well enough to
    merge values that differ only by rounding or anti-aliasing."""
    r1, g1, b1, a1 = c1
    r2, g2, b2, a2 = c2
    if abs(a1 - a2) > 0.08:
        return 999.0
    rm = (r1 + r2) / 2
    dr, dg, db = r1 - r2, g1 - g2, b1 - b2
    return (((2 + rm / 256) * dr * dr) + (4 * dg * dg) + ((2 + (255 - rm) / 256) * db * db)) ** 0.5


def cluster_colors(observations, threshold=12.0):
    """observations: list of (rgba, count, ev_ids). Returns clusters sorted by count."""
    ordered = sorted(observations, key=lambda o: (-o[1], to_hex(o[0])))
    clusters = []
    for rgba, count, evs in ordered:
        for c in clusters:
            if color_distance(c["rgba"], rgba) <= threshold:
                c["count"] += count
                c["evidence"].update(evs)
                c["members"].add(to_hex(rgba))
                break
        else:
            clusters.append({
                "rgba": rgba, "count": count,
                "evidence": set(evs), "members": {to_hex(rgba)},
            })
    clusters.sort(key=lambda c: (-c["count"], to_hex(c["rgba"])))
    return clusters


# ---- scales ---------------------------------------------------------------
def detect_base_unit(values_with_counts, candidates=(8, 6, 5, 4, 3, 2), coverage=0.8):
    """The largest candidate that divides at least `coverage` of observed mass."""
    total = sum(c for _, c in values_with_counts)
    if not total:
        return 1, 0.0
    best_cand, best_ratio = 1, 1.0
    for cand in candidates:
        hit = sum(c for v, c in values_with_counts if v > 0 and abs(v / cand - round(v / cand)) < 1e-9)
        ratio = hit / total
        if ratio >= coverage:
            return cand, round(ratio, 3)
        # No candidate reaches the coverage bar: keep the one that explains the
        # most spacing mass, so the reported unit stays honest about the fit.
        if ratio > best_ratio or (ratio == best_ratio and cand > best_cand):
            best_cand, best_ratio = cand, ratio
    return best_cand, round(best_ratio, 3)


def median(xs):
    s = sorted(xs)
    if not s:
        return 0.0
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


# ---- aggregation ----------------------------------------------------------
def collect(evidence_dir: str):
    led = Ledger(evidence_dir).load()
    entries = led.by_kind("computed-style")
    if not entries:
        raise SystemExit("no computed-style evidence found — run capture.mjs first")

    # property -> value -> {count, evidence:set}
    agg: dict = defaultdict(lambda: defaultdict(lambda: {"count": 0, "evidence": set()}))
    fonts: dict = defaultdict(lambda: {"count": 0, "evidence": set()})
    for e in entries:
        data = led.read_data(e["id"])
        for prop, values in (data.get("frequency") or {}).items():
            for value, count in values.items():
                slot = agg[prop][value]
                slot["count"] += count
                slot["evidence"].add(e["id"])
        for f in data.get("fonts") or []:
            key = f"{f.get('family')} {f.get('weight')} {f.get('style')}".strip()
            fonts[key]["count"] += 1
            fonts[key]["evidence"].add(e["id"])
    return led, agg, fonts, [e["id"] for e in entries]


def build_tokens(evidence_dir: str, color_threshold=12.0):
    led, agg, fonts, ev_ids = collect(evidence_dir)
    out = {
        "schema_version": 1,
        "target": led.data.get("target"),
        "derived_from": {"evidence": ev_ids, "ledger": os.path.join(evidence_dir, "ledger.json")},
        "method": "clustered from getComputedStyle observations; no value is inferred",
    }

    # colours, grouped by the property that produced them
    colors = {}
    for prop in COLOR_PROPS:
        obs = []
        for value, slot in agg.get(prop, {}).items():
            rgba = parse_color(value)
            if rgba is None or rgba[3] == 0:
                continue
            obs.append((rgba, slot["count"], slot["evidence"]))
        if not obs:
            continue
        role = {"color": "text", "background-color": "surface", "border-top-color": "border"}[prop]
        clusters = cluster_colors(obs, color_threshold)
        colors[role] = [
            {
                "token": f"--{role}-{i + 1}",
                "value": to_hex(c["rgba"]),
                "usage": c["count"],
                "merged_from": sorted(c["members"]) if len(c["members"]) > 1 else [],
                "evidence": sorted(c["evidence"]),
            }
            for i, c in enumerate(clusters)
        ]
    out["colors"] = colors

    # spacing
    space_obs: dict = defaultdict(lambda: {"count": 0, "evidence": set()})
    for prop in SPACE_PROPS:
        for value, slot in agg.get(prop, {}).items():
            m = PX.match(value)
            if not m:
                continue
            px = float(m.group(1))
            if px <= 0:
                continue
            space_obs[px]["count"] += slot["count"]
            space_obs[px]["evidence"].update(slot["evidence"])
    pairs = [(v, s["count"]) for v, s in space_obs.items()]
    base, coverage = detect_base_unit(pairs)
    out["spacing"] = {
        "base_unit_px": base,
        "base_unit_coverage": coverage,
        "note": "base_unit is the largest unit dividing >=80% of observed spacing mass",
        "scale": [
            {
                "token": f"--space-{int(v) if v == int(v) else v}",
                "value": f"{int(v) if v == int(v) else v}px",
                "steps_of_base": round(v / base, 2) if base else None,
                "usage": s["count"],
                "evidence": sorted(s["evidence"]),
            }
            for v, s in sorted(space_obs.items(), key=lambda kv: kv[0])
        ],
    }

    # type scale
    size_obs: dict = defaultdict(lambda: {"count": 0, "evidence": set()})
    for value, slot in agg.get("font-size", {}).items():
        m = PX.match(value)
        if m:
            size_obs[float(m.group(1))]["count"] += slot["count"]
            size_obs[float(m.group(1))]["evidence"].update(slot["evidence"])
    sizes = sorted(size_obs)
    ratios = [round(sizes[i + 1] / sizes[i], 3) for i in range(len(sizes) - 1) if sizes[i]]
    out["typography"] = {
        "families": [
            {"value": v, "usage": s["count"], "evidence": sorted(s["evidence"])}
            for v, s in sorted(agg.get("font-family", {}).items(), key=lambda kv: -kv[1]["count"])
        ],
        "weights": [
            {"value": v, "usage": s["count"], "evidence": sorted(s["evidence"])}
            for v, s in sorted(agg.get("font-weight", {}).items(), key=lambda kv: -kv[1]["count"])
        ],
        "loaded_faces": [
            {"value": k, "evidence": sorted(v["evidence"])}
            for k, v in sorted(fonts.items(), key=lambda kv: -kv[1]["count"])
        ],
        "scale": [
            {
                "token": f"--text-{int(v) if v == int(v) else v}",
                "value": f"{int(v) if v == int(v) else v}px",
                "usage": size_obs[v]["count"],
                "evidence": sorted(size_obs[v]["evidence"]),
            }
            for v in sizes
        ],
        "observed_step_ratios": ratios,
        "median_step_ratio": round(median(ratios), 3) if ratios else None,
        "line_heights": [
            {"value": v, "usage": s["count"], "evidence": sorted(s["evidence"])}
            for v, s in sorted(agg.get("line-height", {}).items(), key=lambda kv: -kv[1]["count"])
        ],
        "letter_spacing": [
            {"value": v, "usage": s["count"], "evidence": sorted(s["evidence"])}
            for v, s in sorted(agg.get("letter-spacing", {}).items(), key=lambda kv: -kv[1]["count"])
        ],
    }

    # radii + shadows, verbatim because there is nothing to cluster usefully
    def verbatim(prop, token_prefix):
        rows = sorted(agg.get(prop, {}).items(), key=lambda kv: -kv[1]["count"])
        return [
            {
                "token": f"--{token_prefix}-{i + 1}",
                "value": v,
                "usage": s["count"],
                "evidence": sorted(s["evidence"]),
            }
            for i, (v, s) in enumerate(rows)
        ]

    out["radii"] = verbatim("border-radius", "radius")
    out["shadows"] = verbatim("box-shadow", "shadow")
    out["borders"] = verbatim("border-top-width", "border-width")

    layout = {}
    for prop, name in (("max-width", "max_widths"), ("grid-template-columns", "grid_templates"),
                       ("display", "display_modes"), ("flex-direction", "flex_directions")):
        rows = sorted(agg.get(prop, {}).items(), key=lambda kv: -kv[1]["count"])[:12]
        layout[name] = [{"value": v, "usage": s["count"], "evidence": sorted(s["evidence"])} for v, s in rows]
    out["layout"] = layout

    counts = {
        "colors": sum(len(v) for v in colors.values()),
        "spacing_steps": len(out["spacing"]["scale"]),
        "type_steps": len(out["typography"]["scale"]),
        "radii": len(out["radii"]),
        "shadows": len(out["shadows"]),
    }
    out["summary"] = counts
    return out


def to_css(tokens: dict) -> str:
    lines = [
        "/* Generated by Blueprint from measured evidence. Do not hand-edit:",
        f"   regenerate with tools/tokens.py so every value keeps its Evidence IDs. */",
        ":root {",
    ]
    for role, rows in (tokens.get("colors") or {}).items():
        lines.append(f"  /* {role} */")
        for r in rows:
            val = r["value"].split("@")[0]
            lines.append(f"  {r['token']}: {val}; /* x{r['usage']} {','.join(r['evidence'][:3])} */")
    for key, label in (("spacing", "scale"),):
        lines.append("  /* spacing */")
        for r in tokens.get(key, {}).get(label, []):
            lines.append(f"  {r['token']}: {r['value']}; /* x{r['usage']} */")
    lines.append("  /* type */")
    for r in tokens.get("typography", {}).get("scale", []):
        lines.append(f"  {r['token']}: {r['value']}; /* x{r['usage']} */")
    for group in ("radii", "shadows"):
        if tokens.get(group):
            lines.append(f"  /* {group} */")
            for r in tokens[group]:
                lines.append(f"  {r['token']}: {r['value']}; /* x{r['usage']} */")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Derive design tokens from measured evidence")
    ap.add_argument("--dir", default="blueprint/evidence", help="evidence directory")
    ap.add_argument("--out", default="blueprint/tokens.json")
    ap.add_argument("--css", default="", help="also write CSS custom properties here")
    ap.add_argument("--color-threshold", type=float, default=12.0,
                    help="merge colours closer than this weighted-RGB distance (default 12)")
    args = ap.parse_args(argv)

    led = Ledger(args.dir).load()
    problems = led.verify()
    if problems:
        print("refusing to derive tokens from an unsound ledger:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    tokens = build_tokens(args.dir, args.color_threshold)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(tokens, fh, indent=2)
        fh.write("\n")
    print(f"wrote {args.out}")
    for k, v in tokens["summary"].items():
        print(f"  {k}: {v}")
    print(f"  base spacing unit: {tokens['spacing']['base_unit_px']}px "
          f"(covers {tokens['spacing']['base_unit_coverage']:.0%} of observations)")
    if tokens["typography"]["median_step_ratio"]:
        print(f"  median type step ratio: {tokens['typography']['median_step_ratio']}")
    if args.css:
        os.makedirs(os.path.dirname(os.path.abspath(args.css)), exist_ok=True)
        with open(args.css, "w", encoding="utf-8") as fh:
            fh.write(to_css(tokens))
        print(f"wrote {args.css}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
