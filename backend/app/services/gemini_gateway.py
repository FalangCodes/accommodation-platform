"""Shared Gemini admission control. Deferred work remains in PostgreSQL."""
import asyncio
import logging
import re
import secrets
import time
import math
from google import genai
from google.genai import types
from app.core.config import settings
from app.services.cache_service import get_redis

logger = logging.getLogger(__name__)
MODEL = "gemini-3.6-flash"
QUOTA_SECONDS = 24 * 60 * 60
SPACING_MS = 13_000
KEYS = [f"gemini:{name}" for name in ("quota", "temporary", "inflight", "spacing", "failures")]
_quota_until = 0.0

CLAIM = """
local pause = math.max(redis.call('PTTL', KEYS[1]), redis.call('PTTL', KEYS[2]))
if pause > 0 then return pause end
local busy = math.max(redis.call('PTTL', KEYS[3]), redis.call('PTTL', KEYS[4]))
if busy > 0 then return busy end
redis.call('SET', KEYS[3], ARGV[1], 'PX', 120000)
redis.call('SET', KEYS[4], '1', 'PX', ARGV[2])
return 0
"""
FINISH = """
if ARGV[2] == 'quota' then
  redis.call('SET', KEYS[1], 'quota exhausted', 'EX', ARGV[3])
end
if redis.call('GET', KEYS[3]) ~= ARGV[1] then return 0 end
if ARGV[2] == 'temporary' then
  local count = redis.call('INCR', KEYS[5])
  redis.call('EXPIRE', KEYS[5], 86400)
  local delay = math.min(900, 60 * (2 ^ math.min(count - 1, 4)))
  redis.call('SET', KEYS[2], 'temporary failure', 'EX', delay)
elseif ARGV[2] == 'success' then
  redis.call('DEL', KEYS[5])
end
redis.call('SET', KEYS[4], '1', 'PX', ARGV[4])
redis.call('DEL', KEYS[3])
return 1
"""
PAUSE = "return math.max(0, redis.call('TTL', KEYS[1]), redis.call('TTL', KEYS[2]))"
RESTORE = """
if redis.call('TTL', KEYS[1]) < tonumber(ARGV[1]) then
  redis.call('SET', KEYS[1], 'quota exhausted', 'EX', ARGV[1])
end
return 1
"""


class GeminiDeferred(Exception):
    def __init__(self, message, retry_after=60, attempted=False):
        super().__init__(message)
        self.retry_after = retry_after
        self.attempted = attempted


def create_client():
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(
        timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)))


def is_quota_error(error):
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    return str(code) == "429" or bool(re.search(r"\b429\b|\bRESOURCE_EXHAUSTED\b", str(error)))


async def pause_seconds():
    """Fail closed if the shared gate cannot be read; never probe Gemini then."""
    try:
        redis = await get_redis()
        await _restore_quota(redis)
        return int(await redis.eval(PAUSE, 2, *KEYS[:2]))
    except Exception:
        logger.warning("[Gemini] Shared admission storage unavailable; deferring work")
        return 60


async def _restore_quota(redis):
    # Retain the quota decision locally if Redis briefly fails during the write,
    # and republish the remaining pause when the shared store recovers.
    remaining = math.ceil(_quota_until - time.monotonic())
    if remaining > 0:
        await redis.eval(RESTORE, 1, KEYS[0], remaining)


async def generate_content(client_factory, **kwargs):
    global _quota_until
    token = secrets.token_hex(16)
    try:
        redis = await get_redis()
        await _restore_quota(redis)
        delay = int(await redis.eval(CLAIM, 4, *KEYS[:4], token, SPACING_MS))
    except Exception:
        raise GeminiDeferred("Shared admission storage unavailable; review remains pending") from None
    if delay:
        seconds = (delay + 999) // 1000
        raise GeminiDeferred(f"Shared cooldown or request pacing active; retry in at least {seconds}s", retry_after=seconds)
    outcome = "success"
    try:
        # No SDK retry loop: application scheduling owns retries and cooldowns.
        client = client_factory()
        return await asyncio.to_thread(client.models.generate_content, **kwargs)
    except asyncio.CancelledError:
        # Cancelling to_thread does not stop its HTTP request. Retain the lease
        # until expiry so a scheduler shutdown cannot start an overlapping call.
        outcome = "cancelled"
        raise
    except Exception as error:
        outcome = "quota" if is_quota_error(error) else "temporary"
        if outcome == "quota":
            _quota_until = time.monotonic() + QUOTA_SECONDS
            logger.warning("[Gemini] Quota exhausted; pausing all Gemini requests for 24 hours")
        else:
            logger.warning("[Gemini] Provider failure; applying bounded shared backoff")
        # Do not log provider payloads, prompts or credentials.
        raise GeminiDeferred("Quota cooldown active" if outcome == "quota" else "Temporary Gemini failure",
                             retry_after=QUOTA_SECONDS if outcome == "quota" else 60, attempted=True) from None
    finally:
        if outcome != "cancelled":
            try:
                finished = await redis.eval(FINISH, 5, *KEYS, token, outcome, QUOTA_SECONDS, SPACING_MS)
                if not finished:
                    logger.error("[Gemini] Request lease expired before completion")
            except Exception:
                # Keep the lease in place rather than allowing an immediate burst.
                logger.error("[Gemini] Could not persist request outcome; shared gate must recover before retry")
