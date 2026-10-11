"""P4: derived immutable graph preview and all-link integrity, no publication."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts import atlas_v2_graph_preview as p4

ROOT=Path(__file__).resolve().parents[1]


class HistoricalGraphPreviewContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=p4.p3.p1.load_snapshot(ROOT)
        cls.snapshot["root"]=ROOT
        cls.data=p4.projection(cls.snapshot)

    def test_totals_match_p3_and_source_only(self):
        d=self.data
        self.assertEqual(d["schema_version"],"atlas-v2-graph-preview-1")
        self.assertFalse(d["historical_truth_verified_by_ci"])
        self.assertEqual((d["scope"]["start_year"],d["scope"]["end_year"]),(1762,1800))
        for key,n in {"contexts":13,"people":28,"houses":4,"affiliations":18,
                      "roles":43,"institutions":3,"relations":27}.items():
            with self.subTest(key=key):
                self.assertEqual(d["counts"][key],n)
                self.assertEqual(len(d[key]),n)

    def test_no_orphan_actor_context_house_source_or_link(self):
        d=self.data
        contexts={r["id"] for r in d["contexts"]}
        people={r["id"] for r in d["people"]}
        houses={r["id"] for r in d["houses"]}
        institutes={r["id"] for r in d["institutions"]}
        sources=set(d["sources"])
        for row in d["roles"]:
            self.assertIn(row["context_id"],contexts)
            self.assertTrue((row["person_id"] in people and row["institution_id"] is None)
                            or (row["person_id"] is None and row["institution_id"] in institutes))
        for row in d["affiliations"]:
            self.assertIn(row["house_id"],houses)
            self.assertIn(row["person_id"],people)
            self.assertFalse(row["time_qualified"])
        for row in d["relations"]:
            self.assertLessEqual(set(row["people"]),people)
            self.assertLessEqual(set(row["contexts"]),contexts)
            self.assertTrue(row["people"] or row["contexts"])
        for collection in ("roles","houses","affiliations","relations"):
            for row in d[collection]:
                with self.subTest(kind=collection,id=row["id"]):
                    self.assertTrue(row["sources"])
                    self.assertLessEqual(set(row["sources"]),sources)

    def test_only_safe_documented_public_https_sources(self):
        for source_id,s in self.data["sources"].items():
            with self.subTest(id=source_id):
                u=urlsplit(s["url"])
                self.assertEqual(u.scheme,"https")
                self.assertTrue(u.hostname)
                self.assertFalse(u.username or u.password)
                self.assertNotIn(u.hostname,{"drive.google.com","docs.google.com"})
                self.assertTrue(s["title"])
        self.assertNotIn("1000428575.jpg",json.dumps(self.data,ensure_ascii=False))
        self.assertFalse(any("ethnic_origin" in p for p in self.data["people"]))

    def test_george_iii_is_one_actor_but_two_governing_contexts(self):
        george=[r for r in self.data["roles"] if r["person_id"]=="gb-george3"
                and r["start_year"]<=1788<=r["end_year"]]
        self.assertEqual({r["context_id"] for r in george},
                         {"ctx-world-gb","ctx-world-han"})
        union=[r for r in self.data["relations"] if r["kind"]=="personal_union"]
        self.assertEqual(len(union),1)
        self.assertEqual(union[0]["people"],["gb-george3"])
        self.assertEqual(set(union[0]["contexts"]),{"ctx-world-gb","ctx-world-han"})

    def test_two_duplicate_records_kept_as_one_source_qualified_relation(self):
        marr=next(r for r in self.data["relations"] if r["id"]=="v2-p3-rel-dn-ru-marriage")
        self.assertEqual(marr["raw_record_ids"],
                         ["dn-ru-marriage","wp-marriage-1745"])
        treaty=next(r for r in self.data["relations"] if r["id"]=="v2-p3-rel-dn-ru-pr-peace")
        self.assertEqual(treaty["raw_record_ids"],
                         ["dn-ru-pr-peace","wp-petersburg-peace"])

    def test_paul_branch_is_not_official_house_renaming(self):
        rows=[r for r in self.data["affiliations"] if r["person_id"]=="ru-paul1"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["kind"],"branch_lineage")
        self.assertIn("Не заявляется как смена официального",rows[0]["branch"])

    def test_carlos_actual_reign_begin_not_conflated_with_pilot_year(self):
        carlos=next(r for r in self.data["roles"] if r["id"]=="v2-role-ex-es-carlos3")
        self.assertIsNone(carlos["start_date"])
        self.assertIn("1759",carlos["note"])
        self.assertEqual(carlos["start_year"],1781)
        elizabeth=next(r for r in self.data["roles"] if r["id"]=="v2-role-dn-ru-elizabeth")
        self.assertEqual(elizabeth["end_date"]["value"],"1762-01-05")
        self.assertEqual(elizabeth["end_date"]["precision"],"day")

    def test_consorthship_and_republic_institutions_keep_types(self):
        year=1795
        france=[r for r in self.data["roles"] if r["context_id"]=="ctx-world-frrep"
                and r["start_year"]<=year<=r["end_year"]]
        self.assertEqual({r["title"] for r in france},
                         {"Национальный конвент","Директория"})
        self.assertTrue(all(r["person_id"] is None and r["kind"]=="institutional"
                            for r in france))
        self.assertTrue(all(r["kind"]!="sovereign" for r in self.data["roles"]
                            if r["person_id"]=="fr-antoinette"))

    def test_browser_code_has_syntactic_javascript_and_explicit_feature_flag(self):
        js=ROOT/"site/atlas-v2-graph.js"
        text=js.read_text(encoding="utf-8")
        for snippet in ("atlasV2","v2Year","atlas-v2-graph.json","v2Links",
                        "atlas-v2-source","history[push?'pushState':'replaceState']",
                        "aria-modal","role','button","atlas-v2-node"):
            self.assertIn(snippet,text)
        self.assertNotIn("innerHTML",text)
        self.assertNotIn("eval(",text)
        if shutil.which("node"):
            subprocess.run(["node","--check",str(js)],check=True,capture_output=True)

    def test_preview_copies_normal_site_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            origin=base/"dist"; origin.mkdir()
            (origin/"index.html").write_text(
                "<!doctype html><html><body>"
                "<script id='chronology-data' type='application/json'>{}</script>"
                "</body></html>",encoding="utf-8")
            (origin/"atlas.json").write_text("{}\n",encoding="utf-8")
            (origin/"site.js").write_text("/* unchanged */\n",encoding="utf-8")
            (origin/"SHA256SUMS").write_text("old-checksum\n",encoding="utf-8")
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in origin.iterdir()}
            output=base/"p4"
            report=p4.preview_build(ROOT,origin,output)
            self.assertTrue(report["canonical_dist_unchanged"])
            self.assertEqual(report["counts"]["relations"],27)
            self.assertEqual({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in origin.iterdir()},before)
            self.assertEqual((output/"site.js").read_text(),"/* unchanged */\n")
            html=(output/"index.html").read_text(encoding="utf-8")
            self.assertIn("src='./atlas-v2-graph.js'",html)
            self.assertIn("href='./atlas-v2-graph.css'",html)
            projection=json.loads((output/"atlas-v2-graph.json").read_text())
            self.assertEqual(projection,self.data)
            for line in (output/"SHA256SUMS").read_text().splitlines():
                expected,name=line.split("  ",1)
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(),
                                 expected)
            with self.assertRaisesRegex(ValueError,"preview output"):
                p4.preview_build(ROOT,origin,output)

    def test_no_change_to_main_pages_allowlist(self):
        public=(ROOT/".github/workflows/publish-pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("'atlas-v2-graph.json'",public)
        self.assertNotIn("'atlas-v2-graph.js'",public)
        self.assertNotIn("'atlas-v2-graph.css'",public)
        builder=(ROOT/"scripts/soviet_audit.py").read_text(encoding="utf-8")
        self.assertNotIn("atlas-v2-graph.js",builder)


if __name__=="__main__":
    unittest.main()
