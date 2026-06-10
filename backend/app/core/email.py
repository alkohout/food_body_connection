import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_FROM = "kohoutal@gmail.com"


def send_reset_email(to_email: str, reset_link: str):
    password = os.environ.get("SMTP_PASSWORD")
    if not password:
        raise RuntimeError("SMTP_PASSWORD not set in environment")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Food–Body Connection: Reset your password"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    text = (
        f"You requested a password reset for Food–Body Connection.\n\n"
        f"Click the link below to reset your password (expires in 1 hour):\n{reset_link}\n\n"
        f"If you didn't request this, you can ignore this email."
    )
    html = f"""
    <p>You requested a password reset for <strong>Food–Body Connection</strong>.</p>
    <p><a href="{reset_link}">Reset your password</a></p>
    <p>This link expires in <strong>1 hour</strong>.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_FROM, password)
        server.sendmail(SMTP_FROM, to_email, msg.as_string())
