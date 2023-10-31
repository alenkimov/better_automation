import asyncio
from contextlib import asynccontextmanager

import aiohttp
from aiohttp_socks import ProxyConnector
from tqdm.asyncio import tqdm
import pyuseragents


def curry_async(async_func):
    async def curried(*args, **kwargs):
        def bound_async_func(*args2, **kwargs2):
            return async_func(*(args + args2), **{**kwargs, **kwargs2})

        return bound_async_func

    return curried


async def bounded_gather(*fs, max_tasks=None, **tqdm_kwargs):
    if max_tasks is None:
        return await tqdm.gather(fs, **tqdm_kwargs)

    semaphore = asyncio.Semaphore(max_tasks)

    async def worker(fn):
        async with semaphore:
            return await fn

    return await tqdm.gather(*(worker(fn) for fn in fs), **tqdm_kwargs)


@asynccontextmanager
async def proxy_session(proxy: str = None, user_agent: str = None) -> aiohttp.ClientSession:
    connector = ProxyConnector.from_url(proxy) if proxy else aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        session.headers["user-agent"] = user_agent or pyuseragents.random()
        yield session
