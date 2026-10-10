#!/usr/bin/env python3
"""Deterministic Chromium E2E against the actual built SPA, not an LLM report.

Usage: python tests/browser_smuta_map.py --dist dist --output browser-evidence
Requires playwright (browser only; production site has no dependencies).
"""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def check(dist: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}/'
    reports=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for w,h in [(1440,1000),(390,844),(768,1024),(844,390)]:
                page=browser.new_page(viewport={'width':w,'height':h})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?map=smuta#/timeline/1608')
                expect(page.locator('.smuta-evidence')).to_have_count(5)
                expect(page.locator('.smuta-workspace')).to_be_visible()
                expect(page.locator('#atlas-year-value')).to_have_text('1608')
                expect(page.locator('.smuta-water path[data-water]')).not_to_have_count(0)
                expect(page.locator('.smuta-water path[data-water]')).to_have_count(41)
                expect(page.locator('.smuta-water-source a')).to_have_attribute('href',__import__('re').compile('natural-earth-vector'))
                page.locator('#smuta-water-toggle').uncheck()
                expect(page.locator('.smuta-water path[data-water]')).to_have_count(0)
                page.locator('#smuta-water-toggle').check()
                expect(page.locator('.smuta-water path[data-water]')).to_have_count(41)
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
                # A source page is NOT requested by clicking a map pin.
                page.screenshot(path=str(output/f'map-{w}.png'),full_page=True)
                page.locator('.smuta-marker[data-place="yaroslavl"]').click()
                expect(page.locator('.smuta-evidence')).to_have_count(1)
                expect(page.locator('.smuta-evidence h3')).to_contain_text('Ярославль')
                expect(page).to_have_url(__import__('re').compile('place=yaroslavl'))
                page.reload()
                expect(page.locator('.smuta-evidence')).to_have_count(1)
                # Same city, four years later: different evidence, no carry-forward.
                slider=page.locator('#atlas-year-range');slider.focus()
                for _ in range(4):slider.press('ArrowRight')
                expect(page.locator('#atlas-year-value')).to_have_text('1612')
                expect(page.locator('.smuta-evidence')).to_have_count(1)
                expect(page.locator('.smuta-evidence')).to_contain_text('Совет всея земли')
                page.screenshot(path=str(output/f'city-{w}.png'),full_page=True)
                # A missing year MUST be an evidence gap, never retained control.
                slider.focus();slider.press('ArrowLeft')
                expect(page.locator('#atlas-year-value')).to_have_text('1611')
                expect(page.locator('.smuta-evidence')).to_have_count(0)
                expect(page.locator('.smuta-empty')).to_contain_text('пробел в исследовании')
                page.locator('#smuta-all-period').check()
                expect(page.locator('.smuta-evidence')).to_have_count(2)
                expect(page.locator('.smuta-status')).to_contain_text('Весь период')
                # Query-only history navigation changes city without reload.
                # Inspect parallel centers without inventing a multi-year reign.
                slider.focus()
                for _ in range(3):slider.press('ArrowLeft')
                expect(page.locator('#atlas-year-value')).to_have_text('1608')
                page.locator('.smuta-mode-compare').click()
                expect(page.locator('.smuta-comparison-lead h3')).to_have_text('Центры власти · 1608')
                expect(page.locator('.smuta-comparison-legal')).to_contain_text('Василий')
                expect(page.locator('.smuta-center-observation')).to_have_count(5)
                expect(page.locator('.smuta-mode-compare')).to_have_attribute('aria-pressed','true')
                expect(page).to_have_url(__import__('re').compile('compare=1'))
                slider.focus()
                for _ in range(2):slider.press('ArrowRight')
                expect(page.locator('.smuta-comparison-lead h3')).to_have_text('Центры власти · 1610')
                expect(page.locator('.smuta-comparison-legal')).to_contain_text('Шуйский')
                expect(page.locator('.smuta-center-observation')).to_have_count(3)
                expect(page.locator('.smuta-comparison-legal')).not_to_contain_text('Владислав')
                expect(page.locator('.smuta-center-observation').filter(has_text='Владислав')).to_have_count(1)
                page.screenshot(path=str(output/f'compare-{w}.png'),full_page=True)
                page.locator('.smuta-mode-evidence').click()
                expect(page.locator('.smuta-mode-evidence')).to_have_attribute('aria-pressed','true')
                page.locator('#smuta-city').select_option('moscow')
                page.locator('#smuta-all-period').check()
                expect(page.locator('.smuta-evidence')).to_have_count(4)
                page.go_back();expect(page.locator('#smuta-city')).to_have_value('yaroslavl')
                expect(page.locator('.smuta-evidence')).to_have_count(2)
                # Unlocated multi-city claim remains visible, without a fake polygon.
                page.locator('#smuta-city').select_option('unlocated')
                expect(page.locator('.smuta-evidence')).to_have_count(1)
                expect(page.locator('.smuta-unlocated')).to_be_visible()
                page.locator('.smuta-return').click()
                expect(page.locator('.smuta-workspace')).to_be_hidden()
                expect(page.locator('.atlas-timeline-workspace')).to_be_visible()
                assert not errors,errors
                reports.append({'viewport':[w,h],'status':'passed','js_errors':errors})
                page.close()
            # Reproduce the previously inconclusive 1991 filter test using DOM selectors.
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.goto(origin+'#/timeline/1991')
            page.get_by_role('button',name='1991 · СССР',exact=True).click()
            page.get_by_role('button',name='География власти · 9',exact=True).click()
            for key,n in [('all',9),('law',7),('military',1),('all',9)]:
                page.locator(f'.atlas-transition-filter[data-filter="{key}"]').click()
                expect(page.locator('.atlas-geo-entry')).to_have_count(n)
                expect(page.locator(f'.atlas-transition-filter[data-filter="{key}"]')).to_have_attribute('aria-pressed','true')
            reports.append({'regression':'1991 filters 9/7/1/9','status':'passed'})
            browser.close()
    finally:server.shutdown()
    (output/'receipt.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(reports,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dist',type=Path,default=Path('dist'));parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    a=parser.parse_args();check(a.dist,a.output)
