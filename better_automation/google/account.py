from enum import StrEnum
from pathlib import Path
from typing import Sequence, Iterable

from pydantic import BaseModel

from twitter.utils import hidden_value, load_lines, write_lines


def format_cookies(cookies):
    """
    # Фикс непонятно чего..
    """
    for cookie in cookies:
        if cookie.get('sameSite') == 'no_restriction':
            cookie['sameSite'] = 'None'


class GoogleAccountStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    BAD_COOKIES = "BAD_COOKIES"
    RECOVERY_EMAIL_REQUIRED = "RECOVERY_EMAIL_REQUIRED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    PHONE_VERIFICATION_REQUIRED = "PHONE_VERIFICATION_REQUIRED"
    BANNED = "BANNED"
    GOOD = "GOOD"

    def __str__(self):
        return self.value


class GoogleAccount(BaseModel):
    email:          str
    password:       str
    recovery_email: str | None = None
    # TODO Валидировать cookies
    cookies:        list | None = None
    status: GoogleAccountStatus = GoogleAccountStatus.UNKNOWN

    @property
    def hidden_password(self) -> str | None:
        return hidden_value(self.password) if self.password else None

    def __repr__(self):
        return f"{self.__class__.__name__}(email={self.email})"

    def __str__(self):
        return self.email


def from_file(
        filepath: Path | str,
        *,
        separator: str = ":",
        fields: Sequence[str] = ("email", "password", "recovery_email"),
) -> list[GoogleAccount]:
    """
    :param filepath: Путь до файла с данными об аккаунтах.
    :param separator: Разделитель между данными в строке.
    :param fields: Кортеж, содержащий имена полей в порядке их появления в строке.
     Должно содержать как минимум два поля - email и password: `("email", )`
    :return: Список аккаунтов.
    """
    accounts = []
    for line in load_lines(filepath):
        data = dict(zip(fields, line.split(separator)))
        data.update({key: None for key in data if not data[key]})
        accounts.append(GoogleAccount(**data))
    return accounts


def to_file(
        filepath: Path | str,
        accounts: Iterable[GoogleAccount],
        *,
        separator: str = ";",
        fields: Sequence[str] = ("email", "password", "recovery_email"),
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
