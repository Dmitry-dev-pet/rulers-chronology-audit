#!/usr/bin/env python3
"""Verify a *partial, published* Chernenko facsimile review, not archive authenticity.

The original birth facts and issue HC-0005 remain unchanged. The linked full
archival pages are not considered inspected until an independent visual check.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import historical_disputes as h
from scripts import historical_biographical_disputes as bio

ROOT = h.ROOT
SOURCE = Path("research/contradictions/chernenko-facsimile-2026-10-13.json")
EXPECTED_MARKERS = {
    "entry_number": "32", "birth_day": "18", "baptism_day": "23",
    "given_name": "Константин", "family_name_parent_column": "Черненко",
}
EXPECTED_IMAGES = {
    "HC5-PHOTO-AUTHOR": (
        "https://ostkraft.ru/insimgs/2300/img2254.jpg",
        "published_cropped_photo", True, "alexey-nilogov-published-fragment"
    ),
    "HC5-PHOTO-REPRINT": (
        "https://newdaynews.ru/pict/text/26/09/23/r23_596159761.jpg",
        "press_reprint_same_fragment", True, "alexey-nilogov-published-fragment"
    ),
    "HC5-PAGE-LINK-1": (
        "https://culture19.ru/uploads/files/00000001.JPG",
        "archival_page_link_uninspected", False, "official-catalog-linked-document"
    ),
    "HC5-PAGE-LINK-26": (
        "https://culture19.ru/uploads/files/00000026.JPG",
        "archival_page_link_uninspected", False, "official-catalog-linked-document"
    ),
}


def validate(document: dict, biography: dict, canonical_facts: list[dict]) -> dict:
    if (not isinstance(document, dict) or
        document.get("schema_version") != "historical-facsimile-evidence-v1"
        or document.get("related_case_id") != "HC-0005"
        or document.get("person_id") != "person-654bc370814d5452"
        or document.get("canonical_fact_id") !=
            "fact-research-20261010-chernenko-birth-archive"
        or document.get("canonical_source_id") != "TP308"
        or document.get("review_scope") !=
            "published_photographic_crop_and_archival_catalog_not_full_manuscript"):
        raise ValueError("Incorrect facsimile research scope or historical identity")

    for flag in (
        "birth_year_visually_verified_from_crop",
        "official_full_pages_visually_inspected",
        "original_manuscript_independently_authenticated",
        "independent_primary_checked",
        "source_images_copied_to_repository",
        "dispute_resolution_proposed",
    ):
        if document.get(flag) is not False:
            raise ValueError("Unverified manuscript/photo may not be promoted: " + flag)
    if document.get("case_remains_open") is not True:
        raise ValueError("Cannot close a dispute from cropped secondary facsimile alone")
    c = next((x for x in biography["cases"]
              if x["id"] == document["related_case_id"]), None)
    if (c is None or c["review_status"] != "open" or
        c["resolution"] is not None or c["person_id"] != document["person_id"] or
        c["reviewed_primary_acts"] is not False):
        raise ValueError("Underlying disputed biography was changed or auto-resolved")
    f = next((x for x in canonical_facts
              if x["id"] == document["canonical_fact_id"]), None)
    if (f is None or f["person_id"] != c["person_id"] or f["kind"] != "birth"
        or f["value"]["value"] != "1912-09-18"
        or f["value"]["calendar"] != "julian"
        or f["verification"] != "reference_checked"
        or "TP308" not in f["sources"]):
        raise ValueError("Original archival person fact was silently rewritten")

    catalog = document.get("official_catalog")
    if (not isinstance(catalog, dict) or
        catalog.get("url") != "https://culture19.ru/contents/587-7-metricheskaya-zapis.html"
        or catalog.get("year_stated_by_catalog") != 1912
        or catalog.get("record_number") != "32"
        or catalog.get("source_role") != "archival_attribution_not_photographic_verification"
        or not catalog.get("shelfmark")):
        raise ValueError("Official archive catalog provenance missing")
    if (document.get("catalog_birth_date_julian") != "1912-09-18"
        or document.get("catalog_baptism_date_julian") != "1912-09-23"):
        raise ValueError("Raw archival catalog day/year attribution changed")

    images = document.get("images")
    if (not isinstance(images, list) or
        len(images) != len(EXPECTED_IMAGES) or
        len({i.get("id") for i in images}) != len(images)):
        raise ValueError("Both same-origin crops and both uninspected archive pages required")
    for i in images:
        if (not isinstance(i, dict) or
            not h.safe_url(i.get("url")) or
            (i.get("url"), i.get("kind"), i.get("viewed_as_pixels"),
             i.get("origin_group")) != EXPECTED_IMAGES.get(i.get("id")) or
            not isinstance(i.get("attribution"), str) or not i["attribution"]):
            raise ValueError("Image provenance/visual inspection status may not be invented")
    markers = document.get("visible_markers_from_cropped_photo")
    if (not isinstance(markers, list) or
        len(markers) != len(EXPECTED_MARKERS) or
        {x.get("field"): x.get("transcription") for x in markers}
        != EXPECTED_MARKERS or
        any(x.get("confidence") not in {"high", "medium"} for x in markers)):
        raise ValueError("Cropped manuscript transcription drifted or guessed")
    if (not isinstance(document.get("visual_limitations"), list) or
        len(document["visual_limitations"]) < 4 or
        not isinstance(document.get("followup"), str) or
        not document["followup"]):
        raise ValueError("Uncertainty and next archival gate must be explicit")
    return document


def verify(root: Path = ROOT) -> dict:
    doc = h.load_json(root / SOURCE)
    bio_doc = bio.registry(root)
    facts = h.read_jsonl(root / "data/atlas/person_facts.jsonl")
    return validate(doc, bio_doc, facts)


def main() -> int:
    doc = verify()
    print(json.dumps({
        "schema_version": doc["schema_version"],
        "case_id": doc["related_case_id"],
        "published_crop_visually_viewed": True,
        "official_full_pages_visually_inspected": False,
        "primary_manuscript_independently_authenticated": False,
        "birth_year_from_visible_crop": False,
        "dispute_resolved": False,
        "catalog_date_julian": doc["catalog_birth_date_julian"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
