import json
from typing import Iterable
from itertools import islice


def chunks(elements: Iterable, n: int) -> Iterable[list]:
    """
    :param elements: Iterable
    :param n: Number per chunk
    :return: Yield successive n-sized chunks from elements
    """
    it = iter(elements)
    while True:
        chunk = list(islice(it, n))
        if not chunk:
            return
        yield chunk


def to_json(obj) -> str:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=True)


def curry_async(async_func):
    async def curried(*args, **kwargs):
        def bound_async_func(*args2, **kwargs2):
            return async_func(*(args + args2), **{**kwargs, **kwargs2})

        return bound_async_func

    return curried
