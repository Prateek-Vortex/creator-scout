from __future__ import annotations

import re
import socket

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

_STUB_RESOLUTIONS: dict[str, bool] = {}


def stub_domain_resolution(domain: str, is_valid: bool) -> None:
    """Stub a domain's resolution status for unit tests."""
    _STUB_RESOLUTIONS[domain.lower().strip()] = is_valid


def clear_stubs() -> None:
    """Clear any active stubs."""
    _STUB_RESOLUTIONS.clear()


def verify_email_format_and_domain(email: str) -> bool:
    """Verify syntax and check if domain has a valid mail exchanger (MX) or IP routing."""
    email = str(email or "").strip()
    if not email:
        return False

    if not EMAIL_PATTERN.match(email):
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False
    domain = parts[1].lower().strip()
    if not domain:
        return False

    # Check test stubs first
    if domain in _STUB_RESOLUTIONS:
        return _STUB_RESOLUTIONS[domain]

    # DNS resolving checks
    try:
        import dns.resolver
        try:
            answers = dns.resolver.resolve(domain, "MX")
            if len(answers) > 0:
                return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            pass
        except Exception:
            pass
    except ImportError:
        pass

    # Fallback: check if domain resolves via socket getaddrinfo
    try:
        socket.getaddrinfo(domain, None)
        return True
    except socket.gaierror:
        return False
