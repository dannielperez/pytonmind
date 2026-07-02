# pytonmind

Small Python helpers for **Tonmind** IP speakers (SIP paging / broadcast),
alongside the sibling `pyakuvox` / `pyalgo` / `pyfanvil` / `pydahua` wrappers.

Verified live against a `TM2504SIP` (firmware `CS20-V3.4.x`).

## Scope (v0.1)

- **Identify** a host as Tonmind (`identify()` — open `overview.get` CGI; serial
  `TM...` / firmware `CS...`).
- **Config get/set** via the device CGI (`/cgi-bin/CGI?config=<name>.get|.set`,
  JSON `{"result":0,"data":{...}}`): `overview`, `sip`, `sipadvanced`,
  `network`, `rtp`, `audio`, `onvif`, `autoprovision`, …
- **SIP** — `get_sip()` returns the two accounts as `SipAccount`s;
  `set_sip_server(address, port, account)` repoints registration.
- **Control API** (`/api/*`) — `play_file()`, `play_stream()`, `stop()`,
  `output()`, `sip_call()`.
- **RTP multicast validation** — `validate_multicast()` enforces the manual's
  rules (multicast range, port range, and the no-consecutive-ports-per-address
  gotcha, §2.9).
- **Provisioning** — `SipAccount.as_provision_dict()` for MAC-based auto-provision
  config (§2.11).

## Quick example

```python
from pytonmind import identify, TonmindClient

print(identify("192.0.2.5"))            # TonmindDevice(serial="TM...", version="CS...")

t = TonmindClient("192.0.2.5", "admin", "tm1234")
for i, acc in t.get_sip().items():
    print(i, acc.user_name, acc.server_host)
t.play_stream("http://host/announce.mp3")   # /api/play?action=startstream
# t.login(); t.set_sip_server("192.0.2.10")  # writes need a web login
```

## Notes

- Manual defaults: IP `192.168.5.200`, user `admin` / password `tm1234`.
- Config **reads are open**; **writes require a web login** (cookie + MD5); the
  exact login field names vary by firmware — `login()` is best-effort.
- Generic package; site inventory and credentials live in the private consumers.

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

## License

[MIT](LICENSE).
