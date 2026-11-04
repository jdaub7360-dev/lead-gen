"""Merge enrichment into the client's data files.

  domains  -> write data/<client>/domains.json (every website we know: Top Leads, 990s, governments, schools)
  top      -> add website, phone, contacts, LinkedIn search links, trigger type and email-security
              findings to data/<client>/top_leads.json

LinkedIn: we never scrape LinkedIn. We generate LinkedIn *search* links (person name + organization),
which open LinkedIn's own search for the rep.
Usage: python3 enrich.py domains|top data/<client>"""
import json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sources"))
import geo


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def li_person(name, org):
    q = urllib.parse.quote(f"{re.sub(r'\\(.*?\\)', '', name).strip()} {org}")
    return f"https://www.linkedin.com/search/results/people/?keywords={q}"


def li_company(org):
    return f"https://www.linkedin.com/search/results/companies/?keywords={urllib.parse.quote(org)}"


def ein_from(t):
    for s in t.get("sources", []):
        m = re.search(r"/organizations/(\d{9})", s)
        if m:
            return m.group(1)
    return t.get("ein", "")


def domains(d):
    out = set()
    for t in load(f"{d}/top_leads.json", []):
        out.add(t.get("website", ""))
    for v in load(f"{d}/top_leads_contacts.json", {}).values():
        if isinstance(v, dict) and v.get("website"):
            out.add(v["website"])
    for v in load(f"{d}/enrich_990.json", {}).values():
        out.add(v.get("website", ""))
    for v in load(f"{d}/gov_directory.json", {}).values():
        out.add(v.get("website", ""))
    for v in load(f"{d}/schools.json", []):
        out.add(v.get("website", ""))
    clean = sorted({re.sub(r"^www\.", "", x.strip().lower().split("/")[0]) for x in out
                    if x and "." in x and "@" not in x and " " not in x.strip()})
    json.dump(clean, open(f"{d}/domains.json", "w"), indent=0)
    print(f"{len(clean)} domains -> {d}/domains.json", file=sys.stderr)


def top(d):
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "configs", os.path.basename(d.rstrip("/")) + ".json")))
    nps = load(f"{d}/nonprofits.json", [])
    leads = load(f"{d}/top_leads.json", [])
    e990 = load(f"{d}/enrich_990.json", {})
    manual = load(f"{d}/top_leads_contacts.json", {})
    triggers = manual.get("_trigger_types", {})
    checks = load(f"{d}/domain_checks.json", {})
    for t in leads:
        name = t["name"]
        ein = ein_from(t)
        if ein:
            t["ein"] = ein
        f = e990.get(ein.zfill(9)) if ein else None
        if f and "error" not in f:
            t.setdefault("website", "")
            t["website"] = t["website"] or f["website"]
            t["phone"] = t.get("phone") or f["phone"]
            t["employees"] = f["employees"]
            def rank(o):
                t = o["title"].lower()
                if re.search(r"\b(ceo|chief executive|executive director|president)\b", t) and "vice" not in t:
                    return 0
                if re.search(r"\b(cfo|chief financial|coo|chief operating|finance|operations)\b", t):
                    return 1
                return 2
            paid = sorted([o for o in f["officers"] if o["comp"] > 0], key=lambda o: (rank(o), -o["comp"]))
            people = [{"name": o["name"], "title": o["title"]} for o in paid]
            names = {p["name"] for p in people}
            if f["principal_officer"] and f["principal_officer"] not in names:
                people.append({"name": f["principal_officer"], "title": "Listed as principal officer on 990"})
            chair = next((o for o in f["officers"] if "chair" in o["title"].lower() and o["comp"] == 0), None)
            if chair and len(people) < 3:
                people.append({"name": chair["name"], "title": f"{chair['title']} (board)"})
            t["contacts"] = people[:3]
            t["contacts_source"] = f"IRS Form 990, period ending {f['tax_period_end']}"
        m = manual.get(name)
        if m and m.get("zip"):
            t["zip"] = m["zip"]
        if m:
            t["website"] = m.get("website") or t.get("website", "")
            t["phone"] = m.get("phone") or t.get("phone", "")
            if m.get("contacts"):
                t["contacts"] = m["contacts"]
                t["contacts_source"] = "; ".join(sorted({c["source"] for c in m["contacts"]}))
        for c in t.get("contacts", []):
            c["linkedin"] = li_person(c["name"], name)
        t["linkedin_company"] = li_company(name)
        t["website"] = re.sub(r"^(https?://)?(www\.)?", "", t.get("website", "")).strip("/")
        point = geo.point_for_zip(t["zip"]) if t.get("zip") else None
        if not point and ein:
            np_row = next((x for x in nps if x["ein"].zfill(9) == ein.zfill(9)), None)
            point = geo.point_for_zip(np_row["zip"]) if np_row else None
        if not point:
            fips = next((k for k, v in cfg["counties"].items() if v == t["county"]), None)
            point = geo.point_for_county(cfg["state_fips"], fips) if fips else None
        t["office"], t["miles"] = geo.nearest_office(cfg, point)
        t["trigger_type"] = triggers.get(name, t.get("trigger_type", ""))
        dom = re.sub(r"^www\.", "", (t.get("website") or "").split("/")[0])
        chk = checks.get(dom)
        t["email_security"] = "; ".join(chk["findings"]) if chk and chk["findings"] else ("No issues found" if chk else "")
    for t in leads:
        score_and_script(cfg, t, checks)
    leads.sort(key=lambda t: -t["score"])
    json.dump(leads, open(f"{d}/top_leads.json", "w"), indent=1)
    print(f"enriched {len(leads)} top leads", file=sys.stderr)


