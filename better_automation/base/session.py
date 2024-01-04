from curl_cffi import requests


class BaseAsyncSession(requests.AsyncSession):
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-US,en",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="110", "Google Chrome";v="110"',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
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
            **session_kwargs,
    ):
        proxies = {"http": proxy, "https": proxy}
        headers = session_kwargs["headers"] = session_kwargs.get("headers") or {}
        headers.update(self.DEFAULT_HEADERS)
        session_kwargs["impersonate"] = session_kwargs.get("impersonate") or self.DEFAULT_IMPERSONATE
        super().__init__(proxies=proxies, **session_kwargs)

    @property
    def user_agent(self) -> str:
        return self.headers["user-agent"]
