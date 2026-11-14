"""Append sent applications to job_applications_tracker.xlsx.

If the workbook is open in Excel (Windows locks it), the row is queued in
tracker_pending.csv and flushed on the next successful write.

Run `python tracker.py` on its own to flush the queue after closing Excel.

"Future Emails" sheet (addresses to mail later):
    python tracker.py future <email> [company] [role] [note]   # save one
    python tracker.py pending                                   # list Pending ones

"Apply Links" sheet (matching posts that have an apply link, applied manually):
    python tracker.py link <apply_url> [company] [role] [note] [post_url]

"Recruiter Outreach" sheet (posts with no email/link: connect, then message after accept):
    python tracker.py recruiter add|set|list|today ...
"""
import csv
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent
XLSX = ROOT / "job_applications_tracker.xlsx"
PENDING = ROOT / "tracker_pending.csv"
FIELDS = ["date", "company", "agency", "email", "role", "exp", "location", "resume", "score"]
HEADER_ROW = 4
FONT = "Arial"
THIN = Side(style="thin", color="D0D5DD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BAND = PatternFill("solid", fgColor="F5F7FA")
INPUT = PatternFill("solid", fgColor="FFF7CC")


def _save(wb):
    wb.save(XLSX)


def _last_row(ws):
    r = HEADER_ROW
    while ws.cell(row=r + 1, column=5).value:
        r += 1
    return r


def _write(ws, row):
    known = {str(ws.cell(row=r, column=5).value).lower() for r in range(HEADER_ROW + 1, _last_row(ws) + 1)}
    if row["email"].lower() in known:
        return False
    r = _last_row(ws) + 1
    n = r - HEADER_ROW
    score = int(row["score"]) if str(row["score"]).isdigit() else row["score"]
    vals = [n, date.fromisoformat(row["date"]), row["company"] or "Not named in post", row["agency"],
            row["email"], row["role"], row["exp"], row["location"] or "Not mentioned",
            row["resume"], score, "Sent", f"=B{r}+5", ""]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=FONT, size=10)
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=c in (6, 8, 13))
        if n % 2 == 0:
            cell.fill = BAND
    for c in (1, 2, 9, 10, 11, 12):
        ws.cell(row=r, column=c).alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(row=r, column=2).number_format = "DD-MMM-YYYY"
    ws.cell(row=r, column=12).number_format = "DD-MMM-YYYY"
    ws.cell(row=r, column=5).hyperlink = f"mailto:{row['email']}"
    ws.cell(row=r, column=5).font = Font(name=FONT, size=10, color="0563C1", underline="single")
    for c in (11, 13):
        ws.cell(row=r, column=c).fill = INPUT
    ws.auto_filter.ref = f"A{HEADER_ROW}:M{r}"
    return True


def _read_pending():
    if not PENDING.exists():
        return []
    with PENDING.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _queue(row):
    new = not PENDING.exists()
    with PENDING.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def add(row=None):
    """Write `row` (plus anything queued) to the workbook. Returns a status string."""
    rows = _read_pending() + ([row] if row else [])
    if not rows:
        return "tracker: nothing to add"
    if not XLSX.exists():
        if row:
            _queue(row)
        return f"tracker: {XLSX.name} not found, row queued in {PENDING.name}"
    try:
        wb = load_workbook(XLSX)
        ws = wb["Applications"]
        added = sum(_write(ws, r) for r in rows)
        if FUTURE in wb.sheetnames:
            _mark_future_sent(wb[FUTURE], {r["email"].lower() for r in rows})
        _save(wb)
    except PermissionError:
        if row:
            _queue(row)
        return f"tracker: workbook is open in Excel, row queued in {PENDING.name} (close Excel and run: python tracker.py)"
    PENDING.unlink(missing_ok=True)
    skipped = len(rows) - added
    return f"tracker: added {added} row(s)" + (f", {skipped} already in sheet" if skipped else "")


# ---- "Future Emails" sheet: addresses saved to mail later -------------------

FUTURE = "Future Emails"
FUTURE_HEAD = ["#", "Email", "Company", "Role", "Why saved / Note", "Added On", "Status"]
FUTURE_WIDTH = [5, 38, 24, 40, 50, 13, 12]


