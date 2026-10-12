"""Atomic authentication request budgets shared by every backend worker."""
import hashlib
import hmac
import ipaddress
import logging

from fastapi import HTTPException, Request
from app.core.config import settings
from app.services.cache_service import get_redis

logger = logging.getLogger(__name__)

# Every attempt reserves a slot before checking credentials. Successful sign-in
# clears the account budget; IP budgets always count every attempt.
POLICIES = {
    "login": (900, 60, 5),
    "registration": (3600, 10, 3),
    "email": (3600, 30, 5),
    "token": (900, 30, None),
    "refresh": (60, 180, None),
}

CLAIM = """
local retry = 0
for i, key in ipairs(KEYS) do
  local count = tonumber(redis.call('GET', key) or '0')
  if count >= tonumber(ARGV[i + 1]) then
    retry = math.max(retry, math.max(1, redis.call('TTL', key)))
  end
end
if retry > 0 then return retry end
for _, key in ipairs(KEYS) do
  local count = redis.call('INCR', key)
  if count == 1 then redis.call('EXPIRE', key, ARGV[1]) end
end
return 0
"""


def client_ip(request: Request) -> str:
    """Only a configured proxy may supply the last address in its XFF chain.

    Nginx appends the real client address. The backend port must be accessible
    only to that proxy, and Uvicorn must leave the original peer untouched.
    """
    peer = request.client.host if request.client else "unknown"
    trusted = {value.strip() for value in settings.AUTH_TRUSTED_PROXY_IPS.split(",") if value.strip()}
    address = peer
    if peer in trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            address = forwarded.rsplit(",", 1)[-1].strip()
    try:
        parsed = ipaddress.ip_address(address)
        if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
            parsed = parsed.ipv4_mapped
        return str(parsed)
    except ValueError:
        return peer


def identity_digest(value: str) -> str:
    # Do not store raw email addresses or IPs in rate-limit Redis keys.
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


async def enforce_auth_limit(request: Request, policy: str, email: str | None = None):
    window, ip_budget, account_budget = POLICIES[policy]
    keys = [f"auth-limit:{policy}:ip:{identity_digest(client_ip(request))}"]
    budgets = [ip_budget]
    if email is not None and account_budget is not None:
        keys.append(f"auth-limit:{policy}:account:{identity_digest(str(email).strip().lower())}")
        budgets.append(account_budget)
    try:
        redis = await get_redis()
        retry = int(await redis.eval(CLAIM, len(keys), *keys, window, *budgets))
    except Exception:
        logger.error("Authentication rate-limit storage unavailable")
        raise HTTPException(status_code=503,
                            detail="Authentication is temporarily unavailable. Please try again shortly.",
                            headers={"Retry-After": "60"}) from None
    if retry:
        minutes = (retry + 59) // 60
        raise HTTPException(status_code=429,
                            detail=f"Too many attempts. Please try again in {minutes} minute(s).",
                            headers={"Retry-After": str(retry)})


async def reset_login_failures(email: str):
    """A successful sign-in starts a fresh account budget, but keeps IP usage."""
    key = f"auth-limit:login:account:{identity_digest(str(email).strip().lower())}"
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception:
        logger.error("Authentication failure counter could not be reset")
        raise HTTPException(status_code=503,
                            detail="Authentication is temporarily unavailable. Please try again shortly.",
                            headers={"Retry-After": "60"}) from None
