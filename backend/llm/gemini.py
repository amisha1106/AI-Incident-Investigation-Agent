"""
Gemini LLM wrapper using google-generativeai directly.
Uses gemini-1.5-flash (free tier, 15 RPM / 1M TPD limit).
"""

import google.generativeai as genai
from loguru import logger
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_MAX_TOKENS


def get_gemini_client() -> genai.GenerativeModel:
    """Initialize and return Gemini model."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/app/apikey"
        )
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config=genai.types.GenerationConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_TOKENS,
        ),
    )
    logger.info(f"Gemini client initialized: {GEMINI_MODEL}")
    return model


def call_gemini(prompt: str, system_prompt: str = "") -> str:
    """
    Single call to Gemini. Returns text response.
    Handles free-tier rate limit gracefully.
    """
    try:
        client = get_gemini_client()
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = client.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        raise
