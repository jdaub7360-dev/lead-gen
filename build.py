"""Build the lead workbook for one client from the source data files.
Usage: python3 build.py configs/<client>.json data/ output/<file>.xlsx"""
import json, sys, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3A5F")
INPUT_FILL = PatternFill("solid", fgColor="FFF4CC")
STATUSES = ["New", "Researching", "Contact found", "Emailed", "Follow-up 1", "Follow-up 2",
            "Replied", "Meeting booked", "Moved to HubSpot", "Not a fit", "Do not contact"]


def style_header(ws, headers, widths):
    ws.append(headers)
    for i, (h, w) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HDR_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    ws.row_dimensions[1].height = 32


def finish(ws, status_col, tier_col=None):
    n = ws.max_row
    for row in ws.iter_rows(min_row=2, max_row=n):
        for c in row:
            c.font = Font(name=FONT, size=10)
            c.alignment = Alignment(vertical="top", wrap_text=False)
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"{status_col}2:{status_col}{max(n, 2) + 500}")
    ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{n}"
    if tier_col:
        rng = f"{tier_col}2:{tier_col}{n + 500}"
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{tier_col}2="A"'], fill=PatternFill("solid", fgColor="CDEFD6")))
        ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{tier_col}2="B"'], fill=PatternFill("solid", fgColor="FFF0C2")))


def hubspot_check(col):
    # Flags a row when its organization name appears in the Suppression tab (pasted from HubSpot)
    return f'=IF(COUNTIF(Suppression!$A:$A,{col}{{r}})>0,"In HubSpot","")'


