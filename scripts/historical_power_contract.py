#!/usr/bin/env python3
"""HPM P1: validate synthetic transition fixtures, not historical evidence.

This module is intentionally isolated from canonical data, SQL, and publication.
It uses only the Python standard library and never writes anything.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("tests/fixtures/historical_power_synthetic_v1.json")
PREFIX = "fixture:"
DATE_PATTERNS = {
    "year": re.compile(r"[0-9]{4}\Z"),
    "month": re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])\Z"),
    "day": re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\Z"),
}
DATE_CALENDARS = {"julian", "gregorian", "unspecified"}
DATE_QUALIFIERS = {"as_recorded", "approximate", "disputed"}
ACTORS = {"person", "institution"}
CONTEXTS = {"polity", "polity_regime", "composite_monarchy", "other_context"}
ROLES = {"sovereign", "co_regent", "regent", "institutional", "other"}
EVENTS = {"accession", "election", "appointment", "coronation", "recognition",
          "death", "abdication", "resignation", "deposition", "seizure",
          "regime_change", "institutional_change"}
PARTICIPANTS = {"outgoing", "incoming", "contender", "electing_body",
                "appointing_body", "regent", "actor", "witness"}
DIMENSIONS = {
    "accession_mechanism": {"inheritance", "election", "appointment", "conquest",
                            "coup", "voluntary_transfer", "institutional_reform",
                            "other", "mixed", "unknown"},
    "departure_reason": {"death", "abdication", "resignation", "deposition",
                         "term_end", "office_abolished", "other", "unknown"},
    "violence": {"violent", "nonviolent", "mixed", "unknown"},
    "contestation": {"contested", "uncontested", "mixed", "unknown"},
    "dynastic_continuity": {"same_house", "change_of_house", "non_dynastic",
                             "mixed", "unknown"},
}
ABSENCE = {"unknown", "not_applicable", "institutional_change"}


def _required(item: object, keys: set[str], label: str) -> dict:
    if not isinstance(item, dict) or set(item) != keys:
        raise ValueError(f"{label}: required fields differ from {sorted(keys)}")
    return item


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty string required")
    return value


def _id(value: object, label: str) -> str:
    s = _text(value, label)
    if not s.startswith(PREFIX) or not re.fullmatch(r"fixture:[a-z0-9][a-z0-9-]*", s):
        raise ValueError(f"{label}: synthetic fixture IDs only")
    return s


def _unique(records: object, name: str, all_ids: set[str]) -> dict[str, dict]:
    if not isinstance(records, list):
        raise ValueError(f"{name}: list required")
    result = {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError(f"{name}: record must be an object")
        ident = _id(item.get("id"), f"{name}.id")
        if ident in all_ids:
            raise ValueError(f"{name}: duplicate ID {ident}")
        result[ident] = item
        all_ids.add(ident)
    return result


def _date(value: object) -> None:
    date = _required(value, {"value", "calendar", "precision", "qualifier"}, "date")
    precision = date["precision"]
    if precision not in DATE_PATTERNS or date["calendar"] not in DATE_CALENDARS \
            or date["qualifier"] not in DATE_QUALIFIERS:
        raise ValueError("date: invalid precision/calendar/qualifier")
    raw = date["value"]
    if not isinstance(raw, str) or not DATE_PATTERNS[precision].fullmatch(raw) \
            or raw[:4] == "0000":
        raise ValueError("date: literal precision or year invalid")
    if precision == "day":
        year, month, day = (int(x) for x in raw.split("-"))
        leap_gregorian = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        leap_julian = year % 4 == 0
        leap = (leap_gregorian if date["calendar"] == "gregorian"
                else leap_julian)  # unspecified: permit either, do not pick a calendar
        limit = (29 if leap else 28) if month == 2 else (30 if month in (4, 6, 9, 11) else 31)
        if day > limit:
            raise ValueError("date: impossible day for stated calendar")


def _refs(values: object, known: dict, label: str, *, may_be_empty: bool = False) -> list[str]:
    if not isinstance(values, list) or (not may_be_empty and not values) \
            or len(values) != len(set(x for x in values if isinstance(x, str))):
        raise ValueError(f"{label}: nonempty unique refs required unless explicitly optional")
    for ref in values:
        if not isinstance(ref, str) or ref not in known:
            raise ValueError(f"{label}: dangling reference {ref!r}")
    return values


def validate(document: dict) -> dict:
    """Raise ValueError on a broken synthetic contract; return unchanged input."""
    _required(document, {"schema_version", "synthetic_only", "historical_truth_verified_by_ci",
                         "scope", "actors", "contexts", "roles", "events", "sources",
                         "transitions"}, "document")
    if document["schema_version"] != "hpm-synthetic-v1" \
            or document["synthetic_only"] is not True \
            or document["historical_truth_verified_by_ci"] is not False:
        raise ValueError("document: synthetic-only / no historical verification invariant")
    scope = _required(document["scope"], {"id", "unit", "coverage"}, "scope")
    _id(scope["id"], "scope.id")
    if scope["unit"] != "transition" or scope["coverage"] != "synthetic_only":
        raise ValueError("scope: sample cannot certify historical population coverage")
    all_ids = {scope["id"]}
    actors = _unique(document["actors"], "actors", all_ids)
    contexts = _unique(document["contexts"], "contexts", all_ids)
    roles = _unique(document["roles"], "roles", all_ids)
    events = _unique(document["events"], "events", all_ids)
    sources = _unique(document["sources"], "sources", all_ids)
    transitions = _unique(document["transitions"], "transitions", all_ids)
    for actor in actors.values():
        _required(actor, {"id", "kind"}, "actor")
        if actor["kind"] not in ACTORS:
            raise ValueError("actor: invalid kind")
    for context in contexts.values():
        _required(context, {"id", "kind"}, "context")
        if context["kind"] not in CONTEXTS:
            raise ValueError("context: invalid kind")
    for role in roles.values():
        _required(role, {"id", "actor_id", "context_id", "kind"}, "role")
        if role["actor_id"] not in actors or role["context_id"] not in contexts:
            raise ValueError("role: actor/context reference missing")
        if role["kind"] not in ROLES:
            raise ValueError("role: unsupported role kind")
        if (role["kind"] == "institutional") != (actors[role["actor_id"]]["kind"] == "institution"):
            raise ValueError("role: institution cannot be silently treated as person")
    for event in events.values():
        _required(event, {"id", "kind", "date"}, "event")
        if event["kind"] not in EVENTS:
            raise ValueError("event: unsupported kind")
        _date(event["date"])
    for source in sources.values():
        _required(source, {"id", "kind", "locator"}, "source")
        if source["kind"] != "synthetic_fixture" or not _text(source["locator"], "source locator"):
            raise ValueError("source: only explicit synthetic evidence is permitted")
    for t in transitions.values():
        _required(t, {"id", "scope_ref", "context_refs", "outgoing_role_refs",
                      "incoming_role_refs", "absence", "event_refs", "participants",
                      "classification_claims"}, "transition")
        if t["scope_ref"] != scope["id"]:
            raise ValueError("transition: undeclared research scope")
        ctx = _refs(t["context_refs"], contexts, "transition contexts")
        outgoing = _refs(t["outgoing_role_refs"], roles, "outgoing roles", may_be_empty=True)
        incoming = _refs(t["incoming_role_refs"], roles, "incoming roles", may_be_empty=True)
        for ref in outgoing + incoming:
            if roles[ref]["context_id"] not in ctx:
                raise ValueError("transition: role context not in declared context_refs")
        absence = _required(t["absence"], {"outgoing", "incoming"}, "absence")
        for side, refs in (("outgoing", outgoing), ("incoming", incoming)):
            reason = absence[side]
            if (refs and reason is not None) or (not refs and reason not in ABSENCE):
                raise ValueError(f"transition: empty {side} roles require reason; populated roles require null")
        evrefs = _refs(t["event_refs"], events, "transition events")
        if not outgoing and not incoming and not any(events[e]["kind"] in
                                                   {"regime_change", "institutional_change"}
                                                   for e in evrefs):
            raise ValueError("transition: role-free transition requires an institutional event")
        participants = t["participants"]
        if not isinstance(participants, list):
            raise ValueError("participants: list required")
        for participant in participants:
            _required(participant, {"actor_id", "role"}, "participant")
            if participant["actor_id"] not in actors or participant["role"] not in PARTICIPANTS:
                raise ValueError("participant: actor/reference or role invalid")
            side = participant["role"]
            if side in {"incoming", "outgoing"}:
                side_roles = incoming if side == "incoming" else outgoing
                if not any(roles[ref]["actor_id"] == participant["actor_id"] for ref in side_roles):
                    raise ValueError("participant: role occupant not in transition role links")
        claims = t["classification_claims"]
        if not isinstance(claims, list):
            raise ValueError("claims: list required")
        for claim in claims:
            _required(claim, {"id", "dimension", "value", "source_refs", "verification",
                              "caveat"}, "classification claim")
            cid = _id(claim["id"], "claim.id")
            if cid in all_ids:
                raise ValueError("classification claim: duplicate ID")
            all_ids.add(cid)
            if claim["dimension"] not in DIMENSIONS or \
                    claim["value"] not in DIMENSIONS[claim["dimension"]]:
                raise ValueError("classification claim: unqualified or unsupported classification")
            if claim["verification"] != "synthetic_only" or \
                    not _text(claim["caveat"], "claim caveat"):
                raise ValueError("classification claim: cannot claim historical verification")
            evidence = claim["source_refs"]
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("classification claim: source provenance required")
            seen = set()
            for ref in evidence:
                _required(ref, {"source_id", "pinpoint"}, "claim source reference")
                if ref["source_id"] not in sources or ref["source_id"] in seen \
                        or not _text(ref["pinpoint"], "source pinpoint"):
                    raise ValueError("classification claim: source/pinpoint missing or duplicated")
                seen.add(ref["source_id"])
    return document


def fixture(root: Path = ROOT) -> dict:
    """Read test-only data, not canonical history. No file mutations."""
    return validate(json.loads((root / FIXTURE).read_text(encoding="utf-8")))


def claims_for(document: dict, transition_id: str, dimension: str) -> dict:
    """Expose alternatives; never adjudicate and never calculate a percentage."""
    if dimension not in DIMENSIONS:
        raise ValueError("Unsupported classification dimension")
    t = next((t for t in document["transitions"] if t["id"] == transition_id), None)
    if t is None:
        raise ValueError("Unknown transition")
    claims = [c for c in t["classification_claims"] if c["dimension"] == dimension]
    values = sorted({c["value"] for c in claims})
    state = ("not_studied" if not claims else "competing_claims" if len(values) > 1
             else "unknown" if values == ["unknown"] else "mixed" if values == ["mixed"]
             else "classified")
    return {"state": state, "values": values, "claim_ids": [c["id"] for c in claims],
            "source_refs": [ref for c in claims for ref in c["source_refs"]]}


if __name__ == "__main__":
    d = fixture()
    print(f"HPM synthetic contract valid: {len(d['transitions'])} transitions")
