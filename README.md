# Lead pipeline (multi-client)

Builds a prospect workbook for a B2B services company from free public data, plus a
researched "Top Leads" tab with draft outreach. infinIT is client #1.

## How it works

| Step | What | Where |
|---|---|---|
| 1. Profile | Client website → verticals, geography, proof points, angles | `configs/<client>.json` |
| 2. Lists | Public sources filtered to the client's geography and size range | `sources/*.py` |
| 3. Research | Claude picks the best 15-25 accounts, finds a timely trigger, drafts 3 emails each | `data/<client>/top_leads.json` |
| 4. Build | One workbook: Top Leads, a tab per vertical with A/B/C tiers, Apollo import, suppression check | `build.py` |
| 5. Work it | Rep enriches contacts in Apollo, sends from Outlook, updates Status | the sheet |

## Sources (all free, no API keys)

| Source | Gives us | Script |
|---|---|---|
| IRS Exempt Organizations file | Nonprofits, healthcare, religious orgs with revenue | `sources/irs_bmf.py` |
| IRS Form 990 e-filings (read in place from IRS archives) | Website, phone, employees, named officers | `sources/irs_990.py` |
| USAspending.gov | DoD contract recipients by county | `sources/usaspending.py` |
| Census population estimates | Cities, villages, townships | `sources/census_gov.py` |
| Census Government Units listing | Official websites, addresses, lead official titles; school districts | `sources/census_gus.py` |
| Census Gazetteer | Distance to the client's nearest office | `sources/geo.py` |
| HHS OCR breach portal | Healthcare breaches under investigation (trigger) | `sources/hhs_breach.py` |
| Public DNS | Email provider, SPF, DMARC, HTTPS (personalization hook) | `sources/domain_check.py` |
| Web research (Claude, weekly) | Triggers, contacts for non-nonprofits, drafts | `data/<client>/top_leads*.json` |

LinkedIn: links are LinkedIn *search* links (name + organization). Nothing is scraped.

## Running

```
./run.sh infinit data     # refresh lists and enrichment
./run.sh infinit build    # after top_leads.json is written: enrich Top Leads and build the workbook
python3 mailer.py ...     # email it (Resend)
```

## Adding a new client

1. Copy `configs/infinit.json` to `configs/<new>.json` and change the counties, ZIP prefixes,
   size ranges and messaging. Claude can draft this from the client's website.
2. Turn sources on or off to match their verticals (a dental-IT MSP doesn't need DoD data).
3. Run `./run.sh <new>` after Claude writes `data/<new>/top_leads.json` and `apollo_searches.json`.

## Guardrails

- Never writes to the client's CRM. HubSpot names get pasted into the Suppression tab instead.
- Drafts only. A person reviews and sends every email.
- Cold email volume stays within safe per-inbox limits (see Start Here tab).
