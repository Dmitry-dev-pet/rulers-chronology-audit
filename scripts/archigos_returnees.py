"""Reproducible descriptive statistics for Archigos 4.1 leader spells.

This is NOT a verified list of historical persons. It treats a leader ID as
provisionally identifying a person only if the supplied birth years agree.
External evidence is required to clear remaining identity ambiguities.
Neither canonical atlas records nor source archives are ever changed.
"""
from __future__ import annotations

import hashlib
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

EXPECTED_SHA256 = "3e3b4092a7ac5a7e78cd86df6e6287c69027bf6fe60c9396adf136a39b1943ad"
SOURCE_URL = "https://www.rochester.edu/college/faculty/hgoemans/data.htm"
MAX_PAGE = 100


def read_archigos(path: Path) -> tuple[list[dict], str]:
    """Read only the separately obtained and checksum-verified original .dta."""
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Archigos source must be a file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("Archigos 4.1 SHA-256 mismatch; refuse unknown dataset version")
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Archigos .dta analysis needs pandas in the research environment") from exc
    frame = pd.read_stata(path, convert_categoricals=False, convert_dates=False)
    required = {"leadid", "obsid", "leader", "idacr", "startdate", "enddate", "yrborn"}
    if not required.issubset(frame.columns):
        raise ValueError("Source columns differ from pinned Archigos 4.1 contract")
    return frame.to_dict(orient="records"), digest


def calculate_returnees(
    rows: list[dict],
    start_year: int = 1875,
    end_year: int = 2015,
    country_code: str = "",
    min_gap_days: int = 1,
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """Return gap statistics and a paginated, deterministic evidence list.

    Cohorts are grouped by both country code and leader UUID. Same-day
    adjacent spells do not count as departures. Period overlap is merged.
    Conflicting positive birth years cause an ID group to be quarantined.
    This conservative rule can exclude legitimate leaders with erroneous
    biographical metadata, a documented limitation of this first benchmark.
    """
    if not 1875 <= start_year <= end_year <= 2015:
        raise ValueError("Supported research window is 1875..2015")
    if not isinstance(min_gap_days, int) or not 1 <= min_gap_days <= 36525:
        raise ValueError("min_gap_days must be between 1 and 36525")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
        raise ValueError("limit must be 1..100")
    if not isinstance(offset, int) or not 0 <= offset <= 100000:
        raise ValueError("offset must be 0..100000")
    country_code = country_code.strip().upper()
    if country_code and (len(country_code) != 3 or not country_code.isalpha() or not country_code.isascii()):
        raise ValueError("country_code must be a three-letter Archigos code")

    buckets = defaultdict(list)
    for row in rows:
        country = str(row["idacr"]).strip().upper()
        if country_code and country != country_code:
            continue
        identity = str(row["leadid"]).strip().lower()
        if not identity or not country:
            continue
        start = date.fromisoformat(str(row["startdate"]))
        end = date.fromisoformat(str(row["enddate"]))
        if end < start:
            raise ValueError("Archigos spell end precedes start")
        birth = row.get("yrborn")
        birth_year = None
        if birth is not None:
            try:
                numeric = int(birth)
                if 1 <= numeric <= 2015:
                    birth_year = numeric
            except (TypeError, ValueError, OverflowError):
                pass
        buckets[(country, identity)].append({
            "start": start, "end": end, "obsid": str(row["obsid"]),
            "name": str(row["leader"]), "birth_year": birth_year,
        })

    returns = []
    anomalies = []
    for (country, identity), spells in sorted(buckets.items()):
        birth_years = sorted({x["birth_year"] for x in spells if x["birth_year"] is not None})
        if len(birth_years) > 1:
            anomalies.append({
                "country_code": country, "leadid": identity,
                "conflicting_birth_years": birth_years,
                "obsids": sorted({x["obsid"] for x in spells}),
                "status": "excluded_identity_conflict",
            })
            continue
        spells.sort(key=lambda x: (x["start"], x["end"], x["obsid"]))
        merged = []
        for spell in spells:
            if merged and spell["start"] <= merged[-1]["end"]:
                last = merged[-1]
                last["end"] = max(last["end"], spell["end"])
                last["obsids"].append(spell["obsid"])
            else:
                merged.append({
                    "start": spell["start"], "end": spell["end"],
                    "obsids": [spell["obsid"]], "name": spell["name"],
                })
        for previous, next_spell in zip(merged, merged[1:]):
            gap = (next_spell["start"] - previous["end"]).days
            # Require observed exit AND subsequent re-entry inside the window.
            if gap < min_gap_days or previous["end"].year < start_year or next_spell["start"].year > end_year:
                continue
            returns.append({
                "country_code": country, "leadid": identity,
                "leader_label": next_spell["name"],
                "previous_obsids": previous["obsids"],
                "return_obsids": next_spell["obsids"],
                "previous_end": previous["end"].isoformat(),
                "return_start": next_spell["start"].isoformat(),
                "gap_days": gap,
                "verification": "derived_from_archigos_not_identity_verified",
            })

    returns.sort(key=lambda x: (x["country_code"], x["return_start"], x["leadid"], x["return_obsids"]))
    days = [x["gap_days"] for x in returns]
    groups = Counter(x["country_code"] for x in returns)
    return {
        "dataset": "Archigos 4.1",
        "source_url": SOURCE_URL,
        "source_sha256": EXPECTED_SHA256,
        "method": "Separate country+leader UUID; union overlapping/touching spells; compute return_start - previous_end in days; exclude conflicting positive birth years.",
        "window": {"start_year": start_year, "end_year": end_year, "country_code": country_code or None, "min_gap_days": min_gap_days},
        "observations_in_input": len(rows),
        "return_events": len(returns),
        "unique_returning_country_person_keys": len({(x["country_code"], x["leadid"]) for x in returns}),
        "mean_gap_days": round(statistics.mean(days), 3) if days else None,
        "median_gap_days": statistics.median(days) if days else None,
        "events_by_country": dict(sorted(groups.items())),
        "excluded_conflicting_identity_groups": anomalies,
        "result_offset": offset,
        "result_limit": limit,
        "events": returns[offset:offset + limit],
        "page_has_more": offset + limit < len(returns),
        "historical_truth_verified_by_ci": False,
        "caveat": "These are coded leadership spells, not all legal offices. Same UUID is not sufficient proof of identity; unobserved or inconsistent birth dates remain a limitation.",
    }
