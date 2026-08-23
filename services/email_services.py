import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

MAIL_USER = os.getenv("mail_user")
MAIL_PASS = os.getenv("mail_pass")


def send_email(to: str, subject: str, html_body: str):
    if not MAIL_USER or not MAIL_PASS:
        raise RuntimeError("mail_user or mail_pass not set in .env")

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Society Tracker <{MAIL_USER}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_USER, to, msg.as_string())
            print(f"Email sent to {to}")
    except Exception as e:
        print(f"Error sending email: {e}")
        raise