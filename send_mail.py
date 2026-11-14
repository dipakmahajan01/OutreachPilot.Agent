"""Send one job-application email via Gmail SMTP with the resume attached.

Usage:
    python send_mail.py --to hr@example.com --subject "..." --body-file drafts/x.txt [--dry-run]

Reads GMAIL_USER / GMAIL_APP_PASSWORD / FROM_NAME from .env.
--resume picks the attachment: "backend", "sde", "ai", or a file path.
Appends every successful send to sent_log.csv and refuses to mail the same address twice.
Also adds a row to job_applications_tracker.xlsx (see tracker.py).
"""
import argparse
import csv
import mimetypes
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import tracker

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "sent_log.csv"
LOG_FIELDS = ["timestamp", "to", "subject", "role", "score", "resume", "post_url"]
# Resume keys -> file. Override the paths in .env (RESUME_BACKEND / RESUME_SDE / RESUME_AI).
RESUMES = {
    "backend": "resume/backend.pdf",
    "sde": "resume/sde.pdf",
    "ai": "resume/genai.pdf",
}


def load_env():
    env = {}
    path = ROOT / ".env"
    if not path.exists():
        sys.exit("ERROR: .env not found. Copy .env.example to .env and fill it in.")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    for key in ("GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if not env.get(key):
            sys.exit(f"ERROR: {key} missing in .env")
    return env


def already_sent(address):
    if not LOG.exists():
        return False
    with LOG.open(newline="", encoding="utf-8") as f:
        return any(row["to"].lower() == address.lower() for row in csv.DictReader(f))


def log_send(row):
    new = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body-file", required=True)
    p.add_argument("--resume", required=True, help='"backend", "sde", "ai", or a file path')
    p.add_argument("--role", default="")
    p.add_argument("--score", default="")
    p.add_argument("--post-url", default="")
    p.add_argument("--company", default="")
    p.add_argument("--agency", default="", help="recruiting agency, if the post is for a client")
    p.add_argument("--exp", default="", help='experience asked, e.g. "4–6 yrs"')
    p.add_argument("--location", default="", help='e.g. "Bangalore · Hybrid"')
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    env = load_env()
    if already_sent(a.to):
        sys.exit(f"SKIP: already mailed {a.to}")

    resumes = {k: env.get(f"RESUME_{k.upper()}", v) for k, v in RESUMES.items()}
    resume = Path(resumes.get(a.resume, a.resume))
    if not resume.is_absolute():
        resume = ROOT / resume
    if not resume.exists():
        sys.exit(f"ERROR: resume not found at {resume}")

    msg = EmailMessage()
    from_name = env.get("FROM_NAME", "")
    msg["From"] = f"{from_name} <{env['GMAIL_USER']}>" if from_name else env["GMAIL_USER"]
    msg["To"] = a.to
    msg["Subject"] = a.subject
    msg.set_content(Path(a.body_file).read_text(encoding="utf-8"))

    ctype = mimetypes.guess_type(resume.name)[0] or "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    msg.add_attachment(resume.read_bytes(), maintype=maintype, subtype=subtype, filename=resume.name)

    if a.dry_run:
        print(f"DRY RUN: would send to {a.to} | {a.subject} | attachment {resume.name}")
        return

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(env["GMAIL_USER"], env["GMAIL_APP_PASSWORD"])
        s.send_message(msg)

    log_send({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "to": a.to, "subject": a.subject, "role": a.role,
        "score": a.score, "resume": resume.name, "post_url": a.post_url,
    })
    print(f"SENT: {a.to}")
    label = {"backend": "Backend", "sde": "SDE", "ai": "GenAI"}.get(a.resume, resume.name)
    print(tracker.add({
        "date": datetime.now().date().isoformat(), "company": a.company, "agency": a.agency,
        "email": a.to, "role": a.role, "exp": a.exp, "location": a.location,
        "resume": label, "score": a.score,
    }))


if __name__ == "__main__":
    main()
