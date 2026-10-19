#!/usr/bin/env python3
"""Infer the data model and API surface from observed evidence.

Two independent signals, kept separate in the output so a reviewer can see
which is which:

  network  — JSON response *shapes* (key/type only; capture.mjs never writes
             payload content). An endpoint path becomes a resource name, its
             shape becomes fields. This is observation.
  dom      — repeated sibling structures in the measured DOM. Three or more
             siblings with the same signature and similar geometry is a
             collection view, and its inner slots are the fields a row shows.
             This is inference from layout, and it is labelled as such.

Every field carries its Evidence IDs. Fields nothing supports are listed under
`unknowns` rather than invented.

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

ID_SEGMENT = re.compile(
    r"^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{24,}|me|self)$",
    re.I,
)
VERSION_SEGMENT = re.compile(r"^v\d+$", re.I)
NOISE_SEGMENT = {
    "api", "graphql", "rest", "public", "internal", "data",
    # Static-asset plumbing: a path under these names is not a resource.
    "static", "assets", "_next", "build", "dist", "chunks", "_nuxt", "cdn",
}
# Words that already end in s. Stripping the s would invent a resource name
# nobody uses, and the inferred model is meant to read like the real thing.
UNCOUNTABLE = {
    "status", "data", "media", "news", "series", "species", "analysis",
    "settings", "metadata", "credentials", "address",
}
CLASS_NOISE = re.compile(r"[0-9]{2,}|[0-9a-f]{6,}")

MIN_REPEATS = 3


def singularize(word: str) -> str:
    w = word.lower()
    if w in UNCOUNTABLE:
        return w
    for suffix, repl in (("ies", "y"), ("ses", "s"), ("xes", "x"), ("hes", "h")):
        if w.endswith(suffix) and len(w) > len(suffix) + 1:
            return w[: -len(suffix)] + repl
    # `status`, `address`, `analysis` and friends end in s without being plural.
    if w.endswith(("ss", "us", "is", "os")):
        return w
    if w.endswith("s") and len(w) > 2:
        return w[:-1]
    return w


def resource_name(path: str) -> str | None:
    segs = [s for s in path.split("/") if s]
    nouns = [
        s for s in segs
        if not ID_SEGMENT.match(s) and not VERSION_SEGMENT.match(s)
        and s.lower() not in NOISE_SEGMENT and not s.startswith((".", "_"))
        and "." not in s
    ]
    if not nouns:
        return None
    return singularize(nouns[-1])


def flatten_shape(shape, prefix="", depth=0, out=None):
    """Turn a jsonShape tree into dotted field paths -> type string."""
    if out is None:
        out = {}
    if depth > 5:
        return out
    if isinstance(shape, dict):
        for k, v in shape.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                flatten_shape(v, key, depth + 1, out)
            else:
                out[key] = str(v)
    elif isinstance(shape, list):
        inner = shape[0] if shape else "unknown"
        if isinstance(inner, (dict, list)):
            flatten_shape(inner, f"{prefix}[]" if prefix else "[]", depth + 1, out)
        else:
            out[(f"{prefix}[]" if prefix else "[]")] = str(inner)
    else:
        if prefix:
            out[prefix] = str(shape)
    return out


def collection_root(shape):
    """If the response wraps a list of objects, return (key, item_shape)."""
    if isinstance(shape, list) and shape and isinstance(shape[0], dict):
        return "[]", shape[0]
    if isinstance(shape, dict):
        for k, v in shape.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return k, v[0]
    return None, None


# ---- network signal -------------------------------------------------------
def from_network(led: Ledger):
    entities: dict = defaultdict(lambda: {
        "fields": defaultdict(lambda: {"types": set(), "observations": 0, "evidence": set()}),
        "endpoints": {},
        "observations": 0,
        "evidence": set(),
    })
    endpoints = []
    for e in led.by_kind("network-schema"):
        data = led.read_data(e["id"])
        for req in data.get("requests", []):
            shape = req.get("shape")
            ep = {
                "method": req.get("method"),
                "host": req.get("host"),
                "path": req.get("path"),
                "status": req.get("status"),
                "queryKeys": req.get("queryKeys", []),
                "contentType": req.get("contentType"),
                "evidence": e["id"],
                "has_shape": bool(shape) and shape != "unparsed",
            }
            endpoints.append(ep)
            if not ep["has_shape"]:
                continue
            name = resource_name(req.get("path", ""))
            if not name:
                continue
            key, item = collection_root(shape)
            fields_src = item if item is not None else shape
            ent = entities[name]
            ent["observations"] += 1
            ent["evidence"].add(e["id"])
            ent["endpoints"][f"{req.get('method')} {req.get('path')}"] = {
                "status": req.get("status"),
                "collection_key": key,
                "evidence": e["id"],
            }
            for fname, ftype in flatten_shape(fields_src).items():
                slot = ent["fields"][fname.lstrip(".")]
                slot["types"].add(ftype)
                slot["observations"] += 1
                slot["evidence"].add(e["id"])
    return entities, endpoints


# ---- dom signal -----------------------------------------------------------
def signature(el) -> str:
    classes = [CLASS_NOISE.sub("*", c) for c in (el.get("classes") or [])][:2]
    bits = [el.get("tag", "?")]
    if el.get("role"):
        bits.append(f"[role={el['role']}]")
    bits.extend("." + c for c in classes if c)
    return "".join(bits)


def contains(outer, inner) -> bool:
    a, b = outer.get("box") or {}, inner.get("box") or {}
    if not a or not b:
        return False
    return (
        inner.get("depth", 0) > outer.get("depth", 0)
        and b["x"] >= a["x"] - 1 and b["y"] >= a["y"] - 1
        and b["x"] + b["w"] <= a["x"] + a["w"] + 1
        and b["y"] + b["h"] <= a["y"] + a["h"] + 1
        and (b["w"] * b["h"]) < (a["w"] * a["h"])
    )


def from_dom(led: Ledger):
    collections = []
    for e in led.by_kind("dom-skeleton"):
        data = led.read_data(e["id"])
        els = data.get("elements") or []
        groups: dict = defaultdict(list)
        for el in els:
            groups[(signature(el), el.get("depth"))].append(el)

        for (sig, depth), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(members) < MIN_REPEATS:
                continue
            widths = [m["box"]["w"] for m in members if m.get("box")]
            heights = [m["box"]["h"] for m in members if m.get("box")]
            if not widths or max(widths) == 0:
                continue
            # Real collection rows are near-uniform in one axis.
            w_spread = (max(widths) - min(widths)) / max(widths)
            h_spread = (max(heights) - min(heights)) / max(heights) if max(heights) else 1
            if w_spread > 0.25 and h_spread > 0.5:
                continue
            probe = max(members, key=lambda m: m["box"]["w"] * m["box"]["h"])
            slots: dict = defaultdict(lambda: {"count": 0, "text": 0, "tags": set()})
            for cand in els:
                if cand is probe or not contains(probe, cand):
                    continue
                s = signature(cand)
                slots[s]["count"] += 1
                slots[s]["text"] += cand.get("textLength") or 0
                slots[s]["tags"].add(cand.get("tag"))
            if not slots:
                continue
            collections.append({
                "signature": sig,
                "depth": depth,
                "rows_observed": len(members),
                "viewport": e.get("viewport"),
                "uniform_width": round(1 - w_spread, 3),
                "evidence": [e["id"]],
                "row_slots": [
                    {
                        "signature": s,
                        "per_row_count": v["count"],
                        "carries_text": v["text"] > 0,
                        "likely_field": (
                            "image" if "img" in v["tags"] else
                            "link" if "a" in v["tags"] else
                            "label" if v["text"] > 0 else "container"
                        ),
                    }
                    for s, v in sorted(slots.items(), key=lambda kv: -kv[1]["count"])[:12]
                ],
            })
    return collections


def infer_relationships(entities):
    rels = []
    names = set(entities)
    for name, ent in entities.items():
        for fname in ent["fields"]:
            leaf = fname.split(".")[-1].replace("[]", "")
            if leaf.endswith("_id") or leaf.endswith("Id"):
                target = singularize(re.sub(r"(_id|Id)$", "", leaf))
                if target and target != name:
                    rels.append({
                        "from": name, "field": fname, "to": target,
                        "kind": "belongs_to",
                        "basis": "field name ends in _id",
                        "target_observed": target in names,
                    })
            else:
                head = fname.split(".")[0].replace("[]", "")
                if head != fname and singularize(head) in names and singularize(head) != name:
                    rels.append({
                        "from": name, "field": fname, "to": singularize(head),
                        "kind": "embeds",
                        "basis": "nested object key matches another observed resource",
                        "target_observed": True,
                    })
    seen, out = set(), []
    for r in rels:
        k = (r["from"], r["field"], r["to"], r["kind"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def build_model(evidence_dir: str):
    led = Ledger(evidence_dir).load()
    entities, endpoints = from_network(led)
    collections = from_dom(led)

    ents = []
    for name, ent in sorted(entities.items(), key=lambda kv: -kv[1]["observations"]):
        fields = []
        for fname, slot in sorted(ent["fields"].items()):
            fields.append({
                "name": fname,
                "type": "|".join(sorted(slot["types"])),
                "observations": slot["observations"],
                "evidence": sorted(slot["evidence"]),
                "status": "observed",
            })
        ents.append({
            "name": name,
            "source": "network",
            "status": "observed",
            "observations": ent["observations"],
            "field_count": len(fields),
            "fields": fields,
            "endpoints": ent["endpoints"],
            "evidence": sorted(ent["evidence"]),
        })

    unknowns = []
    if not ents and collections:
        unknowns.append(
            "No JSON API responses were observed. Entities below are inferred from "
            "repeated DOM structure only: field names are not known, just the slots a row renders."
        )
    if not ents and not collections:
        unknowns.append(
            "Neither JSON responses nor repeated DOM structures were observed. "
            "There is no evidence for a data model yet — capture the screens where lists appear."
        )
    for ep in endpoints:
        if ep["contentType"] == "application/json" and not ep["has_shape"]:
            unknowns.append(f"{ep['method']} {ep['path']} returned JSON that could not be parsed into a shape")

    return {
        "schema_version": 1,
        "target": led.data.get("target"),
        "method": "entities from observed JSON shapes; collections from measured DOM repetition",
        "entities": ents,
        "dom_collections": collections,
        "relationships": infer_relationships(entities),
        "endpoints": endpoints,
        "unknowns": sorted(set(unknowns)),
        "summary": {
            "entities_observed": len(ents),
            "dom_collections_inferred": len(collections),
            "endpoints_seen": len(endpoints),
            "json_endpoints_with_shape": sum(1 for e in endpoints if e["has_shape"]),
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Infer a data model from evidence")
    ap.add_argument("--dir", default="blueprint/evidence")
    ap.add_argument("--out", default="blueprint/model.json")
    args = ap.parse_args(argv)

    led = Ledger(args.dir).load()
    problems = led.verify()
    if problems:
        print("refusing to infer a model from an unsound ledger:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    model = build_model(args.dir)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(model, fh, indent=2)
        fh.write("\n")
    print(f"wrote {args.out}")
    for k, v in model["summary"].items():
        print(f"  {k}: {v}")
    for u in model["unknowns"]:
        print(f"  unknown: {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
