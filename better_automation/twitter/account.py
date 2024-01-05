from base64 import b64decode
from enum import StrEnum
import json

from pydantic import Field

from ..base import BaseAccount

TWITTER_AUTH_TOKEN_PATTERN = r"^[a-f0-9]{40}$"


class TwitterAccountStatus(StrEnum):
    BAD_TOKEN = "BAD_TOKEN"  # (401) 32
    UNKNOWN = "UNKNOWN"
    SUSPENDED = "SUSPENDED"  # (403) 64, (200) 141
    LOCKED = "LOCKED"  # (403) 326
    GOOD = "GOOD"

    def __str__(self):
        return self.value


class TwitterAccount(BaseAccount):
    auth_token: str = Field(default=None, pattern=TWITTER_AUTH_TOKEN_PATTERN)
    id: int | None = None
    ct0: str | None = None
    status: TwitterAccountStatus = TwitterAccountStatus.UNKNOWN

    @classmethod
    def from_cookies(
            cls,
            cookies: dict | str,
            *,
            base64: bool = False,
            **kwargs,
    ) -> "TwitterAccount":
        if base64:
            cookies = json.loads(b64decode(cookies).decode('utf-8'))
        elif isinstance(cookies, str):
            cookies = json.loads(cookies)

        auth_token = None
        ct0 = None

        for cookie in cookies:
            if cookie['name'] == 'auth_token':
                auth_token = cookie['value']
            elif cookie['name'] == 'ct0':
                ct0 = cookie['value']

        if auth_token is None:
            raise ValueError("auth_token not found in cookies.")

        ct0 = kwargs.pop("ct0", None) or ct0

        account = cls(auth_token, **kwargs)
        account.ct0 = ct0
        return account
