import asyncio
from typing import Iterable, Callable
from collections import defaultdict

from tqdm.asyncio import tqdm

from .http_client import CustomClientSession
from .proxy import Proxy


async def _process_accounts_with_session(
        accounts: Iterable,
        fn: Callable,
        *,
        proxy: Proxy = None,
):
    async with CustomClientSession(proxy=proxy) as session:
        for account in accounts:
            await fn(session, account)


async def bounded_gather(funcs, max_tasks=None):
    if max_tasks is None:
        return await tqdm.gather(*funcs)

    semaphore = asyncio.Semaphore(max_tasks)

    async def worker(fn):
        async with semaphore:
            return await fn

    return await tqdm.gather(*(worker(fn) for fn in funcs))


async def process_accounts_with_session(
        accounts: Iterable,
        proxies: Iterable[Proxy],
        fn: Callable,
        max_tasks: int = None,
):
    proxy_to_accounts: defaultdict[Proxy: list[accounts]] = defaultdict(list)
    if proxies:
        proxies = tuple(proxies)
        for i, account in enumerate(accounts):
            proxy = proxies[i % len(proxies)]
            proxy_to_accounts[proxy].append(account)
    else:
        proxy_to_accounts[None] = list(accounts)
    tasks = [_process_accounts_with_session(accounts, fn, proxy=proxy) for proxy, accounts in proxy_to_accounts.items()]
    await bounded_gather(tasks, max_tasks)
