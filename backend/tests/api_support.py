"""Constants and helpers shared by the backend tests and their fixtures."""

import zlib

PAYMENT_SECRET = "test-payment-secret-0123456789abcdef"


class CodeCatcher:
    """Stands in for the SMS service: keeps every sign-in code it is asked to send."""

    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, code: str, text: str) -> None:
        self.sent.append((to, code, text))

    def code_for(self, mobile: str) -> str:
        return [code for to, code, _ in self.sent if to == mobile][-1]


def mobile_for(name: str) -> str:
    """A stable, valid 10-digit Indian mobile number for a test customer's name."""
    return f"9{zlib.crc32(name.encode()) % 10**9:09d}"


def complete_signup(client, mobile: str, name: str, age: int = 30, address=None):
    """After "Continue with Google" (or for a new number): verify `mobile` by code, then make the profile."""
    sms = client.app.state.login_sms_sender
    sent = client.post("/api/auth/otp/send", json={"mobile": mobile})
    assert sent.status_code == 200, sent.text
    verified = client.post("/api/auth/otp/verify", json={"mobile": mobile, "code": sms.code_for(mobile)})
    assert verified.status_code == 200, verified.text
    body = {"name": name, "age": age, **({"address": address} if address else {})}
    return client.post("/api/auth/signup", json=body)


def google_sign_up(client, name: str, mobile: str | None = None):
    """Sign in as the fake Google account <name>; a new customer verifies a number and creates a profile."""
    res = client.post("/api/auth/google", json={"credential": f"{name}-token-xxxxxxxxxx"})
    assert res.status_code == 200, res.text
    if "signup" in res.json():
        res = complete_signup(client, mobile or mobile_for(name), res.json()["signup"]["name"])
        assert res.status_code == 200, res.text
    return res
