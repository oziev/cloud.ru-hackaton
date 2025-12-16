
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from shared.config.settings import settings
from shared.utils.logger import api_logger
class EmailService:
    def __init__(self):
        self.smtp_host = getattr(settings, 'smtp_host', None)
        self.smtp_port = getattr(settings, 'smtp_port', 587)
        self.smtp_user = getattr(settings, 'smtp_user', None)
        self.smtp_password = getattr(settings, 'smtp_password', None)
        self.smtp_from = getattr(settings, 'smtp_from', 'testops-copilot@cloud.ru')
        self.enabled = getattr(settings, 'email_notifications_enabled', False)
    def _is_configured(self) -> bool:
        return self.enabled and self.smtp_host and self.smtp_user and self.smtp_password
    def send_notification(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        if not self._is_configured():
            api_logger.warning("Email service not configured, skipping notification")
            return False
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_from
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            api_logger.info(f"Email notification sent to {to}", extra={"subject": subject})
            return True
        except Exception as e:
            api_logger.error(f"Failed to send email notification: {e}", exc_info=True)
            return False
    def send_generation_completed(
        self,
        to: str,
        request_id: str,
        tests_count: int,
        status: str = "completed"
    ) -> bool:
        subject = f"Test Generation {'Completed' if status == 'completed' else 'Failed'}"
        body = f
        html_body = f
        return self.send_notification(to, subject, body, html_body)
    def send_error_notification(
        self,
        to: str,
        request_id: str,
        error_message: str
    ) -> bool:
        subject = "Test Generation Error"
        body = f
        html_body = f
        return self.send_notification(to, subject, body, html_body)
email_service = EmailService()