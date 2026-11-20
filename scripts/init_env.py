"""Create local-only credentials once, without printing or overwriting secrets."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    print("Existing .env retained. Fill any missing settings using .env.example.")
else:
    values = (root / ".env.example").read_text()
    for key in ("POSTGRES_PASSWORD", "JWT_SECRET", "SEED_ADMIN_PASSWORD", "SEED_LAB_PASSWORD", "SEED_FIELD_PASSWORD"):
        values = values.replace(f"{key}=\n", f"{key}={secrets.token_urlsafe(36)}\n")
    with destination.open("x") as output:
        output.write(values)
    destination.chmod(0o600)
    print("Created private .env with random local database, signing, and demo account credentials.")
