from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Union

from app.core.config import settings

def send_email(
    subject: str,
    recipients: Union[str, List[str]],
    body: str,
    html: str = None,
) -> bool:
    """
    Send an email using SMTP configuration from settings.

    Args:
        subject: Email subject.
        recipients: Single email address or list of email addresses.
        body: Plain text body of the email.
        html: Optional HTML body of the email.

    Returns:
        True if email was sent successfully, False otherwise.
    """
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        # In development, we might not have real credentials; just log and pretend.
        if settings.DEBUG:
            print(f"[DEBUG] Would send email to {recipients} with subject: {subject}")
            print(f"[DEBUG] Body: {body}")
            if html:
                print(f"[DEBUG] HTML: {html}")
            return True
        else:
            # In production, we don't want to fail silently, but we'll log and return False.
            print("[ERROR] Email credentials not configured.")
            return False

    # Normalize recipients to a list
    if isinstance(recipients, str):
        recipients = [recipients]

    # Create the email message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    msg["To"] = ", ".join(recipients)

    # Set the content
    if html:
        msg.add_alternative(body, subtype="plain")
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(body)

    # Create a secure SSL context
    context = ssl.create_default_context()

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            if settings.MAIL_STARTTLS:
                server.starttls(context=context)
            if settings.MAIL_USE_CREDENTIALS:
                server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        return False