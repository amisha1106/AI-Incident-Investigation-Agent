"""
API authentication utilities.
"""

from fastapi import Header, HTTPException, status

from config import API_KEY


def verify_api_key(
    x_api_key: str | None = Header(default=None),
) -> None:
    """
    Validate the API key supplied by the client.
    """

    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication is not configured.",
        )

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )