"""Unit tests for pytonmind (pure — no network)."""

from pytonmind import SipAccount, validate_multicast
from pytonmind.client import TonmindClient


def test_sip_account_provision_dict():
    acc = SipAccount(user_name="100", password="secret", server_host="192.0.2.10",
                     server_port=5060, expire_time=120)
    d = acc.as_provision_dict(index=1)
    assert d["sip.account1.user_name"] == "100"
    assert d["sip.account1.auth_id"] == "100"        # defaults to user_name
    assert d["sip.account1.display_name"] == "100"
    assert d["sip.account1.server_host"] == "192.0.2.10"
    assert d["sip.account1.expire_time"] == "120"
    assert d["sip.account1.enable"] == "1"


def test_validate_multicast_rules():
    # consecutive ports on the same address are rejected (manual §2.9)
    bad = validate_multicast([("239.255.0.1", 8000), ("239.255.0.1", 8001)])
    assert any("consecutive" in p for p in bad)
    # non-consecutive on same address is fine
    ok = validate_multicast([("239.255.0.1", 8000), ("239.255.0.1", 8002)])
    assert ok == []
    # out-of-range address + port
    probs = validate_multicast([("10.0.0.1", 500)])
    assert any("multicast range" in p for p in probs)
    assert any("port outside" in p for p in probs)


def test_get_sip_parses_accounts(monkeypatch):
    c = TonmindClient("192.0.2.5")
    monkeypatch.setattr(c, "get_config", lambda name: {
        "sip0": {"enable": "1", "username": "100", "authname": "100",
                 "displayname": "Lobby", "serveraddr": "192.0.2.10",
                 "serverport": "5060", "expires": "30"},
        "sip1": {"enable": "0", "username": "", "serveraddr": ""},
    })
    sip = c.get_sip()
    assert sip[0].user_name == "100"
    assert sip[0].server_host == "192.0.2.10"
    assert sip[0].expire_time == 30
    assert sip[0].enable is True
    assert sip[1].enable is False


def test_set_sip_server_builds_fields(monkeypatch):
    captured = {}
    c = TonmindClient("192.0.2.5")
    monkeypatch.setattr(c, "set_config", lambda name, fields: captured.update({"name": name, **fields}))
    c.set_sip_server("192.0.2.10", port=5060, account=0)
    assert captured["name"] == "sip"
    assert captured["sip0_serveraddr"] == "192.0.2.10"
    assert captured["sip0_serverport"] == "5060"
    assert captured["sip0_enable"] == "1"
