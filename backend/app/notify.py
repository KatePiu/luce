"""Invio email al tutor umano in caso di escalation. SMTP semplice, nessuna dipendenza esterna."""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from app.config import settings


def send_escalation_email(subject: str, body: str) -> None:
    if not settings.smtp_host:
        # In sviluppo, senza SMTP configurato, si logga soltanto invece di far fallire la richiesta.
        print(f"[notify] SMTP non configurato — email non inviata.\nOggetto: {subject}\n{body}")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = settings.human_tutor_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
