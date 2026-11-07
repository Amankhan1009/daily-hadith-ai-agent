# HadeethEnc Integration Package (`src/hadeethenc/`)

This package provides a typed HTTP client and deterministic invariant verification engine for the official [HadeethEnc REST API](https://hadeethenc.com/api/v1/).

---

## Module Overview

| File | Purpose | Key Exports |
|---|---|---|
| **[`client.py`](client.py)** | Resilient HTTP client using `httpx` with timeout management and retries | `HadeethEncClient`, domain exceptions |
| **[`schemas.py`](schemas.py)** | Strict Pydantic v2 data models for API list and detail payloads | `HadeethEncListResponse`, `HadeethEncEnglishDetail`, `HadeethEncArabicDetail`, `HadeethEncCandidatePair` |
| **[`verifier.py`](verifier.py)** | Deterministic cross-payload validator and regex citation parser | `verify_candidate_pair()`, `VerificationResult` |
| **[`__init__.py`](__init__.py)** | Public package interface | Unified façade for external modules |

---

## Deterministic Verification Invariants

```mermaid
flowchart TD
    A["Fetch English Detail"] --> B["Fetch Arabic Counterpart"]
    B --> C{"ID Invariance: en.id == ar.id?"}
    C -- No --> Fail1["Reject: ERR_RECORD_MISMATCH"]
    C -- Yes --> D{"Arabic Text Identity: en.hadeeth_ar == ar.hadeeth?"}
    D -- No --> Fail2["Reject: ERR_RECORD_MISMATCH"]
    D -- Yes --> E{"Attribution Match: en.attribution_ar == ar.attribution?"}
    E -- No --> Fail3["Reject: ERR_ATTRIBUTION_MISMATCH"]
    E -- Yes --> F{"Approved Collection & Number?"}
    F -- No --> Fail4["Reject: ERR_UNAPPROVED_COLLECTION / ERR_AMBIGUOUS_CITATION"]
    F -- Yes --> Pass["VERIFIED: Return Canonical Hadith Number"]
```

### Approved Collection Regex Grammar
- **Sahih al-Bukhari:** `صحيح البخاري(?:\s*\(\d+/\s*\d+\))?\s*\((\d+)\)`
- **Sahih Muslim:** `صحيح مسلم(?:\s*\(\d+/\s*\d+\))?\s*\((\d+)\)`
- **Agreed Upon:** Both collections matched or explicitly attributed with `متفق عليه`.