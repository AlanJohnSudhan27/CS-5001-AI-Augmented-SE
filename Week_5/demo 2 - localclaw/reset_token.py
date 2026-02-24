"""
reset_token.py — Clear cached Hotmail OAuth token.
Run this if you change SCOPES or need to re-authenticate.
"""
import keyring

KEYRING_APP = "localclaw"
email = input("Enter your Hotmail address: ").strip()
key   = f"hotmail_token_cache_{email}"

try:
    keyring.delete_password(KEYRING_APP, key)
    print(f"✅ Token cleared for {email}")
    print("   Run gateway.py — it will prompt for a one-time browser login.")
except Exception:
    print(f"ℹ️  No cached token found for {email}.")
