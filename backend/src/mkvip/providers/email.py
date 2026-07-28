import html
import smtplib
from collections.abc import Callable
from email.message import EmailMessage
from typing import Protocol


class EmailSender(Protocol):
    def send_verification_email(self, recipient: str, token: str) -> None:
        raise NotImplementedError

    def send_password_reset_email(self, recipient: str, token: str) -> None:
        raise NotImplementedError


class SmtpEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        public_app_url: str,
        timeout_seconds: float,
        starttls: bool,
        username: str | None,
        password: str | None,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._public_app_url = public_app_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._starttls = starttls
        self._username = username
        self._password = password
        self._smtp_factory = smtp_factory

    def send_verification_email(self, recipient: str, token: str) -> None:
        self._send(
            recipient,
            "Vérifie ton adresse MK-VIP",
            f"{self._public_app_url}/#verify-email={token}",
            "Vérifier mon adresse",
        )

    def send_password_reset_email(self, recipient: str, token: str) -> None:
        self._send(
            recipient,
            "Réinitialise ton mot de passe MK-VIP",
            f"{self._public_app_url}/#reset-password={token}",
            "Choisir un nouveau mot de passe",
        )

    def _send(
        self,
        recipient: str,
        subject: str,
        link: str,
        call_to_action: str,
    ) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(f"{call_to_action} : {link}")
        message.add_alternative(
            (
                "<html><body>"
                f'<p><a href="{html.escape(link, quote=True)}">'
                f"{html.escape(call_to_action)}</a></p>"
                "</body></html>"
            ),
            subtype="html",
        )
        with self._smtp_factory(
            self._host,
            self._port,
            timeout=self._timeout_seconds,
        ) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
