"""Atomic Redis limits and duplicate protection; no message or recipient is stored."""
import hashlib
from fastapi import HTTPException
from app.services.cache_service import get_redis

# A pending attempt is retained rather than retried automatically after a crash.
# SMTP acceptance and Redis completion cannot be made one atomic transaction.
CLAIM = """
local previous = redis.call('GET', KEYS[1])
if previous then
  if string.sub(previous, 1, 64) ~= ARGV[1] then return {4, 0} end
  local state = string.sub(previous, 66)
  if state == 'sent' then return {1, 0} end
  if state == 'pending' then return {2, 0} end
  return {3, 0}
end
local count = tonumber(redis.call('GET', KEYS[2]) or '0')
if count >= 5 then return {5, math.max(1, redis.call('TTL', KEYS[2]))} end
if redis.call('EXISTS', KEYS[3]) == 1 then return {5, math.max(1, redis.call('TTL', KEYS[3]))} end
local next_count = redis.call('INCR', KEYS[2])
if next_count == 1 then redis.call('EXPIRE', KEYS[2], 3600) end
redis.call('SET', KEYS[3], '1', 'EX', 60)
redis.call('SET', KEYS[1], ARGV[1] .. ':pending', 'EX', 86400)
return {0, 0}
"""
COMPLETE = """
if redis.call('GET', KEYS[1]) == ARGV[1] .. ':pending' then
  redis.call('SET', KEYS[1], ARGV[1] .. ':' .. ARGV[2], 'EX', 86400)
  return 1
end
return 0
"""


def message_digest(listing_id, message):
    return hashlib.sha256(f"{listing_id}\n{message}".encode("utf-8")).hexdigest()


async def claim_enquiry(student_user_id, listing_id, request_id, digest):
    request_key = f"enquiry:request:{student_user_id}:{request_id}"
    try:
        redis = await get_redis()
        state, retry_after = await redis.eval(CLAIM, 3, request_key,
            f"enquiry:hour:{student_user_id}", f"enquiry:cooldown:{student_user_id}:{listing_id}", digest)
    except Exception:
        raise HTTPException(status_code=503, detail="Enquiries are temporarily unavailable. Please try again later.") from None
    if state == 4:
        raise HTTPException(status_code=409, detail="This request ID was already used for a different enquiry.")
    if state == 2:
        raise HTTPException(status_code=409, detail="This enquiry is already being sent or its delivery is unconfirmed. Please wait before submitting another.")
    if state == 3:
        raise HTTPException(status_code=503, detail="Delivery could not be confirmed. Wait at least a minute before starting a new enquiry.")
    if state == 5:
        raise HTTPException(status_code=429, detail="Please wait before sending another enquiry. You can send up to five per hour.",
                            headers={"Retry-After": str(retry_after)})
    return request_key, state == 1


async def complete_enquiry(request_key, digest, state):
    redis = await get_redis()
    if not await redis.eval(COMPLETE, 1, request_key, digest, state):
        raise RuntimeError("Enquiry completion was not recorded")
