"""
core/processor.py
Processes incoming emails: builds prompts, calls Ollama, handles output.
"""

from core.config import Config
from core.ollama import OllamaClient
from core.guerrillamail import MailSummary, MailDetail, GuerrillaMailClient
from core.logger import get_logger

log = get_logger("processor")


class EmailProcessor:
    """
    Receives a fetched email, sends it to Ollama, and handles the reply.

    In DRY_RUN mode: logs the reply to terminal + log file.
    Otherwise:       logs the reply (Guerrilla Mail has no outbound SMTP).
                     Wire in your own SMTP relay in _send_reply() if needed.
    """

    def __init__(self, cfg: Config, ollama: OllamaClient, gm: GuerrillaMailClient):
        self.cfg    = cfg
        self.ollama = ollama
        self.gm     = gm

    def process(self, summary: MailSummary) -> bool:
        """
        Full pipeline for a single email:
          1. Fetch full body
          2. Build prompt
          3. Call Ollama
          4. Output reply
          5. Optionally delete email

        Returns True if processing succeeded, False otherwise.
        """
        log.info("Processing | From: %s | Subject: %s", summary.mail_from, summary.mail_subject)

        detail = self.gm.fetch_email(summary)
        if not detail:
            log.warning("Could not fetch email ID %s — skipping.", summary.mail_id)
            return False

        body = detail.body_text
        if not body.strip():
            log.info("Empty body — skipping email ID %s.", summary.mail_id)
            return False

        prompt = self._build_prompt(detail)
        reply  = self.ollama.chat(prompt)

        self._output_reply(detail, reply)

        if self.cfg.DELETE_AFTER_READ:
            self.gm.delete_email(summary)
            log.info("Deleted email ID %s.", summary.mail_id)

        return True

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_prompt(self, detail: MailDetail) -> str:
        body_preview = detail.body_text[:self.cfg.MAX_BODY_CHARS]
        truncated    = len(detail.body_text) > self.cfg.MAX_BODY_CHARS

        prompt = (
            f"You received an email. Here are the details:\n\n"
            f"FROM: {detail.mail_from}\n"
            f"SUBJECT: {detail.mail_subject}\n"
            f"DATE: {detail.mail_date}\n"
            f"---\n"
            f"{body_preview}"
        )
        if truncated:
            prompt += "\n[... email truncated ...]"
        prompt += "\n---\n\nPlease write a helpful, professional reply."
        return prompt

    def _output_reply(self, detail: MailDetail, reply: str) -> None:
        separator = "=" * 60
        block = (
            f"\n{separator}\n"
            f"  TO      : {detail.mail_from}\n"
            f"  SUBJECT : Re: {detail.mail_subject}\n"
            f"{separator}\n"
            f"{reply}\n"
            f"{separator}\n"
        )

        if self.cfg.DRY_RUN:
            log.info("[DRY RUN] Generated reply:\n%s", block)
        else:
            log.info("Reply ready:\n%s", block)
            self._send_reply(detail, reply)

    def _send_reply(self, detail: MailDetail, reply: str) -> None:
        """
        Outbound sending hook.
        Guerrilla Mail has no outbound SMTP — wire your own relay here.

        Example (using smtplib with a Gmail relay):

            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(reply)
            msg["From"]    = "your-relay@gmail.com"
            msg["To"]      = detail.mail_from
            msg["Subject"] = f"Re: {detail.mail_subject}"
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login("your-relay@gmail.com", "app-password")
                s.sendmail(msg["From"], msg["To"], msg.as_string())
        """
        log.info(
            "SEND hook not configured. Reply logged only.\n"
            "To actually send replies, implement _send_reply() in core/processor.py"
        )
