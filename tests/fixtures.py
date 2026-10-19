"""Synthetic evidence builders so the test suite runs offline, with no browser."""
from __future__ import annotations

import json
import os
import sys

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from ledger import Ledger  # noqa: E402


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def style_frequency(colors=None, sizes=None, spaces=None, families=None, extra=None):
    freq = {}
    freq["color"] = colors if colors is not None else {"rgb(17, 17, 17)": 40, "rgb(100, 100, 100)": 10}
    freq["background-color"] = {"rgb(255, 255, 255)": 30}
    freq["font-size"] = sizes if sizes is not None else {"16px": 20, "24px": 6, "32px": 2}
    freq["font-family"] = families if families is not None else {"Inter, sans-serif": 50}
    for prop, values in (spaces or {"padding-top": {"8px": 12, "16px": 9}, "gap": {"24px": 4}}).items():
        freq[prop] = values
    if extra:
        freq.update(extra)
    return freq


def make_evidence(
    root,
    target="https://target.test/",
    title="Target Brand",
    frequency=None,
    elements=None,
    landmarks=None,
    texts=None,
    requests=None,
    assets=None,
    viewport="1440",
):
    """Build a complete evidence dir with a sound ledger."""
    led = Ledger(root).init(target)
    raw = os.path.join(root, "raw")

    p = write_json(os.path.join(raw, f"styles-{viewport}.json"), {
        "url": target,
        "viewport": {"w": int(viewport), "h": 900},
        "frequency": frequency if frequency is not None else style_frequency(),
        "fonts": [{"family": "Inter", "weight": "400", "style": "normal", "status": "loaded"}],
    })
    led.add("computed-style", target, "test/fixture", p, viewport=viewport)

    p = write_json(os.path.join(raw, f"dom-{viewport}.json"), {
        "url": target,
        "title": title,
        "viewport": {"w": int(viewport), "h": 900},
        "documentHeight": 2000,
        "elementCount": 200,
        "measuredElements": len(elements or []),
        "landmarks": landmarks if landmarks is not None else [
            {"tag": "header", "role": None, "label": None},
            {"tag": "main", "role": None, "label": None},
            {"tag": "footer", "role": None, "label": None},
        ],
        "elements": elements or [],
    })
    led.add("dom-skeleton", target, "test/fixture", p, viewport=viewport)

    p = write_json(os.path.join(raw, f"text-{viewport}.json"), {
        "url": target, "note": "test", "strings": texts or [],
    })
    led.add("text-corpus", target, "test/fixture", p, viewport=viewport)

    p = write_json(os.path.join(raw, f"assets-{viewport}.json"), {
        "url": target, "note": "test", "assets": assets or [],
    })
    led.add("asset-inventory", target, "test/fixture", p, viewport=viewport)

    if requests is not None:
        p = write_json(os.path.join(raw, "network.json"), {
            "url": target, "note": "test", "requests": requests,
        })
        led.add("network-schema", target, "test/fixture", p)

    led.save()
    return led


def grid_rows(n=5, sig_classes=("card",), tag="li", y0=100, w=300, h=80, depth=4):
    """n uniform sibling rows, each containing a link and a label slot."""
    els = []
    for i in range(n):
        y = y0 + i * (h + 10)
        els.append({
            "tag": tag, "role": None, "type": None, "aria": None,
            "classes": list(sig_classes), "depth": depth,
            "box": {"x": 0, "y": y, "w": w, "h": h}, "textLength": 0, "styles": {},
        })
        els.append({
            "tag": "a", "role": None, "type": None, "aria": None,
            "classes": [], "depth": depth + 1,
            "box": {"x": 8, "y": y + 8, "w": 200, "h": 20}, "textLength": 18, "styles": {},
        })
        els.append({
            "tag": "span", "role": None, "type": None, "aria": None,
            "classes": ["meta"], "depth": depth + 1,
            "box": {"x": 8, "y": y + 40, "w": 120, "h": 16}, "textLength": 9, "styles": {},
        })
    return els
