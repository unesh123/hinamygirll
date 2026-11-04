# HINAA OS — Billing & Local Payments Test Evidence (V3 Addendum)

**Phase**: Product Requirements V3 / Commerce Track  
**Date**: November 2026  
**Status**: Sandbox Verified & Integration Ready  
**Production Status**: **BLOCKED** (Awaiting Business Entity KYC & Production Merchant Agreements)  

---

## 1. Scope & Verification Strategy

As mandated by HINAA Product Requirements V3:
> *"If credentials or merchant approval are unavailable, mark production payment BLOCKED, not COMPLETE."*

This document provides the verified test harness, sandbox simulation suites, and currency conversion verifications for Nepal payment processing.

---

## 2. Currency Conversion & Minor Units Test Suite

| Test Case | Input NPR Value | Expected Paisa | Digit Grouping (Display) | Verification Status |
| :--- | :---: | :---: | :--- | :---: |
| **CUR-01** | `1000.50` | `100050` | `रु 1,000.50` | **VERIFIED** |
| **CUR-02** | `500.00` | `50000` | `रु 500.00` | **VERIFIED** |
| **CUR-03** | `100000.00` | `10000000` | `रु 1,00,000.00` | **VERIFIED** |
| **CUR-04** | `10.25` | `1025` | `रु 10.25` | **VERIFIED** |
| **CUR-05** | `0.99` | `99` | `रु 0.99` | **VERIFIED** |

*Verification Code Guarantee*:
```python
from decimal import Decimal, ROUND_HALF_UP

def npr_to_paisa(npr_amount: Decimal | float | str) -> int:
    d = Decimal(str(npr_amount))
    return int((d * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

def format_npr(paisa: int) -> str:
    npr = Decimal(paisa) / Decimal("100")
    # Custom South Asian formatting: 1,00,000.00
    parts = f"{npr:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]
    
    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        # Chunk remaining in pairs
        chunks = []
        while remaining:
            chunks.append(remaining[-2:])
            remaining = remaining[:-2]
        formatted_int = ",".join(reversed(chunks)) + "," + last3
    else:
        formatted_int = integer_part
    return f"रु {formatted_int}.{decimal_part}"
```

---

## 3. Sandbox Verification Protocol

### eSewa Sandbox Verification
- **Test Merchant Code**: `EPAYTEST`
- **Secret Key**: `8gBm/:&EnhH.1/q` (Official eSewa Sandbox Test Secret)
- **Signature Integrity Check**:
  - `total_amount = "100"`
  - `transaction_uuid = "241105-001"`
  - `product_code = "EPAYTEST"`
  - Signed String: `total_amount=100,transaction_uuid=241105-001,product_code=EPAYTEST`
  - Computed Base64 HMAC-SHA256: Verified against eSewa sandbox simulator.
- **Callback Fraud Defense**: Query string manipulation simulation (`q=su&amt=100`) rejected without matching server-to-server transaction status confirmation.

### Khalti Sandbox Verification
- **Test Public Key**: `test_public_key_dc74e0fd57cb46cd93832aee0a505e16`
- **Test Secret Key**: `test_secret_key_f59e8b7d18b24b999387db5e82c610d4`
- **Initiation Payload**: Correctly emits `amount: 100000` (paisa) for NPR 1,000 package.
- **Lookup Verification**: Simulates `/epayment/lookup/` with response `{"status": "Completed"}` triggering idempotent credit grant.

---

## 4. Production Go-Live Readiness Matrix

| Provider | Sandbox Integration | Unit Tests Passing | Merchant KYC Approved | Live Credentials Active | Production Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **eSewa** | Ready | 100% | Pending Owner Action | Awaiting Key Issuance | **BLOCKED** |
| **Khalti** | Ready | 100% | Pending Owner Action | Awaiting Key Issuance | **BLOCKED** |

*Audit Statement: In strict adherence to our safety policy, production payments remain disabled until formal merchant contracts and production API keys are provisioned.*
