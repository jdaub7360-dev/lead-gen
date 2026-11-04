"""E-Rate (USAC open data, free) for schools and libraries in the client's territory:

  competitor_clients.json  organizations whose E-Rate services come from named competitors, with the
                           latest contract expiration (renewal timing) and entity address/phone
  erate_bids.json          FCC Form 470 bid requests posted in the last ~6 months (open procurements),
                           with the contact person
  cyber_pilot_bids.json    Schools & Libraries Cybersecurity Pilot Form 470s (buying cybersecurity)

Datasets: qdmp-ygft (FRN status), 7i5i-83qf (entities), jp7a-89nd + 39tn-hjzv (Form 470), bik4-z7ge (pilot 470).
Usage: python3 sources/erate.py configs/<client>.json data/<client>"""
import collections, datetime, json, os, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import geo

API = "https://opendata.usac.org/resource/{}.json"


def q(ds, where, select=None, limit=50000):
    params = {"$where": where, "$limit": limit}
    if select:
        params["$select"] = select
    url = API.format(ds) + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception:
            if attempt == 2:
                raise


def in_territory(cfg, zip_code):
    office, miles = geo.nearest_office(cfg, geo.point_for_zip((zip_code or "")[:5]))
    ok = miles is not None and miles <= cfg.get("max_miles_from_office", 45)
    return ok, office, miles


def entities(bens):
    out = {}
    bens = list(bens)
    for i in range(0, len(bens), 150):
        chunk = ",".join(f"'{b}'" for b in bens[i:i + 150])
        for e in q("7i5i-83qf", f"entity_number in ({chunk})"):
            out[e["entity_number"]] = e
    return out


def competitor_clients(cfg):
    st = cfg["state_abbr"]
    rows = []
    for name in cfg.get("competitors", []):
        key = name["erate_spin_match"].upper().replace("'", "''")
        rows += q("qdmp-ygft", f"upper(spin_name) like '%{key}%' AND state='{st}'")
    org = collections.defaultdict(lambda: {"years": set(), "services": collections.Counter(), "spend_recent": 0.0,
                                          "contract_end": "", "vendor": "", "contact_email": "", "ben": "", "type": ""})
    for r in rows:
        o = org[(r["ben"], r["spin_name"])]
        y = int(r["funding_year"])
        o["years"].add(y)
        o["services"][r.get("form_471_service_type_name", "")] += 1
        if y >= datetime.date.today().year - 2:
            o["spend_recent"] += float(r.get("total_pre_discount_costs") or 0)
        end = (r.get("contract_expiration_date") or "")[:10]
        o["contract_end"] = max(o["contract_end"], end)
        o.update(vendor=r["spin_name"], ben=r["ben"], name=r["organization_name"].strip(),
                 type=r.get("organization_entity_type_name", ""))
        if y == max(o["years"]):
            o["contact_email"] = r.get("cnct_email", "")
    ents = entities({o["ben"] for o in org.values()})
    out = []
    this_year = datetime.date.today().year
    for o in org.values():
        if max(o["years"]) < this_year - 1:
            continue  # no longer an active customer
        e = ents.get(o["ben"], {})
        z = e.get("physical_zipcode") or e.get("mailing_zipcode") or ""
        ok, office, miles = in_territory(cfg, z)
        if not ok:
            continue
        out.append({"name": o["name"], "vendor": o["vendor"], "type": o["type"], "ben": o["ben"],
                    "first_year": min(o["years"]), "last_year": max(o["years"]), "contract_end": o["contract_end"],
                    "spend_recent": round(o["spend_recent"]), "services": ", ".join(s for s, _ in o["services"].most_common(3)),
                    "contact_email": o["contact_email"], "phone": e.get("phone_number", ""),
                    "address": e.get("physical_address", ""), "city": (e.get("physical_city") or "").title(), "zip": z[:5],
                    "office": office, "miles": miles})
    out.sort(key=lambda r: (r["contract_end"] or "9999", -r["spend_recent"]))
    return out


