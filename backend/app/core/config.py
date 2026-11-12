"""Settings come only from environment variables. A local .env file is read in development."""

import os
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_env() -> None:
    """Load REPO_ROOT/.env if it exists. Real environment variables always win."""
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    from dotenv import load_dotenv

    load_dotenv(path, override=False)


def database_url() -> str:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see README: Run locally)")
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    google_client_id: str  # public: it is sent to the browser
    session_secret: str  # signs session cookies; never leaves the server
    admin_emails: frozenset[str]  # lower-case emails allowed to act as Admin
    cookie_secure: bool  # True behind HTTPS (Render), False on http://localhost
    payment_secret: str = ""  # shared with the (mock) payment provider to sign confirmations
    seals_repo: str = ""  # owner/repo of the public GitHub seals repository
    seals_token: str = ""  # fine-grained token: Contents read/write on that one repository only
    founder_mobile: str = ""  # the Founder's number for the OTP SMS (FOUNDER_MOBILE)
    sms_mode: str = ""  # "msg91" sends real SMS; anything else writes the OTP to the server log
    msg91_auth_key: str = ""
    msg91_template_id: str = ""
    msg91_otp_variable: str = "OTP"
    otp_expiry_minutes: int = 10
    # 10-digit mobiles allowed to act as Admin (ADMIN_MOBILES). Set in the Render dashboard, never committed:
    # the repository is public and these are personal numbers.
    admin_mobiles: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        return cls(
            database_url=database_url(),
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
            session_secret=_secret("SESSION_SECRET"),
            admin_emails=frozenset(
                e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()
            ),
            admin_mobiles=admin_mobiles(os.environ.get("ADMIN_MOBILES", "")),
            cookie_secure=os.environ.get("COOKIE_SECURE", "false").strip().lower() == "true",
            payment_secret=_secret("PAYMENT_WEBHOOK_SECRET"),
            seals_repo=os.environ.get("SEALS_REPO", "").strip(),
            seals_token=os.environ.get("SEALS_GITHUB_TOKEN", "").strip(),
            founder_mobile=os.environ.get("FOUNDER_MOBILE", "").strip(),
            sms_mode=os.environ.get("SMS_MODE", "").strip().lower(),
            msg91_auth_key=os.environ.get("MSG91_AUTH_KEY", "").strip(),
            msg91_template_id=os.environ.get("MSG91_OTP_TEMPLATE_ID", "").strip(),
            msg91_otp_variable=os.environ.get("MSG91_OTP_VARIABLE", "OTP").strip() or "OTP",
            otp_expiry_minutes=int(os.environ.get("OTP_EXPIRY_MINUTES", "10") or 10),
        )


def admin_mobiles(raw: str) -> frozenset[str]:
    """'+91 98470 00001, 9847000002' -> {'9847000001', '9847000002'}. Entries that are not valid Indian
    mobile numbers are left out (and reported), so a typo never matches anyone."""
    out = set()
    for entry in raw.split(","):
        digits = re.sub(r"\D", "", entry)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if re.fullmatch(r"[6-9]\d{9}", digits):
            out.add(digits)
        elif entry.strip():
            print(
                "WARNING: an ADMIN_MOBILES entry is not a valid Indian mobile number; ignored",
                file=sys.stderr,
            )
    return frozenset(out)


def _secret(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < 32:
        # Development fallback, valid until the server restarts. Production sets a real secret.
        print(f"WARNING: {name} missing or short; using a random per-process secret", file=sys.stderr)
        value = secrets.token_urlsafe(48)
    return value
