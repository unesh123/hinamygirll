"""
HINAA OS — Phase 15 Tamper-Evident Cryptographic Audit Logger
Implements canonical hash-chained append-only logging, sequence monotonicity,
HMAC signing, and mathematical verification for tamper/truncation detection.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from hinaa_api.security.contracts import AuditEvent
from hinaa_api.security.secrets import get_keystore_manager
from hinaa_api.security.store import SecurityStore, get_security_store

logger = logging.getLogger(__name__)

GENESIS_PREV_HASH = "0" * 64


class AuditChainLogger:
    """
    Append-only cryptographically verifiable audit logger.
    Links each log entry to the hash of the preceding entry in an unbroken chain.
    """

    def __init__(
        self,
        store: Optional[SecurityStore] = None,
        signing_key: Optional[bytes] = None,
    ) -> None:
        self.store = store or get_security_store()
        self.keystore = get_keystore_manager()
        self.signing_key = signing_key or self.keystore.get_signing_key("audit_chain_key")
        self._lock = threading.RLock()

    def _canonical_digest(
        self,
        event_id: str,
        timestamp: float,
        tenant_id: str,
        subject_id: str,
        action: str,
        resource: str,
        decision: str,
        reason_code: str,
        prev_hash: str,
    ) -> str:
        payload = {
            "action": action,
            "decision": decision,
            "event_id": event_id,
            "prev_hash": prev_hash,
            "reason_code": reason_code,
            "resource": resource,
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "timestamp": round(timestamp, 4),
        }
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def _sign_hash(self, event_hash: str) -> str:
        return hmac.new(self.signing_key, event_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def log_event(
        self,
        tenant_id: str,
        subject_id: str,
        action: str,
        resource: str,
        decision: str,
        reason_code: str,
        event_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> AuditEvent:
        """
        Appends an event to the chain, scrubbing sensitive values and linking to the latest prev_hash.
        """
        with self._lock:
            # Scrub credentials before logging
            scrubber = self.keystore.scrubber
            clean_action = scrubber.scrub(action)
            clean_resource = scrubber.scrub(resource)
            clean_reason = scrubber.scrub(reason_code)

            evt_id = event_id or f"evt_{uuid.uuid4().hex}"
            ts = timestamp if timestamp is not None else time.time()

            # Find latest record to chain from
            latest = self.store.get_latest_audit_event()
            prev_hash = latest.event_hash if latest else GENESIS_PREV_HASH

            event_hash = self._canonical_digest(
                event_id=evt_id,
                timestamp=ts,
                tenant_id=tenant_id,
                subject_id=subject_id,
                action=clean_action,
                resource=clean_resource,
                decision=decision,
                reason_code=clean_reason,
                prev_hash=prev_hash,
            )
            sig = self._sign_hash(event_hash)

            return self.store.append_audit_event(
                event_id=evt_id,
                timestamp=ts,
                tenant_id=tenant_id,
                subject_id=subject_id,
                action=clean_action,
                resource=clean_resource,
                decision=decision,
                reason_code=clean_reason,
                prev_hash=prev_hash,
                event_hash=event_hash,
                signature=sig,
            )

    def verify_chain(self) -> Dict[str, Any]:
        """
        Verifies the full audit trail:
        - Sequence continuity (monotonic 1..N)
        - Unbroken hash chaining (prev_hash[i] == event_hash[i-1])
        - Content hash re-computation
        - Cryptographic signature check
        """
        events = self.store.get_all_audit_events_ordered()
        if not events:
            return {
                "is_valid": True,
                "total_records": 0,
                "last_sequence_id": 0,
                "errors": [],
            }

        errors: List[str] = []
        expected_prev_hash = GENESIS_PREV_HASH

        for i, ev in enumerate(events):
            # 1. Monotonic sequence verification
            expected_seq = i + 1
            if ev.sequence_id != expected_seq:
                errors.append(
                    f"Sequence discontinuity at index {i}: expected sequence_id {expected_seq}, found {ev.sequence_id}."
                )

            # 2. Hash chaining verification
            if ev.prev_hash != expected_prev_hash:
                errors.append(
                    f"Hash link broken at sequence {ev.sequence_id}: record prev_hash {ev.prev_hash} does not match expected {expected_prev_hash}."
                )

            # 3. Content digest verification
            recomputed_hash = self._canonical_digest(
                event_id=ev.event_id,
                timestamp=ev.timestamp,
                tenant_id=ev.tenant_id,
                subject_id=ev.subject_id,
                action=ev.action,
                resource=ev.resource,
                decision=ev.decision,
                reason_code=ev.reason_code,
                prev_hash=ev.prev_hash,
            )
            if recomputed_hash != ev.event_hash:
                errors.append(
                    f"Content integrity failure at sequence {ev.sequence_id}: stored event_hash {ev.event_hash} does not match recomputed {recomputed_hash}."
                )

            # 4. Signature verification
            expected_sig = self._sign_hash(ev.event_hash)
            if not hmac.compare_digest(expected_sig, ev.signature):
                errors.append(
                    f"Cryptographic signature invalid at sequence {ev.sequence_id}: signature does not match signing key."
                )

            # Advance expected prev_hash
            expected_prev_hash = ev.event_hash

        return {
            "is_valid": len(errors) == 0,
            "total_records": len(events),
            "last_sequence_id": events[-1].sequence_id if events else 0,
            "errors": errors,
        }


_global_audit_logger: Optional[AuditChainLogger] = None


def get_audit_logger(
    store: Optional[SecurityStore] = None,
    signing_key: Optional[bytes] = None,
) -> AuditChainLogger:
    global _global_audit_logger
    if store is not None or signing_key is not None:
        return AuditChainLogger(store, signing_key)
    if _global_audit_logger is None:
        _global_audit_logger = AuditChainLogger()
    return _global_audit_logger
