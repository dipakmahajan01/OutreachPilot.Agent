"""Send the next chunk (max 20) from queue/send_queue.txt; sent lines are removed from the queue.

Each queue line is a Python tuple:
    (to, subject, resume_key, role, score, company, agency, exp, location, draft_date)
and its body must exist at drafts/<draft_date>_<to>.txt.

    python scripts/send_queue.py --check            # validate only, send nothing
    python scripts/send_queue.py --n 20 --by-score  # send up to 20, best matches first
"""
import ast
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = Path(sys.argv[sys.argv.index("--queue") + 1]) if "--queue" in sys.argv else ROOT / "queue" / "send_queue.txt"
CHUNK = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20
DRY = "--check" in sys.argv

if not QUEUE.exists():
    sys.exit(f"queue empty: {QUEUE} not found")
rows = [ast.literal_eval(l) for l in QUEUE.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
if "--by-score" in sys.argv:
    rows.sort(key=lambda r: -r[4])
chunk, rest = rows[:CHUNK], rows[CHUNK:]
missing = [r[0] for r in chunk if not os.path.exists(f"{ROOT}/drafts/{r[9]}_{r[0]}.txt")]
print(f"queue={len(rows)} chunk={len(chunk)} missing_drafts={missing}", flush=True)
if DRY or missing:
    sys.exit(0 if DRY else 1)

failed = []
for n, (to, subj, resume, role, score, company, agency, exp, loc, d) in enumerate(chunk, 1):
    cmd = [sys.executable, "send_mail.py", "--to", to, "--subject", subj,
           "--body-file", f"drafts/{d}_{to}.txt", "--resume", resume,
           "--role", role, "--score", str(score), "--company", company,
           "--exp", exp, "--location", loc]
    if agency:
        cmd += ["--agency", agency]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout + r.stderr).strip()
    print(f"[{n}/{len(chunk)}] {to} ({resume}): {out}", flush=True)
    if "SENT" not in out and "already" not in out.lower():
        failed.append((to, subj, resume, role, score, company, agency, exp, loc, d))
    if n < len(chunk):
        time.sleep(random.randint(30, 60))

QUEUE.write_text("".join(repr(r) + "\n" for r in failed + rest), encoding="utf-8")
print(f"DONE failed={len(failed)} left_in_queue={len(failed) + len(rest)}", flush=True)
