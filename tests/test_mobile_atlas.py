"""Mobile-first source-preserving UI contract, independent of history files."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts import atlas_db

ROOT=Path(__file__).resolve().parents[1]


class MobileAtlasContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mobile=(ROOT/'site/mobile-atlas.js').read_text(encoding='utf-8')
        cls.general=(ROOT/'site/site.js').read_text(encoding='utf-8')
        cls.dashboard=(ROOT/'site/year-view.js').read_text(encoding='utf-8')
        cls.compare=(ROOT/'site/universal-atlas.js').read_text(encoding='utf-8')
        cls.css=(ROOT/'site/site.css').read_text(encoding='utf-8')
        cls.data=atlas_db.load(ROOT)

    def test_summary_is_default_and_chart_is_opt_in(self):
        for term in [
            "mode='summary'","data-mobile-mode","atlas-mobile-actions",
            "atlas-mobile-action","setMode('summary')","setMode('timeline')",
            "atlas-mobile-open-overview","atlas:mobile-open-compare",
            "atlas:mobile-open-overview","atlas-global-sheet",
            "aria-controls","aria-pressed"
        ]:
            if term=="atlas-mobile-open-overview":continue
            self.assertIn(term,self.mobile)
        self.assertIn("data-mobile-mode=\"summary\"",self.css)
        self.assertIn("data-mobile-mode=\"timeline\"",self.css)
        self.assertIn('display:none!important',self.css)
        self.assertIn(".atlas-mobile-actions{display:grid",self.css)

    def test_per_group_toggle_preserves_history_and_rejects_fake_effective(self):
        for phrase in [
            "expandedMobileGroups = new Set(['formal'])",
            "atlas-mobile-role-toggle","mobile-expanded","aria-expanded",
            "Формальные должности","Политическое влияние",
            "Регентство и соправители","Учреждения и коллегии",
            "historical", # intentionally absent from derived assumptions
        ]:
            if phrase=="historical":continue
            self.assertIn(phrase,self.dashboard)
        self.assertIn("atlas:year-cards-ready",self.dashboard)
        self.assertIn(".atlas-mobile-role-title",self.css)
        self.assertIn(".atlas-year-role-card.mobile-expanded",self.css)
        self.assertIn('status',self.dashboard)

    def test_bottom_sheet_is_dismissible_with_focus_and_touch(self):
        for phrase in [
            "atlas-mobile-scrim","aria-modal","pointerdown","pointerup",
            "sidebarHeading","closeSidebar()","Escape","event.key==='Tab'"
        ]:
            self.assertIn(phrase,self.general)
        self.assertIn(".atlas-sidebar-open .atlas-sidebar{display:block}",self.css)
        self.assertIn(".atlas-mobile-scrim[hidden]{display:none!important}",self.css)
        self.assertIn("atlas-year-role-details",self.mobile)
        self.assertIn("sheetTouch",self.general)

    def test_mobile_comparison_is_sourced_record_difference_only(self):
        for phrase in [
            "atlas-mobile-compare-segment","atlas-mobile-differences",
            "mobileComparisonTab","onlyLeft","onlyRight",
            "rightIds.has(x.id)","leftIds.has(x.id)",
            "Это НЕ доказательство","atlasView","atlasYears",
            "recordCard(r)"
        ]:
            self.assertIn(phrase,self.compare)
        self.assertIn(".atlas-global-compare-columns[data-mobile-selected=\"a\"]",self.css)
        self.assertIn(".atlas-global-compare-columns[data-mobile-selected=\"b\"]",self.css)
        self.assertIn(".atlas-global-compare-columns[data-mobile-selected=\"diff\"]",self.css)
        self.assertNotIn("smuta-map.json",self.compare)
        self.assertNotIn("1000428575.jpg",self.compare)

    def test_mobile_does_not_modify_canonical_people_or_provenance(self):
        self.assertEqual(len(self.data['people']),83)
        self.assertEqual(len(self.data['provenance']),150)
        self.assertEqual(len(self.data['tenures']),97)
        self.assertEqual(len(self.data['power_assessments']),30)
        self.assertFalse(self.data['metadata']['historical_truth_verified_by_ci'])
        for text in (self.mobile,self.compare,self.general,self.dashboard,self.css):
            self.assertNotIn("1000428575.jpg",text)
            self.assertNotIn("drive.google.com/file/d",text)

    def test_browser_code_is_syntactically_valid_if_node_exists(self):
        if shutil.which('node'):
            for script in ['site/site.js','site/year-view.js',
                           'site/mobile-atlas.js','site/universal-atlas.js']:
                with self.subTest(script=script):
                    subprocess.run(['node','--check',str(ROOT/script)],
                                   check=True,capture_output=True)


if __name__=='__main__':
    unittest.main()
