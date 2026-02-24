"""
core/guerrillamail.py
Complete Guerrilla Mail API client.
Handles session management, inbox polling, fetching, and deletion.
"""

import re
import requests
from dataclasses import dataclass, field
from typing import List, Optional
from core.logger import get_logger

API_URL = "http://api.guerrillamail.com/ajax.php"
HEADERS = {"User-Agent": "LocalClaw-GuerrillaClient/1.0"}

log = get_logger("guerrillamail")


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class MailSummary:
    """Lightweight email summary returned by check_email / get_email_list."""
    mail_id:        str
    mail_from:      str
    mail_subject:   str
    mail_excerpt:   str
    mail_timestamp: int
    mail_read:      int
    mail_date:      str
    att:            int = 0    # 1 if has attachments

    @classmethod
    def from_dict(cls, d: dict) -> "MailSummary":
        return cls(
            mail_id        = str(d.get("mail_id", "")),
            mail_from      = d.get("mail_from", ""),
            mail_subject   = d.get("mail_subject", "(no subject)"),
            mail_excerpt   = d.get("mail_excerpt", ""),
            mail_timestamp = int(d.get("mail_timestamp", 0)),
            mail_read      = int(d.get("mail_read", 0)),
            mail_date      = d.get("mail_date", ""),
            att            = int(d.get("att", 0)),
        )


@dataclass
class MailDetail:
    """Full email content returned by fetch_email."""
    mail_id:      str
    mail_from:    str
    mail_subject: str
    mail_body:    str          # raw HTML
    mail_date:    str
    mail_read:    int
    size:         str          = ""
    att:          int          = 0
    attachments:  list         = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "MailDetail":
        return cls(
            mail_id      = str(d.get("mail_id", "")),
            mail_from    = d.get("mail_from", ""),
            mail_subject = d.get("mail_subject", "(no subject)"),
            mail_body    = d.get("mail_body", ""),
            mail_date    = d.get("mail_date", ""),
            mail_read    = int(d.get("mail_read", 0)),
            size         = str(d.get("size", "")),
            att          = int(d.get("att", 0)),
            attachments  = d.get("att_list", []),
        )

    @property
    def body_text(self) -> str:
        """Return mail body as plain text (HTML tags stripped)."""
        text = re.sub(r"<[^>]+>", " ", self.mail_body)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;",  "&", text)
        text = re.sub(r"&lt;",   "<", text)
        text = re.sub(r"&gt;",   ">", text)
        text = re.sub(r"\s+",    " ", text)
        return text.strip()


# ── Client ────────────────────────────────────────────────────────────────────

