#!/usr/bin/env python3
"""Chromium acceptance of source-qualified 1788 world authority on Pages."""
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


def run(dist:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    assert (dist/"authority.html").is_file(), "Standalone world authority page missing"
    assert (dist/"world-authority-1788.json").is_file(), "World authority JSON missing"
    server=http.server.ThreadingHTTPServer(
        ("127.0.0.1",0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin="http://127.0.0.1:"+str(server.server_port)+"/"
    receipts=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in [(1440,960),(390,844),(320,640),(844,390)]:
                page=browser.new_page(
                    viewport={"width":width,"height":height},
                    is_mobile=width<=900,has_touch=width<=900,device_scale_factor=1)
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(origin+"authority.html?region=hre")
                expect(page.locator("h1")).to_have_text("Мировая сеть власти · 1788")
                expect(page.locator(".world-auth-region")).to_have_count(3)
                expect(page.locator(".world-auth-node")).to_have_count(5)
                expect(page.locator(".world-auth-relation")).to_have_count(4)
                expect(page.locator(".world-auth-region[data-region='hre']")).to_have_attribute(
                    "aria-pressed","true")
                assert page.locator(".world-auth-region").first.bounding_box()["height"]>=43.5
                assert page.locator(".world-auth-filter").first.bounding_box()["height"]>=43.5
                page.screenshot(path=str(out/("authority-hre-"+str(width)+".png")))
                page.locator(".world-auth-node[data-node-id='h-george']").focus()
                page.locator(".world-auth-node[data-node-id='h-george']").press("Enter")
                expect(page.locator("#world-auth-detail")).to_contain_text("Георг III")
                source=page.locator("#world-auth-detail .world-auth-source").first
                assert source.get_attribute("href").startswith("https://")
                self_rel=source.get_attribute("rel")
                assert self_rel=="noopener noreferrer",self_rel
                expect(page.locator(".world-auth-relation[data-edge-id='h-e2']")).to_have_count(1)
                page.locator(".world-auth-relation[data-edge-id='h-e2']").click()
                expect(page.locator("#world-auth-detail")).to_contain_text("не означает")
                # HRE legal office ≠ membership of electorate in imperial framework.
                page.locator(".world-auth-filter input[value='institutional']").uncheck()
                expect(page.locator(".world-auth-relation")).to_have_count(3)
                assert "dims=" in page.url
                page.locator(".world-auth-filter input[value='institutional']").check()
                expect(page.locator(".world-auth-relation")).to_have_count(4)
                if width<=390:
                    data=page.locator(".world-auth-scroll").evaluate(
                        "el=>{el.scrollLeft=330;return {w:el.scrollWidth,c:el.clientWidth,x:el.scrollLeft}}")
                    assert data["w"]>data["c"] and data["x"]>0,data

                # India: formal title, local seizure, restoration and fiscal office are
                # distinct sources and dimensions. No synthetic sovereign of India.
                page.locator(".world-auth-region[data-region='india']").click()
                expect(page.locator(".world-auth-relation")).to_have_count(5)
                expect(page.locator(".world-auth-node[data-node-id='i-delhi']")).to_have_count(1)
                page.locator(".world-auth-relation[data-edge-id='i-e2']").click()
                expect(page.locator("#world-auth-detail")).to_contain_text("Разовое событие")
                expect(page.locator("#world-auth-detail .world-auth-source")).to_have_count(1)
                page.screenshot(path=str(out/("authority-india-"+str(width)+".png")))
                # Qing/Choson diplomatic relation is NOT Qing administration in Korea.
                page.locator(".world-auth-region[data-region='qing']").click()
                expect(page.locator(".world-auth-relation")).to_have_count(3)
                page.locator(".world-auth-relation[data-edge-id='q-e3']").click()
                expect(page.locator("#world-auth-detail")).to_contain_text(
                    "не доказывает прямое")
                expect(page.locator("#world-auth-detail .world-auth-source")).to_have_count(1)
                page.screenshot(path=str(out/("authority-qing-"+str(width)+".png")))
                page.go_back()
                expect(page.locator(".world-auth-region[data-region='india']")).to_have_attribute(
                    "aria-pressed","true")
                # Users can always return to the original v2 SPA.
                link=page.locator(".world-auth-home")
                assert "v2.html" in link.get_attribute("href")
                assert not errors,errors
                receipts.append({"viewport":[width,height],"status":"passed",
                                 "events":["HRE different offices",
                                           "Delhi 1788 not continuous rule",
                                           "Qing-Joseon diplomatic, not province",
                                           "source links and history"],
                                 "js_errors":errors})
                page.close()
            browser.close()
    finally:
        server.shutdown();server.server_close()
    (out/"authority-1788-receipt.json").write_text(
        json.dumps(receipts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipts,ensure_ascii=False))
    return receipts


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dist",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    run(args.dist,args.output)
