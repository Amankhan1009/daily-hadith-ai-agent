# Notification Formatter Package (`src/formatter/`)

This package manages the assembly and formatting of verified Hadith notifications into Telegram-compliant HTML payloads, guaranteeing source invariance, metadata completeness, and explicit segregation of non-canonical commentary.

---

## Module Overview

| File | Purpose | Key Exports |
|---|---|---|
| **[`message.py`](message.py)** | Notification payload assembly, HTML sanitization, character boundary enforcement | `format_daily_hadith_message`, `NotificationPayload`, `escape_html` |
| **[`__init__.py`](__init__.py)** | Public package interface | Clean package exports |

---

## Architecture & Rendering Flow

```mermaid
flowchart TD
    State["Verified Hadith Record"] --> TextSanitize["HTML Entity Escaping"]
    Reflection["Validated AI Reflection"] --> Disclaim["Attach Segregated Non-Canonical Disclaimer"]
    
    TextSanitize --> CorePayload["Assemble Canonical Header & Hadith Body"]
    Disclaim --> ConditionalAppend{"Was Reflection Validated?"}
    
    ConditionalAppend -- "Yes" --> AttachReflection["Append Formatted Reflection Section"]
    ConditionalAppend -- "No" --> SkipReflection["Omit Reflection Cleanly"]
    
    AttachReflection --> LengthCheck{"Length <= 4096 Chars?"}
    SkipReflection --> LengthCheck
    
    LengthCheck -- "Exceeded" --> Abort["Raise ValueError Payload Oversized"]
    LengthCheck -- "Valid" --> PayloadReady["NotificationPayload Ready for Telegram Dispatch"]
```

---

## Invariants Enforced

1. **Sacred Text Invariance:** The core Hadith text is passed directly from the verified primary source and rendered without alteration.
2. **Mandatory Canonical Metadata:** Every notification includes the authentic collection name, reference number, authenticity grade, and canonical URL.
3. **Explicit AI Demarcation:** Any reflection is strictly segregated under `💡 Reflection & Practical Context` and labeled with: `(AI-generated educational commentary — not part of the original Hadith text)`.
4. **HTML Escaping Standard:** All dynamic user or API inputs are escaped using standard HTML entities to eliminate parsing errors in Telegram's Telegram Bot API.

