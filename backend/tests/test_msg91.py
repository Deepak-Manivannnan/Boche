"""The Founder's OTP goes out through MSG91's Flow API: only the code, to 91XXXXXXXXXX, success only on
{"type": "success"}. A failed send drops the code so the Admin can ask again at once."""

import pytest
from draw_support import DAY, sealed_day
from test_admin_draw import ask_otp, ready

from app.draw.otp import Msg91Sender, SmsFailed, indian_mobile


@pytest.fixture
def w(make_client):
    return sealed_day(make_client)


class FakeHttp:
    def __init__(self, status=200, answer=None):
        self.status, self.answer, self.calls = status, answer or {"type": "success", "message": "x"}, []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, body))
        return self.status, self.answer


def test_only_the_code_is_sent_to_the_flow_api_template():
    http = FakeHttp()
    Msg91Sender("KEY", "TEMPLATE", "OTP", http=http).send("+91 98765 43210", "0427", "full text, not sent")
    url, headers, body = http.calls[0]
    assert url == "https://control.msg91.com/api/v5/flow"
    assert headers["authkey"] == "KEY"
    assert body == {"template_id": "TEMPLATE", "recipients": [{"mobiles": "919876543210", "OTP": "0427"}]}


@pytest.mark.parametrize("given", ["9876543210", "+919876543210", "91 98765-43210"])
def test_mobile_numbers_are_sent_as_91_plus_ten_digits(given):
    assert indian_mobile(given) == "919876543210"


@pytest.mark.parametrize("given", ["", "12345", "+44 7700 900123"])
def test_an_invalid_founder_mobile_is_refused(given):
    with pytest.raises(SmsFailed):
        indian_mobile(given)


@pytest.mark.parametrize("status, answer", [(200, {"type": "error", "message": "bad template"}), (401, {})])
def test_msg91_errors_count_as_not_sent_even_with_http_200(status, answer):
    with pytest.raises(SmsFailed):
        Msg91Sender("KEY", "T", http=FakeHttp(status, answer)).send("9876543210", "1234", "")


def test_a_failed_sms_drops_the_code_and_lets_the_admin_retry_at_once(w):
    ready(w)
    w.state.otp_sender = Msg91Sender("KEY", "T", http=FakeHttp(200, {"type": "error"}))
    res = ask_otp(w)
    assert res.status_code == 502
    assert w.admin.get(f"/api/admin/draw-days/{DAY}").json()["otpExpiresAt"] is None
    ok = FakeHttp()
    w.state.otp_sender = Msg91Sender("KEY", "T", http=ok)
    assert ask_otp(w).status_code == 200  # no 60 s wait after a failed send
    assert len(ok.calls) == 1
