#!/usr/bin/env python3
"""Deterministic browser regression: generic atlas works across all 575 years.
Run after build, from a local HTTP origin; no public API and no browser tokens.
"""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import re
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def check(dist: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0),
        functools.partial(QuietHandler, directory=str(dist.resolve())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}/'
    completed = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width, height in [(1440,1000), (390,844), (768,1024), (844,390)]:
                page = browser.new_page(viewport={'width':width,'height':height})
                errors = []
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin + '#/timeline/1685')
                expect(page.locator('#atlas-year-value')).to_have_text('1685')
                expect(page.locator('.atlas-global-controls')).to_be_visible()
                expect(page.locator('.atlas-global-century')).to_have_count(5)
                if width<=900:
                    # Desktop header actions are intentionally hidden on a
                    # phone; the persistent mobile action opens the SAME pane.
                    page.locator('.atlas-mobile-action[data-mobile-action="overview"]').click()
                else:
                    page.locator('.atlas-global-open').filter(has_text='Обзор веков').click()
                expect(page.locator('.atlas-global-sheet')).to_be_visible()
                expect(page.locator('.atlas-global-century-card')).to_have_count(5)
                expect(page.locator('.atlas-global-coverage-row')).to_have_count(20)
                for period in page.locator('.atlas-global-century-card').all():
                    expect(period.locator('.atlas-global-coverage-row')).to_have_count(4)
                expect(page.locator('.atlas-global-sheet-body')).to_contain_text(
                    'отражают лишь годы')
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
                page.screenshot(path=str(output / f'universal-overview-{width}.png'),
                                full_page=True)
                # Comparison must render two different legal/influence/group data
                # windows, not accidentally merge the records for the two years.
                page.locator('.atlas-global-tab').filter(has_text='Сравнить годы').click()
                expect(page.locator('.atlas-global-compare-columns')).to_be_visible()
                expect(page.locator('.atlas-global-year-column')).to_have_count(2)
                if width<=900:
                    expect(page.locator('.atlas-mobile-compare-tab')).to_have_count(3)
                    expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_be_visible()
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_hidden()
                    page.locator('.atlas-mobile-compare-tab[data-tab="b"]').click()
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_visible()
                    page.locator('.atlas-mobile-compare-tab[data-tab="diff"]').click()
                    expect(page.locator('.atlas-mobile-differences')).to_be_visible()
                    expect(page.locator('.atlas-mobile-diff-group')).to_have_count(4)
                    expect(page.locator('.atlas-mobile-differences')).to_contain_text('НЕ доказательство')
                    page.locator('.atlas-mobile-compare-tab[data-tab="a"]').click()
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_contain_text('Иван')
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_contain_text('Пётр')
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_contain_text('Софья')
                expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_contain_text('Маленков')
                expect(page.locator('.atlas-global-year-group')).to_have_count(8)  # four per year
                expect(page.locator('.atlas-global-unverified')).not_to_have_count(0)
                refs = page.locator('.atlas-global-sources a')
                expect(refs).not_to_have_count(0)
                for i in range(min(4,refs.count())):
                    href=refs.nth(i).get_attribute('href')
                    assert href.startswith('https://'),href
                    assert 'drive.google.com' not in href,href
                page.screenshot(path=str(output / f'universal-compare-{width}.png'),
                                full_page=True)
                # The comparison is linkable: it survives reload and browser Back.
                page.locator('.atlas-global-preset[data-left="1917"][data-right="1991"]').click()
                expect(page.locator('.atlas-global-year-column[data-year="1917"]')).to_be_visible()
                if width<=900:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_hidden()
                else:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_visible()
                expect(page).to_have_url(re.compile('atlasYears=1917%2C1991'))
                permalink=page.url
                page.reload()
                expect(page).to_have_url(permalink)
                expect(page.locator('.atlas-global-year-column[data-year="1917"]')).to_be_visible()
                if width<=900:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_hidden()
                else:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_visible()
                page.go_back()
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_be_visible()
                if width<=900:
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_hidden()
                else:
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_visible()
                # Changing one comparison year does not create an inferred ruler.
                first=page.get_by_role('spinbutton',name='Первый год')
                first.fill('1812')
                first.press('Tab')
                expect(page.locator('.atlas-global-year-column[data-year="1812"]')).to_be_visible()
                if width<=900:
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_hidden()
                else:
                    expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_visible()
                # Return to canonical timeline; no stale comparison URL or new
                # route incompatible with the existing 4-tab SPA.
                page.locator('.atlas-global-year-jump[data-year="1812"]').click()
                expect(page.locator('.atlas-global-sheet')).to_be_hidden()
                expect(page.locator('#atlas-year-value')).to_have_text('1812')
                expect(page).to_have_url(re.compile(r'#/timeline/1812$'))
                assert 'atlasView=' not in page.url
                # The deep link can also be opened directly, independent of
                # prior navigation or which century was last selected.
                page.goto(origin + '?atlasView=compare&atlasYears=1917%2C1991#/timeline/1917')
                expect(page.locator('.atlas-global-year-column[data-year="1917"]')).to_be_visible()
                if width<=900:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_hidden()
                else:
                    expect(page.locator('.atlas-global-year-column[data-year="1991"]')).to_be_visible()
                page.locator('.atlas-global-close').click()
                expect(page.locator('.atlas-global-sheet')).to_be_hidden()
                assert 'atlasView=' not in page.url
                # Small landscape may hide century pills to preserve reading
                # height; the same overview remains available through buttons.
                if height>560:
                    page.locator('.atlas-global-century[data-start="1700"]').click()
                    expect(page.locator('#atlas-year-value')).to_have_text('1750')
                    expect(page).to_have_url(re.compile(r'#/timeline/1750$'))
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
                assert not errors,errors
                completed.append({'viewport':[width,height],
                    'overview_centuries':5,'coverage_categories':4,
                    'compare_years':'1685/1953 + 1917/1991 + 1812',
                    'status':'passed','js_errors':errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
    (output/'universal-receipt.json').write_text(
        json.dumps(completed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(completed,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    args=parser.parse_args()
    check(args.dist,args.output)
