from enum import StrEnum
from pathlib import Path
from typing import Sequence, Iterable

from pydantic import Field, BaseModel
from twitter.utils import hidden_value, load_lines, write_lines


class DiscordAccountStatus(StrEnum):
    BAD_TOKEN = "BAD_TOKEN"  # (401, 403?)
    UNKNOWN   = "UNKNOWN"
    GOOD      = "GOOD"

    def __str__(self):
        return self.value


class DiscordAccount(BaseModel):
    auth_token: str = Field(default=None, pattern=r"^[A-Za-z0-9+._-]{72}$")
    username:   str | None = None
    password:   str | None = None
    email:      str | None = None
    name:       str | None = None

    status:         DiscordAccountStatus = DiscordAccountStatus.UNKNOWN
    is_spammer:     bool = False
    is_quarantined: bool = False
    phone:          str | None = None

    @property
    def hidden_auth_token(self) -> str | None:
        return hidden_value(self.auth_token) if self.auth_token else None

    @property
    def hidden_password(self) -> str | None:
        return hidden_value(self.password) if self.password else None

    def __repr__(self):
        return f"{self.__class__.__name__}(auth_token={self.short_auth_token}, username={self.username})"

    def __str__(self):
        return self.hidden_auth_token


def from_file(
        filepath: Path | str,
        *,
        separator: str = ":",
        fields: Sequence[str] = ("auth_token", "password", "email", "username"),
) -> list[DiscordAccount]:
    """
    :param filepath: Путь до файла с данными об аккаунтах.
    :param separator: Разделитель между данными в строке.
    :param fields: Кортеж, содержащий имена полей в порядке их появления в строке.
     Должно содержать как минимум одно поле - auth_token: `("auth_token", )`
    :return: Список Twitter аккаунтов.
    """
    accounts = []
    for line in load_lines(filepath):
        data = dict(zip(fields, line.split(separator)))
        data.update({key: None for key in data if not data[key]})
        accounts.append(DiscordAccount(**data))
    return accounts


def to_file(
        filepath: Path | str,
        accounts: Iterable[DiscordAccount],
        *,
        separator: str = ":",
        fields: Sequence[str] = ("auth_token", "password", "email", "username"),
):
    lines = []
    for account in accounts:
        account_data = []
        for field_name in fields:
            field = getattr(account, field_name)
            field = field if field is not None else ""
            account_data.append(field)
        lines.append(separator.join(account_data))
    write_lines(filepath, lines)