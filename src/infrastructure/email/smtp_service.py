from __future__ import annotations

import logging

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.shared.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger(__name__)

_PREFIX = "[Agroecology Map]"


def _enabled() -> bool:
    return bool(SMTP_HOST and SMTP_USER)


async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    if not _enabled():
        log_event(
            logger,
            logging.INFO,
            "email_skipped",
            reason="smtp_not_configured",
            to_email=mask_email(to_email),
            subject=subject,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = f"{_PREFIX} {subject}"
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        log_event(
            logger,
            logging.INFO,
            "email_send_started",
            to_email=mask_email(to_email),
            subject=subject,
        )
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )
        log_event(
            logger,
            logging.INFO,
            "email_send_completed",
            to_email=mask_email(to_email),
            subject=subject,
        )
        return True
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "email_send_failed",
            to_email=mask_email(to_email),
            subject=subject,
            error=e,
        )
        return False


async def send_confirmation_email(
    to_email: str, token: str, locale: str = "pt-BR"
) -> bool:
    from src.shared.config import APP_URL

    link = f"{APP_URL}/confirm-email?token={token}"

    if locale.startswith("pt"):
        subject = "Confirme seu email"
        body = f"""<h2>Bem-vindo ao Agroecology Map AI!</h2>
<p>Obrigado por se registrar. Clique no link abaixo para confirmar seu email:</p>
<p><a href="{link}">{link}</a></p>
<p>Este link expira em 24 horas.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    else:
        subject = "Confirm your email"
        body = f"""<h2>Welcome to Agroecology Map AI!</h2>
<p>Thank you for registering. Click the link below to confirm your email:</p>
<p><a href="{link}">{link}</a></p>
<p>This link expires in 24 hours.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""

    return await send_email(to_email, subject, body)


async def send_reset_email(to_email: str, token: str, locale: str = "pt-BR") -> bool:
    from src.shared.config import APP_URL

    link = f"{APP_URL}/reset-password?token={token}"

    if locale.startswith("pt"):
        subject = "Redefinição de senha"
        body = f"""<h2>Redefinição de senha</h2>
<p>Clique no link abaixo para redefinir sua senha:</p>
<p><a href="{link}">{link}</a></p>
<p>Este link expira em 1 hora.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    else:
        subject = "Password Reset"
        body = f"""<h2>Password Reset</h2>
<p>Click the link below to reset your password:</p>
<p><a href="{link}">{link}</a></p>
<p>This link expires in 1 hour.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""

    return await send_email(to_email, subject, body)


async def send_admin_new_user_notification(
    user_email: str, user_name: str, locale: str = "pt-BR"
) -> bool:
    from src.shared.config import ADMIN_EMAIL

    subject = f"New user registered: {user_email}"
    body = f"""<h2>New User Registration</h2>
<p>A new user has registered on Agroecology Map AI:</p>
<table>
<tr><td><strong>Name:</strong></td><td>{user_name}</td></tr>
<tr><td><strong>Email:</strong></td><td>{user_email}</td></tr>
<tr><td><strong>Locale:</strong></td><td>{locale}</td></tr>
</table>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""

    return await send_email(ADMIN_EMAIL, subject, body)
