# LLM & Reflection Generation Package (`src/llm/`)

This package manages the generation of supplementary, educational reflections using **Groq Cloud** and `openai/gpt-oss-120b`.

---

## Module Overview

| File | Purpose | Key Exports |
|---|---|---|
| **[`prompts.py`](prompts.py)** | System prompt defining theological boundaries & negative constraints | `build_reflection_prompt`, `REFLECTION_SYSTEM_PROMPT` |
| **[`client.py`](client.py)** | Resilient Groq client with timeout, retry, and fail-safe fallback | `GroqReflectionClient`, `ReflectionResult` |
| **[`__init__.py`](__init__.py)** | Public package interface | Clean package exports |

---

## Theological Safety Invariants

```mermaid
flowchart TD
    Hadith[Deterministic Verified Hadith] --> Prompt[Strict Negative Constraint Prompt]
    Prompt --> Groq[Groq Cloud LLM]
    Groq --> Check{Generation Outcome}
    Check -- Missing Key --> Omit[ai_reflection: None | status: OMITTED]
    Check -- Network / RateLimit Failure --> Fail[ai_reflection: None | status: FAILED]
    Check -- Valid Takeaway --> Success[ai_reflection: 2-3 Bullets | status: GENERATED]
    Omit --> Pipeline[Daily Notification Pipeline]
    Fail --> Pipeline
    Success --> Pipeline
```

### Strict Negative Constraints
1. **Zero Text Paraphrasing:** The model must never re-translate, modify, or output the Hadith text.
2. **Zero Legal Rulings (No Fatwas):** The model must never formulate binding Islamic jurisprudence or halaal/haraam declarations.
3. **Segregated Presentation:** Any generated reflection is clearly demarcated under `💡 Reflection & Context` and labeled as AI-generated.
4. **Fail-Safe Delivery:** If Groq is unavailable, the system delivers the authentic Hadith on its own without interruption.