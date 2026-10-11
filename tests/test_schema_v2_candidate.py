"""Non-production contract proof for historical Atlas schema v2.

Checks source representation and foreign-key rules; NOT historical attestation.
The v1 SQLite, canonical sources and SPA are never modified by these tests.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts import atlas_db

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "data/atlas/world-pilots"


def read_world(name):
    return json.loads((WORLD / name).read_text(encoding="utf-8"))


class AtlasV2Candidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canon = atlas_db.load(ROOT)
        cls.net = read_world("dynasty-1762-1780.json")
        cls.ext = read_world("extension-1781-1800.json")
        cls.houses = read_world("dynasty-footprints-1762-1800.json")
        cls.coverage = read_world("coverage-1762-1800.json")
        cls.cases = json.loads((ROOT / "data/atlas/transition-cases.json").read_text(encoding="utf-8"))
        cls.temp = tempfile.TemporaryDirectory()
        path = Path(cls.temp.name) / "copy-v1.sqlite"
        atlas_db.write_sqlite(cls.canon, path, (ROOT / "schemas/atlas.sql").read_text(encoding="utf-8"))
        cls.base = sqlite3.connect(path)

    @classmethod
    def tearDownClass(cls):
        cls.base.close()
        cls.temp.cleanup()

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.base.backup(self.db)
        self.db.executescript((ROOT / "schemas/atlas_v2_candidate.sql").read_text(encoding="utf-8"))
        self.db.execute("PRAGMA foreign_keys=ON")

    def tearDown(self):
        self.db.close()

    def context(self, ident, kind="polity"):
        self.db.execute("INSERT INTO v2_contexts(id,label,kind) VALUES(?,?,?)", (ident, ident, kind))

    def period(self, ident, lo, hi, meaning="observation"):
        self.db.execute(
            "INSERT INTO v2_periods(id,start_year,end_year,meaning) VALUES(?,?,?,?)",
            (ident,lo,hi,meaning),
        )

    def assertion(self, ident, source, category="legal"):
        catalog = {s["id"]:s for group in (self.canon["sources"], self.net["sources"], self.ext["sources"])
                   for s in group}
        item = catalog[source]
        legacy = source if source in {s["id"] for s in self.canon["sources"]} else None
        self.db.execute(
            "INSERT OR IGNORE INTO v2_sources VALUES(?,?,?,?,?,?,?)",
            ("test:"+source, "test-source-namespace",source,item["title"],item["url"],
             legacy,item.get("verification","unverified")),
        )
        self.db.execute("INSERT INTO v2_assertions VALUES(?,?,?,?,?,?)",
                        (ident,category,"Source-limited test statement",
                         "This test makes no independent historical claim",
                         "not_assessed",item.get("verification","unverified")))
        self.db.execute("INSERT INTO v2_assertion_sources VALUES(?,?,?)",
                        (ident,"test:"+source,""))

    def test_v1_schema_and_rows_unchanged(self):
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])
        for table,key in [("people","people"),("provenance","provenance")]:
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0],
                             len(self.canon[key]))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM entries WHERE kind='tenures'").fetchone()[0],
            len(self.canon["tenures"]))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""INSERT INTO v2_roles
                (id,context_id,title,role_kind,period_id,assertion_id,origin,native_id)
                VALUES ('bad','missing','x','sovereign','bad','bad','test','bad')""")

    def test_1685_two_tsars_one_regent_not_single_real_ruler(self):
        terms = {t["id"]:t for t in self.canon["tenures"]}
        ivan,peter,sofia = [terms[x] for x in
                            ("tenure-r04","tenure-r05-joint","tenure-r22")]
        self.assertEqual([ivan["office_id"],peter["office_id"],sofia["office_id"]],
                         ["tsar","tsar","regent"])
        self.assertEqual(len({ivan["person_id"],peter["person_id"],sofia["person_id"]}),3)
        for term in (ivan,peter,sofia):
            self.assertEqual(term["start"]["precision"],"year")
            self.assertTrue(int(term["start"]["value"]) <= 1685 <= int(term["end"]["value"]))
        self.assertTrue(any(x["person_id"] == sofia["person_id"]
                            and x["assessment_kind"] == "regent"
                            for x in self.canon["power_assessments"]))

    def test_1762_sequential_reigns_are_only_year_overlaps(self):
        terms = {t["id"]:t for t in self.canon["tenures"]}
        ids = ("tenure-r10","tenure-r11","tenure-r12")
        self.assertEqual(len({terms[x]["person_id"] for x in ids}),3)
        for ident in ids:
            t=terms[ident]
            self.assertTrue(int(t["start"]["value"])<=1762<=int(t["end"]["value"]))
            self.assertEqual(t["end"]["precision"],"year")
        roles={r["id"]:r for r in self.net["roles"]}
        self.assertEqual(roles["dn-ru-elizabeth"]["end_gregorian"],"1762-01-05")
        self.assertEqual(
            [roles[x]["canonical_tenure_id"] for x in
             ("dn-ru-elizabeth","dn-ru-peter3","dn-ru-catherine2")],list(ids))
        self.period("year-1762",1762,1762)
        self.assertEqual(self.db.execute(
            "SELECT meaning FROM v2_periods WHERE id='year-1762'").fetchone()[0],
            "observation")

    def test_1788_two_legal_roles_support_union_not_family_equivalence(self):
        george = [r for r in self.net["roles"] if r["person_id"]=="gb-george3"]
        self.assertEqual({x["polity_id"] for x in george},{"gb","han"})
        for c in ("gb","han"): self.context(c)
        self.period("window",1760,1800,"research_window")
        self.db.execute(
            "INSERT INTO v2_external_people VALUES(?,?,?,?,?)",
            ("world-dynasty","gb-george3","George III",None,"unresolved"))
        for r in george:
            claim="claim:"+r["id"]
            self.assertion(claim,r["source_ids"][0])
            self.db.execute("""INSERT INTO v2_roles
                (id,context_id,external_person_origin,external_person_id,
                 title,role_kind,period_id,assertion_id,origin,native_id)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (r["id"],r["polity_id"],"world-dynasty","gb-george3",
                 r["title"],r["role_kind"],"window",claim,"world",r["id"]))
        self.assertion("union-claim","DN03","chronology")
        self.db.execute("""INSERT INTO v2_context_relations
            (id,context_a,context_b,kind,external_person_origin,external_person_id,
             period_id,assertion_id) VALUES(?,?,?,?,?,?,?,?)""",
            ("union-gb-han","gb","han","personal_union",
             "world-dynasty","gb-george3","window","union-claim"))
        self.assertEqual(self.db.execute(
            "SELECT * FROM v2_personal_unions_without_role_candidates").fetchall(),[])
        self.db.execute("DELETE FROM v2_roles WHERE context_id='han'")
        self.assertEqual(self.db.execute(
            "SELECT id FROM v2_personal_unions_without_role_candidates").fetchall(),
            [("union-gb-han",)])
        bourbon=next(h for h in self.houses["families"] if h["id"]=="bourbon")
        names={m["person_id"] for m in bourbon["members"]}
        self.assertTrue({"fr-louis16","es-carlos3"}.issubset(names))

    def test_1795_republic_has_institutions_not_missing_king(self):
        rows=[r for r in self.ext["institutions"] if r["polity_id"]=="frrep"
              and r["start_year"]<=1795<=r["end_year"]]
        self.assertEqual({r["id"] for r in rows},
                         {"ex-fr-convention","ex-fr-directory"})
        self.context("frrep","polity_regime")
        self.context("fr","polity_regime")
        self.period("year-1795",1795,1795)
        for r in rows:
            self.db.execute("INSERT INTO v2_institutions(id,label,kind) VALUES(?,?,?)",
                            (r["id"],r["name"],r["kind"]))
            claim="claim:"+r["id"]
            self.assertion(claim,r["source_ids"][0],"institutional")
            self.db.execute("""INSERT INTO v2_roles
                (id,context_id,institution_id,title,role_kind,period_id,
                 assertion_id,origin,native_id) VALUES(?,?,?,?,?,?,?,?,?)""",
                ("role:"+r["id"],"frrep",r["id"],r["name"],"institutional",
                 "year-1795",claim,"world",r["id"]))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM v2_roles WHERE institution_id IS NOT NULL").fetchone()[0],2)
        policy={p["polity_id"]:p for p in self.coverage["polities"]}
        self.assertEqual(policy["fr"]["historical_end"],1792)
        self.assertEqual(policy["frrep"]["historical_start"],1792)

    def test_1991_law_and_military_evidence_are_not_polygons(self):
        dossier=next(x for x in self.cases["cases"] if x["id"]=="ussr-1991")
        self.assertTrue({"legal","practical","claim","institutional"}.issubset(
            {r["category"] for r in dossier["records"]}))
        obs=dossier["territorial_evidence"]
        self.assertTrue(all(x["geometry_verified"] is False and x["limitation"]
                            and x["sources"] for x in obs))
        self.assertTrue({"law","military"}.issubset({x["nature"] for x in obs}))
        self.context("ussr")
        self.period("year-1991",1991,1991)
        for n,nature in enumerate(("law","military")):
            o=next(x for x in obs if x["nature"]==nature)
            place="test-place:"+str(n)
            self.db.execute("INSERT INTO v2_places(id,label,kind) VALUES(?,?,?)",
                            (place,o["place"],"other"))
            claim="claim:"+str(n)
            self.assertion(claim,o["sources"][0],"legal" if nature=="law" else "practical")
            self.db.execute("""INSERT INTO v2_territorial_observations
                (id,place_id,context_id,nature,authority,period_id,assertion_id)
                VALUES(?,?,?,?,?,?,?)""",
                (o["id"],place,"ussr",nature,o["authority"],"year-1991",claim))
        self.assertEqual(self.db.execute(
            "SELECT nature FROM v2_territorial_observations ORDER BY nature").fetchall(),
            [("law",),("military",)])

    def test_research_gap_not_historical_absence_and_evidence_gate(self):
        tus=next(p for p in self.coverage["polities"] if p["polity_id"]=="tusc")
        self.assertEqual((tus["researched_from"],tus["researched_through"]),(1781,1800))
        self.assertNotIn("historical_end",tus)
        self.context("tusc")
        self.period("tuscany-research",1781,1800,"research_window")
        self.assertion("scope-claim",tus["source_ids"][0],"coverage")
        self.db.execute("""INSERT INTO v2_research_scopes
            (id,context_id,domain,period_id,assertion_id) VALUES(?,?,?,?,?)""",
            ("tos-offices","tusc","formal_offices","tuscany-research","scope-claim"))
        self.assertEqual(self.db.execute(
            "SELECT id FROM v2_assertions_without_sources").fetchall(),[])
        self.db.execute("INSERT INTO v2_assertions VALUES(?,?,?,?,?,?)",
                        ("invalid-unsourced","coverage","Test claim","Cannot export",
                         "not_assessed","unverified"))
        self.assertEqual(self.db.execute(
            "SELECT id FROM v2_assertions_without_sources").fetchall(),
            [("invalid-unsourced",)])


if __name__ == "__main__":
    unittest.main()
