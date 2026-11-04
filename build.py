"""Build the lead workbook for one client from the data files in data/<client>/.
Usage: python3 build.py configs/<client>.json data/<client> output/<file>.xlsx"""
import datetime, json, math, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sources"))
import geo
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

# ---------- style ----------
FONT = "Arial"
NAVY, INK, MUTED, LINK = "1F3A5F", "222222", "6B7280", "1155CC"
HDR_FILL = PatternFill("solid", fgColor=NAVY)
BAND_FILL = PatternFill("solid", fgColor="F4F6F9")
INPUT_FILL = PatternFill("solid", fgColor="FFF4CC")
THIN = Side(style="thin", color="D9DEE5")
STATUSES = ["New", "Researching", "Contact found", "Emailed", "Follow-up 1", "Follow-up 2",
            "Replied", "Meeting booked", "Moved to HubSpot", "Not a fit", "Do not contact"]
STATUS_COLORS = {"Meeting booked": ("C6EFCE", "1E6B34"), "Moved to HubSpot": ("C6EFCE", "1E6B34"),
                 "Replied": ("DDEBF7", "1F4E79"), "Emailed": ("FFF2CC", "7A5B00"),
                 "Follow-up 1": ("FFF2CC", "7A5B00"), "Follow-up 2": ("FFF2CC", "7A5B00"),
                 "Not a fit": ("EEEEEE", "777777"), "Do not contact": ("FFC7CE", "9C0006")}
TIER_COLORS = {"A": ("D8F0DE", "1E6B34"), "B": ("FFF1C9", "7A5B00"), "C": ("EEEEEE", "777777")}
SHORT_FINDING = [("No DMARC", "No DMARC"), ("monitor only", "DMARC monitor-only"), ("No SPF", "No SPF"),
                 ("+all", "SPF allows anyone"), ("GoDaddy", "GoDaddy email"), ("Self-hosted", "Self-hosted email"),
                 ("Yahoo", "Yahoo email"), ("plain HTTP", "Site not HTTPS (verify)")]


def f(size=10, bold=False, color=INK, italic=False, underline=None):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic, underline=underline)


def short_findings(check):
    if not check:
        return ""
    if not check.get("findings"):
        return "OK"
    out = []
    for finding in check["findings"]:
        for key, label in SHORT_FINDING:
            if key in finding and label not in out:
                out.append(label)
    return ", ".join(out)


def table(ws, headers, widths, rows, freeze="C2", wrap_cols=(), row_height=None, status_col=None,
          tier_col=None, link_cols=(), money_cols=(), int_cols=(), note=None):
    """Write a styled table. rows: list of lists; a cell may be (text, url) for a hyperlink.
    note: optional one-line explanation placed above the header (header then sits on row 2)."""
    top = 1
    if note:
        ws.append([note])
        ws.cell(1, 1).font = f(9, italic=True, color=MUTED)
        top = 2
        freeze = freeze[0] + str(int(freeze[1:]) + 1)
    ws.append(headers)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        c = ws.cell(top, i)
        c.font = f(bold=True, color="FFFFFF")
        c.fill = HDR_FILL
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[top].height = 30
    for r_i, row in enumerate(rows, top + 1):
        for c_i, val in enumerate(row, 1):
            cell = ws.cell(r_i, c_i)
            if isinstance(val, tuple):
                text, url = val
                cell.value = text
                if url and text:
                    cell.hyperlink = url
                    cell.font = f(color=LINK, underline="single")
                else:
                    cell.font = f()
            else:
                cell.value = val
                cell.font = f()
            cell.alignment = Alignment(vertical="top", wrap_text=c_i in wrap_cols)
            cell.border = Border(bottom=THIN)
            if c_i in money_cols:
                cell.number_format = '"$"#,##0'
            elif c_i in int_cols:
                cell.number_format = "#,##0"
        if row_height:
            ws.row_dimensions[r_i].height = row_height(row) if callable(row_height) else row_height
    n = max(ws.max_row, top + 1)
    d1 = top + 1
    last = get_column_letter(len(headers))
    ws.freeze_panes = freeze
    ws.auto_filter.ref = f"A{top}:{last}{n}"
    ws.sheet_view.zoomScale = 100
    if status_col:
        col = get_column_letter(status_col)
        dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}{d1}:{col}{n + 500}")
        for s, (bg, fg) in STATUS_COLORS.items():
            ws.conditional_formatting.add(f"{col}{d1}:{col}{n + 500}", FormulaRule(
                formula=[f'${col}{d1}="{s}"'], fill=PatternFill("solid", fgColor=bg), font=Font(color=fg, bold=True)))
    if tier_col:
        col = get_column_letter(tier_col)
        for t, (bg, fg) in TIER_COLORS.items():
            ws.conditional_formatting.add(f"{col}{d1}:{col}{n + 500}", FormulaRule(
                formula=[f'${col}{d1}="{t}"'], fill=PatternFill("solid", fgColor=bg), font=Font(color=fg, bold=True)))
        for r in range(d1, n + 1):
            ws.cell(r, tier_col).alignment = Alignment(horizontal="center", vertical="top")
    ws.conditional_formatting.add(f"A{d1}:{last}{n + 500}",  # banding last: tier/status colors win
                                  FormulaRule(formula=["MOD(ROW(),2)=0"], fill=BAND_FILL, stopIfTrue=False))
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{top}:{top}"


