"""Client for Tonmind IP speakers — verified live against a TM2504SIP
(firmware CS20-V3.4.x).

Two interfaces, both on the built-in web server:

  * **Config CGI** — ``/cgi-bin/CGI?config=<name>.get`` (GET) and
    ``?config=<name>.set`` (POST). Returns JSON
    ``{"result":0,"reason":"OK","data":{...}}`` (result 0 = OK). Config names
    seen: ``overview, sip, sipadvanced, network, networkadvanced, rtp, audio,
    autoprovision, datetime, onvif, firewall, security, httpurl, alarmin``.
    Reads are open; writes need a web login (cookie).
  * **Control API** — ``/api/play``, ``/api/output``, ``/api/relay``,
    ``/api/sipcall`` (documented on the device's own help page), e.g.
    ``/api/play?action=start&file=bell1&mode=once&volume=30`` or
    ``?action=startstream&stream=<url>`` / ``?action=stop``.

Manual defaults: IP ``192.168.5.200``, user ``admin`` / password ``tm1234``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from .sip import SipAccount

DEFAULT_IP = "192.168.5.200"
DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "tm1234"
CGI = "/cgi-bin/CGI"


class TonmindError(RuntimeError):
    pass


@dataclass
class TonmindDevice:
    host: str
    reachable: bool = False
    is_tonmind: bool = False
    serial: str = ""       # e.g. "TM2504SIP-S21-112"
    version: str = ""      # e.g. "CS20-V3.4.6N"
    uid: str = ""
    sip_status: str = ""   # sip1status, e.g. "REG SUCCESS"


def identify(host: str, *, timeout: float = 6.0, verify_ssl: bool = False) -> TonmindDevice:
    """Fingerprint via the open ``overview.get`` CGI (serial ``TM...`` = Tonmind)."""
    dev = TonmindDevice(host=host)
    try:
        r = requests.get(f"http://{host}{CGI}", params={"config": "overview.get",
                         "t": int(time.time())}, timeout=timeout, verify=verify_ssl)
    except requests.RequestException:
        return dev
    dev.reachable = True
    try:
        d = r.json().get("data") or {}
    except ValueError:
        return dev
    dev.serial = d.get("serialnumber", "")
    dev.version = d.get("version", "")
    dev.uid = d.get("uid", "")
    dev.sip_status = d.get("sip1status", "")
    dev.is_tonmind = dev.serial.upper().startswith("TM") or dev.version.upper().startswith("CS")
    return dev


class TonmindClient:
    """Client for one Tonmind speaker (config CGI + control API).

    Usage::

        t = TonmindClient("192.0.2.5", "admin", "tm1234")
        t.overview()["serialnumber"]
        t.get_sip()                       # {0: SipAccount(...), 1: SipAccount(...)}
        t.play_stream("http://host/stream.mp3")
    """

    def __init__(self, host: str, username: str = DEFAULT_USER,
                 password: str = DEFAULT_PASSWORD, *, use_ssl: bool = False,
                 verify_ssl: bool = False, timeout: float = 10.0) -> None:
        self.host = host
        self._scheme = "https" if use_ssl else "http"
        self._timeout = timeout
        self._user = username
        self._password = password
        self._s = requests.Session()
        self._s.verify = verify_ssl

    @property
    def base_url(self) -> str:
        return f"{self._scheme}://{self.host}"

    # ── config CGI ──────────────────────────────────────────────────
    def get_config(self, name: str) -> dict:
        """GET ``?config=<name>.get`` → the ``data`` object. Raises on non-zero."""
        r = self._s.get(f"{self.base_url}{CGI}",
                        params={"config": f"{name}.get", "t": int(time.time())},
                        timeout=self._timeout)
        try:
            j = r.json()
        except ValueError as e:
            raise TonmindError(f"{self.host}: {name}.get non-JSON ({r.status_code})") from e
        if j.get("result") not in (0, "0"):
            raise TonmindError(f"{self.host}: {name}.get result={j.get('result')} {j.get('reason')}")
        return j.get("data") or {}

    def set_config(self, name: str, fields: dict[str, str]) -> dict:
        """POST ``?config=<name>.set`` with ``fields``. Needs a web login on
        most firmware; call :meth:`login` first if writes return an auth error."""
        r = self._s.post(f"{self.base_url}{CGI}", params={"config": f"{name}.set"},
                         data={k: str(v) for k, v in fields.items()}, timeout=self._timeout)
        try:
            j = r.json()
        except ValueError as e:
            raise TonmindError(f"{self.host}: {name}.set non-JSON ({r.status_code})") from e
        if j.get("result") not in (0, "0"):
            raise TonmindError(f"{self.host}: {name}.set result={j.get('result')} {j.get('reason')}")
        return j

    def login(self) -> None:
        """Best-effort web login (sets the session cookie needed for writes).

        The device uses a cookie + MD5 scheme; exact field names vary by
        firmware. Reads (:meth:`get_config`) work without it.
        """
        import hashlib
        pw_md5 = hashlib.md5(self._password.encode()).hexdigest()
        self._s.post(f"{self.base_url}{CGI}", params={"config": "login.set"},
                     data={"username": self._user, "password": pw_md5},
                     timeout=self._timeout)

    # ── device info ─────────────────────────────────────────────────
    def overview(self) -> dict:
        return self.get_config("overview")

    # ── SIP ─────────────────────────────────────────────────────────
    def get_sip(self) -> dict[int, SipAccount]:
        """Return the two SIP accounts (index 0/1) parsed from ``sip.get``."""
        data = self.get_config("sip")
        out: dict[int, SipAccount] = {}
        for i in (0, 1):
            s = data.get(f"sip{i}")
            if not isinstance(s, dict):
                continue
            out[i] = SipAccount(
                user_name=s.get("username", ""),
                auth_id=s.get("authname", ""),
                display_name=s.get("displayname", ""),
                server_host=s.get("serveraddr", ""),
                server_port=int(s.get("serverport") or 5060),
                expire_time=int(s.get("expires") or 3600),
                enable=str(s.get("enable", "0")) == "1",
            )
        return out

    # Fields the firmware's ``sip.set`` echoes back verbatim; we preserve them
    # on a server-only change so a full-replace write does not blank them.
    _SIP_PRESERVE = ("protocol", "displayname", "authname", "username",
                     "expires", "regtry", "keepalive", "buttondest", "ringtone",
                     "autoanswer", "delaytime", "proxyenable", "proxyaddr",
                     "proxyport", "nattype", "stunserver", "stunport",
                     "turnserver", "turnport", "callduration")

    def set_sip_server(self, address: str, port: int = 5060, account: int = 0,
                       *, password: str | None = None) -> dict:
        """Point a SIP account's server at ``address`` (login first for writes).

        The firmware's ``sip.set`` is a **full-replace** keyed by ``id`` — it
        does NOT do per-field patching, so any field omitted from the POST is
        cleared. ``sip.get`` also **masks the SIP password** (returns ``""``),
        so a naive read-modify-write silently wipes the account's auth secret
        and the speaker drops to REG-FAIL. We therefore re-supply every field
        read back from the device and REQUIRE ``password`` unless the device
        genuinely has none. Pass the ext's SIP secret to change the server.
        """
        cur = self.get_config("sip").get(f"sip{account}") or {}
        stored_pw = cur.get("password") or ""
        pw = password if password is not None else stored_pw
        if not pw:
            raise TonmindError(
                f"{self.host}: refusing to write sip{account} with an empty "
                "password — sip.get masks the secret, so a server-only change "
                "needs the ext's SIP secret passed as password=...")
        fields = {"id": account, "enable": 1, "serveraddr": address,
                  "serverport": str(port), "password": pw}
        for k in self._SIP_PRESERVE:
            if k in cur and cur[k] != "":
                fields[k] = cur[k]
        return self.set_config("sip", fields)

    # ── control API (/api/*) ────────────────────────────────────────
    def _api(self, path: str, **params) -> requests.Response:
        return self._s.get(f"{self.base_url}/api/{path}", params=params, timeout=self._timeout)

    def play_file(self, file: str, mode: str = "once", count: int = 1,
                  volume: int | None = None) -> None:
        p = {"action": "start", "file": file, "mode": mode, "count": count}
        if volume is not None:
            p["volume"] = volume
        self._api("play", **p)

    def play_stream(self, url: str) -> None:
        self._api("play", action="startstream", stream=url)

    def stop(self) -> None:
        self._api("play", action="stop")
        self._api("play", action="stopstream")

    def output(self, on: bool, duration: int | None = None) -> None:
        p = {"action": "on" if on else "off"}
        if on and duration is not None:
            p["duration"] = duration
        self._api("output", **p)

    def sip_call(self, dest: str) -> None:
        self._api("sipcall", dest=dest)
