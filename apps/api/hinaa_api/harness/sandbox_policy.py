"""
HINAA Sandbox & Security Policy Engine.

Directly addresses lessons from CVE-2025-59532 / GHSA-w5fx-fh39-j5rw:
1. Model-generated cwd or paths MUST NEVER determine the security boundary.
2. Trusted runtime canonicalizes and validates all filesystem access against workspace roots.
3. Fine-grained capability scoping (filesystem, network, process, browser).
4. Network policy governance (DNS egress filtering, protocol restrictions).
5. Environment secret stripping & stdout/stderr credential masking.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from .types import CapabilityPermissions, EnvironmentState


class SandboxSecurityViolation(Exception):
    """Raised when an operation attempts to breach sandbox boundaries."""
    pass


class PolicyRejection(Exception):
    """Raised when an operation is rejected by capability permissions."""
    pass


# Patterns to redact in command outputs
_OUTPUT_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|authorization|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AIza|AKIA)[0-9A-Za-z-_]{35}\b"),
]

# Sensitive environment variable keys to strip from child processes
_SENSITIVE_ENV_KEYS = re.compile(
    r"(?i)(key|token|secret|password|auth|credential|jwt|private|cert|signature|conn_str)"
)


class SandboxPolicyEngine:
    """
    Enforces trusted boundary isolation and capability policies for agent actions.
    """

    @staticmethod
    def canonicalize_path(target_path: str) -> str:
        """Resolve symlinks, redundant slashes, and relative components."""
        return os.path.realpath(os.path.abspath(target_path))

    @classmethod
    def validate_path_containment(
        cls,
        target_path: str,
        allowed_roots: List[str],
        operation_name: str = "access",
    ) -> str:
        """
        GHSA-w5fx-fh39-j5rw hardened check.
        Ensures `target_path` strictly resolves inside one of the `allowed_roots`.
        """
        canonical_target = cls.canonicalize_path(target_path)
        canonical_roots = [cls.canonicalize_path(r) for r in allowed_roots if r]

        if not canonical_roots:
            raise SandboxSecurityViolation(f"No allowed roots configured for {operation_name}.")

        is_contained = False
        for root in canonical_roots:
            try:
                # Check cross-drive on Windows
                if os.name == "nt":
                    if os.path.splitdrive(canonical_target)[0].lower() != os.path.splitdrive(root)[0].lower():
                        continue

                rel = os.path.relpath(canonical_target, root)
                if not (rel.startswith("..") or rel == ".."):
                    is_contained = True
                    break
            except ValueError:
                # Cross-drive exception on Windows
                continue

        if not is_contained:
            raise SandboxSecurityViolation(
                f"Security boundary breach rejected ({operation_name}): path {target_path!r} "
                f"resolves to {canonical_target!r} which is outside allowed workspace roots {canonical_roots}."
            )

        return canonical_target

    @classmethod
    def assert_filesystem_read(
        cls,
        target_path: str,
        permissions: CapabilityPermissions,
        environment: EnvironmentState,
    ) -> str:
        """Verify read permission and workspace root containment."""
        if permissions.is_full_access:
            return cls.canonicalize_path(target_path)

        roots = environment.workspace_roots or permissions.filesystem_read or ["."]
        return cls.validate_path_containment(target_path, roots, "filesystem.read")

    @classmethod
    def assert_filesystem_write(
        cls,
        target_path: str,
        permissions: CapabilityPermissions,
        environment: EnvironmentState,
    ) -> str:
        """Verify write permission and workspace root containment."""
        if permissions.is_full_access:
            return cls.canonicalize_path(target_path)

        roots = environment.workspace_roots or permissions.filesystem_write or ["."]
        return cls.validate_path_containment(target_path, roots, "filesystem.write")

    @classmethod
    def assert_network_access(
        cls,
        destination_url_or_domain: str,
        permissions: CapabilityPermissions,
        environment: EnvironmentState,
    ) -> Tuple[bool, str]:
        """
        Verify network egress against capability permissions and network sandbox policy.
        """
        if permissions.is_full_access:
            return True, "Full access permitted"

        # Extract hostname
        if "://" in destination_url_or_domain:
            parsed = urlparse(destination_url_or_domain)
            domain = parsed.hostname or destination_url_or_domain
        else:
            domain = destination_url_or_domain.split(":")[0].strip()

        domain_lower = domain.lower()

        # Check network enabled
        if not permissions.network_enabled and not environment.network_policy.egress_enabled:
            raise PolicyRejection(f"Network access disabled by policy for destination: {domain}")

        # Check allowed domains
        allowed = set([d.lower() for d in permissions.network_domains + environment.network_policy.allowed_domains])
        
        # Exact or subdomain match
        matched = False
        for allowed_domain in allowed:
            if domain_lower == allowed_domain or domain_lower.endswith(f".{allowed_domain}"):
                matched = True
                break

        if not matched and allowed:
            raise PolicyRejection(
                f"Network egress to {domain!r} rejected. Allowed domains: {sorted(list(allowed))}"
            )

        return True, domain_lower

    @classmethod
    def assert_process_allowed(
        cls,
        command_name: str,
        permissions: CapabilityPermissions,
        environment: EnvironmentState,
    ) -> bool:
        """Verify executable is allowed in process policy."""
        if permissions.is_full_access:
            return True

        cmd_base = os.path.basename(command_name).lower()
        if cmd_base.endswith(".exe"):
            cmd_base = cmd_base[:-4]

        allowed_procs = set([p.lower() for p in permissions.process_types])
        if cmd_base not in allowed_procs:
            raise PolicyRejection(
                f"Process execution of {command_name!r} rejected by policy. Allowed processes: {sorted(list(allowed_procs))}"
            )
        return True

    @staticmethod
    def sanitize_output(text: str) -> str:
        """Mask credentials from command stdout/stderr."""
        if not text:
            return ""
        sanitized = text
        for pat in _OUTPUT_SECRET_PATTERNS:
            sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @staticmethod
    def strip_environment_secrets(env_dict: dict) -> dict:
        """Strip sensitive credentials before spawning child subprocesses."""
        clean = {}
        for k, v in env_dict.items():
            if not _SENSITIVE_ENV_KEYS.search(k):
                clean[k] = v
        return clean
