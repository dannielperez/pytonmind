"""Recorded-fixture contract tests (roadmap L3, issue #1452).

Each parsing entry point is fed a captured/documented response fixture and
checked for the correct DTO fields — replacing the hand-typed inline dicts
used elsewhere in this test suite with a durable, reviewable fixture file, so
a future response-shape change is caught against a concrete recorded payload
rather than an assumption baked into the test itself.

See ``fixtures/README.md`` for fixture provenance.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pytonmind.client import TonmindClient, identify

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_identify_parses_overview_get_fixture() -> None:
    payload = _load("overview_get.json")

    with patch("pytonmind.client.requests.get", return_value=_FakeResponse(payload)):
        device = identify("192.0.2.5")

    assert device.reachable is True
    assert device.is_tonmind is True
    assert device.serial == "TM2504SIP-S21-112"
    assert device.version == "CS20-V3.4.6N"
    assert device.uid == "00112233AABB"
    assert device.sip_status == "REG SUCCESS"


def test_get_sip_parses_sip_get_fixture() -> None:
    payload = _load("sip_get.json")
    client = TonmindClient("192.0.2.5")

    with patch.object(client, "get_config", return_value=payload["data"]):
        accounts = client.get_sip()

    assert accounts[0].user_name == "100"
    assert accounts[0].auth_id == "100"
    assert accounts[0].display_name == "Lobby"
    assert accounts[0].server_host == "192.0.2.10"
    assert accounts[0].server_port == 5060
    assert accounts[0].expire_time == 3600
    assert accounts[0].enable is True
    assert accounts[1].enable is False
