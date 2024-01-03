from curl_cffi import requests


class BaseAsyncSession(requests.AsyncSession):
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    DEFAULT_IMPERSONATE = requests.BrowserType.chrome110
    """
    Базовый асинхронная сессия:
        - Принимает прокси в стандартном URL-формате вместо словаря.
        - По умолчанию устанавливает версию браузера chrome110.
        - По умолчанию устанавливает user-agent под версию браузера chrome110.
    """

    def __init__(
            self,
            proxy: str = None,
            user_agent: str = None,
            **session_kwargs,
    ):
        proxies = {"http": proxy, "https": proxy}
        headers = session_kwargs.pop("headers", {})
        headers["user-agent"] = user_agent or self.DEFAULT_USER_AGENT
        session_kwargs["impersonate"] = session_kwargs.get("impersonate") or self.DEFAULT_IMPERSONATE
        super().__init__(
            proxies=proxies,
            headers=headers,
            **session_kwargs,
        )

    @property
    def user_agent(self) -> str:
        return self.headers["user-agent"]
