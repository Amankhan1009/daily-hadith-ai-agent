# Documentation Directory (`docs/`)

Welcome to the technical specifications and engineering documentation for the **Daily Hadith AI Agent**.

This directory serves as the durable source of truth for all architectural decisions, API contracts, empirical dataset audits, and roadmap progress tracking.

---

## Document Index

| Document | Component | Summary |
|---|---|---|
| **[`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md)** | **Project Management** | The 20-milestone engineering roadmap tracking progress, acceptance criteria, verification evidence, and next actions. |
| **[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)** | **Architecture & Continuity** | Living developer handover document capturing architecture decisions (ADRs), stack choices, invariants, and active tasks. |
| **[`API_CONTRACTS.md`](API_CONTRACTS.md)** | **External Ingestion** | Exact specifications for the official HadeethEnc REST API, dual-payload schemas, and deterministic regex reference extraction. |
| **[`SOURCE_CATALOGUE_AUDIT.md`](SOURCE_CATALOGUE_AUDIT.md)** | **Empirical Data Science** | Empirical audit of HadeethEnc's 7 root categories and 2,776+ Hadiths, establishing acceptance policies and candidate pool capacity (~913 verified Hadiths). |

---

## Architectural Principles Enforced in Docs

1. **Deterministic Precedence:** Theological source text is strictly deterministic. Probabilistic AI models are never permitted to generate, translate, or paraphrase Hadith text.
2. **Fail-Closed Gatekeeping:** Any record lacking an explicit Hadith number, approved collection attribution, or Arabic text match is rejected immediately.
3. **Daily Delivery Idempotency:** The database and scheduling layers guarantee that at most one notification is dispatched per calendar day in `Asia/Kolkata`.