# Weekly run (infinIT)

The scheduled task runs this every Monday morning (starts 5:47 am Eastern so the email lands before 7:00).
Follow it step by step.

## 1. Refresh data
`./run.sh infinit data` refreshes every list and enrichment: IRS nonprofits and 990 contacts, Census governments
and schools, USAspending DoD suppliers, the HHS breach list, and the email-security check.
Steps that fail print `!! step failed` and the run continues with last week's data. USAspending is flaky; the
committed cache in `data/infinit/cache/` is the fallback. Clear that cache on the first Monday of each month.
If `data/infinit/pipeline_status.json` exists (pulled from the live Google Sheet), read it before step 2.

## 2. Research 15-20 new Top Leads
- **Skip** every organization in `data/infinit/history/` and anything marked Not a fit or Do not contact in
  `pipeline_status.json`.
- **Cover both offices.** infinIT has two offices: Cleveland (1801 St Clair Ave NE, 44114) and Warren
  (4195 Parkman Rd NW, 44481). Aim for roughly half the leads within 30 miles of each office; never fewer than
  6 on either side. The `office` and `miles` fields on every list show the nearest office.
- **Where to look first:**
  - `Breach Watch` (breaches.json): Ohio healthcare breaches. Confirm the organization is in the territory.
    Lead with help (incident response, hardening), never with the breach itself.
  - Job postings for IT roles (IT Manager, Systems Administrator, IT Support) in the territory: co-managed angle.
  - Council and trustee agendas and minutes mentioning IT services, cybersecurity, HB 96 or RFPs.
  - Local business news: new locations, acquisitions, leadership changes (Crain's Cleveland, Business Journal
    Daily, Tribune Chronicle, Akron Beacon Journal).
  - Tier A rows on the list tabs with an email-security finding (no DMARC, GoDaddy email): good personalization.
- **Every lead needs a dated, sourced reason to reach out now.** No source, no lead. Never invent facts.
  Set `trigger_date` (YYYY-MM-DD, the date of the event) and `call_reason` (one phrase finishing "I'm calling
  because ...") on every lead. A job posting only counts if the employer is named.
- **Goal is booked first meetings.** Prefer leads with a fresh trigger (under 90 days), a named decision-maker
  and a direct phone. Drop "Good fit, no trigger" leads unless there aren't 15 better ones.
- In each draft body, end with the `{cta}` placeholder instead of a closing question; the build fills in the
  offer for that trigger type (configs/infinit.json → offers) and two proposed times.
- **Re-check** current CMMC status and Ohio HB 96 news before writing those drafts.
- **Contacts:** for nonprofits the enrichment fills 990 officers automatically. For everyone else, find the
  leader on the organization's own site or a government page and add it to `data/infinit/top_leads_contacts.json`
  (name, title, source, zip, website, phone). Mark third-party directory names "(verify)". Never scrape LinkedIn.
- Set `trigger_type` for each lead in `top_leads_contacts.json` → `_trigger_types` (IT job posting, Expansion /
  new sites, Leadership change, Acquisition, HB 96 cyber mandate, CMMC / DFARS, Breach, IT contract decision,
  Critical operations, Good fit, no trigger).
- Write `data/infinit/top_leads.json` in the same format as `data/infinit/history/top_leads_2026-11-04.json`
  (the build sorts by appointment score; the top three become "Call these first"). Then copy it to
  `data/infinit/history/top_leads_YYYY-MM-DD.json`.

## 3. Build
`./run.sh infinit build` merges contacts, LinkedIn search links, nearest office and email-security findings into
the Top Leads and writes `output/infinit_leads_YYYY-MM-DD.xlsx`.

## 4. Check
Convert to PDF with LibreOffice headless, render the Summary and Top Leads pages to PNG and look at them:
counts filled in, no `#` errors, nothing cut off. Fix and rebuild if anything looks wrong.

## 5. Email
`mailer.py` (Resend, from leads@daubenmiregroup.com; never from infinit.us) to `configs/infinit.json` → `email.to`.
Subject: `infinIT leads – week of <Mon date>`. Body: new Top Leads by vertical and by office (Warren / Cleveland),
the 3 to call first and why, and anything notable. Remind them to fill placeholders and add infinIT's postal
address and an opt-out line before sending drafts.

## 6. Commit and push
To `main`: data, history file and workbook. Message: `Weekly leads YYYY-MM-DD`. If any step failed, still commit
what was built and say what failed in the commit message.
