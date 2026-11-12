"""The admin screen asks for as many digits as the server makes, and checks that count before sending."""

import re

from app.draw.otp import CODE_DIGITS
from app.main import FRONTEND_DIR


def test_the_admin_screen_matches_the_otp_length():
    js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    run = js[js.index("admRun: function") :][:600]
    assert re.search(r"\\d\{" + str(CODE_DIGITS) + r"\}", run), "admRun checks the wrong code length"
    assert f"otpBoxes({CODE_DIGITS})" in js