def score_and_script(cfg, t, checks):
    """Appointment score, first-meeting offer, CTA, phone opener and voicemail."""
    import datetime
    w = cfg["scoring"]
    parts = []
    trig = t.get("trigger_type", "")
    pts = w["trigger"].get(trig, 8)
    parts.append(f"trigger {pts}")
    days = None
    if t.get("trigger_date"):
        days = (datetime.date.today() - datetime.date.fromisoformat(t["trigger_date"])).days
    rec = next((p for lim, p in w["recency_days"] if days is not None and days <= lim), w["recency_unknown"] if days is None else 0)
    parts.append(f"recency {rec}")
    cs = t.get("contacts", [])
    if cs and not any("verify" in c["title"].lower() for c in cs[:1]):
        con = w["named_contact"]
    elif cs:
        con = w["named_contact_verify"]
    else:
        con = 0
    parts.append(f"contact {con}")
    ph = w["phone"] if t.get("phone") else 0
    parts.append(f"phone {ph}")
    mi = t.get("miles")
    near = next((p for lim, p in w["miles"] if mi is not None and mi <= lim), 0)
    parts.append(f"distance {near}")
    dom = re.sub(r"^www\.", "", (t.get("website") or "").split("/")[0])
    chk = checks.get(dom) or {}
    hook = any(f.startswith(("No DMARC", "DMARC set to monitor")) for f in chk.get("findings", []))
    em = w["email_finding"] if hook else 0
    parts.append(f"email hook {em}")
    size = w["size_large"] if (t.get("employees") or 0) > 500 else w["size_fit"]
    parts.append(f"size {size}")
    t["score"] = pts + rec + con + ph + near + em + size
    t["score_why"] = ", ".join(parts)
    t["trigger_age_days"] = days

    offer = cfg["offers"].get(trig) or cfg["offers"]["Good fit, no trigger"]
    t["offer"] = offer
    t["email_offer"] = cfg["offers"]["_email_security"] if hook else ""
    t["cta"] = (f"Would {offer} be useful? I can do [Tuesday at 10] or [Thursday at 2], 15-30 minutes, "
                f"by phone or at your office.")
    for k in ("body",):
        if "{cta}" in t.get(k, ""):
            t[k + "_final"] = t[k].replace("{cta}", t["cta"])
        else:
            t[k + "_final"] = t.get(k, "")
    office = t.get("office") or "Northeast Ohio"
    reason = t.get("call_reason") or "we help organizations like yours with IT and security"
    t["phone_opener"] = (f"Hi {{first_name}}, this is [Rep name] with infinIT, the IT company in {office}. "
                         f"I'll be quick: {reason}. We're offering {offer}. "
                         f"Is that worth 15 minutes next week?")
    t["voicemail"] = (f"Hi {{first_name}}, [Rep name] with infinIT in {office}. Calling because {reason}. "
                      f"I'll send a short email too. My number is [phone]. Again, [Rep name], infinIT, [phone].")


if __name__ == "__main__":
    {"domains": domains, "top": top}[sys.argv[1]](sys.argv[2])