def open_bids(cfg):
    st = cfg["state_abbr"]
    since = (datetime.date.today() - datetime.timedelta(days=183)).isoformat()
    forms = q("jp7a-89nd", f"billed_entity_state='{st}' AND certified_datetime >= '{since}'")
    apps = {f["application_number"] for f in forms}
    services = collections.defaultdict(list)
    for i, chunk in enumerate([list(apps)[k:k + 150] for k in range(0, len(apps), 150)]):
        ids = ",".join(f"'{a}'" for a in chunk)
        for s in q("39tn-hjzv", f"application_number in ({ids})"):
            label = " / ".join(filter(None, [s.get("service_category"), s.get("service_type"), s.get("function")]))
            if label and label not in services[s["application_number"]]:
                services[s["application_number"]].append(label)
    out = []
    for f in forms:
        ok, office, miles = in_territory(cfg, f.get("billed_entity_zip"))
        if not ok:
            continue
        out.append({"name": (f.get("billed_entity_name") or "").title(), "city": (f.get("billed_entity_city") or "").title(),
                    "zip": (f.get("billed_entity_zip") or "")[:5], "office": office, "miles": miles,
                    "funding_year": f.get("funding_year"), "posted": (f.get("certified_datetime") or "")[:10],
                    "contract_allowed_from": (f.get("allowable_contract_date") or "")[:10],
                    "applicant_type": f.get("applicant_type", ""), "nickname": f.get("form_nickname", ""),
                    "services": "; ".join(services.get(f["application_number"], []))[:300],
                    "contact": f.get("contact_name", ""), "contact_email": f.get("contact_email", ""),
                    "contact_phone": f.get("contact_phone", ""),
                    "tech_contact": f.get("technical_contact_name", ""), "tech_title": f.get("technical_contact_title", ""),
                    "rfp": f.get("rfp_identifier", ""), "application_number": f["application_number"],
                    "status": f.get("f470_status", "")})
    out.sort(key=lambda r: r["contract_allowed_from"] or r["posted"], reverse=True)
    return out


def cyber_pilot(cfg):
    st = cfg["state_abbr"]
    out = []
    for f in q("bik4-z7ge", f"billed_entity_state='{st}'"):
        ok, office, miles = in_territory(cfg, f.get("billed_entity_zip"))
        if not ok:
            continue
        out.append({"name": (f.get("billed_entity_name") or "").title(), "city": (f.get("billed_entity_city") or "").title(),
                    "zip": (f.get("billed_entity_zip") or "")[:5], "office": office, "miles": miles,
                    "posted": (f.get("certified_date_time") or "")[:10],
                    "contract_allowed_from": (f.get("allowable_contract_date") or "")[:10],
                    "services": (f.get("equipment_and_service_type") or "")[:200], "nickname": f.get("form_nickname", ""),
                    "contact": f.get("main_contact_name", ""), "contact_email": f.get("main_contact_email", ""),
                    "contact_phone": f.get("main_contact_phone", ""), "tech_contact": f.get("technical_contact_name", ""),
                    "tech_title": f.get("technical_contact_title", ""), "status": f.get("fcc_form_470_status", ""),
                    "narrative": (f.get("narrative") or "")[:300]})
    out.sort(key=lambda r: r["posted"], reverse=True)
    return out


def dedupe(rows, key, merge_field):
    out = {}
    for r in rows:
        k = key(r)
        if k in out:
            if r[merge_field] and r[merge_field] not in out[k][merge_field]:
                out[k][merge_field] = (out[k][merge_field] + "; " + r[merge_field])[:400]
        else:
            out[k] = dict(r)
    return list(out.values())


if __name__ == "__main__":
    import re
    cfg = json.load(open(sys.argv[1]))
    d = sys.argv[2]
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
    results = {}
    for name, fn in [("competitor_clients", competitor_clients), ("erate_bids", open_bids), ("cyber_pilot_bids", cyber_pilot)]:
        try:
            results[name] = fn(cfg)
        except Exception as ex:
            print(f"!! {name} failed: {ex}", file=sys.stderr)
    if "erate_bids" in results:
        results["erate_bids"] = dedupe(results["erate_bids"], lambda r: r["application_number"], "services")
    if "cyber_pilot_bids" in results:
        results["cyber_pilot_bids"] = dedupe(results["cyber_pilot_bids"], lambda r: norm(r["name"]), "services")
    if "competitor_clients" in results and "erate_bids" in results:
        posted = {norm(b["name"]): b for b in results["erate_bids"]}
        for r in results["competitor_clients"]:
            b = posted.get(norm(r["name"]))
            r["bid_posted"] = f"{b['posted']} (contracts from {b['contract_allowed_from']})" if b else ""
    for name, rows in results.items():
        json.dump(rows, open(f"{d}/{name}.json", "w"), indent=1)
        print(f"{len(rows)} {name}", file=sys.stderr)
