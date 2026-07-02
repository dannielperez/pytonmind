"""Tonmind SIP account model + RTP-multicast helpers.

From the Tonmind IP Speaker User Manual: each speaker has **two** SIP accounts
with these fields (§2.4.1 SIP Set):

    User Name, Auth ID, Password, Display Name, Server Host, Server Port (5060),
    Outbound Proxy, Expire Time

and supports up to 10 RTP multicast addresses (§2.9) with an important gotcha:
ports for the *same* multicast address must NOT be consecutive.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SipAccount:
    """One Tonmind SIP account (index 1 or 2)."""

    user_name: str = ""        # SIP user account
    auth_id: str = ""          # authentication ID
    password: str = ""
    display_name: str = ""
    server_host: str = ""      # SIP server address
    server_port: int = 5060
    outbound_proxy: str = ""   # for NAT/firewall traversal
    expire_time: int = 3600    # registration expiry (s)
    enable: bool = True

    def as_provision_dict(self, index: int = 1) -> dict[str, str]:
        """Flatten to per-account provisioning keys (index 1 or 2).

        Key names follow the manual's field semantics; confirm the exact
        provisioning template against a device/sample before bulk rollout.
        """
        p = f"sip.account{index}."
        return {
            p + "enable": "1" if self.enable else "0",
            p + "user_name": self.user_name,
            p + "auth_id": self.auth_id or self.user_name,
            p + "password": self.password,
            p + "display_name": self.display_name or self.user_name,
            p + "server_host": self.server_host,
            p + "server_port": str(self.server_port),
            p + "outbound_proxy": self.outbound_proxy,
            p + "expire_time": str(self.expire_time),
        }


def validate_multicast(addr_ports: list[tuple[str, int]]) -> list[str]:
    """Validate RTP multicast address/port pairs against the manual's rules.

    Returns a list of human-readable problems (empty = OK):

    * address must be in 224.0.0.0–239.255.255.255
    * port must be 1024–65536
    * ports for the *same* address must not be consecutive (manual §2.9)
    """
    problems: list[str] = []
    by_addr: dict[str, list[int]] = {}
    for addr, port in addr_ports:
        try:
            first = int(addr.split(".")[0])
        except (ValueError, IndexError):
            problems.append(f"{addr}: not an IPv4 address")
            continue
        if not (224 <= first <= 239):
            problems.append(f"{addr}: outside multicast range 224.0.0.0-239.255.255.255")
        if not (1024 <= port <= 65536):
            problems.append(f"{addr}:{port}: port outside 1024-65536")
        by_addr.setdefault(addr, []).append(port)
    for addr, ports in by_addr.items():
        s = sorted(ports)
        for a, b in zip(s, s[1:]):
            if b - a == 1:
                problems.append(f"{addr}: consecutive ports {a},{b} not allowed "
                                "(use non-consecutive ports for the same address)")
    return problems
