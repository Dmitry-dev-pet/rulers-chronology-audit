#!/usr/bin/env python3
"""Chromium acceptance: Europe 1781–1800 addendum with historical institutions."""
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
    def log_message(self,*args):pass

def run(dist:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    server=http.server.ThreadingHTTPServer(
        ('127.0.0.1',0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}/'
    report=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for w,h in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(viewport={'width':w,'height':h},
                    has_touch=w<=900,is_mobile=w<=900,device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?world=dynasty18&dynYear=1762#/timeline/1762')
                expect(page.locator('#dynasty-year')).to_have_text('1762')
                expect(page.locator('#dynasty-year-range')).to_have_attribute('max','1800')
                expect(page.locator('.dynasty-polity')).to_have_count(12)
                expect(page.locator('.dynasty-person')).to_have_count(12)
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл III')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Жозе I')
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_have_count(0)
                expect(page.locator('.dynasty-country-jump')).to_be_visible()
                expect(page.locator('.dynasty-country-button')).to_have_count(8)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

                page.locator('.dynasty-milestone[data-year="1788"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1788')
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл III')
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл IV')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Мария I')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Карлота Жоакина')
                expect(page.locator('.dynasty-polity[data-polity="tusc"]')).to_contain_text('Леопольд II')
                expect(page.locator('.dynasty-person[data-person-id="hab-maria-luisa"]')).to_contain_text('Испанские Бурбоны')
                page.screenshot(path=str(output/f'dynasty-1788-{w}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1792"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1792')
                expect(page.locator('.dynasty-polity')).to_have_count(13)
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_contain_text('Людовик XVI')
                expect(page.locator('.dynasty-polity[data-polity="frrep"] .dynasty-institution')).to_contain_text('Национальный конвент')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Густав III')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Густав IV Адольф')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('регент')
                expect(page.locator('.dynasty-polity[data-polity="hre"]')).to_contain_text('Леопольд II')
                expect(page.locator('.dynasty-polity[data-polity="hre"]')).to_contain_text('Франц II')
                expect(page.locator('.dynasty-relation[data-kind="regime_change"]')).to_contain_text('республике')
                page.screenshot(path=str(output/f'dynasty-1792-{w}.png'),full_page=True)

                page.locator('.dynasty-milestone[data-year="1796"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1796')
                expect(page.locator('.dynasty-polity[data-polity="ru"]')).to_contain_text('Екатерина II')
                expect(page.locator('.dynasty-polity[data-polity="ru"]')).to_contain_text('Павел I')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_have_count(0)
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_contain_text('Директория')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('регент')

                page.locator('.dynasty-milestone[data-year="1799"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1799')
                expect(page.locator('.dynasty-polity[data-polity="frrep"] .dynasty-institution')).to_have_count(2)
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_contain_text('Директория')
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_contain_text('Консульство')
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_contain_text('Бонапарт')
                expect(page.locator('.dynasty-person[data-person-id="fr-napoleon"]')).to_contain_text('Первый консул')
                expect(page.locator('.dynasty-polity[data-polity="pt"]')).to_contain_text('Принц-регент')
                expect(page.locator('.dynasty-graph-scroll svg g[data-actor-id="fr-napoleon"]')).to_have_count(1)
                expect(page.locator('.dynasty-graph-scroll svg g[data-institution-id="ex-fr-consulate"]')).to_have_count(1)
                expect(page.locator('.dynasty-country-jump')).to_be_visible()
                expect(page.locator('.dynasty-country-button')).to_have_count(8)
                page.locator('.dynasty-country-button[data-country="pt"]').click()
                expect(page.locator('.dynasty-country-button[data-country="pt"]')).to_have_attribute('aria-pressed','true')
                page.wait_for_function("document.querySelector('.dynasty-graph-scroll').scrollLeft > 400")
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_have_count(0)
                page.screenshot(path=str(output/f'dynasty-1799-{w}.png'),full_page=True)

                page.locator('.dynasty-graph-scroll svg g[data-institution-id="ex-fr-consulate"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('.dynasty-institution[data-institution-id="ex-fr-consulate"]')).to_be_focused()

                page.locator('.dynasty-milestone[data-year="1800"]').click()
                expect(page.locator('#dynasty-year')).to_have_text('1800')
                expect(page.locator('.dynasty-polity')).to_have_count(12)
                expect(page.locator('.dynasty-polity[data-polity="frrep"] .dynasty-institution')).to_have_count(1)
                expect(page.locator('.dynasty-polity[data-polity="pr"]')).to_contain_text('Фридрих Вильгельм III')
                expect(page.locator('.dynasty-polity[data-polity="es"]')).to_contain_text('Карл IV')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).to_contain_text('Густав IV Адольф')
                expect(page.locator('.dynasty-polity[data-polity="sw"]')).not_to_contain_text('герцог Карл')
                expect(page.locator('.dynasty-person[data-person-id="fr-louis16"]')).to_have_count(0)
                expect(page.locator('.dynasty-person[data-person-id="pt-carlota"]')).to_contain_text('Не исследовано')
                page.screenshot(path=str(output/f'dynasty-1800-{w}.png'),full_page=True)

                page.locator('[data-dynasty-mode="origin"]').click()
                expect(page.locator('[data-dynasty-mode="origin"]')).to_have_attribute('aria-pressed','true')
                for pid in ('es-carlos4','pt-maria1','sw-gustav4','fr-napoleon'):
                    expect(page.locator(f'.dynasty-person[data-person-id="{pid}"] .dynasty-origin')).to_contain_text('Не исследовано')
                expect(page.locator('.dynasty-person[data-person-id="fr-napoleon"]')).to_contain_text('Дом / род')
                page.locator('[data-dynasty-mode="dynasty"]').click()
                expect(page.locator('.dynasty-person[data-person-id="pt-maria1"]')).to_contain_text('Браганса')

                page.locator('#dynasty-year-range').evaluate("""slider=>{
                    slider.value='1793';slider.dispatchEvent(new Event('input',{bubbles:true}));
                }""")
                expect(page.locator('#dynasty-year')).to_have_text('1793')
                expect(page.locator('.dynasty-polity[data-polity="fr"]')).to_have_count(0)
                expect(page.locator('.dynasty-polity[data-polity="frrep"]')).to_contain_text('Национальный конвент')
                assert 'dynYear=1793' in page.url
                page.go_back()
                expect(page.locator('#dynasty-year')).to_have_text('1799')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.keyboard.press('Escape')
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                assert 'world=dynasty18' not in page.url
                assert not errors,errors
                report.append({'viewport':[w,h],'new_period':[1781,1800],
                    'states_in_1800':12,'institutions':3,'new_persons':16,
                    'years':[1788,1792,1796,1799,1800],
                    'status':'passed','errors':errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/'dynasty-1800-receipt.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    opts=parser.parse_args()
    run(opts.dist,opts.output)
