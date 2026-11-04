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

- **IRS Exempt Organizations Business Master File:** nonprofits, healthcare and religious orgs, with revenue.
- **USAspending.gov:** DoD contract recipients by county (manufacturers facing CMMC / NIST 800-171).
- **Census subcounty population estimates:** cities, villages and townships (Ohio HB 96 cyber-program mandate).
- **Web research:** triggers such as new sites, IT job postings, leadership changes, council actions.

## Adding a new client

1. Copy `configs/infinit.json` to `configs/<new>.json` and change the counties, ZIP prefixes,
   size ranges and messaging. Claude can draft this from the client's website.
2. Turn sources on or off to match their verticals (a dental-IT MSP doesn't need DoD data).
3. Run `./run.sh <new>` after Claude writes `data/<new>/top_leads.json` and `apollo_searches.json`.

## Guardrails

- Never writes to the client's CRM. HubSpot names get pasted into the Suppression tab instead.
- Drafts only. A person reviews and sends every email.
- Cold email volume stays within safe per-inbox limits (see Start Here tab).