def _future_sheet(wb):
    if FUTURE in wb.sheetnames:
        return wb[FUTURE]
    ws = wb.create_sheet(FUTURE, 1)
    ws["A1"] = "Future Emails — saved to mail later"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3A5F")
    ws["A2"] = ("Add any email here (Status = Pending). The outreach skill offers Pending rows on each run "
                "and marks them Sent automatically. Set Status = Skip to drop one.")
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="555555")
    ws.merge_cells("A2:G2")
    for c, (h, w) in enumerate(zip(FUTURE_HEAD, FUTURE_WIDTH), 1):
        cell = ws.cell(row=HEADER_ROW, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
        ws.column_dimensions[chr(64 + c)].width = w
    dv = DataValidation(type="list", formula1='"Pending,Sent,Skip"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"G{HEADER_ROW + 1}:G{HEADER_ROW + 500}")
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=3)
    return ws


def _future_rows(ws):
    r = HEADER_ROW + 1
    while ws.cell(row=r, column=2).value:
        yield r
        r += 1


def _mark_future_sent(ws, emails):
    for r in _future_rows(ws):
        if str(ws.cell(row=r, column=2).value).strip().lower() in emails:
            ws.cell(row=r, column=7, value="Sent")


def save_future(entries):
    """entries: list of dicts with email, company, role, note. Skips duplicates and already-sent."""
    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        return "future: workbook is open in Excel, close it and try again"
    ws = _future_sheet(wb)
    apps = wb["Applications"]
    have = {str(ws.cell(row=r, column=2).value).strip().lower() for r in _future_rows(ws)}
    have |= {str(apps.cell(row=r, column=5).value).lower() for r in range(HEADER_ROW + 1, _last_row(apps) + 1)}
    r = HEADER_ROW + 1 + len(list(_future_rows(ws)))
    added = 0
    for e in entries:
        email = e["email"].strip()
        if email.lower() in have:
            continue
        have.add(email.lower())
        n = r - HEADER_ROW
        vals = [n, email, e.get("company", ""), e.get("role", ""), e.get("note", ""), date.today(), "Pending"]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = Font(name=FONT, size=10)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=c in (4, 5),
                                       horizontal="center" if c in (1, 6, 7) else None)
            if n % 2 == 0:
                cell.fill = BAND
        ws.cell(row=r, column=6).number_format = "DD-MMM-YYYY"
        ws.cell(row=r, column=7).fill = INPUT
        r += 1
        added += 1
    ws.auto_filter.ref = f"A{HEADER_ROW}:G{max(r - 1, HEADER_ROW)}"
    _save(wb)
    return f"future: added {added}, skipped {len(entries) - added} (duplicate or already mailed)"


def pending_future():
    wb = load_workbook(XLSX)
    if FUTURE not in wb.sheetnames:
        return []
    ws = wb[FUTURE]
    return [{"email": ws.cell(row=r, column=2).value, "company": ws.cell(row=r, column=3).value,
             "role": ws.cell(row=r, column=4).value, "note": ws.cell(row=r, column=5).value}
            for r in _future_rows(ws) if (ws.cell(row=r, column=7).value or "Pending") == "Pending"]


# ---- "Apply Links" sheet: matching posts with an apply link (manual apply) ---

LINKS = "Apply Links"
LINKS_HEAD = ["#", "Company", "Role", "Exp / Location / Why", "Apply Link", "LinkedIn Post", "Added On", "Status"]
LINKS_WIDTH = [5, 24, 36, 46, 40, 40, 13, 12]


def _links_sheet(wb):
    if LINKS in wb.sheetnames:
        return wb[LINKS]
    ws = wb.create_sheet(LINKS, 2)
    ws["A1"] = "Apply Links — matching posts to apply manually"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3A5F")
    ws["A2"] = "Open the link, apply, then set Status = Applied (or Skip)."
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="555555")
    ws.merge_cells("A2:H2")
    for c, (h, w) in enumerate(zip(LINKS_HEAD, LINKS_WIDTH), 1):
        cell = ws.cell(row=HEADER_ROW, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
        ws.column_dimensions[chr(64 + c)].width = w
    dv = DataValidation(type="list", formula1='"To Apply,Applied,Skip"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"H{HEADER_ROW + 1}:H{HEADER_ROW + 1000}")
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=3)
    return ws


def save_link(link, company="", role="", note="", post=""):
    """Save one apply link. Skips if the same apply link or post is already in the sheet."""
    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        return "link: workbook is open in Excel, close it and try again"
    ws = _links_sheet(wb)
    r = HEADER_ROW + 1
    have = set()
    while ws.cell(row=r, column=5).value:
        have |= {str(ws.cell(row=r, column=5).value).strip().lower(), str(ws.cell(row=r, column=6).value or "").strip().lower()}
        r += 1
    if link.strip().lower() in have or (post and post.strip().lower() in have):
        return "link: already saved"
    n = r - HEADER_ROW
    vals = [n, company, role, note, link, post, date.today(), "To Apply"]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=FONT, size=10)
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=c in (3, 4),
                                   horizontal="center" if c in (1, 7, 8) else None)
        if n % 2 == 0:
            cell.fill = BAND
    for c, url in ((5, link), (6, post)):
        if url:
            ws.cell(row=r, column=c).hyperlink = url
            ws.cell(row=r, column=c).font = Font(name=FONT, size=10, color="0563C1", underline="single")
    ws.cell(row=r, column=7).number_format = "DD-MMM-YYYY"
    ws.cell(row=r, column=8).fill = INPUT
    ws.auto_filter.ref = f"A{HEADER_ROW}:H{r}"
    _save(wb)
    return "link: added 1"


