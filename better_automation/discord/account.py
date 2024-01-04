from enum import StrEnum

from pydantic import Field

from ..base import BaseAccount

DISCORD_AUTH_TOKEN_PATTERN = r"^[A-Za-z0-9+._-]{72}$"


class DiscordAccountStatus(StrEnum):
    BAD_TOKEN = "BAD_TOKEN"  # (401, 403?)
    UNKNOWN   = "UNKNOWN"
    GOOD      = "GOOD"

    def __str__(self):
        return self.value


class DiscordAccount(BaseAccount):
    auth_token:     str = Field(default=None, pattern=DISCORD_AUTH_TOKEN_PATTERN)
    status:         DiscordAccountStatus = DiscordAccountStatus.UNKNOWN,
    is_spammer:     bool = False
    is_quarantined: bool = False
    phone:          str | None = None
    # TODO TOTP_secret
