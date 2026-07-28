import logging
import ssl
from email.message import EmailMessage
from uuid import uuid4

from mkvip.api.routes.auth import deliver_email_safely
from mkvip.providers.email import SmtpEmailSender


class RecordingSmtp:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.connection = (host, port, timeout)
        self.messages: list[EmailMessage] = []
        self.started_tls = False
        self.tls_context: ssl.SSLContext | None = None
        self.login_credentials: tuple[str, str] | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self, *, context: ssl.SSLContext) -> None:
        self.started_tls = True
        self.tls_context = context

    def login(self, username: str, password: str) -> None:
        self.login_credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_smtp_sender_builds_fragment_links_without_external_delivery() -> None:
    smtp_instances: list[RecordingSmtp] = []

    def smtp_factory(host: str, port: int, timeout: float) -> RecordingSmtp:
        smtp = RecordingSmtp(host, port, timeout)
        smtp_instances.append(smtp)
        return smtp

    sender = SmtpEmailSender(
        host="mailpit",
        port=1025,
        sender="MK-VIP <no-reply@mkvip.local>",
        public_app_url="http://localhost:5173",
        timeout_seconds=10,
        starttls=False,
        username=None,
        password=None,
        smtp_factory=smtp_factory,
    )

    sender.send_verification_email("investor@example.com", "verification-token")
    sender.send_password_reset_email("investor@example.com", "reset-token")

    verification = smtp_instances[0].messages[0].get_body(
        preferencelist=("html",)
    ).get_content()
    reset = smtp_instances[1].messages[0].get_body(
        preferencelist=("html",)
    ).get_content()
    assert "http://localhost:5173/#verify-email=verification-token" in verification
    assert "http://localhost:5173/#reset-password=reset-token" in reset
    assert smtp_instances[0].connection == ("mailpit", 1025, 10)


def test_smtp_sender_uses_tls_and_credentials_without_exposing_password() -> None:
    smtp_instances: list[RecordingSmtp] = []
    password = "smtp-super-secret"

    def smtp_factory(host: str, port: int, timeout: float) -> RecordingSmtp:
        smtp = RecordingSmtp(host, port, timeout)
        smtp_instances.append(smtp)
        return smtp

    sender = SmtpEmailSender(
        host="smtp.example.test",
        port=587,
        sender="MK-VIP <no-reply@mkvip.local>",
        public_app_url="https://app.example.test/",
        timeout_seconds=5,
        starttls=True,
        username="mailer",
        password=password,
        smtp_factory=smtp_factory,
    )

    sender.send_verification_email("investor@example.com", "verification-token")

    smtp = smtp_instances[0]
    assert smtp.started_tls is True
    assert smtp.tls_context is not None
    assert smtp.tls_context.check_hostname is True
    assert smtp.tls_context.verify_mode == ssl.CERT_REQUIRED
    assert smtp.login_credentials == ("mailer", password)
    assert password not in repr(sender)
    assert password not in smtp.messages[0].as_string()


def test_deliver_email_safely_logs_only_delivery_metadata(caplog) -> None:
    recipient = "investor@example.com"
    raw_token = "raw-token"
    smtp_password = "smtp-super-secret"
    hmac_secret = "hmac-super-secret"
    user_id = uuid4()

    def failing_sender() -> None:
        raise RuntimeError("SMTP unavailable")

    with caplog.at_level(logging.ERROR):
        deliver_email_safely(
            failing_sender,
            purpose="email_verification",
            user_id=user_id,
        )

    record = caplog.records[0]
    assert record.message == "auth_email_delivery_failed"
    assert record.purpose == "email_verification"
    assert record.user_id == str(user_id)
    assert record.error_type == "RuntimeError"
    rendered_log = caplog.text
    assert recipient not in rendered_log
    assert raw_token not in rendered_log
    assert smtp_password not in rendered_log
    assert hmac_secret not in rendered_log