# ---- "Recruiter Outreach" sheet: connect on LinkedIn, message after accept ---

RECRUIT = "Recruiter Outreach"
RECRUIT_HEAD = ["#", "Recruiter", "LinkedIn Profile", "Company", "Role", "Exp / Location / Why",
                "Requested On", "Status", "Messaged On"]
RECRUIT_WIDTH = [5, 26, 42, 24, 34, 40, 13, 12, 13]


def _recruit_sheet(wb):
    if RECRUIT in wb.sheetnames:
        return wb[RECRUIT]
    ws = wb.create_sheet(RECRUIT, 3)
    ws["A1"] = "Recruiter Outreach — LinkedIn connect, then message"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3A5F")
    ws["A2"] = "Status: Requested -> Connected -> Messaged (or Skip). Updated by the scan."
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="555555")
    ws.merge_cells("A2:I2")
    for c, (h, w) in enumerate(zip(RECRUIT_HEAD, RECRUIT_WIDTH), 1):
        cell = ws.cell(row=HEADER_ROW, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
        ws.column_dimensions[chr(64 + c)].width = w
    dv = DataValidation(type="list", formula1='"Requested,Connected,Messaged,Skip"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"H{HEADER_ROW + 1}:H{HEADER_ROW + 1000}")
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=3)
    return ws


def _recruit_rows(ws):
    r = HEADER_ROW + 1
    while ws.cell(row=r, column=3).value:
        yield r
        r += 1


def _norm(url):
    return url.strip().rstrip("/").lower().replace("https://www.", "https://")


def recruiter_add(profile, name="", company="", role="", note="", status="Requested"):
    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        return "recruiter: workbook is open in Excel, close it and try again"
    ws = _recruit_sheet(wb)
    rows = list(_recruit_rows(ws))
    if any(_norm(str(ws.cell(row=r, column=3).value)) == _norm(profile) for r in rows):
        return "recruiter: already saved"
    r = HEADER_ROW + 1 + len(rows)
    n = r - HEADER_ROW
    vals = [n, name, profile, company, role, note, date.today(), status, None]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=FONT, size=10)
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=c in (5, 6),
                                   horizontal="center" if c in (1, 7, 8, 9) else None)
        if n % 2 == 0:
            cell.fill = BAND
    ws.cell(row=r, column=3).hyperlink = profile
    ws.cell(row=r, column=3).font = Font(name=FONT, size=10, color="0563C1", underline="single")
    for c in (7, 9):
        ws.cell(row=r, column=c).number_format = "DD-MMM-YYYY"
    ws.cell(row=r, column=8).fill = INPUT
    ws.auto_filter.ref = f"A{HEADER_ROW}:I{r}"
    _save(wb)
    return "recruiter: added 1"


def recruiter_set(profile, status):
    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        return "recruiter: workbook is open in Excel, close it and try again"
    ws = _recruit_sheet(wb)
    for r in _recruit_rows(ws):
        if _norm(str(ws.cell(row=r, column=3).value)) == _norm(profile):
            ws.cell(row=r, column=8, value=status)
            if status == "Messaged":
                ws.cell(row=r, column=9, value=date.today()).number_format = "DD-MMM-YYYY"
            _save(wb)
            return f"recruiter: {status}"
    return "recruiter: not found"


def recruiter_list(status=None):
    wb = load_workbook(XLSX, read_only=True)
    if RECRUIT not in wb.sheetnames:
        return []
    ws = wb[RECRUIT]
    out = []
    for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
        if not row[2]:
            break
        if status is None or row[7] == status:
            out.append({"name": row[1], "profile": row[2], "company": row[3], "role": row[4],
                        "requested": row[6], "status": row[7]})
    return out


# ---- "Indeed Applications" sheet: jobs applied via Indeed "Easily apply" ----

INDEED = "Indeed Applications"
INDEED_HEAD = ["#", "Job Key", "Company", "Role", "Location", "Job Link", "Date", "Status", "Note"]
INDEED_WIDTH = [5, 18, 26, 36, 22, 40, 13, 14, 44]


