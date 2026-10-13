#!/usr/bin/env python3
"""Mobile-first UX regression on the fully built public SPA, real Chromium.

Never accepts a hidden chart as "readable" or screenshots as sufficient proof.
Touch gesture is simulated as PointerEvents; not a physical-device claim.
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


def run(dist: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    server=http.server.ThreadingHTTPServer(
        ('127.0.0.1',0),
        functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}/'
    result=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            mobile=[(390,844),(360,740),(320,640),(768,1024),(844,390)]
            for width,height in mobile:
                page=browser.new_page(viewport={'width':width,'height':height},
                                      device_scale_factor=1,
                                      has_touch=True,is_mobile=True)
                errors=[]
                page.on('pageerror',lambda exc:errors.append(str(exc)))
                # The canonical root is an entry page, not a hidden year redirect.
                page.goto(origin)
                expect(page.locator('#panel-home')).to_be_visible()
                expect(page.locator('#atlas-home-title')).to_contain_text('Где и когда')
                expect(page.locator('.atlas-home-card')).to_have_count(4)
                expect(page.locator('.modes-wrap')).to_be_hidden()
                page.locator('#atlas-home-year').fill('1762')
                page.locator('#atlas-home-year-form button').click()
                expect(page).to_have_url(re.compile(r'#/timeline/1762$'))
                expect(page.locator('#panel-timeline')).to_be_visible()
                if height <= 560:
                    expect(page.locator('.atlas-home-shortcut')).to_be_visible()
                    page.locator('.atlas-home-shortcut').click()
                else:
                    page.locator('.brand').click()
                expect(page.locator('#panel-home')).to_be_visible()
                page.goto(origin+'#/timeline/1685')
                expect(page.locator('html')).to_have_class(re.compile(r'\batlas-mobile\b'))
                expect(page.locator('#panel-timeline')).to_have_attribute('data-mobile-mode','summary')
                expect(page.locator('#atlas-year-value')).to_have_text('1685')
                expect(page.locator('.atlas-mobile-actions')).to_be_visible()
                expect(page.locator('.atlas-mobile-action')).to_have_count(4)
                expect(page.locator('.mode-tab')).to_have_count(4)
                expect(page.locator('.mode-tab[data-view="timeline"] .atlas-mobile-tab-label')).to_have_text('Год')
                expect(page.locator('.mode-tab[data-view="research"] .atlas-mobile-tab-label')).to_have_text('Источники')
                expect(page.locator('.atlas-year-dashboard-heading strong')).to_have_text('1685')
                expect(page.locator('.atlas-mobile-year-caption')).to_be_visible()
                expect(page.locator('#panel-timeline:not(.smuta-map-active) .smuta-modebar')).to_be_hidden()
                expect(page.locator('.atlas-year-role-card')).to_have_count(4)
                expect(page.locator('.atlas-mobile-role-toggle')).to_have_count(4)
                expect(page.locator('.atlas-year-role-card[data-kind="formal"] .atlas-mobile-role-toggle')).to_have_attribute('aria-expanded','false')
                expect(page.locator('.atlas-year-role-card[data-kind="effective"] .atlas-mobile-role-toggle')).to_have_attribute('aria-expanded','false')
                expect(page.locator('.atlas-timeline-workspace')).to_be_hidden()
                expect(page.locator('.timeline-toolbar')).to_be_hidden()
                expect(page.locator('.atlas-mobile-role-title').first).to_be_visible()
                expect(page.locator('.atlas-mobile-highlights')).to_be_visible()
                expect(page.locator('.atlas-mobile-highlight')).to_have_count(4)
                expect(page.locator('.atlas-mobile-highlight[data-kind="formal"]')).to_contain_text('Иван V')
                expect(page.locator('.atlas-mobile-highlight[data-kind="formal"]')).to_contain_text('Пётр I')
                expect(page.locator('.atlas-mobile-highlight[data-kind="effective"]')).to_contain_text('Софья')
                expect(page.locator('.atlas-mobile-highlight[data-kind="regency"]')).to_contain_text('Софья')
                expect(page.locator('.atlas-mobile-highlights-note')).to_contain_text('не одновременный')
                # Histography-inspired playback advances only canonical year
                # queries, stops on request and never fabricates transitions.
                play=page.locator('.atlas-year-play')
                expect(play).to_be_visible()
                expect(play).to_have_attribute('aria-pressed','false')
                expect(page.locator('.atlas-year-playback-note')).to_contain_text(
                    'не анимация фактической передачи власти')
                assert play.bounding_box()['height']>=43.5
                page.locator('.atlas-year-playback-step').select_option('1')
                play.click()
                expect(play).to_have_attribute('aria-pressed','true')
                expect(page.locator('#atlas-year-value')).to_have_text('1686',timeout=5000)
                play.click()
                expect(play).to_have_attribute('aria-pressed','false')
                paused=page.locator('#atlas-year-value').inner_text()
                page.wait_for_timeout(1000)
                assert page.locator('#atlas-year-value').inner_text()==paused
                page.evaluate("""() => {
                    const s=document.getElementById('atlas-year-range');
                    s.value='1685';
                    s.dispatchEvent(new Event('input',{bubbles:true}));
                }""")
                expect(page.locator('#atlas-year-value')).to_have_text('1685')

                # Mobile tap targets must be physically large, while body itself
                # fits the viewport. Horizontal chips and the chart scroll locally.
                for loc in [
                    page.locator('.mode-tab').first,
                    page.locator('.atlas-mobile-action').first,
                    page.locator('.atlas-mobile-role-toggle').first,
                    page.locator('.atlas-year-step').first,
                ]:
                    assert loc.bounding_box()['height']>=43.5,loc
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
                assert page.evaluate(
                    "parseFloat(getComputedStyle(document.querySelector('.atlas-mobile-role-title')).fontSize)>=16")
                screenshot=output/f'mobile-summary-{width}.png'
                page.screenshot(path=str(screenshot),full_page=True)
                # One tap from the preview expands the original canonical card.
                page.locator('.atlas-mobile-highlight[data-kind="formal"]').click()
                expect(page.locator('.atlas-year-role-card[data-kind="formal"] .atlas-mobile-role-toggle')).to_have_attribute('aria-expanded','true')
                expect(page.locator('.atlas-year-person-link').first).to_be_visible()

                regency=page.locator('.atlas-year-role-card[data-kind="regency"]')
                regency.locator('.atlas-mobile-role-toggle').click()
                expect(regency.locator('.atlas-mobile-role-toggle')).to_have_attribute('aria-expanded','true')
                expect(regency.locator('.atlas-year-role-items')).to_be_visible()
                expect(regency).to_contain_text('Софья')
                regency.locator('.atlas-mobile-role-toggle').click()
                expect(regency.locator('.atlas-year-role-items')).to_be_hidden()
                if height>560:
                    page.locator('.atlas-mobile-method summary').click()
                    expect(page.locator('.atlas-mobile-method p')).to_be_visible()

                # Summary's "all records" goes to the existing sourced inspector
                # in a bottom sheet, not to a tiny off-screen desktop column.
                page.locator('.atlas-year-role-card[data-kind="formal"] .atlas-year-role-details').click()
                expect(page.locator('#panel-timeline')).to_have_attribute('data-mobile-mode','timeline')
                expect(page.locator('.atlas-sidebar')).to_be_visible()
                expect(page.locator('.atlas-sidebar')).to_have_attribute('aria-modal','true')
                expect(page.locator('.atlas-sidebar-heading')).to_contain_text('Все записи')
                expect(page.locator('.atlas-sidebar .timeline-selection')).to_be_hidden()
                expect(page.locator('.atlas-sidebar .atlas-year-inspector')).to_be_visible()
                expect(page.locator('.atlas-mobile-scrim')).to_be_visible()
                assert page.locator('.atlas-sidebar').bounding_box()['height'] <= height*.87+1
                page.screenshot(path=str(output/f'mobile-bottom-sheet-{width}.png'),full_page=True)
                page.locator('.atlas-sidebar-close').click()
                expect(page.locator('.atlas-sidebar')).to_be_hidden()
                expect(page.locator('.atlas-mobile-scrim')).to_be_hidden()

                expect(page.locator('.timeline-toolbar')).to_be_visible()
                expect(page.locator('.atlas-timeline-workspace')).to_be_visible()
                expect(page.locator('.era-btn[data-era="dual"]')).to_have_attribute('aria-pressed','true')
                expect(page.locator('.atlas-year-dashboard-cards')).to_be_hidden()
                expect(page.locator('.atlas-year-playback')).to_be_hidden()
                expect(page.locator('.timeline-scroll')).to_be_visible()
                expect(page.locator('.time-bar')).not_to_have_count(0)
                page.screenshot(path=str(output/f'mobile-timeline-{width}.png'),full_page=True)

                # A genuine chart item can still open details and outside
                # dismissal restores independent touch scrolling.
                page.locator('.time-bar').first.click()
                expect(page.locator('.atlas-sidebar')).to_be_visible()
                expect(page.locator('.atlas-mobile-scrim')).to_be_visible()
                page.locator('.atlas-mobile-scrim').click(position={'x':5,'y':5})
                expect(page.locator('.atlas-sidebar')).to_be_hidden()
                page.locator('.atlas-mobile-action[data-mobile-action="summary"]').click()
                expect(page.locator('.atlas-timeline-workspace')).to_be_hidden()
                expect(page.locator('.atlas-year-dashboard-cards')).to_be_visible()
                # Simulated touch swipe on the year title changes ONE year,
                # leaving all historical records and calendar semantics intact.
                page.evaluate("""() => {
                    const h=document.querySelector('.atlas-year-dashboard-heading h2');
                    for (const [type,x] of [['pointerdown',240],['pointerup',120]])
                        h.dispatchEvent(new PointerEvent(type,{
                            bubbles:true, pointerType:'touch', pointerId:37,
                            clientX:x,clientY:90}));
                }""")
                expect(page.locator('#atlas-year-value')).to_have_text('1686')

                # Quick overview is a separately scrollable overlay even when
                # the chart workspace is hidden by summary-first CSS.
                page.locator('.atlas-mobile-action[data-mobile-action="overview"]').click()
                expect(page.locator('.atlas-global-sheet')).to_be_visible()
                expect(page.locator('.atlas-global-sheet-head')).to_be_visible()
                expect(page.locator('.atlas-global-century-card')).to_have_count(5)
                expect(page.locator('.atlas-global-coverage-row')).to_have_count(20)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/f'mobile-centuries-{width}.png'),full_page=True)
                page.locator('.atlas-global-close').click()
                expect(page.locator('.atlas-global-sheet')).to_be_hidden()

                # The comparison is A/B/differences, never two unreadable
                # 180-pixel columns. Differences are SET differences of source
                # record IDs, not invented claims of political succession.
                page.goto(origin+'?atlasView=compare&atlasYears=1685%2C1953#/timeline/1685')
                expect(page.locator('.atlas-global-sheet')).to_be_visible()
                expect(page.locator('.atlas-mobile-compare-tab')).to_have_count(3)
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_be_visible()
                expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_hidden()
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_contain_text('Софья')
                page.locator('.atlas-mobile-compare-tab[data-tab="b"]').click()
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_be_hidden()
                expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_be_visible()
                expect(page.locator('.atlas-global-year-column[data-year="1953"]')).to_contain_text('Маленков')
                page.locator('.atlas-mobile-compare-tab[data-tab="diff"]').click()
                expect(page.locator('.atlas-mobile-differences')).to_be_visible()
                expect(page.locator('.atlas-mobile-diff-group')).to_have_count(4)
                expect(page.locator('.atlas-mobile-differences')).to_contain_text('НЕ доказательство')
                expect(page.locator('.atlas-global-compare-columns')).to_be_hidden()
                page.screenshot(path=str(output/f'mobile-differences-{width}.png'),full_page=True)
                page.locator('.atlas-mobile-compare-tab[data-tab="a"]').click()
                expect(page.locator('.atlas-global-year-column[data-year="1685"]')).to_be_visible()
                page.locator('.atlas-global-preset[data-left="1917"][data-right="1991"]').click()
                expect(page.locator('.atlas-global-year-column[data-year="1917"]')).to_be_visible()
                expect(page).to_have_url(re.compile('atlasYears=1917%2C1991'))
                page.reload()
                expect(page.locator('.atlas-mobile-compare-tab[data-tab="a"]')).to_have_attribute('aria-pressed','true')
                expect(page.locator('.atlas-global-year-column[data-year="1917"]')).to_be_visible()
                page.locator('.atlas-global-year-jump[data-year="1917"]').click()
                expect(page.locator('.atlas-global-sheet')).to_be_hidden()
                expect(page.locator('#atlas-year-value')).to_have_text('1917')

                # Biography search is still a separate, readable screen.
                page.locator('#tab-people').click()
                expect(page.locator('#panel-people')).to_be_visible()
                expect(page.locator('.spa-people-grid')).to_be_visible()
                expect(page.locator('.spa-person-card')).not_to_have_count(0)
                page.locator('.spa-person-card').first.click()
                expect(page.locator('.spa-person-detail')).to_be_visible()
                expect(page.locator('#panel-people')).to_have_class(re.compile('spa-profile-open'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.screenshot(path=str(output/f'mobile-biography-{width}.png'),full_page=True)
                assert not errors,errors
                result.append({
                    'viewport':[width,height],'summary':'passed','timeline':'passed',
                    'bottom_sheet':'passed','comparison':'passed','differences':'passed',
                    'biography':'passed','js_errors':errors})
                page.close()

            desktop=browser.new_page(viewport={'width':1440,'height':1000})
            desktop.goto(origin)
            expect(desktop.locator('#panel-home')).to_be_visible()
            expect(desktop.locator('.atlas-home-card')).to_have_count(4)
            desktop.locator('.atlas-home-card[href="#/people"]').click()
            expect(desktop.locator('#panel-people')).to_be_visible()
            desktop.goto(origin+'#/timeline/1685')
            expect(desktop.locator('html')).not_to_have_class(re.compile(r'\batlas-mobile\b'))
            expect(desktop.locator('.atlas-mobile-actions')).to_be_hidden()
            expect(desktop.locator('.atlas-year-play')).to_be_visible()
            expect(desktop.locator('.atlas-year-role-head h3').first).to_be_visible()
            expect(desktop.locator('.atlas-timeline-workspace')).to_be_visible()
            expect(desktop.locator('.timeline-toolbar')).to_be_visible()
            desktop.close()
            browser.close()
    finally:
        server.shutdown()
    (output/'mobile-receipt.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dist',type=Path,default=Path('dist'))
    parser.add_argument('--output',type=Path,default=Path('browser-evidence'))
    args=parser.parse_args()
    run(args.dist,args.output)
