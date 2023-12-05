from base64 import b64decode
from pathlib import Path
from enum import StrEnum
import json

from pydantic import Field

from ..utils import load_lines
from ..base import BaseAccount


class TwitterAccountStatus(StrEnum):
    BAD_TOKEN = "BAD_TOKEN"  # (401) 32
    UNKNOWN = "UNKNOWN"
    SUSPENDED = "SUSPENDED"  # (403) 64, (200) 141
    LOCKED = "LOCKED"  # (403) 326
    GOOD = "GOOD"


class TwitterAccount(BaseAccount):
    auth_token: str = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    id: int | None = None
    ct0: str | None = None
    status: TwitterAccountStatus = TwitterAccountStatus.UNKNOWN

    @classmethod
    def from_cookies(
            cls,
            cookies: dict | str,
            *,
            base64: bool = False,
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

        account = cls(auth_token)
        account.ct0 = ct0
        return account

    @classmethod
    def from_file(
            cls,
            filepath: Path | str,
            *,
            cookies: bool = False,
            base64: bool = False,
    ) -> list["TwitterAccount"]:
        if cookies:
            return [cls.from_cookies(cookie, base64=base64)
                    for cookie in load_lines(filepath)]
        else:
            return [cls(auth_token) for auth_token in load_lines(filepath)]
