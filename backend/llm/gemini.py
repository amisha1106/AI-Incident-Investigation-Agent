"""
Gemini LLM wrapper using google-generativeai directly.

The wrapper handles Gemini quota exhaustion and temporary failures
gracefully. After a 429 quota error or temporary availability failure
is detected, subsequent calls are temporarily skipped so the
application can immediately use its deterministic fallback logic.

A circuit breaker is also used to prevent repeated calls when Gemini
continues failing.
"""

import time

import google.generativeai as genai
from loguru import logger

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
    GEMINI_REQUEST_TIMEOUT,
)

from infrastructure.resilience import (
    CircuitOpenError,
    gemini_circuit,
)


# ---------------------------------------------------------
# Gemini protection settings
# ---------------------------------------------------------

# Number of seconds during which Gemini calls are skipped after
# detecting quota exhaustion.
GEMINI_QUOTA_COOLDOWN_SECONDS = 60

# Number of seconds during which Gemini calls are skipped after
# a timeout / temporary availability failure.
GEMINI_FAILURE_COOLDOWN_SECONDS = 30


# Timestamp until which Gemini quota calls should be skipped.
_gemini_quota_cooldown_until = 0.0

# Timestamp until which Gemini calls should be skipped after
# a temporary failure.
_gemini_failure_cooldown_until = 0.0


# ---------------------------------------------------------
# Error detection
# ---------------------------------------------------------

def _is_gemini_quota_error(
    error: Exception,
) -> bool:
    """
    Detect Gemini quota/rate-limit errors.

    The installed google-generativeai client may surface quota
    exhaustion as ResourceExhausted / HTTP 429 errors.
    """

    error_text = str(error).lower()

    return (
        "429" in error_text
        or "quota exceeded" in error_text
        or "resourceexhausted" in error_text
        or "rate limit" in error_text
    )


def _is_gemini_temporary_failure(
    error: Exception,
) -> bool:
    """
    Detect temporary Gemini/network availability failures.
    """

    error_text = str(error).lower()

    return (
        "502" in error_text
        or "503" in error_text
        or "504" in error_text
        or "deadline expired" in error_text
        or "deadline exceeded" in error_text
        or "timeout" in error_text
        or "timed out" in error_text
        or "temporarily unavailable" in error_text
    )


# ---------------------------------------------------------
# Cooldown state
# ---------------------------------------------------------

def _gemini_quota_is_active() -> bool:
    """Return True when Gemini is temporarily disabled due to quota."""

    return (
        time.monotonic()
        < _gemini_quota_cooldown_until
    )


def _gemini_failure_is_active() -> bool:
    """Return True when Gemini is temporarily disabled after a failure."""

    return (
        time.monotonic()
        < _gemini_failure_cooldown_until
    )


def _activate_gemini_failure_cooldown() -> None:
    """
    Temporarily disable Gemini after a timeout or temporary failure.
    """

    global _gemini_failure_cooldown_until

    _gemini_failure_cooldown_until = (
        time.monotonic()
        + GEMINI_FAILURE_COOLDOWN_SECONDS
    )

    logger.warning(
        "[Gemini] Temporary failure cooldown activated for "
        f"{GEMINI_FAILURE_COOLDOWN_SECONDS} seconds."
    )


def _activate_gemini_quota_cooldown() -> None:
    """
    Temporarily disable Gemini after quota exhaustion.
    """

    global _gemini_quota_cooldown_until

    _gemini_quota_cooldown_until = (
        time.monotonic()
        + GEMINI_QUOTA_COOLDOWN_SECONDS
    )

    logger.warning(
        "[Gemini] Quota cooldown activated for "
        f"{GEMINI_QUOTA_COOLDOWN_SECONDS} seconds."
    )


# ---------------------------------------------------------
# Gemini client
# ---------------------------------------------------------

def get_gemini_client() -> genai.GenerativeModel:
    """
    Initialize and return the configured Gemini model.
    """

    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )

    genai.configure(
        api_key=GEMINI_API_KEY
    )

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config=genai.types.GenerationConfig(
            temperature=GEMINI_TEMPERATURE,
            max_output_tokens=GEMINI_MAX_TOKENS,
        ),
    )

    logger.info(
        f"Gemini client initialized: {GEMINI_MODEL}"
    )

    return model


# ---------------------------------------------------------
# Gemini request
# ---------------------------------------------------------

def call_gemini(
    prompt: str,
    system_prompt: str = "",
) -> str:
    """
    Make a single Gemini call.

    Protection layers:

    1. Quota cooldown
    2. Temporary failure cooldown
    3. Circuit breaker
    4. Gemini request
    5. Failure classification
    6. Circuit-breaker state update

    The caller is responsible for applying the appropriate
    deterministic fallback when this function raises.
    """

    # -----------------------------------------------------
    # Fast path: quota cooldown
    # -----------------------------------------------------

    if _gemini_quota_is_active():

        remaining = max(
            0,
            int(
                _gemini_quota_cooldown_until
                - time.monotonic()
            ),
        )

        logger.warning(
            "[Gemini] Skipping API call because quota cooldown "
            f"is active ({remaining}s remaining)."
        )

        raise RuntimeError(
            "Gemini quota cooldown is active. "
            "Using deterministic fallback."
        )

    # -----------------------------------------------------
    # Fast path: temporary failure cooldown
    # -----------------------------------------------------

    if _gemini_failure_is_active():

        remaining = max(
            0,
            int(
                _gemini_failure_cooldown_until
                - time.monotonic()
            ),
        )

        logger.warning(
            "[Gemini] Skipping API call because temporary "
            f"failure cooldown is active ({remaining}s remaining)."
        )

        raise RuntimeError(
            "Gemini temporary failure cooldown is active. "
            "Using deterministic fallback."
        )

    # -----------------------------------------------------
    # Circuit breaker
    # -----------------------------------------------------

    if not gemini_circuit.allow_request():

        logger.warning(
            "[Gemini] Circuit breaker is open. "
            "Skipping Gemini request."
        )

        raise CircuitOpenError(
            "Gemini circuit breaker is open. "
            "Using deterministic fallback."
        )

    # -----------------------------------------------------
    # Build client
    # -----------------------------------------------------

    client = get_gemini_client()

    full_prompt = (
        f"{system_prompt}\n\n{prompt}"
        if system_prompt
        else prompt
    )

    # -----------------------------------------------------
    # Gemini request
    # -----------------------------------------------------

    try:

        response = client.generate_content(
            full_prompt,
            request_options={
                "timeout": GEMINI_REQUEST_TIMEOUT,
            },
        )

        # -------------------------------------------------
        # Successful request
        # -------------------------------------------------

        gemini_circuit.record_success()

        logger.debug(
            "[Gemini] Request completed successfully."
        )

        return response.text.strip()

    except Exception as e:

        logger.error(
            f"Gemini call failed: {e}"
        )

        # -------------------------------------------------
        # Record circuit-breaker failure
        # -------------------------------------------------

        gemini_circuit.record_failure()

        logger.warning(
            "[Gemini] Circuit breaker state: "
            f"{gemini_circuit.state()}"
        )

        # -------------------------------------------------
        # Detect quota exhaustion
        # -------------------------------------------------

        if _is_gemini_quota_error(e):

            _activate_gemini_quota_cooldown()

        # -------------------------------------------------
        # Detect temporary availability failure
        # -------------------------------------------------

        elif _is_gemini_temporary_failure(e):

            _activate_gemini_failure_cooldown()

        # -------------------------------------------------
        # Re-raise so the Investigation Agent can use
        # deterministic fallback logic.
        # -------------------------------------------------

        raise