def _indeed_sheet(wb):
    if INDEED in wb.sheetnames:
        return wb[INDEED]
    ws = wb.create_sheet(INDEED, 4)
    ws["A1"] = "Indeed Applications — Easily-apply jobs"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3A5F")
    ws["A2"] = "Status: Applied | Skipped (question not answerable) | External (saved to Apply Links)."
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="555555")
    ws.merge_cells("A2:I2")
    for c, (h, w) in enumerate(zip(INDEED_HEAD, INDEED_WIDTH), 1):
        cell = ws.cell(row=HEADER_ROW, column=c, value=h)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER
        ws.column_dimensions[chr(64 + c)].width = w
    ws.freeze_panes = ws.cell(row=HEADER_ROW + 1, column=3)
    return ws


def indeed_add(jk, company="", role="", location="", status="Applied", note=""):
    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        return "indeed: workbook is open in Excel, close it and try again"
    ws = _indeed_sheet(wb)
    r = HEADER_ROW + 1
    while ws.cell(row=r, column=2).value:
        if str(ws.cell(row=r, column=2).value) == jk:
            return "indeed: already saved"
        r += 1
    n = r - HEADER_ROW
    url = f"https://in.indeed.com/viewjob?jk={jk}"
    vals = [n, jk, company, role, location, url, date.today(), status, note]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = Font(name=FONT, size=10)
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=c in (4, 9),
                                   horizontal="center" if c in (1, 7, 8) else None)
        if n % 2 == 0:
            cell.fill = BAND
    ws.cell(row=r, column=6).hyperlink = url
    ws.cell(row=r, column=6).font = Font(name=FONT, size=10, color="0563C1", underline="single")
    ws.cell(row=r, column=7).number_format = "DD-MMM-YYYY"
    ws.auto_filter.ref = f"A{HEADER_ROW}:I{r}"
    _save(wb)
    return f"indeed: {status}"


def indeed_rows():
    wb = load_workbook(XLSX, read_only=True)
    if INDEED not in wb.sheetnames:
        return []
    out = []
    for row in wb[INDEED].iter_rows(min_row=HEADER_ROW + 1, values_only=True):
        if not row[1]:
            break
        out.append({"jk": str(row[1]), "date": str(row[6])[:10], "status": row[7]})
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "future":
        # python tracker.py future <email> [company] [role] [note]
        a = sys.argv[2:] + [""] * 3
        print(save_future([{"email": a[0], "company": a[1], "role": a[2], "note": a[3]}]))
    elif len(sys.argv) > 2 and sys.argv[1] == "link":
        # python tracker.py link <apply_url> [company] [role] [note] [post_url]
        a = sys.argv[2:] + [""] * 4
        print(save_link(a[0], a[1], a[2], a[3], a[4]))
    elif len(sys.argv) > 2 and sys.argv[1] == "recruiter":
        # python tracker.py recruiter add <profile_url> [name] [company] [role] [note]
        # python tracker.py recruiter set <profile_url> <Requested|Connected|Messaged|Skip>
        # python tracker.py recruiter list [status]      |   python tracker.py recruiter today
        cmd, a = sys.argv[2], sys.argv[3:] + [""] * 5
        if cmd == "add":
            print(recruiter_add(a[0], a[1], a[2], a[3], a[4]))
        elif cmd == "set":
            print(recruiter_set(a[0], a[1]))
        elif cmd == "today":
            print(sum(1 for x in recruiter_list() if str(x["requested"])[:10] == date.today().isoformat()))
        else:
            for x in recruiter_list(a[0] or None):
                print(f"{x['status']} | {x['name']} | {x['profile']} | {x['company'] or ''} | {x['role'] or ''}")
    elif len(sys.argv) > 2 and sys.argv[1] == "indeed":
        # python tracker.py indeed add <jk> [company] [role] [location] [Applied|Skipped|External] [note]
        # python tracker.py indeed today      (Applied count today)
        # python tracker.py indeed seen       (all job keys already handled, comma-separated)
        cmd, a = sys.argv[2], sys.argv[3:] + [""] * 6
        if cmd == "add":
            print(indeed_add(a[0], a[1], a[2], a[3], a[4] or "Applied", a[5]))
        elif cmd == "today":
            print(sum(1 for x in indeed_rows() if x["status"] == "Applied" and x["date"] == date.today().isoformat()))
        elif cmd == "seen":
            print(",".join(x["jk"] for x in indeed_rows()))
    elif len(sys.argv) > 1 and sys.argv[1] == "pending":
        for p in pending_future():
            print(f"{p['email']} | {p['company'] or ''} | {p['role'] or ''} | {p['note'] or ''}")
    else:
        print(add())