def text_height(texts_widths, line_pt=12.75, pad=6, min_h=30):
    """Estimate a row height for wrapped text cells: [(text, column_width), ...]."""
    lines = 1
    for text, width in texts_widths:
        per_line = max(int(width * 1.15), 10)
        n = sum(max(1, math.ceil(len(p) / per_line)) for p in str(text or "").split("\n"))
        lines = max(lines, n)
    return max(min_h, lines * line_pt + pad)


def url(domain):
    return f"https://{domain}" if domain else ""


def site(domain):
    """(display text without www., link) for a website cell."""
    d = re.sub(r"^(https?://)?(www\.)?", "", (domain or "").strip()).strip("/")
    return (d, url(d)) if d and "." in d and "@" not in d else ""


def hubspot(col, r):
    return f'=IF(COUNTIF(Suppression!$A:$A,{col}{r})>0,"In HubSpot","")'


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def near(cfg, zip_code=None, county=None):
    point = geo.point_for_zip(zip_code) if zip_code else None
    if not point and county:
        fips = next((k for k, v in cfg["counties"].items() if v == county), None)
        point = geo.point_for_county(cfg["state_fips"], fips) if fips else None
    return geo.nearest_office(cfg, point)


def build(cfg, d, out):
    client = cfg["client"]
    today = datetime.date.today()
    top = load(f"{d}/top_leads.json", [])
    dod = sorted(load(f"{d}/dod.json", []), key=lambda r: -r["dod_total"])
    nps = load(f"{d}/nonprofits.json", [])
    gov = sorted(load(f"{d}/gov.json", []), key=lambda r: -r["population"])
    gdir = load(f"{d}/gov_directory.json", {})
    schools = sorted(load(f"{d}/schools.json", []), key=lambda r: -(r["enrollment"] or 0))
    e990 = load(f"{d}/enrich_990.json", {})
    checks = load(f"{d}/domain_checks.json", {})
    breaches = load(f"{d}/breaches.json", [])
    searches = load(f"{d}/apollo_searches.json", [])
    chk = lambda dom: checks.get(re.sub(r"^www\.", "", (dom or "").split("/")[0]))
    lo, hi = cfg["nonprofit"]["sweet_spot"]
    wb = Workbook()

    # ================= Summary =================
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for col, w in zip("ABCDEFG", [3, 30, 12, 10, 12, 12, 64]):
        ws.column_dimensions[col].width = w
    ws["B2"] = f"{client} Lead Report"
    ws["B2"].font = f(20, True, NAVY)
    ws["B3"] = f"Week of {today:%B %-d, %Y}  ·  Public data plus researched triggers  ·  Prepared by The Daubenmire Group"
    ws["B3"].font = f(10, color=MUTED)

    def section(row, title):
        ws.cell(row, 2, title).font = f(12, True, NAVY)
        for c in range(2, 8):
            ws.cell(row, c).border = Border(bottom=Side(style="medium", color=NAVY))

    section(5, "What's in this workbook")
    hdr = ["List", "Accounts", "Tier A", "Warren side", "Cleveland side", "What it's for"]
    for i, h in enumerate(hdr, 2):
        c = ws.cell(6, i, h)
        c.font = f(9, True, MUTED)
    lists = [
        ("Top Leads", "'Top Leads'!C:C", None, "'Top Leads'!F:F", "Researched this week. Each has a reason to reach out now, contacts and drafts. Start here."),
        ("Manufacturing (DoD)", "'Manufacturing (DoD)'!B:B", "'Manufacturing (DoD)'!A:A", "'Manufacturing (DoD)'!E:E", "Defense suppliers in your counties. NIST 800-171 / CMMC angle."),
        ("Nonprofits", "Nonprofits!B:B", "Nonprofits!A:A", "Nonprofits!D:D", "With website, phone and named leaders from IRS 990 filings."),
        ("Healthcare", "Healthcare!B:B", "Healthcare!A:A", "Healthcare!D:D", "Behavioral health, clinics, care providers. HIPAA angle."),
        ("Religious", "Religious!B:B", "Religious!A:A", "Religious!D:D", "Faith-based organizations that file with the IRS."),
        ("Government", "Government!B:B", "Government!A:A", "Government!E:E", "Cities, villages, townships. Ohio HB 96 cyber-program angle."),
        ("Schools", "Schools!B:B", "Schools!A:A", "Schools!D:D", "School districts. HB 96 applies here too."),
        ("Breach Watch", "'Breach Watch'!B:B", None, None, "Ohio healthcare breaches under federal investigation. Verify location first."),
        ("Competitor Clients", "'Competitor Clients'!B:B", None, "'Competitor Clients'!F:F", "FIT / Blue Technologies customers, with contract end dates. Green = re-bidding this winter."),
        ("School Bids", "'School Bids'!C:C", None, "'School Bids'!E:E", "Open E-Rate bid requests from local schools and libraries, with the contact."),
        ("Cyber Pilot", "'Cyber Pilot'!B:B", None, "'Cyber Pilot'!C:C", "Districts proven to buy cybersecurity (FCC Cybersecurity Pilot)."),
    ]
    for i, (name, rng, tier_rng, office_rng, note) in enumerate(lists, 7):
        ws.cell(i, 2, name).font = f(bold=True)
        ws.cell(i, 2).hyperlink = f"#'{name}'!A1"
        ws.cell(i, 2).font = f(bold=True, color=LINK)
        hdr_rows = 1  # header row (the Breach Watch note sits in column A only)
        ws.cell(i, 3, f"=COUNTA({rng})-{hdr_rows}").number_format = "#,##0"
        ws.cell(i, 4, f'=COUNTIF({tier_rng},"A")' if tier_rng else "").number_format = "#,##0"
        ws.cell(i, 5, f'=COUNTIF({office_rng},"Warren")' if office_rng else "").number_format = "#,##0"
        ws.cell(i, 6, f'=COUNTIF({office_rng},"Cleveland")' if office_rng else "").number_format = "#,##0"
        ws.cell(i, 7, note).font = f(color=MUTED)
        for c in (3, 4, 5, 6):
            ws.cell(i, c).font = f()
            ws.cell(i, c).alignment = Alignment(horizontal="right")
    r = 7 + len(lists) + 1
    section(r, "Call these first")
    for i, t in enumerate(top[:3], r + 1):
        ws.cell(i, 2, f"{i - r}. {t['name']}").font = f(bold=True)
        ws.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(i, 3, f"Score {t.get('score', '')}\n{t.get('office', '')} · {t.get('miles', '')} mi").font = f(9, color=MUTED)
        ws.cell(i, 3).alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=i, start_column=4, end_row=i, end_column=7)
        ws.cell(i, 4, t["why_now"]).font = f()
        ws.cell(i, 4).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = text_height([(t["why_now"], 92), (t["name"], 30)], min_h=34) + 4
    r = r + 5
    section(r, "Pipeline (Top Leads)")
    for i, (label, st) in enumerate([("Emailed or following up", None), ("Replied", "Replied"),
                                     ("Meetings booked", "Meeting booked")], r + 1):  # Top Leads Status column
        ws.cell(i, 2, label).font = f()
        formula = (f'=COUNTIF(\'Top Leads\'!Q:Q,"Emailed")+COUNTIF(\'Top Leads\'!Q:Q,"Follow-up 1")'
                   f'+COUNTIF(\'Top Leads\'!Q:Q,"Follow-up 2")') if st is None else f'=COUNTIF(\'Top Leads\'!Q:Q,"{st}")'
        ws.cell(i, 3, formula).font = f(bold=True)
    r = r + 5
    section(r, "How to use it")
    steps = ["1. Paste your HubSpot company names into the Suppression tab. Existing accounts get flagged on every tab.",
             "2. Work Top Leads: check the contact, personalize the draft on the Drafts tab, send from Outlook, set Status.",
             "3. Then take Tier A rows from the list tabs a batch at a time. Click a website or LinkedIn link to research fast.",
             "4. Before sending any draft: fill placeholders, add infinIT's postal address and an opt-out line, re-check the source link."]
    for i, s in enumerate(steps, r + 1):
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=7)
        ws.cell(i, 2, s).font = f()
    r = r + len(steps) + 2
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=7)
    ws.cell(r, 2, "Sources: IRS Exempt Organizations file and Form 990 e-filings; USAspending.gov; U.S. Census Bureau "
                  "population estimates and Government Units listing; HHS OCR breach portal; public DNS; web research "
                  "(links on each lead). Revenue and officer data can be 1-2 years old.").font = f(9, color=MUTED, italic=True)
    ws.cell(r, 2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 40

    # ================= Top Leads =================
    tl = wb.create_sheet("Top Leads")
    h = ["#", "Score", "Organization", "Vertical", "City", "Nearest office", "Miles", "Trigger", "Why now", "First-meeting offer", "Website", "Main phone",
         "Contact 1 (click: LinkedIn search)", "Contact 2", "Email security", "Company on LinkedIn",
         "Status", "Rep", "Last touch", "Notes", "In HubSpot?"]
    w = [4, 7, 28, 14, 12, 10, 7, 18, 52, 36, 22, 15, 34, 34, 22, 13, 15, 10, 11, 28, 11]
    rows = []
    for i, t in enumerate(top, 1):
        cs = t.get("contacts", [])
        cell = lambda c: (f"{c['name']} – {c['title']}", c.get("linkedin", "")) if c else ""
        rows.append([i, t.get("score", ""), t["name"], t["vertical"].replace(" (DoD supplier)", ""), t["city"],
                     t.get("office", ""), t.get("miles", ""), t.get("trigger_type", ""), t["why_now"],
                     (t.get("offer", "")[:1].upper() + t.get("offer", "")[1:]),
                     site(t.get("website")), t.get("phone", ""),
                     cell(cs[0] if cs else None), cell(cs[1] if len(cs) > 1 else None),
                     short_findings(chk(t.get("website"))) or "", ("Search", t.get("linkedin_company", "")),
                     "New", "", "", t.get("notes", ""), hubspot("C", i + 1)])
    table(tl, h, w, rows, freeze="D2", wrap_cols=(3, 9, 10, 13, 14, 15, 20), status_col=17,
          row_height=lambda row: text_height([(row[8], 52), (row[9], 36)]))
    for rr, t in enumerate(top, 2):
        tl.cell(rr, 19).number_format = "mmm d"
        sc = tl.cell(rr, 2)
        sc.alignment = Alignment(horizontal="center", vertical="top")
        sc.font = f(bold=True, color=NAVY)
        if t.get("score_why"):
            sc.comment = Comment(f"Appointment score {t['score']}/100\n{t['score_why']}", "Lead report")
    tl.conditional_formatting.add(f"B2:B{tl.max_row}", FormulaRule(formula=["$B2>=75"], fill=PatternFill("solid", fgColor="D8F0DE")))

    # ================= Drafts =================
    dr = wb.create_sheet("Drafts")
    h = ["#", "Organization", "Who to email", "Subject", "Email (day 1)", "Phone opener (day 2)", "Voicemail",
         "Follow-up 1 (day 4)", "Follow-up 2 (day 10)", "Source 1", "Source 2", "Source 3"]
    w = [4, 26, 28, 28, 66, 42, 34, 42, 36, 10, 10, 10]
    rows = []
    for i, t in enumerate(top, 1):
        srcs = t.get("sources", [])[:3] + [""] * 3
        who = t["contact_role"]
        if t.get("contacts"):
            who = f"{t['contacts'][0]['name']} ({t['contacts'][0]['title']})\nRole: {t['contact_role']}"
        rows.append([i, t["name"], who, t["subject"], t.get("body_final") or t["body"], t.get("phone_opener", ""),
                     t.get("voicemail", ""), t["fu1"], t["fu2"]]
                    + [(f"Link {k + 1}", s) if s else "" for k, s in enumerate(srcs[:3])])
    table(dr, h, w, rows, freeze="C2", wrap_cols=(2, 3, 4, 5, 6, 7, 8, 9),
          row_height=lambda row: text_height([(row[4], 66), (row[5], 42), (row[7], 42)]))

    # ================= Call Plan =================
    cp = wb.create_sheet("Call Plan")
    start = today + datetime.timedelta(days=(7 - today.weekday()) % 7 or 0)  # this Monday if run on Monday, else next
    if today.weekday() != 0:
        start = today + datetime.timedelta(days=(7 - today.weekday()))
    def biz(n):  # n-th business day after start (0 = start)
        d, k = start, 0
        while k < n:
            d += datetime.timedelta(days=1)
            if d.weekday() < 5:
                k += 1
        return d
    steps = [(0, "Email 1 + view LinkedIn"), (1, "Call: opener, else voicemail"), (3, "Follow-up 1 email"),
             (5, "Call #2"), (8, "Follow-up 2 email"), (10, "Last call: ask for the meeting")]
    h = ["#", "Organization", "Contact", "Phone", "Nearest office"] + \
        [f"{biz(n):%a %b %-d}\n{a}" for n, a in steps] + ["Booked?", "Meeting date", "Notes"]
    w = [4, 28, 30, 15, 15] + [17] * len(steps) + [10, 12, 30]
    rows = []
    for i, t in enumerate(top, 1):
        c0 = (t.get("contacts") or [{}])[0]
        near_visit = t.get("miles") is not None and t["miles"] <= 15
        cells = []
        for n, a in steps:
            txt = "☐"
            if n == 5 and near_visit:
                txt = "☐ or drop in (≤15 mi)"
            cells.append(txt)
        rows.append([i, t["name"], f"{c0.get('name', '')} – {c0.get('title', '')}" if c0 else t["contact_role"],
                     t.get("phone", ""), f"{t.get('office', '')} · {t.get('miles', '')} mi"] + cells + ["", "", ""])
    table(cp, h, w, rows, freeze="C2", wrap_cols=(2, 3),
          note=("Two touches a week for two weeks. Replace ☐ with ✓ as you go. Leads within 15 miles of an office: "
                "drop in on the day-8 touch. Mark Booked? = Yes when a first meeting is on the calendar."))
    cp.row_dimensions[2].height = 44
    booked_col = 6 + len(steps)
    dvb = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    cp.add_data_validation(dvb)
    dvb.add(f"{get_column_letter(booked_col)}3:{get_column_letter(booked_col)}{cp.max_row + 200}")
    cp.conditional_formatting.add(f"A3:{get_column_letter(len(h))}{cp.max_row + 200}", FormulaRule(
        formula=[f'${get_column_letter(booked_col)}3="Yes"'], fill=PatternFill("solid", fgColor="C6EFCE")))
    for rr in range(3, cp.max_row + 1):
        cp.cell(rr, booked_col + 1).number_format = "mmm d"


    # ================= Competitor Clients =================
    comp = load(f"{d}/competitor_clients.json", []) + [
        dict(m, office=near(cfg, m.get("zip"))[0], miles=near(cfg, m.get("zip"))[1], bid_posted="")
        for m in load(f"{d}/competitor_contracts_manual.json", [])]
    comp.sort(key=lambda r: (r.get("contract_end") or "9999", -(r.get("spend_recent") or 0)))
    renew_by = (today.replace(year=today.year + 1, month=9, day=30)).isoformat()
    cw = wb.create_sheet("Competitor Clients")
    h = ["Contract ends", "Organization", "Competitor", "Type", "City", "Nearest office", "Miles",
         "Services they buy", "Spend, last 3 yrs", "Customer since", "Main phone", "Contact on file",
         "Bid posted?", "Source", "Status", "Notes"]
    w = [12, 38, 20, 14, 14, 10, 7, 44, 14, 10, 15, 28, 22, 10, 15, 30]
    rows = []
    for x in comp:
        end = datetime.date.fromisoformat(x["contract_end"]) if x.get("contract_end") else None
        src = x.get("source") or f"https://opendata.usac.org/resource/qdmp-ygft.json?ben={x.get('ben', '')}"
        rows.append([end, x["name"], x["vendor"].replace("TechnologiesLLC", "Technologies"), x.get("type", ""),
                     x.get("city", ""), x.get("office", ""), x.get("miles", ""), x.get("services", ""),
                     x.get("spend_recent", ""), x.get("first_year", ""), x.get("phone", ""),
                     x.get("contact_email", ""), x.get("bid_posted") or "Not yet", ("Link", src), "New",
                     x.get("note", "")])
    table(cw, h, w, rows, freeze="C2", wrap_cols=(2, 8, 16), status_col=15, money_cols=(9,),
          note=("Schools and libraries buying network/IT services from competitors (federal E-Rate records), plus public "
                "contracts. Green = contract ends by " + renew_by + ": they re-bid this winter. Reach out BEFORE their "
                "Form 470 posts; once it posts, respond only through the bid. No gifts or free services to E-Rate applicants."))
    for rr in range(3, cw.max_row + 1):
        cw.cell(rr, 1).number_format = "mmm d, yyyy"
    cw.conditional_formatting.add(f"A3:P{cw.max_row}", FormulaRule(
        formula=[f'AND($A3<>"",$A3<=DATE({renew_by[:4]},{int(renew_by[5:7])},{int(renew_by[8:])}))'],
        fill=PatternFill("solid", fgColor="D8F0DE")))

    # ================= School Bids (E-Rate) =================
    bids = load(f"{d}/erate_bids.json", [])
    sb = wb.create_sheet("School Bids")
    h = ["Posted", "Contracts allowed from", "Organization", "City", "Nearest office", "Miles", "What they're buying",
         "Contact", "Email", "Phone", "Technical contact", "RFP / application #", "Status", "Notes"]
    w = [11, 13, 34, 14, 10, 7, 60, 22, 28, 15, 28, 18, 15, 30]
    rows = []
    for x in bids:
        rows.append([datetime.date.fromisoformat(x["posted"]) if x.get("posted") else "",
                     datetime.date.fromisoformat(x["contract_allowed_from"]) if x.get("contract_allowed_from") else "",
                     x["name"], x["city"], x["office"], x["miles"], x["services"], x["contact"], x["contact_email"],
                     x["contact_phone"], ", ".join(filter(None, [x["tech_contact"], x["tech_title"]])),
                     x.get("rfp") or x["application_number"], "New", ""])
    table(sb, h, w, rows, freeze="D2", wrap_cols=(3, 7, 11), status_col=13,
          note=("Open FCC Form 470 bid requests from schools and libraries in your territory (last 6 months). Bidding on "
                "E-Rate-funded work requires an E-Rate service provider number (SPIN). Respond through the bid; no gifts."))
    for rr in range(3, sb.max_row + 1):
        sb.cell(rr, 1).number_format = "mmm d"
        sb.cell(rr, 2).number_format = "mmm d"

    # ================= Cyber Pilot =================
    cyb = load(f"{d}/cyber_pilot_bids.json", [])
    cy = wb.create_sheet("Cyber Pilot")
    h = ["Organization", "City", "Nearest office", "Miles", "Posted", "Cybersecurity they asked for", "Contact",
         "Email", "Phone", "Technical contact", "Status", "Notes"]
    w = [36, 16, 10, 7, 11, 60, 22, 28, 15, 28, 15, 30]
    rows = [[x["name"], x["city"], x["office"], x["miles"],
             datetime.date.fromisoformat(x["posted"]) if x.get("posted") else "", x["services"], x["contact"],
             x["contact_email"], x["contact_phone"], ", ".join(filter(None, [x["tech_contact"], x["tech_title"]])),
             "New", ""] for x in cyb]
    table(cy, h, w, rows, freeze="B2", wrap_cols=(1, 6, 10), status_col=11,
          note=("Districts and libraries in the FCC Schools & Libraries Cybersecurity Pilot: proven buyers of endpoint "
                "protection, monitoring/detection and identity security. Pilot purchases go through bids; pitch the rest."))
    for rr in range(3, cy.max_row + 1):
        cy.cell(rr, 5).number_format = "mmm d, yyyy"

    # ================= Manufacturing (DoD) =================
    md = wb.create_sheet("Manufacturing (DoD)")
    sam = load(f"{d}/sam_cache.json", {}).get("entities", {})
    h = ["Tier", "Company", "City", "County", "Nearest office", "Miles", "DoD obligations FY24-26",
         "Website", "SAM.gov contacts (name, title)", "Email security", "DoD awards", "UEI", "Status", "Notes",
         "In HubSpot?"]
    w = [6, 42, 13, 12, 10, 7, 18, 24, 40, 20, 13, 15, 15, 30, 11]
    rows = []
    for i, x in enumerate(dod, 2):
        sm = sam.get(x.get("uei", ""), {})
        sm = {} if sm.get("not_found") else sm
        o, mi = near(cfg, sm.get("zip"), x["county"])
        people = "; ".join(f"{p['name']} ({p['title']})" for p in sm.get("contacts", [])[:2])
        rows.append([f'=IF(AND(G{i}>=Settings!$B$4,G{i}<=Settings!$B$5),"A",IF(G{i}<Settings!$B$4,"C","B"))',
                     x["name"].title(), sm.get("city", ""), x["county"], o, mi, round(x["dod_total"]),
                     site(sm.get("website")), people, short_findings(chk(sm.get("website"))),
                     ("View awards", f"https://www.usaspending.gov/recipient/{x['recipient_id']}/latest") if x.get("recipient_id") else "",
                     x.get("uei", ""), "New", "", hubspot("B", i)])
    table(md, h, w, rows, freeze="C2", status_col=13, tier_col=1, money_cols=(7,))

    # ================= Nonprofit verticals =================
    for vert in ["Nonprofits", "Healthcare", "Religious"]:
        key = {"Nonprofits": "Nonprofit"}.get(vert, vert)
        rs = sorted([x for x in nps if x["vertical"] == key], key=lambda x: -x["revenue"])
        ws = wb.create_sheet(vert)
        h = ["Tier", "Organization", "City", "Nearest office", "Miles", "Type", "Revenue (latest 990)", "Employees",
             "Website", "Main phone", "Leader (990)", "Other officers (990)", "Email security", "990 filings",
             "Status", "Notes", "In HubSpot?"]
        w = [6, 38, 14, 10, 7, 18, 15, 11, 24, 15, 24, 36, 20, 11, 15, 26, 11]
        rows = []
        for i, x in enumerate(rs, 2):
            e = e990.get(x["ein"].zfill(9), {})
            e = {} if "error" in e else e
            leader = next((o for o in e.get("officers", []) if o["comp"] > 0 and re.search(
                r"\b(ceo|chief executive|executive director|president)\b", o["title"].lower()) and "vice" not in o["title"].lower()), None)
            leader_txt = f"{leader['name']} ({leader['title']})" if leader else e.get("principal_officer", "")
            lead_name = leader["name"] if leader else e.get("principal_officer", "")
            others = "; ".join([f"{o['name']} ({o['title']})" for o in e.get("officers", [])
                                if o["name"] != lead_name][:3])[:180]
            rows.append([f'=IF(AND(G{i}>=Settings!$B$2,G{i}<=Settings!$B$3),"A",IF(G{i}<Settings!$B$2,"C","B"))',
                         x["name"], x["city"], x.get("office", ""), x.get("miles", ""), x["type"], x["revenue"],
                         e.get("employees") or "",
                         site(e.get("website")), e.get("phone", ""),
                         leader_txt, others, short_findings(chk(e.get("website"))),
                         ("View", x["propublica"]), "New", "", hubspot("B", i)])
        table(ws, h, w, rows, freeze="C2", status_col=15, tier_col=1, money_cols=(7,), int_cols=(8,))

    # ================= Government =================
    gw = wb.create_sheet("Government")
    h = ["Tier", "Municipality", "Type", "County", "Nearest office", "Miles", "Population (2024 est.)", "Website",
         "Lead official (title)", "Mailing address", "Email security", "HB 96 deadline", "Status", "Notes", "In HubSpot?"]
    w = [6, 28, 10, 11, 10, 7, 14, 26, 24, 30, 20, 13, 15, 26, 11]
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
    gidx = {(norm(k.split("|")[0]), k.split("|")[1]): v for k, v in gdir.items()}
    gidx_any = {norm(k.split("|")[0]): v for k, v in gdir.items()}
    rows = []
    for i, x in enumerate(gov, 2):
        g = gidx.get((norm(x["name"]), x["kind"])) or gidx_any.get(norm(x["name"]), {})
        addr = ", ".join(filter(None, [g.get("address", ""), g.get("mail_city", "")]))
        o, mi = near(cfg, g.get("zip"), x["county"])
        rows.append([f'=IF(AND(G{i}>=Settings!$B$6,G{i}<=Settings!$B$7),"A",IF(G{i}<Settings!$B$6,"C","B"))',
                     x["name"] if x["kind"] == "Township" else f"{x['name']} ({x['kind']})", x["kind"], x["county"],
                     o, mi, x["population"], site(g.get("website")), g.get("contact_title", ""),
                     addr, short_findings(chk(g.get("website"))),
                     "Jan 1, 2026" if x["kind"] == "City" else "July 1, 2026", "New", "", hubspot("B", i)])
    table(gw, h, w, rows, freeze="C2", status_col=13, tier_col=1, int_cols=(7,))

    # ================= Schools =================
    sw = wb.create_sheet("Schools")
    h = ["Tier", "School district", "County", "Nearest office", "Miles", "Enrollment", "Website", "Lead official (title)",
         "Mailing address", "Email security", "Status", "Notes", "In HubSpot?"]
    w = [6, 40, 11, 10, 7, 12, 30, 18, 30, 20, 15, 26, 11]
    rows = []
    for i, x in enumerate(schools, 2):
        name = re.sub(r"\bSch(ool)? Dist\b", "School District", x["name"]).replace("Hgts", "Heights").replace(" Lsd", " Local School District")
        o, mi = near(cfg, x.get("zip"), x["county"])
        rows.append([f'=IF(AND(F{i}>=Settings!$B$8,F{i}<=Settings!$B$9),"A",IF(F{i}<Settings!$B$8,"C","B"))',
                     name, x["county"], o, mi, x["enrollment"], site(x["website"]), x["contact_title"],
                     ", ".join(filter(None, [x["address"], x["mail_city"]])), short_findings(chk(x["website"])),
                     "New", "", hubspot("B", i)])
    table(sw, h, w, rows, freeze="C2", status_col=11, tier_col=1, int_cols=(6,))

    # ================= Breach Watch =================
    bw = wb.create_sheet("Breach Watch")
    h = ["Reported", "Organization", "Entity type", "People affected", "Breach type", "Where the data was",
         "In our area? (verify)", "Status", "Notes"]
    w = [11, 44, 18, 15, 20, 26, 18, 15, 40]
    rows = [[datetime.datetime.strptime(x["reported"], "%m/%d/%Y").date(), x["name"], x["entity_type"],
             x["individuals"], x["breach_type"], x["location"], "", "New", ""] for x in breaches]
    table(bw, h, w, rows, freeze="C2", status_col=8, int_cols=(4,),
          note="HHS lists the state only. Confirm the organization is in your area, and lead with help "
               "(incident response, hardening), never with the breach itself.")
    for rr in range(3, bw.max_row + 1):
        bw.cell(rr, 1).number_format = "mmm d, yyyy"

    # ================= Apollo Import =================
    ai = wb.create_sheet("Apollo Import")
    rows = [[t["name"], t.get("website", ""), t["city"], cfg["state_abbr"], t["vertical"], "Top Leads"] for t in top]
    rows += [[x["name"].title(), "", "", cfg["state_abbr"], "Manufacturing (DoD)", "DoD tier A"]
             for x in dod if 100000 <= x["dod_total"] <= 20000000]
    for x in nps:
        if lo <= x["revenue"] <= hi:
            e = e990.get(x["ein"].zfill(9), {})
            rows.append([x["name"], e.get("website", "") if "error" not in e else "", x["city"], cfg["state_abbr"],
                         x["vertical"], "Nonprofit tier A"])
    table(ai, ["Company Name", "Website", "City", "State", "Vertical", "Source"], [42, 28, 18, 8, 22, 18], rows, freeze="B2")

    # ================= Apollo Searches =================
    asr = wb.create_sheet("Apollo Searches")
    table(asr, ["Segment", "Apollo filters", "Titles to target", "Why it fits"], [26, 70, 46, 50], searches,
          freeze="B2", wrap_cols=(1, 2, 3, 4), row_height=lambda row: text_height([(row[1], 70), (row[3], 50)]))

    # ================= Suppression =================
    sp = wb.create_sheet("Suppression")
    table(sp, ["Company name (paste from HubSpot export)", "Domain (optional)"], [50, 30], [], freeze="A2")

    # ================= Settings =================
    st = wb.create_sheet("Settings")
    settings = [
        ("Nonprofit revenue, tier A minimum", lo, "Roughly 20+ staff"),
        ("Nonprofit revenue, tier A maximum", hi, "Above this, most have internal IT (co-managed angle)"),
        ("DoD obligations, tier A minimum", 100000, "Repeat DoD supplier"),
        ("DoD obligations, tier A maximum", 20000000, "Above this, likely a larger company with its own IT"),
        ("Municipality population, tier A minimum", 5000, "Big enough to budget for managed IT"),
        ("Municipality population, tier A maximum", cfg["government"]["co_managed_above"], "Above this, likely an IT department"),
        ("School enrollment, tier A minimum", 500, "Smaller districts rarely have a full IT team"),
        ("School enrollment, tier A maximum", 4000, "Above this, co-managed angle"),
    ]
    table(st, ["Setting", "Value", "Note"], [44, 16, 60], [list(s) for s in settings], freeze="A2")
    for rr in range(2, len(settings) + 2):
        st.cell(rr, 2).fill = INPUT_FILL
        st.cell(rr, 2).number_format = "#,##0"
    st.conditional_formatting = type(st.conditional_formatting)()  # no banding over the yellow inputs
    st.cell(len(settings) + 3, 1, "Yellow cells are inputs. Tier formulas on the list tabs read these values.").font = f(9, italic=True, color=MUTED)

    # Row banding must never hide tier/status/booked/score colors: give it the lowest priority everywhere
    for sheet in wb.worksheets:
        for cf in sheet.conditional_formatting:
            for rule in cf.rules:
                if rule.formula == ["MOD(ROW(),2)=0"]:
                    rule.priority = 9999
    wb.save(out)
    print(f"wrote {out} | top {len(top)} | dod {len(dod)} | np {len(nps)} | gov {len(gov)} | schools {len(schools)} "
          f"| breaches {len(breaches)}", file=sys.stderr)


if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3])
