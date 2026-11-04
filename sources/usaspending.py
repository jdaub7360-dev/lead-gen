"""DoD contract recipients located in the client's counties (USAspending.gov, free, no key).
Pages through award records per county and aggregates by recipient. Each county is cached,
so a rerun after an API hiccup resumes where it stopped."""
import json, os, sys, time, urllib.request

API = "https://api.usaspending.gov/api/v2"
FIELDS = ["Recipient Name", "Award Amount", "recipient_id", "Recipient UEI", "Recipient Location", "Description", "NAICS"]


def _post(path, body, tries=7):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except Exception as e:  # this API returns intermittent 503s and empty replies
            if i == tries - 1:
                raise
            print(f"    retry {i + 1}: {e}", file=sys.stderr, flush=True)
            time.sleep(min(60, 3 * 2 ** i))


def county_recipients(cfg, fips, cache_dir):
    """One row per recipient, already summed by the API (far fewer pages than award records)."""
    path = f"{cache_dir}/dod_{fips}.json"
    if os.path.exists(path):
        return json.load(open(path))
    d = cfg["dod"]
    rows, page = [], 1
    while True:
        res = _post("/search/spending_by_category/recipient/", {
            "filters": {
                "award_type_codes": ["A", "B", "C", "D"],
                "agencies": [{"type": "awarding", "tier": "toptier", "name": d["agency"]}],
                "recipient_locations": [{"country": "USA", "state": cfg["state_abbr"], "county": fips}],
                "time_period": [{"start_date": d["start_date"], "end_date": d["end_date"]}],
            },
            "category": "recipient", "limit": 100, "page": page})
        rows += res.get("results", [])
        # results are sorted by amount; stop once we are below the minimum
        if not res.get("page_metadata", {}).get("hasNext") or (rows and (rows[-1].get("amount") or 0) < d["min_total"]):
            break
        page += 1
    json.dump(rows, open(path, "w"))
    return rows


def fetch(cfg, cache_dir):
    d = cfg["dod"]
    out = {}
    for fips, county in cfg["counties"].items():
        recs = county_recipients(cfg, fips, cache_dir)
        print(f"  {county}: {len(recs)} recipients", file=sys.stderr, flush=True)
        for r in recs:
            key = r.get("recipient_id") or r["name"]
            rec = out.setdefault(key, {"name": r["name"], "uei": r.get("uei"), "recipient_id": r.get("recipient_id"),
                                       "county": county, "dod_total": 0.0})
            rec["dod_total"] += r.get("amount") or 0
    skip = [k.upper() for k in d.get("exclude_name_keywords", []) + d.get("exclude_large_companies", [])]
    return [r for r in out.values() if d["min_total"] <= r["dod_total"] <= d["max_total"]
            and not any(k in r["name"].upper() for k in skip)]


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    cache = os.path.join(os.path.dirname(out_path) or ".", "cache")
    os.makedirs(cache, exist_ok=True)
    rows = fetch(cfg, cache)
    json.dump(rows, open(out_path, "w"), indent=1)
    print(len(rows), "DoD recipients written", file=sys.stderr)
