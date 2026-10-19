import os
import tempfile
import unittest

from fixtures import make_evidence
from sweep import (SKIP_DIRS, brand_phrases, brand_tokens, copy_windows,
                   gather_reference, registrable_label, scan)

LONG = "we help teams ship their work faster than ever before without the usual friction"


class TestBrandDerivation(unittest.TestCase):
    def test_registrable_label_picks_the_owner(self):
        for host, label in (("open.spotify.com", "spotify"), ("spotify.com", "spotify"),
                            ("bbc.co.uk", "bbc"), ("a.b.c.notion.so", "notion"),
                            ("localhost", "localhost"), ("", "")):
            self.assertEqual(registrable_label(host), label, host)

    def test_brand_is_the_suffix_shared_by_every_title(self):
        self.assertEqual(brand_phrases(["Home | Acme Cloud", "Pricing | Acme Cloud"]),
                         {"acme cloud"})

    def test_a_single_multi_word_title_is_a_brand(self):
        self.assertEqual(brand_phrases(["Hacker News"]), {"hacker news"})

    def test_generic_titles_produce_no_brand(self):
        self.assertEqual(brand_phrases(["Sign in", "Sign in"]), set())
        self.assertEqual(brand_phrases(["Alpha page", "Beta page"]), set())
        self.assertEqual(brand_phrases([]), set())

    def test_host_and_extras_join_the_token_set(self):
        tokens = brand_tokens("https://acme.io/x", ["Dashboard – Acme"], ["AcmeCloud"])
        self.assertEqual(tokens, {"acme", "acme.io", "acmecloud"})

    def test_generic_hosts_never_become_brands(self):
        self.assertNotIn("example", brand_tokens("https://example.com/", [], []))


class TestCopyWindows(unittest.TestCase):
    def test_a_long_string_yields_overlapping_windows(self):
        w = copy_windows(LONG, 40)
        self.assertGreater(len(w), 1)
        self.assertTrue(all(len(x) == 40 for x in w))

    def test_strings_shorter_than_the_window_are_ignored(self):
        self.assertEqual(copy_windows("too short to matter", 40), set())

    def test_the_tail_is_always_covered(self):
        self.assertIn(LONG[-40:], copy_windows(LONG, 40))


class TestScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.evidence = os.path.join(self.tmp.name, "evidence")
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        make_evidence(
            self.evidence,
            target="https://acme.io/",
            title="Acme Cloud",
            texts=[LONG],
            assets=[{"kind": "image", "url": "https://cdn.acme.io/hero.png"}],
        )
        self.ref = gather_reference(self.evidence, 40, [])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, body):
        path = os.path.join(self.src, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def test_a_clean_tree_produces_no_findings(self):
        self.write("app/page.tsx", "export default () => <h1>Dispatch</h1>;\n")
        self.assertEqual(scan(self.src, self.ref, [], []), [])

    def test_catches_the_brand_name(self):
        self.write("app/header.tsx", "const title = 'Acme Cloud';\n")
        findings = scan(self.src, self.ref, [], [])
        self.assertEqual([f["kind"] for f in findings], ["brand"])
        self.assertEqual(findings[0]["line"], 1)
        self.assertEqual(findings[0]["file"], os.path.join("app", "header.tsx"))

    def test_catches_the_brand_across_a_line_break(self):
        self.write("app/x.html", "<h1>Acme\n  Cloud</h1>\n")
        findings = scan(self.src, self.ref, [], [])
        self.assertTrue(any(f["kind"] == "brand" and f["match"] == "acme cloud"
                            for f in findings))

    def test_overlapping_brand_tokens_report_once(self):
        self.write("app/header.tsx", "const t = 'Acme Cloud';\n")
        matches = [f["match"] for f in scan(self.src, self.ref, [], []) if f["kind"] == "brand"]
        self.assertEqual(matches, ["acme cloud"])

    def test_catches_the_target_host(self):
        self.write("lib/api.ts", "const BASE = 'https://acme.io/api';\n")
        kinds = {f["kind"] for f in scan(self.src, self.ref, [], [])}
        self.assertIn("host", kinds)

    def test_catches_verbatim_copy(self):
        self.write("app/hero.tsx", f"<p>{LONG}</p>\n")
        findings = scan(self.src, self.ref, [], [])
        self.assertTrue(any(f["kind"] == "copy" for f in findings))

    def test_catches_a_partial_lift_of_a_long_paragraph(self):
        self.write("app/hero.tsx", f"<p>{LONG[:55]} — and then our own words.</p>\n")
        self.assertTrue(any(f["kind"] == "copy" for f in scan(self.src, self.ref, [], [])))

    def test_catches_the_targets_asset_url(self):
        self.write("app/img.tsx", "<img src='https://cdn.acme.io/hero.png' />\n")
        kinds = {f["kind"] for f in scan(self.src, self.ref, [], [])}
        self.assertTrue({"asset", "host"} & kinds)

    def test_allow_list_exempts_a_named_file(self):
        rel = os.path.join("docs", "COMPARISON.md")
        self.write(rel, "We differ from Acme Cloud in these ways.\n")
        self.assertTrue(scan(self.src, self.ref, [], []))
        self.assertEqual(scan(self.src, self.ref, [], [rel]), [])

    def test_vendor_directories_are_skipped(self):
        self.write(os.path.join("node_modules", "pkg", "index.js"), "// Acme Cloud\n")
        self.assertIn("node_modules", SKIP_DIRS)
        self.assertEqual(scan(self.src, self.ref, [], []), [])

    def test_binary_and_lockfiles_are_skipped(self):
        self.write("package-lock.json", '{"name":"Acme Cloud"}\n')
        self.write("logo.svg", "<!-- Acme Cloud -->\n")
        self.assertEqual(scan(self.src, self.ref, [], []), [])

    def test_excluded_paths_are_skipped(self):
        self.write(os.path.join("notes", "scratch.md"), "Acme Cloud\n")
        self.assertEqual(scan(self.src, self.ref, [os.path.join(self.src, "notes")], []), [])

    def test_findings_are_deduplicated_and_ordered(self):
        self.write("b.ts", "// Acme Cloud\n// Acme Cloud again\n")
        self.write("a.ts", "// Acme Cloud\n")
        findings = scan(self.src, self.ref, [], [])
        self.assertEqual([f["file"] for f in findings], ["a.ts", "b.ts", "b.ts"])

    def test_refuses_an_unsound_ledger(self):
        victim = os.path.join(self.evidence, "raw", "text-1440.json")
        with open(victim, "w", encoding="utf-8") as fh:
            fh.write("{}")
        with self.assertRaises(SystemExit):
            gather_reference(self.evidence, 40, [])


if __name__ == "__main__":
    unittest.main()
