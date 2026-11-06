# Guardrails AI & Reflection Safety Package (`src/guardrails/`)

This package enforces deterministic validation and theological guardrails over LLM-generated reflections before they are permitted into the daily notification payload.

---

## Module Overview

| File | Purpose | Key Exports |
|---|---|---|
| **[`rules.py`](rules.py)** | Deterministic boundary regex patterns, word limits, and prohibited decree vocabularies | `PROHIBITED_LEGAL_PATTERNS`, `PROHIBITED_CITATION_PATTERNS`, `MAX_REFLECTION_WORDS` |
| **[`validator.py`](validator.py)** | Pure, testable validation engine verifying structural and domain rules | `ReflectionValidator`, `GuardrailResult`, `validate_reflection` |
| **[`__init__.py`](__init__.py)** | Public package interface | Clean package exports |

---

## Guardrail Architecture & Flow

```mermaid
flowchart TD
    LLM[Raw Groq Reflection] --> EmptyCheck{Is Non-Empty?}
    EmptyCheck -- No --> RejectEmpty[Status: REJECTED | ERR_EMPTY_REFLECTION]
    EmptyCheck -- Yes --> WordCheck{Word Count: 8 to 150?}
    
    WordCheck -- No --> RejectWord[Status: REJECTED | ERR_REFLECTION_TOO_LONG / SHORT]
    WordCheck -- Yes --> BulletCheck{Has Bullet Structure?}
    
    BulletCheck -- No --> RejectBullet[Status: REJECTED | ERR_MISSING_BULLET_STRUCTURE]
    BulletCheck -- Yes --> FatwaCheck{Contains Fatwa / Decree?}
    
    FatwaCheck -- Yes --> RejectFatwa[Status: REJECTED | ERR_THEOLOGICAL_DECREE]
    FatwaCheck -- No --> CitationCheck{Contains Fabricated Citation?}
    
    CitationCheck -- Yes --> RejectCite[Status: REJECTED | ERR_UNAUTHORIZED_CITATION]
    CitationCheck -- No --> LeakageCheck{Repeats Hadith Text?}
    
    LeakageCheck -- Yes --> RejectLeak[Status: REJECTED | ERR_HADITH_TEXT_LEAKAGE]
    LeakageCheck -- No --> Passed[Status: PASSED | Allowed in Telegram Dispatch]

    RejectEmpty --> FailClosed[Omit AI Reflection & Deliver Pure Hadith Alone]
    RejectWord --> FailClosed
    RejectBullet --> FailClosed
    RejectFatwa --> FailClosed
    RejectCite --> FailClosed
    RejectLeak --> FailClosed
```

---

## Safety Invariants Enforced

1. **Zero Theological Decrees:** The model must never formulate binding Islamic jurisprudence (e.g. declaring something explicitly Fard, Haram, or Halal as a decree).
2. **Zero Citation Fabrication:** The reflection cannot reference volume/page numbers or invent Isnad narrators. Citations belong strictly in the verified metadata header.
3. **Sacred Text Invariance:** The model cannot copy or re-translate 8+ consecutive words from the original Hadith text.
4. **Fail-Closed Fallback:** If any rail is violated, the system omits the commentary cleanly (`ai_reflection_status: OMITTED_GUARDRAIL_FAILED`) and delivers the verified Hadith alone.

