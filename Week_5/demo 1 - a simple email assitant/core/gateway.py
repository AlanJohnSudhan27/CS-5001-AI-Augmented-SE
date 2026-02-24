"""
core/gateway.py
The main gateway loop. Wires together GuerrillaMail, Ollama, and the Processor.
"""

import time
import signal
import sys

from core.config import Config
from core.guerrillamail import GuerrillaMailClient
from core.ollama import OllamaClient
from core.processor import EmailProcessor
from core.logger import get_logger

log = get_logger("gateway")


class Gateway:
    """
    Orchestrates the full LocalClaw loop:
      - Initializes Guerrilla Mail inbox
      - Checks Ollama is reachable
      - Polls inbox on a fixed interval
      - Hands each new email to EmailProcessor
    """

    def __init__(self, cfg: Config):
        self.cfg       = cfg
        self.running   = False
        self.gm        = None
        self.ollama    = None
        self.processor = None

        # Graceful shutdown on SIGINT / SIGTERM
        signal.signal(signal.SIGINT,  self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    # ── Startup ───────────────────────────────────────────────────────────────

    def _banner(self) -> None:
        w = 60
        print("=" * w)
        print(f"  {'LocalClaw — Guerrilla Mail + Ollama Edition':^{w-4}}")
        print("=" * w)
        print(f"  Inbox  : {self.gm.email}")
        print(f"  Model  : {self.cfg.OLLAMA_MODEL}")
        print(f"  Poll   : every {self.cfg.POLL_INTERVAL}s")
        print(f"  DryRun : {self.cfg.DRY_RUN}")
        print("=" * w)
        print()
        print("  Send emails to the inbox above.")
        print("  LocalClaw will read them and generate AI replies.")
        print("  Press Ctrl+C to stop.\n")

    def _check_ollama(self) -> None:
        if not self.ollama.is_running():
            log.error(
                "Ollama is not running!\n"
                "  Start it with: ollama serve\n"
                "  Then pull a model: ollama pull %s",
                self.cfg.OLLAMA_MODEL,
            )
            sys.exit(1)
        log.info("Ollama is running. Model: %s", self.cfg.OLLAMA_MODEL)

    def _init(self) -> None:
        log.info("Initializing gateway …")

        self.ollama = OllamaClient(self.cfg)
        self._check_ollama()

        self.gm = GuerrillaMailClient(
            email_user=self.cfg.GUERRILLA_EMAIL_USER
        )

        self.processor = EmailProcessor(self.cfg, self.ollama, self.gm)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._init()
        self._banner()

        self.running = True
        while self.running:
            self._tick()
            for _ in range(self.cfg.POLL_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

        log.info("Gateway stopped.")

    def _tick(self) -> None:
        """Single poll cycle: check inbox and process any new emails."""
        try:
            mails = self.gm.check_email()

            if not mails:
                log.info("No new emails. Waiting %ds …", self.cfg.POLL_INTERVAL)
                return

            log.info("Found %d new email(s).", len(mails))
            for mail in mails:
                try:
                    self.processor.process(mail)
                except Exception as e:
                    log.exception("Error processing email ID %s: %s", mail.mail_id, e)

        except Exception as e:
            log.exception("Error during poll cycle: %s", e)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _shutdown(self, *_) -> None:
        log.info("Shutdown signal received. Stopping …")
        self.running = False
