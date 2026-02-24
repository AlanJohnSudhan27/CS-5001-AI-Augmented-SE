"""
LocalClaw — Personal AI Email Assistant
Guerrilla Mail + Ollama Edition

Entry point. Run this to start the gateway.
"""

import sys
import argparse
from core.gateway import Gateway
from core.config import Config


def parse_args():
    parser = argparse.ArgumentParser(
        description="LocalClaw — Personal AI Email Assistant (Guerrilla Mail + Ollama)"
    )
    parser.add_argument(
        "--inbox", "-i",
        default="",
        help="Custom inbox name (e.g. 'myclaw' → myclaw@guerrillamailblock.com). "
             "Leave empty for a random address."
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Ollama model to use (overrides config). e.g. llama3, mistral, phi3"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Log AI replies without taking any action."
    )
    parser.add_argument(
        "--poll", "-p",
        type=int,
        default=None,
        help="Poll interval in seconds (overrides config)."
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available Ollama models and exit."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg  = Config()

    # CLI overrides
    if args.inbox:
        cfg.GUERRILLA_EMAIL_USER = args.inbox
    if args.model:
        cfg.OLLAMA_MODEL = args.model
    if args.dry_run:
        cfg.DRY_RUN = True
    if args.poll:
        cfg.POLL_INTERVAL = args.poll

    if args.list_models:
        from core.ollama import OllamaClient
        client = OllamaClient(cfg)
        models = client.list_models()
        if models:
            print("\nAvailable Ollama models:")
            for m in models:
                print(f"  • {m}")
        else:
            print("No models found or Ollama is not running.")
        sys.exit(0)

    gateway = Gateway(cfg)
    gateway.run()


if __name__ == "__main__":
    main()
