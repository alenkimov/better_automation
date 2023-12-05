from .session import BaseAsyncSession


class BaseClient:
    DEFAULT_HEADERS = None

    def __init__(self, **session_kwargs):
        self.session = BaseAsyncSession(
            headers=session_kwargs.pop("headers", None) or self.DEFAULT_HEADERS,
            **session_kwargs,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.close()

    def close(self):
        self.session.close()
