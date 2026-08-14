from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from src.shared.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from src.shared.logging_utils import log_event, mask_email

logger = logging.getLogger("agroecology.email")

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


async def send_suggestion_submitted_email(
    admin_email: str, submitter_name: str, submitter_email: str, title: str
) -> bool:
    subject = "New document suggestion submitted"
    display_title = title or "Untitled"
    body = f"""<h2>New Suggestion</h2>
<p>A user has submitted a new document suggestion:</p>
<table>
<tr><td><strong>User:</strong></td><td>{submitter_name} ({submitter_email})</td></tr>
<tr><td><strong>Title:</strong></td><td>{display_title}</td></tr>
</table>
<p>Log in to the admin panel to review it.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    return await send_email(admin_email, subject, body)


async def send_suggestion_approved_email(
    user_email: str, title: str, locale: str = "pt-BR"
) -> bool:
    display_title = title or "Untitled"
    if locale.startswith(("pt", "es")):
        if locale.startswith("pt"):
            subject = "Sua sugestão foi aprovada"
            body = f"""<h2>Sugestão Aprovada</h2>
<p>Sua sugestão <strong>{display_title}</strong> foi aprovada e já está disponível na base de conhecimento.</p>
<p>Em até 48h o artigo será indexado/ingerido e estará disponível para consulta no Chat.</p>
<p>Obrigado por contribuir!</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
        else:
            subject = "Tu sugerencia fue aprobada"
            body = f"""<h2>Sugerencia Aprobada</h2>
<p>Tu sugerencia <strong>{display_title}</strong> fue aprobada y ya está disponible en la base de conocimiento.</p>
<p>En hasta 48h el artículo será indexado/ingerido y estará disponible para consulta en el Chat.</p>
<p>¡Gracias por contribuir!</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    elif locale.startswith("fr"):
        subject = "Votre suggestion a été approuvée"
        body = f"""<h2>Suggestion Approuvée</h2>
<p>Votre suggestion <strong>{display_title}</strong> a été approuvée et est désormais disponible dans la base de connaissances.</p>
<p>Dans un délai de 48h, l'article sera indexé/ingéré et disponible dans le Chat.</p>
<p>Merci d'avoir contribué !</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    else:
        subject = "Your suggestion was approved"
        body = f"""<h2>Suggestion Approved</h2>
<p>Your suggestion <strong>{display_title}</strong> has been approved and is now available in the knowledge base.</p>
<p>Within 48h the article will be indexed/ingested and available in the Chat.</p>
<p>Thank you for contributing!</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    return await send_email(user_email, subject, body)


async def send_suggestion_rejected_email(
    user_email: str, title: str, admin_comment: str, locale: str = "pt-BR"
) -> bool:
    display_title = title or "Untitled"
    if locale.startswith(("pt", "es")):
        if locale.startswith("pt"):
            subject = "Sua sugestão foi revisada"
            body = f"""<h2>Sugestão Revisada</h2>
<p>Sua sugestão <strong>{display_title}</strong> foi revisada.</p>
<p><strong>Comentário:</strong> {admin_comment}</p>
<p>Você pode enviar uma nova sugestão a qualquer momento.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
        else:
            subject = "Tu sugerencia fue revisada"
            body = f"""<h2>Sugerencia Revisada</h2>
<p>Tu sugerencia <strong>{display_title}</strong> fue revisada.</p>
<p><strong>Comentario:</strong> {admin_comment}</p>
<p>Puedes enviar una nueva sugerencia en cualquier momento.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    elif locale.startswith("fr"):
        subject = "Votre suggestion a été révisée"
        body = f"""<h2>Suggestion Révisée</h2>
<p>Votre suggestion <strong>{display_title}</strong> a été révisée.</p>
<p><strong>Commentaire :</strong> {admin_comment}</p>
<p>Vous pouvez envoyer une nouvelle suggestion à tout moment.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    else:
        subject = "Your suggestion was reviewed"
        body = f"""<h2>Suggestion Reviewed</h2>
<p>Your suggestion <strong>{display_title}</strong> has been reviewed.</p>
<p><strong>Comment:</strong> {admin_comment}</p>
<p>You can submit a new suggestion at any time.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    return await send_email(user_email, subject, body)


async def send_delete_account_confirmation_email(
    to_email: str, token: str, locale: str = "pt-BR"
) -> bool:
    from src.shared.config import APP_URL

    link = f"{APP_URL}/confirm-delete-account?token={token}"

    if locale.startswith("pt"):
        subject = "Confirme a exclusão da sua conta"
        body = f"""<h2>Exclusão de Conta</h2>
<p>Recebemos uma solicitação para excluir sua conta no Agroecology Map AI.</p>
<p>Clique no link abaixo para confirmar a exclusão:</p>
<p><a href="{link}">{link}</a></p>
<p><strong>Atenção:</strong> Esta ação é irreversível. Seus dados pessoais serão anonimizados permanentemente.</p>
<p>Este link expira em 1 hora.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""
    else:
        subject = "Confirm your account deletion"
        body = f"""<h2>Account Deletion</h2>
<p>We received a request to delete your account on Agroecology Map AI.</p>
<p>Click the link below to confirm the deletion:</p>
<p><a href="{link}">{link}</a></p>
<p><strong>Warning:</strong> This action is irreversible. Your personal data will be permanently anonymized.</p>
<p>This link expires in 1 hour.</p>
<hr>
<p><small>Agroecology Map AI — Free Software (GPLv3)</small></p>"""

    return await send_email(to_email, subject, body)


async def send_orcid_link_confirmation_email(
    to_email: str, token: str, locale: str = "pt-BR"
) -> bool:
    from src.shared.config import APP_URL

    link = f"{APP_URL}/auth/orcid/confirm-link?token={token}"

    if locale.startswith("pt"):
        subject = "Confirme o vinculo com ORCID"
        body = f"""<h2>Vincular ORCID</h2>
<p>Recebemos uma solicitação para vincular uma conta ORCID ao seu perfil no Agroecology Map AI.</p>
<p>Clique no link abaixo para confirmar o vinculo:</p>
<p><a href="{link}">{link}</a></p>
<p>Este link expira em breve. Se voce nao solicitou isso, ignore este email.</p>
<hr>
<p><small>Agroecology Map AI - Free Software (GPLv3)</small></p>"""
    else:
        subject = "Confirm ORCID account linking"
        body = f"""<h2>Link ORCID</h2>
<p>We received a request to link an ORCID account to your Agroecology Map AI profile.</p>
<p>Click the link below to confirm the link:</p>
<p><a href="{link}">{link}</a></p>
<p>This link expires soon. If you did not request this, ignore this email.</p>
<hr>
<p><small>Agroecology Map AI - Free Software (GPLv3)</small></p>"""

    return await send_email(to_email, subject, body)
