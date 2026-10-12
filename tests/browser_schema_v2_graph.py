#!/usr/bin/env python3
"""Chromium acceptance of P4 opt-in historical dynasty graph SPA preview."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


def run(dist:Path,output:Path,entry:str=''):
    output.mkdir(parents=True,exist_ok=True)
    assert (dist/"atlas-v2-graph.json").is_file(), "Missing opt-in P4 preview export"
    assert entry in ('','v2.html'), 'Only reviewed Pages entry is allowed'
    if entry: assert (dist/entry).is_file(), 'Standalone v2.html missing'
    server=http.server.ThreadingHTTPServer(
        ("127.0.0.1",0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    origin="http://127.0.0.1:"+str(server.server_port)+"/"
    entry_origin=origin+entry
    report=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in ((1440,960),(390,844),(320,640),(844,390)):
                page=browser.new_page(
                    viewport={"width":width,"height":height},
                    is_mobile=width<=900,has_touch=width<=900,
                    device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                base=entry_origin+"?atlasV2=graph&v2Year=1788#/timeline/1762"
                page.goto(base)
                expect(page.locator(".atlas-v2-layer")).to_be_visible()
                expect(page.locator(".atlas-v2-heading")).to_have_text(
                    "Династии и политическая власть")
                expect(page.locator("#atlas-v2-year")).to_have_text("1788")
                expect(page.locator(".atlas-v2-graph-scroll svg")).to_be_visible()
                expect(page.locator(".atlas-v2-node-house")).to_have_count(4)
                expect(page.locator(".atlas-v2-node-context")).not_to_have_count(0)
                expect(page.locator(".atlas-v2-node-person[data-entity-id='gb-george3']")).to_have_count(1)
                assert page.locator(".atlas-v2-close").bounding_box()["height"]>=43.5
                assert page.locator(".atlas-v2-filter").first.bounding_box()["height"]>=43.5
                page.screenshot(path=str(output/("v2-graph-1788-"+str(width)+".png")))
                george=page.locator(".atlas-v2-node-person[data-entity-id='gb-george3']")
                george.focus()
                george.press("Enter")
                expect(page.locator("#atlas-v2-detail")).to_contain_text("Георг III")
                expect(page.locator("#atlas-v2-detail")).to_contain_text("Ганновер")
                first_source=page.locator("#atlas-v2-detail .atlas-v2-source").first
                assert first_source.get_attribute("href").startswith("https://")
                assert first_source.get_attribute("rel")=="noopener noreferrer"
                if width<=390:
                    scroll=page.locator(".atlas-v2-graph-scroll")
                    after=scroll.evaluate(
                        "el=>{const w=el.scrollWidth;el.scrollLeft=480;return {w,x:el.scrollLeft,c:el.clientWidth}}")
                    assert after["w"]>after["c"] and after["x"]>0,after

                # Hide house edges without hiding the political relationships.
                page.locator(".atlas-v2-filter input[value='houses']").uncheck()
                expect(page.locator(".atlas-v2-node-house")).to_have_count(0)
                assert "v2Links=" in page.url
                page.locator(".atlas-v2-filter input[value='houses']").check()
                expect(page.locator(".atlas-v2-node-house")).to_have_count(4)

                # Relation-type filter and independent evidence/citation panel.
                page.goto(entry_origin+"?atlasV2=graph&v2Year=1762&v2Links=personal_union#/timeline/1762")
                expect(page.locator("#atlas-v2-year")).to_have_text("1762")
                union=page.locator(
                    ".atlas-v2-relation[data-relation-id='v2-p3-rel-dn-union-gb-han']")
                expect(union).to_have_count(1)
                union.click()
                expect(page.locator("#atlas-v2-detail")).to_contain_text(
                    "Личная уния Великобритании и Ганновера")
                expect(page.locator("#atlas-v2-detail .atlas-v2-source")).to_have_count(1)
                page.screenshot(path=str(output/("v2-graph-union-1762-"+str(width)+".png")))

                # Republic institutions: not two imaginary kings.
                page.goto(entry_origin+"?atlasV2=graph&v2Year=1795&v2Links=institutional#/timeline/1762")
                expect(page.locator("#atlas-v2-year")).to_have_text("1795")
                expect(page.locator(".atlas-v2-node-institution")).to_have_count(2)
                expect(page.locator(".atlas-v2-node-person")).to_have_count(0)
                expect(page.locator(".atlas-v2-node-context[data-entity-id='ctx-world-frrep']")).to_have_count(1)
                institution=page.locator(
                    ".atlas-v2-node-institution[data-entity-id='v2-inst-ex-fr-convention']")
                institution.focus()
                institution.press("Enter")
                expect(page.locator("#atlas-v2-detail")).to_contain_text("Национальный конвент")
                expect(page.locator("#atlas-v2-detail .atlas-v2-source")).to_have_count(1)
                page.screenshot(path=str(output/("v2-graph-france-1795-"+str(width)+".png")))

                # Deep links/history and close do not disturb the ordinary SPA.
                page.locator(".atlas-v2-close").click()
                expect(page.locator(".atlas-v2-layer")).to_be_hidden()
                assert "atlasV2=graph" not in page.url
                expect(page.locator("#panel-timeline")).to_be_visible()
                expect(page.locator("#atlas-v2-launch")).to_be_visible()
                page.locator("#atlas-v2-launch").click()
                expect(page.locator(".atlas-v2-layer")).to_be_visible()
                page.locator(".atlas-v2-close").click()
                page.go_back()
                expect(page.locator(".atlas-v2-layer")).to_be_visible()
                expect(page.locator("#atlas-v2-year")).to_have_text("1788")
                assert not errors,errors
                report.append({
                    "viewport":[width,height],"status":"passed",
                    "features":["year","filters","SVG keyboard selection","sources","preview launch",
                                "personal_union","French collective institutions",
                                "history","mobile scrolling"],
                    "js_errors":errors,
                })
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/"v2-graph-receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dist",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--entry",default="",choices=["","v2.html"])
    args=parser.parse_args()
    run(args.dist,args.output,args.entry)
