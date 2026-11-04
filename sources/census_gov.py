"""Cities, villages and townships with population (Census subcounty estimates, free).
Download: https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/cities/totals/sub-est2024_<fips>.csv"""
import csv, json, sys


def fetch(cfg, path):
    g = cfg["government"]
    best = {}
    for r in csv.DictReader(open(path, encoding="latin-1")):
        # 061 = county subdivision (townships, and cities/villages that are their own subdivision)
        # 157 = place-within-county part (cities/villages)
        if r["SUMLEV"] not in ("061", "157") or r["COUNTY"] not in cfg["counties"] or r["FUNCSTAT"] != "A":
            continue
        name = r["NAME"]
        pop = int(r["POPESTIMATE2024"] or 0)
        kind = ("Township" if name.endswith("township") else "City" if name.endswith("city")
                else "Village" if name.endswith("village") else None)
        if not kind or pop < g["min_population"]:
            continue
        key = (name, r["COUNTY"])
        if kind != "Township":
            key = (name, "")  # a city can straddle counties; keep one row with summed population
        rec = best.setdefault(key, {"name": name.replace(" city", "").replace(" village", "").replace(" township", "")
                                    + (" Township" if kind == "Township" else ""),
                                    "kind": kind, "county": cfg["counties"][r["COUNTY"]], "population": 0, "_seen": set()})
        if (r["SUMLEV"], r["COUNTY"], r["PLACE"]) in rec["_seen"]:
            continue
        rec["_seen"].add((r["SUMLEV"], r["COUNTY"], r["PLACE"]))
        if r["SUMLEV"] == "157" or kind == "Township":
            rec["population"] += pop
    rows = []
    for rec in best.values():
        rec.pop("_seen")
        if g["min_population"] <= rec["population"] <= g.get("max_population", 10**9):
            rec["segment"] = "Government (co-managed)" if rec["population"] >= g["co_managed_above"] else "Government"
            rows.append(rec)
    return rows


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    rows = fetch(cfg, sys.argv[2])
    json.dump(rows, open(sys.argv[3], "w"), indent=1)
    print(len(rows), "municipalities written", file=sys.stderr)
