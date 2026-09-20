import ipaddress
import logging
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private and reserved networks to block for SSRF safety
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),    # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / Cloud metadata (AWS/GCP/Azure)
    ipaddress.ip_network("172.16.0.0/12"),  # Private RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),   # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),   # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"), # 6to4 Relay Anycast
    ipaddress.ip_network("192.168.0.0/16"), # Private RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),# TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"), # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),    # Multicast
    ipaddress.ip_network("240.0.0.0/4"),    # Reserved
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::1/128"),        # Loopback
    ipaddress.ip_network("fc00::/7"),       # Unique local address (ULA)
    ipaddress.ip_network("fe80::/10"),      # Link-local
    ipaddress.ip_network("ff00::/8"),       # Multicast
]

MAX_URL_LENGTH = 2048


class SSRFValidationError(Exception):
    """Raised when a URL violates SSRF safety constraints."""
    pass


def is_ip_blocked(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked/private/link-local network."""
    if ip_addr.is_private or ip_addr.is_loopback or ip_addr.is_link_local or ip_addr.is_multicast or ip_addr.is_reserved:
        return True
    for network in BLOCKED_NETWORKS:
        if ip_addr in network:
            return True
    return False


def validate_url_safety(
    url: str,
    allow_localhost: bool = False,
    resolve_dns: bool = True,
) -> Tuple[bool, Optional[str]]:
    """Validate URL scheme, structure, and check for SSRF risks.
    
    Returns:
        (is_safe, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    if len(url) > MAX_URL_LENGTH:
        return False, f"URL exceeds maximum allowed length of {MAX_URL_LENGTH} characters"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL syntax: {e}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL lacks a valid hostname"

    # Normalize hostname
    hostname_clean = hostname.lower().strip(".")

    # Direct IP address check
    try:
        ip_obj = ipaddress.ip_address(hostname_clean)
        if not allow_localhost and is_ip_blocked(ip_obj):
            return False, f"Direct IP address {hostname_clean} is a blocked/private/loopback address (SSRF protection)"
        return True, None
    except ValueError:
        # Not a literal IP address, treat as domain
        pass

    # Hostname string check
    if not allow_localhost:
        if hostname_clean in ("localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "instance-data"):
            return False, f"Hostname '{hostname_clean}' is a reserved local/metadata name"

    # DNS Resolution check (prevent DNS rebinding / internal routing)
    if resolve_dns and not allow_localhost:
        try:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            addr_info = socket.getaddrinfo(hostname_clean, port, proto=socket.IPPROTO_TCP)
            for entry in addr_info:
                sockaddr = entry[4]
                resolved_ip_str = sockaddr[0]
                resolved_ip = ipaddress.ip_address(resolved_ip_str)
                if is_ip_blocked(resolved_ip):
                    return False, f"Domain '{hostname_clean}' resolves to private/internal IP {resolved_ip_str} (SSRF protection)"
        except socket.gaierror as e:
            # DNS resolution failure will be handled by the HTTP client at fetch time
            logger.warning(f"DNS resolution warning for {hostname_clean}: {e}")
        except Exception as e:
            logger.warning(f"Error resolving DNS for safety check: {e}")

    return True, None
