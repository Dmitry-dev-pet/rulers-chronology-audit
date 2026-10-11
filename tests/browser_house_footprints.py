#!/usr/bin/env python3
"""Chromium acceptance: house presence timeline and sourced dynastic branches."""
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
    report=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(
                    viewport={'width':width,'height':height},
                    is_mobile=width<=900,has_touch=width<=900,
                    device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?world=dynasty18&dynYear=1788&dynView=houses#/timeline/1762')
                expect(page.locator('.dynasty-layer')).to_be_visible()
                expect(page.locator('#dynasty-year')).to_have_text('1788')
                expect(page.locator('[data-dynasty-view="houses"]')).to_have_attribute('aria-pressed','true')
                expect(page.locator('.dynasty-footprint-panel')).to_be_visible()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_hidden()
                expect(page.locator('.dynasty-color-controls')).to_be_hidden()
                expect(page.locator('.dynasty-notice')).to_be_hidden()
                if width<=390 and height>=640:
                    chart=page.locator('.dynasty-footprint-scroll').bounding_box()
                    assert chart and chart['y']<height*.75, (width,height,chart)
                expect(page.locator('.dynasty-house-group')).to_have_count(4)
                expect(page.locator('.dynasty-house-year')).to_have_count(5)
                expect(page.locator('.dynasty-house-group[data-family-id="bourbon"] .dynasty-house-row[data-country="fr"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-group[data-family-id="bourbon"] .dynasty-house-row[data-country="es"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="ex-es-carlos3"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="ex-es-carlos4"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="ex-tusc-leopold"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="dn-han-george"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-summary-line').filter(has_text='Бурбоны')).to_contain_text('нескольких государствах')
                expect(page.locator('.dynasty-house-summary-line').filter(has_text='Ганноверский')).to_contain_text('личная уния')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if width<=390 and height>=640:
                    page.wait_for_function("document.querySelector('.dynasty-footprint-scroll').scrollLeft>200")
                page.screenshot(path=str(output/f'house-footprints-1788-{width}.png'),full_page=True)

                page.locator('.dynasty-house-bar[data-role-id="ex-es-carlos4"]').click()
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('Карл IV')
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('Бурбоны')
                expect(page.locator('.dynasty-footprint-detail .dynasty-source').first).to_have_attribute('href',
                    __import__('re').compile(r'^https://'))
                expect(page.locator('#dynasty-year')).to_have_text('1788')

                # The secondary layer is intentionally opt-in. A French Habsburg
                # consort is NOT reported as dynastic sovereignty of France.
                expect(page.locator('.dynasty-house-bar[data-role-id="dn-fr-antoinette-queen"]')).to_have_count(0)
                page.locator('#dynasty-show-secondary').check()
                expect(page.locator('.dynasty-house-bar[data-role-id="dn-fr-antoinette-queen"]')).to_have_count(1)
                expect(page.locator('.dynasty-house-bar[data-role-id="dn-fr-antoinette-queen"]')).to_have_attribute('data-category','extra')
                expect(page.locator('.dynasty-house-summary-line').filter(has_text='Габсбург-Лотарингские')).not_to_contain_text('Франция')

                # Membership from paternal lineage must be visibly distinguished
                # from a direct official house name (the Russian dynasty remains Romanov).
                page.locator('#dynasty-year-range').evaluate("""el=>{
                    el.value='1798';el.dispatchEvent(new Event('input',{bubbles:true}));
                }""")
                expect(page.locator('#dynasty-year')).to_have_text('1798')
                expect(page.locator('.dynasty-house-summary-line').filter(has_text='Гольштейн-Готторпские')).to_contain_text('родственные ветви')
                expect(page.locator('.dynasty-house-bar[data-role-id="ex-ru-paul"]')).to_have_attribute('data-category','lineage')
                expect(page.locator('.dynasty-house-bar[data-role-id="ex-pt-carlota"]')).to_have_attribute('data-category','extra')
                page.locator('.dynasty-house-bar[data-role-id="ex-ru-paul"]').click()
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('Романов')
                expect(page.locator('.dynasty-footprint-detail')).to_contain_text('Генеалогическая ветвь')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/f'house-footprints-1798-{width}.png'),full_page=True)

                page.locator('[data-dynasty-view="network"]').click()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_visible()
                expect(page.locator('.dynasty-footprint-panel')).to_be_hidden()
                assert 'dynView=houses' not in page.url
                page.locator('[data-dynasty-view="houses"]').click()
                expect(page.locator('.dynasty-footprint-panel')).to_be_visible()
                assert 'dynView=houses' in page.url
                page.go_back()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_visible()
                page.go_forward()
                expect(page.locator('.dynasty-footprint-panel')).to_be_visible()
                expect(page.locator('#dynasty-year')).to_have_text('1798')

                page.keyboard.press('Escape')
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                assert 'world=dynasty18' not in page.url
                assert 'dynView=houses' not in page.url
                assert not errors, errors
                report.append({
                    'viewport':[width,height],
                    'dynasties':4,
                    'years':[1788,1798],
                    'features':['separate powers','personal union','branch lineage','optional consorts',
                                'source citations','deep link','mobile pan'],
                    'status':'passed','javascript_errors':errors
                })
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/'house-footprints-receipt.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    opts=parser.parse_args()
    run(opts.dist,opts.output)
