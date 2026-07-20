"""Loopback-only bind-address validation for the REST frontend.

The approved design mandates loopback-only benchmark mode (design doc
"Non-functional requirements"; `DECISION_LOG.md` D-006 for the same
principle in the core runtime). A remote-candidate/non-loopback mode is
explicitly out of scope for this milestone. This module is the single
gate that enforces it: every address the given host name resolves to must
itself be a loopback address, or the host is rejected *before* any socket
is opened.
"""

from __future__ import annotations

import ipaddress
import socket

from cavbench.gateway.errors import NonLoopbackBindError


def validate_loopback_host(host: str) -> str:
    """Return `host` unchanged if every address it resolves to is a
    loopback address (IPv4 127.0.0.0/8 or IPv6 ::1); otherwise raise
    `NonLoopbackBindError` without ever opening a socket.

    Rejects, among others: `0.0.0.0`, `::` (the unspecified/"any"
    addresses -- binding these listens on every interface, not just
    loopback), any LAN/public address, and any hostname that resolves to
    a non-loopback address (including a hostname that resolves to *both*
    a loopback and a non-loopback address -- partial loopback resolution
    is still rejected).
    """
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise NonLoopbackBindError(f"cannot resolve bind host {host!r}: {exc}") from exc

    if not infos:
        raise NonLoopbackBindError(f"bind host {host!r} resolved to no addresses")

    non_loopback: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in infos:
        raw_address = str(sockaddr[0])
        # strip IPv6 zone id (e.g. "fe80::1%en0") before parsing
        address_text = raw_address.split("%", 1)[0]
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError as exc:
            raise NonLoopbackBindError(f"bind host {host!r} resolved to unparseable address {raw_address!r}") from exc
        if not address.is_loopback:
            non_loopback.append(str(address))

    if non_loopback:
        raise NonLoopbackBindError(
            f"bind host {host!r} resolves to non-loopback address(es) {sorted(set(non_loopback))!r}; "
            "the M-GPI-1 REST frontend only serves loopback benchmark mode "
            "(e.g. '127.0.0.1', '::1', or 'localhost') -- remote-candidate mode is out of scope for this milestone"
        )

    return host
