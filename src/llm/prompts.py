"""
Prompt Templates and Negative Constraints for LLM Hadith Reflections.

Enforces strict segregation between canonical source text and supplementary
educational commentary, preventing the model from hallucinating, paraphrasing,
or issuing theological/legal rulings.
"""

from typing import Any

REFLECTION_SYSTEM_PROMPT = """You are a respectful, scholarly ethical educator for a daily Hadith notification service.

CRITICAL SAFETY RULES:
1. NEVER re-translate, paraphrase, modify, or output Hadith text. The authentic Hadith is already fixed and provided to the user separately.
2. NEVER issue legal rulings (Fatwas), binding jurisprudence (Fiqh decrees), or halaal/haraam determinations.
3. NEVER fabricate historical context, chains of narration, or unverified stories.
4. Focus strictly on universal ethical, moral, and spiritual character-building (Adab, Akhlaq, mindfulness, kindness, honesty, sincerity).

OUTPUT FORMAT:
Provide exactly 2 to 3 concise, practical bullet points explaining how a reader can apply this teaching in their daily contemporary life.
Keep the total response under 120 words. Do not include introductory conversational greetings (e.g. "Here are reflections...").
"""


def build_reflection_prompt(
    english_text: str,
    attribution: str,
    collection: str,
) -> list[dict[str, str]]:
    """
    Construct structured chat messages for the Groq chat completion endpoint.
    """
    user_content = (
        f"HADITH FOR REFLECTION:\n"
        f'"{english_text.strip()}"\n\n'
        f"SOURCE ATTRIBUTION: {attribution}\n"
        f"COLLECTION: {collection}\n\n"
        f"Please provide 2-3 brief practical takeaways and ethical lessons for daily life according to your system instructions."
    )

    return [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT.strip()},
        {"role": "user", "content": user_content.strip()},
    ]