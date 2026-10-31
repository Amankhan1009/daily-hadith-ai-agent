# Source Catalogue Audit & Acceptance Specification

> **Durable Technical Specification**  
> *Component:* Source Ingestion, Empirical Data Audit, and Candidate Selection Policy  
> *Milestone:* Milestone 06 — Source Catalogue Audit  
> *Date:* 2026-10-31  

---

## 1. Executive Summary & Purpose

Before building the daily retrieval and scheduling pipeline, an empirical audit of the **HadeethEnc** catalogue was conducted to evaluate:
1. **Thematic Taxonomy & Volume:** The breadth and depth of categories available for daily reminders.
2. **Collection Distribution:** The real-world proportion of *Sahih al-Bukhari*, *Sahih Muslim*, and *Agreed Upon* narrations versus unapproved compilations.
3. **Citation Formatting Patterns:** The structural variance between precision-cited Hadiths and bibliographic-only entries.
4. **Candidate Pool Capacity:** The viable number of unique, strictly verified Hadiths available for long-term daily delivery.

---

## 2. HadeethEnc Catalogue Taxonomy

Empirical querying of the official `/categories/roots/` endpoint revealed **7 root categories** encompassing **452 subcategories** and **2,776+ total Hadiths**:

| Category ID | Root Category Title | Total Hadiths | Suitability for Daily Delivery | Priority Tier |
|---|---|---|---|---|
| **5** | **Virtues and Manners (*Fada’il wa al-Adab*)** | **751** | **Highest:** Character, kindness, patience, dhikr, etiquette | **Tier 1 (Primary)** |
| **1** | **The Noble Qur’an and Qur’anic Sciences** | **81** | **High:** Virtues of recitation, memorization, and teaching | **Tier 1 (Core)** |
| **3** | **The Creed (*’Aqeedah*)** | **471** | **High:** Foundational belief, trust in Allah, divine names | **Tier 1 (Core)** |
| **7** | **Seerah and History** | **213** | **Medium-High:** Life of the Prophet ﷺ and companions | **Tier 2 (Secondary)** |
| **6** | **Da‘wah and Hisbah** | **100** | **Medium:** Calling to good, community responsibility | **Tier 2 (Secondary)** |
| **4** | **Jurisprudence (*Fiqh*)** | **1,150** | **Selective:** Worship (Salah/Sawm) suitable; legal rulings excluded | **Tier 3 (Selective)** |
| **2** | **The Hadith and Hadith Sciences** | **10** | **Low:** Technical methodology and terminology | **Excluded** |

---

## 3. Empirical Audit Findings

Two representative Tier-1 categories were audited using live API sampling and evaluated against our deterministic verifier (`verify_candidate_pair`):

### 3.1 Category 5: Virtues and Manners (Sample: 20 records)
- **Passed (Strictly Verified):** **15 / 20 (75.0%)**
  - *Agreed Upon (Al-Bukhari & Muslim):* 7 (35.0%)
  - *Sahih Muslim:* 6 (30.0%)
  - *Sahih al-Bukhari:* 2 (10.0%)
- **Rejected (Fail-Closed):** **5 / 20 (25.0%)**
  - *ERR_UNAPPROVED_COLLECTION:* 5 (100% of rejections were narrations from *Jami` at-Tirmidhi*, *Sunan Abi Dawud*, or *Sunan Ibn Majah*).
  - *Text Corruption / Arabic Mismatches:* 0 (0.0%).

### 3.2 Category 1: The Noble Qur’an (Sample: 15 records)
- **Passed (Strictly Verified):** **9 / 15 (60.0%)**
  - *Agreed Upon (Al-Bukhari & Muslim):* 5 (33.3%)
  - *Sahih al-Bukhari:* 2 (13.3%)
  - *Sahih Muslim:* 2 (13.3%)
- **Rejected (Fail-Closed):** **6 / 15 (40.0%)**
  - *ERR_UNAPPROVED_COLLECTION:* 3 (Narrations from *At-Tirmidhi* and *Abu Dawud*).
  - *ERR_AMBIGUOUS_CITATION:* 3 (Bibliographic book-edition listings without specific Hadith numbers).

---

## 4. Key Architectural Discovery: Citation Granularity

The audit exposed two distinct citation structures entered by HadeethEnc editors:

1. **Precision-Cited Records (Type A):**
   - The Arabic reference includes book, volume, page, and canonical Hadith number:
     e.g., `صحيح البخاري (6/ 192) (5027)` or `صحيح مسلم (1/ 545) (791)`.
   - **System Policy:** Fully accepted. Enables clear user-facing citations: `Sahih al-Bukhari #5027`.

2. **Bibliographic-Only Records (Type B):**
   - The Arabic reference lists print details without a Hadith number:
     e.g., `صحيح البخاري –الجامع الصحيح- دار طوق النجاة، 1422هـ`.
   - **System Policy:** **Strict Fail-Closed Rejection.** Any candidate with `hadith_number is None` is rejected with `ERR_AMBIGUOUS_CITATION`. Telegram notifications must never display placeholder or missing citation numbers (`#None`).

---

## 5. Candidate Pool Capacity & Sustainability

Evaluating the Tier-1 candidate pool under strict verification:

| Category | Total Corpus | Estimated Acceptance Rate | Estimated Verified Pool |
|---|---|---|---|
| **Category 5 (Virtues & Manners)** | 751 | ~75% | ~560 Hadiths |
| **Category 1 (The Noble Qur’an)** | 81 | ~60% | ~48 Hadiths |
| **Category 3 (The Creed)** | 471 | ~65% | ~305 Hadiths |
| **Total Tier-1 Candidate Pool** | **1,303** | **~70%** | **~913 Verified Hadiths** |

> [!NOTE]
> **Long-Term Sustainability:** A verified pool of **~913 Hadiths** provides **approximately 2.5 years** of daily, non-repeating delivery at 1 Hadith per day.

---

## 6. Catalogue Acceptance & Ingestion Rules for Daily Agent

When the daily scheduling worker queries HadeethEnc:
1. **Target Rotation:** The ingestion engine selects candidates rotating across **Tier 1 categories** (`5`, `1`, `3`).
2. **Deterministic Pre-Filter:** Every candidate must pass `verify_candidate_pair()`:
   - Identical English-embedded and Arabic payload texts.
   - Identical attribution strings.
   - Verified membership in *Sahih al-Bukhari*, *Sahih Muslim*, or *Agreed Upon*.
   - Non-null, regex-parsed canonical Hadith number.
3. **Fail-Closed Fallback:** If a candidate fails any invariant, it is logged with its rejection error code, flagged in the database as rejected, and the pipeline immediately evaluates the next candidate in the queue.
