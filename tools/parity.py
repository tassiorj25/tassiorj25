#!/usr/bin/env python3
"""Score a clone against its target, from evidence on both sides.

The trick is symmetry: you capture your own clone with the same capture.mjs you
pointed at the target, then this compares the two derived systems. Nobody has
to be asked whether it "looks close" — the answer is a number per dimension,
and --gate can fail a build on it.

Dimensions and weights:
  palette    25  usage-weighted share of the target's colour mass matched
  type       25  usage-weighted share of the target's font sizes matched
  spacing    20  base-unit agreement plus scale overlap
  shape      10  radii and shadows
  structure  20  landmark sequence and element density per viewport

Stdlib only.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import Ledger  # noqa: E402
from tokens import build_tokens, color_distance, parse_color  # noqa: E402

WEIGHTS = {"palette": 25, "type": 25, "spacing": 20, "shape": 10, "structure": 20}


def _usage_weighted_match(target_rows, clone_values, match_fn):
    total = sum(r["usage"] for r in target_rows) or 0
    if total == 0:
        return 1.0, [], []
    matched_mass, missing, matched = 0, [], []
    for r in target_rows:
        hit = next((cv for cv in clone_values if match_fn(r["value"], cv)), None)
        if hit is None:
            missing.append({"value": r["value"], "usage": r["usage"], "evidence": r["evidence"][:3]})
        else:
            matched_mass += r["usage"]
            matched.append({"target": r["value"], "clone": hit})
    return matched_mass / total, missing, matched


def palette_parity(t_tokens, c_tokens, threshold=18.0):
    per_role, details = {}, {}
    for role in ("text", "surface", "border"):
        t_rows = t_tokens.get("colors", {}).get(role, [])
        c_vals = [r["value"] for r in c_tokens.get("colors", {}).get(role, [])]
        if not t_rows:
            continue

        def close(tv, cv):
            a, b = parse_color(tv.split("@")[0]), parse_color(cv.split("@")[0])
            return a is not None and b is not None and color_distance(a, b) <= threshold

        ratio, missing, _ = _usage_weighted_match(t_rows, c_vals, close)
        per_role[role] = round(100 * ratio, 2)
        details[role] = {"unmatched_target_colors": missing[:8]}
    score = round(sum(per_role.values()) / len(per_role), 2) if per_role else 100.0
    return score, {"per_role": per_role, "detail": details, "threshold": threshold}


def type_parity(t_tokens, c_tokens):
    t_rows = t_tokens.get("typography", {}).get("scale", [])
    c_vals = [r["value"] for r in c_tokens.get("typography", {}).get("scale", [])]
    ratio, missing, _ = _usage_weighted_match(t_rows, c_vals, lambda tv, cv: tv == cv)
    t_fam = {r["value"] for r in t_tokens.get("typography", {}).get("families", [])}
    c_fam = {r["value"] for r in c_tokens.get("typography", {}).get("families", [])}
    fam_overlap = len(t_fam & c_fam) / len(t_fam) if t_fam else 1.0
    score = round(100 * (0.75 * ratio + 0.25 * fam_overlap), 2)
    return score, {
        "size_mass_matched_pct": round(100 * ratio, 2),
        "family_overlap_pct": round(100 * fam_overlap, 2),
        "unmatched_target_sizes": missing[:10],
        "note": "font families intentionally differ once you substitute your own type — "
                "expect this to be below 100 and treat it as a decision, not a defect",
    }


def spacing_parity(t_tokens, c_tokens):
    t_sp, c_sp = t_tokens.get("spacing", {}), c_tokens.get("spacing", {})
    base_match = 1.0 if t_sp.get("base_unit_px") == c_sp.get("base_unit_px") else 0.0
    t_rows = t_sp.get("scale", [])
    c_vals = [r["value"] for r in c_sp.get("scale", [])]
    ratio, missing, _ = _usage_weighted_match(t_rows, c_vals, lambda tv, cv: tv == cv)
    score = round(100 * (0.4 * base_match + 0.6 * ratio), 2)
    return score, {
        "target_base_unit_px": t_sp.get("base_unit_px"),
        "clone_base_unit_px": c_sp.get("base_unit_px"),
        "base_unit_match": bool(base_match),
        "scale_mass_matched_pct": round(100 * ratio, 2),
        "unmatched_target_steps": missing[:10],
    }


def shape_parity(t_tokens, c_tokens):
    parts, detail = [], {}
    for group in ("radii", "shadows"):
        t_rows = t_tokens.get(group, [])
        c_vals = [r["value"] for r in c_tokens.get(group, [])]
        if not t_rows:
            continue
        ratio, missing, _ = _usage_weighted_match(t_rows, c_vals, lambda tv, cv: tv == cv)
        parts.append(ratio)
        detail[group] = {"matched_pct": round(100 * ratio, 2), "unmatched": missing[:6]}
    score = round(100 * sum(parts) / len(parts), 2) if parts else 100.0
    return score, detail


def _landmark_profile(led: Ledger):
    """viewport -> (landmark sequence, measured element count)"""
    out = {}
    for e in led.by_kind("dom-skeleton"):
        data = led.read_data(e["id"])
        vp = e.get("viewport") or str(data.get("viewport", {}).get("w", "?"))
        seq = [f"{l.get('tag')}:{l.get('role') or ''}" for l in data.get("landmarks", [])]
        out[vp] = (seq, data.get("measuredElements", 0), data.get("documentHeight", 0))
    return out


def structure_parity(t_dir, c_dir):
    t_prof = _landmark_profile(Ledger(t_dir).load())
    c_prof = _landmark_profile(Ledger(c_dir).load())
    shared = sorted(set(t_prof) & set(c_prof), key=lambda v: int(v) if str(v).isdigit() else 0)
    if not shared:
        return 0.0, {
            "error": "no shared viewport between target and clone evidence — "
                     "capture the clone at the same --viewports as the target",
            "target_viewports": sorted(t_prof), "clone_viewports": sorted(c_prof),
        }
    rows = []
    for vp in shared:
        t_seq, t_n, t_h = t_prof[vp]
        c_seq, c_n, c_h = c_prof[vp]
        seq_ratio = difflib.SequenceMatcher(None, t_seq, c_seq).ratio() if (t_seq or c_seq) else 1.0
        density = min(t_n, c_n) / max(t_n, c_n) if max(t_n, c_n) else 1.0
        height = min(t_h, c_h) / max(t_h, c_h) if max(t_h, c_h) else 1.0
        rows.append({
            "viewport": vp,
            "landmark_sequence_pct": round(100 * seq_ratio, 2),
            "element_density_pct": round(100 * density, 2),
            "page_height_pct": round(100 * height, 2),
            "target_landmarks": t_seq[:12],
            "clone_landmarks": c_seq[:12],
            "score": round(100 * (0.5 * seq_ratio + 0.25 * density + 0.25 * height), 2),
        })
    score = round(sum(r["score"] for r in rows) / len(rows), 2)
    return score, {"per_viewport": rows}


def run(target_dir, clone_dir, color_threshold=18.0):
    for d in (target_dir, clone_dir):
        problems = Ledger(d).load().verify()
        if problems:
            raise SystemExit(f"unsound ledger in {d}: {problems[0]}")
    t_tokens = build_tokens(target_dir)
    c_tokens = build_tokens(clone_dir)

    scores, details = {}, {}
    scores["palette"], details["palette"] = palette_parity(t_tokens, c_tokens, color_threshold)
    scores["type"], details["type"] = type_parity(t_tokens, c_tokens)
    scores["spacing"], details["spacing"] = spacing_parity(t_tokens, c_tokens)
    scores["shape"], details["shape"] = shape_parity(t_tokens, c_tokens)
    scores["structure"], details["structure"] = structure_parity(target_dir, clone_dir)

    overall = round(sum(scores[k] * WEIGHTS[k] for k in WEIGHTS) / sum(WEIGHTS.values()), 2)
    return {
        "schema_version": 1,
        "target_evidence": target_dir,
        "clone_evidence": clone_dir,
        "weights": WEIGHTS,
        "scores": scores,
        "overall": overall,
        "details": details,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Score a clone against its target from evidence")
    ap.add_argument("--target", default="blueprint/evidence", help="target evidence dir")
    ap.add_argument("--clone", default="blueprint/clone-evidence", help="clone evidence dir")
    ap.add_argument("--out", default="blueprint/parity.json")
    ap.add_argument("--color-threshold", type=float, default=18.0)
    ap.add_argument("--gate", type=float, default=None, help="exit 1 if overall is below this")
    args = ap.parse_args(argv)

    report = run(args.target, args.clone, args.color_threshold)
    print(f"overall parity  {report['overall']:.2f}/100\n")
    for dim, w in WEIGHTS.items():
        print(f"  {dim:<10} {report['scores'][dim]:>6.2f}  (weight {w})")
    det = report["details"]
    if det["structure"].get("error"):
        print(f"\n  structure: {det['structure']['error']}")
    for role, rows in det["palette"]["detail"].items():
        for m in rows["unmatched_target_colors"][:3]:
            print(f"  unmatched {role} colour {m['value']} (used x{m['usage']}, {','.join(m['evidence'])})")
    for m in det["spacing"]["unmatched_target_steps"][:3]:
        print(f"  unmatched spacing step {m['value']} (used x{m['usage']})")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    print(f"\nwrote {args.out}")

    if args.gate is not None and report["overall"] < args.gate:
        print(f"GATE FAIL — parity {report['overall']} < {args.gate}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
