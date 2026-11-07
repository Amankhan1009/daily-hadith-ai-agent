"""
Automated Unit and Integration Tests for HadeethEnc Client & Invariant Verifier.
"""

import httpx
import pytest

from src.hadeethenc import (
    HadeethEncArabicDetail,
    HadeethEncCandidatePair,
    HadeethEncClient,
    HadeethEncEnglishDetail,
    HadeethEncNetworkError,
    HadeethEncNotFoundError,
    HadeethEncResponseError,
    verify_candidate_pair,
)

# ------------------------------------------------------------------------------
# Mock Data Fixtures
# ------------------------------------------------------------------------------

MOCK_ENGLISH_PAYLOAD = {
    "id": "5913",
    "title": "The best of you are those who learn the Qur'an and teach it",
    "hadeeth": "The Prophet said: The best of you are those who learn the Qur'an and teach it.",
    "attribution": "Narrated by Al-Bukhāri",
    "grade": "Authentic",
    "explanation": "Explanation text...",
    "hints": ["Hint 1"],
    "categories": ["1"],
    "translations": ["en", "ar"],
    "hadeeth_ar": "«خيركم من تعلم القرآن وعلمه»",
    "attribution_ar": "رواه البخاري",
    "grade_ar": "صحيح",
}

MOCK_ARABIC_PAYLOAD = {
    "id": "5913",
    "title": "خيركم من تعلم القرآن وعلمه",
    "hadeeth": "«خيركم من تعلم القرآن وعلمه»",
    "attribution": "رواه البخاري",
    "grade": "صحيح",
    "explanation": "شرح الحديث...",
    "hints": ["فائدة"],
    "categories": ["1"],
    "translations": ["en", "ar"],
    "reference": "صحيح البخاري (6/ 192) (5027).\nفتح الباري (1/ 374).",
}

MOCK_LIST_PAYLOAD = {
    "data": [
        {"id": "5913", "title": "The best of you...", "translations": ["en", "ar"]},
        {"id": "5907", "title": "Keep reciting...", "translations": ["en", "ar"]},
    ],
    "meta": {"current_page": "1", "last_page": 5, "total_items": 10, "per_page": "2"},
}


# ------------------------------------------------------------------------------
# HTTP Client Tests (Using httpx.MockTransport)
# ------------------------------------------------------------------------------


def test_client_get_hadiths_by_category_success():
    """Verify listing Hadiths returns a valid, typed HadeethEncListResponse."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "hadeeths/list/" in str(request.url)
        return httpx.Response(200, json=MOCK_LIST_PAYLOAD)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        result = client.get_hadiths_by_category(category_id=1, page=1, per_page=2)

        assert len(result.data) == 2
        assert result.data[0].id == "5913"
        assert result.meta.total_items == 10


def test_client_get_candidate_pair_success():
    """Verify fetching both records generates a synchronized HadeethEncCandidatePair."""

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("language") == "en":
            return httpx.Response(200, json=MOCK_ENGLISH_PAYLOAD)
        if params.get("language") == "ar":
            return httpx.Response(200, json=MOCK_ARABIC_PAYLOAD)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        pair = client.get_candidate_pair("5913")

        assert pair.source_id == "5913"
        assert pair.english.attribution == "Narrated by Al-Bukhāri"
        assert "5027" in pair.arabic.reference
        assert pair.canonical_url == "https://hadeethenc.com/en/browse/hadith/5913"


def test_client_404_raises_not_found():
    """Verify HTTP 404 is mapped to HadeethEncNotFoundError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        with pytest.raises(HadeethEncNotFoundError):
            client.get_english_hadith("999999")


def test_client_empty_response_raises_not_found():
    """Verify HTTP 200 with empty body/string is treated as Not Found."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json="")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        with pytest.raises(HadeethEncNotFoundError):
            client.get_english_hadith("999999")


def test_client_timeout_raises_network_error():
    """Verify request timeouts map cleanly to HadeethEncNetworkError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        with pytest.raises(HadeethEncNetworkError) as exc_info:
            client.get_english_hadith("5913")
        assert "timed out" in str(exc_info.value).lower()


