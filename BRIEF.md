# Lead Gen System: Brief

*Built by The Daubenmire Group. First client: infinIT (managed IT provider, Cleveland and Warren, Ohio). Updated Nov 19, 2026.*

## In one sentence
Every Monday morning, an automated AI researcher finds 15–20 Northeast Ohio organizations with a **specific, dated reason to need an IT partner right now**, adds named contacts, a first-meeting offer and call scripts, and emails a ready-to-work spreadsheet to infinIT's sales team.

## The problem it solves
Bought lead lists tell you *who exists*. They don't tell you *who needs you this month*. Sales reps waste time on accounts with no reason to switch. This system combines free public records with weekly news research to surface **triggers**: a breach, a competitor contract ending, a new state mandate, an expansion, a leadership change, an IT job they can't fill.

## How it works (weekly)
1. **Refresh the lists** (automated scripts, about 1 minute). Pulls about 2,500 organizations in the territory from public data and adds websites, phones, leaders and an email-security check.
2. **Research** (AI, about 10 minutes). Searches the news, council minutes, job postings and federal filings for new triggers, verifies each with a source link, and drafts outreach.
3. **Score and build.** Ranks every lead 0–100 by likelihood of booking a meeting and builds the workbook.
4. **Deliver.** Emails the workbook to the reps (Justin Daubenmire, Eric Conaway) from leads@daubenmiregroup.com and saves everything to GitHub.
5. **Remember.** Past weeks' leads are stored so nobody is pitched twice; earlier leads carry forward in their own tab.

## Where leads come from (all public, nothing purchased)
| Source | What it reveals |
|---|---|
| Federal E-Rate records (USAC) | Which schools and libraries pay competitors (FIT Technologies, Blue Technologies) and when their contracts end. Also open bid requests and cybersecurity-program participants. |
| HHS breach portal | Ohio healthcare organizations that reported a data breach |
| USAspending.gov + SAM.gov | Defense manufacturers facing NIST 800-171 / CMMC cybersecurity rules |
| IRS nonprofit file + Form 990 filings | Nonprofits and healthcare orgs with revenue, staff count, leaders, website and phone |
| Census Bureau | Every city, village, township and school district, with website and lead official. Ohio HB 96 requires them to have a cybersecurity program. |
| Public DNS | Email-security gaps (for example, no DMARC record), a concrete opener |
| Weekly web research | Expansions, acquisitions, new executives, IT job postings, council IT decisions |

Territory: within about 45 miles of either office (Cleveland and Warren). Every lead shows its nearest office and distance.

## What the rep gets (Excel workbook)
- **Summary:** counts, a Warren/Cleveland split, and the 3 to call first.
- **Top Leads:** ranked, each with trigger, named contacts (with LinkedIn search links), phone, email-security finding and a suggested first-meeting offer.
- **Drafts:** first email, phone opener, voicemail and two follow-ups per lead.
- **Call Plan:** a dated 14-day sequence (email, call, follow-up), with drop-in visits for leads within 15 miles.
- **Back-up lists:** Competitor Clients, School Bids, Cyber Pilot, Manufacturing (DoD), Nonprofits, Healthcare, Government, Schools, Breach Watch.
- **Suppression tab:** paste HubSpot accounts here to flag existing customers.

## How leads are ranked (appointment score, 0–100)
Trigger strength and freshness, plus: named decision-maker, direct phone, distance to an office, email-security hook, size fit. The weights are editable and will be tuned to whatever actually books meetings.

## Guardrails
- Never writes to HubSpot or ConnectWise. Never emails prospects; drafts only, and a person sends them.
- Every claim has a source link. Names from third-party directories are marked "(verify)".
- No LinkedIn scraping (only LinkedIn search links).
- E-Rate rules: no gifts or free offers to schools and libraries, and no contact outside the bid once it posts.
- Cold-email volume kept around 30–50 a day per rep; CAN-SPAM footer required.

## Technology
- **Code and data:** GitHub `jdaub7360-dev/lead-gen` (Python). Key files: `README.md`, `WEEKLY.md` (the AI's weekly instructions), `configs/infinit.json` (territory, offices, offers, scoring), `sources/` (one script per data source), `build.py` (workbook), `mailer.py` (email).
- **Schedule:** Claude Code scheduled task, Mondays 5:47 am Eastern.
- **Services:** Resend (email, `RESEND_API_KEY`), SAM.gov (optional, free, `SAM_API_KEY`). Everything else is free public data.
- **Reuse:** a new client is a new config file (territory, offices, verticals, competitors, offers). Built to become a product for other MSPs.

## Status (Nov 19, 2026)
- Live since Nov 9. Weekly workbooks are being researched, built and emailed.
- **Known issue:** the scheduled runs can't save back to GitHub yet. They run in a general-purpose environment without access to the repo. Fix: a dedicated "lead-gen" cloud environment with the repo attached. Until then, weekly lead history isn't kept, so leads could repeat.
- **Next:** track meetings booked for 4–6 weeks and tune scoring; confirm infinIT's offers and E-Rate provider number (SPIN); optional Apollo integration under a credit cap.

## For an AI system using this
Start with `WEEKLY.md` and `configs/infinit.json`. Lead records live in `data/infinit/top_leads.json` (current week) and `data/infinit/history/` (past weeks): JSON objects with `name`, `vertical`, `city`, `county`, `trigger_type`, `trigger_date`, `why_now`, `contacts`, `phone`, `website`, `score`, `offer`, `subject`, `body`, `fu1`, `fu2`, `sources`. Treat every lead as a hypothesis backed by its `sources`; re-verify before acting.
