"""
Pydantic v2 Schemas for HadeethEnc REST API.

Provides strict structural models for list responses, detailed single-record
responses (English and Arabic), and paired candidate representations.
"""

from pydantic import BaseModel, ConfigDict, Field


class HadeethEncListItem(BaseModel):
    """A single Hadith entry from the paginated category list."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Unique HadeethEnc record ID")
    title: str = Field(description="Summary title of the Hadith")
    translations: list[str] = Field(
        default_factory=list,
        description="List of available language codes (e.g. ['ar', 'en', 'ur'])",
    )


class HadeethEncPaginationMeta(BaseModel):
    """Pagination metadata from the list endpoint."""

    model_config = ConfigDict(extra="ignore")

    current_page: str
    last_page: int
    total_items: int
    per_page: str


class HadeethEncListResponse(BaseModel):
    """Envelope returned by GET /hadeeths/list/."""

    model_config = ConfigDict(extra="ignore")

    data: list[HadeethEncListItem]
    meta: HadeethEncPaginationMeta


class HadeethEncEnglishDetail(BaseModel):
    """
    Schema for GET /hadeeths/one/?language=en&id={id}.
    Note: English payload omits the canonical 'reference' field, but includes
    embedded 'hadeeth_ar' and 'attribution_ar'.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    hadeeth: str = Field(description="Canonical English translation text")
    attribution: str = Field(description="English attribution, e.g. 'Narrated by Al-Bukhari'")
    grade: str = Field(description="Authenticity grade, e.g. 'Authentic'")
    explanation: str | None = None
    hints: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    translations: list[str] = Field(default_factory=list)

    # Embedded Arabic cross-check fields
    hadeeth_ar: str = Field(description="Arabic text embedded in the English response")
    hadeeth_intro_ar: str | None = None
    explanation_ar: str | None = None
    attribution_ar: str = Field(description="Arabic attribution, e.g. 'رواه البخاري'")
    grade_ar: str = Field(description="Arabic grade, e.g. 'صحيح'")


class HadeethEncArabicDetail(BaseModel):
    """
    Schema for GET /hadeeths/one/?language=ar&id={id}.
    Contains the authoritative 'reference' citation string.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    hadeeth: str = Field(description="Canonical Arabic text")
    attribution: str = Field(description="Arabic attribution, e.g. 'رواه البخاري'")
    grade: str = Field(description="Arabic grade, e.g. 'صحيح'")
    explanation: str | None = None
    hints: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    translations: list[str] = Field(default_factory=list)
    reference: str = Field(description="Authoritative citation with book, volume, and number")


class HadeethEncCandidatePair(BaseModel):
    """
    Encapsulates correlated English and Arabic records for a candidate Hadith ID.
    """

    model_config = ConfigDict(extra="ignore")

    source_id: str
    english: HadeethEncEnglishDetail
    arabic: HadeethEncArabicDetail
    canonical_url: str = Field(description="Official HadeethEnc browse URL")
