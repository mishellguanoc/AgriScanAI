"""
Email utilities for sending diagnosis reports on demand.

The app only calls this module from an explicit user action, so SMTP work never
runs during normal page rendering.
"""

from __future__ import annotations

import html
import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_secret(key: str, default: str = "") -> str:
    try:
        import streamlit as st

        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str
    use_tls: bool = True


def get_smtp_config() -> SmtpConfig | None:
    host = _get_secret("SMTP_HOST")
    port_raw = _get_secret("SMTP_PORT", "587")
    username = _get_secret("SMTP_USERNAME")
    password = _get_secret("SMTP_PASSWORD")
    sender = _get_secret("EMAIL_FROM", username)
    use_tls = _get_secret("SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"}

    if not all([host, port_raw, username, password, sender]):
        return None

    try:
        port = int(port_raw)
    except ValueError:
        return None

    return SmtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        use_tls=use_tls,
    )


def is_valid_email(address: str) -> bool:
    return bool(EMAIL_RE.match((address or "").strip()))


def _report_lines(res: dict, report_messages: Iterable[dict]) -> list[str]:
    confidence = float(res.get("confidence", 0.0)) * 100
    captured_at = res.get("dt") or "N/D"
    lat = res.get("lat", "N/D")
    lon = res.get("lon", "N/D")

    lines = [
        "Reporte de diagnóstico AgriScan AI",
        "",
        f"Cultivo: {res.get('plant', 'N/D')}",
        f"Diagnóstico: {res.get('disease', 'N/D')}",
        f"Confianza: {confidence:.1f}%",
        f"Fecha de captura: {captured_at}",
        f"Ubicación: {lat}, {lon}",
        "",
        "Informe agronómico:",
    ]

    for msg in report_messages:
        if msg.get("role") == "assistant" and msg.get("content"):
            lines.extend(["", str(msg["content"])])
            break

    return lines


def send_diagnosis_email(recipient: str, res: dict, report_messages: Iterable[dict]) -> None:
    config = get_smtp_config()
    if config is None:
        raise RuntimeError(
            "Configura SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD y EMAIL_FROM."
        )

    recipient = recipient.strip()
    if not is_valid_email(recipient):
        raise ValueError("Ingresa un correo electrónico válido.")

    lines = _report_lines(res, report_messages)
    text_body = "\n".join(lines)
    html_body = "<br>".join(html.escape(line) for line in lines)

    msg = EmailMessage()
    msg["Subject"] = f"Diagnóstico AgriScan AI: {res.get('disease', 'resultado')}"
    msg["From"] = config.sender
    msg["To"] = recipient
    msg.set_content(text_body)
    msg.add_alternative(
        f"""
        <html>
          <body style="font-family:Inter,Arial,sans-serif;line-height:1.5;">
            <h2 style="color:#2E7D32;">Reporte de diagnóstico AgriScan AI</h2>
            <p>{html_body}</p>
          </body>
        </html>
        """,
        subtype="html",
    )

    with smtplib.SMTP(config.host, config.port, timeout=20) as smtp:
        if config.use_tls:
            smtp.starttls()
        smtp.login(config.username, config.password)
        smtp.send_message(msg)
