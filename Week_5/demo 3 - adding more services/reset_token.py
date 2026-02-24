"""
reset_token.py — Clear ALL cached LocalClaw tokens.
Run this if you need to re-authenticate any or all gateways.
"""
import keyring
import config

KEYRING_APP = "localclaw"

TOKENS = [
    {
        "label":   "Hotmail / Outlook (Email Gateway)",
        "key":     f"hotmail_token_cache_{config.EMAIL_ADDRESS}",
        "hint":    "gateway.py will open a browser login on next start.",
    },
    {
        "label":   "GitHub Personal Access Token (GitHub Gateway)",
        "key":     f"github_token_{config.GITHUB_USERNAME}",
        "hint":    "github_gateway.py will prompt for a new PAT on next start.",
    },
    {
        "label":   "Canvas LMS API Token (Canvas Gateway)",
        "key":     "canvas_token",
        "hint":    "canvas_gateway.py will prompt for a new token on next start.",
    },
]


def delete_token(label: str, key: str, hint: str) -> bool:
    try:
        keyring.delete_password(KEYRING_APP, key)
        print(f"  ✅  Cleared  — {label}")
        print(f"       {hint}")
        return True
    except Exception:
        print(f"  ℹ️   Not found — {label} (already cleared or never set)")
        return False


def main():
    print()
    print("═" * 56)
    print("  LocalClaw — Token Reset")
    print("═" * 56)
    print()
    print("  1)  Reset ALL tokens (full re-authentication)")
    print("  2)  Reset Hotmail token only")
    print("  3)  Reset GitHub token only")
    print("  4)  Reset Canvas token only")
    print()

    choice = input("  Choose [1-4]: ").strip()
    print()

    if choice == "1":
        for t in TOKENS:
            delete_token(**t)
    elif choice == "2":
        delete_token(**TOKENS[0])
    elif choice == "3":
        delete_token(**TOKENS[1])
    elif choice == "4":
        delete_token(**TOKENS[2])
    else:
        print("  Invalid choice. No tokens were changed.")
        return

    print()
    print("  Done. Restart the affected gateway(s) to re-authenticate.")
    print()


if __name__ == "__main__":
    main()
