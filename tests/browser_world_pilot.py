#!/usr/bin/env python3
"""International year-1762 SPA pilot browser acceptance in Chromium."""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run(dist:Path, output:Path):
    output.mkdir(parents=True,exist_ok=True)
    srv=http.server.ThreadingHTTPServer(
        ('127.0.0.1',0),functools.partial(Handler,directory=str(dist.resolve())))
    threading.Thread(target=srv.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{srv.server_port}/'
    results=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in [(1440,960),(390,844),(320,640)]:
                page=browser.new_page(viewport={'width':width,'height':height},
                                       is_mobile=width<=900,has_touch=width<=900)
                errors=[]
                page.on('pageerror',lambda exc:errors.append(str(exc)))
                page.goto(origin+'?world=1762#/timeline/1762')
                expect(page.locator('.atlas-world-layer')).to_be_visible()
                expect(page.locator('#atlas-world-title')).to_have_text('Европа · 1762')
                expect(page.locator('.atlas-world-country')).to_have_count(3)
                expect(page.locator('.atlas-world-person')).to_have_count(4)
                expect(page.locator('.atlas-world-graph-scroll svg')).to_be_visible()
                expect(page.locator('.atlas-world-relation')).to_have_count(2)
                expect(page.locator('.atlas-world-person').filter(has_text='Екатерина II')).to_contain_text('Штеттин')
                expect(page.locator('.atlas-world-person').filter(has_text='Пётр III')).to_contain_text('Киль')
                expect(page.locator('.atlas-world-country-grid')).to_contain_text('Людовик XV')
                expect(page.locator('.atlas-world-country-grid')).to_contain_text('Фридрих II')
                expect(page.locator('.atlas-world-citations a').first).to_have_attribute('href',
                    __import__('re').compile(r'^https://'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert page.locator('.atlas-world-mode').first.bounding_box()['height']>=43.5
                page.screenshot(path=str(output/f'world-1762-states-{width}.png'),full_page=True)

                page.locator('[data-world-mode="origin"]').click()
                expect(page.locator('[data-world-mode="origin"]')).to_have_attribute('aria-pressed','true')
                expect(page.locator('.atlas-world-status')).to_contain_text('этнокультурное')
                expect(page.locator('.atlas-world-person').filter(has_text='Екатерина II')).to_contain_text('Немецкое княжеское происхождение')
                for name in ('Пётр III','Людовик XV','Фридрих II'):
                    expect(page.locator('.atlas-world-person').filter(has_text=name)).to_contain_text('Не исследовано')
                page.screenshot(path=str(output/f'world-1762-origin-{width}.png'),full_page=True)

                page.locator('[data-world-mode="dynasty"]').click()
                expect(page.locator('[data-world-mode="dynasty"]')).to_have_attribute('aria-pressed','true')
                for dynasty in ('Бурбоны','Гогенцоллерны','Гольштейн-Готторп','Ангальт-Цербстский'):
                    expect(page.locator('.atlas-world-country-grid')).to_contain_text(dynasty)
                page.screenshot(path=str(output/f'world-1762-dynasties-{width}.png'),full_page=True)
                page.keyboard.press('Escape')
                expect(page.locator('.atlas-world-layer')).to_be_hidden()
                assert 'world=1762' not in page.url

                # An existing arbitrary year remains intact on entering and leaving.
                page.goto(origin+'#/timeline/1685')
                expect(page.locator('#atlas-year-value')).to_have_text('1685')
                page.locator('.atlas-year-world-link').click()
                expect(page.locator('.atlas-world-layer')).to_be_visible()
                assert 'world=1762' in page.url
                page.locator('.atlas-world-close').click()
                expect(page.locator('.atlas-world-layer')).to_be_hidden()
                expect(page.locator('#atlas-year-value')).to_have_text('1685')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert not errors, errors
                results.append({'viewport':[width,height],'people':4,'countries':3,
                                'modes':['state','origin','dynasty'],'status':'passed',
                                'errors':errors})
                page.close()
            browser.close()
    finally:
        srv.shutdown()
        srv.server_close()
    (output/'world-pilot-receipt.json').write_text(
        json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    args=parser.parse_args()
    run(args.dist,args.output)