class GuerrillaMailClient:
    """
    Full Guerrilla Mail API client.

    Usage:
        client = GuerrillaMailClient()
        print(client.email)                      # disposable inbox address
        mails  = client.check_email()            # poll for new emails
        detail = client.fetch_email(mails[0])    # get full email content
        print(detail.body_text)
        client.delete_email(mails[0])
    """

    def __init__(self, email_user: str = ""):
        self._session   = requests.Session()
        self._session.headers.update(HEADERS)
        self.sid_token  = ""
        self.email      = ""
        self.seq        = 0          # tracks last seen mail_id for check_email
        self._init(email_user)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call(self, func: str, extra: Optional[dict] = None) -> dict:
        """Make a single API call and return parsed JSON."""
        params = {
            "f":     func,
            "ip":    "127.0.0.1",
            "agent": "LocalClaw",
        }
        if self.sid_token:
            params["sid_token"] = self.sid_token
        if extra:
            params.update(extra)

        try:
            resp = self._session.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            log.error("API call timed out for function: %s", func)
            return {}
        except requests.exceptions.ConnectionError:
            log.error("Cannot reach Guerrilla Mail API. Check your internet connection.")
            return {}
        except requests.exceptions.HTTPError as e:
            log.error("HTTP error calling %s: %s", func, e)
            return {}
        except Exception as e:
            log.error("Unexpected error calling %s: %s", func, e)
            return {}

    def _init(self, email_user: str) -> None:
        """Initialize session: get or set an inbox address."""
        if email_user:
            data = self._call("set_email_user", {"email_user": email_user, "lang": "en"})
        else:
            data = self._call("get_email_address", {"lang": "en"})

        self.sid_token = data.get("sid_token", "")
        self.email     = data.get("email_addr", "")

        if not self.email:
            raise RuntimeError("Failed to initialize Guerrilla Mail session.")

        log.info("Inbox initialized: %s", self.email)

    # ── Address management ────────────────────────────────────────────────────

    def get_email_address(self) -> str:
        """Return the current inbox address."""
        return self.email

    def set_email_user(self, email_user: str) -> str:
        """
        Switch to a different inbox by username.
        Returns the new full email address.
        """
        data = self._call("set_email_user", {"email_user": email_user, "lang": "en"})
        self.sid_token = data.get("sid_token", self.sid_token)
        self.email     = data.get("email_addr", self.email)
        self.seq       = 0
        log.info("Switched inbox to: %s", self.email)
        return self.email

    def forget_me(self) -> None:
        """Forget the current session on the server side."""
        self._call("forget_me", {"email_addr": self.email})
        self.sid_token = ""
        self.email     = ""
        self.seq       = 0
        log.info("Session forgotten.")

    # ── Reading mail ──────────────────────────────────────────────────────────

    def check_email(self, skip_system: bool = True) -> List[MailSummary]:
        """
        Poll for new emails since the last call.
        Returns a list of MailSummary objects.

        Args:
            skip_system: If True, filters out Guerrilla Mail system/welcome emails.
        """
        data  = self._call("check_email", {"seq": self.seq})
        raw   = data.get("list", [])

        if skip_system:
            raw = [m for m in raw if "guerrillamail" not in m.get("mail_from", "").lower()]

        mails = [MailSummary.from_dict(m) for m in raw]

        if mails:
            self.seq = max(int(m.mail_id) for m in mails)

        return mails

    def get_email_list(self, offset: int = 0, skip_system: bool = True) -> List[MailSummary]:
        """
        Get the full inbox list starting from offset (max 20 per call).

        Args:
            offset:      Pagination offset.
            skip_system: Filter out Guerrilla Mail system emails.
        """
        data = self._call("get_email_list", {"offset": offset, "seq": self.seq})
        raw  = data.get("list", [])

        if skip_system:
            raw = [m for m in raw if "guerrillamail" not in m.get("mail_from", "").lower()]

        return [MailSummary.from_dict(m) for m in raw]

    def get_older_list(self, seq: int, offset: int = 0) -> List[MailSummary]:
        """
        Get emails older (lower ID) than seq.
        Useful for paginating backwards through the inbox.
        """
        data = self._call("get_older_list", {"seq": seq, "offset": offset})
        raw  = data.get("list", [])
        return [MailSummary.from_dict(m) for m in raw]

    def fetch_email(self, mail: MailSummary) -> Optional[MailDetail]:
        """
        Fetch the full content of an email.

        Args:
            mail: A MailSummary object (from check_email or get_email_list).

        Returns:
            MailDetail with full body, or None on failure.
        """
        data = self._call("fetch_email", {"email_id": str(mail.mail_id)})
        if not data:
            return None
        return MailDetail.from_dict(data)

    def fetch_email_by_id(self, mail_id: str) -> Optional[MailDetail]:
        """Fetch the full content of an email by its raw ID string."""
        data = self._call("fetch_email", {"email_id": str(mail_id)})
        if not data:
            return None
        return MailDetail.from_dict(data)

    # ── Managing mail ─────────────────────────────────────────────────────────

    def delete_email(self, *mails) -> bool:
        """
        Delete one or more emails.

        Args:
            mails: MailSummary objects or raw mail_id strings/ints.

        Returns:
            True if deletion was acknowledged.
        """
        ids = []
        for m in mails:
            if isinstance(m, MailSummary):
                ids.append(str(m.mail_id))
            else:
                ids.append(str(m))

        params = {f"email_ids[{i}]": mid for i, mid in enumerate(ids)}
        data   = self._call("del_email", params)
        deleted = data.get("deleted_ids", [])
        log.info("Deleted email IDs: %s", deleted)
        return bool(deleted)

    # ── Convenience ───────────────────────────────────────────────────────────

    def wait_for_email(self, timeout: int = 120, poll: int = 10) -> Optional[MailSummary]:
        """
        Block until a new email arrives or timeout is reached.

        Args:
            timeout: Max seconds to wait.
            poll:    Seconds between checks.

        Returns:
            The first new MailSummary, or None if timed out.
        """
        import time
        elapsed = 0
        while elapsed < timeout:
            mails = self.check_email()
            if mails:
                return mails[0]
            time.sleep(poll)
            elapsed += poll
        return None

    def inbox_count(self) -> int:
        """Return the total number of emails in the inbox."""
        data = self._call("get_email_list", {"offset": 0, "seq": self.seq})
        return int(data.get("count", 0))
