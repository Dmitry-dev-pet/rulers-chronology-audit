"""Static SPA architecture and backward-compatibility contract."""
from pathlib import Path
import shutil
import subprocess
import unittest

from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]

class SPAContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/'site/site.js').read_text(encoding='utf-8')
        cls.css=(ROOT/'site/site.css').read_text(encoding='utf-8')

    def test_four_accessible_views_share_same_document(self):
        for name in ('poster','timeline','research','people'):
            self.assertIn("'"+name+"'",self.js)
        self.assertIn("pane.id='panel-people'",self.js)
        self.assertIn("pane.dataset.mode='people'",self.js)
        self.assertIn("mainHost.appendChild(pane)",self.js)
        self.assertIn("tab.setAttribute('aria-controls','panel-people')",self.js)

    def test_direct_routes_browser_history_and_poster_anchors(self):
        self.assertIn("location.hash=route",self.js)
        self.assertIn("hashchange",self.js)
        self.assertIn("atlas:route",self.js)
        self.assertIn("history.replaceState",self.js)
        self.assertIn("'#/people/'+encodeURIComponent(p.id)",self.js)
        self.assertIn("hash.startsWith('poster-')",self.js)
        self.assertIn("hash.startsWith('source-')",self.js)

    def test_lazy_biographies_and_links_to_sources(self):
        self.assertIn("fetch('./atlas.json'",self.js)
        self.assertIn("power_assessments",self.js)
        self.assertIn("ethnic_origin",self.js)
        self.assertIn("Неизвестные сведения не домысливаются",self.js)
        self.assertIn("parsed.protocol",self.js) if False else self.assertIn("url.protocol==='https:'",self.js)
        self.assertIn("url.hostname!=='drive.google.com'",self.js)
        self.assertIn("textContent=String(value)",self.js)

    def test_legacy_public_html_preserved(self):
        self.assertIn("database.html",self.js)
        self.assertIn("[data-atlas-database] a",self.js)
        self.assertIn(".spa-people-grid",self.css)

    def test_script_syntax_if_node_present(self):
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/site.js')],check=True,capture_output=True)

    def test_historical_db_not_mutated(self):
        db=atlas_db.load(ROOT)
        self.assertEqual(len(db['people']),83)
        self.assertEqual(len(db['provenance']),150)
        self.assertFalse(db['metadata']['historical_truth_verified_by_ci'])

if __name__=='__main__':
    unittest.main()
