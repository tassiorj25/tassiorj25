import json
import os
import tempfile
import unittest

from fixtures import TOOLS, make_evidence, write_json  # noqa: F401
from ledger import Ledger, sha256_file


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "evidence")

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_empty_sound_ledger(self):
        led = Ledger(self.root).init("https://target.test/")
        self.assertTrue(os.path.isfile(led.path))
        self.assertEqual(led.data["target"], "https://target.test/")
        self.assertEqual(led.entries, [])
        self.assertEqual(led.verify(), [])

    def test_ids_are_sequential_and_entries_carry_hashes(self):
        led = Ledger(self.root).init("https://target.test/")
        p = write_json(os.path.join(self.root, "raw", "a.json"), {"a": 1})
        e1 = led.add("note", "https://target.test/", "test", p)
        p2 = write_json(os.path.join(self.root, "raw", "b.json"), {"b": 2})
        e2 = led.add("note", "https://target.test/", "test", p2)
        self.assertEqual([e1["id"], e2["id"]], ["EV-0001", "EV-0002"])
        self.assertEqual(e1["sha256"], sha256_file(p))
        self.assertEqual(e1["data_ref"], "raw/a.json")

    def test_rejects_unknown_kind(self):
        led = Ledger(self.root).init("https://target.test/")
        p = write_json(os.path.join(self.root, "raw", "a.json"), {})
        with self.assertRaises(ValueError):
            led.add("telepathy", "https://target.test/", "test", p)

    def test_rejects_missing_data_file(self):
        led = Ledger(self.root).init("https://target.test/")
        with self.assertRaises(FileNotFoundError):
            led.add("note", "https://target.test/", "test", os.path.join(self.root, "nope.json"))

    def test_verify_catches_an_edited_raw_file(self):
        led = make_evidence(self.root)
        self.assertEqual(led.verify(), [])
        victim = os.path.join(self.root, led.entries[0]["data_ref"])
        with open(victim, "w", encoding="utf-8") as fh:
            json.dump({"frequency": {"color": {"rgb(255, 0, 0)": 999}}}, fh)
        problems = Ledger(self.root).load().verify()
        self.assertEqual(len(problems), 1)
        self.assertIn("sha256 mismatch", problems[0])
        self.assertIn("EV-0001", problems[0])

    def test_verify_catches_a_deleted_raw_file(self):
        led = make_evidence(self.root)
        os.remove(os.path.join(self.root, led.entries[1]["data_ref"]))
        problems = Ledger(self.root).load().verify()
        self.assertEqual(len(problems), 1)
        self.assertIn("raw file missing", problems[0])

    def test_verify_catches_duplicate_ids(self):
        led = make_evidence(self.root)
        led.entries.append(dict(led.entries[0]))
        problems = led.verify()
        self.assertTrue(any("duplicate Evidence ID" in p for p in problems))

    def test_cite_reports_unknown_ids(self):
        led = make_evidence(self.root)
        self.assertEqual(led.cite(["EV-0001"]), [])
        self.assertEqual(led.cite(["EV-0001", "EV-9999"]), ["EV-9999"])

    def test_load_rejects_a_future_schema(self):
        led = Ledger(self.root).init("https://target.test/")
        led.data["schema_version"] = 99
        led.save()
        with self.assertRaises(ValueError):
            Ledger(self.root).load()

    def test_read_data_round_trips(self):
        led = make_evidence(self.root)
        data = led.read_data("EV-0001")
        self.assertIn("frequency", data)
        with self.assertRaises(KeyError):
            led.read_data("EV-4242")

    def test_load_or_init_is_idempotent(self):
        make_evidence(self.root)
        led = Ledger(self.root).load_or_init("https://other.test/")
        self.assertEqual(led.data["target"], "https://target.test/")
        self.assertEqual(len(led.entries), 4)


if __name__ == "__main__":
    unittest.main()
