import os
import tempfile
import unittest

from fixtures import grid_rows, make_evidence
from model import (build_model, collection_root, contains, flatten_shape,
                   resource_name, signature, singularize)


class TestNaming(unittest.TestCase):
    def test_singularize_handles_the_common_plurals(self):
        for plural, singular in (("users", "user"), ("stories", "story"),
                                 ("boxes", "box"), ("addresses", "address"),
                                 ("status", "status"), ("data", "data")):
            self.assertEqual(singularize(plural), singular, plural)

    def test_resource_name_ignores_ids_versions_and_plumbing(self):
        self.assertEqual(resource_name("/api/v2/playlists/42"), "playlist")
        self.assertEqual(resource_name("/api/users/550e8400-e29b-41d4-a716-446655440000"), "user")
        self.assertEqual(resource_name("/v1/me/tracks"), "track")
        self.assertEqual(resource_name("/graphql"), None)
        self.assertEqual(resource_name("/"), None)
        self.assertEqual(resource_name("/_next/static/chunk.js"), None)


class TestShapes(unittest.TestCase):
    def test_flatten_shape_produces_dotted_field_paths(self):
        shape = {"id": "string<uuid>", "owner": {"id": "number", "name": "string"},
                 "tags": ["string", "x3"]}
        flat = flatten_shape(shape)
        self.assertEqual(flat["id"], "string<uuid>")
        self.assertEqual(flat["owner.name"], "string")
        self.assertEqual(flat["tags[]"], "string")

    def test_collection_root_finds_the_wrapped_list(self):
        key, item = collection_root({"items": [{"id": "number"}], "total": "number"})
        self.assertEqual(key, "items")
        self.assertEqual(item, {"id": "number"})
        key, item = collection_root([{"id": "number"}])
        self.assertEqual(key, "[]")
        self.assertEqual(collection_root({"id": "number"}), (None, None))


class TestDomGeometry(unittest.TestCase):
    def test_contains_requires_both_depth_and_enclosure(self):
        outer = {"depth": 2, "box": {"x": 0, "y": 0, "w": 100, "h": 100}}
        inner = {"depth": 3, "box": {"x": 10, "y": 10, "w": 20, "h": 20}}
        self.assertTrue(contains(outer, inner))
        self.assertFalse(contains(inner, outer))
        shallow = {"depth": 1, "box": {"x": 10, "y": 10, "w": 20, "h": 20}}
        self.assertFalse(contains(outer, shallow))
        outside = {"depth": 3, "box": {"x": 500, "y": 10, "w": 20, "h": 20}}
        self.assertFalse(contains(outer, outside))

    def test_signature_normalises_generated_class_hashes(self):
        a = signature({"tag": "li", "classes": ["css-1a2b3c", "row"]})
        b = signature({"tag": "li", "classes": ["css-9f8e7d", "row"]})
        self.assertEqual(a, b)

    def test_signature_includes_role_when_present(self):
        self.assertIn("[role=listitem]", signature({"tag": "div", "role": "listitem", "classes": []}))


class TestBuildModel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "evidence")

    def tearDown(self):
        self.tmp.cleanup()

    def test_entities_come_from_observed_json_shapes(self):
        make_evidence(self.root, requests=[{
            "method": "GET", "host": "target.test", "path": "/api/v1/playlists",
            "queryKeys": ["limit"], "status": 200, "contentType": "application/json",
            "resourceType": "fetch",
            "shape": {"items": [{"id": "string<uuid>", "name": "string",
                                 "owner_id": "number", "created": "string<date>"}],
                      "total": "number"},
        }])
        m = build_model(self.root)
        self.assertEqual(m["summary"]["entities_observed"], 1)
        ent = m["entities"][0]
        self.assertEqual(ent["name"], "playlist")
        self.assertEqual(ent["status"], "observed")
        names = {f["name"] for f in ent["fields"]}
        self.assertEqual(names, {"id", "name", "owner_id", "created"})
        for f in ent["fields"]:
            self.assertTrue(f["evidence"])

    def test_belongs_to_is_inferred_from_an_id_field(self):
        make_evidence(self.root, requests=[{
            "method": "GET", "host": "target.test", "path": "/api/tracks",
            "queryKeys": [], "status": 200, "contentType": "application/json",
            "resourceType": "fetch",
            "shape": [{"id": "number", "album_id": "number"}],
        }])
        rels = build_model(self.root)["relationships"]
        self.assertEqual(len(rels), 1)
        self.assertEqual((rels[0]["from"], rels[0]["to"], rels[0]["kind"]),
                         ("track", "album", "belongs_to"))
        self.assertFalse(rels[0]["target_observed"])

    def test_repeated_dom_rows_become_an_inferred_collection(self):
        make_evidence(self.root, elements=grid_rows(n=6))
        m = build_model(self.root)
        self.assertEqual(m["summary"]["entities_observed"], 0)
        self.assertGreaterEqual(m["summary"]["dom_collections_inferred"], 1)
        col = next(c for c in m["dom_collections"] if c["signature"].startswith("li."))
        self.assertEqual(col["rows_observed"], 6)
        kinds = {s["likely_field"] for s in col["row_slots"]}
        self.assertIn("link", kinds)
        self.assertIn("label", kinds)
        self.assertTrue(col["evidence"])

    def test_two_rows_are_not_a_collection(self):
        make_evidence(self.root, elements=grid_rows(n=2))
        self.assertEqual(build_model(self.root)["summary"]["dom_collections_inferred"], 0)

    def test_says_so_when_there_is_no_evidence_instead_of_inventing_a_model(self):
        make_evidence(self.root)
        m = build_model(self.root)
        self.assertEqual(m["entities"], [])
        self.assertEqual(m["dom_collections"], [])
        self.assertTrue(m["unknowns"])
        self.assertIn("no evidence for a data model", " ".join(m["unknowns"]))

    def test_unparsed_json_is_recorded_as_an_unknown(self):
        make_evidence(self.root, requests=[{
            "method": "GET", "host": "target.test", "path": "/api/feed",
            "queryKeys": [], "status": 200, "contentType": "application/json",
            "resourceType": "fetch", "shape": "unparsed",
        }])
        m = build_model(self.root)
        self.assertTrue(any("/api/feed" in u for u in m["unknowns"]))


if __name__ == "__main__":
    unittest.main()
