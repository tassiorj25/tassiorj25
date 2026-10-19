#!/usr/bin/env python3
"""Originality sweep — the gate that stands between a rebuild and a rip-off.

Blueprint rebuilds behaviour. It does not ship the target's name, marks, copy
or asset URLs. This scans your source tree for traces of the target using the
evidence you captured as the reference, and fails closed: any finding is a
non-zero exit, so it can sit in CI or in front of a deploy.

What it looks for
  brand     the target's brand tokens, derived from its host and page titles
  host      the target's domain, in code, configs or comments
  asset     asset URLs from the target's inventory
  copy      captured strings reproduced verbatim (default: 40+ characters)

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import Ledger  # noqa: E402

SKIP_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "out", "coverage",
    "__pycache__", ".venv", "venv", ".turbo", ".cache", "vendor", ".svelte-kit",
    "target", ".pytest_cache", ".mypy_cache",
}
SKIP_FILES = re.compile(
    r"(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|Cargo\.lock|"
    r".*\.(png|jpe?g|gif|webp|avif|ico|svg|woff2?|ttf|otf|eot|mp4|webm|mp3|wav|"
    r"pdf|zip|gz|tgz|br|wasm|map|pyc)$)", re.I,
)
GENERIC_TOKENS = {
    "www", "app", "api", "web", "cdn", "assets", "static", "com", "net", "org",
    "io", "co", "dev", "localhost", "github", "google", "cloudflare", "vercel",
    "amazonaws", "gstatic", "googleapis", "jsdelivr", "unpkg", "fontawesome",
    "bootstrap", "tailwind", "react", "next", "vue", "svelte", "example",
    # Generic words that routinely sit next to a brand in a <title> and would
    # otherwise flag every file that says "home" or "pricing".
    "home", "login", "signin", "signup", "logout", "dashboard", "about",
    "pricing", "blog", "docs", "documentation", "help", "search", "settings",
    "welcome", "index", "page", "product", "products", "features", "contact",
    "terms", "privacy", "support", "account", "profile", "admin", "news",
    "sign", "log", "in", "out", "up", "the", "and", "for", "your", "my",
    "new", "all", "view", "edit", "create", "delete", "save", "menu", "more",
}
MAX_FILE_BYTES = 2_000_000


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def registrable_label(host: str) -> str:
    """The label that identifies the owner: `spotify` in `open.spotify.com`."""
    labels = [l for l in (host or "").lower().split(".") if l]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    cand = labels[-2]
    if cand in {"co", "com", "net", "org", "gov", "ac"} and len(labels) >= 3:
        cand = labels[-3]
    return cand


def title_parts(title: str) -> list:
    """Split "Page name | Brand" into its parts, trimmed and lowercased."""
    return [p.strip().lower() for p in re.split(r"[|·•—–:]|\s+-\s+", title or "") if p.strip()]


def brand_phrases(titles) -> set:
    """The brand hiding in the page titles, including multi-word names.

    With several titles, the brand is the part they all share — that is what a
    "Page name | Brand" suffix is. With a single title, every part of it is a
    candidate, which is how a bare two-word title is caught.
    """
    per_title = [set(title_parts(t)) for t in titles if (t or "").strip()]
    if not per_title:
        return set()
    common = set.intersection(*per_title) if len(per_title) > 1 else per_title[0]
    out = set()
    for part in common:
        words = part.split()
        if not (1 <= len(words) <= 4) or len(part) > 40 or len(part) < 4:
            continue
        if all(w.strip(".,!?'\"") in GENERIC_TOKENS for w in words):
            continue
        out.add(part)
    return out


def brand_tokens(target_url: str, titles, extra) -> set:
    tokens = set()
    host = urlparse(target_url).hostname or ""
    if host:
        tokens.add(host.lower())
        tokens.add(registrable_label(host))
    tokens |= brand_phrases(titles)
    tokens.update(e.strip().lower() for e in extra if e.strip())
    return {t for t in tokens if len(t) >= 4 and t not in GENERIC_TOKENS}


def copy_windows(normalized: str, window: int) -> set:
    """Sliding windows over a captured string.

    Matching whole strings only would miss the common case: someone keeps the
    first sentence of a paragraph and rewrites the rest. Windows of `window`
    characters at half-window stride catch a partial lift while still being
    long enough that ordinary English never collides.
    """
    if len(normalized) < window:
        return set()
    stride = max(1, window // 2)
    out = {normalized[i:i + window] for i in range(0, len(normalized) - window + 1, stride)}
    out.add(normalized[-window:])
    return out


def gather_reference(evidence_dir: str, min_copy_len: int, extra_brands):
    led = Ledger(evidence_dir).load()
    problems = led.verify()
    if problems:
        raise SystemExit(f"unsound ledger in {evidence_dir}: {problems[0]}")

    strings, titles, assets, hosts = set(), [], set(), set()
    for e in led.by_kind("text-corpus"):
        for s in led.read_data(e["id"]).get("strings", []):
            strings |= copy_windows(normalize(s), min_copy_len)
    for e in led.by_kind("dom-skeleton"):
        t = led.read_data(e["id"]).get("title")
        if t:
            titles.append(t)
    for e in led.by_kind("asset-inventory"):
        for a in led.read_data(e["id"]).get("assets", []):
            url = a.get("url") or ""
            if url.startswith("http"):
                assets.add(url)
                h = urlparse(url).hostname
                if h:
                    hosts.add(h.lower())
    target = led.data.get("target") or ""
    th = urlparse(target).hostname
    if th:
        hosts.add(th.lower())
    return {
        "target": target,
        "brands": brand_tokens(target, titles, extra_brands),
        "copy": strings,
        "assets": assets,
        # Third-party CDNs and font hosts show up in any site's inventory, and
        # your clone may legitimately use the same ones, so only hosts that
        # identify the target itself are worth flagging.
        "hosts": {h for h in hosts if registrable_label(h) not in GENERIC_TOKENS},
        "titles": titles,
    }


def most_specific(matches) -> list:
    """Drop a match that is contained in a longer one on the same line.

    "Acme Cloud" and "Acme" both fire on the same text; reporting both just
    makes the same problem look like two.
    """
    found = sorted(set(matches), key=len, reverse=True)
    kept = []
    for m in found:
        if not any(m != k and m in k for k in kept):
            kept.append(m)
    return sorted(kept)


def iter_source_files(root: str, excludes):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not any(
                os.path.abspath(os.path.join(dirpath, d)) == os.path.abspath(x)
                or os.path.abspath(os.path.join(dirpath, d)).startswith(os.path.abspath(x) + os.sep)
                for x in excludes
            )
        )
        for name in sorted(filenames):
            if SKIP_FILES.match(name):
                continue
            path = os.path.join(dirpath, name)
            if any(os.path.abspath(path).startswith(os.path.abspath(x)) for x in excludes):
                continue
            try:
                if os.path.getsize(path) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def scan(root: str, ref, excludes, allow) -> list:
    findings = []
    allow_lower = {a.lower() for a in allow}
    brand_res = {
        b: re.compile(
            r"(?<![a-z0-9])" + r"\s+".join(re.escape(w) for w in b.split()) + r"(?![a-z0-9])",
            re.I,
        )
        for b in ref["brands"]
    }
    host_res = {h: re.compile(re.escape(h), re.I) for h in ref["hosts"]}

    for path in iter_source_files(root, excludes):
        try:
            with open(path, encoding="utf-8", errors="strict") as fh:
                raw = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        rel = os.path.relpath(path, root)
        if rel.lower() in allow_lower:
            continue
        lines = raw.splitlines()

        norm = normalize(raw)
        brands_hit = set()

        for i, line in enumerate(lines, 1):
            if len(line) > 4000:
                line = line[:4000]
            for brand in most_specific(b for b, rx in brand_res.items() if rx.search(line)):
                brands_hit.add(brand)
                findings.append({
                    "severity": "high", "kind": "brand", "file": rel, "line": i,
                    "match": brand, "excerpt": line.strip()[:160],
                    "why": "the target's brand token must not appear in your product",
                })
            for host in most_specific(h for h, rx in host_res.items() if rx.search(line)):
                findings.append({
                    "severity": "high", "kind": "host", "file": rel, "line": i,
                    "match": host, "excerpt": line.strip()[:160],
                    "why": "pointing at the target's domain means you did not rebuild it",
                })

        # A formatter can break a brand across lines ("Acme\n  Cloud"), so check
        # the whitespace-normalised whole file for anything the line pass missed.
        # Resolve specificity across the whole file first, then subtract what
        # the line pass already reported — otherwise dropping "Acme" in favour
        # of "Acme Cloud" on a line lets "Acme" back in here.
        whole_file = most_specific(b for b, rx in brand_res.items() if rx.search(norm))
        for brand in (b for b in whole_file if b not in brands_hit):
            findings.append({
                "severity": "high", "kind": "brand", "file": rel, "line": 0,
                "match": brand, "excerpt": "(split across lines)",
                "why": "the target's brand token must not appear in your product",
            })

        for s in ref["copy"]:
            if s in norm:
                line_no = next(
                    (i for i, ln in enumerate(lines, 1) if s[:60] in normalize(ln)), 0
                )
                findings.append({
                    "severity": "high", "kind": "copy", "file": rel, "line": line_no,
                    "match": s[:120], "excerpt": "",
                    "why": "verbatim copy from the target — write your own",
                })
        for asset in ref["assets"]:
            if asset.lower() in raw.lower():
                line_no = next((i for i, ln in enumerate(lines, 1) if asset.lower() in ln.lower()), 0)
                findings.append({
                    "severity": "high", "kind": "asset", "file": rel, "line": line_no,
                    "match": asset[:160], "excerpt": "",
                    "why": "the target's asset URL — supply your own asset",
                })

    seen, out = set(), []
    for f in findings:
        k = (f["file"], f["line"], f["kind"], f["match"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    out.sort(key=lambda f: (f["file"], f["line"], f["kind"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Originality sweep: fail closed on traces of the target")
    ap.add_argument("--dir", default="blueprint/evidence", help="target evidence dir")
    ap.add_argument("--source", default=".", help="source tree to scan")
    ap.add_argument("--brand", action="append", default=[],
                    help="extra brand token to treat as the target's (repeatable)")
    ap.add_argument("--exclude", action="append", default=[],
                    help="path to skip, beyond the evidence dir and the usual vendor dirs")
    ap.add_argument("--allow", action="append", default=[],
                    help="relative file path allowed to mention the target (e.g. docs/COMPARISON.md)")
    ap.add_argument("--min-copy-len", type=int, default=40,
                    help="shortest captured string treated as copy (default 40 chars)")
    ap.add_argument("--out", default="", help="write findings as JSON here")
    ap.add_argument("--warn-only", action="store_true",
                    help="report and exit 0 — use while building, never before shipping")
    args = ap.parse_args(argv)

    ref = gather_reference(args.dir, args.min_copy_len, args.brand)
    excludes = list(args.exclude) + [args.dir, os.path.join(args.source, "blueprint", "evidence")]
    findings = scan(args.source, ref, excludes, args.allow)

    print(f"target        : {ref['target']}")
    print(f"brand tokens  : {', '.join(sorted(ref['brands'])) or '(none derived)'}")
    print(f"copy windows  : {len(ref['copy'])} of {args.min_copy_len} chars")
    print(f"asset urls    : {len(ref['assets'])}")
    print(f"scanned       : {args.source}\n")

    if not findings:
        print("CLEAN — no traces of the target in the scanned tree.")
    else:
        by_kind = {}
        for f in findings:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        for f in findings[:60]:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"  [{f['kind']}] {loc}  {f['match']}")
            if f["excerpt"]:
                print(f"           {f['excerpt']}")
        if len(findings) > 60:
            print(f"  … and {len(findings) - 60} more")
        print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(by_kind.items())))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({
                "target": ref["target"],
                "brands": sorted(ref["brands"]),
                "findings": findings,
                "clean": not findings,
            }, fh, indent=2)
            fh.write("\n")
        print(f"wrote {args.out}")

    if findings and not args.warn_only:
        print(f"\nGATE FAIL — {len(findings)} trace(s) of the target. "
              f"Rebrand before you ship.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
