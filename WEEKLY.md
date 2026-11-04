# Weekly run (infinIT)

The scheduled task runs this every Monday at 7:00 am Eastern. Follow it step by step.

1. **Refresh the lists:** `./run.sh infinit`. If USAspending fails, delete nothing; the committed cached
   county files in `data/infinit/cache/` are used. Clear the cache once a month so the DoD data refreshes.
2. **Research new Top Leads (15-20):**
   - Skip every organization that appears in `data/infinit/history/` (all past weeks' Top Leads).
   - Mix the verticals: DoD manufacturers, healthcare and behavioral health, nonprofits, municipalities (HB 96),
     plus one or two from the Apollo Searches segments. Favor Trumbull, Mahoning, Summit, Cuyahoga.
   - Each lead needs a dated, sourced reason to reach out now. No source, no lead.
   - Re-check the CMMC status before writing manufacturing drafts (Phase 2 paused July 2026; confirm whether that changed).
   - Write `data/infinit/top_leads.json` in the same format as earlier weeks (subject, body, fu1, fu2, sources...).
   - Copy it to `data/infinit/history/top_leads_YYYY-MM-DD.json`.
3. **Build:** `python3 build.py configs/infinit.json data/infinit output/infinit_leads_YYYY-MM-DD.xlsx`
   (run.sh already does this; rerun it after writing the new top leads).
4. **Check:** recalculate with LibreOffice and confirm no `#` errors, as in the first run.
5. **Email** the workbook with `mailer.py` (Resend, from leads@daubenmiregroup.com; never from infinit.us) to the recipients in `configs/infinit.json` → `email.to`.
   Body: number of new Top Leads by vertical, the 3 to call first and why, and anything notable
   (e.g. a regulation change). Subject: `infinIT leads – week of <Mon date>`.
6. **Commit and push** to `main`: new data, history file and workbook. Message: `Weekly leads YYYY-MM-DD`.
7. If any step fails (email especially), still commit what was built and say what failed in the commit message.
