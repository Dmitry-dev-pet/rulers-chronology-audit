#!/usr/bin/env python3
"""Four-viewport Chromium acceptance of research coverage matrix (not state coverage)."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def run(dist:Path,output:Path):
    output.mkdir(parents=True,exist_ok=True)
    assert (dist/"coverage.html").is_file()
    assert (dist/"world-authority-coverage.json").is_file()
    server=http.server.ThreadingHTTPServer(
        ("127.0.0.1",0),functools.partial(Quiet,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin="http://127.0.0.1:"+str(server.server_port)+"/"
    receipts=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in ((1440,960),(390,844),(320,640),(844,390)):
                page=browser.new_page(
                    viewport={"width":width,"height":height},
                    is_mobile=width<=900,has_touch=width<=900,device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda exc:errors.append(str(exc)))
                page.goto(origin+"coverage.html")
                expect(page.locator("h1")).to_have_text("Где мы уже исследовали историю?")
                expect(page.locator(".coverage-cell-button")).to_have_count(21)
                expect(page.locator('.coverage-cell-button[data-status="partial_sample"]')).to_have_count(8)
                expect(page.locator('.coverage-cell-button[data-status="not_researched"]')).to_have_count(13)
                expect(page.locator(".coverage-dim-button")).to_have_count(6)
                expect(page.locator(".coverage-summary")).to_contain_text("24 отношений")
                expect(page.locator(".coverage-dim-button[data-dimension='all']")).to_have_attribute(
                    "aria-pressed","true")
                assert page.locator(".coverage-cell-button").first.bounding_box()["height"]>=44
                assert page.locator(".coverage-dim-button").first.bounding_box()["height"]>=43.5

                # Japan is studied in 1688 & 1888 but explicitly NOT in 1788.
                jp1788=page.locator(".coverage-cell-button[data-area='jp'][data-year='1788']")
                expect(jp1788).to_contain_text("Не исследовано")
                jp1788.click()
                expect(page.locator("#coverage-detail")).to_contain_text("НЕ свидетельство отсутствия")
                expect(page.locator("#coverage-detail .coverage-source")).to_have_count(0)
                expect(page.locator("#coverage-detail .coverage-open-network")).to_have_count(0)

                # The 1688 Japan sample is partial, has sources, and deep links.
                jp1688=page.locator(".coverage-cell-button[data-area='jp'][data-year='1688']")
                expect(jp1688).to_contain_text("2 записей")
                jp1688.click()
                expect(page.locator("#coverage-detail")).to_contain_text("Частичный")
                graph=page.locator("#coverage-detail .coverage-open-network")
                expect(graph).to_have_attribute("href",
                    "./authority.html?year=1688&region=jp")
                first=page.locator("#coverage-detail .coverage-source").first
                assert first.get_attribute("href").startswith("https://")
                assert first.get_attribute("rel")=="noopener noreferrer"

                # Selected filter NEVER changes an investigated cell into a
                # historical-absence assertion; zero is a source-type count.
                page.locator(".coverage-dim-button[data-dimension='military']").click()
                qing=page.locator(".coverage-cell-button[data-area='qing'][data-year='1788']")
                expect(qing).to_have_attribute("data-status","partial_sample")
                expect(qing).to_contain_text("0 записей")
                qing.click()
                expect(page.locator("#coverage-detail")).to_contain_text(
                    "не доказывает отсутствие такого вида власти")
                page.screenshot(path=str(output/f"coverage-military-{width}.png"))

                # Diplomatic relations Qing/Joseon, distinguished from absence.
                page.locator(".coverage-dim-button[data-dimension='diplomatic']").click()
                expect(qing).to_contain_text("1 запись")
                qing.click()
                expect(page.locator("#coverage-detail")).to_contain_text("Дипломатические")
                expect(page.locator("#coverage-detail .coverage-open-network")).to_have_attribute(
                    "href","./authority.html?year=1788&region=qing")
                assert page.locator("#coverage-detail .coverage-source").count()>0
                page.screenshot(path=str(output/f"coverage-diplomatic-{width}.png"))

                # Direct link restores year/scope/dimension and history works.
                page.goto(origin+"coverage.html?year=1888&area=jp&kind=institutional")
                expect(page.locator(".coverage-dim-button[data-dimension='institutional']")).to_have_attribute(
                    "aria-pressed","true")
                expect(page.locator(".coverage-cell-button[data-area='jp'][data-year='1888']")).to_have_attribute(
                    "aria-pressed","true")
                expect(page.locator("#coverage-detail")).to_contain_text(
                    "Сведения выбранного типа: 3")
                page.locator(".coverage-cell-button[data-area='eng'][data-year='1888']").click()
                expect(page.locator("#coverage-detail")).to_contain_text(
                    "ещё не исследовано")
                page.go_back()
                expect(page.locator(".coverage-cell-button[data-area='jp'][data-year='1888']")).to_have_attribute(
                    "aria-pressed","true")
                if width<=390:
                    metrics=page.locator(".coverage-matrix-scroll").evaluate(
                        "el=>{el.scrollLeft=370;return {w:el.scrollWidth,c:el.clientWidth,x:el.scrollLeft}}")
                    assert metrics["w"]>metrics["c"] and metrics["x"]>0,metrics
                assert "./authority.html" in page.locator(".world-auth-home").get_attribute("href")
                assert not errors,errors
                receipts.append({"viewport":[width,height],"status":"passed",
                                 "reviewed_cells":8,"unresearched_cells":13,
                                 "checks":["no false absence","no 1688/1888 interpolation",
                                           "dimension filters","real source links",
                                           "keyboard-ready buttons","mobile scroll",
                                           "direct links and history"],"js_errors":errors})
                page.close()
            browser.close()
    finally:
        server.shutdown();server.server_close()
    (output/"world-research-coverage-receipt.json").write_text(
        json.dumps(receipts,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    print(json.dumps(receipts,ensure_ascii=False))
    return receipts


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    run(args.dist,args.output)
