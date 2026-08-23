from typing import Optional

from celery_app import celery_app
from services.email_services import send_email


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def task_send_status_change_email(
    self,
    to: str,
    name: str,
    complaint_id: int,
    category: str,
    old_status: str,
    new_status: str,
    note: Optional[str] = None,
):
    try:
        note_html = f"<p><strong>Note from admin:</strong> {note}</p>" if note else ""
        send_email(
            to=to,
            subject=f"Complaint #{complaint_id} status updated",
            html_body=f"""
            <p>Hi {name},</p>
            <p>Your <strong>{category}</strong> complaint (#{complaint_id}) status changed
               from <strong>{old_status}</strong> to <strong>{new_status}</strong>.</p>
            {note_html}
            """,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def task_send_important_notice_email(
    self,
    to: str,
    name: str,
    notice_title: str,
    notice_body: str,
):
    try:
        send_email(
            to=to,
            subject=f"Important notice: {notice_title}",
            html_body=f"""
            <p>Hi {name},</p>
            <p>A new important notice has been posted on the society notice board:</p>
            <h3>{notice_title}</h3>
            <p>{notice_body}</p>
            """,
        )
    except Exception as exc:
        raise self.retry(exc=exc)