# OutreachPilot — "send all"

Say this in Claude Code when you want the queued drafts mailed (once a day is enough):

---

send all — count today's rows in sent_log.csv, slots = 20 − that count. Run
`python scripts/send_queue.py --check`, then `python scripts/send_queue.py --n <slots> --by-score`.
Report who was sent, any failures (they stay in the queue), and what is left for tomorrow.

---

The script waits 30–60 seconds between emails, never mails the same address twice (sent_log.csv),
and logs every send in job_applications_tracker.xlsx.
