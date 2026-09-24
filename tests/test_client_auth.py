"""fetch()가 어떤 세션으로 KRX를 부르는지 (네트워크 없이)."""
from __future__ import annotations

import pytest
import requests

from krx_data_api import client
from krx_data_api.exceptions import KRXAuthError, KRXAuthRequiredError


class FakeAuth:
    """로그인할 때마다 새 세션을 내주는 KRXAuth 대역."""

    def __init__(self):
        self.logins = 0
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self.logins += 1
            self._session = requests.Session()
        return self._session

    def invalidate(self):
        self._session = None


def _fake_json(responses, seen):
    """호출마다 responses에서 하나씩 꺼냄. 'LOGOUT'이면 인증 거절을 흉내."""

    def json_data(bld, params, *, session=None, menu_id=None):
        seen.append(session)
        r = responses.pop(0)
        if r == "LOGOUT":
            raise KRXAuthRequiredError("LOGOUT")
        return r

    return json_data


def _call(**kw):
    return client.fetch("listed_stocks", **kw)


def test_default_uses_login_session_when_credentials_exist(monkeypatch):
    auth, seen = FakeAuth(), []
    monkeypatch.setattr(client, "_resolve_auth", lambda **_: auth)
    monkeypatch.setattr(client.transport, "json_data", _fake_json([{"output": []}], seen))

    _call()

    assert auth.logins == 1
    assert seen == [auth.session]  # 비로그인 헛요청 없이 첫 요청부터 로그인 세션


def test_logout_on_login_session_relogs_in_once(monkeypatch):
    auth, seen = FakeAuth(), []
    monkeypatch.setattr(client, "_resolve_auth", lambda **_: auth)
    monkeypatch.setattr(
        client.transport, "json_data", _fake_json(["LOGOUT", {"output": []}], seen)
    )

    _call()

    assert auth.logins == 2
    assert seen[0] is not seen[1]  # 끊긴 세션을 버리고 새 세션으로 재시도


def test_user_supplied_session_is_not_retried(monkeypatch):
    auth, seen = FakeAuth(), []
    monkeypatch.setattr(client, "_resolve_auth", lambda **_: auth)
    monkeypatch.setattr(client.transport, "json_data", _fake_json(["LOGOUT"], seen))
    mine = requests.Session()

    with pytest.raises(KRXAuthRequiredError):
        _call(session=mine)

    assert seen == [mine]
    assert auth.logins == 0


def test_no_credentials_falls_back_to_anonymous(monkeypatch):
    seen = []
    monkeypatch.setattr(client, "_resolve_auth", lambda **_: None)
    monkeypatch.setattr(client.transport, "json_data", _fake_json(["LOGOUT"], seen))

    with pytest.raises(KRXAuthRequiredError):
        _call()

    assert seen == [None]


def test_auth_false_skips_login(monkeypatch):
    seen = []

    def boom(**_):
        raise AssertionError("auth=False인데 로그인 시도")

    monkeypatch.setattr(client, "_resolve_auth", boom)
    monkeypatch.setattr(client.transport, "json_data", _fake_json([{"output": []}], seen))

    _call(auth=False)

    assert seen == [None]


def test_resolve_auth_required_raises_without_credentials(monkeypatch):
    from krx_data_api import auth as auth_mod

    auth_mod.reset_krx_auth()
    monkeypatch.delenv("KRX_ID", raising=False)
    monkeypatch.delenv("KRX_PW", raising=False)
    try:
        assert client._resolve_auth(required=False) is None
        with pytest.raises(KRXAuthError):
            client._resolve_auth(required=True)
    finally:
        auth_mod.reset_krx_auth()
