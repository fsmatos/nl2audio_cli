from openai import OpenAI

from .logging import get_logger
from .validation import check_openai_api_key


def llm_clean_for_tts(
    text: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Rewrite newsletter text for better TTS quality."""
    logger = get_logger()

    try:
        api_key = check_openai_api_key()
        client = OpenAI(api_key=api_key)
        prompt = f"""Rewrite this newsletter text to be more natural and read-aloud friendly.
        Fix formatting, improve sentence flow, and make it sound conversational.
        Keep the same content and meaning, just improve readability.

        Text to rewrite:
        {text}"""

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content
        logger.info(
            f"LLM prep completed successfully with {model}, used {response.usage.total_tokens} tokens"
        )
        return result
    except Exception as e:
        logger.error(f"LLM prep failed: {e}. Using original text.")
        return text
