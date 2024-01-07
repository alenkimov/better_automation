from datetime import datetime, timedelta

from pydantic import BaseModel


class AuthToken(BaseModel):
    auth_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def from_googleapis(cls, auth_token: str, refresh_token: str, expires_in: int):
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        return cls(auth_token=auth_token, refresh_token=refresh_token, expires_at=expires_at)

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at

    @property
    def short_auth_token(self) -> str:
        start = self.auth_token[:3]
        end = self.auth_token[-3:]
        return f"{start}**{end}"

    def __str__(self):
        return self.short_auth_token