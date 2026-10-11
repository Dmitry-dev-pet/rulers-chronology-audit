"""Audit source coverage, not historical absence, in Europe 1762–1800."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"data/atlas/world-pilots"

def read(name):
    return json.loads((P/name).read_text(encoding="utf-8"))

def coverage():
    base=read("1762.json")
    dyn=read("dynasty-1762-1780.json")
    ext=read("extension-1781-1800.json")
    states=base["countries"]+dyn["additional_polities"]+ext["additional_polities"]
    roles=dyn["roles"]+ext["additional_roles"]
    institutions=ext["institutions"]
    records=[]
    for state in states:
        years=[]
        for year in range(1762,1801):
            active=[r for r in roles if r["polity_id"]==state["id"] and r["start_year"]<=year<=r["end_year"]]
            organs=[x for x in institutions if x["polity_id"]==state["id"] and x["start_year"]<=year<=x["end_year"]]
            if state["id"]=="meck":
                status="context_only"
            elif year<state.get("introduced_from",1762):
                status="not_researched"
            elif active or organs:
                status="documented_roles"
            else:
                status="gap_or_transition"
            years.append({"year":year,"status":status,
                "role_ids":[r["id"] for r in active],
                "institution_ids":[x["id"] for x in organs]})
        records.append({"polity_id":state["id"],"name":state["name"],
            "kind":state.get("kind"),"years":years})
    return {"schema_version":"europe-coverage-v1",
      "period":{"start":1762,"end":1800},
      "methodology":"Documented role coverage, NOT a claim of historical completeness. Year intersections are not same-day rule.",
      "states":records}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("coverage-1762-1800.json"))
    args=p.parse_args()
    args.output.write_text(json.dumps(coverage(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
