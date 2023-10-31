from datetime import datetime
from enum import Enum
import re
from functools import wraps, cached_property

AUTH_TOKEN_PATTERN = re.compile(r'^[a-f0-9]{40}$')


def is_valid_auth_token(auth_token: str) -> bool:
    return bool(AUTH_TOKEN_PATTERN.match(auth_token))


def parse_datetime(created_at_str: str) -> datetime:
    return datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')


class AccountStatus(Enum):
    BAD_TOKEN = "BAD_TOKEN"  # (401) 32
    UNKNOWN = "UNKNOWN"
    BANNED = "BANNED"  # (403) 64, (200) 141
    LOCKED = "LOCKED"  # (403) 326
    GOOD = "GOOD"


class Account:
    def __init__(
            self,
            auth_token: str,
            *,
            ct0: str = None,
            data: dict = None,
    ):
        self._auth_token = auth_token
        self.ct0 = ct0
        self.status: AccountStatus = AccountStatus.UNKNOWN

        self._data = None
        if data: self.data = data

    @property
    def auth_token(self) -> str:
        return self._auth_token

    @property
    def short_auth_token(self) -> str:
        first_four = self._auth_token[:4]
        last_four = self._auth_token[-4:]
        return f"{first_four}...{last_four}"

    def __repr__(self):
        return f"<TwitterAccount auth_token={self.short_auth_token} id={self.id} username={self.username}>"

    def __str__(self):
        return f"[{self.short_auth_token}]"

    def _ensure_data(self, method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            if not self._data:
                raise ValueError("Request user data first")
            return method(*args, **kwargs)

        return wrapper

    @property
    def data(self) -> dict | None:
        return self._data

    @data.setter
    def data(self, value: dict):
        self._data = value
        # Сбрасываем кешированные свойства
        self.__dict__.pop('id', None)
        self.__dict__.pop('created_at', None)

    @cached_property
    def id(self) -> int:
        return int(self._data["rest_id"])

    @cached_property
    def created_at(self) -> datetime:
        return parse_datetime(self._data["legacy"]["created_at"])

    @property
    def name(self) -> str:
        return self._data["legacy"]["name"]

    @property
    def username(self) -> str:
        return self._data["legacy"]["username"]

    # @classmethod
    # def from_cookies(
    #         cls,
    #         cookies: dict | str,
    #         base64: bool = False,
    #         *,
    #         ct0: str = None,
    #         user_agent: str = None,
    #         wait_on_rate_limit: bool = True,
    # ) -> "Account":
    #     raise NotImplementedError
