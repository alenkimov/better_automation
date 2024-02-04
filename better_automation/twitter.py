from pathlib import Path
from typing import Sequence, Iterable

from .utils import load_lines, write_lines

import twitter


def from_file(
        filepath: Path | str,
        *,
        separator: str = ":",
        fields: Sequence[str] = ("auth_token", "password", "email", "username"),
) -> list[twitter.Account]:
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
        accounts.append(twitter.Account(**data))
    return accounts


def to_file(
        filepath: Path | str,
        accounts: Iterable[twitter.Account],
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
