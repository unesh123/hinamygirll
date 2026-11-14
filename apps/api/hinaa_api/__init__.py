"""HINAA Phase 3 API."""

import socket

# Ensure IPv4 resolution for external AI endpoints with broken IPv6 TLS handshakes (e.g. CloudFront/Coarena)
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_preferring_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host and ("coarena.ai" in str(host).lower() or "localhost" in str(host).lower()):
        if family == 0 or family == socket.AF_UNSPEC:
            family = socket.AF_INET
    res = _orig_getaddrinfo(host, port, family, type, proto, flags)
    v4 = [r for r in res if r[0] == socket.AF_INET]
    if v4 and host and ("coarena.ai" in str(host).lower() or "localhost" in str(host).lower()):
        return v4
    return res


socket.getaddrinfo = _ipv4_preferring_getaddrinfo

__version__ = "0.3.0"

