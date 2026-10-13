#!/usr/bin/env python3
"""Chromium acceptance for historical European dynastic graph (no outside assets)."""
from __future__ import annotations
import argparse
import functools
import http.server
import json
import re
import threading
from pathlib import Path
from playwright.sync_api import expect,sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


def run(dist:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    server=http.server.ThreadingHTTPServer(
        ('127.0.0.1',0),
        functools.partial(QuietHandler,directory=str(dist.resolve()))
    )
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}/'
    report=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            for width,height in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(viewport={'width':width,'height':height},
                    is_mobile=width<=900,has_touch=width<=900,device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?world=dynasty18&dynYear=1762#/timeline/1762')
                expect(page.locator('.dynasty-layer')).to_be_visible()
                expect(page.locator('#dynasty-title')).to_have_text('Династические связи Европы')
                expect(page.locator('#dynasty-year')).to_have_text('1762')
                expect(page.locator('.dynasty-polity')).to_have_count(12)
                expect(page.locator('.dynasty-person')).to_have_count(12)
                expect(page.locator('.dynasty-office')).to_have_count(15)
                expect(page.locator('.dynasty-graph-scroll svg')).to_be_visible()
                expect(page.locator('.dynasty-person[data-person-id="ru-elizabeth"]')).to_contain_text('Елизавета')
                expect(page.locator('.dynasty-person[data-person-id="ru-peter3"]')).to_contain_text('Пётр III')
                expect(page.locator('.dynasty-person[data-person-id="ru-catherine2"]')).to_contain_text('Екатерина II')
                expect(page.locator('.dynasty-polity[data-polity="gb"]')).to_contain_text('Георг III')
                expect(page.locator('.dynasty-polity[data-polity="han"]')).to_contain_text('Георг III')
                expect(page.locator('.dynasty-person[data-person-id="gb-george3"]')).to_have_count(1)
                expect(page.locator('.dynasty-person[data-person-id="hab-maria"]')).to_contain_text('Мария Терезия')
                expect(page.locator('.dynasty-polity[data-polity="hre"]')).to_contain_text('Франц')
                expect(page.locator('.dynasty-polity[data-polity="hab"]')).not_to_contain_text('Император Священной')
                expect(page.locator('.dynasty-relation[data-kind="treaty"]')).to_have_count(1)
                expect(page.locator('.dynasty-polity[data-polity="meck"]')).to_contain_text('место рождения')
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл III')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Жозе I')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Адольф Фредрик')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Франц')
                assert page.locator('.dynasty-color-mode').first.bounding_box()['height']>=43.5
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/f'dynasty-network-1762-{width}.png'),full_page=True)

                page.locator('[data-dynasty-mode="origin"]').click()
                expect(page.locator('[data-dynasty-mode="origin"]')).to_have_attribute('aria-pressed','true')
                expect(page.locator('.dynasty-person[data-person-id="ru-catherine2"] .dynasty-origin')).to_contain_text('Немецкое')
                for person in ('gb-george3','gb-charlotte','hab-maria','hre-francis','pr-frederick2'):
                    expect(page.locator(f'.dynasty-person[data-person-id="{person}"] .dynasty-origin')).to_contain_text('Не исследовано')
                page.screenshot(path=str(output/f'dynasty-network-origin-{width}.png'),full_page=True)

                page.locator('[data-dynasty-mode="dynasty"]').click()
                expect(page.locator('.dynasty-person[data-person-id="hab-maria"]')).to_contain_text('Габсбург')
                expect(page.locator('.dynasty-person[data-person-id="gb-george3"]')).to_contain_text('Ганновер')
                expect(page.locator('.dynasty-person[data-person-id="gb-charlotte"]')).to_contain_text('Мекленбург')

                page.locator('.dynasty-milestone[data-year="1765"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1765')
                expect(page.locator('.dynasty-polity[data-polity="hre"]')).to_contain_text('Иосиф II')
                expect(page.locator('.dynasty-polity[data-polity="hre"]')).to_contain_text('Франц')
                expect(page.locator('.dynasty-polity[data-polity="hab"]')).to_contain_text('Соправитель Марии Терезии')
                expect(page.locator('.dynasty-person[data-person-id="fr-antoinette"]')).to_have_count(0)

                page.locator('.dynasty-milestone[data-year="1770"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1770')
                expect(page.locator('.dynasty-relation[data-kind="marriage"]').filter(has_text='Марии-Антуанетты')).to_have_count(1)
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Дофин')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Дофина')
                expect(page.locator('.dynasty-person[data-person-id="fr-antoinette"]')).to_have_count(1)
                page.screenshot(path=str(output/f'dynasty-network-1770-{width}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1774"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1774')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Людовик XV')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Людовик XVI')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Королева-консорт')
                expect(page.locator('.dynasty-polity[data-polity="pr"]')).to_contain_text('Король Пруссии')
                page.go_back()
                expect(page.locator('#dynasty-year')).to_have_text('1770')

                page.locator('.dynasty-milestone[data-year="1780"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1780')
                expect(page.locator('.dynasty-person[data-person-id="hre-francis"]')).to_have_count(0)
                expect(page.locator('.dynasty-polity[data-polity="hab"]')).to_contain_text('Самостоятельный')
                expect(page.locator('.dynasty-polity[data-polity="hab"]')).to_contain_text('Мария Терезия')
                page.screenshot(path=str(output/f'dynasty-network-1780-{width}.png'),full_page=True)

                # Slider is independent of the original SPA year (year precision only).
                page.locator('#dynasty-year-range').evaluate("""el=>{
                    el.value='1777';el.dispatchEvent(new Event('input',{bubbles:true}));
                }""")
                expect(page.locator('#dynasty-year')).to_have_text('1777')
                expect(page.locator('#dynasty-year-range')).to_have_value('1777')
                assert 'dynYear=1777' in page.url

                # The graph opens a real person card; no invisible tooltip-only facts.
                page.locator('.dynasty-graph-scroll svg g[data-actor-id="gb-george3"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('.dynasty-person[data-person-id="gb-george3"]')).to_be_focused()
                expect(page.locator('.dynasty-sources a').first).to_have_attribute(
                    'href',re.compile('^https://'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

                page.keyboard.press('Escape')
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                assert 'world=dynasty18' not in page.url
                assert not errors, errors

                # Navigate from the previously deployed pilot, not only direct URL.
                page.goto(origin+'?world=1762#/timeline/1762')
                expect(page.locator('.atlas-world-layer')).to_be_visible()
                page.locator('.atlas-world-network-link').click()
                expect(page.locator('.dynasty-layer')).to_be_visible()
                expect(page.locator('#dynasty-year')).to_have_text('1762')
                expect(page.locator('.atlas-world-layer')).to_be_hidden()
                page.locator('.dynasty-close').click()
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                expect(page.locator('#atlas-year-value')).to_have_text('1762')
                assert not errors,errors
                report.append({'viewport':[width,height],'polities':8,'people_in_full_pilot':12,
                    'years':[1762,1765,1770,1774,1780],'palette':['state','dynasty','origin'],
                    'status':'passed','javascript_errors':errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/'dynasty-network-receipt.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    args=parser.parse_args()
    run(args.dist,args.output)
