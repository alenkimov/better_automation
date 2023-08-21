import aiohttp
import pyuseragents
from aiohttp.typedefs import LooseHeaders


class BetterHTTPClient:
    def __init__(
            self,
            session: aiohttp.ClientSession,
            *,
            headers: LooseHeaders = None,
            useragent: str = None,
    ):
        self.session = session
        self._cookies = {}
        self._headers = headers or {}

        if useragent is None:
            useragent = pyuseragents.random()
        self.set_useragent(useragent)

    async def request(self, method: str, url, **kwargs):
        headers = self._headers.copy() if self._headers else {}
        cookies = self._cookies.copy() if self._cookies else {}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        if "cookies" in kwargs:
            cookies.update(kwargs.pop("cookies"))
        return await self.session._request(
            method,
            url,
            headers=headers,
            cookies=cookies,
            **kwargs,
        )

    def set_useragent(self, useragent: str):
        self.session.headers.update({'user-agent': useragent})
