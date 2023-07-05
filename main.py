import asyncio
import logging
import subprocess
import time
from typing import Optional
import redis.asyncio as redis
import uvicorn
import requests
import random
from fastapi import Depends, FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Dict

from config import settings

app = FastAPI(dependencies=[Depends(RateLimiter(times=1, seconds=5))])
logger = logging.getLogger(__name__)
# .env variables can be validated and accessed from the config, here to set a log level
logging.basicConfig(level=settings.LOG_LEVEL.upper())


class UserResponse(BaseModel):
    user_id: Optional[str]
    email: Optional[str]
    name: Optional[str]

@app.get("/")
def root():
    # endpoints can be marked as `async def` if they do async work, otherwise use `def`
    # which will make the request run on a thread "awaited"
    return {"message": "Hello world. Welcome to FastAPI!"}


@app.post("/task/", response_model=UserResponse)
def current_user(card: str):
    # this endpoint's repsonse will match the UserResponse model
    postdata: Dict[str, str] = {"card": card}

    headersList = {
 "Accept": "*/*",
 "Content-Type": "application/json" 
}
    gate = random.randint(1,13)
    response = requests.post(f"https://cvv-fortis{gate}.up.railway.app/runserver/", json=postdata, headers=headersList)

    res = response.text
    return {"response": str(res)}

# @app.get("/cached", response_model=UserResponse)
# @cache(expire=30)  # cache for 30 seconds
# async def cached():
#     # for demonstration purposes, this is a slow endpoint that waits 5 seconds
#     await asyncio.sleep(5)
#     return {
#         "user_id": "0123456789",
#         "email": "cached@kylegill.com",
#         "name": "Vouch",
#     }


@app.on_event("startup")
async def startup():
    redis_url = f"redis://{settings.REDISUSER}:{settings.REDISPASSWORD}@{settings.REDISHOST}:{settings.REDISPORT}"
    try:
        red = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(red)
    except Exception:
        raise Exception(
            "Redis connection failed, ensure redis is running on the default port 6379"
        )

    FastAPICache.init(RedisBackend(red), prefix="fastapi-cache")


@app.middleware("http")
async def time_request(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["Server-Timing"] = str(process_time)
    logger.info(f"{request.method} {round(process_time, 5)}s {request.url}")
    return response


def dev():
    try:
        subprocess.check_output(["redis-cli", "ping"], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        logger.warning(
            "Redis is not already running, have you started it with redis-server?"
        )
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
