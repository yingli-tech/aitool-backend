"""One retry budget per AI operation; never log provider messages or payloads."""
import json
import logging
import math
import random
import time
from email.utils import parsedate_to_datetime

from openai import APIConnectionError, APIError

SAFE_MESSAGE = "AI service is temporarily unavailable. Please try again shortly."
MAX_ATTEMPTS = 3
logger = logging.getLogger(__name__)
PERMANENT_CODES = {
    "credit_balance_exhausted", "project_spend_limit_exceeded",
    "organization_spend_limit_exceeded", "organization_usage_limit_exceeded",
    "insufficient_quota", "billing_hard_limit_reached",
}


class AIServiceError(Exception):
    def __init__(self):
        super().__init__(SAFE_MESSAGE)


class AIValidationError(ValueError):
    """Messages must describe validation rules, never include response values."""


def _error_fields(error):
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        body = body.get("error", body)
    body = body if isinstance(body, dict) else {}
    return (getattr(error, "code", None) or body.get("code"),
            getattr(error, "type", None) or body.get("type"))


def _retryable(error):
    if isinstance(error, (APIConnectionError, AIValidationError)):
        return True
    status = getattr(error, "status_code", None)
    if status == 429:
        code, kind = _error_fields(error)
        if code in PERMANENT_CODES or kind in PERMANENT_CODES:
            return False
        # Unknown quota errors are not assumed transient.
        return code in (None, "rate_limit_exceeded") and kind in (
            None, "rate_limit_exceeded", "requests", "tokens")
    return status in (500, 503)


def _retry_after(error):
    response = getattr(error, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, delay) if math.isfinite(delay) else None


def run_ai_operation(operation, action):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return action()
        except (APIError, AIValidationError) as error:
            code, _ = _error_fields(error)
            retry = attempt < MAX_ATTEMPTS and _retryable(error)
            logger.warning(json.dumps({
                "operation": operation, "attempt": attempt,
                "error_type": type(error).__name__,
                "http_status": getattr(error, "status_code", None),
                "openai_error_code": code,
                "validation_error": str(error) if isinstance(error, AIValidationError) else None,
                "retry": retry,
            }))
            if not retry:
                raise AIServiceError() from error
            delay = _retry_after(error)
            if delay is None:
                delay = 2 ** (attempt - 1) + random.uniform(0, 1)
            time.sleep(delay)
