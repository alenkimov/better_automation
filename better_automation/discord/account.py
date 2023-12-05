from enum import StrEnum

from pydantic import Field

from ..base import BaseAccount


class DiscordAccountStatus(StrEnum):
    BAD_TOKEN = "BAD_TOKEN"
    UNKNOWN = "UNKNOWN"
    BANNED = "BANNED"
    GOOD = "GOOD"


class DiscordAccount(BaseAccount):
    auth_token: str = Field(default=None, pattern=r"^[A-Za-z0-9+._-]{72}$")
    status: DiscordAccountStatus = DiscordAccountStatus.UNKNOWN,
    is_spammer: bool = False
    is_quarantined: bool = False
