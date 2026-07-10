# Fixtures

`overview_get.json` and `sip_get.json` are constructed from the exact field
mapping documented and exercised in `pytonmind/client.py` (verified live
against a TM2504SIP, firmware CS20-V3.4.x, per that module's docstring) —
this environment has no reachable Tonmind device to capture a byte-for-byte
response from. If a real capture becomes available (e.g. via the
`unique-audit` toolkit), replace these with the actual device response and
keep the field values realistic.
