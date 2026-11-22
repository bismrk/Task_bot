"""Telegram WebApp authentication and identity dependencies."""

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.config import Settings, get_settings
from src.models.user import User
from src.services.user_service import get_or_create_user


def validate_init_data(
    raw_init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
    allow_dev_mock: bool = False,
) -> dict[str, Any]:
    """Validate Telegram WebApp initData query string per official Telegram specification.

    Constructs data-check string, calculates expected HMAC-SHA256 signature,
    verifies with constant-time comparison, enforces expiration and future drift,
    and parses user payload.

    Args:
        raw_init_data: Raw URL-encoded initData string received from WebApp client.
        bot_token: Telegram bot token secret.
        max_age_seconds: Maximum allowed age for auth_date (defaults to 86400s / 24h).
        allow_dev_mock: Whether to accept development mock signatures outside Telegram.

    Returns:
        Dictionary of validated parameters with 'user' parsed as a Python dict.

    Raises:
        HTTPException: Status 401 Unauthorized with detailed description if verification fails.
    """
    if not raw_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    parsed_pairs = urllib.parse.parse_qsl(raw_init_data, keep_blank_values=True)
    parsed_dict: dict[str, str] = dict(parsed_pairs)

    # Allow mock developer authentication in local browser testing outside Telegram
    if allow_dev_mock and parsed_dict.get("hash") == "mock_dev_hash":
        user_raw = parsed_dict.get("user")
        if user_raw:
            try:
                user_obj = json.loads(user_raw)
                if not isinstance(user_obj, dict) or "id" not in user_obj:
                    user_obj = {"id": 1396728720, "first_name": "DevUser"}
            except Exception:
                user_obj = {"id": 1396728720, "first_name": "DevUser"}
        else:
            user_obj = {"id": 1396728720, "first_name": "DevUser"}
        result_data: dict[str, Any] = dict(parsed_dict)
        result_data["user"] = user_obj
        return result_data

    if "hash" not in parsed_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    received_hash = parsed_dict["hash"]

    if "auth_date" not in parsed_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid auth_date in initData",
        )

    try:
        auth_date = int(parsed_dict["auth_date"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid auth_date in initData",
        )

    current_timestamp = int(time.time())
    if current_timestamp - auth_date > max_age_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData has expired",
        )

    if auth_date - current_timestamp > 60:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram initData auth_date is in the future",
        )

    items_to_check = [
        f"{k}={v}" for k, v in sorted(parsed_dict.items()) if k != "hash"
    ]
    data_check_string = "\n".join(items_to_check)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData signature",
        )

    if "user" not in parsed_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid user object in initData",
        )

    try:
        user_obj = json.loads(parsed_dict["user"])
        if not isinstance(user_obj, dict) or "id" not in user_obj:
            raise ValueError
        int(user_obj["id"])
    except (json.JSONDecodeError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid user object in initData",
        )

    result_data: dict[str, Any] = dict(parsed_dict)
    result_data["user"] = user_obj
    return result_data


def get_current_user_id(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> int:
    """Extract and validate Telegram initData from request headers, returning the user telegram_id.

    Accepts 'Authorization: tma <data>', 'Authorization: Bearer <data>',
    or 'X-Telegram-Init-Data: <data>' headers.

    Raises:
        HTTPException: Status 401 Unauthorized if credentials are missing, malformed, or invalid.
    """
    raw_init_data: str | None = None
    auth_header = request.headers.get("Authorization")

    if auth_header is not None:
        parts = auth_header.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() in ("tma", "bearer") and parts[1].strip():
            raw_init_data = parts[1].strip()
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials",
            )
    elif "x-telegram-init-data" in request.headers:
        x_val = request.headers.get("x-telegram-init-data", "").strip()
        if x_val:
            raw_init_data = x_val
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication credentials",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication credentials",
        )

    bot_token = ""
    app_settings = getattr(request.app.state, "settings", None)
    if app_settings is not None:
        bot_token = getattr(app_settings, "BOT_TOKEN", "")
    if not bot_token and settings is not None:
        bot_token = getattr(settings, "BOT_TOKEN", "")

    is_debug = getattr(settings, "DEBUG", False) if settings is not None else False
    if not is_debug and app_settings is not None:
        is_debug = getattr(app_settings, "DEBUG", False)

    parsed_data = validate_init_data(
        raw_init_data=raw_init_data,
        bot_token=bot_token,
        allow_dev_mock=is_debug,
    )
    return int(parsed_data["user"]["id"])


async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Retrieve existing user or automatically provision a new user record.

    Ensures seamless onboarding for direct Mini App launches with default
    timezone 'Europe/Kyiv'.
    """
    user, _ = await get_or_create_user(session, telegram_id=user_id, timezone="Europe/Kyiv")
    return user


__all__ = [
    "get_current_user",
    "get_current_user_id",
    "validate_init_data",
]