def test_client_500_raises_response_error():
    """Verify upstream HTTP 500 errors map to HadeethEncResponseError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        with pytest.raises(HadeethEncResponseError) as exc_info:
            client.get_english_hadith("5913")
        assert "HTTP 500" in str(exc_info.value)


def test_client_malformed_payload_raises_response_error():
    """Verify unexpected payload structure triggers HadeethEncResponseError."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Missing required fields like 'hadeeth', 'attribution'
        return httpx.Response(200, json={"id": "5913", "title": "Incomplete"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = HadeethEncClient(client=http_client)
        with pytest.raises(HadeethEncResponseError) as exc_info:
            client.get_english_hadith("5913")
        assert "Malformed English payload" in str(exc_info.value)


# ------------------------------------------------------------------------------
# Deterministic Verifier Invariant Tests
# ------------------------------------------------------------------------------


def create_mock_pair(
    en_arabic_text: str = "«خيركم من تعلم القرآن وعلمه»",
    ar_arabic_text: str = "«خيركم من تعلم القرآن وعلمه»",
    en_attr_ar: str = "رواه البخاري",
    ar_attr_ar: str = "رواه البخاري",
    reference_text: str = "صحيح البخاري (6/ 192) (5027)",
) -> HadeethEncCandidatePair:
    """Helper to assemble test candidate pairs with specific field overrides."""
    en_dict = dict(MOCK_ENGLISH_PAYLOAD)
    en_dict["hadeeth_ar"] = en_arabic_text
    en_dict["attribution_ar"] = en_attr_ar

    ar_dict = dict(MOCK_ARABIC_PAYLOAD)
    ar_dict["hadeeth"] = ar_arabic_text
    ar_dict["attribution"] = ar_attr_ar
    ar_dict["reference"] = reference_text

    return HadeethEncCandidatePair(
        source_id="5913",
        english=HadeethEncEnglishDetail.model_validate(en_dict),
        arabic=HadeethEncArabicDetail.model_validate(ar_dict),
        canonical_url="https://hadeethenc.com/en/browse/hadith/5913",
    )


def test_verifier_valid_bukhari_passes():
    """Valid Sahih al-Bukhari pair must pass with correct number extracted."""
    pair = create_mock_pair(reference_text="صحيح البخاري (6/ 192) (5027).\nفتح الباري (1/ 374).")
    result = verify_candidate_pair(pair)

    assert result.is_valid is True
    assert result.collection == "Sahih al-Bukhari"
    assert result.hadith_number == "5027"
    assert result.rejection_reason is None


def test_verifier_valid_muslim_passes():
    """Valid Sahih Muslim pair must pass with correct number extracted."""
    pair = create_mock_pair(
        en_attr_ar="رواه مسلم",
        ar_attr_ar="رواه مسلم",
        reference_text="صحيح مسلم (1/ 545) (791)",
    )
    result = verify_candidate_pair(pair)

    assert result.is_valid is True
    assert result.collection == "Sahih Muslim"
    assert result.hadith_number == "791"
    assert result.rejection_reason is None


def test_verifier_agreed_upon_passes():
    """Agreed Upon ('متفق عليه') narration must resolve to Agreed Upon collection."""
    pair = create_mock_pair(
        en_attr_ar="متفق عليه",
        ar_attr_ar="متفق عليه",
        reference_text="صحيح البخاري (5027)\nصحيح مسلم (791)",
    )
    result = verify_candidate_pair(pair)

    assert result.is_valid is True
    assert result.collection == "Agreed Upon (Al-Bukhari & Muslim)"
    assert result.hadith_number in ["5027", "791"]


def test_verifier_arabic_mismatch_fails_closed():
    """If embedded English Arabic does not match primary Arabic text, fail closed."""
    pair = create_mock_pair(
        en_arabic_text="نص مختلف عن الأصل تماما",
        ar_arabic_text="«خيركم من تعلم القرآن وعلمه»",
    )
    result = verify_candidate_pair(pair)

    assert result.is_valid is False
    assert "ERR_RECORD_MISMATCH" in str(result.rejection_reason)


def test_verifier_attribution_mismatch_fails():
    """If English record attribution does not match Arabic attribution, fail closed."""
    pair = create_mock_pair(
        en_attr_ar="رواه البخاري",
        ar_attr_ar="رواه مسلم",
    )
    result = verify_candidate_pair(pair)

    assert result.is_valid is False
    assert "ERR_RECORD_MISMATCH" in str(result.rejection_reason)


def test_verifier_unapproved_collection_fails():
    """Non-canonical or unapproved collections (e.g. Tirmidhi) must be rejected for V1."""
    pair = create_mock_pair(
        en_attr_ar="رواه الترمذي",
        ar_attr_ar="رواه الترمذي",
        reference_text="سنن الترمذي (5/ 175) (2909)",
    )
    result = verify_candidate_pair(pair)

    assert result.is_valid is False
    assert "ERR_UNAPPROVED_COLLECTION" in str(result.rejection_reason)


def test_verifier_missing_reference_fails():
    """If the Arabic reference citation is empty or whitespace, fail closed."""
    pair = create_mock_pair(reference_text="   ")
    result = verify_candidate_pair(pair)

    assert result.is_valid is False
    assert "ERR_MISSING_REFERENCE" in str(result.rejection_reason)


def test_verifier_bibliographic_citation_without_number_fails():
    """Verify that a record citing Bukhari/Muslim without an exact Hadith number is rejected fail-closed."""
    en = HadeethEncEnglishDetail(
        id="10112",
        title="Greatest Surah",
        hadeeth="Shall I teach you...",
        attribution="Narrated by Bukhari",
        grade="Authentic",
        hadeeth_ar="ألا أعلمك أعظم سورة",
        attribution_ar="رواه البخاري",
        grade_ar="صحيح",
    )
    ar = HadeethEncArabicDetail(
        id="10112",
        title="أعظم سورة",
        hadeeth="ألا أعلمك أعظم سورة",
        attribution="رواه البخاري",
        grade="صحيح",
        reference="صحيح البخاري –الجامع الصحيح- دار طوق النجاة، 1422هـ",  # Bibliographic only
    )
    pair = HadeethEncCandidatePair(source_id="10112", english=en, arabic=ar, canonical_url="url")
    res = verify_candidate_pair(pair)
    assert not res.is_valid
    assert "ERR_AMBIGUOUS_CITATION" in res.rejection_reason
