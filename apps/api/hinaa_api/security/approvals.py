"""
HINAA OS — Phase 15 Cryptographic Human Approval Ceremony Engine
Implements parameter-bound single-use authorization tokens, anti-replay nonces,
time-bounded validity, parameter tamper detection, and Nepal commerce safe limits.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from hinaa_api.security.contracts import ApprovalCeremonyToken
from hinaa_api.security.secrets import get_keystore_manager
from hinaa_api.security.store import SecurityStore, get_security_store

logger = logging.getLogger(__name__)

# Max single Nepal commerce authorization limit (NPR 50,000 = 5,000,000 paisa)
MAX_NEPAL_COMMERCE_PAISA = 5_000_000


class ApprovalCeremonyManager:
    """
    Manages human authorization challenges and cryptographic ceremony tokens.
    Guarantees:
    - Parameter binding: Token is valid strictly for the specific parameters hashed in parameters_digest.
    - Anti-replay: Nonce is consumed atomically; second attempt is rejected.
    - Anti-tampering: Changing amount, target, or recipient breaks verification.
    - Bounded lifespan: Enforces strict TTL (default 300s).
    """

    def __init__(
        self,
        store: Optional[SecurityStore] = None,
        signing_key: Optional[bytes] = None,
    ) -> None:
        self.store = store or get_security_store()
        self.keystore = get_keystore_manager()
        self.signing_key = signing_key or self.keystore.get_signing_key("approval_ceremony_key")

    @staticmethod
    def digest_parameters(parameters: Dict[str, Any]) -> str:
        canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _sign_token(
        self,
        token_id: str,
        tenant_id: str,
        action: str,
        parameters_digest: str,
        nonce: str,
        amount_paisa: Optional[int],
        expires_at: float,
    ) -> str:
        amt_str = str(amount_paisa if amount_paisa is not None else 0)
        raw = f"{token_id}:{tenant_id}:{action}:{parameters_digest}:{nonce}:{amt_str}:{round(expires_at, 2)}"
        return hmac.new(self.signing_key, raw.encode("utf-8"), hashlib.sha256).hexdigest()

    def create_challenge(
        self,
        tenant_id: str,
        action: str,
        parameters: Dict[str, Any],
        amount_paisa: Optional[int] = None,
        ttl_seconds: float = 300.0,
    ) -> ApprovalCeremonyToken:
        """
        Creates a new pending authorization challenge for a high-impact operation.
        """
        # Nepal commerce safe limits check
        if amount_paisa is not None:
            if amount_paisa < 0:
                raise ValueError("Amount cannot be negative.")
            if amount_paisa > MAX_NEPAL_COMMERCE_PAISA:
                raise ValueError(
                    f"Amount {amount_paisa} paisa exceeds max safety limit of {MAX_NEPAL_COMMERCE_PAISA} paisa (NPR 50,000)."
                )

        token_id = f"chl_{secrets.token_hex(12)}"
        nonce = secrets.token_hex(16)
        now = time.time()
        expires_at = now + ttl_seconds
        param_digest = self.digest_parameters(parameters)

        sig = self._sign_token(
            token_id=token_id,
            tenant_id=tenant_id,
            action=action,
            parameters_digest=param_digest,
            nonce=nonce,
            amount_paisa=amount_paisa,
            expires_at=expires_at,
        )

        token = ApprovalCeremonyToken(
            token_id=token_id,
            tenant_id=tenant_id,
            action=action,
            parameters_digest=param_digest,
            nonce=nonce,
            issued_at=now,
            expires_at=expires_at,
            consumed_at=None,
            amount_paisa=amount_paisa,
            currency="NPR",
            approved_by=None,
            signature=sig,
            status="PENDING",
        )
        self.store.save_approval_token(token)
        return token

    def approve_challenge(
        self,
        token_id: str,
        approver_id: str,
        approver_role: str,
    ) -> ApprovalCeremonyToken:
        """User or Owner explicitly signs off on the pending challenge."""
        token = self.store.get_approval_token(token_id)
        if not token:
            raise KeyError(f"Approval challenge '{token_id}' not found.")

        if token.status != "PENDING":
            raise ValueError(f"Challenge '{token_id}' is already in status '{token.status}'.")

        now = time.time()
        if now > token.expires_at:
            token.status = "EXPIRED"
            self.store.save_approval_token(token)
            raise TimeoutError("Approval challenge has expired.")

        token.status = "APPROVED"
        token.approved_by = approver_id
        self.store.save_approval_token(token)
        return token

    def reject_challenge(self, token_id: str, rejecter_id: str) -> ApprovalCeremonyToken:
        token = self.store.get_approval_token(token_id)
        if not token:
            raise KeyError(f"Approval challenge '{token_id}' not found.")

        token.status = "REJECTED"
        token.approved_by = rejecter_id
        self.store.save_approval_token(token)
        return token

    def verify_and_consume(
        self,
        token_id: str,
        action: str,
        parameters: Dict[str, Any],
        tenant_id: str,
        amount_paisa: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Validates token signature, action match, parameter integrity, expiration,
        and atomically consumes the nonce.
        """
        token = self.store.get_approval_token(token_id)
        if not token:
            return False, "TOKEN_NOT_FOUND"

        # 1. Tenant binding
        if token.tenant_id != tenant_id:
            return False, "CROSS_TENANT_REPLAY_BLOCKED"

        # 2. Action binding
        if token.action != action:
            return False, "ACTION_MISMATCH"

        # 3. Status check
        if token.status == "CONSUMED":
            return False, "ALREADY_CONSUMED_REPLAY_BLOCKED"
        if token.status != "APPROVED":
            return False, f"TOKEN_NOT_APPROVED_{token.status}"

        # 4. Expiration check
        now = time.time()
        if now > token.expires_at:
            return False, "TOKEN_EXPIRED"

        # 5. Parameter hash integrity check (anti-tamper)
        current_digest = self.digest_parameters(parameters)
        if current_digest != token.parameters_digest:
            return False, "PARAMETER_TAMPERED"

        # 6. Amount integrity check
        if amount_paisa is not None and token.amount_paisa is not None:
            if amount_paisa != token.amount_paisa:
                return False, "AMOUNT_TAMPERED"

        # 7. Signature verification
        expected_sig = self._sign_token(
            token_id=token.token_id,
            tenant_id=token.tenant_id,
            action=token.action,
            parameters_digest=token.parameters_digest,
            nonce=token.nonce,
            amount_paisa=token.amount_paisa,
            expires_at=token.expires_at,
        )
        if not hmac.compare_digest(expected_sig, token.signature):
            return False, "SIGNATURE_INVALID"

        # 8. Atomic consumption (prevents concurrent replay)
        success = self.store.consume_approval_token(token_id=token.token_id, nonce=token.nonce)
        if not success:
            return False, "CONCURRENT_CONSUMPTION_BLOCKED"

        return True, "AUTHORIZED"


_global_ceremony_manager: Optional[ApprovalCeremonyManager] = None


def get_ceremony_manager(
    store: Optional[SecurityStore] = None,
    signing_key: Optional[bytes] = None,
) -> ApprovalCeremonyManager:
    global _global_ceremony_manager
    if store is not None or signing_key is not None:
        return ApprovalCeremonyManager(store, signing_key)
    if _global_ceremony_manager is None:
        _global_ceremony_manager = ApprovalCeremonyManager()
    return _global_ceremony_manager
