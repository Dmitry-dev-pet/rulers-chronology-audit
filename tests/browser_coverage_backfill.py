#!/usr/bin/env python3
"""Real Chromium acceptance: restored eighteenth-century European ruler coverage."""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import expect, sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def run(dist:Path, output:Path):
    output.mkdir(parents=True,exist_ok=True)
    server=http.server.ThreadingHTTPServer(
        ('127.0.0.1',0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}/'
    results=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for w,h in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(viewport={'width':w,'height':h},
                                      is_mobile=w<=900,has_touch=w<=900)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?world=dynasty18&dynYear=1762&dynView=houses#/timeline/1762')
                expect(page.locator('.dynasty-layer')).to_be_visible()
                expect(page.locator('#dynasty-year')).to_have_text('1762')
                expect(page.locator('.dynasty-footprint-panel')).to_be_visible()
                expect(page.locator('.dynasty-house-group')).to_have_count(6)
                expect(page.locator('.dynasty-house-group[data-family-id="braganza"]')).to_be_visible()
                expect(page.locator('.dynasty-house-group[data-family-id="hohenzollern"]')).to_be_visible()
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-pt-jose1"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-es-carlos3-early"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-sw-adolf"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-tusc-francis"]')).to_have_count(0)
                page.locator('#dynasty-show-secondary').check()
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-tusc-francis"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-tusc-francis"]')).to_have_attribute('data-category','extra')
                page.locator('#dynasty-show-secondary').uncheck()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

                page.locator('[data-dynasty-view="network"]').click()
                expect(page.locator('.dynasty-polity')).to_have_count(12)
                expect(page.locator('.dynasty-person')).to_have_count(12)
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл III')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Жозе I')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Адольф Фредрик')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Франц')
                expect(page.locator('.dynasty-graph-scroll svg g[data-actor-id="pt-jose1"]')).to_have_count(1)
                expect(page.locator('.dynasty-country-button[data-country="es"]')).to_have_count(1)
                if w<=390 and h>=640:
                    page.screenshot(path=str(output/f'coverage-1762-{w}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1771"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1771')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Густав III')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Адольф Фредрик')
                expect(page.locator('.dynasty-events')).to_contain_text('1771')

                page.locator('.dynasty-milestone[data-year="1777"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1777')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Жозе I')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Мария I')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Педру III')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('король-супруг')
                expect(page.locator('.dynasty-events')).to_contain_text('1777')
                page.screenshot(path=str(output/f'coverage-1777-{w}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1790"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1790')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Леопольд II')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Фердинанд III')
                expect(page.locator('.dynasty-person[data-person-id="tusc-ferdinand3"]')).to_have_count(1)

                page.locator('.dynasty-milestone[data-year="1799"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1799')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Фердинанд III')
                expect(page.locator('.dynasty-events')).to_contain_text('изгнан')
                page.locator('[data-dynasty-view="houses"]').click()
                expect(page.locator('.dynasty-house-bar[data-role-id="bg-tusc-ferdinand"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-summary-line').filter(has_text='Габсбург-Лотарингские')).to_contain_text('нескольких государствах')
                page.locator('.dynasty-house-bar[data-role-id="bg-tusc-ferdinand"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('Фердинанд III')
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('1790–1799')
                assert page.locator('.dynasty-footprint-detail .dynasty-source').count()>=3
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/f'coverage-1799-{w}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1800"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1800')
                page.locator('[data-dynasty-view="network"]').click()
                expect(page.locator('.dynasty-person[data-person-id="tusc-ferdinand3"]')).to_have_count(0)
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('После 1799')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Мария I')
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл IV')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.keyboard.press('Escape')
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                assert not errors,errors
                results.append({'viewport':[w,h],
                                'restored_polities':['es','pt','sw','tusc'],
                                'dynastic_houses':6,'years':[1762,1771,1777,1790,1799,1800],
                                'status':'passed','javascript_errors':errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/'coverage-backfill-receipt.json').write_text(
        json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--dist',type=Path,default=Path('dist'))
    ap.add_argument('--output',type=Path,default=Path('browser-evidence'))
    args=ap.parse_args()
    run(args.dist,args.output)