def build(cfg, data_dir, out):
    wb = Workbook()
    today = datetime.date.today().isoformat()

    # ---------- Start Here ----------
    ws = wb.active
    ws.title = "Start Here"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 110
    rows = [
        (f"{cfg['client']} lead pipeline", ""),
        ("Built", today),
        ("Tabs", "Top Leads: researched accounts with draft emails, worked first.\n"
                 "Manufacturing (DoD), Nonprofits, Healthcare, Religious, Government: full prospect lists, tiered A/B/C.\n"
                 "Apollo Import: upload to Apollo (Lists > Import CSV, as Companies) to find decision-makers.\n"
                 "Apollo Searches: saved-search recipes for segments that have no public list (professional services, private practices, manufacturers without DoD work).\n"
                 "Suppression: paste HubSpot company names here; every tab flags matches in the 'In HubSpot?' column.\n"
                 "Settings: the thresholds that drive the A/B/C tiers. Yellow cells are editable inputs."),
        ("Weekly workflow", "1. Paste a fresh HubSpot company export into Suppression (column A, names only).\n"
                            "2. Work Top Leads first: find the contact in Apollo, personalize the draft, send from your Outlook, set Status.\n"
                            "3. Then take Tier A rows from the vertical tabs, a batch at a time, through Apollo.\n"
                            "4. When a lead replies or books a meeting, set Status to 'Moved to HubSpot' and create it in HubSpot by hand.\n"
                            "   This sheet never writes to HubSpot, so the ConnectWise sync is untouched."),
        ("Sending limits", "Keep cold email from a rep's main infinit.us inbox to roughly 30-50 per day, plain text, no attachments, "
                           "and stop following up after 2 follow-ups. Every email needs infinIT's postal address and a way to opt out "
                           "(CAN-SPAM). Mark opt-outs 'Do not contact'."),
        ("Status values", ", ".join(STATUSES)),
        ("Sources", "IRS Exempt Organizations Business Master File (eo_oh.csv); USAspending.gov DoD contract awards "
                    f"{cfg['dod']['start_date']} to {cfg['dod']['end_date']}; U.S. Census Bureau subcounty population estimates 2024; "
                    "web research for Top Leads (links in each row)."),
        ("Caveats", "Revenue figures come from each organization's latest IRS filing and can be a year or two old. "
                    "DoD totals are contract obligations to that location, not company revenue. Verify before quoting a number to a prospect."),
    ]
    for r in rows:
        ws.append(r)
    ws["A1"].font = Font(name=FONT, bold=True, size=14)
    for row in ws.iter_rows(min_row=2):
        row[0].font = Font(name=FONT, bold=True)
        row[1].font = Font(name=FONT)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        row[0].alignment = Alignment(vertical="top")

    # ---------- Settings ----------
    st = wb.create_sheet("Settings")
    st.column_dimensions["A"].width = 44
    st.column_dimensions["B"].width = 16
    st.column_dimensions["C"].width = 70
    st.append(["Setting", "Value", "Note"])
    settings = [
        ("Nonprofit revenue, tier A minimum", cfg["nonprofit"]["sweet_spot"][0], "Roughly 20+ staff"),
        ("Nonprofit revenue, tier A maximum", cfg["nonprofit"]["sweet_spot"][1], "Above this, most have internal IT (co-managed angle)"),
        ("DoD obligations, tier A minimum", 100000, "Repeat DoD supplier, handles controlled information"),
        ("DoD obligations, tier A maximum", 20000000, "Above this, likely a larger company with its own IT"),
        ("Municipality population, tier A minimum", 5000, "Big enough to budget for managed IT"),
        ("Municipality population, tier A maximum", cfg["government"]["co_managed_above"], "Above this, likely an IT department (co-managed angle)"),
    ]
    for s in settings:
        st.append(list(s))
    for c in st[1]:
        c.font = Font(name=FONT, bold=True, color="FFFFFF"); c.fill = HDR_FILL
    for r in range(2, len(settings) + 2):
        st.cell(r, 2).fill = INPUT_FILL
        st.cell(r, 2).number_format = "#,##0"
        for col in (1, 2, 3):
            st.cell(r, col).font = Font(name=FONT)
    st.append([])
    st.append(["Yellow cells are inputs. Tier formulas on the list tabs read these values."])
    st.cell(st.max_row, 1).font = Font(name=FONT, italic=True)

    # ---------- Top Leads ----------
    top = json.load(open(f"{data_dir}/top_leads.json"))
    tl = wb.create_sheet("Top Leads", 1)
    h = ["#", "Organization", "Vertical", "City", "County", "Website", "Size signal", "Why now (trigger)",
         "Angle", "Who to find in Apollo", "Email subject", "Email body (draft)", "Follow-up 1 (day 4)",
         "Follow-up 2 (day 10)", "Status", "Rep", "Contact name", "Contact email", "Last touch", "Notes",
         "Sources", "In HubSpot?"]
    style_header(tl, h, [4, 30, 18, 14, 11, 24, 26, 48, 40, 28, 34, 70, 50, 50, 15, 12, 18, 24, 12, 30, 40, 12])
    for i, t in enumerate(top, 1):
        r = i + 1
        tl.append([i, t["name"], t["vertical"], t["city"], t["county"], t.get("website", ""), t["size"], t["why_now"],
                   t["angle"], t["contact_role"], t["subject"], t["body"], t["fu1"], t["fu2"], "New", "", "", "", "",
                   t.get("notes", ""), "\n".join(t.get("sources", [])), hubspot_check("B").format(r=r)])
    finish(tl, "O")
    for row in tl.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    for r in range(2, tl.max_row + 1):
        tl.row_dimensions[r].height = 220

    # ---------- DoD manufacturing ----------
    dod = sorted(json.load(open(f"{data_dir}/dod.json")), key=lambda r: -r["dod_total"])
    md = wb.create_sheet("Manufacturing (DoD)")
    h = ["Tier", "Company", "City", "County", "Address", "ZIP", "DoD obligations FY24-FY26 ($)", "DoD awards (count)",
         "What they sold DoD (sample)", "Industry (NAICS)", "UEI", "USAspending profile", "Status", "Notes", "In HubSpot?"]
    style_header(md, h, [6, 38, 16, 11, 30, 8, 16, 10, 50, 34, 15, 30, 15, 30, 12])
    for i, d in enumerate(dod, 2):
        md.append([f'=IF(AND(G{i}>=Settings!$B$4,G{i}<=Settings!$B$5),"A",IF(G{i}<Settings!$B$4,"C","B"))',
                   d["name"].title(), d.get("city", ""), d["county"], (d.get("address") or "").title(), d.get("zip", ""),
                   round(d["dod_total"]), d.get("awards", ""), d.get("items", ""), d.get("naics", ""), d.get("uei", ""),
                   f"https://www.usaspending.gov/recipient/{d['recipient_id']}/latest" if d.get("recipient_id") else "",
                   "New", "", hubspot_check("B").format(r=i)])
        md.cell(i, 7).number_format = "#,##0"
    finish(md, "M", "A")

    # ---------- Nonprofit verticals ----------
    np_rows = json.load(open(f"{data_dir}/nonprofits.json"))
    for vert in ["Nonprofits", "Healthcare", "Religious"]:
        key = {"Nonprofits": "Nonprofit"}.get(vert, vert)
        rows = sorted([r for r in np_rows if r["vertical"] == key], key=lambda r: -r["revenue"])
        ws = wb.create_sheet(vert)
        h = ["Tier", "Organization", "City", "ZIP", "Address", "Type", "NTEE code", "Revenue, latest IRS filing ($)",
             "Assets ($)", "Filing period", "EIN", "ProPublica (990s, officers)", "Status", "Notes", "In HubSpot?"]
        style_header(ws, h, [6, 42, 16, 8, 30, 20, 9, 16, 14, 10, 11, 34, 15, 30, 12])
        for i, d in enumerate(rows, 2):
            ws.append([f'=IF(AND(H{i}>=Settings!$B$2,H{i}<=Settings!$B$3),"A",IF(H{i}<Settings!$B$2,"C","B"))',
                       d["name"], d["city"], d["zip"], d["address"], d["type"], d["ntee"], d["revenue"], d["assets"],
                       d["tax_period"], d["ein"], d["propublica"], "New", "", hubspot_check("B").format(r=i)])
            ws.cell(i, 8).number_format = "#,##0"
            ws.cell(i, 9).number_format = "#,##0"
        finish(ws, "M", "A")

    # ---------- Government ----------
    gov = sorted(json.load(open(f"{data_dir}/gov.json")), key=lambda r: -r["population"])
    gw = wb.create_sheet("Government")
    h = ["Tier", "Municipality", "Type", "County", "Population (2024 est.)", "Segment", "HB 96 angle", "Status", "Notes", "In HubSpot?"]
    style_header(gw, h, [6, 30, 10, 11, 14, 22, 60, 15, 30, 12])
    ang = cfg["messaging"]["vertical_angles"]
    for i, d in enumerate(gov, 2):
        deadline = "Jan 1, 2026" if d["kind"] == "City" else "July 1, 2026"
        gw.append([f'=IF(AND(E{i}>=Settings!$B$6,E{i}<=Settings!$B$7),"A",IF(E{i}<Settings!$B$6,"C","B"))',
                   d["name"], d["kind"], d["county"], d["population"], d["segment"],
                   f"HB 96 cyber program deadline was {deadline}. Ask if the program is documented and audit-ready.",
                   "New", "", hubspot_check("B").format(r=i)])
        gw.cell(i, 5).number_format = "#,##0"
    finish(gw, "H", "A")

    # ---------- Apollo Import ----------
    ai = wb.create_sheet("Apollo Import")
    style_header(ai, ["Company Name", "Website", "City", "State", "Vertical", "Tier source"], [42, 28, 18, 8, 22, 20])
    for t in top:
        ai.append([t["name"], t.get("website", ""), t["city"], cfg["state_abbr"], t["vertical"], "Top Leads"])
    for d in dod:
        if 100000 <= d["dod_total"] <= 20000000:
            ai.append([d["name"].title(), "", d.get("city", ""), cfg["state_abbr"], "Manufacturing (DoD)", "DoD tier A"])
    for d in np_rows:
        lo, hi = cfg["nonprofit"]["sweet_spot"]
        if lo <= d["revenue"] <= hi:
            ai.append([d["name"], "", d["city"], cfg["state_abbr"], d["vertical"], "Nonprofit tier A"])
    for row in ai.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=FONT, size=10)
    ai.auto_filter.ref = f"A1:F{ai.max_row}"

    # ---------- Apollo Searches ----------
    asr = wb.create_sheet("Apollo Searches")
    style_header(asr, ["Segment", "Apollo filters", "Titles to target", "Why it fits infinIT"], [26, 70, 50, 50])
    for row in json.load(open(f"{data_dir}/apollo_searches.json")):
        asr.append(row)
    for row in asr.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=FONT, size=10); c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------- Suppression ----------
    sp = wb.create_sheet("Suppression")
    style_header(sp, ["Company name (paste from HubSpot export)", "Domain (optional)"], [50, 30])
    sp.freeze_panes = "A2"

    wb.save(out)
    print("wrote", out, "| top", len(top), "| dod", len(dod), "| np", len(np_rows), "| gov", len(gov), file=sys.stderr)


if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3])
