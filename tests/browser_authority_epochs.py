#!/usr/bin/env python3
"""Browser acceptance: England/Japan/Mughals 1688 and Japan/Ethiopia 1888.

Screenshots and verified source links for existing GitHub Pages authority.html;
the older 1788 route and mobile layout must remain compatible.
"""
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


def run(dist:Path,output:Path)->list[dict]:
    output.mkdir(parents=True,exist_ok=True)
    for year in (1688,1788,1888):
        assert (dist/f"world-authority-{year}.json").is_file(),year
    server=http.server.ThreadingHTTPServer(
        ("127.0.0.1",0),functools.partial(Quiet,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f"http://127.0.0.1:{server.server_port}/authority.html"
    receipts=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in ((1440,960),(390,844),(320,640),(844,390)):
                page=browser.new_page(
                    viewport={"width":width,"height":height},
                    is_mobile=width<=900,has_touch=width<=900,device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(origin+"?year=1688&region=eng")
                expect(page.locator("h1")).to_have_text("Мировая сеть власти · 1688")
                expect(page.locator(".world-auth-year")).to_have_count(3)
                expect(page.locator(".world-auth-year[data-year='1688']")).to_have_attribute(
                    "aria-pressed","true")
                expect(page.locator(".world-auth-region")).to_have_count(3)
                expect(page.locator(".world-auth-relation")).to_have_count(2)
                expect(page.locator(".world-auth-relation[data-edge-id='e1688-william-arrival']")).to_have_count(1)
                assert page.locator(".world-auth-year").first.bounding_box()["height"]>=43.5
                page.locator(".world-auth-relation[data-edge-id='e1688-william-arrival']").click()
                expect(page.locator("#world-auth-detail")).to_contain_text("1689")
                expect(page.locator("#world-auth-detail")).to_contain_text("Разовое событие")
                ref=page.locator("#world-auth-detail .world-auth-source").first
                assert ref.get_attribute("href").startswith("https://")
                page.screenshot(path=str(output/f"1688-eng-{width}.png"))
                page.locator(".world-auth-region[data-region='jp']").click()
                expect(page.locator(".world-auth-relation")).to_have_count(2)
                expect(page.locator(".world-auth-node[data-node-id='e1688-higashiyama']")).to_have_count(1)
                expect(page.locator(".world-auth-node[data-node-id='e1688-tsunayoshi']")).to_have_count(1)
                page.locator(".world-auth-region[data-region='mughal']").click()
                expect(page.locator(".world-auth-relation")).to_have_count(1)
                page.screenshot(path=str(output/f"1688-mughal-{width}.png"))
                if width<=390:
                    data=page.locator(".world-auth-scroll").evaluate(
                        "el=>{el.scrollLeft=350;return {w:el.scrollWidth,c:el.clientWidth,x:el.scrollLeft}}")
                    assert data["w"]>data["c"] and data["x"]>0,data

                # Independent second-century snapshot; no 1788 data leakage.
                page.locator(".world-auth-year[data-year='1888']").click()
                expect(page.locator("h1")).to_have_text("Мировая сеть власти · 1888")
                expect(page.locator(".world-auth-year[data-year='1888']")).to_have_attribute(
                    "aria-pressed","true")
                expect(page.locator(".world-auth-region")).to_have_count(2)
                expect(page.locator(".world-auth-region[data-region='jp']")).to_have_attribute(
                    "aria-pressed","true")
                expect(page.locator(".world-auth-relation")).to_have_count(4)
                change=page.locator(".world-auth-relation[data-edge-id='e1888-cabinet-transition']")
                change.click()
                expect(page.locator("#world-auth-detail")).to_contain_text("1888-04-30")
                expect(page.locator("#world-auth-detail")).to_contain_text("Разовое событие")
                page.screenshot(path=str(output/f"1888-japan-{width}.png"))
                page.locator(".world-auth-region[data-region='et']").click()
                expect(page.locator(".world-auth-relation")).to_have_count(3)
                allegiance=page.locator(".world-auth-relation[data-edge-id='e1888-menelik-yohannes']")
                allegiance.click()
                expect(page.locator("#world-auth-detail")).to_contain_text("Формальная")
                expect(page.locator("#world-auth-detail")).to_contain_text("не означает")
                expect(page.locator("#world-auth-detail .world-auth-source")).to_have_count(1)
                page.screenshot(path=str(output/f"1888-ethiopia-{width}.png"))

                # Existing 1788 legacy entry and dynasty link stay functional.
                page.locator(".world-auth-year[data-year='1788']").click()
                expect(page.locator("h1")).to_have_text("Мировая сеть власти · 1788")
                expect(page.locator(".world-auth-region")).to_have_count(3)
                expect(page.locator(".world-auth-relation")).to_have_count(4)
                page.go_back()
                expect(page.locator(".world-auth-year[data-year='1888']")).to_have_attribute(
                    "aria-pressed","true")
                assert page.locator(".world-auth-home").get_attribute("href").startswith("./v2.html")
                assert not errors, errors
                receipts.append({
                    "viewport":[width,height],"status":"passed",
                    "years":[1688,1788,1888],
                    "checks":["1688 no William coronation","1688 shogun and emperor distinct",
                              "1888 Ito-Kuroda 30 April handover",
                              "1888 Menelik Shewa not emperor","source links",
                              "browser history","mobile scroll"],"js_errors":errors
                })
                page.close()
            browser.close()
    finally:
        server.shutdown();server.server_close()
    (output/"authority-epochs-receipt.json").write_text(
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
