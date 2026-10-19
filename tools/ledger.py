#!/usr/bin/env python3
"""Evidence ledger: the integrity spine of a Blueprint run.

Nothing reaches a spec without an Evidence ID. Every ID points at a raw
capture file on disk and carries that file's sha256, so a claim can be
re-checked against the bytes it came from. `verify` recomputes every hash and
fails if a raw file was edited, replaced or removed after the fact.

Stdlib only. Usable as a CLI or imported by the other tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

LEDGER_NAME = "ledger.json"
RAW_DIR = "raw"
SCHEMA_VERSION = 1

KINDS = (
    "screenshot",
    "dom-skeleton",
    "computed-style",
    "network-schema",
    "asset-inventory",
    "text-corpus",
    "flow-trace",
    "robots",
    "note",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Ledger:
    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, LEDGER_NAME)
        self.raw_dir = os.path.join(root, RAW_DIR)
        self.data: dict = {}

    # ---- lifecycle -------------------------------------------------------
    def init(self, target: str) -> "Ledger":
        os.makedirs(self.raw_dir, exist_ok=True)
        self.data = {
            "schema_version": SCHEMA_VERSION,
            "target": target,
            "created_at": _utcnow(),
            "entries": [],
        }
        self.save()
        return self

    def load(self) -> "Ledger":
        with open(self.path, encoding="utf-8") as fh:
            self.data = json.load(fh)
        if self.data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported ledger schema_version={self.data.get('schema_version')!r}"
            )
        return self

    def load_or_init(self, target: str) -> "Ledger":
        if os.path.exists(self.path):
            return self.load()
        return self.init(target)

    def save(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=False)
            fh.write("\n")
        os.replace(tmp, self.path)

    # ---- entries ---------------------------------------------------------
    @property
    def entries(self) -> list:
        return self.data.setdefault("entries", [])

    def next_id(self) -> str:
        return "EV-%04d" % (len(self.entries) + 1)

    def add(
        self,
        kind: str,
        source: str,
        method: str,
        data_path: str,
        note: str = "",
        viewport: str = "",
    ) -> dict:
        if kind not in KINDS:
            raise ValueError(f"unknown kind {kind!r}; expected one of {', '.join(KINDS)}")
        if not os.path.isfile(data_path):
            raise FileNotFoundError(data_path)
        rel = os.path.relpath(data_path, self.root)
        entry = {
            "id": self.next_id(),
            "kind": kind,
            "source": source,
            "method": method,
            "captured_at": _utcnow(),
            "data_ref": rel.replace(os.sep, "/"),
            "sha256": sha256_file(data_path),
            "bytes": os.path.getsize(data_path),
        }
        if viewport:
            entry["viewport"] = viewport
        if note:
            entry["note"] = note
        self.entries.append(entry)
        return entry

    def get(self, ev_id: str) -> dict | None:
        for e in self.entries:
            if e["id"] == ev_id:
                return e
        return None

    def by_kind(self, kind: str) -> list:
        return [e for e in self.entries if e["kind"] == kind]

    def read_data(self, ev_id: str):
        entry = self.get(ev_id)
        if entry is None:
            raise KeyError(ev_id)
        path = os.path.join(self.root, entry["data_ref"])
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    # ---- integrity -------------------------------------------------------
    def verify(self) -> list:
        """Return a list of problem strings. Empty list means the ledger is sound."""
        problems = []
        seen = set()
        for e in self.entries:
            ev_id = e.get("id", "<missing id>")
            if ev_id in seen:
                problems.append(f"{ev_id}: duplicate Evidence ID")
            seen.add(ev_id)
            path = os.path.join(self.root, e.get("data_ref", ""))
            if not os.path.isfile(path):
                problems.append(f"{ev_id}: raw file missing ({e.get('data_ref')})")
                continue
            actual = sha256_file(path)
            if actual != e.get("sha256"):
                problems.append(
                    f"{ev_id}: sha256 mismatch — raw file changed after capture "
                    f"(ledger={str(e.get('sha256'))[:12]}… disk={actual[:12]}…)"
                )
        return problems

    def cite(self, ids) -> list:
        """Return the IDs that do not exist in this ledger."""
        known = {e["id"] for e in self.entries}
        return [i for i in ids if i not in known]


# ---- CLI -----------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Blueprint evidence ledger")
    ap.add_argument("--dir", default="blueprint/evidence", help="evidence directory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create an empty ledger")
    p_init.add_argument("--target", required=True)

    p_add = sub.add_parser("add", help="register a raw capture file")
    p_add.add_argument("--kind", required=True, choices=KINDS)
    p_add.add_argument("--source", required=True, help="the URL or artifact observed")
    p_add.add_argument("--method", required=True, help="how it was captured")
    p_add.add_argument("--data", required=True, help="path to the raw capture file")
    p_add.add_argument("--viewport", default="")
    p_add.add_argument("--note", default="")

    sub.add_parser("verify", help="recompute every hash; exit 1 on any problem")

    p_cite = sub.add_parser("cite", help="check that Evidence IDs exist")
    p_cite.add_argument("ids", nargs="+")

    p_list = sub.add_parser("list", help="list entries")
    p_list.add_argument("--kind", choices=KINDS)

    args = ap.parse_args(argv)
    led = Ledger(args.dir)

    if args.cmd == "init":
        led.init(args.target)
        print(f"ledger initialised at {led.path} for target {args.target}")
        return 0

    try:
        led.load()
    except FileNotFoundError:
        print(f"no ledger at {led.path} — run `ledger.py --dir {args.dir} init` first", file=sys.stderr)
        return 2

    if args.cmd == "add":
        entry = led.add(
            args.kind, args.source, args.method, args.data, args.note, args.viewport
        )
        led.save()
        print(entry["id"])
        return 0

    if args.cmd == "verify":
        problems = led.verify()
        if problems:
            print(f"FAIL — {len(problems)} problem(s) in {led.path}:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print(f"OK — {len(led.entries)} evidence entries, all hashes match")
        return 0

    if args.cmd == "cite":
        missing = led.cite(args.ids)
        if missing:
            print("FAIL — unknown Evidence IDs: " + ", ".join(missing), file=sys.stderr)
            return 1
        print("OK — all cited Evidence IDs exist")
        return 0

    if args.cmd == "list":
        rows = led.by_kind(args.kind) if args.kind else led.entries
        for e in rows:
            vp = f" [{e['viewport']}]" if e.get("viewport") else ""
            print(f"{e['id']}  {e['kind']:<16}{vp} {e['source']}")
        print(f"\n{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
