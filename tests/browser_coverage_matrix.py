#!/usr/bin/env python3
"""Chromium: source-qualified 1762–1800 coverage matrix and mobile interaction."""
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
    result=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for w,h in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(viewport={'width':w,'height':h},
                    is_mobile=w<=900,has_touch=w<=900,device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin+'?world=dynasty18&dynYear=1795&dynView=coverage#/timeline/1762')
                expect(page.locator('.dynasty-layer')).to_be_visible()
                expect(page.locator('[data-dynasty-view="coverage"]')).to_have_attribute(
                    'aria-pressed','true')
                expect(page.locator('.dynasty-coverage-panel')).to_be_visible()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_hidden()
                expect(page.locator('.dynasty-footprint-panel')).to_be_hidden()
                expect(page.locator('.dynasty-color-controls')).to_be_hidden()
                expect(page.locator('#dynasty-year')).to_have_text('1795')
                expect(page.locator('.dynasty-coverage-row[data-polity]')).to_have_count(13)
                expect(page.locator('.dynasty-coverage-year-label')).to_have_count(39)
                expect(page.locator('.dynasty-coverage-cell')).to_have_count(13*39)
                expect(page.locator('.dynasty-coverage-legend-item')).to_have_count(7)
                expect(page.locator('.dynasty-coverage-overview')).to_contain_text(
                    '1 ячейка-пробел')
                expect(page.locator('.dynasty-coverage-overview')).to_contain_text(
                    '0 ячеек вне нашей выборки')
                expect(page.locator('.dynasty-coverage-cell[data-polity="tusc"][data-year="1795"]')
                       ).to_have_attribute('data-coverage-status','office')
                expect(page.locator('.dynasty-coverage-cell[data-polity="tusc"][data-year="1790"]')
                       ).to_have_attribute('data-coverage-status','office')
                expect(page.locator('.dynasty-coverage-cell[data-polity="tusc"][data-year="1800"]')
                       ).to_have_attribute('data-coverage-status','research_gap')
                expect(page.locator('.dynasty-coverage-cell[data-polity="fr"][data-year="1793"]')
                       ).to_have_attribute('data-coverage-status','historically_not_in_force')
                expect(page.locator('.dynasty-coverage-cell[data-polity="frrep"][data-year="1791"]')
                       ).to_have_attribute('data-coverage-status','historically_not_in_force')
                expect(page.locator('.dynasty-coverage-cell[data-polity="frrep"][data-year="1795"]')
                       ).to_have_attribute('data-coverage-status','institution')
                expect(page.locator('.dynasty-coverage-cell[data-polity="es"][data-year="1770"]')
                       ).to_have_attribute('data-coverage-status','office')
                expect(page.locator('.dynasty-coverage-cell[data-polity="meck"][data-year="1800"]')
                       ).to_have_attribute('data-coverage-status','birthplace_context')
                expect(page.locator('.dynasty-coverage-task-card')).to_have_count(4)
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Фердинанд')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Фердинанд')
                expect(page.locator('.dynasty-coverage-detail a.dynasty-source')).not_to_have_count(0)
                expect(page.locator('.dynasty-coverage-detail a').last).to_have_attribute(
                    'href',re.compile('^https://'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if w<=390 and h>=640:
                    box=page.locator('.dynasty-coverage-scroll').bounding_box()
                    assert box and box['y']<h*.82, (w,h,box)
                    page.wait_for_function("document.querySelector('.dynasty-coverage-scroll').scrollLeft>200")
                page.screenshot(path=str(output/f'coverage-1795-{w}.png'),full_page=True)

                # A tap on a highlighted year selects evidence and updates
                # the SPA year; selected cell navigation is not an inert legend.
                page.locator('.dynasty-coverage-cell[data-polity="tusc"][data-year="1795"]').click()
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('1795')
                page.locator('.dynasty-coverage-cell[data-polity="tusc"][data-year="1800"]').click()
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Пробел реестра')
                expect(page.locator('#dynasty-year')).to_have_text('1795')

                # Keyboard reaches cells outside the currently visible scroll
                # segment and the row labels remain non-interactive captions.
                page.locator('.dynasty-coverage-cell[data-polity="es"][data-year="1770"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('#dynasty-year')).to_have_text('1770')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Карл III')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text(
                    'Королевство Испания')
                assert 'dynView=coverage' in page.url

                page.locator('.dynasty-coverage-cell[data-polity="fr"][data-year="1793"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('#dynasty-year')).to_have_text('1793')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text(
                    'историческая граница государственного режима')
                expect(page.locator('.dynasty-coverage-detail a.dynasty-source')).to_have_count(4)

                page.locator('.dynasty-coverage-cell[data-polity="frrep"][data-year="1795"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text(
                    'Национальный конвент')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text(
                    'Директория')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text(
                    'коллективный институт')
                page.screenshot(path=str(output/f'coverage-republic-1795-{w}.png'),full_page=True)

                page.locator('.dynasty-coverage-cell[data-polity="frrep"][data-year="1799"]').focus()
                page.keyboard.press('Enter')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Консульство')
                expect(page.locator('.dynasty-coverage-detail')).to_contain_text('Бонапарт')
                expect(page.locator('.dynasty-coverage-detail')).not_to_contain_text(
                    'Император Франции')

                # The three views remain URL-addressable and browser history
                # correctly restores the selection.
                page.locator('[data-dynasty-view="houses"]').click()
                expect(page.locator('.dynasty-footprint-panel')).to_be_visible()
                assert 'dynView=houses' in page.url
                page.locator('[data-dynasty-view="network"]').click()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_visible()
                assert 'dynView=' not in page.url
                page.locator('[data-dynasty-view="coverage"]').click()
                expect(page.locator('.dynasty-coverage-panel')).to_be_visible()
                page.go_back()
                expect(page.locator('.dynasty-person-graph-panel')).to_be_visible()
                page.go_forward()
                expect(page.locator('.dynasty-coverage-panel')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.keyboard.press('Escape')
                expect(page.locator('.dynasty-layer')).to_be_hidden()
                assert 'world=dynasty18' not in page.url

                # Optional coverage asset failure must NOT take down the
                # established people and dynasty screens.
                if w==390:
                    page.route('**/world-coverage-1800.json',
                        lambda route:route.fulfill(status=404,body='unavailable'))
                    page.goto(origin+'?world=dynasty18&dynYear=1788#/timeline/1762')
                    expect(page.locator('.dynasty-person-graph-panel')).to_be_visible()
                    expect(page.locator('.dynasty-graph-scroll svg')).to_be_visible()
                    page.locator('[data-dynasty-view="coverage"]').click()
                    expect(page.locator('.dynasty-coverage-overview')).to_contain_text(
                        'не загружена')
                assert not errors,errors
                result.append({'viewport':[w,h],
                    'matrix':[13,39],'year_cells':507,
                    'research_gap_cells':1,'out_of_sample_cells':0,
                    'views':['network','houses','coverage'],
                    'status':'passed','javascript_errors':errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/'coverage-matrix-receipt.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    opts=parser.parse_args()
    run(opts.dist,opts.output)
