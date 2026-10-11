"""Regression test for harmless v2.html publication in existing GitHub Pages."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import atlas_v2_pages as pages


class ExistingPagesV2(unittest.TestCase):
    @staticmethod
    def seed(directory: Path):
        directory.mkdir(parents=True)
        (directory / "index.html").write_text(
            "<!doctype html><html><body>"
            "<script id='chronology-data' type='application/json'>{}</script>"
            "<script defer src='./site.js'></script>"
            "</body></html>", encoding="utf-8")
        (directory / "site.js").write_text(
            "/* old shell */\n", encoding="utf-8")
        (directory / "atlas.json").write_text(
            '{"metadata":{"historical_truth_verified_by_ci":false}}\n',
            encoding="utf-8")
        (directory / "SHA256SUMS").write_text(
            "placeholder\n", encoding="utf-8")

    def test_direct_pages_v2_entry_without_modifying_homepage(self):
        with tempfile.TemporaryDirectory() as temp:
            dist=Path(temp) / "dist"
            self.seed(dist)
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in dist.iterdir()}
            receipt=pages.build(pages.ROOT,dist)
            self.assertEqual(receipt["status"],"ready_for_existing_pages_deploy")
            self.assertTrue(receipt["original_index_unchanged"])
            self.assertIn("v2.html?atlasV2=graph&v2Year=1788",receipt["site_entry"])
            self.assertFalse(receipt["historical_truth_verified_by_ci"])
            self.assertEqual(receipt["counts"]["relations"],27)
            self.assertEqual(receipt["counts"]["contexts"],13)
            self.assertEqual({p.name for p in dist.iterdir()},set(before) | set(pages.PUBLIC_FILES))
            for name,old in before.items():
                if name!="SHA256SUMS":
                    self.assertEqual(
                        hashlib.sha256((dist/name).read_bytes()).hexdigest(),old)
            original=(dist/"index.html").read_text(encoding="utf-8")
            v2=(dist/"v2.html").read_text(encoding="utf-8")
            self.assertNotIn("atlas-v2-launch",original)
            self.assertIn("atlas-v2-launch",v2)
            self.assertIn("src='./atlas-v2-graph.js'",v2)
            self.assertIn("href='./atlas-v2-graph.css'",v2)
            self.assertIn("world-authority-launch",v2)
            world_html=(dist/"authority.html").read_text(encoding="utf-8")
            self.assertIn("src=\"./world-authority.js\"",world_html)
            self.assertIn("id=\"world-authority-app\"",world_html)
            self.assertNotIn("world-authority.js",original)
            authority=json.loads((dist/"world-authority-1788.json").read_text())
            self.assertEqual(authority["focus_year"],1788)
            self.assertEqual(authority["counts"]["links"],12)
            self.assertEqual(authority["counts"]["nodes"],18)
            self.assertEqual(len(authority["sources"]),8)
            self.assertFalse(authority["historical_truth_verified_by_ci"])
            self.assertFalse(authority["sample_covers_all_world"])
            self.assertFalse(authority["geographic_boundaries_verified"])
            for year,expected_regions,expected_edges in (
                    (1688,3,5),(1888,2,7)):
                new=json.loads(
                    (dist/f"world-authority-{year}.json").read_text(encoding="utf-8"))
                self.assertEqual(new["focus_year"],year)
                self.assertEqual(len(new["regions"]),expected_regions)
                self.assertEqual(len(new["edges"]),expected_edges)
                self.assertFalse(new["historical_truth_verified_by_ci"])
                self.assertFalse(new["geographic_boundaries_verified"])
                self.assertFalse(new["sample_covers_all_world"])
            data=json.loads((dist/"atlas-v2-graph.json").read_text())
            self.assertEqual(data["schema_version"],"atlas-v2-graph-preview-1")
            self.assertFalse(data["historical_truth_verified_by_ci"])
            for line in (dist/"SHA256SUMS").read_text().splitlines():
                digest,name=line.split("  ",1)
                self.assertEqual(hashlib.sha256((dist/name).read_bytes()).hexdigest(),
                                 digest)
            with self.assertRaisesRegex(ValueError,"already exist"):
                pages.build(pages.ROOT,dist)

    def test_never_overwrites_unrecognized_pages_build(self):
        with tempfile.TemporaryDirectory() as temp:
            dist=Path(temp)/"dist"
            self.seed(dist)
            (dist/"v2.html").write_text("do not overwrite",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"already exist"):
                pages.build(pages.ROOT,dist)
            self.assertEqual((dist/"v2.html").read_text(),"do not overwrite")

    def test_main_pages_publisher_not_cross_origin(self):
        workflow=(pages.ROOT/".github/workflows/publish-pages.yml").read_text()
        self.assertIn("actions/deploy-pages@",workflow)
        self.assertIn("github.ref == 'refs/heads/main'",workflow)
        self.assertIn("python3 -m scripts.atlas_v2_pages",workflow)
        self.assertIn("'v2.html'",workflow)
        self.assertIn("'atlas-v2-graph.json'",workflow)
        # Original image stays outside the public output.
        self.assertIn("1000428575.jpg",workflow)


if __name__=="__main__":
    unittest.main()
