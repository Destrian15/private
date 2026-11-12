#!/usr/bin/env python3
"""Monitoring jobdesk harian: ringkasan harian + pengingat deadline (H-2, H-1, H-0, terlambat)."""
import csv
import os
import smtplib
import ssl
import sys
from collections import defaultdict
from datetime import date, datetime
from email.message import EmailMessage
from html import escape
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Jakarta"))
REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "2"))  # kirim pengingat mulai H-n
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
CSV_FILE = os.getenv("TASKS_FILE", "tasks.csv")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_TO = os.getenv("MAIL_TO", "")  # email Anda (penerima ringkasan + CC pengingat)

DONE = {"selesai", "done"}
PAUSED = {"ditunda", "hold"}


def load_tasks(today):
    tasks, errors = [], []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for n, row in enumerate(csv.DictReader(f), start=2):
            row = {k: (v or "").strip() for k, v in row.items()}
            if not row.get("jobdesk"):
                continue
            try:
                dl = datetime.strptime(row["deadline"], "%Y-%m-%d").date()
            except ValueError:
                errors.append(f"Baris {n} ('{row['jobdesk']}'): format deadline salah, gunakan YYYY-MM-DD")
                continue
            row["deadline_date"] = dl
            row["delta"] = (dl - today).days
            tasks.append(row)
    return tasks, errors


def label(delta):
    if delta < 0:
        return f"TERLAMBAT {abs(delta)} hari"
    if delta == 0:
        return "HARI INI"
    return f"H-{delta}"


def color(delta):
    if delta < 0:
        return "#c0392b"
    if delta <= REMINDER_DAYS:
        return "#e67e22"
    return "#2c3e50"


def table(rows):
    head = "".join(
        f"<th style='text-align:left;padding:6px 10px;background:#f2f2f2;border:1px solid #ddd'>{h}</th>"
        for h in ["Jobdesk", "PIC", "Prioritas", "Deadline", "Sisa", "Status", "Catatan"]
    )
    body = ""
    for r in rows:
        td = "padding:6px 10px;border:1px solid #ddd"
        body += (
            "<tr>"
            f"<td style='{td}'>{escape(r['jobdesk'])}</td>"
            f"<td style='{td}'>{escape(r['pic'])}</td>"
            f"<td style='{td}'>{escape(r['prioritas'])}</td>"
            f"<td style='{td}'>{r['deadline_date'].strftime('%d %b %Y')}</td>"
            f"<td style='{td};color:{color(r['delta'])};font-weight:bold'>{label(r['delta'])}</td>"
            f"<td style='{td}'>{escape(r['status'])}</td>"
            f"<td style='{td}'>{escape(r['catatan'])}</td>"
            "</tr>"
        )
    return f"<table style='border-collapse:collapse;font-size:14px'><tr>{head}</tr>{body}</table>"


def plain(rows):
    return "\n".join(
        f"- [{label(r['delta'])}] {r['jobdesk']} | PIC: {r['pic']} | {r['deadline']} | {r['status']}"
        for r in rows
    )


_smtp = None


def send(to, subject, html, text, cc=""):
    global _smtp
    if DRY_RUN or not (SMTP_USER and SMTP_PASS):
        print(f"\n=== [{'DRY RUN' if DRY_RUN else 'SMTP BELUM DISET'}] To: {to} | Cc: {cc}\nSubject: {subject}\n{text}\n")
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_USER, to, subject
    if cc:
        msg["Cc"] = cc
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    if _smtp is None:
        _smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context())
        _smtp.login(SMTP_USER, SMTP_PASS)
    _smtp.send_message(msg)
    print(f"Terkirim: {subject} -> {to}")


def main():
    today = datetime.now(TZ).date()
    tasks, errors = load_tasks(today)
    active = [t for t in tasks if t["status"].lower() not in DONE]
    done = [t for t in tasks if t["status"].lower() in DONE]
    running = [t for t in active if t["status"].lower() not in PAUSED]

    overdue = sorted([t for t in running if t["delta"] < 0], key=lambda t: t["delta"])
    due_soon = sorted([t for t in running if 0 <= t["delta"] <= REMINDER_DAYS], key=lambda t: t["delta"])
    upcoming = sorted([t for t in running if t["delta"] > REMINDER_DAYS], key=lambda t: t["delta"])
    paused = [t for t in active if t["status"].lower() in PAUSED]

    pct = round(len(done) / len(tasks) * 100) if tasks else 0

    # ---------- 1. Ringkasan harian ----------
    subject = (
        f"[Jobdesk {today.strftime('%d/%m/%Y')}] "
        f"{len(overdue)} terlambat, {len(due_soon)} mendekati deadline, {len(upcoming)} berjalan"
    )
    html = f"<h2>Monitoring Jobdesk - {today.strftime('%A, %d %B %Y')}</h2>"
    html += f"<p>Total tugas: <b>{len(tasks)}</b> | Selesai: <b>{len(done)}</b> ({pct}%) | Aktif: <b>{len(active)}</b></p>"
    text = f"Monitoring Jobdesk {today}\nTotal {len(tasks)} | Selesai {len(done)} ({pct}%) | Aktif {len(active)}\n"
    for title, rows in [
        ("Terlambat", overdue),
        (f"Mendekati deadline (H-{REMINDER_DAYS} s.d. hari ini)", due_soon),
        ("Sedang berjalan", upcoming),
        ("Ditunda", paused),
    ]:
        if rows:
            html += f"<h3>{title} ({len(rows)})</h3>{table(rows)}"
            text += f"\n{title} ({len(rows)})\n{plain(rows)}\n"
    if not active:
        html += "<p>Semua tugas selesai. 🎉</p>"
    if errors:
        html += "<h3>Perlu diperbaiki di tasks.csv</h3><ul>" + "".join(f"<li>{escape(e)}</li>" for e in errors) + "</ul>"
        text += "\nPerlu diperbaiki:\n" + "\n".join(errors) + "\n"

    summary_to = MAIL_TO or "(MAIL_TO belum diset)"
    send(summary_to, subject, html, text)

    # ---------- 2. Pengingat deadline per PIC ----------
    alerts = overdue + due_soon
    by_pic = defaultdict(list)
    for t in alerts:
        by_pic[(t["pic"], t["email_pic"])].append(t)

    for (pic, email), rows in by_pic.items():
        worst = min(r["delta"] for r in rows)
        subj = f"[PENGINGAT {label(worst)}] {len(rows)} jobdesk atas nama {pic or 'tanpa PIC'}"
        body_html = (
            f"<p>Halo {escape(pic) or 'Tim'}, berikut jobdesk yang mendekati/melewati deadline:</p>{table(rows)}"
            "<p>Mohon update status di tasks.csv setelah selesai.</p>"
        )
        send(email or MAIL_TO, subj, body_html, f"Halo {pic},\n{plain(rows)}\n", cc=MAIL_TO if email else "")

    # Ringkasan untuk tab Actions
    step = os.getenv("GITHUB_STEP_SUMMARY")
    if step:
        with open(step, "a", encoding="utf-8") as f:
            f.write(f"### Jobdesk {today}\n- Terlambat: {len(overdue)}\n- Mendekati deadline: {len(due_soon)}\n"
                    f"- Berjalan: {len(upcoming)}\n- Selesai: {len(done)} ({pct}%)\n")

    if _smtp:
        _smtp.quit()
    if errors:
        print("\n".join(errors), file=sys.stderr)


if __name__ == "__main__":
    main()
