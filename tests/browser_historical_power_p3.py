#!/usr/bin/env python3
"""Opt-in HPM P3 source trace UI: desktop, mobile and back/forward history."""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run(dist: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    payload=json.loads((dist/"hpm-pilot.json").read_text(encoding="utf-8"))
    assert payload["counts"]["candidate_events"]==10
    assert (dist/"v2.html").is_file()
    server=http.server.ThreadingHTTPServer(
        ("127.0.0.1",0),functools.partial(QuietHandler,directory=str(dist.resolve())))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    origin="http://127.0.0.1:"+str(server.server_port)+"/"
    report=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            for width,height in ((1440,960),(390,844),(320,640),(844,390)):
                page=browser.new_page(
                    viewport={"width":width,"height":height},
                    is_mobile=width<=900,has_touch=width<=900)
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(origin+"v2.html")
                expect(page.locator("#hpm-lab")).to_be_hidden()
                expect(page.locator("#hpm-p3-launch")).to_be_visible()
                assert "historical-power-lab" not in (
                    page.locator("html").get_attribute("class") or "")

                page.goto(origin+"v2.html?hpm=pilot#/timeline/1762")
                lab=page.locator("#hpm-lab")
                expect(lab).to_be_visible()
                expect(lab.locator("h2")).to_have_text("Как менялась власть?")
                try:
                    expect(lab.locator(".hpm-event")).to_have_count(10)
                except AssertionError as exc:
                    raise AssertionError(
                        f"HPM pilot not rendered, URL={page.url}, "
                        f"lab={lab.inner_text()[:1800]!r}, js_errors={errors!r}") from exc
                expect(lab.locator(".hpm-fact").nth(2)).to_contain_text("10 / 10")
                assert lab.locator(".hpm-close").bounding_box()["height"] >= 43.5
                assert lab.locator(".hpm-filter").first.bounding_box()["height"] >= 43.5
                assert lab.locator(".hpm-detail").count()==1
                source=lab.locator(".hpm-detail .hpm-sources a").first
                expect(source).to_be_visible()
                assert source.get_attribute("href").startswith("https://")
                assert source.get_attribute("rel")=="noopener noreferrer"
                assert len(page.locator(".hpm-kind").all())==4

                # Year-index candidate not a fabricated exact transfer date.
                lab.locator(".hpm-filter").nth(0).select_option("1774")
                expect(lab.locator(".hpm-event")).to_have_count(1)
                expect(lab.locator(".hpm-fact").nth(2)).to_contain_text("1 / 1")
                expect(lab.locator(".hpm-detail")).to_contain_text("UNKNOWN")
                expect(lab.locator(".hpm-detail")).to_contain_text("Источниковое утверждение")
                assert "hpmYear=1774" in page.url

                # An unstudied year stays an explicit *sample* zero, never history zero.
                lab.locator(".hpm-filter").nth(0).select_option("1780")
                expect(lab.locator(".hpm-event")).to_have_count(0)
                expect(lab.locator(".hpm-detail")).to_contain_text(
                    "Это не означает отсутствия передачи власти")

                lab.locator(".hpm-filter").nth(0).select_option("1799")
                expect(lab.locator(".hpm-event")).to_have_count(1)
                expect(lab.locator(".hpm-detail")).to_contain_text("institutional")
                expect(lab.locator(".hpm-detail .hpm-role")).to_have_count(2)
                assert lab.locator(".hpm-graph-link").get_attribute("href").find("atlasV2=graph")!=-1

                # Institutional linkage is a legal source claim, not a ruler person.
                lab.locator(".hpm-filter").nth(2).select_option("candidate")
                expect(lab.locator(".hpm-event")).to_have_count(0)
                assert "hpmLink=candidate" in page.url
                page.go_back()
                expect(lab.locator(".hpm-event")).to_have_count(1)

                if width <= 390:
                    assert lab.evaluate(
                        "el=>el.scrollWidth <= innerWidth+8")
                    assert lab.locator(".hpm-detail").bounding_box()["width"]<=width

                page.screenshot(path=str(output/("hpm-p3-"+str(width)+".png")))
                lab.locator(".hpm-close").click()
                expect(lab).to_be_hidden()
                assert "hpm=pilot" not in page.url
                expect(page.locator("#hpm-p3-launch")).to_be_visible()
                assert not errors, errors
                report.append({"viewport":[width,height],"status":"passed",
                               "features":["feature flag","trace to public sources",
                                           "role direction","sample denominator",
                                           "unknown","year with zero samples",
                                           "mobile focus targets","history"],"js_errors":errors})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    (output/"hpm-p3-receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--dist",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    run(args.dist,args.output)
