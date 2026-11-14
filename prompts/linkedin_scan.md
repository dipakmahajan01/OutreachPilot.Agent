# OutreachPilot — LinkedIn scan prompt

Schedule this in Claude Code with `/loop 10m` (or CronCreate, every 10 minutes).
Replace `<PROJECT>` with the folder where you cloned this repo.

---

LinkedIn scan + draft run for <PROJECT>. NEVER send any email in this run — emails are sent only when I say "send all", in chunks of at most 20 per day.

Use the claude-in-chrome tools on my Chrome profile (LinkedIn already logged in). If a login, checkpoint, "unusual activity", "restricted" page or any LinkedIn warning about invitations shows, STOP, cancel this schedule, and tell me. Never open, click or type into any tab that is not linkedin.com, and mention any lookalike sign-in page you see. Never open apply links — only copy their text.

1. Pick ONE keyword per run, rotating through the "Search keywords" in profile.md (never repeat the previous run's keyword).
2. Open https://www.linkedin.com/search/results/content/?keywords=<kw>&sortBy=%22date_posted%22 and inject scanner/linkedin_collector.js, then run `await __scan(5)`.
3. Score each post against profile.md. Skip: roles outside India unless remote-India; stacks outside my skills (e.g. Java/.NET/PHP/SAP); 8+ year minimums; interns/freshers; open-to-work posts; referral or data-collection forms; posts older than ~2 weeks.
4. (A) EMAIL posts (`__res.hits`), for each match:
   - `python tracker.py future "<email>" "<company>" "<role>" "<exp, location, why>"`
   - write a 110–150 word draft to `drafts/<today>_<email>.txt` using only profile.md facts (see templates/email_draft.example.txt); pick the resume per profile.md
   - append a tuple line `(to, subject, resume, role, score, company, agency, exp, location, draft_date)` to `queue/send_queue.txt`, but never while a send batch is running.
5. (B) LINK posts (`__res.lp`): for each matching job, `python tracker.py link "<apply_url>" "<company>" "<role>" "<exp, location, why>"`. For multi-job posts, map each link to its own job.
6. (C) NO-CONTACT posts (`__res.np`): a real hiring post that matches but has no email or link, posted by a recruiter/HR person. At most 15 connection requests per day (`python tracker.py recruiter today`). Open the poster's profile, click Connect (directly or under More), choose "Send without a note", confirm Pending, then `python tracker.py recruiter add "<profile_url>" "<name>" "<company>" "<role>" "<why>"`.
7. (D) FOLLOW-UP: check up to 5 rows from `python tracker.py recruiter list Requested`. If a profile now shows **1st** degree (not just a Message button), send the FULL VERSION of drafts/linkedin_cold_message.txt once, with {Name} and {Role} filled in, then `python tracker.py recruiter set "<profile_url>" Messaged`. Never message anyone twice.
8. Run `__remember()` so the same emails and links are skipped next time.
9. End with one line: keyword, posts scanned, emails drafted, links saved, connects sent (today's total), messages sent.
