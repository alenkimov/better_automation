from base64 import b64decode
from enum import Enum
import json
import re

from pathlib import Path

from ..utils import load_lines
from .models import UserData

AUTH_TOKEN_PATTERN = re.compile(r'^[a-f0-9]{40}$')


def is_valid_auth_token(auth_token: str) -> bool:
    return bool(AUTH_TOKEN_PATTERN.match(auth_token))


class AccountStatus(Enum):
    BAD_TOKEN = "BAD_TOKEN"  # (401) 32
    UNKNOWN = "UNKNOWN"
    SUSPENDED = "SUSPENDED"  # (403) 64, (200) 141
    LOCKED = "LOCKED"  # (403) 326
    GOOD = "GOOD"


class Account:
    def __init__(
            self,
            auth_token: str,
            *,
            ct0: str = None,
            data: UserData = None,
            status: AccountStatus = AccountStatus.UNKNOWN
    ):
        if not is_valid_auth_token(auth_token):
            raise ValueError("Bad token")

        self._auth_token = auth_token
        self.ct0 = ct0
        self.data = data
        self.status = status

    @classmethod
    def from_cookies(
            cls,
            cookies: dict | str,
            *,
            base64: bool = False,
            data: UserData = None,
    ) -> "Account":
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
            raise ValueError("No auth_token found in cookies")

        return cls(auth_token, ct0=ct0, data=data)

    @classmethod
    def from_file(
            cls,
            filepath: Path | str,
            *,
            cookies: bool = False,
            base64: bool = False,
    ) -> list["Account"]:
        if cookies:
            return [cls.from_cookies(cookie, base64=base64)
                    for cookie in load_lines(filepath)]
        else:
            return [cls(auth_token) for auth_token in load_lines(filepath)]

    @property
    def auth_token(self) -> str:
        return self._auth_token

    @property
    def short_auth_token(self) -> str:
        first_four = self._auth_token[:4]
        last_four = self._auth_token[-4:]
        return f"{first_four}...{last_four}"

    def __repr__(self):
        return f"<TwitterAccount auth_token={self.short_auth_token}>"

    def __str__(self):
        return self.short_auth_token
