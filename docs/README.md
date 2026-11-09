# Documentation Directory (`docs/`)

Welcome to the technical specifications and engineering documentation for the **Daily Hadith AI Agent**.

This directory serves as the durable source of truth for all architectural decisions, API contracts, empirical dataset audits, and roadmap progress tracking.

---

## Document Index

| Document | Component | Summary |
|---|---|---|
| **[`PROJECT_WORKFLOW.md`](PROJECT_WORKFLOW.md)** | **Master Architecture & Guide** | Comprehensive end-to-end system workflow, interview pitch, 4 invariants, 8 LangGraph nodes, cloud design, and interview masterclass. |
| **[`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md)** | **Project Management** | The 20-milestone engineering roadmap tracking progress, acceptance criteria, verification evidence, and next actions. |
| **[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)** | **Architecture & Continuity** | Living developer handover document capturing architecture decisions (ADRs), stack choices, invariants, and active tasks. |
| **[`RUNBOOK.md`](RUNBOOK.md)** | **Production Operations** | Comprehensive operational runbook covering live monitoring, CLI tools, manual triggers, secret rotation, and disaster recovery. |
| **[`SECURITY_AUDIT.md`](SECURITY_AUDIT.md)** | **Defensive Engineering** | Security posture report evaluating threat models, OWASP Top 10 for LLMs, constant-time verification, and container hardening. |
| **[`DEFINITION_OF_DONE.md`](DEFINITION_OF_DONE.md)** | **Quality Assurance** | The 20-point verification matrix auditing functional, architectural, safety, and testing invariants with concrete proof. |
| **[`FCM_INTEGRATION_SPIKE.md`](FCM_INTEGRATION_SPIKE.md)** | **Future Mobile Architecture** | Technical design spike evaluating Firebase Cloud Messaging (FCM), dual-payload strategy, and multi-channel notification schemas. |
| **[`API_CONTRACTS.md`](API_CONTRACTS.md)** | **External Ingestion** | Exact specifications for the official HadeethEnc REST API, dual-payload schemas, and deterministic regex reference extraction. |
| **[`SOURCE_CATALOGUE_AUDIT.md`](SOURCE_CATALOGUE_AUDIT.md)** | **Empirical Data Science** | Empirical audit of HadeethEnc's 7 root categories and 2,776+ Hadiths, establishing acceptance policies and candidate pool capacity (~913 verified Hadiths). |

---

## Architectural Principles Enforced in Docs

1. **Deterministic Precedence:** Theological source text is strictly deterministic. Probabilistic AI models are never permitted to generate, translate, or paraphrase Hadith text.
2. **Fail-Closed Gatekeeping:** Any record lacking an explicit Hadith number, approved collection attribution, or Arabic text match is rejected immediately.
3. **Daily Delivery Idempotency:** The database and scheduling layers guarantee that at most one notification is dispatched per calendar day in `Asia/Kolkata`.