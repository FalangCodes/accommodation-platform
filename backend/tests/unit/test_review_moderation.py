"""Mocked provider and cache checks; execute with the Azure backend suite."""
import fnmatch
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from app.services import nlp_service, insight_engine, cache_service


def response():
    return dict(overall_sentiment="negative", sentiment_score=.9,
                is_spam=False, is_toxic=False, aspects=[])


def provider(monkeypatch, payload=None, error=None):
    calls = []
    def generate(**kwargs):
        calls.append((threading.get_ident(), kwargs))
        if error:
            raise error
        return SimpleNamespace(text=json.dumps(payload))
    monkeypatch.setattr(nlp_service, "_get_client", lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    # These tests isolate structured output. Shared Redis admission is exercised
    # separately by test_gemini_quota.py with real Redis and a mocked provider.
    async def ungated(factory, **kwargs):
        return await asyncio.to_thread(factory().models.generate_content, **kwargs)
    monkeypatch.setattr(nlp_service, "generate_content", ungated)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("spam,toxic,flagged", [(False,False,False),(True,False,True),(False,True,True),(True,True,True)])
async def test_spam_and_toxicity_are_independent_moderation_signals(monkeypatch, spam, toxic, flagged):
    payload=response()
    payload.update(is_spam=spam, is_toxic=toxic)
    calls=provider(monkeypatch,payload)
    result=await nlp_service.analyse_review(1,"The WiFi never works and management ignores repairs.")
    assert result["is_toxic"] is flagged
    assert bool(result["moderation_reason"]) is flagged
    assert len(calls)==1 and calls[0][0]!=threading.get_ident()
    assert "is_toxic" in calls[0][1]["config"].response_json_schema["required"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["missing_toxicity","bad_sentiment","bad_confidence","string_flag","bad_aspect","duplicate_aspect","empty_response"])
async def test_incomplete_or_invalid_analysis_cannot_clear_a_review(monkeypatch, invalid):
    payload=response()
    aspect=dict(aspect="safety",mentioned=True,sentiment="positive",confidence=.9,rationale="Security is mentioned.")
    if invalid=="missing_toxicity": payload.pop("is_toxic")
    elif invalid=="bad_sentiment": payload["overall_sentiment"]="safe"
    elif invalid=="bad_confidence": payload["sentiment_score"]=1.5
    elif invalid=="string_flag": payload["is_toxic"]="false"
    elif invalid=="bad_aspect": payload["aspects"]=[dict(aspect,aspect="unrecognised")]
    elif invalid=="duplicate_aspect": payload["aspects"]=[aspect,aspect]
    else: payload=None
    provider(monkeypatch,payload)
    assert await nlp_service.analyse_review(1,"A valid accommodation review requiring analysis.") is None


@pytest.mark.asyncio
async def test_quota_failure_returns_no_clearance(monkeypatch):
    provider(monkeypatch,error=RuntimeError("429 RESOURCE_EXHAUSTED; retry later"))
    assert await nlp_service.analyse_review(1,"The WiFi is unreliable.") is None


@pytest.mark.asyncio
async def test_moderation_receives_the_full_accepted_text(monkeypatch):
    body="An ordinary accommodation experience. "*70 + " Profane wording near the end."
    assert 2000<len(body)<=3000
    calls=provider(monkeypatch,response())
    await nlp_service.analyse_review(1,body)
    assert body in calls[0][1]["contents"]
    assert "obscene/profane wording" in calls[0][1]["config"].system_instruction


@pytest.mark.asyncio
async def test_immediate_insight_refresh_never_spends_gemini_quota(monkeypatch):
    from google import genai
    from app.core.config import settings
    calls=[]
    def forbidden(*args,**kwargs):
        calls.append(True)
        raise AssertionError("No summary provider calls during immediate refresh")
    monkeypatch.setattr(settings,"GEMINI_API_KEY","test-placeholder")
    monkeypatch.setattr(genai,"Client",forbidden)
    text=await insight_engine.generate_opinion("safety","mostly_positive",None,None,mention_count=3,positive_rate=100)
    assert text and calls==[]


@pytest.mark.asyncio
async def test_old_public_cache_is_retired_without_touching_view_or_auth_keys(monkeypatch):
    values={"reviews:1":json.dumps([{"body":"OLD FLAGGED REVIEW"}]),"views:1":"3","auth:example":"unchanged"}
    class Redis:
        async def get(self,key): return values.get(key)
        async def set(self,key,value,**kwargs): values[key]=value
        async def delete(self,*keys):
            for key in keys: values.pop(key,None)
        async def keys(self,pattern): return [key for key in values if fnmatch.fnmatchcase(key,pattern)]
        async def incr(self,key): values[key]=str(int(values.get(key,"0"))+1)
    async def redis(): return Redis()
    monkeypatch.setattr(cache_service,"get_redis",redis)
    assert await cache_service.cache_get("reviews:1") is None
    await cache_service.cache_set("reviews:1",[],60)
    assert await cache_service.cache_get("reviews:1")==[]
    await cache_service.cache_set("search:test",{"safe":True},60)
    await cache_service.cache_delete_pattern("search:*")
    assert await cache_service.cache_get("search:test") is None
    await cache_service.cache_set("analytics:1",{"total_views":3},60)
    await cache_service.increment_view(1)
    assert await cache_service.cache_get("analytics:1") is None
    await cache_service.cache_delete("reviews:1")
    assert await cache_service.cache_get("reviews:1") is None
    assert values["views:1"]=="4" and values["auth:example"]=="unchanged"
