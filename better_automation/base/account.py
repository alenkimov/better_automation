from pathlib import Path
from typing import Sequence, Iterable

from pydantic import BaseModel

from ..utils import load_lines, write_lines


class BaseAccount(BaseModel):
    auth_token: str | None = None
    username:   str | None = None
    password:   str | None = None
    email:      str | None = None
    name:       str | None = None

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
        return f"{self.__class__.__name__}(auth_token={self.short_auth_token}, username={self.username})"

    def __str__(self):
        return self.short_auth_token

    @classmethod
    def from_file(
            cls,
            filepath: Path | str,
            *,
            separator: str = ":",
            fields: Sequence[str] = ("auth_token", "password", "email", "username"),
    ):
        """
        :param filepath: Путь до файла с данными об аккаунтах.
        :param separator: Разделитель между данными в строке.
        :param fields: Кортеж, содержащий имена полей в порядке их появления в строке.
         Должно содержать как минимум одно поле - auth_token: `("auth_token", )`
        :return: Список аккаунтов.
        """
        accounts = []
        for line in load_lines(filepath):
            data = dict(zip(fields, line.split(separator)))
            data.update({key: None for key in data if not data[key]})
            accounts.append(cls(**data))

        return accounts

    @classmethod
    def to_file(
            cls,
            filepath: Path | str,
            accounts: Iterable["BaseAccount"],
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
