"""Two-way sync between the lead history and the live Google Sheet the rep works in.

  pull: read the Pipeline tab (Status, Rep, Contact, Last touch, Outcome notes, Do-not-contact)
        -> data/<client>/pipeline_status.json, used to skip contacted leads and score triggers
  push: append this week's Top Leads to the Pipeline tab with Status "New"

Auth: a Google service account. Put the whole key JSON in the GOOGLE_SERVICE_ACCOUNT_JSON secret and
share the sheet with the service account's email (Editor). Sheet ID lives in configs/<client>.json
under pipeline_sheet.id.

Usage: python3 sources/sheets_sync.py pull|push configs/<client>.json data/<client>"""
import json, os, sys, time, urllib.parse, urllib.request
import jwt  # PyJWT, uses the installed cryptography package for RS256

TAB = "Pipeline"
COLUMNS = ["Week", "Organization", "Vertical", "City", "County", "Trigger type", "Why now", "Website",
           "Main phone", "Key contacts (verify)", "Email security", "Status", "Rep", "Contact used",
           "Contact email", "Last touch", "Outcome notes"]
SCOPE = "https://www.googleapis.com/auth/spreadsheets"


def token():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or sys.exit("Missing GOOGLE_SERVICE_ACCOUNT_JSON secret.")
    sa = json.loads(raw)
    now = int(time.time())
    assertion = jwt.encode({"iss": sa["client_email"], "scope": SCOPE, "aud": sa["token_uri"],
                            "iat": now, "exp": now + 3600}, sa["private_key"], algorithm="RS256")
    data = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": assertion}).encode()
    with urllib.request.urlopen(sa["token_uri"], data, timeout=30) as r:
        return json.load(r)["access_token"]


def api(method, sheet_id, path, body=None, tok=None):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}{path}"
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def contacts_text(t):
    return "; ".join(f"{c['name']} ({c['title']})" + (f" {c['linkedin']}" if c.get("linkedin") else "")
                     for c in t.get("contacts", []))


def pull(cfg, data_dir):
    sid = cfg["pipeline_sheet"]["id"]
    res = api("GET", sid, f"/values/{urllib.parse.quote(TAB)}!A1:Q", tok=token())
    rows = res.get("values", [])
    if not rows:
        return
    head = rows[0]
    out = {}
    for r in rows[1:]:
        d = dict(zip(head, r + [""] * (len(head) - len(r))))
        if d.get("Organization"):
            out[f"{d['Week']}|{d['Organization']}"] = d
    json.dump(out, open(f"{data_dir}/pipeline_status.json", "w"), indent=1)
    print(f"pulled {len(out)} pipeline rows", file=sys.stderr)


def push(cfg, data_dir):
    sid = cfg["pipeline_sheet"]["id"]
    top = json.load(open(f"{data_dir}/top_leads.json"))
    week = top[0].get("week") if top else ""
    tok = token()
    existing = api("GET", sid, f"/values/{urllib.parse.quote(TAB)}!A2:B", tok=tok).get("values", [])
    have = {f"{r[0]}|{r[1]}" for r in existing if len(r) > 1}
    new = [[t.get("week", week), t["name"], t["vertical"], t["city"], t["county"], t.get("trigger_type", ""),
            t["why_now"], t.get("website", ""), t.get("phone", ""), contacts_text(t),
            t.get("email_security", ""), "New", "", "", "", "", ""]
           for t in top if f"{t.get('week', week)}|{t['name']}" not in have]
    if new:
        api("POST", sid, f"/values/{urllib.parse.quote(TAB)}!A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
            {"values": new}, tok=tok)
    print(f"pushed {len(new)} new rows", file=sys.stderr)


if __name__ == "__main__":
    action, cfg_path, data_dir = sys.argv[1:4]
    cfg = json.load(open(cfg_path))
    if not cfg.get("pipeline_sheet", {}).get("id"):
        sys.exit("No pipeline_sheet.id in config; skipping sheet sync.")
    {"pull": pull, "push": push}[action](cfg, data_dir)
