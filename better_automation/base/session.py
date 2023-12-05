from curl_cffi import requests

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"


class BaseAsyncSession(requests.AsyncSession):
    """
    Базовый асинхронная сессия:
        - Принимает прокси в стандартном URL-формате вместо словаря.
        - По умолчанию устанавливает версию браузера chrome110.
        - По умолчанию устанавливает user-agent под версию браузера chrome110.
    """

    def __init__(
            self,
            proxy: str = None,
            user_agent: str = DEFAULT_USER_AGENT,
            *,
            impersonate: requests.BrowserType = requests.BrowserType.chrome110,
            **session_kwargs,
    ):
        proxies = {"http": proxy, "https": proxy}
        headers = session_kwargs.pop("headers", {})
        headers["user-agent"] = user_agent
        super().__init__(
            proxies=proxies,
            headers=headers,
            impersonate=impersonate,
            **session_kwargs,
        )

    @property
    def user_agent(self) -> str:
        return self.headers["user-agent"]
