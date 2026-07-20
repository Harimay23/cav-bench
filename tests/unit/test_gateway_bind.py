"""Loopback-only bind-address validation tests (M-GPI-1 review follow-up).

`socket.getaddrinfo` calls for arbitrary hostnames are mocked for
determinism (no live DNS dependency in CI); the loopback-literal cases
(`127.0.0.1`, `::1`, `localhost`) resolve via the real resolver, since
those never touch the network.
"""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from cavbench.gateway.bind import validate_loopback_host
from cavbench.gateway.core import GatewaySession
from cavbench.gateway.errors import NonLoopbackBindError
from cavbench.gateway.rest import GatewayRestServer
from cavbench.scenarios.loader import load_builtin_pack

PACK = load_builtin_pack("core-v1")


def _addrinfo(*sockaddrs: tuple[int, str]) -> list[tuple[int, int, int, str, tuple]]:
    result = []
    for family, address in sockaddrs:
        sockaddr = (address, 0) if family == socket.AF_INET else (address, 0, 0, 0)
        result.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
    return result


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_allowed_loopback_hosts(host: str) -> None:
    assert validate_loopback_host(host) == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::"])
def test_rejects_unspecified_any_address(host: str) -> None:
    with pytest.raises(NonLoopbackBindError):
        validate_loopback_host(host)


@pytest.mark.parametrize("host", ["8.8.8.8", "192.168.1.5", "10.0.0.1", "203.0.113.7"])
def test_rejects_non_loopback_literal_addresses(host: str) -> None:
    with pytest.raises(NonLoopbackBindError):
        validate_loopback_host(host)


def test_rejects_hostname_resolving_to_a_non_loopback_address() -> None:
    with patch("socket.getaddrinfo", return_value=_addrinfo((socket.AF_INET, "93.184.216.34"))):
        with pytest.raises(NonLoopbackBindError):
            validate_loopback_host("lan-host.example")


def test_rejects_hostname_with_mixed_loopback_and_non_loopback_resolution() -> None:
    """A hostname that resolves to *both* a loopback and a non-loopback
    address is still rejected -- partial loopback resolution is not
    sufficient, since the socket layer could bind either."""
    with patch(
        "socket.getaddrinfo",
        return_value=_addrinfo((socket.AF_INET, "127.0.0.1"), (socket.AF_INET, "203.0.113.9")),
    ):
        with pytest.raises(NonLoopbackBindError):
            validate_loopback_host("mixed-host.example")


def test_allows_hostname_resolving_only_to_loopback_addresses() -> None:
    with patch(
        "socket.getaddrinfo",
        return_value=_addrinfo((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")),
    ):
        assert validate_loopback_host("loopback-alias.example") == "loopback-alias.example"


def test_unresolvable_hostname_is_rejected_not_silently_ignored() -> None:
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("name or service not known")):
        with pytest.raises(NonLoopbackBindError):
            validate_loopback_host("this-host-does-not-resolve.invalid")


def test_gateway_rest_server_rejects_non_loopback_host_before_binding_a_socket() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="bind-reject")
    with pytest.raises(NonLoopbackBindError):
        GatewayRestServer(session, host="0.0.0.0")


def test_gateway_rest_server_accepts_loopback_host() -> None:
    scenario = PACK.get("HP-01")
    session = GatewaySession.start(scenario, seed=0, run_id="bind-accept")
    with GatewayRestServer(session, host="127.0.0.1") as server:
        assert server.base_url.startswith("http://127.0.0.1:")
