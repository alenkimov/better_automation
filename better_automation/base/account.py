from pathlib import Path
from pydantic import BaseModel

from ..utils import load_lines


class BaseAccount(BaseModel):
    auth_token: str | None = None
    username: str | None = None
    password: str | None = None
    email: str | None = None
    name: str | None = None

    def __init__(
            self,
            auth_token: str,
            *,
            username: str = None,
            password: str = None,
            email: str = None,
    ):
        super().__init__(
            auth_token=auth_token,
            username=username,
            password=password,
            email=email,
        )

    @property
    def short_auth_token(self) -> str:
        start = self.auth_token[:3]
        end = self.auth_token[-3:]
        return f"{start}**{end}"

    @property
    def short_password(self) -> str:
        start = self.password[:2]
        end = self.password[-2:]
        return f"{start}**{end}"

    def __repr__(self):
        return f"<{self.__class__.__name__} auth_token={self.short_auth_token}>"

    def __str__(self):
        return self.short_auth_token

    @classmethod
    def from_file(
            cls,
            filepath: Path | str,
    ) -> list["BaseAccount"]:
        return [cls(auth_token) for auth_token in load_lines(filepath)]
