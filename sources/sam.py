"""Websites and official points of contact for DoD suppliers, from SAM.gov (Entity Management API v3).

Free public API key (SAM.gov profile -> "Public API Key") stored as the SAM_API_KEY secret.
A personal key with no SAM.gov role allows only 10 requests/day, so this:
  - asks for 10 UEIs per request (one page of 10 records resolves 10 suppliers),
  - spends at most SAM_DAILY_CALLS requests per day (default 9) and records usage in the cache,
  - fills the cache highest-priority first (tier A dollar range, closest to an office),
  - never re-fetches a supplier fetched in the last 180 days.
Public data only: website, physical address, POC names and titles (POC emails/phones are restricted).
Keys expire every 90 days; regenerate on SAM.gov and update the secret.
Usage: python3 sources/sam.py configs/<client>.json data/<client>"""
import datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import geo

BASE = "https://api.sam.gov/entity-information/v3/entities"


def pocs(entity):
    out = []
    for kind, poc in (entity.get("pointsOfContact") or {}).items():
        if isinstance(poc, dict) and (poc.get("firstName") or poc.get("lastName")):
            name = " ".join(filter(None, [poc.get("firstName"), poc.get("middleInitial"), poc.get("lastName")])).title()
            label = {"governmentBusinessPOC": "Government business POC", "electronicBusinessPOC": "Electronic business POC",
                     "pastPerformancePOC": "Past performance POC"}.get(kind, kind)
            title = (poc.get("title") or "").title()
            out.append({"name": name, "title": title or label, "role": label})
    order = {"Government business POC": 0, "Electronic business POC": 1}
    out.sort(key=lambda p: order.get(p["role"], 9))
    seen, uniq = set(), []
    for p in out:
        if p["name"] not in seen:
            seen.add(p["name"])
            uniq.append(p)
    return uniq


def parse(entity):
    reg = entity.get("entityRegistration") or {}
    core = entity.get("coreData") or {}
    info = core.get("entityInformation") or {}
    addr = core.get("physicalAddress") or {}
    web = (info.get("entityURL") or "").strip().lower()
    for pre in ("https://", "http://"):
        web = web.removeprefix(pre)
    web = web.removeprefix("www.").strip("/")
    return {"uei": reg.get("ueiSAM", ""), "legal_name": reg.get("legalBusinessName", ""),
            "dba": reg.get("dbaName", ""), "registration_status": reg.get("registrationStatus", ""),
            "website": web, "city": (addr.get("city") or "").title(), "zip": (addr.get("zipCode") or "")[:5],
            "address": (addr.get("addressLine1") or "").title(), "contacts": pocs(entity),
            "fetched": datetime.date.today().isoformat()}


def main(cfg_path, d):
    key = os.environ.get("SAM_API_KEY")
    if not key:
        print("SAM_API_KEY not set; skipping SAM.gov enrichment.", file=sys.stderr)
        return
    cfg = json.load(open(cfg_path))
    path = f"{d}/sam_cache.json"
    cache = json.load(open(path)) if os.path.exists(path) else {"_usage": {}, "entities": {}}
    today = datetime.date.today().isoformat()
    budget = int(os.environ.get("SAM_DAILY_CALLS", "9")) - cache["_usage"].get(today, 0)
    stale = (datetime.date.today() - datetime.timedelta(days=180)).isoformat()

    dod = json.load(open(f"{d}/dod.json"))
    lo, hi = 100000, 20000000

    def priority(x):
        office, miles = geo.nearest_office(cfg, geo.point_for_county(
            cfg["state_fips"], next((k for k, v in cfg["counties"].items() if v == x["county"]), "")))
        return (0 if lo <= x["dod_total"] <= hi else 1, miles if miles is not None else 99, -x["dod_total"])

    todo = [x["uei"] for x in sorted(dod, key=priority)
            if x.get("uei") and cache["entities"].get(x["uei"], {}).get("fetched", "") < stale]
    print(f"{len(todo)} suppliers need SAM.gov data; {max(budget, 0)} requests left today", file=sys.stderr)
    calls = 0
    for i in range(0, len(todo), 10):
        if calls >= budget:
            break
        batch = todo[i:i + 10]
        params = {"api_key": key, "ueiSAM": "[" + "~".join(batch) + "]",
                  "includeSections": "entityRegistration,coreData,pointsOfContact"}
        url = BASE + "?" + urllib.parse.urlencode(params, safe="[]~,")
        try:
            calls += 1
            with urllib.request.urlopen(url, timeout=90) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")[:200]
            print(f"!! SAM.gov HTTP {e.code}: {msg}", file=sys.stderr)
            if e.code in (401, 403, 429):
                break  # bad/expired key or daily limit reached
            continue
        found = set()
        for ent in data.get("entityData", []) or []:
            rec = parse(ent)
            if rec["uei"]:
                cache["entities"][rec["uei"]] = rec
                found.add(rec["uei"])
        for u in batch:
            if u not in found:
                cache["entities"][u] = {"uei": u, "not_found": True, "fetched": today}
        time.sleep(1)
    cache["_usage"][today] = cache["_usage"].get(today, 0) + calls
    json.dump(cache, open(path, "w"), indent=1)
    have = sum(1 for v in cache["entities"].values() if not v.get("not_found"))
    print(f"SAM.gov: {calls} requests today; {have} suppliers with data in cache", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:3])
