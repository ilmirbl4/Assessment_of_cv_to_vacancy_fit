"""Create missing subsystem env files without printing or overwriting secrets."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    for name in (
        ".env",
        "backend/.env",
        "ml/.env",
        "collector/.env",
        "monitoring/.env",
        "deploy/db.env",
        "deploy/backup.env",
        "frontend/.env",
    ):
        path = ROOT / name
        if not path.exists():
            text = Path(str(path) + ".example").read_text()
            if name == "deploy/db.env":
                text = text.replace("POSTGRES_PASSWORD=\n", "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32) + "\n")
            path.write_text(text)
            path.chmod(0o600)
            print("Created", name)
        else:
            print("Preserved", name)


if __name__ == "__main__":
    main()
