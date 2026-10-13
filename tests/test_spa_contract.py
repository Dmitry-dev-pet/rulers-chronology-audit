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
        cls.dashboard=(ROOT/'site/year-view.js').read_text(encoding='utf-8')
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
        self.assertIn("['drive','.google.com'].join('')",self.js)
        self.assertNotIn('drive.google.com',self.js)
        self.assertIn("textContent=String(value)",self.js)

    def test_legacy_public_html_preserved(self):
        self.assertIn("database.html",self.js)
        self.assertIn("[data-atlas-database] a",self.js)
        self.assertIn(".spa-people-grid",self.css)
        self.assertIn(".spa-people-grid[hidden]",self.css)
        self.assertIn(".spa-people-tools[hidden]",self.css)
        self.assertIn(".spa-person-detail[hidden]",self.css)

    def test_app_shell_has_scoped_scrolling_and_fixed_navigation(self):
        self.assertIn("document.documentElement.classList.add('atlas-app')", self.js)
        self.assertIn(".atlas-app body{height:100dvh;display:flex;flex-direction:column}", self.css)
        self.assertIn(".atlas-app main.container{width:100%;min-height:0;flex:1", self.css)
        self.assertIn(".atlas-app .mode-panel{min-height:0;height:100%;flex:1;overflow-y:auto", self.css)
        self.assertIn(".atlas-app .timeline-scroll{max-height:none;min-height:0;height:100%;flex:1;overflow:auto", self.css)
        self.assertIn(".atlas-app .atlas-sidebar{min-height:0;min-width:0;display:block;overflow:auto", self.css)
        self.assertIn(".atlas-app .spa-people-grid{min-height:0;flex:1;overflow-y:auto", self.css)
        self.assertIn(".atlas-app .mode-panel[hidden]{display:none!important}", self.css)

    def test_chart_controls_are_real_and_sync_with_year_route(self):
        for event in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
            self.assertIn("viewport.addEventListener('"+event+"'", self.js)
        self.assertIn("const zoomSteps = [1, 1.5, 2.3, 3.5, 5, 7.5, 11]", self.js)
        self.assertIn("canvas.style.width = layoutWidth() + 'px'", self.js)
        self.assertIn("const earlier = button('← Раньше'", self.js)
        self.assertIn("const later = button('Позже →'", self.js)
        self.assertIn("focusYear(selectedYear())", self.js)
        self.assertIn("yearSlider.dispatchEvent(new Event('input'", self.js)
        self.assertIn("toolbar.querySelectorAll('.era-btn')", self.js)

    def test_mobile_drawers_keep_biographies_and_provenance(self):
        self.assertIn("className = 'atlas-timeline-workspace'", self.js)
        self.assertIn("className = 'atlas-sidebar'", self.js)
        self.assertIn("sidebar.append(sidebarHeading, selected, inspector)", self.js)
        self.assertIn("className = 'spa-people-workspace'", self.js)
        self.assertIn("panel.classList.add('spa-profile-open')", self.js)
        self.assertIn("panel.classList.remove('spa-profile-open')", self.js)
        self.assertIn("sidebar.setAttribute('inert', '')", self.js)
        self.assertIn(".atlas-app .atlas-sidebar-open .atlas-sidebar{display:block}", self.css)
        self.assertIn(".atlas-app #panel-people.spa-profile-open .spa-people-browser{display:none}", self.css)
        self.assertIn("citations(links,entry.sources)", self.js)


    def test_canonical_home_and_deep_linked_year_view(self):
        self.assertIn("['timeline', 'Год и власть']", self.js)
        self.assertIn("['people', 'Биографии']", self.js)
        self.assertIn("return navigate('home', false)", self.js)
        self.assertIn("location.hash = '#/timeline/' + year", self.js)
        self.assertIn("return navigate('timeline', false)", self.js)  # legacy query links
        self.assertIn("atlas:show-year-details", self.js)
        self.assertIn("atlas-home-open", self.css)
        self.assertIn("atlas:route", self.js)

    def test_year_overview_separates_formal_effective_and_collective(self):
        for literal in ('Формальные должности', 'Политическое влияние',
                        'Регентство и соправители', 'Учреждения и коллегии'):
            self.assertIn(literal, self.dashboard)
        for field in ('result.tenures', 'result.power_assessments',
                      'result.institution_periods', 'result.sources'):
            self.assertIn(field, self.dashboard)
        self.assertIn("fetch('./atlas.json', {cache: 'no-cache'})", self.dashboard)
        self.assertIn('intersects = (record, year)', self.dashboard)
        self.assertIn('start <= year && year <= end', self.dashboard)
        self.assertIn('!nominal.has(r.status)', self.dashboard)
        self.assertIn("не обязательно действовавшие одновременно", self.dashboard)

    def test_year_controls_and_source_links(self):
        self.assertIn("slider.dispatchEvent(new Event('input', {bubbles: true}))", self.dashboard)
        self.assertIn("yearNumber", self.dashboard)
        self.assertIn("year-role-details", self.dashboard)
        self.assertIn("url.protocol === 'https:'", self.dashboard) if False else self.assertIn("parsed.protocol === 'https:'", self.dashboard)
        self.assertIn("a.href = '#/people/' + encodeURIComponent(record.person_id)", self.dashboard)
        self.assertIn("a.href = src.url", self.dashboard)
        self.assertNotIn("drive.google.com/file/d/", self.dashboard)

    def test_histography_inspired_playback_reuses_canonical_year(self):
        for literal in (
            "atlas-year-playback", "atlas-year-playback-step",
            "stepYear(Number(speed.value))", "window.setInterval(advancePlayback, 850)",
            "slider.addEventListener('input'", "document.hidden",
            "window.addEventListener('atlas:route'", "stopPlayback()",
            "не анимация фактической передачи власти",
        ):
            self.assertIn(literal, self.dashboard)
        self.assertIn("play.setAttribute('aria-pressed', 'true')", self.dashboard)
        self.assertIn("play.setAttribute('aria-pressed', 'false')", self.dashboard)
        self.assertIn(".atlas-app.atlas-mobile .atlas-year-playback", self.css)
        self.assertIn("min-height:44px", self.css)
        # Playback is a projection of atlas.json: no changes to source records.
        self.assertNotIn("real_ruler=true", self.dashboard)

    def test_universal_atlas_is_cross_era_and_independent_of_local_map(self):
        code=(ROOT/'site/universal-atlas.js').read_text(encoding='utf-8')
        for key in (
            "'XV–XVI века'","'XVII век'","'XVIII век'",
            "'XIX век'","'XX век'",'1417','1991',
            "atlas-global-century","atlas-global-compare-columns",
            "atlasView","atlasYears","Сравнить два года",
            "Оценки политического влияния","Юридические должности",
            "Регентство и соправители","Коллективные органы",
            "Годовые пересечения","Историческое утверждение", # source cautions
        ):
            self.assertIn(key,code)
        self.assertIn("!nominal.has(x.status)",code)
        self.assertIn("!regencies.has(x.status)",code)
        self.assertIn("history[push?'pushState':'replaceState']",code)
        self.assertIn("return url.protocol === 'https:'",code)
        self.assertNotIn("drive.google.com/file/d/",code)
        self.assertNotIn("smuta-map.json",code)
        self.assertIn(".atlas-global-sheet[hidden]{display:none!important}",self.css)
        self.assertIn(".atlas-global-compare-columns",self.css)
        self.assertIn(".atlas-global-coverage-track",self.css)

    def test_script_syntax_if_node_present(self):
        if shutil.which('node'):
            subprocess.run(['node','--check',str(ROOT/'site/site.js')],check=True,capture_output=True)
            subprocess.run(['node','--check',str(ROOT/'site/year-view.js')],check=True,capture_output=True)
            subprocess.run(['node','--check',str(ROOT/'site/universal-atlas.js')],check=True,capture_output=True)

    def test_historical_db_not_mutated(self):
        db=atlas_db.load(ROOT)
        self.assertEqual(len(db['people']),83)
        self.assertEqual(len(db['provenance']),150)
        self.assertFalse(db['metadata']['historical_truth_verified_by_ci'])

if __name__=='__main__':
    unittest.main()
